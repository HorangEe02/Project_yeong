"""Regulated prescription and lab OCR intake ORM models."""

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


class RegulatedDocument(TimestampMixin, Base):
    """Persist an intake-only regulated document OCR preview.

    Attributes:
        id: Stable document identifier.
        owner_subject_hash: HMAC of the issuer-qualified authenticated subject.
        document_type: Regulated document type.
        status: Preview lifecycle status.
        image_sha256: SHA-256 hash of the uploaded image bytes.
        image_mime_type: Accepted image MIME type.
        image_size_bytes: Uploaded image size in bytes.
        ocr_provider: OCR provider used for preview extraction.
        ocr_confidence: OCR confidence from 0.0 to 1.0.
        ocr_text_hash: SHA-256 hash of OCR text without storing raw OCR text.
        parsed_snapshot: Structured preview or confirmation snapshot without raw OCR text.
        warning_codes: Stable warning codes produced by intake.
        consult_cta: Professional-consultation CTA displayed to the user.
        algorithm_version: Intake parser contract version.
        raw_image_deleted_at: Time when the raw image left service memory/storage.
        expires_at: Time after which the preview cannot be confirmed.
        confirmed_at: Time when the user confirmed the structured fields.
        created_at: Server-side record creation timestamp.
        updated_at: Server-side record update timestamp.
    """

    __tablename__ = "regulated_documents"
    __table_args__ = (
        CheckConstraint("length(owner_subject_hash) = 64", name="owner_subject_hash_length"),
        CheckConstraint(
            "document_type IN ('prescription', 'lab_result')",
            name="regulated_document_type_allowed",
        ),
        CheckConstraint(
            "status IN ('requires_confirmation', 'confirmed', 'expired', 'failed')",
            name="regulated_document_status_allowed",
        ),
        CheckConstraint(
            "image_mime_type IN ('image/jpeg', 'image/png', 'image/webp')",
            name="regulated_document_image_mime_type_allowed",
        ),
        CheckConstraint("image_size_bytes > 0", name="regulated_document_image_size_positive"),
        CheckConstraint(
            "ocr_confidence IS NULL OR (ocr_confidence >= 0 AND ocr_confidence <= 1)",
            name="regulated_document_ocr_confidence_range",
        ),
        CheckConstraint("length(image_sha256) = 64", name="regulated_document_image_sha_length"),
        Index("ix_regulated_documents_owner_created_at", "owner_subject_hash", "created_at"),
        Index(
            "ix_regulated_documents_owner_status_created_at",
            "owner_subject_hash",
            "status",
            "created_at",
        ),
        Index("ix_regulated_documents_expires_at", "expires_at"),
    )

    id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4)
    owner_subject_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    document_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    image_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    image_mime_type: Mapped[str] = mapped_column(String(32), nullable=False)
    image_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    ocr_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ocr_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    ocr_text_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    parsed_snapshot: Mapped[dict[str, Any]] = mapped_column(
        postgresql.JSONB, nullable=False, default=dict
    )
    warning_codes: Mapped[list[str]] = mapped_column(postgresql.JSONB, nullable=False, default=list)
    consult_cta: Mapped[dict[str, Any]] = mapped_column(
        postgresql.JSONB, nullable=False, default=dict
    )
    algorithm_version: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_image_deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PrescriptionItem(TimestampMixin, Base):
    """Persist a user-confirmed prescription intake item.

    Attributes:
        id: Stable prescription item identifier.
        document_id: Source regulated document identifier.
        medication_name_text: User-confirmed medication name text.
        dose_text: User-confirmed dose text copied from the document.
        frequency_text: User-confirmed frequency text copied from the document.
        period_text: User-confirmed period text copied from the document.
        route_text: User-confirmed route text copied from the document.
        prescribed_date_text: User-confirmed prescription or dispensing date text.
        confidence: Confidence retained from OCR or manual review.
        source: Source marker for confirmed fields.
        sort_order: Display order.
        created_at: Server-side record creation timestamp.
        updated_at: Server-side record update timestamp.
    """

    __tablename__ = "prescription_items"
    __table_args__ = (
        CheckConstraint("medication_name_text <> ''", name="prescription_medication_nonempty"),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="prescription_item_confidence_range",
        ),
        CheckConstraint("sort_order >= 0", name="prescription_item_sort_order_nonnegative"),
        Index("ix_prescription_items_document_id", "document_id"),
    )

    id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("regulated_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    medication_name_text: Mapped[str] = mapped_column(String(160), nullable=False)
    dose_text: Mapped[str | None] = mapped_column(String(80), nullable=True)
    frequency_text: Mapped[str | None] = mapped_column(String(120), nullable=True)
    period_text: Mapped[str | None] = mapped_column(String(80), nullable=True)
    route_text: Mapped[str | None] = mapped_column(String(80), nullable=True)
    prescribed_date_text: Mapped[str | None] = mapped_column(String(40), nullable=True)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False, default=1)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class LabResultItem(TimestampMixin, Base):
    """Persist a user-confirmed lab result intake item.

    Attributes:
        id: Stable lab item identifier.
        document_id: Source regulated document identifier.
        test_name_text: User-confirmed lab test name text.
        value_text: User-confirmed value text.
        unit_text: User-confirmed unit text.
        reference_range_text: User-confirmed reference range text.
        measured_at_text: User-confirmed measurement date text.
        confidence: Confidence retained from OCR or manual review.
        source: Source marker for confirmed fields.
        sort_order: Display order.
        created_at: Server-side record creation timestamp.
        updated_at: Server-side record update timestamp.
    """

    __tablename__ = "lab_result_items"
    __table_args__ = (
        CheckConstraint("test_name_text <> ''", name="lab_result_test_name_nonempty"),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="lab_result_item_confidence_range",
        ),
        CheckConstraint("sort_order >= 0", name="lab_result_item_sort_order_nonnegative"),
        Index("ix_lab_result_items_document_id", "document_id"),
    )

    id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("regulated_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    test_name_text: Mapped[str] = mapped_column(String(160), nullable=False)
    value_text: Mapped[str | None] = mapped_column(String(80), nullable=True)
    unit_text: Mapped[str | None] = mapped_column(String(40), nullable=True)
    reference_range_text: Mapped[str | None] = mapped_column(String(120), nullable=True)
    measured_at_text: Mapped[str | None] = mapped_column(String(40), nullable=True)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False, default=1)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
