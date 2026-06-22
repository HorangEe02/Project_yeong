"""Local Markdown WIKI retrieval for safe Ollama explanation context.

The lexical scanner (:func:`retrieve_llm_wiki_context`) is the historical,
file-system-only contract and stays unchanged. :func:`retrieve_llm_wiki_context_db`
adds an opt-in pgvector semantic path (vector / hybrid) with entity-link boosting
that always falls back to the lexical result, so the explanation pipeline keeps
working when embeddings, pgvector, or the wiki tables are unavailable.
"""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any

import httpx
from sqlalchemy import text

from src.config import Settings
from src.db.session import get_sessionmaker
from src.llm.ollama import validate_local_ollama_settings
from src.services.wiki_embedding_targets import EMBEDDING_TABLES, get_target

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

MAX_WIKI_FILE_BYTES = 1_000_000
MAX_QUERY_TERMS = 24
MIN_QUERY_TERM_CHARS = 2
TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣][0-9A-Za-z가-힣_.+/-]*")
STOP_TERMS = {
    "and",
    "the",
    "with",
    "기준",
    "내용",
    "사용자",
    "설명",
    "정보",
    "섭취",
    "주의",
    "확인",
}

# Minimum candidate pool fetched from pgvector before trimming to
# ``llm_wiki_max_sources``; oversampling keeps room for entity boosts and the
# hybrid lexical merge to reorder results meaningfully.
MIN_VECTOR_CANDIDATE_POOL = 12
VECTOR_CANDIDATE_MULTIPLIER = 3
# Additive score bonus applied to a vector citation whose document also appears
# in the lexical result set (hybrid mode). Small so a strong vector-only hit can
# still outrank a weak lexical-overlap hit.
HYBRID_LEXICAL_BONUS = 0.05
# Additive score bonus applied to a citation explicitly linked to a requested
# entity key via ``entity_wiki_links``. Large enough to float a linked source
# above unrelated vector neighbours.
ENTITY_LINK_BONUS = 0.25
# Weight ceiling for lexical-ONLY documents in the hybrid merge. Raw lexical
# scores are term-frequency sums (often tens) and would otherwise dominate the
# vector cosine scale (~0-1) and entity boost. Lexical-only hits are normalized
# into [0, this] so they still surface but never outrank curated / entity-linked
# semantic hits.
LEXICAL_ONLY_WEIGHT = 0.55
EMBEDDING_REQUEST_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True)
class LlmWikiCitation:
    """One sanitized source citation retrieved from local Markdown WIKI.

    Attributes:
        title: Human-readable Markdown document title.
        source_path: Relative path from the configured WIKI root.
        heading: Nearest matching heading, when available.
        excerpt: Bounded excerpt used as local LLM grounding context.
        score: Deterministic lexical relevance score.
    """

    title: str
    source_path: str
    heading: str | None
    excerpt: str
    score: float


@dataclass(frozen=True)
class LlmWikiRetrievalResult:
    """Sanitized WIKI retrieval result.

    Attributes:
        query: Bounded query string derived from structured analysis fields.
        citations: Retrieved source citations.
    """

    query: str
    citations: tuple[LlmWikiCitation, ...]


def retrieve_llm_wiki_context(query: str, settings: Settings) -> LlmWikiRetrievalResult:
    """Retrieve local Markdown WIKI excerpts for Gemma 4 explanations.

    Args:
        query: Structured, sanitized text assembled by the caller.
        settings: Runtime settings with WIKI retrieval controls.

    Returns:
        Bounded citations from local Markdown files. Missing or disabled WIKI
        configuration returns an empty result instead of failing the explanation.
    """
    bounded_query = _collapse_whitespace(query)[:800]
    if (
        not settings.llm_wiki_retrieval_enabled
        or settings.llm_wiki_max_sources <= 0
        or not bounded_query
    ):
        return LlmWikiRetrievalResult(query=bounded_query, citations=())

    wiki_root = settings.llm_wiki_path
    if not wiki_root.is_dir():
        return LlmWikiRetrievalResult(query=bounded_query, citations=())

    terms = _query_terms(bounded_query)
    if not terms:
        return LlmWikiRetrievalResult(query=bounded_query, citations=())

    citations: list[LlmWikiCitation] = []
    for markdown_path in _iter_markdown_files(wiki_root):
        content = _read_markdown(markdown_path)
        if content is None:
            continue
        citation = _score_markdown(
            path=markdown_path,
            root=wiki_root,
            content=content,
            terms=terms,
            excerpt_chars=settings.llm_wiki_excerpt_chars,
        )
        if citation is not None:
            citations.append(citation)

    citations.sort(key=lambda item: (-item.score, item.source_path, item.heading or ""))
    return LlmWikiRetrievalResult(
        query=bounded_query,
        citations=tuple(citations[: settings.llm_wiki_max_sources]),
    )


async def retrieve_llm_wiki_context_db(
    query: str,
    settings: Settings,
    *,
    entity_keys: tuple[str, ...] = (),
) -> LlmWikiRetrievalResult:
    """Retrieve WIKI citations using pgvector semantic search with lexical fallback.

    This is the database-backed counterpart to :func:`retrieve_llm_wiki_context`.
    It preserves the same :class:`LlmWikiRetrievalResult` / :class:`LlmWikiCitation`
    contract, including relative ``source_path`` values, so callers can swap to it
    without changing how citations are exposed to the client.

    Behaviour by mode:

    - ``enable_wiki_vector_rag=False`` or ``llm_wiki_retrieval_mode == "lexical"``:
      delegate straight to the lexical scanner.
    - ``"vector"``: embed the query through Ollama and rank wiki chunks by cosine
      distance on ``wiki_chunk_embeddings``.
    - ``"hybrid"``: as ``"vector"``, then merge the lexical result (dedupe by
      ``source_path``, add a small bonus to documents present in both).

    When ``entity_keys`` resolve to ``entity_wiki_links`` rows, the linked
    documents are boosted; any linked document missing from the vector candidate
    pool has its top chunk fetched and appended.

    This path is intentionally fail-open: on any embedding or database error, or
    when the vector search yields no hits, it returns the lexical result instead
    of failing the explanation. Such fallbacks are logged at debug level (they are
    an expected degraded mode, not a swallowed bug).

    Args:
        query: Structured, sanitized text assembled by the caller.
        settings: Runtime settings with WIKI retrieval controls.
        entity_keys: Optional DB entity keys (e.g. supplement ``category_key`` or
            food ``cuisine_code``) used to boost explicitly linked documents.

    Returns:
        Bounded citations with relative source paths. Disabled, lexical-mode, or
        failed semantic retrieval all degrade to the lexical result.
    """
    lexical_result = retrieve_llm_wiki_context(query, settings)
    if not settings.enable_wiki_vector_rag or settings.llm_wiki_retrieval_mode == "lexical":
        return lexical_result
    if not lexical_result.query or settings.llm_wiki_max_sources <= 0:
        return lexical_result

    citations = await _semantic_citations(
        lexical_result.query,
        settings,
        entity_keys=tuple(dict.fromkeys(key for key in entity_keys if key)),
    )
    if citations is None:
        return lexical_result

    if settings.llm_wiki_retrieval_mode == "hybrid":
        citations = _merge_lexical(citations, lexical_result.citations)

    citations.sort(key=lambda item: (-item.score, item.source_path, item.heading or ""))
    return LlmWikiRetrievalResult(
        query=lexical_result.query,
        citations=tuple(citations[: settings.llm_wiki_max_sources]),
    )


async def _semantic_citations(
    bounded_query: str,
    settings: Settings,
    *,
    entity_keys: tuple[str, ...],
) -> list[LlmWikiCitation] | None:
    """Embed the query and run the pgvector candidate search.

    Centralizes the fail-open boundary so the public function keeps a single
    fallback path. Every degraded outcome is logged at debug level; ``None``
    signals the caller to use the lexical result instead.

    Args:
        bounded_query: Bounded, sanitized query text.
        settings: Runtime settings with embedding and retrieval controls.
        entity_keys: Deduplicated, non-empty entity keys for link boosting.

    Returns:
        Candidate citations, or ``None`` when embedding, the DB query, or the
        result set make the semantic path unusable.
    """
    try:
        embedding = await _embed_query(bounded_query, settings)
    except (httpx.HTTPError, OSError, ValueError, RuntimeError) as exc:
        logger.debug("WIKI vector retrieval falling back to lexical (embedding failed): %s", exc)
        return None
    if not embedding:
        logger.debug("WIKI vector retrieval falling back to lexical (empty embedding).")
        return None

    try:
        citations = await _vector_citations(
            embedding=embedding,
            settings=settings,
            entity_keys=entity_keys,
        )
    except Exception as exc:
        # Fail-open by design (see function docstring): any DB/pgvector error
        # degrades to the lexical result rather than failing the explanation.
        logger.debug("WIKI vector retrieval falling back to lexical (db query failed): %s", exc)
        return None
    if not citations:
        logger.debug("WIKI vector retrieval falling back to lexical (no vector hits).")
        return None
    return citations


def _apply_query_prompt(query: str, model: str) -> str:
    """Prepend the model's documented query prompt prefix, when one is defined.

    Instruction-tuned embedders (e.g. ``embeddinggemma``) expect a query-side
    prefix that must match the document-side prefix used at ingestion. Unknown
    models embed raw text; the table lookup in the vector query is what gates an
    unregistered model to the lexical fallback.

    Args:
        query: Bounded, sanitized query text.
        model: Configured WIKI embedding model name.

    Returns:
        The query text with the model's query prefix applied, or unchanged when
        the model has no registered prefix.
    """
    try:
        return get_target(model).format_query(query)
    except KeyError:
        return query


async def _embed_query(query: str, settings: Settings) -> tuple[float, ...]:
    """Embed a bounded query through the local Ollama embeddings API.

    The configured ``wiki_embedding_model`` selects both the model and its
    documented query prompt prefix, so queries are embedded the same way the
    matching documents were at ingestion.

    Args:
        query: Bounded, sanitized query text.
        settings: Runtime settings providing the Ollama host and embedding model.

    Returns:
        The embedding vector, or an empty tuple when the response has no vector.

    Raises:
        OllamaConfigurationError: If the configured runtime is not an allowed
            local Ollama endpoint.
        httpx.HTTPError: If the local embeddings request fails.
        ValueError: If the response body is not a usable JSON object.
    """
    validate_local_ollama_settings(settings)
    endpoint = f"{settings.ollama_base_url.rstrip('/')}/api/embeddings"
    prompt = _apply_query_prompt(query, settings.wiki_embedding_model)
    payload = {"model": settings.wiki_embedding_model, "prompt": prompt}
    async with httpx.AsyncClient() as client:
        response = await client.post(
            endpoint,
            json=payload,
            timeout=EMBEDDING_REQUEST_TIMEOUT_SECONDS,
        )
    response.raise_for_status()
    body = response.json()
    if not isinstance(body, dict):
        raise ValueError("Ollama embeddings response was not a JSON object.")
    return _coerce_embedding(body.get("embedding"))


def _coerce_embedding(value: Any) -> tuple[float, ...]:
    """Coerce a raw embedding payload into a finite float vector.

    Args:
        value: Candidate embedding sequence from the embeddings API.

    Returns:
        Finite embedding values, or an empty tuple when the payload is unusable.
    """
    if not isinstance(value, list) or not value:
        return ()
    vector: list[float] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, int | float):
            return ()
        numeric = float(item)
        if not math.isfinite(numeric):
            return ()
        vector.append(numeric)
    return tuple(vector)


async def _vector_citations(
    *,
    embedding: tuple[float, ...],
    settings: Settings,
    entity_keys: tuple[str, ...],
) -> list[LlmWikiCitation]:
    """Run cosine top-K retrieval and entity boosting in one short read session.

    Args:
        embedding: Query embedding vector.
        settings: Runtime settings with source and excerpt bounds.
        entity_keys: Deduplicated, non-empty entity keys for link boosting.

    Returns:
        Candidate citations ranked by vector similarity, including any boosted or
        injected entity-linked documents. Empty when no chunks match.

    Raises:
        KeyError: If ``wiki_embedding_model`` is not a registered model. The caller
            treats this as a fail-open to the lexical result.
    """
    table = get_target(settings.wiki_embedding_model).table
    candidate_pool = max(
        settings.llm_wiki_max_sources * VECTOR_CANDIDATE_MULTIPLIER,
        MIN_VECTOR_CANDIDATE_POOL,
    )
    embedding_literal = _vector_literal(embedding)
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        rows = await _fetch_vector_rows(
            session,
            embedding_literal=embedding_literal,
            limit=candidate_pool,
            table=table,
        )
        citations = [
            _citation_from_row(row, excerpt_chars=settings.llm_wiki_excerpt_chars) for row in rows
        ]
        if entity_keys:
            citations = await _apply_entity_boost(
                session,
                citations=citations,
                entity_keys=entity_keys,
                embedding_literal=embedding_literal,
                excerpt_chars=settings.llm_wiki_excerpt_chars,
                table=table,
            )
    return citations


def _require_embedding_table(table: str) -> str:
    """Return the table name only if it is a registry-owned embedding table.

    The model-selected table is interpolated into SQL — pgvector columns are
    dimension-typed, so the table cannot be a bound parameter — so it must be
    validated against the registry allowlist before it reaches a query string.

    Args:
        table: Candidate embedding table name.

    Returns:
        The validated table name.

    Raises:
        ValueError: If the table is not in the registry allowlist.
    """
    if table not in EMBEDDING_TABLES:
        raise ValueError(f"refusing to query non-allowlisted embedding table {table!r}")
    return table


async def _fetch_vector_rows(
    session: AsyncSession,
    *,
    embedding_literal: str,
    limit: int,
    table: str,
) -> Sequence[Any]:
    """Fetch the nearest wiki chunks for a query embedding.

    Args:
        session: Open async read session.
        embedding_literal: pgvector text literal for the query embedding.
        limit: Maximum candidate rows to fetch.
        table: Model-selected embedding table (registry-allowlisted).

    Returns:
        Result rows joining chunk, document, and cosine distance.
    """
    safe_table = _require_embedding_table(table)
    statement = text(f"""
        SELECT
            d.title AS title,
            d.rel_path AS rel_path,
            c.heading AS heading,
            c.content AS content,
            (e.embedding OPERATOR(extensions.<=>) CAST(:embedding AS extensions.vector)) AS distance
        FROM {safe_table} AS e
        JOIN wiki_chunks AS c ON c.id = e.chunk_id
        JOIN wiki_documents AS d ON d.id = c.document_id
        ORDER BY e.embedding OPERATOR(extensions.<=>) CAST(:embedding AS extensions.vector) ASC
        LIMIT :limit
        """)
    result = await session.execute(
        statement,
        {"embedding": embedding_literal, "limit": limit},
    )
    return result.all()


async def _apply_entity_boost(
    session: AsyncSession,
    *,
    citations: list[LlmWikiCitation],
    entity_keys: tuple[str, ...],
    embedding_literal: str,
    excerpt_chars: int,
    table: str,
) -> list[LlmWikiCitation]:
    """Boost and, when needed, inject documents linked to requested entities.

    Args:
        session: Open async read session.
        citations: Vector candidate citations to boost in place.
        entity_keys: Deduplicated, non-empty entity keys.
        embedding_literal: Query embedding literal used to rank injected chunks.
        excerpt_chars: Maximum excerpt length for injected citations.
        table: Model-selected embedding table to rank injected chunks against.

    Returns:
        Citations with linked-document bonuses applied and any missing linked
        documents appended via their best-matching chunk.
    """
    linked_slugs = await _linked_slugs(session, entity_keys)
    if not linked_slugs:
        return citations

    present_slugs: set[str] = set()
    boosted: list[LlmWikiCitation] = []
    for citation in citations:
        slug = _slug_from_source_path(citation.source_path)
        present_slugs.add(slug)
        if slug in linked_slugs:
            boosted.append(replace(citation, score=round(citation.score + ENTITY_LINK_BONUS, 4)))
        else:
            boosted.append(citation)

    missing_slugs = [slug for slug in linked_slugs if slug not in present_slugs]
    if missing_slugs:
        injected = await _fetch_linked_chunks(
            session,
            slugs=tuple(missing_slugs),
            embedding_literal=embedding_literal,
            excerpt_chars=excerpt_chars,
            table=table,
        )
        boosted.extend(injected)
    return boosted


async def _linked_slugs(session: AsyncSession, entity_keys: tuple[str, ...]) -> set[str]:
    """Return wiki slugs linked to any of the requested entity keys.

    Args:
        session: Open async read session.
        entity_keys: Deduplicated, non-empty entity keys.

    Returns:
        Set of linked wiki slugs (possibly empty).
    """
    statement = text("SELECT wiki_slug FROM entity_wiki_links WHERE entity_key = ANY(:keys)")
    result = await session.execute(statement, {"keys": list(entity_keys)})
    return {row.wiki_slug for row in result.all()}


async def _fetch_linked_chunks(
    session: AsyncSession,
    *,
    slugs: tuple[str, ...],
    embedding_literal: str,
    excerpt_chars: int,
    table: str,
) -> list[LlmWikiCitation]:
    """Fetch the best chunk for each linked document missing from the candidates.

    Args:
        session: Open async read session.
        slugs: Linked wiki slugs absent from the vector candidate pool.
        embedding_literal: Query embedding literal used to pick each top chunk.
        excerpt_chars: Maximum excerpt length for injected citations.
        table: Model-selected embedding table (registry-allowlisted).

    Returns:
        One boosted citation per linked document that has at least one embedded
        chunk.
    """
    safe_table = _require_embedding_table(table)
    statement = text(f"""
        SELECT DISTINCT ON (d.slug)
            d.title AS title,
            d.rel_path AS rel_path,
            c.heading AS heading,
            c.content AS content,
            (e.embedding OPERATOR(extensions.<=>) CAST(:embedding AS extensions.vector)) AS distance
        FROM wiki_documents AS d
        JOIN wiki_chunks AS c ON c.document_id = d.id
        JOIN {safe_table} AS e ON e.chunk_id = c.id
        WHERE d.slug = ANY(:slugs)
        ORDER BY d.slug, e.embedding OPERATOR(extensions.<=>) CAST(:embedding AS extensions.vector) ASC
        """)
    result = await session.execute(
        statement,
        {"embedding": embedding_literal, "slugs": list(slugs)},
    )
    injected: list[LlmWikiCitation] = []
    for row in result.all():
        citation = _citation_from_row(row, excerpt_chars=excerpt_chars)
        injected.append(replace(citation, score=round(citation.score + ENTITY_LINK_BONUS, 4)))
    return injected


def _citation_from_row(row: Any, *, excerpt_chars: int) -> LlmWikiCitation:
    """Build a citation from a vector result row.

    Args:
        row: Result row exposing title, rel_path, heading, content, distance.
        excerpt_chars: Maximum excerpt length.

    Returns:
        Citation with a relative source path and a cosine-similarity score.
    """
    title = _collapse_whitespace(str(row.title))[:120] or "WIKI"
    heading = _collapse_whitespace(str(row.heading))[:120] if row.heading else None
    excerpt = _collapse_whitespace(str(row.content))[:excerpt_chars].strip()
    score = round(1.0 - float(row.distance), 4)
    return LlmWikiCitation(
        title=title,
        source_path=str(row.rel_path),
        heading=heading,
        excerpt=excerpt,
        score=score,
    )


def _merge_lexical(
    vector_citations: list[LlmWikiCitation],
    lexical_citations: tuple[LlmWikiCitation, ...],
) -> list[LlmWikiCitation]:
    """Merge lexical citations into vector citations, deduped by source path.

    Vector citations win on identity; documents present in both gain a small
    lexical bonus. Lexical-only documents are appended so a strong lexical match
    missing from the vector pool can still surface.

    Args:
        vector_citations: Citations from the vector search (already boosted).
        lexical_citations: Citations from the lexical scanner.

    Returns:
        Merged citation list with one entry per source path.
    """
    lexical_by_path = {citation.source_path: citation for citation in lexical_citations}
    merged: list[LlmWikiCitation] = []
    seen: set[str] = set()
    for citation in vector_citations:
        seen.add(citation.source_path)
        if citation.source_path in lexical_by_path:
            merged.append(replace(citation, score=round(citation.score + HYBRID_LEXICAL_BONUS, 4)))
        else:
            merged.append(citation)
    max_lexical = max((c.score for c in lexical_citations), default=0.0) or 1.0
    for source_path, citation in lexical_by_path.items():
        if source_path not in seen:
            # Rescale the raw lexical score into a sub-vector band so a strong
            # lexical-only note can surface without outranking curated /
            # entity-linked semantic hits.
            normalized = round(LEXICAL_ONLY_WEIGHT * citation.score / max_lexical, 4)
            merged.append(replace(citation, score=normalized))
    return merged


def _slug_from_source_path(source_path: str) -> str:
    """Return the document slug (file stem) for a relative source path.

    Args:
        source_path: Relative POSIX source path such as ``minerals/iron.md``.

    Returns:
        The file stem used as the wiki slug (e.g. ``iron``).
    """
    return PurePosixPath(source_path).stem


def _vector_literal(vector: tuple[float, ...]) -> str:
    """Serialize a finite embedding vector as a pgvector text literal.

    Args:
        vector: Dense embedding values.

    Returns:
        A ``[v0,v1,...]`` literal suitable for ``CAST(... AS extensions.vector)``.
    """
    return "[" + ",".join(str(float(value)) for value in vector) + "]"


def _iter_markdown_files(root: Path) -> list[Path]:
    """Return visible Markdown files below a WIKI root.

    Args:
        root: Configured WIKI root.

    Returns:
        Sorted visible Markdown file paths.
    """
    return sorted(
        path
        for path in root.rglob("*.md")
        if path.is_file() and not any(part.startswith(".") for part in path.relative_to(root).parts)
    )


def _read_markdown(path: Path) -> str | None:
    """Read one bounded Markdown file.

    Args:
        path: Markdown file path.

    Returns:
        File text, or None when it cannot be safely read.
    """
    try:
        if path.stat().st_size > MAX_WIKI_FILE_BYTES:
            return None
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _score_markdown(
    *,
    path: Path,
    root: Path,
    content: str,
    terms: tuple[str, ...],
    excerpt_chars: int,
) -> LlmWikiCitation | None:
    """Score one Markdown document against query terms.

    Args:
        path: Markdown file path.
        root: WIKI root used to compute relative source path.
        content: Markdown content.
        terms: Normalized query terms.
        excerpt_chars: Maximum excerpt length.

    Returns:
        Citation when the document has a positive lexical score.
    """
    title = _title(content) or path.stem.replace("-", " ")
    heading = _matching_heading(content, terms)
    lower_title = title.casefold()
    lower_heading = (heading or "").casefold()
    lower_content = content.casefold()
    score = 0.0
    for term in terms:
        if term in lower_title:
            score += 8.0
        if term in lower_heading:
            score += 5.0
        score += min(lower_content.count(term), 12) * 1.0
    if score <= 0:
        return None
    return LlmWikiCitation(
        title=_collapse_whitespace(title)[:120],
        source_path=_relative_source_path(path, root),
        heading=_collapse_whitespace(heading)[:120] if heading else None,
        excerpt=_excerpt(content, terms, excerpt_chars),
        score=round(score, 3),
    )


def _query_terms(query: str) -> tuple[str, ...]:
    """Extract bounded lexical retrieval terms.

    Args:
        query: Sanitized query text.

    Returns:
        Unique terms in first-seen order.
    """
    terms: list[str] = []
    seen: set[str] = set()
    for match in TOKEN_RE.finditer(query.casefold()):
        term = match.group(0).strip("._/-")
        if len(term) < MIN_QUERY_TERM_CHARS or term in STOP_TERMS or term in seen:
            continue
        terms.append(term)
        seen.add(term)
        if len(terms) >= MAX_QUERY_TERMS:
            break
    return tuple(terms)


def _title(content: str) -> str | None:
    """Return the first H1 title from Markdown content."""
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return None


def _matching_heading(content: str, terms: tuple[str, ...]) -> str | None:
    """Return the first heading that matches a query term."""
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped.startswith("#"):
            continue
        heading = stripped.lstrip("#").strip()
        lower_heading = heading.casefold()
        if any(term in lower_heading for term in terms):
            return heading
    return None


def _excerpt(content: str, terms: tuple[str, ...], max_chars: int) -> str:
    """Return a bounded excerpt around the first matching term."""
    collapsed = _collapse_whitespace(content)
    lower_content = collapsed.casefold()
    first_index = min(
        (index for term in terms if (index := lower_content.find(term)) >= 0),
        default=0,
    )
    start = max(first_index - max_chars // 3, 0)
    end = min(start + max_chars, len(collapsed))
    return collapsed[start:end].strip()


def _relative_source_path(path: Path, root: Path) -> str:
    """Return a POSIX relative source path for API citations."""
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name


def _collapse_whitespace(value: str) -> str:
    """Collapse whitespace for bounded prompts and excerpts."""
    return " ".join(value.split())
