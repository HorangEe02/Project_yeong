"""Create backend-only media object tables.

Revision ID: 0014_create_backend_only_media_tables
Revises: 0013_index_user_supplement_foreign_keys
Create Date: 2026-05-27 00:00:00.000000

These tables hold private object references and sanitized processing metadata
for retained user media. They are backend-only by default: RLS is enabled and
Supabase client-role grants are explicitly revoked. Raw image bytes, raw OCR
text, provider payloads, request headers, and secrets are intentionally absent.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014_create_backend_only_media_tables"
down_revision: str | Sequence[str] | None = "0013_index_user_supplement_foreign_keys"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BACKEND_ONLY_MEDIA_TABLES = (
    "media_objects",
    "media_processing_runs",
    "supplement_image_evidence",
)


def upgrade() -> None:
    """Create backend-only media tables and keep Supabase Data API fail-closed."""
    op.create_table(
        "media_objects",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_subject_hash", sa.String(length=64), nullable=False),
        sa.Column("domain", sa.String(length=40), nullable=False),
        sa.Column("source_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("object_storage_provider", sa.String(length=32), nullable=False),
        sa.Column("object_ref", sa.String(length=1024), nullable=False),
        sa.Column("object_version_id", sa.String(length=256), nullable=True),
        sa.Column("image_sha256", sa.String(length=64), nullable=False),
        sa.Column("image_mime_type", sa.String(length=32), nullable=False),
        sa.Column("image_size_bytes", sa.Integer(), nullable=False),
        sa.Column("width_px", sa.Integer(), nullable=True),
        sa.Column("height_px", sa.Integer(), nullable=True),
        sa.Column(
            "exif_stripped",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
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
            name=op.f("ck_media_objects_owner_subject_hash_length"),
        ),
        sa.CheckConstraint(
            "length(image_sha256) = 64",
            name=op.f("ck_media_objects_image_sha256_length"),
        ),
        sa.CheckConstraint(
            "image_size_bytes > 0",
            name=op.f("ck_media_objects_image_size_positive"),
        ),
        sa.CheckConstraint(
            "width_px IS NULL OR width_px > 0",
            name=op.f("ck_media_objects_width_px_positive"),
        ),
        sa.CheckConstraint(
            "height_px IS NULL OR height_px > 0",
            name=op.f("ck_media_objects_height_px_positive"),
        ),
        sa.CheckConstraint(
            (
                "domain IN ('supplement_label', 'food_meal', "
                "'regulated_document', 'profile_attachment')"
            ),
            name=op.f("ck_media_objects_media_object_domain_allowed"),
        ),
        sa.CheckConstraint(
            "object_storage_provider IN ('supabase_s3', 's3', 'local')",
            name=op.f("ck_media_objects_media_object_storage_provider_allowed"),
        ),
        sa.CheckConstraint(
            (
                "object_ref <> '' AND object_ref NOT LIKE '%://%' "
                "AND object_ref NOT LIKE '/%' AND object_ref NOT LIKE '%..%'"
            ),
            name=op.f("ck_media_objects_media_object_ref_private"),
        ),
        sa.CheckConstraint(
            "image_mime_type IN ('image/jpeg', 'image/png', 'image/webp')",
            name=op.f("ck_media_objects_media_object_image_mime_type_allowed"),
        ),
        sa.CheckConstraint(
            (
                "status IN ('temporary', 'retained', 'pending_review', "
                "'approved', 'deleted', 'failed')"
            ),
            name=op.f("ck_media_objects_media_object_status_allowed"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_media_objects")),
    )
    op.create_index(
        "ix_media_objects_owner_domain_created_at",
        "media_objects",
        ["owner_subject_hash", "domain", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_media_objects_owner_status",
        "media_objects",
        ["owner_subject_hash", "status"],
        unique=False,
    )
    op.create_index(
        "ix_media_objects_retained_until",
        "media_objects",
        ["retained_until"],
        unique=False,
    )
    op.create_index(
        "ix_media_objects_source_run_id",
        "media_objects",
        ["source_run_id"],
        unique=False,
    )

    op.create_table(
        "supplement_image_evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("analysis_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("media_object_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("image_role", sa.String(length=40), nullable=False),
        sa.Column("quality_status", sa.String(length=40), nullable=False),
        sa.Column(
            "quality_codes",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "roi_snapshot",
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
            "image_role IN ('front', 'supplement_facts', 'barcode', 'side_panel', 'other')",
            name=op.f("ck_supplement_image_evidence_image_role_allowed"),
        ),
        sa.CheckConstraint(
            "quality_status IN ('usable', 'retake_recommended', 'rejected')",
            name=op.f("ck_supplement_image_evidence_quality_status_allowed"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(quality_codes) = 'array'",
            name=op.f("ck_supplement_image_evidence_quality_codes_array"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(roi_snapshot) = 'object'",
            name=op.f("ck_supplement_image_evidence_roi_snapshot_object"),
        ),
        sa.ForeignKeyConstraint(
            ["analysis_run_id"],
            ["supplement_analysis_runs.id"],
            name=op.f("fk_supplement_image_evidence_analysis_run_id_supplement_analysis_runs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["media_object_id"],
            ["media_objects.id"],
            name=op.f("fk_supplement_image_evidence_media_object_id_media_objects"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_supplement_image_evidence")),
    )
    op.create_index(
        "ix_supplement_image_evidence_analysis_run_id",
        "supplement_image_evidence",
        ["analysis_run_id"],
        unique=False,
    )
    op.create_index(
        "ix_supplement_image_evidence_media_object_id",
        "supplement_image_evidence",
        ["media_object_id"],
        unique=False,
    )
    op.create_index(
        "ix_supplement_image_evidence_quality_status",
        "supplement_image_evidence",
        ["quality_status"],
        unique=False,
    )

    op.create_table(
        "media_processing_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("media_object_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pipeline_type", sa.String(length=40), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=True),
        sa.Column("model_version", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("output_hash", sa.String(length=64), nullable=True),
        sa.Column(
            "sanitized_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "warning_codes",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
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
            (
                "pipeline_type IN ('supplement_ocr', 'food_detection', "
                "'vision_roi', 'regulated_ocr', 'quality_check')"
            ),
            name=op.f("ck_media_processing_runs_media_processing_pipeline_type_allowed"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'succeeded', 'requires_review', 'failed')",
            name=op.f("ck_media_processing_runs_media_processing_status_allowed"),
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name=op.f("ck_media_processing_runs_media_processing_confidence_range"),
        ),
        sa.CheckConstraint(
            "output_hash IS NULL OR length(output_hash) = 64",
            name=op.f("ck_media_processing_runs_media_processing_output_hash_length"),
        ),
        sa.ForeignKeyConstraint(
            ["media_object_id"],
            ["media_objects.id"],
            name=op.f("fk_media_processing_runs_media_object_id_media_objects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_media_processing_runs")),
    )
    op.create_index(
        "ix_media_processing_runs_media_object_id",
        "media_processing_runs",
        ["media_object_id"],
        unique=False,
    )
    op.create_index(
        "ix_media_processing_runs_pipeline_status",
        "media_processing_runs",
        ["pipeline_type", "status"],
        unique=False,
    )
    op.create_index(
        "ix_media_processing_runs_created_at",
        "media_processing_runs",
        ["created_at"],
        unique=False,
    )

    for table_name in BACKEND_ONLY_MEDIA_TABLES:
        op.execute(f"ALTER TABLE public.{table_name} ENABLE ROW LEVEL SECURITY")
        op.execute(f"""
            COMMENT ON TABLE public.{table_name} IS
            'Internal media pipeline table. Direct backend PostgreSQL access only; Supabase Data API grants are intentionally revoked and RLS is fail-closed.';
            """)

    op.execute("""
        REVOKE ALL PRIVILEGES ON TABLE
            public.media_objects,
            public.media_processing_runs,
            public.supplement_image_evidence
        FROM PUBLIC
        """)
    op.execute("""
        DO $$
        DECLARE
            role_name text;
        BEGIN
            FOREACH role_name IN ARRAY ARRAY['anon', 'authenticated', 'service_role'] LOOP
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
                    EXECUTE format(
                        'REVOKE ALL PRIVILEGES ON TABLE public.media_objects, public.media_processing_runs, public.supplement_image_evidence FROM %I',
                        role_name
                    );
                END IF;
            END LOOP;
        END
        $$;
        """)


def downgrade() -> None:
    """Drop backend-only media tables."""
    op.drop_table("media_processing_runs")
    op.drop_table("supplement_image_evidence")
    op.drop_table("media_objects")
