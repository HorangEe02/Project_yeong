"""Ingest the local LLM-WIKI into pgvector tables for semantic RAG.

Walks the Obsidian wiki (``--root``, default = the project LLM-WIKI), parses each
markdown page (frontmatter title/category/tags), chunks it by heading section,
embeds each chunk with an Ollama embedding model, and upserts ``wiki_documents`` /
``wiki_chunks`` plus the per-model embedding table.

Multi-model aware. Documents and chunks are model-independent; embeddings are
written into the model's dedicated table (pgvector columns are dimension-typed):

- ``bge-m3``         (1024-dim) -> ``wiki_chunk_embeddings``
- ``embeddinggemma`` (768-dim)  -> ``wiki_chunk_embeddings_gemma``

The routing (table, dimension, retrieval prompt prefix) comes from
``src.services.wiki_embedding_targets`` so the read and write paths never drift.
Running a second model over a wiki already ingested by the first does NOT skip the
documents: the document/chunk rows are reused and only the missing per-model
embeddings are generated.

Idempotent on two levels: a document whose ``content_hash`` is unchanged keeps its
chunks (changed documents have chunks + all their embeddings replaced via cascade),
and each chunk embedding is created only when absent for the selected model. So a
re-run after a partial failure fills only the gaps.

Dotfolders (``.smart-env``, ``.obsidian`` …) are skipped — only human-authored
markdown is indexed. Dry-run by default; pass ``--apply`` to write. Connection via
``--dsn`` (asyncpg URL, password may come from the ``PGPASSWORD`` env var).

References:
    https://github.com/pgvector/pgvector
    https://github.com/ollama/ollama/blob/main/docs/api.md#generate-embeddings
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import time
import unicodedata
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from uuid import uuid4

import asyncpg
from src.services.wiki_embedding_targets import (
    DEFAULT_EMBEDDING_MODEL,
    WikiEmbeddingTarget,
    get_target,
    known_models,
)

DEFAULT_ROOT = Path("/Volumes/Corsair EX400U Media/LLM-WIKI")
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
SOURCE_MANIFEST_VERSION = "llm-wiki-rag-v1"

MAX_CHUNK_CHARS = 1600
MIN_CHUNK_CHARS = 40
MAX_CHUNKS_PER_DOC = 60
MAX_SUMMARY_CHARS = 600
EMBED_MAX_RETRIES = 3
_HEADING_RE = re.compile(r"^#{1,6}\s+(.*)$")
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _nfc(text: str) -> str:
    """Return NFC-normalized text (macOS filenames/content are often NFD)."""
    return unicodedata.normalize("NFC", text)


def _sha256(text: str) -> str:
    """Return a hex SHA-256 digest of text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def iter_markdown(root: Path) -> list[Path]:
    """Return visible markdown files under the wiki root (dotfolders excluded)."""
    return sorted(
        p
        for p in root.rglob("*.md")
        if p.is_file() and not any(part.startswith(".") for part in p.relative_to(root).parts)
    )


def parse_frontmatter(text: str) -> tuple[dict[str, str | list[str]], str]:
    """Split YAML-ish frontmatter from markdown body.

    Args:
        text: Full markdown file content.

    Returns:
        (frontmatter dict with str/list values, body text without frontmatter).
    """
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    front: dict[str, str | list[str]] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, _, raw = line.partition(":")
        key = key.strip()
        value = raw.strip()
        if value.startswith("[") and value.endswith("]"):
            front[key] = [v.strip().strip("'\"") for v in value[1:-1].split(",") if v.strip()]
        else:
            front[key] = value.strip("'\"")
    return front, text[match.end() :]


def _title(body: str, front: dict, slug: str) -> str:
    """Return the document title (frontmatter > first H1 > slug)."""
    if isinstance(front.get("title"), str) and front["title"]:
        return str(front["title"])
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return slug.replace("-", " ")


def _summary(body: str) -> str | None:
    """Return a bounded summary from the takeaway/요약 area near the top."""
    collapsed = " ".join(body.split())
    return collapsed[:MAX_SUMMARY_CHARS] or None


def _hard_wrap(text: str, limit: int) -> list[str]:
    """Split text into pieces no longer than ``limit`` characters.

    Breaks on the last newline (then space) before the limit so wrapping follows a
    natural boundary, falling back to a hard cut for unbroken runs. Sections with
    no blank-line breaks (long tables / wiki-link lists) would otherwise exceed the
    Ollama embeddings input limit (~2048 tokens) and fail with HTTP 500.

    Args:
        text: Text to split.
        limit: Maximum characters per piece.

    Returns:
        Non-empty text pieces, each at most ``limit`` characters.
    """
    pieces: list[str] = []
    remaining = text.strip()
    while len(remaining) > limit:
        window = remaining[:limit]
        cut = window.rfind("\n")
        if cut < limit // 2:
            cut = window.rfind(" ")
        if cut < limit // 2:
            cut = limit
        pieces.append(remaining[:cut].strip())
        remaining = remaining[cut:].strip()
    if remaining:
        pieces.append(remaining)
    return [piece for piece in pieces if piece]


def chunk_sections(body: str) -> list[tuple[str | None, str]]:
    """Chunk markdown body into (heading, content) sections, bounded in size.

    Args:
        body: Markdown body without frontmatter.

    Returns:
        List of (heading-or-None, chunk-text) tuples, each bounded by
        ``MAX_CHUNK_CHARS`` so every chunk stays within the embeddings input limit.
    """
    sections: list[tuple[str | None, list[str]]] = [(None, [])]
    for line in body.splitlines():
        heading = _HEADING_RE.match(line.strip())
        if heading:
            sections.append((heading.group(1).strip(), []))
        else:
            sections[-1][1].append(line)
    chunks: list[tuple[str | None, str]] = []
    for heading, lines in sections:
        text = "\n".join(lines).strip()
        if not text:
            continue
        prefix = f"{heading}\n" if heading else ""
        # Bound each section: split on blank lines, then hard-wrap any single
        # paragraph that still exceeds the cap (long tables / link lists have no
        # blank lines, so they must be force-split before embedding). The wrap
        # limit leaves room for the heading prefix so prefix+chunk stays bounded.
        wrap_limit = max(MIN_CHUNK_CHARS, MAX_CHUNK_CHARS - len(prefix))
        buf = prefix
        paragraphs: list[str] = []
        for para in re.split(r"\n\s*\n", text):
            paragraphs.extend(_hard_wrap(para, wrap_limit) if len(para) > wrap_limit else [para])
        for para in paragraphs:
            candidate = (buf + "\n\n" + para).strip() if buf.strip() else para
            if len(candidate) > MAX_CHUNK_CHARS and buf.strip():
                chunks.append((heading, buf.strip()))
                buf = (f"{heading}\n" if heading else "") + para
            else:
                buf = candidate
        if buf.strip() and len(buf.strip()) >= MIN_CHUNK_CHARS:
            chunks.append((heading, buf.strip()))
    return chunks[:MAX_CHUNKS_PER_DOC]


def embed_text(
    text: str, *, ollama_url: str, model: str, dimensions: int, prefix: str = ""
) -> list[float]:
    """Return an Ollama embedding for text.

    Args:
        text: Text to embed.
        ollama_url: Ollama base URL.
        model: Embedding model name.
        dimensions: Expected embedding dimension (validated).
        prefix: Model-specific document prompt prefix prepended before embedding.

    Returns:
        Embedding vector.

    Raises:
        ValueError: If the response dimension does not match the expected one.
        RuntimeError: If the embeddings request fails after retries.
    """
    payload = json.dumps({"model": model, "prompt": f"{prefix}{text}"}).encode("utf-8")
    last_error: Exception | None = None
    for attempt in range(EMBED_MAX_RETRIES):
        try:
            req = urllib.request.Request(
                f"{ollama_url}/api/embeddings",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError) as exc:
            # Transient (server busy / connection reset): back off and retry.
            last_error = exc
            if attempt < EMBED_MAX_RETRIES - 1:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise RuntimeError(f"ollama embeddings failed after retries: {exc}") from exc
        vector = data.get("embedding") or []
        if len(vector) != dimensions:
            raise ValueError(
                f"embedding dim {len(vector)} != expected {dimensions} for model {model}"
            )
        return [float(x) for x in vector]
    raise RuntimeError(f"ollama embeddings failed: {last_error}")


def _vector_literal(vector: list[float]) -> str:
    """Return a pgvector text literal like ``[0.1,0.2,...]``."""
    return "[" + ",".join(repr(round(x, 6)) for x in vector) + "]"


async def _load_or_replace_document(
    conn: asyncpg.Connection,
    *,
    slug: str,
    raw: str,
    body: str,
    front: dict,
    rel_path: str,
    rechunk_oversized: bool = False,
) -> tuple[object, list[asyncpg.Record], str]:
    """Ensure the document and its chunks exist and are current.

    Unchanged documents (same ``content_hash``) keep their existing chunks; changed
    or new documents are (re)written with freshly computed chunks, which cascades
    away any stale embeddings in every per-model table.

    When ``rechunk_oversized`` is set, an unchanged document whose stored chunks
    exceed ``MAX_CHUNK_CHARS`` (left behind before the chunker hard-cap fix) is also
    re-chunked. This is the maintenance path for repairing oversized legacy chunks
    that the embeddings API rejects.

    Args:
        conn: Open asyncpg connection.
        slug: Document slug (file stem, NFC-normalized).
        raw: Full NFC file content (hashed for idempotency).
        body: Markdown body without frontmatter.
        front: Parsed frontmatter mapping.
        rel_path: POSIX-relative path from the wiki root.
        rechunk_oversized: Re-chunk unchanged docs that still hold oversized chunks.

    Returns:
        ``(document_id, chunk_rows, status)`` where ``chunk_rows`` expose ``id`` and
        ``content`` and ``status`` is one of ``unchanged`` / ``written`` / ``empty``.
    """
    content_hash = _sha256(raw)
    existing = await conn.fetchrow(
        "select id, content_hash from wiki_documents where slug=$1", slug
    )
    reuse = bool(existing) and existing["content_hash"] == content_hash
    if reuse and rechunk_oversized:
        max_len = await conn.fetchval(
            "select max(length(content)) from wiki_chunks where document_id=$1", existing["id"]
        )
        reuse = not (max_len and max_len > MAX_CHUNK_CHARS)
    if reuse:
        chunk_rows = await conn.fetch(
            "select id, content from wiki_chunks where document_id=$1 order by chunk_index",
            existing["id"],
        )
        return existing["id"], chunk_rows, "unchanged"

    chunks = chunk_sections(body)
    if not chunks:
        return None, [], "empty"

    category = front.get("category") if isinstance(front.get("category"), str) else None
    tags = front.get("tags") if isinstance(front.get("tags"), list) else []
    title = _title(body, front, slug)
    doc_id = uuid4()
    async with conn.transaction():
        if existing:
            await conn.execute("delete from wiki_documents where id=$1", existing["id"])
        await conn.execute(
            """insert into wiki_documents
               (id, slug, title, category, rel_path, tags, summary, content_hash,
                source_manifest_version)
               values ($1,$2,$3,$4,$5,$6::jsonb,$7,$8,$9)""",
            doc_id,
            slug,
            title[:300],
            (category or None) and category[:40],
            rel_path,
            json.dumps(tags, ensure_ascii=False),
            _summary(body),
            content_hash,
            SOURCE_MANIFEST_VERSION,
        )
        for index, (heading, content) in enumerate(chunks):
            await conn.execute(
                """insert into wiki_chunks
                   (id, document_id, heading, chunk_index, content, content_hash, token_count)
                   values ($1,$2,$3,$4,$5,$6,$7)""",
                uuid4(),
                doc_id,
                (heading or None) and heading[:300],
                index,
                content,
                _sha256(content),
                len(content.split()),
            )
        chunk_rows = await conn.fetch(
            "select id, content from wiki_chunks where document_id=$1 order by chunk_index",
            doc_id,
        )
    return doc_id, chunk_rows, "written"


async def _ensure_chunk_embeddings(
    conn: asyncpg.Connection,
    *,
    chunk_rows: list[asyncpg.Record],
    ollama_url: str,
    target: WikiEmbeddingTarget,
    stats: Counter[str],
) -> None:
    """Generate missing embeddings for the selected model into its target table.

    Args:
        conn: Open asyncpg connection.
        chunk_rows: Chunk rows exposing ``id`` and ``content``.
        ollama_url: Ollama base URL.
        target: Resolved embedding target (model, table, dimension, prompt prefix).
        stats: Counter accumulating ``embeddings_existing`` / ``embeddings_written``.

    Raises:
        ValueError: If an embedding has an unexpected dimension.
        RuntimeError: If an embeddings request fails after retries.
    """
    insert_sql = (
        f"insert into {target.table} "
        "(id, chunk_id, embedding, embedding_model, embedding_dimensions) "
        "values ($1,$2,$3::extensions.vector,$4,$5) "
        "on conflict (chunk_id, embedding_model) do nothing"
    )
    exists_sql = f"select 1 from {target.table} where chunk_id=$1 and embedding_model=$2"
    for chunk in chunk_rows:
        if await conn.fetchval(exists_sql, chunk["id"], target.model):
            stats["embeddings_existing"] += 1
            continue
        vector = embed_text(
            chunk["content"],
            ollama_url=ollama_url,
            model=target.model,
            dimensions=target.dimensions,
            prefix=target.document_prompt_prefix,
        )
        await conn.execute(
            insert_sql,
            uuid4(),
            chunk["id"],
            _vector_literal(vector),
            target.model,
            target.dimensions,
        )
        stats["embeddings_written"] += 1


async def ingest(
    *,
    dsn: str,
    root: Path,
    ollama_url: str,
    target: WikiEmbeddingTarget,
    limit: int | None,
    rechunk_oversized: bool = False,
) -> dict:
    """Ingest wiki markdown and embed it with the selected model.

    Args:
        dsn: asyncpg connection URL.
        root: Wiki root directory.
        ollama_url: Ollama base URL.
        target: Resolved embedding target (model, table, dimension, prompt prefix).
        limit: Optional cap on processed files (for smoke runs).
        rechunk_oversized: Re-chunk unchanged docs whose stored chunks exceed the cap.

    Returns:
        Count-only summary including per-model embedding totals and failures.
    """
    files = iter_markdown(root)
    if limit is not None:
        files = files[:limit]
    conn = await asyncpg.connect(dsn=dsn)
    stats: Counter[str] = Counter()
    # Prime reported keys so a zero count still appears in the summary.
    for key in (
        "documents_written",
        "documents_unchanged",
        "skipped_empty",
        "embeddings_written",
        "embeddings_existing",
        "failed_docs",
    ):
        stats[key] = 0
    failures: list[dict[str, str]] = []
    try:
        for path in files:
            slug = _nfc(path.stem)
            try:
                raw = _nfc(path.read_text(encoding="utf-8", errors="replace"))
                front, body = parse_frontmatter(raw)
                rel_path = path.relative_to(root).as_posix()
                _doc_id, chunk_rows, status = await _load_or_replace_document(
                    conn,
                    slug=slug,
                    raw=raw,
                    body=body,
                    front=front,
                    rel_path=rel_path,
                    rechunk_oversized=rechunk_oversized,
                )
                if status == "empty":
                    stats["skipped_empty"] += 1
                    continue
                stats["documents_unchanged" if status == "unchanged" else "documents_written"] += 1
                await _ensure_chunk_embeddings(
                    conn,
                    chunk_rows=list(chunk_rows),
                    ollama_url=ollama_url,
                    target=target,
                    stats=stats,
                )
            except Exception as exc:
                # Per-document isolation: failures are reported and retried on the
                # next idempotent run (committed docs keep their hash; only the
                # missing per-model embeddings are refilled).
                stats["failed_docs"] += 1
                failures.append({"slug": slug, "error": f"{type(exc).__name__}: {str(exc)[:140]}"})
        totals = {
            "documents_in_db": await conn.fetchval("select count(*) from wiki_documents"),
            "chunks_in_db": await conn.fetchval("select count(*) from wiki_chunks"),
            "model_embeddings_in_db": await conn.fetchval(
                f"select count(*) from {target.table} where embedding_model=$1", target.model
            ),
        }
    finally:
        await conn.close()
    return {
        "processed_files": len(files),
        "model": target.model,
        "table": target.table,
        "dimensions": target.dimensions,
        **dict(stats),
        **totals,
        "failures": failures[:50],
    }


def _resolve_target(args: argparse.Namespace) -> WikiEmbeddingTarget:
    """Resolve the embedding target from the registry plus optional overrides.

    Args:
        args: Parsed CLI arguments (``model``, ``table``, ``dimensions``).

    Returns:
        The embedding target to ingest with.

    Raises:
        SystemExit: If the model is unknown and no explicit ``--table`` is given.
    """
    try:
        base = get_target(args.model)
    except KeyError:
        if not args.table or args.dimensions is None:
            raise SystemExit(
                f"ERROR: unknown model {args.model!r}; known: {', '.join(known_models())}. "
                "Pass --table and --dimensions to ingest an unregistered model."
            ) from None
        return WikiEmbeddingTarget(model=args.model, table=args.table, dimensions=args.dimensions)
    table = args.table or base.table
    dimensions = args.dimensions if args.dimensions is not None else base.dimensions
    return WikiEmbeddingTarget(
        model=base.model,
        table=table,
        dimensions=dimensions,
        query_prompt_prefix=base.query_prompt_prefix,
        document_prompt_prefix=base.document_prompt_prefix,
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--ollama-url", default=DEFAULT_OLLAMA_URL)
    parser.add_argument("--model", default=DEFAULT_EMBEDDING_MODEL)
    parser.add_argument(
        "--table", default=None, help="Override the registry target table (rarely needed)."
    )
    parser.add_argument(
        "--dimensions", type=int, default=None, help="Override the registry embedding dimension."
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--summary", type=Path, default=None)
    parser.add_argument(
        "--rechunk-oversized",
        action="store_true",
        help="Re-chunk unchanged docs whose stored chunks exceed the size cap.",
    )
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.root.expanduser()
    if not root.is_dir():
        raise SystemExit(f"ERROR: wiki root not found: {root}")
    target = _resolve_target(args)
    if not args.apply:
        files = iter_markdown(root)
        if args.limit is not None:
            files = files[: args.limit]
        summary = {
            "apply_requested": False,
            "markdown_files": len(files),
            "root_name": root.name,
            "model": target.model,
            "table": target.table,
            "dimensions": target.dimensions,
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    summary = asyncio.run(
        ingest(
            dsn=args.dsn,
            root=root,
            ollama_url=args.ollama_url,
            target=target,
            limit=args.limit,
            rechunk_oversized=args.rechunk_oversized,
        )
    )
    summary["apply_requested"] = True
    if args.summary:
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
