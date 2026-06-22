"""Create medical record and patient status tables.

Revision ID: 0017_create_medical_record_status_tables
Revises: 0016_create_health_profile_metric_tables
Create Date: 2026-05-27 00:00:00.000000

These tables separate regulated OCR intake previews from longitudinal,
user-confirmed medical records. They intentionally do not store raw document
images, raw OCR text, provider payloads, diagnosis output, treatment
instructions, request headers, or secrets. Existing regulated OCR tables are
also hardened for Supabase Data API exposure.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0017_create_medical_record_status_tables"
down_revision: str | Sequence[str] | None = "0016_create_health_profile_metric_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SENSITIVE_MEDICAL_TABLES = (
    "regulated_documents",
    "prescription_items",
    "lab_result_items",
    "medical_record_collections",
    "patient_conditions",
    "patient_medications",
    "patient_status_snapshots",
)


def upgrade() -> None:
    """Create medical tables and harden Supabase client-role exposure."""
    op.create_table(
        "medical_record_collections",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_subject_hash", sa.String(length=64), nullable=False),
        sa.Column("record_type", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True), nullable=True),
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
            name=op.f("ck_medical_record_collections_medical_owner_hash_length"),
        ),
        sa.CheckConstraint(
            (
                "record_type IN ('condition', 'medication', 'allergy', "
                "'lab_result', 'prescription', 'visit_note')"
            ),
            name=op.f("ck_medical_record_collections_medical_record_type_allowed"),
        ),
        sa.CheckConstraint(
            (
                "source IN ('user_manual', 'regulated_ocr_confirmed', "
                "'clinic_import', 'health_platform')"
            ),
            name=op.f("ck_medical_record_collections_medical_record_source_allowed"),
        ),
        sa.CheckConstraint(
            "status IN ('active', 'archived', 'deleted', 'requires_review')",
            name=op.f("ck_medical_record_collections_medical_record_status_allowed"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(consent_snapshot) = 'object'",
            name=op.f("ck_medical_record_collections_medical_record_consent_snapshot_object"),
        ),
        sa.ForeignKeyConstraint(
            ["source_document_id"],
            ["regulated_documents.id"],
            name=op.f("fk_medical_record_collections_source_document_id_regulated_documents"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_medical_record_collections")),
    )
    op.create_index(
        "ix_medical_record_collections_owner_status_created_at",
        "medical_record_collections",
        ["owner_subject_hash", "status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_medical_record_collections_owner_type_created_at",
        "medical_record_collections",
        ["owner_subject_hash", "record_type", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_medical_record_collections_source_document_id",
        "medical_record_collections",
        ["source_document_id"],
        unique=False,
    )

    op.create_table(
        "patient_conditions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("medical_collection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("condition_text", sa.String(length=180), nullable=False),
        sa.Column("condition_code_system", sa.String(length=80), nullable=True),
        sa.Column("condition_code_hash", sa.String(length=64), nullable=True),
        sa.Column("clinical_status", sa.String(length=32), nullable=False),
        sa.Column("onset_date_text", sa.String(length=80), nullable=True),
        sa.Column("source", sa.String(length=40), nullable=False),
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
            "condition_text <> ''",
            name=op.f("ck_patient_conditions_patient_condition_text_nonempty"),
        ),
        sa.CheckConstraint(
            "condition_code_hash IS NULL OR length(condition_code_hash) = 64",
            name=op.f("ck_patient_conditions_patient_condition_code_hash_length"),
        ),
        sa.CheckConstraint(
            "clinical_status IN ('active', 'inactive', 'resolved', 'unknown')",
            name=op.f("ck_patient_conditions_patient_condition_status_allowed"),
        ),
        sa.CheckConstraint(
            "source IN ('user_confirmed', 'clinician_document')",
            name=op.f("ck_patient_conditions_patient_condition_source_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["medical_collection_id"],
            ["medical_record_collections.id"],
            name=op.f("fk_patient_conditions_medical_collection_id_medical_record_collections"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_patient_conditions")),
    )
    op.create_index(
        "ix_patient_conditions_medical_collection_id",
        "patient_conditions",
        ["medical_collection_id"],
        unique=False,
    )

    op.create_table(
        "patient_medications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("medical_collection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("medication_name_text", sa.String(length=180), nullable=False),
        sa.Column("dose_text", sa.String(length=120), nullable=True),
        sa.Column("frequency_text", sa.String(length=120), nullable=True),
        sa.Column("route_text", sa.String(length=80), nullable=True),
        sa.Column("period_text", sa.String(length=120), nullable=True),
        sa.Column("active_status", sa.String(length=32), nullable=False),
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True), nullable=True),
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
            "medication_name_text <> ''",
            name=op.f("ck_patient_medications_patient_medication_name_nonempty"),
        ),
        sa.CheckConstraint(
            "active_status IN ('active', 'stopped', 'unknown')",
            name=op.f("ck_patient_medications_patient_medication_active_status_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["medical_collection_id"],
            ["medical_record_collections.id"],
            name=op.f("fk_patient_medications_medical_collection_id_medical_record_collections"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_document_id"],
            ["regulated_documents.id"],
            name=op.f("fk_patient_medications_source_document_id_regulated_documents"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_patient_medications")),
    )
    op.create_index(
        "ix_patient_medications_medical_collection_id",
        "patient_medications",
        ["medical_collection_id"],
        unique=False,
    )
    op.create_index(
        "ix_patient_medications_source_document_id",
        "patient_medications",
        ["source_document_id"],
        unique=False,
    )

    op.create_table(
        "patient_status_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_subject_hash", sa.String(length=64), nullable=False),
        sa.Column("status_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("summary_type", sa.String(length=40), nullable=False),
        sa.Column("input_window_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("input_window_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "symptom_categories",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "metric_summary",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "medication_summary",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "risk_flags",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("data_quality", sa.String(length=32), nullable=False),
        sa.Column("generated_by", sa.String(length=32), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
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
            name=op.f("ck_patient_status_snapshots_patient_status_owner_hash_length"),
        ),
        sa.CheckConstraint(
            (
                "summary_type IN ('self_report', 'device_summary', "
                "'confirmed_record_summary', 'system_derived')"
            ),
            name=op.f("ck_patient_status_snapshots_patient_status_summary_type_allowed"),
        ),
        sa.CheckConstraint(
            (
                "input_window_end IS NULL OR input_window_start IS NULL OR "
                "input_window_end >= input_window_start"
            ),
            name=op.f("ck_patient_status_snapshots_patient_status_input_window_order"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(symptom_categories) = 'array'",
            name=op.f("ck_patient_status_snapshots_patient_status_symptom_categories_array"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(metric_summary) = 'object'",
            name=op.f("ck_patient_status_snapshots_patient_status_metric_summary_object"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(medication_summary) = 'object'",
            name=op.f("ck_patient_status_snapshots_patient_status_medication_summary_object"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(risk_flags) = 'array'",
            name=op.f("ck_patient_status_snapshots_patient_status_risk_flags_array"),
        ),
        sa.CheckConstraint(
            "data_quality IN ('complete', 'partial', 'insufficient')",
            name=op.f("ck_patient_status_snapshots_patient_status_data_quality_allowed"),
        ),
        sa.CheckConstraint(
            "generated_by IN ('user', 'backend_rule', 'llm_summary')",
            name=op.f("ck_patient_status_snapshots_patient_status_generated_by_allowed"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_patient_status_snapshots")),
    )
    op.create_index(
        "ix_patient_status_snapshots_owner_status_at",
        "patient_status_snapshots",
        ["owner_subject_hash", "status_at"],
        unique=False,
    )
    op.create_index(
        "ix_patient_status_snapshots_owner_expires_at",
        "patient_status_snapshots",
        ["owner_subject_hash", "expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_patient_status_snapshots_data_quality",
        "patient_status_snapshots",
        ["data_quality"],
        unique=False,
    )

    for table_name in SENSITIVE_MEDICAL_TABLES:
        op.execute(f"ALTER TABLE public.{table_name} ENABLE ROW LEVEL SECURITY")
        op.execute(f"""
            COMMENT ON TABLE public.{table_name} IS
            'Sensitive medical record table. Direct backend PostgreSQL access only in this phase; Supabase Data API grants are intentionally revoked and RLS is fail-closed.';
            """)

    op.execute("""
        REVOKE ALL PRIVILEGES ON TABLE
            public.regulated_documents,
            public.prescription_items,
            public.lab_result_items,
            public.medical_record_collections,
            public.patient_conditions,
            public.patient_medications,
            public.patient_status_snapshots
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
                        'REVOKE ALL PRIVILEGES ON TABLE public.regulated_documents, public.prescription_items, public.lab_result_items, public.medical_record_collections, public.patient_conditions, public.patient_medications, public.patient_status_snapshots FROM %I',
                        role_name
                    );
                END IF;
            END LOOP;
        END
        $$;
        """)


def downgrade() -> None:
    """Drop new medical record tables while keeping existing hardening in place."""
    op.drop_table("patient_status_snapshots")
    op.drop_table("patient_medications")
    op.drop_table("patient_conditions")
    op.drop_table("medical_record_collections")
