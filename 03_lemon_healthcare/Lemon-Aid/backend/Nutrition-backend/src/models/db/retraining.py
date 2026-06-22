"""Learning dataset, annotation, and model registry ORM models."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base
from src.models.db.mixins import TimestampMixin


class LearningDatasetVersion(TimestampMixin, Base):
    """Persist one privacy-reviewed learning dataset version.

    Attributes:
        id: Stable dataset version identifier.
        dataset_key: Learning dataset family key.
        version: Dataset semantic or date-based version string.
        status: Dataset lifecycle status.
        source_window_start: Earliest source candidate timestamp.
        source_window_end: Latest source candidate timestamp.
        manifest_hash: SHA-256 hash of the exported sanitized manifest.
        train_count: Number of training split items.
        val_count: Number of validation split items.
        test_count: Number of test split items.
        privacy_review_status: Privacy review lifecycle status.
        created_by_hash: HMAC of the operator subject.
        frozen_at: Dataset freeze timestamp.
        created_at: Server-side record creation timestamp.
        updated_at: Server-side record update timestamp.
    """

    __tablename__ = "learning_dataset_versions"
    __table_args__ = (
        CheckConstraint(
            (
                "dataset_key IN ('supplement_roi_detection', "
                "'supplement_ocr_detection', 'supplement_ocr_recognition', "
                "'food_detection', 'food_classification', 'image_embedding')"
            ),
            name="learning_dataset_key_allowed",
        ),
        CheckConstraint("version <> ''", name="learning_dataset_version_nonempty"),
        CheckConstraint(
            "status IN ('draft', 'frozen', 'training', 'evaluated', 'approved', 'retired')",
            name="learning_dataset_status_allowed",
        ),
        CheckConstraint(
            "source_window_end IS NULL OR source_window_start IS NULL OR "
            "source_window_end >= source_window_start",
            name="learning_dataset_source_window_order",
        ),
        CheckConstraint(
            "manifest_hash IS NULL OR length(manifest_hash) = 64",
            name="learning_dataset_manifest_hash_length",
        ),
        CheckConstraint("train_count >= 0", name="learning_dataset_train_count_nonnegative"),
        CheckConstraint("val_count >= 0", name="learning_dataset_val_count_nonnegative"),
        CheckConstraint("test_count >= 0", name="learning_dataset_test_count_nonnegative"),
        CheckConstraint(
            "privacy_review_status IN ('pending', 'approved', 'rejected')",
            name="learning_dataset_privacy_review_status_allowed",
        ),
        CheckConstraint(
            "created_by_hash IS NULL OR length(created_by_hash) = 64",
            name="learning_dataset_created_by_hash_length",
        ),
        Index("ix_learning_dataset_versions_key_status", "dataset_key", "status"),
        Index(
            "ix_learning_dataset_versions_privacy_review_status",
            "privacy_review_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4)
    dataset_key: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    source_window_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    source_window_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    manifest_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    train_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    val_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    test_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    privacy_review_status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_by_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    frozen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LearningDatasetItem(TimestampMixin, Base):
    """Persist one sanitized user-consented learning dataset item.

    Attributes:
        id: Stable dataset item identifier.
        dataset_version_id: Parent dataset version identifier.
        owner_subject_hash: HMAC of the source data owner for revoke/delete-all.
        media_object_id: Optional source media object reference.
        learning_image_object_id: Optional existing supplement learning object reference.
        source_domain: Source data domain.
        task_type: Learning task type.
        label_status: Label lifecycle status.
        split: Dataset split name.
        label_snapshot: Sanitized structured label only.
        label_hash: SHA-256 hash of the sanitized label snapshot.
        quality_score: Optional bounded reviewer quality score.
        consent_snapshot: Consent type and policy-version snapshot.
        retained_until: Automatic dataset retention deadline.
        revoked_at: Timestamp set when user consent or delete-all removes the item.
        created_at: Server-side record creation timestamp.
        updated_at: Server-side record update timestamp.
    """

    __tablename__ = "learning_dataset_items"
    __table_args__ = (
        CheckConstraint("length(owner_subject_hash) = 64", name="dataset_item_owner_hash_length"),
        CheckConstraint(
            "label_status = 'revoked' OR media_object_id IS NOT NULL OR "
            "learning_image_object_id IS NOT NULL",
            name="dataset_item_source_required",
        ),
        CheckConstraint(
            "source_domain IN ('supplement', 'food')", name="dataset_item_domain_allowed"
        ),
        CheckConstraint(
            (
                "task_type IN ('yolo_detection', 'paddleocr_detection', "
                "'paddleocr_recognition', 'food_classification', 'embedding')"
            ),
            name="dataset_item_task_type_allowed",
        ),
        CheckConstraint(
            "label_status IN ('auto_labeled', 'human_reviewed', 'rejected', 'revoked')",
            name="dataset_item_label_status_allowed",
        ),
        CheckConstraint(
            "split IN ('train', 'val', 'test', 'holdout')",
            name="dataset_item_split_allowed",
        ),
        CheckConstraint(
            "jsonb_typeof(label_snapshot) = 'object'",
            name="dataset_item_label_snapshot_object",
        ),
        CheckConstraint(
            "label_hash IS NULL OR length(label_hash) = 64",
            name="dataset_item_label_hash_length",
        ),
        CheckConstraint(
            "quality_score IS NULL OR (quality_score >= 0 AND quality_score <= 1)",
            name="dataset_item_quality_score_range",
        ),
        CheckConstraint(
            "jsonb_typeof(consent_snapshot) = 'object'",
            name="dataset_item_consent_snapshot_object",
        ),
        Index("ix_learning_dataset_items_dataset_version_id", "dataset_version_id"),
        Index("ix_learning_dataset_items_owner_status", "owner_subject_hash", "label_status"),
        Index("ix_learning_dataset_items_media_object_id", "media_object_id"),
        Index("ix_learning_dataset_items_learning_image_object_id", "learning_image_object_id"),
    )

    id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4)
    dataset_version_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("learning_dataset_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    owner_subject_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    media_object_id: Mapped[UUID | None] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("media_objects.id", ondelete="SET NULL"),
        nullable=True,
    )
    learning_image_object_id: Mapped[UUID | None] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("learning_image_objects.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_domain: Mapped[str] = mapped_column(String(32), nullable=False)
    task_type: Mapped[str] = mapped_column(String(40), nullable=False)
    label_status: Mapped[str] = mapped_column(String(32), nullable=False)
    split: Mapped[str] = mapped_column(String(16), nullable=False)
    label_snapshot: Mapped[dict[str, Any]] = mapped_column(
        postgresql.JSONB,
        nullable=False,
        default=dict,
    )
    label_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    quality_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    consent_snapshot: Mapped[dict[str, Any]] = mapped_column(
        postgresql.JSONB,
        nullable=False,
        default=dict,
    )
    retained_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AnnotationTask(TimestampMixin, Base):
    """Persist one sanitized human-review annotation task.

    Attributes:
        id: Stable annotation task identifier.
        owner_subject_hash: HMAC of the source data owner for revoke/delete-all.
        media_object_id: Optional source media object identifier.
        learning_image_object_id: Optional consent-retained learning image identifier.
        task_type: Review task type.
        status: Annotation lifecycle status.
        assignee_role: Reviewer role category.
        label_snapshot: Sanitized reviewer label only.
        review_notes_code: Stable review note code instead of free text.
        reviewer_hash: HMAC of the reviewer subject.
        completed_at: Review completion timestamp.
        created_at: Server-side record creation timestamp.
        updated_at: Server-side record update timestamp.
    """

    __tablename__ = "annotation_tasks"
    __table_args__ = (
        CheckConstraint(
            "length(owner_subject_hash) = 64",
            name="annotation_task_owner_hash_length",
        ),
        CheckConstraint(
            "task_type IN ('supplement_roi_box', 'ocr_textline_label', 'food_box', 'food_class')",
            name="annotation_task_type_allowed",
        ),
        CheckConstraint(
            "status IN ('pending', 'in_review', 'accepted', 'rejected', 'cancelled')",
            name="annotation_task_status_allowed",
        ),
        CheckConstraint(
            "assignee_role IN ('operator', 'nutrition_reviewer', 'data_reviewer')",
            name="annotation_task_assignee_role_allowed",
        ),
        CheckConstraint(
            "jsonb_typeof(label_snapshot) = 'object'",
            name="annotation_task_label_snapshot_object",
        ),
        CheckConstraint(
            "reviewer_hash IS NULL OR length(reviewer_hash) = 64",
            name="annotation_task_reviewer_hash_length",
        ),
        Index("ix_annotation_tasks_owner_status", "owner_subject_hash", "status"),
        Index("ix_annotation_tasks_media_object_id", "media_object_id"),
        Index("ix_annotation_tasks_learning_image_object_id", "learning_image_object_id"),
        Index("ix_annotation_tasks_task_status", "task_type", "status"),
    )

    id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4)
    owner_subject_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    media_object_id: Mapped[UUID | None] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("media_objects.id", ondelete="SET NULL"),
        nullable=True,
    )
    learning_image_object_id: Mapped[UUID | None] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("learning_image_objects.id", ondelete="SET NULL"),
        nullable=True,
    )
    task_type: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    assignee_role: Mapped[str] = mapped_column(String(40), nullable=False)
    label_snapshot: Mapped[dict[str, Any]] = mapped_column(
        postgresql.JSONB,
        nullable=False,
        default=dict,
    )
    review_notes_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    reviewer_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ModelTrainingRun(TimestampMixin, Base):
    """Persist one model training run with sanitized config and metrics.

    Attributes:
        id: Stable training run identifier.
        model_family: Model family key.
        base_model: Sanitized base model tag.
        dataset_version_id: Training dataset version identifier.
        hyperparam_snapshot: Sanitized training configuration.
        metrics_snapshot: Verified validation metrics only.
        artifact_ref: Private model artifact reference.
        status: Training lifecycle status.
        started_at: Training start timestamp.
        ended_at: Training finish timestamp.
        created_at: Server-side record creation timestamp.
        updated_at: Server-side record update timestamp.
    """

    __tablename__ = "model_training_runs"
    __table_args__ = (
        CheckConstraint(
            (
                "model_family IN ('yolo', 'paddleocr_det', 'paddleocr_rec', "
                "'food_classifier', 'image_embedding')"
            ),
            name="model_training_family_allowed",
        ),
        CheckConstraint("base_model <> ''", name="model_training_base_model_nonempty"),
        CheckConstraint(
            "jsonb_typeof(hyperparam_snapshot) = 'object'",
            name="model_training_hyperparam_snapshot_object",
        ),
        CheckConstraint(
            "jsonb_typeof(metrics_snapshot) = 'object'",
            name="model_training_metrics_snapshot_object",
        ),
        CheckConstraint(
            "artifact_ref IS NULL OR (artifact_ref <> '' AND artifact_ref NOT LIKE '%://%' "
            "AND artifact_ref NOT LIKE '/%' AND artifact_ref NOT LIKE '%..%')",
            name="model_training_artifact_ref_private",
        ),
        CheckConstraint(
            (
                "status IN ('queued', 'running', 'succeeded', 'failed', "
                "'approved_for_deploy', 'rejected')"
            ),
            name="model_training_status_allowed",
        ),
        CheckConstraint(
            "ended_at IS NULL OR started_at IS NULL OR ended_at >= started_at",
            name="model_training_time_order",
        ),
        Index("ix_model_training_runs_dataset_version_id", "dataset_version_id"),
        Index("ix_model_training_runs_family_status", "model_family", "status"),
    )

    id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4)
    model_family: Mapped[str] = mapped_column(String(40), nullable=False)
    base_model: Mapped[str] = mapped_column(String(160), nullable=False)
    dataset_version_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("learning_dataset_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    hyperparam_snapshot: Mapped[dict[str, Any]] = mapped_column(
        postgresql.JSONB,
        nullable=False,
        default=dict,
    )
    metrics_snapshot: Mapped[dict[str, Any]] = mapped_column(
        postgresql.JSONB,
        nullable=False,
        default=dict,
    )
    artifact_ref: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ModelRegistryEntry(TimestampMixin, Base):
    """Persist one deployable model registry entry.

    Attributes:
        id: Stable model registry identifier.
        task_type: Deployable model task type.
        model_version: Deployable model version label.
        training_run_id: Source training run identifier.
        artifact_ref: Private model artifact reference.
        deployment_status: Deployment lifecycle status.
        metric_gate_snapshot: Approval criteria and result snapshot.
        rollback_model_id: Optional rollback target model identifier.
        approved_by_hash: HMAC of the approving operator.
        approved_at: Approval timestamp.
        created_at: Server-side record creation timestamp.
        updated_at: Server-side record update timestamp.
    """

    __tablename__ = "model_registry"
    __table_args__ = (
        CheckConstraint(
            (
                "task_type IN ('supplement_roi_detection', 'supplement_ocr_detection', "
                "'supplement_ocr_recognition', 'food_detection', 'food_classification', "
                "'image_embedding')"
            ),
            name="model_registry_task_type_allowed",
        ),
        CheckConstraint("model_version <> ''", name="model_registry_version_nonempty"),
        CheckConstraint(
            "artifact_ref <> '' AND artifact_ref NOT LIKE '%://%' AND "
            "artifact_ref NOT LIKE '/%' AND artifact_ref NOT LIKE '%..%'",
            name="model_registry_artifact_ref_private",
        ),
        CheckConstraint(
            "deployment_status IN ('candidate', 'staging', 'production', 'rolled_back', 'retired')",
            name="model_registry_deployment_status_allowed",
        ),
        CheckConstraint(
            "jsonb_typeof(metric_gate_snapshot) = 'object'",
            name="model_registry_metric_gate_snapshot_object",
        ),
        CheckConstraint(
            "approved_by_hash IS NULL OR length(approved_by_hash) = 64",
            name="model_registry_approved_by_hash_length",
        ),
        Index("ix_model_registry_task_status", "task_type", "deployment_status"),
        Index("ix_model_registry_training_run_id", "training_run_id"),
    )

    id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4)
    task_type: Mapped[str] = mapped_column(String(64), nullable=False)
    model_version: Mapped[str] = mapped_column(String(120), nullable=False)
    training_run_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("model_training_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    artifact_ref: Mapped[str] = mapped_column(String(1024), nullable=False)
    deployment_status: Mapped[str] = mapped_column(String(32), nullable=False)
    metric_gate_snapshot: Mapped[dict[str, Any]] = mapped_column(
        postgresql.JSONB,
        nullable=False,
        default=dict,
    )
    rollback_model_id: Mapped[UUID | None] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("model_registry.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_by_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ModelEvalResult(TimestampMixin, Base):
    """Persist one verified model evaluation metric result.

    Attributes:
        id: Stable model evaluation result identifier.
        model_id: Evaluated model registry identifier.
        eval_dataset_version_id: Evaluation dataset version identifier.
        metric_name: Metric key such as precision, recall, CER, or WER.
        metric_value: Verified numeric metric value.
        subgroup_key: Optional sanitized evaluation subgroup key.
        failure_bucket: Optional sanitized failure bucket key.
        created_at: Server-side record creation timestamp.
        updated_at: Server-side record update timestamp.
    """

    __tablename__ = "model_eval_results"
    __table_args__ = (
        CheckConstraint("metric_name <> ''", name="model_eval_metric_name_nonempty"),
        CheckConstraint(
            "metric_value >= 0",
            name="model_eval_metric_value_nonnegative",
        ),
        Index("ix_model_eval_results_model_id", "model_id"),
        Index("ix_model_eval_results_dataset_metric", "eval_dataset_version_id", "metric_name"),
    )

    id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4)
    model_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("model_registry.id", ondelete="CASCADE"),
        nullable=False,
    )
    eval_dataset_version_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("learning_dataset_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    metric_name: Mapped[str] = mapped_column(String(80), nullable=False)
    metric_value: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    subgroup_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    failure_bucket: Mapped[str | None] = mapped_column(String(120), nullable=True)
