"""Create learning dataset and model registry tables.

Revision ID: 0018_create_learning_dataset_model_registry_tables
Revises: 0017_create_medical_record_status_tables
Create Date: 2026-05-27 00:00:00.000000

These tables keep model retraining lineage backend-only. They store sanitized
labels, hashes, counts, private artifact references, and verified metrics only.
They intentionally do not store raw images, raw OCR text, provider payloads,
signed URLs, public URLs, request headers, user subjects, tokens, or secrets.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0018_create_learning_dataset_model_registry_tables"
down_revision: str | Sequence[str] | None = "0017_create_medical_record_status_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RETRAINING_TABLES = (
    "learning_dataset_versions",
    "learning_dataset_items",
    "annotation_tasks",
    "model_training_runs",
    "model_registry",
    "model_eval_results",
)


def upgrade() -> None:
    """Create retraining lineage tables and revoke Supabase client-role access."""
    op.create_table(
        "learning_dataset_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dataset_key", sa.String(length=64), nullable=False),
        sa.Column("version", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("source_window_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_window_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("manifest_hash", sa.String(length=64), nullable=True),
        sa.Column("train_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("val_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("test_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("privacy_review_status", sa.String(length=32), nullable=False),
        sa.Column("created_by_hash", sa.String(length=64), nullable=True),
        sa.Column("frozen_at", sa.DateTime(timezone=True), nullable=True),
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
                "dataset_key IN ('supplement_roi_detection', "
                "'supplement_ocr_detection', 'supplement_ocr_recognition', "
                "'food_detection', 'food_classification', 'image_embedding')"
            ),
            name=op.f("ck_learning_dataset_versions_learning_dataset_key_allowed"),
        ),
        sa.CheckConstraint(
            "version <> ''",
            name=op.f("ck_learning_dataset_versions_learning_dataset_version_nonempty"),
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'frozen', 'training', 'evaluated', 'approved', 'retired')",
            name=op.f("ck_learning_dataset_versions_learning_dataset_status_allowed"),
        ),
        sa.CheckConstraint(
            (
                "source_window_end IS NULL OR source_window_start IS NULL OR "
                "source_window_end >= source_window_start"
            ),
            name=op.f("ck_learning_dataset_versions_learning_dataset_source_window_order"),
        ),
        sa.CheckConstraint(
            "manifest_hash IS NULL OR length(manifest_hash) = 64",
            name=op.f("ck_learning_dataset_versions_learning_dataset_manifest_hash_length"),
        ),
        sa.CheckConstraint(
            "train_count >= 0",
            name=op.f("ck_learning_dataset_versions_learning_dataset_train_count_nonnegative"),
        ),
        sa.CheckConstraint(
            "val_count >= 0",
            name=op.f("ck_learning_dataset_versions_learning_dataset_val_count_nonnegative"),
        ),
        sa.CheckConstraint(
            "test_count >= 0",
            name=op.f("ck_learning_dataset_versions_learning_dataset_test_count_nonnegative"),
        ),
        sa.CheckConstraint(
            "privacy_review_status IN ('pending', 'approved', 'rejected')",
            name=op.f(
                "ck_learning_dataset_versions_learning_dataset_privacy_review_status_allowed"
            ),
        ),
        sa.CheckConstraint(
            "created_by_hash IS NULL OR length(created_by_hash) = 64",
            name=op.f("ck_learning_dataset_versions_learning_dataset_created_by_hash_length"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_learning_dataset_versions")),
    )
    op.create_index(
        "ix_learning_dataset_versions_key_status",
        "learning_dataset_versions",
        ["dataset_key", "status"],
        unique=False,
    )
    op.create_index(
        "ix_learning_dataset_versions_privacy_review_status",
        "learning_dataset_versions",
        ["privacy_review_status"],
        unique=False,
    )

    op.create_table(
        "learning_dataset_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dataset_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_subject_hash", sa.String(length=64), nullable=False),
        sa.Column("media_object_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("learning_image_object_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_domain", sa.String(length=32), nullable=False),
        sa.Column("task_type", sa.String(length=40), nullable=False),
        sa.Column("label_status", sa.String(length=32), nullable=False),
        sa.Column("split", sa.String(length=16), nullable=False),
        sa.Column(
            "label_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("label_hash", sa.String(length=64), nullable=True),
        sa.Column("quality_score", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column(
            "consent_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("retained_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
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
            name=op.f("ck_learning_dataset_items_dataset_item_owner_hash_length"),
        ),
        sa.CheckConstraint(
            (
                "label_status = 'revoked' OR media_object_id IS NOT NULL OR "
                "learning_image_object_id IS NOT NULL"
            ),
            name=op.f("ck_learning_dataset_items_dataset_item_source_required"),
        ),
        sa.CheckConstraint(
            "source_domain IN ('supplement', 'food')",
            name=op.f("ck_learning_dataset_items_dataset_item_domain_allowed"),
        ),
        sa.CheckConstraint(
            (
                "task_type IN ('yolo_detection', 'paddleocr_detection', "
                "'paddleocr_recognition', 'food_classification', 'embedding')"
            ),
            name=op.f("ck_learning_dataset_items_dataset_item_task_type_allowed"),
        ),
        sa.CheckConstraint(
            "label_status IN ('auto_labeled', 'human_reviewed', 'rejected', 'revoked')",
            name=op.f("ck_learning_dataset_items_dataset_item_label_status_allowed"),
        ),
        sa.CheckConstraint(
            "split IN ('train', 'val', 'test', 'holdout')",
            name=op.f("ck_learning_dataset_items_dataset_item_split_allowed"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(label_snapshot) = 'object'",
            name=op.f("ck_learning_dataset_items_dataset_item_label_snapshot_object"),
        ),
        sa.CheckConstraint(
            "label_hash IS NULL OR length(label_hash) = 64",
            name=op.f("ck_learning_dataset_items_dataset_item_label_hash_length"),
        ),
        sa.CheckConstraint(
            "quality_score IS NULL OR (quality_score >= 0 AND quality_score <= 1)",
            name=op.f("ck_learning_dataset_items_dataset_item_quality_score_range"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(consent_snapshot) = 'object'",
            name=op.f("ck_learning_dataset_items_dataset_item_consent_snapshot_object"),
        ),
        sa.ForeignKeyConstraint(
            ["dataset_version_id"],
            ["learning_dataset_versions.id"],
            name=op.f("fk_learning_dataset_items_dataset_version_id_learning_dataset_versions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["media_object_id"],
            ["media_objects.id"],
            name=op.f("fk_learning_dataset_items_media_object_id_media_objects"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["learning_image_object_id"],
            ["learning_image_objects.id"],
            name=op.f("fk_learning_dataset_items_learning_image_object_id_learning_image_objects"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_learning_dataset_items")),
    )
    op.create_index(
        "ix_learning_dataset_items_dataset_version_id",
        "learning_dataset_items",
        ["dataset_version_id"],
        unique=False,
    )
    op.create_index(
        "ix_learning_dataset_items_owner_status",
        "learning_dataset_items",
        ["owner_subject_hash", "label_status"],
        unique=False,
    )
    op.create_index(
        "ix_learning_dataset_items_media_object_id",
        "learning_dataset_items",
        ["media_object_id"],
        unique=False,
    )
    op.create_index(
        "ix_learning_dataset_items_learning_image_object_id",
        "learning_dataset_items",
        ["learning_image_object_id"],
        unique=False,
    )

    op.create_table(
        "annotation_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_subject_hash", sa.String(length=64), nullable=False),
        sa.Column("media_object_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("task_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("assignee_role", sa.String(length=40), nullable=False),
        sa.Column(
            "label_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("review_notes_code", sa.String(length=80), nullable=True),
        sa.Column("reviewer_hash", sa.String(length=64), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
            name=op.f("ck_annotation_tasks_annotation_task_owner_hash_length"),
        ),
        sa.CheckConstraint(
            "task_type IN ('supplement_roi_box', 'ocr_textline_label', 'food_box', 'food_class')",
            name=op.f("ck_annotation_tasks_annotation_task_type_allowed"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'in_review', 'accepted', 'rejected', 'cancelled')",
            name=op.f("ck_annotation_tasks_annotation_task_status_allowed"),
        ),
        sa.CheckConstraint(
            "assignee_role IN ('operator', 'nutrition_reviewer', 'data_reviewer')",
            name=op.f("ck_annotation_tasks_annotation_task_assignee_role_allowed"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(label_snapshot) = 'object'",
            name=op.f("ck_annotation_tasks_annotation_task_label_snapshot_object"),
        ),
        sa.CheckConstraint(
            "reviewer_hash IS NULL OR length(reviewer_hash) = 64",
            name=op.f("ck_annotation_tasks_annotation_task_reviewer_hash_length"),
        ),
        sa.ForeignKeyConstraint(
            ["media_object_id"],
            ["media_objects.id"],
            name=op.f("fk_annotation_tasks_media_object_id_media_objects"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_annotation_tasks")),
    )
    op.create_index(
        "ix_annotation_tasks_owner_status",
        "annotation_tasks",
        ["owner_subject_hash", "status"],
        unique=False,
    )
    op.create_index(
        "ix_annotation_tasks_media_object_id",
        "annotation_tasks",
        ["media_object_id"],
        unique=False,
    )
    op.create_index(
        "ix_annotation_tasks_task_status",
        "annotation_tasks",
        ["task_type", "status"],
        unique=False,
    )

    op.create_table(
        "model_training_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("model_family", sa.String(length=40), nullable=False),
        sa.Column("base_model", sa.String(length=160), nullable=False),
        sa.Column("dataset_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "hyperparam_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "metrics_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("artifact_ref", sa.String(length=1024), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
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
                "model_family IN ('yolo', 'paddleocr_det', 'paddleocr_rec', "
                "'food_classifier', 'image_embedding')"
            ),
            name=op.f("ck_model_training_runs_model_training_family_allowed"),
        ),
        sa.CheckConstraint(
            "base_model <> ''",
            name=op.f("ck_model_training_runs_model_training_base_model_nonempty"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(hyperparam_snapshot) = 'object'",
            name=op.f("ck_model_training_runs_model_training_hyperparam_snapshot_object"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(metrics_snapshot) = 'object'",
            name=op.f("ck_model_training_runs_model_training_metrics_snapshot_object"),
        ),
        sa.CheckConstraint(
            (
                "artifact_ref IS NULL OR (artifact_ref <> '' AND artifact_ref NOT LIKE '%://%' "
                "AND artifact_ref NOT LIKE '/%' AND artifact_ref NOT LIKE '%..%')"
            ),
            name=op.f("ck_model_training_runs_model_training_artifact_ref_private"),
        ),
        sa.CheckConstraint(
            (
                "status IN ('queued', 'running', 'succeeded', 'failed', "
                "'approved_for_deploy', 'rejected')"
            ),
            name=op.f("ck_model_training_runs_model_training_status_allowed"),
        ),
        sa.CheckConstraint(
            "ended_at IS NULL OR started_at IS NULL OR ended_at >= started_at",
            name=op.f("ck_model_training_runs_model_training_time_order"),
        ),
        sa.ForeignKeyConstraint(
            ["dataset_version_id"],
            ["learning_dataset_versions.id"],
            name=op.f("fk_model_training_runs_dataset_version_id_learning_dataset_versions"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_model_training_runs")),
    )
    op.create_index(
        "ix_model_training_runs_dataset_version_id",
        "model_training_runs",
        ["dataset_version_id"],
        unique=False,
    )
    op.create_index(
        "ix_model_training_runs_family_status",
        "model_training_runs",
        ["model_family", "status"],
        unique=False,
    )

    op.create_table(
        "model_registry",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_type", sa.String(length=64), nullable=False),
        sa.Column("model_version", sa.String(length=120), nullable=False),
        sa.Column("training_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("artifact_ref", sa.String(length=1024), nullable=False),
        sa.Column("deployment_status", sa.String(length=32), nullable=False),
        sa.Column(
            "metric_gate_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("rollback_model_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_by_hash", sa.String(length=64), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
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
                "task_type IN ('supplement_roi_detection', 'supplement_ocr_detection', "
                "'supplement_ocr_recognition', 'food_detection', 'food_classification', "
                "'image_embedding')"
            ),
            name=op.f("ck_model_registry_model_registry_task_type_allowed"),
        ),
        sa.CheckConstraint(
            "model_version <> ''",
            name=op.f("ck_model_registry_model_registry_version_nonempty"),
        ),
        sa.CheckConstraint(
            (
                "artifact_ref <> '' AND artifact_ref NOT LIKE '%://%' AND "
                "artifact_ref NOT LIKE '/%' AND artifact_ref NOT LIKE '%..%'"
            ),
            name=op.f("ck_model_registry_model_registry_artifact_ref_private"),
        ),
        sa.CheckConstraint(
            "deployment_status IN ('candidate', 'staging', 'production', 'rolled_back', 'retired')",
            name=op.f("ck_model_registry_model_registry_deployment_status_allowed"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(metric_gate_snapshot) = 'object'",
            name=op.f("ck_model_registry_model_registry_metric_gate_snapshot_object"),
        ),
        sa.CheckConstraint(
            "approved_by_hash IS NULL OR length(approved_by_hash) = 64",
            name=op.f("ck_model_registry_model_registry_approved_by_hash_length"),
        ),
        sa.ForeignKeyConstraint(
            ["training_run_id"],
            ["model_training_runs.id"],
            name=op.f("fk_model_registry_training_run_id_model_training_runs"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["rollback_model_id"],
            ["model_registry.id"],
            name=op.f("fk_model_registry_rollback_model_id_model_registry"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_model_registry")),
    )
    op.create_index(
        "ix_model_registry_task_status",
        "model_registry",
        ["task_type", "deployment_status"],
        unique=False,
    )
    op.create_index(
        "ix_model_registry_training_run_id",
        "model_registry",
        ["training_run_id"],
        unique=False,
    )

    op.create_table(
        "model_eval_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("model_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("eval_dataset_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("metric_name", sa.String(length=80), nullable=False),
        sa.Column("metric_value", sa.Numeric(precision=8, scale=6), nullable=False),
        sa.Column("subgroup_key", sa.String(length=120), nullable=True),
        sa.Column("failure_bucket", sa.String(length=120), nullable=True),
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
            "metric_name <> ''",
            name=op.f("ck_model_eval_results_model_eval_metric_name_nonempty"),
        ),
        sa.CheckConstraint(
            "metric_value >= 0",
            name=op.f("ck_model_eval_results_model_eval_metric_value_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["model_id"],
            ["model_registry.id"],
            name=op.f("fk_model_eval_results_model_id_model_registry"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["eval_dataset_version_id"],
            ["learning_dataset_versions.id"],
            name=op.f("fk_model_eval_results_eval_dataset_version_id_learning_dataset_versions"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_model_eval_results")),
    )
    op.create_index(
        "ix_model_eval_results_model_id",
        "model_eval_results",
        ["model_id"],
        unique=False,
    )
    op.create_index(
        "ix_model_eval_results_dataset_metric",
        "model_eval_results",
        ["eval_dataset_version_id", "metric_name"],
        unique=False,
    )

    for table_name in RETRAINING_TABLES:
        op.execute(f"ALTER TABLE public.{table_name} ENABLE ROW LEVEL SECURITY")
        op.execute(f"""
            COMMENT ON TABLE public.{table_name} IS
            'Sensitive retraining lineage table. Backend-only direct PostgreSQL access; Supabase Data API grants are intentionally revoked and RLS is fail-closed.';
            """)

    op.execute("""
        REVOKE ALL PRIVILEGES ON TABLE
            public.learning_dataset_versions,
            public.learning_dataset_items,
            public.annotation_tasks,
            public.model_training_runs,
            public.model_registry,
            public.model_eval_results
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
                        'REVOKE ALL PRIVILEGES ON TABLE public.learning_dataset_versions, public.learning_dataset_items, public.annotation_tasks, public.model_training_runs, public.model_registry, public.model_eval_results FROM %I',
                        role_name
                    );
                END IF;
            END LOOP;
        END
        $$;
        """)


def downgrade() -> None:
    """Drop retraining lineage tables."""
    op.drop_table("model_eval_results")
    op.drop_table("model_registry")
    op.drop_table("model_training_runs")
    op.drop_table("annotation_tasks")
    op.drop_table("learning_dataset_items")
    op.drop_table("learning_dataset_versions")
