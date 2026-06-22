"""Create backend-only food and meal preview tables.

Revision ID: 0015_create_food_meal_tables
Revises: 0014_create_backend_only_media_tables
Create Date: 2026-05-27 00:00:00.000000

These tables hold current-user meal records and sanitized food image analysis
previews. They are created fail-closed for Supabase client roles: RLS is
enabled and Data API grants are explicitly revoked. Original images, OCR text,
provider payloads, request headers, and secrets are intentionally absent.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0015_create_food_meal_tables"
down_revision: str | Sequence[str] | None = "0014_create_backend_only_media_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FOOD_MEAL_TABLES = (
    "meal_records",
    "meal_food_items",
    "food_image_analysis_runs",
)


def upgrade() -> None:
    """Create food/meal tables and keep Supabase Data API fail-closed."""
    op.create_table(
        "meal_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_subject", sa.String(length=512), nullable=False),
        sa.Column("client_request_id", sa.String(length=80), nullable=True),
        sa.Column("eaten_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("meal_type", sa.String(length=24), nullable=False),
        sa.Column("source", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "nutrition_summary",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
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
            "owner_subject <> ''",
            name=op.f("ck_meal_records_owner_subject_nonempty"),
        ),
        sa.CheckConstraint(
            "meal_type IN ('breakfast', 'lunch', 'dinner', 'snack', 'unknown')",
            name=op.f("ck_meal_records_meal_type_allowed"),
        ),
        sa.CheckConstraint(
            "source IN ('camera', 'gallery', 'manual', 'imported')",
            name=op.f("ck_meal_records_meal_source_allowed"),
        ),
        sa.CheckConstraint(
            "status IN ('requires_confirmation', 'confirmed', 'deleted', 'failed')",
            name=op.f("ck_meal_records_meal_status_allowed"),
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name=op.f("ck_meal_records_meal_confidence_range"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(nutrition_summary) = 'object'",
            name=op.f("ck_meal_records_nutrition_summary_object"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_meal_records")),
    )
    op.create_index(
        "ix_meal_records_owner_eaten_at",
        "meal_records",
        ["owner_subject", "eaten_at"],
        unique=False,
    )
    op.create_index(
        "ix_meal_records_owner_status",
        "meal_records",
        ["owner_subject", "status"],
        unique=False,
    )
    op.create_index(
        "ix_meal_records_owner_deleted_at",
        "meal_records",
        ["owner_subject", "deleted_at"],
        unique=False,
    )

    op.create_table(
        "meal_food_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("meal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("food_name_text", sa.String(length=160), nullable=False),
        sa.Column("canonical_food_id", sa.String(length=120), nullable=True),
        sa.Column("portion_amount", sa.Numeric(12, 4), nullable=True),
        sa.Column("portion_unit", sa.String(length=40), nullable=True),
        sa.Column("kcal", sa.Numeric(10, 2), nullable=True),
        sa.Column("carb_g", sa.Numeric(10, 2), nullable=True),
        sa.Column("protein_g", sa.Numeric(10, 2), nullable=True),
        sa.Column("fat_g", sa.Numeric(10, 2), nullable=True),
        sa.Column("sodium_mg", sa.Numeric(12, 2), nullable=True),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
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
            "food_name_text <> ''",
            name=op.f("ck_meal_food_items_food_name_text_nonempty"),
        ),
        sa.CheckConstraint(
            "portion_amount IS NULL OR portion_amount >= 0",
            name=op.f("ck_meal_food_items_portion_nonnegative"),
        ),
        sa.CheckConstraint(
            "kcal IS NULL OR kcal >= 0",
            name=op.f("ck_meal_food_items_kcal_nonnegative"),
        ),
        sa.CheckConstraint(
            "carb_g IS NULL OR carb_g >= 0",
            name=op.f("ck_meal_food_items_carb_g_nonnegative"),
        ),
        sa.CheckConstraint(
            "protein_g IS NULL OR protein_g >= 0",
            name=op.f("ck_meal_food_items_protein_g_nonnegative"),
        ),
        sa.CheckConstraint(
            "fat_g IS NULL OR fat_g >= 0",
            name=op.f("ck_meal_food_items_fat_g_nonnegative"),
        ),
        sa.CheckConstraint(
            "sodium_mg IS NULL OR sodium_mg >= 0",
            name=op.f("ck_meal_food_items_sodium_mg_nonnegative"),
        ),
        sa.CheckConstraint(
            "source IN ('vision', 'manual', 'database_match')",
            name=op.f("ck_meal_food_items_meal_food_source_allowed"),
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name=op.f("ck_meal_food_items_meal_food_confidence_range"),
        ),
        sa.CheckConstraint(
            "sort_order >= 0",
            name=op.f("ck_meal_food_items_sort_order_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["meal_id"],
            ["meal_records.id"],
            name=op.f("fk_meal_food_items_meal_id_meal_records"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_meal_food_items")),
    )
    op.create_index(
        "ix_meal_food_items_meal_id",
        "meal_food_items",
        ["meal_id"],
        unique=False,
    )
    op.create_index(
        "ix_meal_food_items_canonical_food_id",
        "meal_food_items",
        ["canonical_food_id"],
        unique=False,
    )

    op.create_table(
        "food_image_analysis_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_subject", sa.String(length=512), nullable=False),
        sa.Column("client_request_id", sa.String(length=80), nullable=True),
        sa.Column("media_object_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("meal_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("image_sha256", sa.String(length=64), nullable=False),
        sa.Column("image_mime_type", sa.String(length=32), nullable=False),
        sa.Column("image_size_bytes", sa.Integer(), nullable=False),
        sa.Column("detector_model", sa.String(length=120), nullable=True),
        sa.Column("classifier_model", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "detected_items_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "nutrition_estimate_snapshot",
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
            "owner_subject <> ''",
            name=op.f("ck_food_image_analysis_runs_owner_subject_nonempty"),
        ),
        sa.CheckConstraint(
            "length(image_sha256) = 64",
            name=op.f("ck_food_image_analysis_runs_image_sha256_length"),
        ),
        sa.CheckConstraint(
            "image_mime_type IN ('image/jpeg', 'image/png', 'image/webp')",
            name=op.f("ck_food_image_analysis_runs_image_mime_type_allowed"),
        ),
        sa.CheckConstraint(
            "image_size_bytes > 0",
            name=op.f("ck_food_image_analysis_runs_image_size_positive"),
        ),
        sa.CheckConstraint(
            "status IN ('requires_confirmation', 'confirmed', 'failed')",
            name=op.f("ck_food_image_analysis_runs_food_image_status_allowed"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(detected_items_snapshot) = 'object'",
            name=op.f("ck_food_image_analysis_runs_detected_items_snapshot_object"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(nutrition_estimate_snapshot) = 'object'",
            name=op.f("ck_food_image_analysis_runs_nutrition_estimate_snapshot_object"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(warning_codes) = 'array'",
            name=op.f("ck_food_image_analysis_runs_warning_codes_array"),
        ),
        sa.ForeignKeyConstraint(
            ["media_object_id"],
            ["media_objects.id"],
            name=op.f("fk_food_image_analysis_runs_media_object_id_media_objects"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["meal_id"],
            ["meal_records.id"],
            name=op.f("fk_food_image_analysis_runs_meal_id_meal_records"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_food_image_analysis_runs")),
    )
    op.create_index(
        "ix_food_image_analysis_runs_owner_created_at",
        "food_image_analysis_runs",
        ["owner_subject", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_food_image_analysis_runs_owner_status_created_at",
        "food_image_analysis_runs",
        ["owner_subject", "status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_food_image_analysis_runs_media_object_id",
        "food_image_analysis_runs",
        ["media_object_id"],
        unique=False,
    )
    op.create_index(
        "ix_food_image_analysis_runs_meal_id",
        "food_image_analysis_runs",
        ["meal_id"],
        unique=False,
    )

    for table_name in FOOD_MEAL_TABLES:
        op.execute(f"ALTER TABLE public.{table_name} ENABLE ROW LEVEL SECURITY")
        op.execute(f"""
            COMMENT ON TABLE public.{table_name} IS
            'Food and meal table. Direct backend PostgreSQL access only in this phase; Supabase Data API grants are intentionally revoked and RLS is fail-closed.';
            """)

    op.execute("""
        REVOKE ALL PRIVILEGES ON TABLE
            public.meal_records,
            public.meal_food_items,
            public.food_image_analysis_runs
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
                        'REVOKE ALL PRIVILEGES ON TABLE public.meal_records, public.meal_food_items, public.food_image_analysis_runs FROM %I',
                        role_name
                    );
                END IF;
            END LOOP;
        END
        $$;
        """)


def downgrade() -> None:
    """Drop food and meal preview tables."""
    op.drop_table("food_image_analysis_runs")
    op.drop_table("meal_food_items")
    op.drop_table("meal_records")
