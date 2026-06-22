"""Database-backed (pgvector) LLM-WIKI retrieval tests.

These tests exercise :func:`retrieve_llm_wiki_context_db` without a live Ollama
runtime or a real pgvector database. The query embedding call and the async
sessionmaker are replaced with fakes via monkeypatching, and stub rows stand in
for ``wiki_chunk_embeddings`` / ``wiki_documents`` / ``entity_wiki_links`` query
results. The lexical contract path is covered by ``test_llm_wiki_retrieval.py``.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from src.config import Settings
from src.services import llm_wiki_retrieval
from src.services.llm_wiki_retrieval import retrieve_llm_wiki_context_db


def _settings(tmp_path: Path, **overrides: object) -> Settings:
    """Return settings pointing at a temporary WIKI root.

    Args:
        tmp_path: Temporary WIKI root for the lexical fallback path.
        overrides: Optional Settings field overrides.

    Returns:
        Settings object for database-backed retrieval tests.
    """
    values: dict[str, object] = {
        "llm_wiki_path": tmp_path,
        "llm_wiki_retrieval_enabled": True,
        "llm_wiki_max_sources": 3,
        "llm_wiki_excerpt_chars": 180,
        "enable_wiki_vector_rag": True,
        "llm_wiki_retrieval_mode": "vector",
        "wiki_embedding_model": "bge-m3",
        "wiki_embedding_dimensions": 4,
        **overrides,
    }
    return Settings(_env_file=None, **values)


def _vector_row(
    *,
    title: str,
    rel_path: str,
    heading: str | None,
    content: str,
    distance: float,
) -> SimpleNamespace:
    """Build a stub vector-search result row.

    Args:
        title: Document title.
        rel_path: Relative document path used as the citation source path.
        heading: Chunk heading or None.
        content: Chunk content used for the excerpt.
        distance: Cosine distance (lower is closer).

    Returns:
        An attribute-accessible row stub matching the retrieval query columns.
    """
    return SimpleNamespace(
        title=title,
        rel_path=rel_path,
        heading=heading,
        content=content,
        distance=distance,
    )


class _StubResult:
    """Stub of a SQLAlchemy result exposing ``all()``."""

    def __init__(self, rows: list[Any]) -> None:
        """Store the rows this result returns.

        Args:
            rows: Result rows to return from ``all()``.
        """
        self._rows = rows

    def all(self) -> list[Any]:
        """Return the stored rows.

        Returns:
            The result rows.
        """
        return self._rows


class _StubSession:
    """Stub async session that routes SQL by inspecting the statement text."""

    def __init__(
        self,
        *,
        vector_rows: list[Any],
        link_rows: list[Any],
        linked_chunk_rows: list[Any],
    ) -> None:
        """Configure the canned result sets for each query shape.

        Args:
            vector_rows: Rows for the cosine top-K candidate query.
            link_rows: Rows for the ``entity_wiki_links`` slug query.
            linked_chunk_rows: Rows for the injected linked-document chunk query.
        """
        self._vector_rows = vector_rows
        self._link_rows = link_rows
        self._linked_chunk_rows = linked_chunk_rows
        self.executed: list[str] = []

    async def __aenter__(self) -> _StubSession:
        """Enter the async context.

        Returns:
            This session stub.
        """
        return self

    async def __aexit__(self, *exc: object) -> None:
        """Exit the async context.

        Args:
            exc: Unused exception triple.
        """
        _ = exc

    async def execute(self, statement: Any, params: dict[str, Any]) -> _StubResult:
        """Return canned rows based on the statement text.

        Args:
            statement: SQLAlchemy ``text()`` clause.
            params: Bound parameters (unused by the stub).

        Returns:
            The matching stub result set.
        """
        _ = params
        sql = str(statement)
        self.executed.append(sql)
        if "entity_wiki_links" in sql:
            return _StubResult(self._link_rows)
        if "DISTINCT ON" in sql:
            return _StubResult(self._linked_chunk_rows)
        return _StubResult(self._vector_rows)


def _install_session(
    monkeypatch: pytest.MonkeyPatch,
    session: _StubSession,
) -> None:
    """Patch ``get_sessionmaker`` to yield the provided stub session.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        session: Stub session returned by the factory.
    """

    def _factory() -> _StubSession:
        return session

    monkeypatch.setattr(llm_wiki_retrieval, "get_sessionmaker", lambda: _factory)


def _install_embedding(
    monkeypatch: pytest.MonkeyPatch,
    vector: tuple[float, ...] = (0.1, 0.2, 0.3, 0.4),
) -> None:
    """Patch the Ollama embedding call with a fixed vector.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        vector: Embedding vector to return.
    """

    async def _fake_embed(query: str, settings: Settings) -> tuple[float, ...]:
        _ = (query, settings)
        return vector

    monkeypatch.setattr(llm_wiki_retrieval, "_embed_query", _fake_embed)


async def test_db_retrieval_passthrough_when_disabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify lexical passthrough when vector RAG is disabled."""
    (tmp_path / "omega-3.md").write_text(
        "# 오메가3\n\n## 효능\n오메가3는 혈중 지질 확인이 필요한 보충제 정보입니다.",
        encoding="utf-8",
    )

    def _boom() -> object:
        raise AssertionError("get_sessionmaker must not be called in lexical mode.")

    async def _boom_embed(query: str, settings: Settings) -> tuple[float, ...]:
        _ = (query, settings)
        raise AssertionError("_embed_query must not be called in lexical mode.")

    monkeypatch.setattr(llm_wiki_retrieval, "get_sessionmaker", _boom)
    monkeypatch.setattr(llm_wiki_retrieval, "_embed_query", _boom_embed)

    result = await retrieve_llm_wiki_context_db(
        "오메가3 효능",
        _settings(tmp_path, enable_wiki_vector_rag=False),
    )

    assert len(result.citations) == 1
    assert result.citations[0].source_path == "omega-3.md"


async def test_db_retrieval_lexical_mode_uses_lexical(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify ``llm_wiki_retrieval_mode='lexical'`` skips the vector path."""
    (tmp_path / "omega-3.md").write_text(
        "# 오메가3\n\n## 효능\n오메가3는 혈중 지질 확인이 필요한 보충제 정보입니다.",
        encoding="utf-8",
    )

    async def _boom_embed(query: str, settings: Settings) -> tuple[float, ...]:
        _ = (query, settings)
        raise AssertionError("_embed_query must not be called in lexical mode.")

    monkeypatch.setattr(llm_wiki_retrieval, "_embed_query", _boom_embed)

    result = await retrieve_llm_wiki_context_db(
        "오메가3 효능",
        _settings(tmp_path, llm_wiki_retrieval_mode="lexical"),
    )

    assert len(result.citations) == 1
    assert result.citations[0].source_path == "omega-3.md"


async def test_db_retrieval_returns_vector_citations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify vector mode builds citations from stubbed rows with cosine scores."""
    _install_embedding(monkeypatch)
    session = _StubSession(
        vector_rows=[
            _vector_row(
                title="오메가3",
                rel_path="entities/omega-3.md",
                heading="효능",
                content="오메가3는 혈중 지질 확인이 필요한 보충제 정보입니다.",
                distance=0.1,
            ),
            _vector_row(
                title="항산화 보충제",
                rel_path="concepts/antioxidants.md",
                heading=None,
                content="항산화 보충제는 세포 보호 관련 참고 정보입니다.",
                distance=0.4,
            ),
        ],
        link_rows=[],
        linked_chunk_rows=[],
    )
    _install_session(monkeypatch, session)

    result = await retrieve_llm_wiki_context_db("오메가3 효능", _settings(tmp_path))

    assert [citation.source_path for citation in result.citations] == [
        "entities/omega-3.md",
        "concepts/antioxidants.md",
    ]
    top = result.citations[0]
    assert top.title == "오메가3"
    assert top.heading == "효능"
    assert top.score == pytest.approx(0.9)
    assert result.citations[1].score == pytest.approx(0.6)
    # source_path stays relative; no absolute path leaks into citations.
    assert all(not citation.source_path.startswith("/") for citation in result.citations)
    assert all("/Volumes/" not in citation.source_path for citation in result.citations)


async def test_db_retrieval_trims_to_max_sources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify the candidate pool is trimmed to ``llm_wiki_max_sources``."""
    _install_embedding(monkeypatch)
    rows = [
        _vector_row(
            title=f"문서 {index}",
            rel_path=f"concepts/doc-{index}.md",
            heading=None,
            content=f"문서 {index} 본문 내용입니다.",
            distance=0.1 * index,
        )
        for index in range(6)
    ]
    session = _StubSession(vector_rows=rows, link_rows=[], linked_chunk_rows=[])
    _install_session(monkeypatch, session)

    result = await retrieve_llm_wiki_context_db(
        "문서 검색",
        _settings(tmp_path, llm_wiki_max_sources=2),
    )

    assert len(result.citations) == 2
    assert [citation.source_path for citation in result.citations] == [
        "concepts/doc-0.md",
        "concepts/doc-1.md",
    ]


async def test_db_retrieval_hybrid_merges_and_dedupes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify hybrid mode merges lexical hits and dedupes by source path."""
    # Lexical scanner will match this same document by its relative path.
    (tmp_path / "concepts").mkdir()
    (tmp_path / "concepts" / "omega-3.md").write_text(
        "# 오메가3\n\n## 효능\n오메가3 혈중 지질 확인이 필요한 보충제 정보입니다.",
        encoding="utf-8",
    )
    (tmp_path / "concepts" / "vitamin-d.md").write_text(
        "# 비타민 D\n\n## 효능\n오메가3 비타민 D 혈중 수치 확인이 필요한 정보입니다.",
        encoding="utf-8",
    )
    _install_embedding(monkeypatch)
    session = _StubSession(
        vector_rows=[
            _vector_row(
                title="오메가3",
                rel_path="concepts/omega-3.md",
                heading="효능",
                content="오메가3 본문 벡터 청크입니다.",
                distance=0.2,
            ),
        ],
        link_rows=[],
        linked_chunk_rows=[],
    )
    _install_session(monkeypatch, session)

    result = await retrieve_llm_wiki_context_db(
        "오메가3 효능",
        _settings(tmp_path, llm_wiki_retrieval_mode="hybrid"),
    )

    paths = [citation.source_path for citation in result.citations]
    # omega-3 appears in both lexical and vector results but only once after merge.
    assert paths.count("concepts/omega-3.md") == 1
    # The lexical-only vitamin-d document is also surfaced by the merge.
    assert "concepts/vitamin-d.md" in paths
    omega = next(c for c in result.citations if c.source_path == "concepts/omega-3.md")
    # Vector base score (1 - 0.2 = 0.8) plus the hybrid lexical-overlap bonus.
    assert omega.score == pytest.approx(0.85)


async def test_db_retrieval_entity_boost_reorders(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify an entity-linked document is boosted above a closer vector hit."""
    _install_embedding(monkeypatch)
    session = _StubSession(
        vector_rows=[
            _vector_row(
                title="항산화 보충제",
                rel_path="concepts/antioxidants.md",
                heading=None,
                content="항산화 보충제 본문입니다.",
                distance=0.10,
            ),
            _vector_row(
                title="미네랄 보충제",
                rel_path="concepts/mineral-supplements.md",
                heading=None,
                content="미네랄 보충제 본문입니다.",
                distance=0.30,
            ),
        ],
        link_rows=[SimpleNamespace(wiki_slug="mineral-supplements")],
        linked_chunk_rows=[],
    )
    _install_session(monkeypatch, session)

    result = await retrieve_llm_wiki_context_db(
        "미네랄",
        _settings(tmp_path),
        entity_keys=("magnesium",),
    )

    paths = [citation.source_path for citation in result.citations]
    # Without boost, antioxidants (1 - 0.10 = 0.90) would rank above the mineral
    # document (1 - 0.30 = 0.70); the entity link lifts the mineral doc to 0.95.
    assert paths[0] == "concepts/mineral-supplements.md"
    boosted = result.citations[0]
    # Base 0.70 (1 - 0.30) plus the entity-link bonus (0.25).
    assert boosted.score == pytest.approx(0.95)
    antioxidants = next(c for c in result.citations if c.source_path == "concepts/antioxidants.md")
    assert antioxidants.score == pytest.approx(0.90)


async def test_db_retrieval_entity_boost_injects_missing_document(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify a linked document missing from the candidate pool is injected."""
    _install_embedding(monkeypatch)
    session = _StubSession(
        vector_rows=[
            _vector_row(
                title="항산화 보충제",
                rel_path="concepts/antioxidants.md",
                heading=None,
                content="항산화 보충제 본문입니다.",
                distance=0.05,
            ),
        ],
        link_rows=[SimpleNamespace(wiki_slug="mineral-supplements")],
        linked_chunk_rows=[
            _vector_row(
                title="미네랄 보충제",
                rel_path="concepts/mineral-supplements.md",
                heading="개요",
                content="미네랄 보충제 주입 청크입니다.",
                distance=0.50,
            ),
        ],
    )
    _install_session(monkeypatch, session)

    result = await retrieve_llm_wiki_context_db(
        "보충제",
        _settings(tmp_path),
        entity_keys=("magnesium",),
    )

    paths = [citation.source_path for citation in result.citations]
    assert "concepts/mineral-supplements.md" in paths
    injected = next(
        c for c in result.citations if c.source_path == "concepts/mineral-supplements.md"
    )
    # Injected top chunk: base 0.50 (1 - 0.50) plus the entity-link bonus (0.25).
    assert injected.score == pytest.approx(0.75)
    assert injected.heading == "개요"


async def test_db_retrieval_fails_open_to_lexical_on_embed_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify an embedding error degrades to the lexical result."""
    (tmp_path / "omega-3.md").write_text(
        "# 오메가3\n\n## 효능\n오메가3는 혈중 지질 확인이 필요한 보충제 정보입니다.",
        encoding="utf-8",
    )

    async def _raise_embed(query: str, settings: Settings) -> tuple[float, ...]:
        _ = (query, settings)
        raise RuntimeError("ollama embeddings unavailable")

    def _boom() -> object:
        raise AssertionError("get_sessionmaker must not be reached after embed failure.")

    monkeypatch.setattr(llm_wiki_retrieval, "_embed_query", _raise_embed)
    monkeypatch.setattr(llm_wiki_retrieval, "get_sessionmaker", _boom)

    result = await retrieve_llm_wiki_context_db("오메가3 효능", _settings(tmp_path))

    assert len(result.citations) == 1
    assert result.citations[0].source_path == "omega-3.md"


async def test_db_retrieval_fails_open_on_empty_vector_hits(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify an empty vector result set degrades to the lexical result."""
    (tmp_path / "omega-3.md").write_text(
        "# 오메가3\n\n## 효능\n오메가3는 혈중 지질 확인이 필요한 보충제 정보입니다.",
        encoding="utf-8",
    )
    _install_embedding(monkeypatch)
    session = _StubSession(vector_rows=[], link_rows=[], linked_chunk_rows=[])
    _install_session(monkeypatch, session)

    result = await retrieve_llm_wiki_context_db("오메가3 효능", _settings(tmp_path))

    assert len(result.citations) == 1
    assert result.citations[0].source_path == "omega-3.md"


async def test_db_retrieval_fails_open_on_db_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify a database error during the vector query degrades to lexical."""
    (tmp_path / "omega-3.md").write_text(
        "# 오메가3\n\n## 효능\n오메가3는 혈중 지질 확인이 필요한 보충제 정보입니다.",
        encoding="utf-8",
    )
    _install_embedding(monkeypatch)

    class _BrokenSession(_StubSession):
        async def execute(self, statement: Any, params: dict[str, Any]) -> _StubResult:
            _ = (statement, params)
            raise RuntimeError("pgvector query failed")

    _install_session(
        monkeypatch,
        _BrokenSession(vector_rows=[], link_rows=[], linked_chunk_rows=[]),
    )

    result = await retrieve_llm_wiki_context_db("오메가3 효능", _settings(tmp_path))

    assert len(result.citations) == 1
    assert result.citations[0].source_path == "omega-3.md"


async def test_db_retrieval_routes_to_model_specific_table(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify a second-model config sends the vector query to that model's table."""
    _install_embedding(monkeypatch)
    session = _StubSession(
        vector_rows=[
            _vector_row(
                title="마그네슘",
                rel_path="entities/magnesium.md",
                heading=None,
                content="마그네슘 권장량 관련 본문입니다.",
                distance=0.2,
            ),
        ],
        link_rows=[],
        linked_chunk_rows=[],
    )
    _install_session(monkeypatch, session)

    result = await retrieve_llm_wiki_context_db(
        "마그네슘 권장량",
        _settings(
            tmp_path,
            wiki_embedding_model="embeddinggemma",
            wiki_embedding_dimensions=768,
        ),
    )

    assert result.citations[0].source_path == "entities/magnesium.md"
    vector_sql = next(
        sql
        for sql in session.executed
        if "DISTINCT ON" not in sql and "entity_wiki_links" not in sql
    )
    # The base bge-m3 table must not be queried when embeddinggemma is configured.
    assert "wiki_chunk_embeddings_gemma" in vector_sql
    assert "FROM wiki_chunk_embeddings AS e" not in vector_sql


async def test_db_retrieval_unknown_model_falls_open_to_lexical(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify an unregistered embedding model degrades to the lexical result."""
    (tmp_path / "omega-3.md").write_text(
        "# 오메가3\n\n## 효능\n오메가3는 혈중 지질 확인이 필요한 보충제 정보입니다.",
        encoding="utf-8",
    )
    _install_embedding(monkeypatch)

    def _boom() -> object:
        raise AssertionError("get_sessionmaker must not run for an unknown model.")

    monkeypatch.setattr(llm_wiki_retrieval, "get_sessionmaker", _boom)

    result = await retrieve_llm_wiki_context_db(
        "오메가3 효능",
        _settings(tmp_path, wiki_embedding_model="model-not-in-registry"),
    )

    assert len(result.citations) == 1
    assert result.citations[0].source_path == "omega-3.md"


def test_apply_query_prompt_is_model_specific() -> None:
    """Verify the query prompt prefix is applied per model (raw for unknown)."""
    assert llm_wiki_retrieval._apply_query_prompt("마그네슘", "bge-m3") == "마그네슘"
    assert (
        llm_wiki_retrieval._apply_query_prompt("마그네슘", "embeddinggemma")
        == "task: search result | query: 마그네슘"
    )
    assert llm_wiki_retrieval._apply_query_prompt("마그네슘", "unknown-model") == "마그네슘"
