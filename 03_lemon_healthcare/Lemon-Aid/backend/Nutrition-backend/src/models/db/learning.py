"""Consent-gated image learning and pgvector ORM models."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import UserDefinedType

from src.db.base import Base
from src.models.db.mixins import TimestampMixin


class PGVectorType(UserDefinedType[tuple[float, ...]]):
    """SQLAlchemy type wrapper for the pgvector `vector` column type.

    The wrapper avoids importing the optional `pgvector` Python package at app
    startup. Runtime adapters may still use pgvector-specific SQL only after the
    learning feature gate passes.
    """

    cache_ok = True

    def get_col_spec(self, **kw: object) -> str:
        """Return the PostgreSQL column specification.

        Args:
            **kw: SQLAlchemy compiler keyword arguments.

        Returns:
            The pgvector column type name.
        """
        _ = kw
        return "extensions.vector"


class LearningImageObject(TimestampMixin, Base):
    """Persist a safe reference to a consent-retained learning image object.

    Attributes:
        id: Stable object identifier.
        owner_subject_hash: HMAC of the issuer-qualified owner subject.
        analysis_id: Supplement preview that produced the image.
        image_sha256: SHA-256 hash of the original image bytes.
        object_uri: Object storage URI. Raw image bytes are never stored in DB.
        object_storage_provider: Storage provider name.
        object_version_id: Optional object version used by versioned stores.
        image_mime_type: Accepted MIME type.
        image_size_bytes: Uploaded image size in bytes.
        retained_until: Automatic deletion deadline.
        status: Learning object lifecycle state.
        consent_snapshot: Consent type and policy-version snapshot.
        review_metadata_snapshot: Sanitized user-confirmed metadata pending manual review.
        deleted_at: Timestamp set after storage deletion.
        created_at: Server-side record creation timestamp.
        updated_at: Server-side record update timestamp.
    """

    __tablename__ = "learning_image_objects"
    __table_args__ = (
        UniqueConstraint(
            "owner_subject_hash",
            "analysis_id",
            "image_sha256",
            name="uq_learning_image_objects_owner_analysis_hash",
        ),
        CheckConstraint("length(owner_subject_hash) = 64", name="owner_subject_hash_length"),
        CheckConstraint("length(image_sha256) = 64", name="image_sha256_length"),
        CheckConstraint("image_size_bytes > 0", name="image_size_positive"),
        CheckConstraint(
            "image_mime_type IN ('image/jpeg', 'image/png', 'image/webp')",
            name="image_mime_type_allowed",
        ),
        CheckConstraint(
            (
                "status IN ("
                "'awaiting_confirmation', 'pending_auto_filter', 'pending_manual_review', "
                "'approved_for_embedding', 'ready', 'embedded', "
                "'deleted', 'cancelled', 'failed', 'rejected_by_auto_filter', "
                "'rejected_by_review'"
                ")"
            ),
            name="learning_image_object_status_allowed",
        ),
        Index("ix_learning_image_objects_owner_status", "owner_subject_hash", "status"),
        Index("ix_learning_image_objects_analysis_id", "analysis_id"),
        Index("ix_learning_image_objects_retained_until", "retained_until"),
    )

    id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4)
    owner_subject_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    analysis_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("supplement_analysis_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    image_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    object_uri: Mapped[str] = mapped_column(String(1024), nullable=False)
    object_storage_provider: Mapped[str] = mapped_column(String(32), nullable=False)
    object_version_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    image_mime_type: Mapped[str] = mapped_column(String(32), nullable=False)
    image_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    retained_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    consent_snapshot: Mapped[dict[str, Any]] = mapped_column(
        postgresql.JSONB, nullable=False, default=dict
    )
    review_metadata_snapshot: Mapped[dict[str, Any]] = mapped_column(
        postgresql.JSONB, nullable=False, default=dict
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ImageEmbeddingJob(TimestampMixin, Base):
    """Persist one asynchronous embedding-upsert job.

    Attributes:
        id: Stable job identifier.
        image_object_id: Source retained image object.
        analysis_id: Supplement preview identifier for lookup and auditing.
        owner_subject_hash: HMAC of the owner subject.
        embedding_model: Model identifier requested for this job.
        status: Job lifecycle state.
        attempt_count: Number of processing attempts.
        next_run_at: Earliest retry time.
        locked_at: Worker lease timestamp.
        locked_by: Worker id holding the lease.
        error_code: Stable failure code.
        error_message: Safe failure summary without raw OCR text.
        metadata_snapshot: User-confirmed structured fields only.
        created_at: Server-side record creation timestamp.
        updated_at: Server-side record update timestamp.
    """

    __tablename__ = "image_embedding_jobs"
    __table_args__ = (
        UniqueConstraint(
            "image_object_id",
            "embedding_model",
            name="uq_image_embedding_jobs_object_model",
        ),
        CheckConstraint("length(owner_subject_hash) = 64", name="owner_subject_hash_length"),
        CheckConstraint("attempt_count >= 0", name="attempt_count_nonnegative"),
        CheckConstraint(
            "status IN ('pending', 'running', 'succeeded', 'failed', 'dead', 'cancelled')",
            name="image_embedding_job_status_allowed",
        ),
        Index("ix_image_embedding_jobs_status_next_run", "status", "next_run_at"),
        Index("ix_image_embedding_jobs_owner_status", "owner_subject_hash", "status"),
        Index("ix_image_embedding_jobs_analysis_id", "analysis_id"),
    )

    id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4)
    image_object_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("learning_image_objects.id", ondelete="CASCADE"),
        nullable=False,
    )
    analysis_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("supplement_analysis_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    owner_subject_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(512), nullable=True)
    metadata_snapshot: Mapped[dict[str, Any]] = mapped_column(
        postgresql.JSONB, nullable=False, default=dict
    )


class ImageEmbeddingRecord(TimestampMixin, Base):
    """Persist a consent-gated image embedding for pgvector lookup.

    Attributes:
        id: Stable embedding record identifier.
        owner_subject_hash: HMAC of the owner subject.
        analysis_id: Supplement preview identifier.
        image_object_id: Source retained image object.
        image_sha256: SHA-256 hash of the original image bytes.
        embedding_model: Model identifier.
        embedding_dimensions: Actual output vector dimensionality.
        embedding: pgvector value.
        embedding_metadata: Sanitized structured metadata.
        deleted_at: Timestamp set after deletion or consent withdrawal.
        created_at: Server-side record creation timestamp.
        updated_at: Server-side record update timestamp.
    """

    __tablename__ = "image_embedding_records"
    __table_args__ = (
        UniqueConstraint(
            "owner_subject_hash",
            "analysis_id",
            "embedding_model",
            "image_sha256",
            name="uq_image_embedding_records_owner_analysis_model_hash",
        ),
        CheckConstraint("length(owner_subject_hash) = 64", name="owner_subject_hash_length"),
        CheckConstraint("length(image_sha256) = 64", name="image_sha256_length"),
        CheckConstraint("embedding_dimensions > 0", name="embedding_dimensions_positive"),
        Index("ix_image_embedding_records_owner_created_at", "owner_subject_hash", "created_at"),
        Index("ix_image_embedding_records_analysis_id", "analysis_id"),
        Index("ix_image_embedding_records_image_object_id", "image_object_id"),
    )

    id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4)
    owner_subject_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    analysis_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("supplement_analysis_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    image_object_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("learning_image_objects.id", ondelete="CASCADE"),
        nullable=False,
    )
    image_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(120), nullable=False)
    embedding_dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[tuple[float, ...]] = mapped_column(PGVectorType(), nullable=False)
    embedding_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        postgresql.JSONB,
        nullable=False,
        default=dict,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
