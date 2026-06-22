"""Create LLM-WIKI semantic RAG tables (pgvector) and entity->wiki links.

Indexes the local Obsidian LLM-WIKI (`llm_wiki_path`) into the DB for semantic
retrieval that grounds Ollama explanations with citable, accurate sources:

- ``wiki_documents``        one row per markdown page (slug, title, category, hash)
- ``wiki_chunks``          heading-bounded sections of each document
- ``wiki_chunk_embeddings``pgvector embeddings (Ollama, e.g. bge-m3, 1024-dim)
- ``entity_wiki_links``    explicit DB-entity -> wiki-slug links (supplement
                           categories, food cuisines, …) from the wiki hub pages

These are reference-knowledge tables (no user PII), exposed read-only to the
backend request role. pgvector lives in the ``extensions`` schema (Supabase
convention), reusing the install from 0005.

Revision ID: 0028_create_wiki_rag_tables
Revises: 0027_create_food_nutrition_table
Create Date: 2026-06-05 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0028_create_wiki_rag_tables"
down_revision: str | Sequence[str] | None = "0027_create_food_nutrition_table"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "lemon_app"
CATALOG_POLICY = "lemon_app_catalog_read"
WIKI_EMBEDDING_DIMENSIONS = 1024


class PGVectorType(sa.types.UserDefinedType[tuple[float, ...]]):
    """Alembic-local pgvector column type wrapper (fixed dimension)."""

    cache_ok = True

    def __init__(self, dimensions: int | None = None) -> None:
        """Store the optional fixed vector dimension.

        Args:
            dimensions: Fixed embedding dimension, or None for an unbounded vector.
        """
        self.dimensions = dimensions

    def get_col_spec(self, **kw: object) -> str:
        """Return the PostgreSQL pgvector type name.

        Args:
            **kw: SQLAlchemy compiler keyword arguments.

        Returns:
            The pgvector type name, dimensioned when configured.
        """
        _ = kw
        if self.dimensions is None:
            return "extensions.vector"
        return f"extensions.vector({self.dimensions})"


def _create_catalog_read_policy(table_name: str) -> None:
    """Expose reference rows to the backend request role without user-data writes."""
    op.execute(f"ALTER TABLE public.{table_name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"""
        CREATE POLICY {CATALOG_POLICY} ON public.{table_name}
          FOR SELECT TO {APP_ROLE}
          USING (true)
        """)
    op.execute(f"ALTER TABLE public.{table_name} FORCE ROW LEVEL SECURITY")
    op.execute(f"GRANT SELECT ON public.{table_name} TO {APP_ROLE}")


def upgrade() -> None:
    """Create wiki RAG tables, the vector index, and read-only policies."""
    op.execute("CREATE SCHEMA IF NOT EXISTS extensions")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions")

    op.create_table(
        "wiki_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slug", sa.String(length=200), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=True),
        sa.Column("rel_path", sa.String(length=512), nullable=False),
        sa.Column(
            "tags",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("source_manifest_version", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("slug <> ''", name=op.f("ck_wiki_documents_slug_nonempty")),
        sa.CheckConstraint("title <> ''", name=op.f("ck_wiki_documents_title_nonempty")),
        sa.CheckConstraint("rel_path <> ''", name=op.f("ck_wiki_documents_rel_path_nonempty")),
        sa.CheckConstraint(
            "jsonb_typeof(tags) = 'array'", name=op.f("ck_wiki_documents_tags_array")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_wiki_documents")),
        sa.UniqueConstraint("slug", name=op.f("uq_wiki_documents_slug")),
    )
    op.create_index(op.f("ix_wiki_documents_category"), "wiki_documents", ["category"])

    op.create_table(
        "wiki_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("heading", sa.String(length=300), nullable=True),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("content <> ''", name=op.f("ck_wiki_chunks_content_nonempty")),
        sa.CheckConstraint("chunk_index >= 0", name=op.f("ck_wiki_chunks_chunk_index_nonnegative")),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["wiki_documents.id"],
            name=op.f("fk_wiki_chunks_document_id_wiki_documents"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_wiki_chunks")),
        sa.UniqueConstraint(
            "document_id", "chunk_index", name=op.f("uq_wiki_chunks_document_chunk")
        ),
    )
    op.create_index(op.f("ix_wiki_chunks_document_id"), "wiki_chunks", ["document_id"])

    op.create_table(
        "wiki_chunk_embeddings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("embedding", PGVectorType(WIKI_EMBEDDING_DIMENSIONS), nullable=False),
        sa.Column("embedding_model", sa.String(length=120), nullable=False),
        sa.Column("embedding_dimensions", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "embedding_dimensions > 0",
            name=op.f("ck_wiki_chunk_embeddings_embedding_dimensions_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["chunk_id"],
            ["wiki_chunks.id"],
            name=op.f("fk_wiki_chunk_embeddings_chunk_id_wiki_chunks"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_wiki_chunk_embeddings")),
        sa.UniqueConstraint(
            "chunk_id", "embedding_model", name=op.f("uq_wiki_chunk_embeddings_chunk_model")
        ),
    )
    # HNSW cosine index works on empty tables (no training set required).
    op.execute(
        "CREATE INDEX ix_wiki_chunk_embeddings_hnsw "
        "ON public.wiki_chunk_embeddings "
        "USING hnsw (embedding extensions.vector_cosine_ops)"
    )

    op.create_table(
        "entity_wiki_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_type", sa.String(length=40), nullable=False),
        sa.Column("entity_key", sa.String(length=120), nullable=False),
        sa.Column("wiki_slug", sa.String(length=200), nullable=False),
        sa.Column(
            "relation", sa.String(length=40), nullable=False, server_default=sa.text("'primary'")
        ),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "entity_type <> ''", name=op.f("ck_entity_wiki_links_entity_type_nonempty")
        ),
        sa.CheckConstraint(
            "entity_key <> ''", name=op.f("ck_entity_wiki_links_entity_key_nonempty")
        ),
        sa.CheckConstraint("wiki_slug <> ''", name=op.f("ck_entity_wiki_links_wiki_slug_nonempty")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_entity_wiki_links")),
        sa.UniqueConstraint(
            "entity_type", "entity_key", "wiki_slug", name=op.f("uq_entity_wiki_links_entity_slug")
        ),
    )
    op.create_index(
        op.f("ix_entity_wiki_links_entity"), "entity_wiki_links", ["entity_type", "entity_key"]
    )

    for table_name in (
        "wiki_documents",
        "wiki_chunks",
        "wiki_chunk_embeddings",
        "entity_wiki_links",
    ):
        _create_catalog_read_policy(table_name)


def downgrade() -> None:
    """Drop wiki RAG tables (FK-safe order). The shared pgvector extension stays."""
    op.drop_index(op.f("ix_entity_wiki_links_entity"), table_name="entity_wiki_links")
    op.drop_table("entity_wiki_links")
    op.execute("DROP INDEX IF EXISTS public.ix_wiki_chunk_embeddings_hnsw")
    op.drop_table("wiki_chunk_embeddings")
    op.drop_index(op.f("ix_wiki_chunks_document_id"), table_name="wiki_chunks")
    op.drop_table("wiki_chunks")
    op.drop_index(op.f("ix_wiki_documents_category"), table_name="wiki_documents")
    op.drop_table("wiki_documents")
