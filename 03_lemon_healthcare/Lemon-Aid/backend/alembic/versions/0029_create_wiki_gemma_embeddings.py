"""Create the second-model WIKI embedding table (EmbeddingGemma, 768-dim).

Adds ``wiki_chunk_embeddings_gemma`` so the same wiki chunks can be embedded by a
second model (Google ``embeddinggemma``, 768-dim) alongside the existing
``wiki_chunk_embeddings`` (Ollama ``bge-m3``, 1024-dim). pgvector columns are
dimension-typed, so a different-dimension model needs its own table rather than a
new row in the 1024-dim column.

Mirrors the 0028 pattern exactly: ``extensions.vector(N)`` via a local
``PGVectorType``, an HNSW cosine index (``extensions.vector_cosine_ops``), a
``(chunk_id, embedding_model)`` uniqueness constraint, and a read-only RLS policy
for the ``lemon_app`` request role. Reference knowledge only (no user PII).

Revision ID: 0029_create_wiki_gemma_embeddings
Revises: 0028_create_wiki_rag_tables
Create Date: 2026-06-06 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0029_create_wiki_gemma_embeddings"
down_revision: str | Sequence[str] | None = "0028_create_wiki_rag_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "lemon_app"
CATALOG_POLICY = "lemon_app_catalog_read"
GEMMA_TABLE = "wiki_chunk_embeddings_gemma"
GEMMA_EMBEDDING_DIMENSIONS = 768
GEMMA_HNSW_INDEX = "ix_wiki_chunk_embeddings_gemma_hnsw"


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
    """Create the Gemma embedding table, its HNSW index, and the read policy."""
    # The shared pgvector extension is installed by 0028; keep idempotent guards so
    # this revision can also apply to a database provisioned independently.
    op.execute("CREATE SCHEMA IF NOT EXISTS extensions")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions")

    op.create_table(
        GEMMA_TABLE,
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("embedding", PGVectorType(GEMMA_EMBEDDING_DIMENSIONS), nullable=False),
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
            name=op.f("ck_wiki_chunk_embeddings_gemma_embedding_dimensions_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["chunk_id"],
            ["wiki_chunks.id"],
            name=op.f("fk_wiki_chunk_embeddings_gemma_chunk_id_wiki_chunks"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_wiki_chunk_embeddings_gemma")),
        sa.UniqueConstraint(
            "chunk_id",
            "embedding_model",
            name=op.f("uq_wiki_chunk_embeddings_gemma_chunk_model"),
        ),
    )
    # HNSW cosine index works on empty tables (no training set required).
    op.execute(
        f"CREATE INDEX {GEMMA_HNSW_INDEX} "
        f"ON public.{GEMMA_TABLE} "
        "USING hnsw (embedding extensions.vector_cosine_ops)"
    )

    _create_catalog_read_policy(GEMMA_TABLE)


def downgrade() -> None:
    """Drop the Gemma embedding table. The shared pgvector extension stays."""
    op.execute(f"DROP INDEX IF EXISTS public.{GEMMA_HNSW_INDEX}")
    op.drop_table(GEMMA_TABLE)
