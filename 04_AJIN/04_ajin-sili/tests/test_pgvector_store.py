"""Supabase pgvector adapter and ingestion wiring tests."""

from __future__ import annotations

import pytest
from langchain_core.documents import Document

from features.search import indexer
from features.search import searcher
from features.search.employee import semantic_search
from features.search.vector_store import EmployeeEmbeddingInput, vector_literal


class FakeEmbeddings:
    """Deterministic embedding test double."""

    def __init__(self, dim: int = 1024):
        """Create a fake embedding provider.

        Args:
            dim: Embedding dimension to return.
        """

        self.dim = dim

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Return one deterministic vector per text.

        Args:
            texts: Texts to embed.

        Returns:
            list[list[float]]: Fake embeddings.
        """

        return [[float(idx + 1)] * self.dim for idx, _ in enumerate(texts)]

    def embed_query(self, text: str) -> list[float]:
        """Return one deterministic query vector.

        Args:
            text: Text to embed.

        Returns:
            list[float]: Fake embedding.
        """

        return [1.0] * self.dim


class FakePgvectorStore:
    """Collect pgvector upsert payloads without a database."""

    def __init__(self) -> None:
        """Create an empty fake store."""

        self.document_chunks = []
        self.employee_embeddings: list[EmployeeEmbeddingInput] = []

    def upsert_document_chunks(self, chunks):  # noqa: ANN001
        """Collect document chunk payloads.

        Args:
            chunks: Document chunks.

        Returns:
            int: Number of chunks collected.
        """

        self.document_chunks.extend(chunks)
        return len(chunks)

    def upsert_employee_embeddings(self, employees):  # noqa: ANN001
        """Collect employee embedding payloads.

        Args:
            employees: Employee embedding payloads.

        Returns:
            int: Number of profiles collected.
        """

        self.employee_embeddings.extend(employees)
        return len(employees)

    def hybrid_search_documents(self, **kwargs):  # noqa: ANN003
        """Return one fake pgvector document search row.

        Args:
            **kwargs: RPC-style search arguments.

        Returns:
            list[dict]: Fake pgvector rows.
        """

        self.last_search_kwargs = kwargs
        return [
            {
                "source_doc_id": "DOC-1",
                "title": "품질 SOP",
                "content": "품질 기준 문서",
                "score": 0.75,
                "metadata": {"doc_type": "SOP", "part_name": "프레스"},
            }
        ]


def test_vector_literal_requires_expected_dimension() -> None:
    """pgvector literals should fail closed on embedding dimension mismatch."""

    assert vector_literal([0.1, 0.2], expected_dim=2) == "[0.1,0.2]"
    with pytest.raises(ValueError):
        vector_literal([0.1], expected_dim=2)


def test_build_pgvector_store_reuses_document_metadata(monkeypatch) -> None:
    """Feature A document ingestion should preserve metadata and per-doc chunk indexes."""

    fake_store = FakePgvectorStore()
    monkeypatch.setattr(indexer, "get_embeddings", lambda: FakeEmbeddings())
    docs = [
        Document(page_content="첫 번째 품질 문서", metadata={"doc_id": "DOC-1", "title": "품질", "doc_type": "SOP"}),
        Document(page_content="두 번째 품질 문서", metadata={"doc_id": "DOC-1", "title": "품질", "doc_type": "SOP"}),
    ]

    written = indexer.build_pgvector_store(docs, batch_size=2, store=fake_store)

    assert written == 2
    assert [chunk.chunk_index for chunk in fake_store.document_chunks] == [0, 1]
    assert {chunk.source_doc_id for chunk in fake_store.document_chunks} == {"DOC-1"}
    assert fake_store.document_chunks[0].metadata["title"] == "품질"


def test_index_employee_one_pgvector_builds_profile_payload() -> None:
    """Employee pgvector upsert should use the same searchable profile text as Chroma."""

    fake_store = FakePgvectorStore()
    employee = {
        "employee_id": "SYS-0001",
        "name": "AJIN 운영관리자",
        "department": "IT전략팀",
        "division": "관리본부",
        "position": "시스템 관리자",
        "plant": "본사",
        "data_class": "real",
        "is_active": 1,
    }

    ok = semantic_search.index_employee_one_pgvector(
        employee,
        embedding=[1.0] * 1024,
        store=fake_store,
    )

    assert ok is True
    payload = fake_store.employee_embeddings[0]
    assert payload.employee_id == "SYS-0001"
    assert payload.department == "IT전략팀"
    assert "시스템 관리자" in payload.profile_text


def test_hybrid_searcher_reads_pgvector_when_enabled(monkeypatch) -> None:
    """HybridSearcher should preserve response shape when reading from pgvector."""

    fake_store = FakePgvectorStore()
    monkeypatch.setenv("VECTOR_READ_MODE", "postgres")
    monkeypatch.setattr(searcher, "get_embeddings", lambda: FakeEmbeddings())

    engine = searcher.HybridSearcher(corpus_chunks=[], pgvector_store=fake_store)
    results = engine.search("품질 기준", k=1, doc_type_filter="SOP")

    assert len(results) == 1
    assert results[0].doc_id == "DOC-1"
    assert results[0].title == "품질 SOP"
    assert results[0].doc_type == "SOP"
    assert fake_store.last_search_kwargs["doc_type_filter"] == "SOP"
