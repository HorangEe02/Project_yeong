"""Create learning vector tables.

Revision ID: 0005_create_learning_vector_tables
Revises: 0004_create_p1_supplement_health
Create Date: 2026-05-15 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_create_learning_vector_tables"
down_revision: str | Sequence[str] | None = "0004_create_p1_supplement_health"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


class PGVectorType(sa.types.UserDefinedType[tuple[float, ...]]):
    """Alembic-local pgvector column type wrapper."""

    cache_ok = True

    def get_col_spec(self, **kw: object) -> str:
        """Return the PostgreSQL type name.

        Args:
            **kw: SQLAlchemy compiler keyword arguments.

        Returns:
            The pgvector type name.
        """
        _ = kw
        return "extensions.vector"


def upgrade() -> None:
    """Apply this migration."""
    op.execute("CREATE SCHEMA IF NOT EXISTS extensions")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions")
    op.create_table(
        "learning_image_objects",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_subject_hash", sa.String(length=64), nullable=False),
        sa.Column("analysis_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("image_sha256", sa.String(length=64), nullable=False),
        sa.Column("object_uri", sa.String(length=1024), nullable=False),
        sa.Column("object_storage_provider", sa.String(length=32), nullable=False),
        sa.Column("object_version_id", sa.String(length=256), nullable=True),
        sa.Column("image_mime_type", sa.String(length=32), nullable=False),
        sa.Column("image_size_bytes", sa.Integer(), nullable=False),
        sa.Column("retained_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "consent_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(owner_subject_hash) = 64",
            name=op.f("ck_learning_image_objects_owner_subject_hash_length"),
        ),
        sa.CheckConstraint(
            "length(image_sha256) = 64",
            name=op.f("ck_learning_image_objects_image_sha256_length"),
        ),
        sa.CheckConstraint(
            "image_size_bytes > 0",
            name=op.f("ck_learning_image_objects_image_size_positive"),
        ),
        sa.CheckConstraint(
            "image_mime_type IN ('image/jpeg', 'image/png', 'image/webp')",
            name=op.f("ck_learning_image_objects_image_mime_type_allowed"),
        ),
        sa.CheckConstraint(
            (
                "status IN ("
                "'awaiting_confirmation', 'ready', 'embedded', "
                "'deleted', 'cancelled', 'failed'"
                ")"
            ),
            name=op.f("ck_learning_image_objects_learning_image_object_status_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["analysis_id"],
            ["supplement_analysis_runs.id"],
            name=op.f("fk_learning_image_objects_analysis_id_supplement_analysis_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_learning_image_objects")),
        sa.UniqueConstraint(
            "owner_subject_hash",
            "analysis_id",
            "image_sha256",
            name="uq_learning_image_objects_owner_analysis_hash",
        ),
    )
    op.create_index(
        "ix_learning_image_objects_owner_status",
        "learning_image_objects",
        ["owner_subject_hash", "status"],
        unique=False,
    )
    op.create_index(
        "ix_learning_image_objects_analysis_id",
        "learning_image_objects",
        ["analysis_id"],
        unique=False,
    )
    op.create_index(
        "ix_learning_image_objects_retained_until",
        "learning_image_objects",
        ["retained_until"],
        unique=False,
    )

    op.create_table(
        "image_embedding_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("image_object_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("analysis_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_subject_hash", sa.String(length=64), nullable=False),
        sa.Column("embedding_model", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by", sa.String(length=120), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.String(length=512), nullable=True),
        sa.Column(
            "metadata_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(owner_subject_hash) = 64",
            name=op.f("ck_image_embedding_jobs_owner_subject_hash_length"),
        ),
        sa.CheckConstraint(
            "attempt_count >= 0",
            name=op.f("ck_image_embedding_jobs_attempt_count_nonnegative"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'succeeded', 'failed', 'dead', 'cancelled')",
            name=op.f("ck_image_embedding_jobs_image_embedding_job_status_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["analysis_id"],
            ["supplement_analysis_runs.id"],
            name=op.f("fk_image_embedding_jobs_analysis_id_supplement_analysis_runs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["image_object_id"],
            ["learning_image_objects.id"],
            name=op.f("fk_image_embedding_jobs_image_object_id_learning_image_objects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_image_embedding_jobs")),
        sa.UniqueConstraint(
            "image_object_id",
            "embedding_model",
            name="uq_image_embedding_jobs_object_model",
        ),
    )
    op.create_index(
        "ix_image_embedding_jobs_status_next_run",
        "image_embedding_jobs",
        ["status", "next_run_at"],
        unique=False,
    )
    op.create_index(
        "ix_image_embedding_jobs_owner_status",
        "image_embedding_jobs",
        ["owner_subject_hash", "status"],
        unique=False,
    )
    op.create_index(
        "ix_image_embedding_jobs_analysis_id",
        "image_embedding_jobs",
        ["analysis_id"],
        unique=False,
    )

    op.create_table(
        "image_embedding_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_subject_hash", sa.String(length=64), nullable=False),
        sa.Column("analysis_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("image_object_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("image_sha256", sa.String(length=64), nullable=False),
        sa.Column("embedding_model", sa.String(length=120), nullable=False),
        sa.Column("embedding_dimensions", sa.Integer(), nullable=False),
        sa.Column("embedding", PGVectorType(), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(owner_subject_hash) = 64",
            name=op.f("ck_image_embedding_records_owner_subject_hash_length"),
        ),
        sa.CheckConstraint(
            "length(image_sha256) = 64",
            name=op.f("ck_image_embedding_records_image_sha256_length"),
        ),
        sa.CheckConstraint(
            "embedding_dimensions > 0",
            name=op.f("ck_image_embedding_records_embedding_dimensions_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["analysis_id"],
            ["supplement_analysis_runs.id"],
            name=op.f("fk_image_embedding_records_analysis_id_supplement_analysis_runs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["image_object_id"],
            ["learning_image_objects.id"],
            name=op.f("fk_image_embedding_records_image_object_id_learning_image_objects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_image_embedding_records")),
        sa.UniqueConstraint(
            "owner_subject_hash",
            "analysis_id",
            "embedding_model",
            "image_sha256",
            name="uq_image_embedding_records_owner_analysis_model_hash",
        ),
    )
    op.create_index(
        "ix_image_embedding_records_owner_created_at",
        "image_embedding_records",
        ["owner_subject_hash", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_image_embedding_records_analysis_id",
        "image_embedding_records",
        ["analysis_id"],
        unique=False,
    )
    op.create_index(
        "ix_image_embedding_records_image_object_id",
        "image_embedding_records",
        ["image_object_id"],
        unique=False,
    )


def downgrade() -> None:
    """Rollback this migration."""
    op.drop_index(
        "ix_image_embedding_records_image_object_id",
        table_name="image_embedding_records",
    )
    op.drop_index("ix_image_embedding_records_analysis_id", table_name="image_embedding_records")
    op.drop_index(
        "ix_image_embedding_records_owner_created_at",
        table_name="image_embedding_records",
    )
    op.drop_table("image_embedding_records")
    op.drop_index("ix_image_embedding_jobs_analysis_id", table_name="image_embedding_jobs")
    op.drop_index("ix_image_embedding_jobs_owner_status", table_name="image_embedding_jobs")
    op.drop_index("ix_image_embedding_jobs_status_next_run", table_name="image_embedding_jobs")
    op.drop_table("image_embedding_jobs")
    op.drop_index("ix_learning_image_objects_retained_until", table_name="learning_image_objects")
    op.drop_index("ix_learning_image_objects_analysis_id", table_name="learning_image_objects")
    op.drop_index("ix_learning_image_objects_owner_status", table_name="learning_image_objects")
    op.drop_table("learning_image_objects")
