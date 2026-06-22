"""Longitudinal medical record and patient status ORM models."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base
from src.models.db.mixins import TimestampMixin


class MedicalRecordCollection(TimestampMixin, Base):
    """Persist one user-confirmed medical record collection.

    Attributes:
        id: Stable medical collection identifier.
        owner_subject_hash: HMAC of the issuer-qualified authenticated subject.
        record_type: Collection type such as condition or medication.
        source: Source of the user-confirmed collection.
        source_document_id: Optional regulated OCR preview that supplied fields.
        status: Collection lifecycle status.
        consent_snapshot: Consent type and policy-version snapshot.
        deleted_at: Soft-delete timestamp.
        created_at: Server-side record creation timestamp.
        updated_at: Server-side record update timestamp.
    """

    __tablename__ = "medical_record_collections"
    __table_args__ = (
        CheckConstraint("length(owner_subject_hash) = 64", name="medical_owner_hash_length"),
        CheckConstraint(
            (
                "record_type IN ('condition', 'medication', 'allergy', 'lab_result', "
                "'prescription', 'visit_note')"
            ),
            name="medical_record_type_allowed",
        ),
        CheckConstraint(
            "source IN ('user_manual', 'regulated_ocr_confirmed', 'clinic_import', 'health_platform')",
            name="medical_record_source_allowed",
        ),
        CheckConstraint(
            "status IN ('active', 'archived', 'deleted', 'requires_review')",
            name="medical_record_status_allowed",
        ),
        CheckConstraint(
            "jsonb_typeof(consent_snapshot) = 'object'",
            name="medical_record_consent_snapshot_object",
        ),
        Index(
            "ix_medical_record_collections_owner_status_created_at",
            "owner_subject_hash",
            "status",
            "created_at",
        ),
        Index(
            "ix_medical_record_collections_owner_type_created_at",
            "owner_subject_hash",
            "record_type",
            "created_at",
        ),
        Index("ix_medical_record_collections_source_document_id", "source_document_id"),
    )

    id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4)
    owner_subject_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    record_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    source_document_id: Mapped[UUID | None] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("regulated_documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    consent_snapshot: Mapped[dict[str, Any]] = mapped_column(
        postgresql.JSONB,
        nullable=False,
        default=dict,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PatientCondition(TimestampMixin, Base):
    """Persist one user-confirmed condition record.

    Attributes:
        id: Stable condition identifier.
        medical_collection_id: Parent medical collection identifier.
        condition_text: User-entered or user-confirmed condition label.
        condition_code_system: Optional standard code system label.
        condition_code_hash: Optional one-way hash of a sensitive code.
        clinical_status: User-confirmed clinical status code.
        onset_date_text: Bounded user/document date text.
        source: Source of the condition fields.
        confirmed_at: User confirmation timestamp.
        created_at: Server-side record creation timestamp.
        updated_at: Server-side record update timestamp.
    """

    __tablename__ = "patient_conditions"
    __table_args__ = (
        CheckConstraint("condition_text <> ''", name="patient_condition_text_nonempty"),
        CheckConstraint(
            "condition_code_hash IS NULL OR length(condition_code_hash) = 64",
            name="patient_condition_code_hash_length",
        ),
        CheckConstraint(
            "clinical_status IN ('active', 'inactive', 'resolved', 'unknown')",
            name="patient_condition_status_allowed",
        ),
        CheckConstraint(
            "source IN ('user_confirmed', 'clinician_document')",
            name="patient_condition_source_allowed",
        ),
        Index("ix_patient_conditions_medical_collection_id", "medical_collection_id"),
    )

    id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4)
    medical_collection_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("medical_record_collections.id", ondelete="CASCADE"),
        nullable=False,
    )
    condition_text: Mapped[str] = mapped_column(String(180), nullable=False)
    condition_code_system: Mapped[str | None] = mapped_column(String(80), nullable=True)
    condition_code_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    clinical_status: Mapped[str] = mapped_column(String(32), nullable=False)
    onset_date_text: Mapped[str | None] = mapped_column(String(80), nullable=True)
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PatientMedication(TimestampMixin, Base):
    """Persist one user-confirmed medication record.

    Attributes:
        id: Stable medication identifier.
        medical_collection_id: Parent medical collection identifier.
        medication_name_text: User-confirmed medication name.
        dose_text: User-confirmed dose text copied from source material.
        frequency_text: User-confirmed frequency text copied from source material.
        route_text: User-confirmed route text.
        period_text: User-confirmed period text.
        active_status: Medication lifecycle status.
        source_document_id: Optional regulated OCR preview source.
        confirmed_at: User confirmation timestamp.
        created_at: Server-side record creation timestamp.
        updated_at: Server-side record update timestamp.
    """

    __tablename__ = "patient_medications"
    __table_args__ = (
        CheckConstraint("medication_name_text <> ''", name="patient_medication_name_nonempty"),
        CheckConstraint(
            "active_status IN ('active', 'stopped', 'unknown')",
            name="patient_medication_active_status_allowed",
        ),
        Index("ix_patient_medications_medical_collection_id", "medical_collection_id"),
        Index("ix_patient_medications_source_document_id", "source_document_id"),
    )

    id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4)
    medical_collection_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("medical_record_collections.id", ondelete="CASCADE"),
        nullable=False,
    )
    medication_name_text: Mapped[str] = mapped_column(String(180), nullable=False)
    dose_text: Mapped[str | None] = mapped_column(String(120), nullable=True)
    frequency_text: Mapped[str | None] = mapped_column(String(120), nullable=True)
    route_text: Mapped[str | None] = mapped_column(String(80), nullable=True)
    period_text: Mapped[str | None] = mapped_column(String(120), nullable=True)
    active_status: Mapped[str] = mapped_column(String(32), nullable=False)
    source_document_id: Mapped[UUID | None] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("regulated_documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PatientStatusSnapshot(TimestampMixin, Base):
    """Persist a non-diagnostic patient data-status snapshot.

    Attributes:
        id: Stable patient status snapshot identifier.
        owner_subject_hash: HMAC of the issuer-qualified authenticated subject.
        status_at: Snapshot reference time.
        summary_type: Type of summarized data state.
        input_window_start: Start of the summarized input window.
        input_window_end: End of the summarized input window.
        symptom_categories: Safe symptom category codes without free text.
        metric_summary: Bounded numeric health metric summary.
        medication_summary: Bounded medication count/category summary.
        risk_flags: Non-diagnostic risk or data-quality codes.
        data_quality: Snapshot data quality status.
        generated_by: Snapshot generator type.
        expires_at: Time when this snapshot should be considered stale.
        created_at: Server-side record creation timestamp.
        updated_at: Server-side record update timestamp.
    """

    __tablename__ = "patient_status_snapshots"
    __table_args__ = (
        CheckConstraint("length(owner_subject_hash) = 64", name="patient_status_owner_hash_length"),
        CheckConstraint(
            "summary_type IN ('self_report', 'device_summary', 'confirmed_record_summary', 'system_derived')",
            name="patient_status_summary_type_allowed",
        ),
        CheckConstraint(
            "input_window_end IS NULL OR input_window_start IS NULL OR input_window_end >= input_window_start",
            name="patient_status_input_window_order",
        ),
        CheckConstraint(
            "jsonb_typeof(symptom_categories) = 'array'",
            name="patient_status_symptom_categories_array",
        ),
        CheckConstraint(
            "jsonb_typeof(metric_summary) = 'object'",
            name="patient_status_metric_summary_object",
        ),
        CheckConstraint(
            "jsonb_typeof(medication_summary) = 'object'",
            name="patient_status_medication_summary_object",
        ),
        CheckConstraint(
            "jsonb_typeof(risk_flags) = 'array'",
            name="patient_status_risk_flags_array",
        ),
        CheckConstraint(
            "data_quality IN ('complete', 'partial', 'insufficient')",
            name="patient_status_data_quality_allowed",
        ),
        CheckConstraint(
            "generated_by IN ('user', 'backend_rule', 'llm_summary')",
            name="patient_status_generated_by_allowed",
        ),
        Index(
            "ix_patient_status_snapshots_owner_status_at",
            "owner_subject_hash",
            "status_at",
        ),
        Index(
            "ix_patient_status_snapshots_owner_expires_at",
            "owner_subject_hash",
            "expires_at",
        ),
        Index("ix_patient_status_snapshots_data_quality", "data_quality"),
    )

    id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4)
    owner_subject_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    summary_type: Mapped[str] = mapped_column(String(40), nullable=False)
    input_window_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    input_window_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    symptom_categories: Mapped[list[str]] = mapped_column(
        postgresql.JSONB,
        nullable=False,
        default=list,
    )
    metric_summary: Mapped[dict[str, Any]] = mapped_column(
        postgresql.JSONB,
        nullable=False,
        default=dict,
    )
    medication_summary: Mapped[dict[str, Any]] = mapped_column(
        postgresql.JSONB,
        nullable=False,
        default=dict,
    )
    risk_flags: Mapped[list[str]] = mapped_column(
        postgresql.JSONB,
        nullable=False,
        default=list,
    )
    data_quality: Mapped[str] = mapped_column(String(32), nullable=False)
    generated_by: Mapped[str] = mapped_column(String(32), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
