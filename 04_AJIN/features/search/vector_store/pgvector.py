"""Supabase Postgres pgvector adapter.

The adapter uses the backend's private Postgres connection path. It does not
depend on Supabase client-side keys and should never be imported by frontend
code.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from sqlalchemy import text
from sqlalchemy.engine import Engine

from core.db import create_sqlalchemy_engine

DEFAULT_EMBEDDING_DIM = 1024
DEFAULT_EMBEDDING_MODEL = "bge-m3"


def vector_literal(vector: Sequence[float], expected_dim: int = DEFAULT_EMBEDDING_DIM) -> str:
    """Convert an embedding vector to a pgvector text literal.

    Args:
        vector: Embedding values.
        expected_dim: Required vector dimension.

    Returns:
        str: pgvector-compatible literal such as ``[0.1,0.2]``.

    Raises:
        ValueError: If the vector dimension is not the expected value.
    """

    if len(vector) != expected_dim:
        raise ValueError(f"embedding dimension mismatch: expected {expected_dim}, got {len(vector)}")
    return "[" + ",".join(format(float(value), ".10g") for value in vector) + "]"


def content_hash(content: str) -> str:
    """Return a stable SHA-256 hash for index idempotency.

    Args:
        content: Text content to hash.

    Returns:
        str: Hex digest.
    """

    return hashlib.sha256(content.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class DocumentChunkInput:
    """Document chunk and embedding payload for pgvector upsert.

    Args:
        source_doc_id: Stable source document id.
        chunk_index: Zero-based chunk index.
        content: Chunk text.
        embedding: Embedding vector matching the configured dimension.
        metadata: Secret-safe source metadata.
        title: Optional display title.
        doc_type: Optional document type filter.
        part_name: Optional part or product filter.
        source_path: Optional source file path.
        data_class: Data lineage class.
    """

    source_doc_id: str
    chunk_index: int
    content: str
    embedding: Sequence[float]
    metadata: Mapping[str, Any] = field(default_factory=dict)
    title: str | None = None
    doc_type: str | None = None
    part_name: str | None = None
    source_path: str | None = None
    data_class: str = "real"


@dataclass(frozen=True)
class EmployeeEmbeddingInput:
    """Employee profile and embedding payload for pgvector upsert.

    Args:
        employee_id: Stable employee id.
        display_name: Employee display name.
        profile_text: Searchable profile text.
        embedding: Embedding vector matching the configured dimension.
        department: Optional department name.
        position: Optional position name.
        metadata: Secret-safe employee metadata.
        data_class: Data lineage class.
        is_active: Whether the profile is searchable.
    """

    employee_id: str
    display_name: str
    profile_text: str
    embedding: Sequence[float]
    department: str | None = None
    position: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    data_class: str = "real"
    is_active: bool = True


@dataclass(frozen=True)
class RagChunkInput:
    """Shared RAG chunk and embedding payload for pgvector upsert.

    Args:
        collection_id: Logical RAG collection id.
        feature_key: Owning feature key.
        display_name: Collection display name.
        source_item_id: Stable source item id.
        chunk_index: Zero-based chunk index.
        content: Chunk text.
        embedding: Embedding vector matching the configured dimension.
        metadata: Secret-safe chunk metadata.
        source_path: Optional source file path.
    """

    collection_id: str
    feature_key: str
    display_name: str
    source_item_id: str
    chunk_index: int
    content: str
    embedding: Sequence[float]
    metadata: Mapping[str, Any] = field(default_factory=dict)
    source_path: str | None = None


class SupabasePgvectorStore:
    """Backend-only adapter for Supabase Postgres pgvector search.

    Args:
        engine: Optional SQLAlchemy engine. When omitted, the app database
            settings create one from ``DATABASE_URL``.
        embedding_model: Embedding model label persisted with each row.
        expected_dim: Required embedding dimension.

    Raises:
        RuntimeError: If no database engine can be created.
    """

    def __init__(
        self,
        engine: Engine | None = None,
        embedding_model: str | None = None,
        expected_dim: int | None = None,
    ) -> None:
        self.engine = engine or create_sqlalchemy_engine()
        self.embedding_model = (
            embedding_model
            or os.getenv("VECTOR_EMBEDDING_MODEL")
            or os.getenv("OLLAMA_MODEL_EMBEDDING")
            or DEFAULT_EMBEDDING_MODEL
        )
        self.embedding_version = os.getenv("VECTOR_EMBEDDING_VERSION", "v1")
        self.expected_dim = int(
            expected_dim
            if expected_dim is not None
            else os.getenv("VECTOR_EMBEDDING_DIM", str(DEFAULT_EMBEDDING_DIM))
        )

    def upsert_document_chunks(self, chunks: Sequence[DocumentChunkInput]) -> int:
        """Upsert document chunks and embeddings.

        Args:
            chunks: Document chunk payloads.

        Returns:
            int: Number of chunks processed.
        """

        if not chunks:
            return 0
        with self.engine.begin() as conn:
            for chunk in chunks:
                metadata = dict(chunk.metadata)
                row = conn.execute(
                    text(
                        """
                        insert into public.document_chunks (
                          source_doc_id, source_path, title, doc_type, part_name,
                          chunk_index, content, content_hash, metadata, data_class, updated_at
                        ) values (
                          :source_doc_id, :source_path, :title, :doc_type, :part_name,
                          :chunk_index, :content, :content_hash, cast(:metadata as jsonb),
                          :data_class, now()
                        )
                        on conflict (source_doc_id, chunk_index) do update set
                          source_path = excluded.source_path,
                          title = excluded.title,
                          doc_type = excluded.doc_type,
                          part_name = excluded.part_name,
                          content = excluded.content,
                          content_hash = excluded.content_hash,
                          metadata = excluded.metadata,
                          data_class = excluded.data_class,
                          updated_at = now()
                        returning id
                        """
                    ),
                    {
                        "source_doc_id": chunk.source_doc_id,
                        "source_path": chunk.source_path,
                        "title": chunk.title,
                        "doc_type": chunk.doc_type,
                        "part_name": chunk.part_name,
                        "chunk_index": chunk.chunk_index,
                        "content": chunk.content,
                        "content_hash": content_hash(chunk.content),
                        "metadata": json.dumps(metadata, ensure_ascii=False),
                        "data_class": chunk.data_class,
                    },
                ).one()
                conn.execute(
                    text(
                        """
                        insert into public.document_embeddings (
                          chunk_id, embedding, embedding_model, embedding_dim,
                          embedding_version, embedded_at, metadata
                        ) values (
                          :chunk_id, cast(:embedding as extensions.vector(1024)),
                          :embedding_model, :embedding_dim, :embedding_version,
                          now(), cast(:metadata as jsonb)
                        )
                        on conflict (chunk_id) do update set
                          embedding = excluded.embedding,
                          embedding_model = excluded.embedding_model,
                          embedding_dim = excluded.embedding_dim,
                          embedding_version = excluded.embedding_version,
                          embedded_at = now(),
                          metadata = excluded.metadata
                        """
                    ),
                    {
                        "chunk_id": row.id,
                        "embedding": vector_literal(chunk.embedding, self.expected_dim),
                        "embedding_model": self.embedding_model,
                        "embedding_dim": self.expected_dim,
                        "embedding_version": self.embedding_version,
                        "metadata": json.dumps(metadata, ensure_ascii=False),
                    },
                )
        return len(chunks)

    def upsert_employee_embeddings(self, employees: Sequence[EmployeeEmbeddingInput]) -> int:
        """Upsert employee profile embeddings.

        Args:
            employees: Employee embedding payloads.

        Returns:
            int: Number of employee profiles processed.
        """

        if not employees:
            return 0
        with self.engine.begin() as conn:
            for employee in employees:
                conn.execute(
                    text(
                        """
                        insert into public.employee_embeddings (
                          employee_id, display_name, department, position, profile_text,
                          embedding, embedding_model, embedding_dim, metadata, data_class,
                          embedding_version, is_active, embedded_at, updated_at
                        ) values (
                          :employee_id, :display_name, :department, :position, :profile_text,
                          cast(:embedding as extensions.vector(1024)), :embedding_model,
                          :embedding_dim, cast(:metadata as jsonb), :data_class,
                          :embedding_version, :is_active, now(), now()
                        )
                        on conflict (employee_id) do update set
                          display_name = excluded.display_name,
                          department = excluded.department,
                          position = excluded.position,
                          profile_text = excluded.profile_text,
                          embedding = excluded.embedding,
                          embedding_model = excluded.embedding_model,
                          embedding_dim = excluded.embedding_dim,
                          embedding_version = excluded.embedding_version,
                          metadata = excluded.metadata,
                          data_class = excluded.data_class,
                          is_active = excluded.is_active,
                          embedded_at = now(),
                          updated_at = now()
                        """
                    ),
                    {
                        "employee_id": employee.employee_id,
                        "display_name": employee.display_name,
                        "department": employee.department,
                        "position": employee.position,
                        "profile_text": employee.profile_text,
                        "embedding": vector_literal(employee.embedding, self.expected_dim),
                        "embedding_model": self.embedding_model,
                        "embedding_dim": self.expected_dim,
                        "embedding_version": self.embedding_version,
                        "metadata": json.dumps(dict(employee.metadata), ensure_ascii=False),
                        "data_class": employee.data_class,
                        "is_active": employee.is_active,
                    },
                )
        return len(employees)

    def upsert_rag_chunks(self, chunks: Sequence[RagChunkInput]) -> int:
        """Upsert shared RAG chunks and embeddings.

        Args:
            chunks: RAG chunk payloads.

        Returns:
            int: Number of RAG chunks processed.
        """

        if not chunks:
            return 0
        with self.engine.begin() as conn:
            for chunk in chunks:
                metadata = dict(chunk.metadata)
                conn.execute(
                    text(
                        """
                        insert into public.rag_collections (
                          collection_id, feature_key, display_name, source_path, metadata, updated_at
                        ) values (
                          :collection_id, :feature_key, :display_name, :source_path,
                          '{}'::jsonb, now()
                        )
                        on conflict (collection_id) do update set
                          feature_key = excluded.feature_key,
                          display_name = excluded.display_name,
                          source_path = excluded.source_path,
                          updated_at = now()
                        """
                    ),
                    {
                        "collection_id": chunk.collection_id,
                        "feature_key": chunk.feature_key,
                        "display_name": chunk.display_name,
                        "source_path": chunk.source_path,
                    },
                )
                row = conn.execute(
                    text(
                        """
                        insert into public.rag_chunks (
                          collection_id, source_item_id, chunk_index, content,
                          content_hash, metadata, updated_at
                        ) values (
                          :collection_id, :source_item_id, :chunk_index, :content,
                          :content_hash, cast(:metadata as jsonb), now()
                        )
                        on conflict (collection_id, source_item_id, chunk_index) do update set
                          content = excluded.content,
                          content_hash = excluded.content_hash,
                          metadata = excluded.metadata,
                          updated_at = now()
                        returning id
                        """
                    ),
                    {
                        "collection_id": chunk.collection_id,
                        "source_item_id": chunk.source_item_id,
                        "chunk_index": chunk.chunk_index,
                        "content": chunk.content,
                        "content_hash": content_hash(chunk.content),
                        "metadata": json.dumps(metadata, ensure_ascii=False),
                    },
                ).one()
                conn.execute(
                    text(
                        """
                        insert into public.rag_chunk_embeddings (
                          chunk_id, embedding, embedding_model, embedding_dim,
                          embedding_version, embedded_at, metadata
                        ) values (
                          :chunk_id, cast(:embedding as extensions.vector(1024)),
                          :embedding_model, :embedding_dim, :embedding_version,
                          now(), cast(:metadata as jsonb)
                        )
                        on conflict (chunk_id) do update set
                          embedding = excluded.embedding,
                          embedding_model = excluded.embedding_model,
                          embedding_dim = excluded.embedding_dim,
                          embedding_version = excluded.embedding_version,
                          embedded_at = now(),
                          metadata = excluded.metadata
                        """
                    ),
                    {
                        "chunk_id": row.id,
                        "embedding": vector_literal(chunk.embedding, self.expected_dim),
                        "embedding_model": self.embedding_model,
                        "embedding_dim": self.expected_dim,
                        "embedding_version": self.embedding_version,
                        "metadata": json.dumps(metadata, ensure_ascii=False),
                    },
                )
        return len(chunks)

    def hybrid_search_documents(
        self,
        query_text: str,
        query_embedding: Sequence[float],
        match_count: int = 10,
        doc_type_filter: str | None = None,
        part_name_filter: str | None = None,
        metadata_filter: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Run backend-only hybrid document search.

        Args:
            query_text: User query text.
            query_embedding: Query embedding.
            match_count: Maximum result count.
            doc_type_filter: Optional exact document type.
            part_name_filter: Optional exact part name.
            metadata_filter: JSONB containment filter.

        Returns:
            list[dict[str, Any]]: RPC rows as dictionaries.
        """

        with self.engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    select *
                      from private.hybrid_search_document_chunks(
                        :query_text,
                        cast(:query_embedding as extensions.vector(1024)),
                        :match_count,
                        :doc_type_filter,
                        :part_name_filter,
                        cast(:metadata_filter as jsonb)
                      )
                    """
                ),
                {
                    "query_text": query_text,
                    "query_embedding": vector_literal(query_embedding, self.expected_dim),
                    "match_count": match_count,
                    "doc_type_filter": doc_type_filter,
                    "part_name_filter": part_name_filter,
                    "metadata_filter": json.dumps(dict(metadata_filter or {}), ensure_ascii=False),
                },
            )
            return [dict(row._mapping) for row in rows]

    def list_documents_by_metadata(
        self,
        match_count: int = 10,
        doc_type_filter: str | None = None,
        part_name_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        """검색어 없이 doc_type / part_name 필터만으로 최신 문서를 반환한다.

        문서 유형 드롭다운만 선택해도 결과가 나오는 UX 를 위해 도입.
        벡터/BM25 점수가 없으므로 created_at desc 로 정렬한다.
        """
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    select
                      dc.id            as chunk_id,
                      dc.source_doc_id as source_doc_id,
                      dc.title         as title,
                      dc.content       as content,
                      dc.metadata      as metadata,
                      0.0::double precision as score,
                      0.0::double precision as vector_similarity,
                      0.0::double precision as keyword_score
                    from public.document_chunks dc
                    where (cast(:doc_type_filter as text) is null or dc.doc_type = cast(:doc_type_filter as text))
                      and (cast(:part_name_filter as text) is null or dc.part_name = cast(:part_name_filter as text))
                    order by dc.created_at desc, dc.chunk_index asc
                    limit greatest(1, least(:match_count, 100))
                    """
                ),
                {
                    "doc_type_filter": doc_type_filter,
                    "part_name_filter": part_name_filter,
                    "match_count": match_count,
                },
            )
            return [dict(row._mapping) for row in rows]

    def search_employees(
        self,
        query_embedding: Sequence[float],
        match_count: int = 20,
        department_filter: str | None = None,
        metadata_filter: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Run backend-only employee semantic search.

        Args:
            query_embedding: Query embedding.
            match_count: Maximum result count.
            department_filter: Optional exact department filter.
            metadata_filter: JSONB containment filter.

        Returns:
            list[dict[str, Any]]: RPC rows as dictionaries.
        """

        with self.engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    select *
                      from private.match_employee_profiles(
                        cast(:query_embedding as extensions.vector(1024)),
                        :match_count,
                        :department_filter,
                        cast(:metadata_filter as jsonb)
                      )
                    """
                ),
                {
                    "query_embedding": vector_literal(query_embedding, self.expected_dim),
                    "match_count": match_count,
                    "department_filter": department_filter,
                    "metadata_filter": json.dumps(dict(metadata_filter or {}), ensure_ascii=False),
                },
            )
            return [dict(row._mapping) for row in rows]

    def search_rag(
        self,
        query_embedding: Sequence[float],
        collection_filter: str | None,
        match_count: int = 10,
        metadata_filter: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Run backend-only shared RAG semantic search.

        Args:
            query_embedding: Query embedding.
            collection_filter: Optional collection id.
            match_count: Maximum result count.
            metadata_filter: JSONB containment filter.

        Returns:
            list[dict[str, Any]]: RPC rows as dictionaries.
        """

        with self.engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    select *
                      from private.match_rag_chunks(
                        cast(:query_embedding as extensions.vector(1024)),
                        :match_count,
                        :collection_filter,
                        cast(:metadata_filter as jsonb)
                      )
                    """
                ),
                {
                    "query_embedding": vector_literal(query_embedding, self.expected_dim),
                    "match_count": match_count,
                    "collection_filter": collection_filter,
                    "metadata_filter": json.dumps(dict(metadata_filter or {}), ensure_ascii=False),
                },
            )
            return [dict(row._mapping) for row in rows]
