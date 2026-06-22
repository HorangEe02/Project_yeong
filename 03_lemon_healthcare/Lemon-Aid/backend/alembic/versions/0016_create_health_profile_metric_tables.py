"""Create health profile snapshot and metric sample tables.

Revision ID: 0016_create_health_profile_metric_tables
Revises: 0015_create_food_meal_tables
Create Date: 2026-05-27 00:00:00.000000

These tables persist versioned body profile data and point-in-time health
metric samples. They contain sensitive health data, so this migration also
hardens the earlier profile/health read-model tables by enabling RLS and
revoking Supabase client-role access. Backend APIs continue to use the direct
PostgreSQL connection; Supabase Data API access is fail-closed by default.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0016_create_health_profile_metric_tables"
down_revision: str | Sequence[str] | None = "0015_create_food_meal_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SENSITIVE_HEALTH_PROFILE_TABLES = (
    "users",
    "health_sync_batches",
    "health_daily_summaries",
    "body_profile_snapshots",
    "health_metric_samples",
)


def upgrade() -> None:
    """Create health profile tables and harden Supabase Data API exposure."""
    op.create_table(
        "body_profile_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_subject", sa.String(length=512), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("sex", sa.String(length=16), nullable=True),
        sa.Column("birth_year", sa.Integer(), nullable=True),
        sa.Column("height_cm", sa.Numeric(5, 2), nullable=True),
        sa.Column("weight_kg", sa.Numeric(5, 2), nullable=True),
        sa.Column("waist_cm", sa.Numeric(5, 2), nullable=True),
        sa.Column("pregnancy_status", sa.String(length=32), nullable=True),
        sa.Column("lactation_status", sa.String(length=32), nullable=True),
        sa.Column("activity_level", sa.String(length=32), nullable=True),
        sa.Column(
            "consent_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
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
            name=op.f("ck_body_profile_snapshots_body_profile_owner_subject_nonempty"),
        ),
        sa.CheckConstraint(
            "source IN ('manual', 'healthkit', 'health_connect', 'clinician_document')",
            name=op.f("ck_body_profile_snapshots_body_profile_source_allowed"),
        ),
        sa.CheckConstraint(
            "sex IS NULL OR sex IN ('male', 'female')",
            name=op.f("ck_body_profile_snapshots_body_profile_sex_allowed"),
        ),
        sa.CheckConstraint(
            "birth_year IS NULL OR (birth_year >= 1900 AND birth_year <= 2100)",
            name=op.f("ck_body_profile_snapshots_body_profile_birth_year_range"),
        ),
        sa.CheckConstraint(
            "height_cm IS NULL OR (height_cm >= 30 AND height_cm <= 260)",
            name=op.f("ck_body_profile_snapshots_body_profile_height_cm_range"),
        ),
        sa.CheckConstraint(
            "weight_kg IS NULL OR (weight_kg >= 1 AND weight_kg <= 500)",
            name=op.f("ck_body_profile_snapshots_body_profile_weight_kg_range"),
        ),
        sa.CheckConstraint(
            "waist_cm IS NULL OR (waist_cm >= 20 AND waist_cm <= 250)",
            name=op.f("ck_body_profile_snapshots_body_profile_waist_cm_range"),
        ),
        sa.CheckConstraint(
            (
                "pregnancy_status IS NULL OR pregnancy_status IN "
                "('not_applicable', 'not_pregnant', 'pregnant', 'unknown')"
            ),
            name=op.f("ck_body_profile_snapshots_body_profile_pregnancy_status_allowed"),
        ),
        sa.CheckConstraint(
            (
                "lactation_status IS NULL OR lactation_status IN "
                "('not_applicable', 'not_lactating', 'lactating', 'unknown')"
            ),
            name=op.f("ck_body_profile_snapshots_body_profile_lactation_status_allowed"),
        ),
        sa.CheckConstraint(
            (
                "activity_level IS NULL OR activity_level IN "
                "('sedentary', 'low_active', 'active', 'very_active', 'unknown')"
            ),
            name=op.f("ck_body_profile_snapshots_body_profile_activity_level_allowed"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(consent_snapshot) = 'object'",
            name=op.f("ck_body_profile_snapshots_body_profile_consent_snapshot_object"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_body_profile_snapshots")),
    )
    op.create_index(
        "ix_body_profile_snapshots_owner_effective_at",
        "body_profile_snapshots",
        ["owner_subject", "effective_at"],
        unique=False,
    )
    op.create_index(
        "ix_body_profile_snapshots_owner_superseded_at",
        "body_profile_snapshots",
        ["owner_subject", "superseded_at"],
        unique=False,
    )

    op.create_table(
        "health_metric_samples",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_subject", sa.String(length=512), nullable=False),
        sa.Column("metric_type", sa.String(length=40), nullable=False),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("value_numeric", sa.Numeric(12, 4), nullable=False),
        sa.Column("unit", sa.String(length=16), nullable=False),
        sa.Column("source_platform", sa.String(length=32), nullable=False),
        sa.Column("source_record_hash", sa.String(length=64), nullable=True),
        sa.Column(
            "quality_flags",
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
            name=op.f("ck_health_metric_samples_health_metric_owner_subject_nonempty"),
        ),
        sa.CheckConstraint(
            (
                "metric_type IN ('steps', 'weight_kg', 'resting_hr_bpm', "
                "'active_energy_kcal', 'blood_pressure_systolic', "
                "'blood_pressure_diastolic', 'glucose_mg_dl')"
            ),
            name=op.f("ck_health_metric_samples_health_metric_type_allowed"),
        ),
        sa.CheckConstraint(
            "value_numeric >= 0",
            name=op.f("ck_health_metric_samples_health_metric_value_nonnegative"),
        ),
        sa.CheckConstraint(
            "unit IN ('count', 'kg', 'bpm', 'kcal', 'mmHg', 'mg/dL')",
            name=op.f("ck_health_metric_samples_health_metric_unit_allowed"),
        ),
        sa.CheckConstraint(
            "source_platform IN ('ios_healthkit', 'android_health_connect', 'manual', 'document')",
            name=op.f("ck_health_metric_samples_health_metric_source_platform_allowed"),
        ),
        sa.CheckConstraint(
            "source_record_hash IS NULL OR length(source_record_hash) = 64",
            name=op.f("ck_health_metric_samples_health_metric_source_record_hash_length"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(quality_flags) = 'array'",
            name=op.f("ck_health_metric_samples_health_metric_quality_flags_array"),
        ),
        sa.UniqueConstraint(
            "owner_subject",
            "source_platform",
            "source_record_hash",
            name=op.f("uq_health_metric_samples_owner_source_hash"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_health_metric_samples")),
    )
    op.create_index(
        "ix_health_metric_samples_owner_measured_at",
        "health_metric_samples",
        ["owner_subject", "measured_at"],
        unique=False,
    )
    op.create_index(
        "ix_health_metric_samples_owner_metric_measured_at",
        "health_metric_samples",
        ["owner_subject", "metric_type", "measured_at"],
        unique=False,
    )

    for table_name in SENSITIVE_HEALTH_PROFILE_TABLES:
        op.execute(f"ALTER TABLE public.{table_name} ENABLE ROW LEVEL SECURITY")
        op.execute(f"""
            COMMENT ON TABLE public.{table_name} IS
            'Sensitive health/profile table. Direct backend PostgreSQL access only in this phase; Supabase Data API grants are intentionally revoked and RLS is fail-closed.';
            """)

    op.execute("""
        REVOKE ALL PRIVILEGES ON TABLE
            public.users,
            public.health_sync_batches,
            public.health_daily_summaries,
            public.body_profile_snapshots,
            public.health_metric_samples
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
                        'REVOKE ALL PRIVILEGES ON TABLE public.users, public.health_sync_batches, public.health_daily_summaries, public.body_profile_snapshots, public.health_metric_samples FROM %I',
                        role_name
                    );
                END IF;
            END LOOP;
        END
        $$;
        """)


def downgrade() -> None:
    """Drop new profile/metric tables while keeping existing hardening in place."""
    op.drop_table("health_metric_samples")
    op.drop_table("body_profile_snapshots")
