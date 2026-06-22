"""Backend-only media object and processing ORM models."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base
from src.models.db.mixins import TimestampMixin


class MediaObject(TimestampMixin, Base):
    """Persist a private object-storage reference for retained user media.

    Attributes:
        id: Stable media object identifier.
        owner_subject_hash: HMAC of the issuer-qualified authenticated subject.
        domain: Media domain such as supplement_label or food_meal.
        source_run_id: Optional source analysis or intake run identifier.
        object_storage_provider: Private storage provider name.
        object_ref: Provider-internal object reference without public URL schemes.
        object_version_id: Optional object version for exact deletion.
        image_sha256: SHA-256 hash of the original image bytes.
        image_mime_type: Accepted image MIME type.
        image_size_bytes: Uploaded image size in bytes.
        width_px: Image width when available.
        height_px: Image height when available.
        exif_stripped: Whether EXIF metadata was stripped before retention.
        retained_until: Automatic deletion deadline.
        status: Media object lifecycle state.
        consent_snapshot: Consent type and policy-version snapshot.
        deleted_at: Timestamp set after object deletion.
        created_at: Server-side record creation timestamp.
        updated_at: Server-side record update timestamp.
    """

    __tablename__ = "media_objects"
    __table_args__ = (
        CheckConstraint("length(owner_subject_hash) = 64", name="owner_subject_hash_length"),
        CheckConstraint("length(image_sha256) = 64", name="image_sha256_length"),
        CheckConstraint("image_size_bytes > 0", name="image_size_positive"),
        CheckConstraint(
            "width_px IS NULL OR width_px > 0",
            name="width_px_positive",
        ),
        CheckConstraint(
            "height_px IS NULL OR height_px > 0",
            name="height_px_positive",
        ),
        CheckConstraint(
            "domain IN ('supplement_label', 'food_meal', 'regulated_document', "
            "'profile_attachment')",
            name="media_object_domain_allowed",
        ),
        CheckConstraint(
            "object_storage_provider IN ('supabase_s3', 's3', 'local')",
            name="media_object_storage_provider_allowed",
        ),
        CheckConstraint(
            "object_ref <> '' AND object_ref NOT LIKE '%://%' AND "
            "object_ref NOT LIKE '/%' AND object_ref NOT LIKE '%..%'",
            name="media_object_ref_private",
        ),
        CheckConstraint(
            "image_mime_type IN ('image/jpeg', 'image/png', 'image/webp')",
            name="media_object_image_mime_type_allowed",
        ),
        CheckConstraint(
            "status IN ('temporary', 'retained', 'pending_review', 'approved', "
            "'deleted', 'failed')",
            name="media_object_status_allowed",
        ),
        Index(
            "ix_media_objects_owner_domain_created_at", "owner_subject_hash", "domain", "created_at"
        ),
        Index("ix_media_objects_owner_status", "owner_subject_hash", "status"),
        Index("ix_media_objects_retained_until", "retained_until"),
        Index("ix_media_objects_source_run_id", "source_run_id"),
    )

    id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4)
    owner_subject_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    domain: Mapped[str] = mapped_column(String(40), nullable=False)
    source_run_id: Mapped[UUID | None] = mapped_column(
        postgresql.UUID(as_uuid=True),
        nullable=True,
    )
    object_storage_provider: Mapped[str] = mapped_column(String(32), nullable=False)
    object_ref: Mapped[str] = mapped_column(String(1024), nullable=False)
    object_version_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    image_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    image_mime_type: Mapped[str] = mapped_column(String(32), nullable=False)
    image_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    width_px: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height_px: Mapped[int | None] = mapped_column(Integer, nullable=True)
    exif_stripped: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    retained_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    consent_snapshot: Mapped[dict[str, Any]] = mapped_column(
        postgresql.JSONB,
        nullable=False,
        default=dict,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MediaProcessingRun(TimestampMixin, Base):
    """Persist sanitized processing metadata for retained private media.

    Attributes:
        id: Stable processing run identifier.
        media_object_id: Source media object identifier.
        pipeline_type: Processing pipeline category.
        provider: Sanitized provider label.
        model_version: Model or runtime version label.
        status: Processing lifecycle state.
        confidence: Optional provider confidence from 0.0 to 1.0.
        output_hash: SHA-256 hash of raw output when a hash is needed.
        sanitized_snapshot: Bounded structured output safe for DB retention.
        warning_codes: Stable warning codes without raw OCR/provider payloads.
        error_code: Stable safe failure code.
        started_at: Processing start time.
        finished_at: Processing finish time.
        created_at: Server-side record creation timestamp.
        updated_at: Server-side record update timestamp.
    """

    __tablename__ = "media_processing_runs"
    __table_args__ = (
        CheckConstraint(
            "pipeline_type IN ('supplement_ocr', 'food_detection', 'vision_roi', "
            "'regulated_ocr', 'quality_check')",
            name="media_processing_pipeline_type_allowed",
        ),
        CheckConstraint(
            "status IN ('pending', 'running', 'succeeded', 'requires_review', 'failed')",
            name="media_processing_status_allowed",
        ),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="media_processing_confidence_range",
        ),
        CheckConstraint(
            "output_hash IS NULL OR length(output_hash) = 64",
            name="media_processing_output_hash_length",
        ),
        Index("ix_media_processing_runs_media_object_id", "media_object_id"),
        Index("ix_media_processing_runs_pipeline_status", "pipeline_type", "status"),
        Index("ix_media_processing_runs_created_at", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4)
    media_object_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("media_objects.id", ondelete="CASCADE"),
        nullable=False,
    )
    pipeline_type: Mapped[str] = mapped_column(String(40), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    output_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sanitized_snapshot: Mapped[dict[str, Any]] = mapped_column(
        postgresql.JSONB,
        nullable=False,
        default=dict,
    )
    warning_codes: Mapped[list[str]] = mapped_column(postgresql.JSONB, nullable=False, default=list)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SupplementImageEvidence(TimestampMixin, Base):
    """Persist sanitized supplement image evidence linked to one preview.

    Attributes:
        id: Stable supplement image evidence identifier.
        analysis_run_id: Source supplement analysis preview identifier.
        media_object_id: Optional retained private media object identifier.
        image_role: Image role such as supplement_facts or barcode.
        quality_status: Safe image-quality outcome.
        quality_codes: Stable quality warning codes without raw OCR/image data.
        roi_snapshot: Sanitized ROI labels/boxes/confidences only.
        created_at: Server-side record creation timestamp.
        updated_at: Server-side record update timestamp.
    """

    __tablename__ = "supplement_image_evidence"
    __table_args__ = (
        CheckConstraint(
            "image_role IN ('front', 'supplement_facts', 'barcode', 'side_panel', 'other')",
            name="image_role_allowed",
        ),
        CheckConstraint(
            "quality_status IN ('usable', 'retake_recommended', 'rejected')",
            name="quality_status_allowed",
        ),
        CheckConstraint(
            "jsonb_typeof(quality_codes) = 'array'",
            name="quality_codes_array",
        ),
        CheckConstraint(
            "jsonb_typeof(roi_snapshot) = 'object'",
            name="roi_snapshot_object",
        ),
        Index("ix_supplement_image_evidence_analysis_run_id", "analysis_run_id"),
        Index("ix_supplement_image_evidence_media_object_id", "media_object_id"),
        Index("ix_supplement_image_evidence_quality_status", "quality_status"),
    )

    id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4)
    analysis_run_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("supplement_analysis_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    media_object_id: Mapped[UUID | None] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("media_objects.id", ondelete="SET NULL"),
        nullable=True,
    )
    image_role: Mapped[str] = mapped_column(String(40), nullable=False)
    quality_status: Mapped[str] = mapped_column(String(40), nullable=False)
    quality_codes: Mapped[list[str]] = mapped_column(postgresql.JSONB, nullable=False, default=list)
    roi_snapshot: Mapped[dict[str, Any]] = mapped_column(
        postgresql.JSONB,
        nullable=False,
        default=dict,
    )
