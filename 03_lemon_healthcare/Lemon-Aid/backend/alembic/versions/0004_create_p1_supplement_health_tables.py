"""Create P1 supplement and health tables.

Revision ID: 0004_create_p1_supplement_health
Revises: 0003_privacy_consent_audit
Create Date: 2026-05-12 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_create_p1_supplement_health"
down_revision: str | Sequence[str] | None = "0003_privacy_consent_audit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply this migration."""
    op.create_table(
        "supplement_products",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_provider", sa.String(length=64), nullable=False),
        sa.Column("source_product_id", sa.String(length=128), nullable=False),
        sa.Column("product_name", sa.String(length=240), nullable=False),
        sa.Column("normalized_product_name", sa.String(length=240), nullable=False),
        sa.Column("manufacturer", sa.String(length=180), nullable=True),
        sa.Column("category", sa.String(length=120), nullable=True),
        sa.Column(
            "source_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("source_manifest_version", sa.String(length=32), nullable=True),
        sa.Column(
            "imported_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False),
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
            "source_provider <> ''",
            name=op.f("ck_supplement_products_source_provider_nonempty"),
        ),
        sa.CheckConstraint(
            "source_product_id <> ''",
            name=op.f("ck_supplement_products_source_product_id_nonempty"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_supplement_products")),
        sa.UniqueConstraint(
            "source_provider",
            "source_product_id",
            name="uq_supplement_products_source_provider_product_id",
        ),
    )
    op.create_index(
        "ix_supplement_products_normalized_name",
        "supplement_products",
        ["normalized_product_name"],
        unique=False,
    )
    op.create_index(
        "ix_supplement_products_manufacturer",
        "supplement_products",
        ["manufacturer"],
        unique=False,
    )

    op.create_table(
        "supplement_product_ingredients",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("standard_name", sa.String(length=160), nullable=False),
        sa.Column("nutrient_code", sa.String(length=80), nullable=True),
        sa.Column("amount", sa.Numeric(precision=14, scale=6), nullable=True),
        sa.Column("unit", sa.String(length=40), nullable=True),
        sa.Column(
            "source_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("sort_order", sa.Integer(), nullable=False),
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
            "amount IS NULL OR amount >= 0",
            name=op.f("ck_supplement_product_ingredients_amount_nonnegative"),
        ),
        sa.CheckConstraint(
            "sort_order >= 0",
            name=op.f("ck_supplement_product_ingredients_sort_order_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["supplement_products.id"],
            name=op.f("fk_supplement_product_ingredients_product_id_supplement_products"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_supplement_product_ingredients")),
    )
    op.create_index(
        "ix_supplement_product_ingredients_product_id",
        "supplement_product_ingredients",
        ["product_id"],
        unique=False,
    )
    op.create_index(
        "ix_supplement_product_ingredients_nutrient_code",
        "supplement_product_ingredients",
        ["nutrient_code"],
        unique=False,
    )

    op.create_table(
        "supplement_analysis_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_subject", sa.String(length=512), nullable=False),
        sa.Column("client_request_id", sa.String(length=80), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("image_sha256", sa.String(length=64), nullable=False),
        sa.Column("image_mime_type", sa.String(length=32), nullable=False),
        sa.Column("image_size_bytes", sa.Integer(), nullable=False),
        sa.Column("ocr_provider", sa.String(length=64), nullable=True),
        sa.Column("ocr_confidence", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("ocr_text_hash", sa.String(length=64), nullable=True),
        sa.Column(
            "parsed_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "match_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "warnings",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("algorithm_version", sa.String(length=64), nullable=False),
        sa.Column("source_manifest_version", sa.String(length=32), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
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
            "status IN ('requires_confirmation', 'confirmed', 'expired', 'failed')",
            name=op.f("ck_supplement_analysis_runs_status_allowed"),
        ),
        sa.CheckConstraint(
            "image_mime_type IN ('image/jpeg', 'image/png', 'image/webp')",
            name=op.f("ck_supplement_analysis_runs_image_mime_type_allowed"),
        ),
        sa.CheckConstraint(
            "image_size_bytes > 0",
            name=op.f("ck_supplement_analysis_runs_image_size_positive"),
        ),
        sa.CheckConstraint(
            "ocr_confidence IS NULL OR (ocr_confidence >= 0 AND ocr_confidence <= 1)",
            name=op.f("ck_supplement_analysis_runs_ocr_confidence_range"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_supplement_analysis_runs")),
        sa.UniqueConstraint(
            "owner_subject",
            "client_request_id",
            name="uq_supplement_analysis_runs_owner_client_request",
        ),
    )
    op.create_index(
        "ix_supplement_analysis_runs_owner_created_at",
        "supplement_analysis_runs",
        ["owner_subject", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_supplement_analysis_runs_owner_status_created_at",
        "supplement_analysis_runs",
        ["owner_subject", "status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_supplement_analysis_runs_expires_at",
        "supplement_analysis_runs",
        ["expires_at"],
        unique=False,
    )

    op.create_table(
        "user_supplements",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_subject", sa.String(length=512), nullable=False),
        sa.Column("source_analysis_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("matched_product_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("manufacturer", sa.String(length=180), nullable=True),
        sa.Column(
            "serving_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "intake_schedule",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "user_confirmed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
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
            "display_name <> ''",
            name=op.f("ck_user_supplements_display_name_nonempty"),
        ),
        sa.ForeignKeyConstraint(
            ["source_analysis_run_id"],
            ["supplement_analysis_runs.id"],
            name=op.f("fk_user_supplements_source_analysis_run_id_supplement_analysis_runs"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["matched_product_id"],
            ["supplement_products.id"],
            name=op.f("fk_user_supplements_matched_product_id_supplement_products"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_supplements")),
    )
    op.create_index(
        "ix_user_supplements_owner_created_at",
        "user_supplements",
        ["owner_subject", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_user_supplements_owner_deleted_at",
        "user_supplements",
        ["owner_subject", "deleted_at"],
        unique=False,
    )

    op.create_table(
        "user_supplement_ingredients",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_supplement_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("nutrient_code", sa.String(length=80), nullable=True),
        sa.Column("amount", sa.Numeric(precision=14, scale=6), nullable=True),
        sa.Column("unit", sa.String(length=40), nullable=True),
        sa.Column("confidence", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
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
            "amount IS NULL OR amount >= 0",
            name=op.f("ck_user_supplement_ingredients_amount_nonnegative"),
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name=op.f("ck_user_supplement_ingredients_confidence_range"),
        ),
        sa.CheckConstraint(
            "sort_order >= 0",
            name=op.f("ck_user_supplement_ingredients_sort_order_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["user_supplement_id"],
            ["user_supplements.id"],
            name=op.f("fk_user_supplement_ingredients_user_supplement_id_user_supplements"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_supplement_ingredients")),
    )
    op.create_index(
        "ix_user_supplement_ingredients_supplement_id",
        "user_supplement_ingredients",
        ["user_supplement_id"],
        unique=False,
    )
    op.create_index(
        "ix_user_supplement_ingredients_nutrient_code",
        "user_supplement_ingredients",
        ["nutrient_code"],
        unique=False,
    )

    op.create_table(
        "health_sync_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_subject", sa.String(length=512), nullable=False),
        sa.Column("client_batch_id", sa.String(length=80), nullable=True),
        sa.Column("source_platform", sa.String(length=32), nullable=False),
        sa.Column("record_count", sa.Integer(), nullable=False),
        sa.Column("accepted_count", sa.Integer(), nullable=False),
        sa.Column("rejected_count", sa.Integer(), nullable=False),
        sa.Column(
            "input_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "result_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
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
            "source_platform IN ('ios_healthkit', 'android_health_connect', 'manual', 'mixed')",
            name=op.f("ck_health_sync_batches_source_platform_allowed"),
        ),
        sa.CheckConstraint(
            "record_count >= 0",
            name=op.f("ck_health_sync_batches_record_count_nonnegative"),
        ),
        sa.CheckConstraint(
            "accepted_count >= 0",
            name=op.f("ck_health_sync_batches_accepted_count_nonnegative"),
        ),
        sa.CheckConstraint(
            "rejected_count >= 0",
            name=op.f("ck_health_sync_batches_rejected_count_nonnegative"),
        ),
        sa.CheckConstraint(
            "accepted_count + rejected_count <= record_count",
            name=op.f("ck_health_sync_batches_accepted_rejected_count_valid"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_health_sync_batches")),
        sa.UniqueConstraint(
            "owner_subject",
            "client_batch_id",
            name="uq_health_sync_batches_owner_client_batch",
        ),
    )
    op.create_index(
        "ix_health_sync_batches_owner_synced_at",
        "health_sync_batches",
        ["owner_subject", "synced_at"],
        unique=False,
    )

    op.create_table(
        "health_daily_summaries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_subject", sa.String(length=512), nullable=False),
        sa.Column("measured_date", sa.Date(), nullable=False),
        sa.Column("source_platform", sa.String(length=32), nullable=False),
        sa.Column("steps", sa.Integer(), nullable=True),
        sa.Column("weight_kg", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("resting_heart_rate_bpm", sa.Integer(), nullable=True),
        sa.Column("active_energy_kcal", sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column("source_record_hash", sa.String(length=64), nullable=True),
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
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
            "source_platform IN ('ios_healthkit', 'android_health_connect', 'manual')",
            name=op.f("ck_health_daily_summaries_source_platform_allowed"),
        ),
        sa.CheckConstraint(
            (
                "steps IS NOT NULL OR weight_kg IS NOT NULL OR "
                "resting_heart_rate_bpm IS NOT NULL OR active_energy_kcal IS NOT NULL"
            ),
            name=op.f("ck_health_daily_summaries_health_metric_present"),
        ),
        sa.CheckConstraint(
            "steps IS NULL OR (steps >= 0 AND steps <= 200000)",
            name=op.f("ck_health_daily_summaries_steps_range"),
        ),
        sa.CheckConstraint(
            "weight_kg IS NULL OR (weight_kg >= 20 AND weight_kg <= 300)",
            name=op.f("ck_health_daily_summaries_weight_kg_range"),
        ),
        sa.CheckConstraint(
            (
                "resting_heart_rate_bpm IS NULL OR "
                "(resting_heart_rate_bpm >= 20 AND resting_heart_rate_bpm <= 240)"
            ),
            name=op.f("ck_health_daily_summaries_resting_heart_rate_range"),
        ),
        sa.CheckConstraint(
            "active_energy_kcal IS NULL OR (active_energy_kcal >= 0 AND active_energy_kcal <= 20000)",
            name=op.f("ck_health_daily_summaries_active_energy_kcal_range"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_health_daily_summaries")),
        sa.UniqueConstraint(
            "owner_subject",
            "measured_date",
            "source_platform",
            name="uq_health_daily_summaries_owner_date_platform",
        ),
    )
    op.create_index(
        "ix_health_daily_summaries_owner_measured_date",
        "health_daily_summaries",
        ["owner_subject", "measured_date"],
        unique=False,
    )
    op.create_index(
        "ix_health_daily_summaries_owner_source_date",
        "health_daily_summaries",
        ["owner_subject", "source_platform", "measured_date"],
        unique=False,
    )


def downgrade() -> None:
    """Rollback this migration."""
    op.drop_index(
        "ix_health_daily_summaries_owner_source_date", table_name="health_daily_summaries"
    )
    op.drop_index(
        "ix_health_daily_summaries_owner_measured_date", table_name="health_daily_summaries"
    )
    op.drop_table("health_daily_summaries")
    op.drop_index("ix_health_sync_batches_owner_synced_at", table_name="health_sync_batches")
    op.drop_table("health_sync_batches")
    op.drop_index(
        "ix_user_supplement_ingredients_nutrient_code",
        table_name="user_supplement_ingredients",
    )
    op.drop_index(
        "ix_user_supplement_ingredients_supplement_id",
        table_name="user_supplement_ingredients",
    )
    op.drop_table("user_supplement_ingredients")
    op.drop_index("ix_user_supplements_owner_deleted_at", table_name="user_supplements")
    op.drop_index("ix_user_supplements_owner_created_at", table_name="user_supplements")
    op.drop_table("user_supplements")
    op.drop_index("ix_supplement_analysis_runs_expires_at", table_name="supplement_analysis_runs")
    op.drop_index(
        "ix_supplement_analysis_runs_owner_status_created_at",
        table_name="supplement_analysis_runs",
    )
    op.drop_index(
        "ix_supplement_analysis_runs_owner_created_at",
        table_name="supplement_analysis_runs",
    )
    op.drop_table("supplement_analysis_runs")
    op.drop_index(
        "ix_supplement_product_ingredients_nutrient_code",
        table_name="supplement_product_ingredients",
    )
    op.drop_index(
        "ix_supplement_product_ingredients_product_id",
        table_name="supplement_product_ingredients",
    )
    op.drop_table("supplement_product_ingredients")
    op.drop_index("ix_supplement_products_manufacturer", table_name="supplement_products")
    op.drop_index("ix_supplement_products_normalized_name", table_name="supplement_products")
    op.drop_table("supplement_products")
