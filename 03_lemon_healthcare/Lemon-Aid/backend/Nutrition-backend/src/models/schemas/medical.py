"""User-confirmed medical record and patient status API schemas."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MAX_PATIENT_STATUS_CODE_LENGTH = 64


class MedicalRecordType(StrEnum):
    """Supported user-confirmed medical record collection types."""

    CONDITION = "condition"
    MEDICATION = "medication"
    ALLERGY = "allergy"
    LAB_RESULT = "lab_result"
    PRESCRIPTION = "prescription"
    VISIT_NOTE = "visit_note"


class MedicalRecordSource(StrEnum):
    """Supported sources for user-confirmed medical records."""

    USER_MANUAL = "user_manual"
    REGULATED_OCR_CONFIRMED = "regulated_ocr_confirmed"
    CLINIC_IMPORT = "clinic_import"
    HEALTH_PLATFORM = "health_platform"


class MedicalRecordStatus(StrEnum):
    """Supported medical record lifecycle states."""

    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"
    REQUIRES_REVIEW = "requires_review"


class ClinicalStatus(StrEnum):
    """Supported user-confirmed condition status codes."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    RESOLVED = "resolved"
    UNKNOWN = "unknown"


class MedicationActiveStatus(StrEnum):
    """Supported user-confirmed medication lifecycle states."""

    ACTIVE = "active"
    STOPPED = "stopped"
    UNKNOWN = "unknown"


class PatientConditionInput(BaseModel):
    """User-entered or user-confirmed condition field payload.

    Attributes:
        condition_text: User-entered or user-confirmed condition label.
        condition_code_system: Optional standard code system label.
        condition_code_hash: Optional one-way code hash.
        clinical_status: User-confirmed clinical status code.
        onset_date_text: Bounded date text copied from the user/document.
        source: Field source marker.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    condition_text: str = Field(min_length=1, max_length=180)
    condition_code_system: str | None = Field(default=None, max_length=80)
    condition_code_hash: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
        pattern=r"^[a-fA-F0-9]{64}$",
    )
    clinical_status: ClinicalStatus = ClinicalStatus.UNKNOWN
    onset_date_text: str | None = Field(default=None, max_length=80)
    source: Literal["user_confirmed", "clinician_document"] = "user_confirmed"


class PatientMedicationInput(BaseModel):
    """User-entered or user-confirmed medication field payload.

    Attributes:
        medication_name_text: User-confirmed medication name.
        dose_text: User-confirmed dose text copied from source material.
        frequency_text: User-confirmed frequency text copied from source material.
        route_text: User-confirmed route text.
        period_text: User-confirmed period text.
        active_status: Medication lifecycle status.
        source_document_id: Optional regulated OCR source document.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    medication_name_text: str = Field(min_length=1, max_length=180)
    dose_text: str | None = Field(default=None, max_length=120)
    frequency_text: str | None = Field(default=None, max_length=120)
    route_text: str | None = Field(default=None, max_length=80)
    period_text: str | None = Field(default=None, max_length=120)
    active_status: MedicationActiveStatus = MedicationActiveStatus.UNKNOWN
    source_document_id: UUID | None = None


class MedicalRecordCreateRequest(BaseModel):
    """Request body for creating a user-confirmed medical record collection.

    Attributes:
        record_type: Medical record collection type.
        source: Source of the user-confirmed record.
        source_document_id: Optional regulated OCR preview source.
        condition: Condition payload for condition records.
        medication: Medication payload for medication/prescription records.
        user_confirmed: Whether the user has already confirmed the structured fields.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    record_type: MedicalRecordType
    source: MedicalRecordSource = MedicalRecordSource.USER_MANUAL
    source_document_id: UUID | None = None
    condition: PatientConditionInput | None = None
    medication: PatientMedicationInput | None = None
    user_confirmed: bool = False

    @model_validator(mode="after")
    def validate_record_payload(self) -> MedicalRecordCreateRequest:
        """Validate record-type and payload compatibility.

        Returns:
            Validated create request.

        Raises:
            ValueError: If the selected record type has no compatible structured payload.
        """
        if self.record_type == MedicalRecordType.CONDITION and self.condition is None:
            raise ValueError("condition records require a condition payload.")
        if (
            self.record_type
            in {
                MedicalRecordType.MEDICATION,
                MedicalRecordType.PRESCRIPTION,
            }
            and self.medication is None
        ):
            raise ValueError("medication or prescription records require a medication payload.")
        if (
            self.record_type
            not in {
                MedicalRecordType.CONDITION,
                MedicalRecordType.MEDICATION,
                MedicalRecordType.PRESCRIPTION,
            }
            and self.condition is None
            and self.medication is None
        ):
            raise ValueError("at least one structured medical payload is required.")
        return self


class MedicalRecordConfirmRequest(BaseModel):
    """Request body for confirming an existing medical record collection.

    Attributes:
        user_confirmed: Must be true to prevent silent OCR-to-record promotion.
        status: Lifecycle status to apply after confirmation.
    """

    model_config = ConfigDict(extra="forbid")

    user_confirmed: Literal[True] = True
    status: Literal[MedicalRecordStatus.ACTIVE, MedicalRecordStatus.ARCHIVED] = (
        MedicalRecordStatus.ACTIVE
    )


class PatientConditionResponse(BaseModel):
    """Response for a user-confirmed condition record."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    condition_text: str
    condition_code_system: str | None = None
    clinical_status: ClinicalStatus
    onset_date_text: str | None = None
    source: Literal["user_confirmed", "clinician_document"]
    confirmed_at: datetime | None = None


class PatientMedicationResponse(BaseModel):
    """Response for a user-confirmed medication record."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    medication_name_text: str
    dose_text: str | None = None
    frequency_text: str | None = None
    route_text: str | None = None
    period_text: str | None = None
    active_status: MedicationActiveStatus
    confirmed_at: datetime | None = None


class MedicalRecordResponse(BaseModel):
    """Response for a user-confirmed medical record collection.

    Attributes:
        id: Medical collection identifier.
        record_type: Collection type.
        source: Source of the structured fields.
        status: Collection lifecycle state.
        conditions: Condition rows.
        medications: Medication rows.
        created_at: Server-side creation timestamp.
        updated_at: Server-side update timestamp.
    """

    id: UUID
    record_type: MedicalRecordType
    source: MedicalRecordSource
    status: MedicalRecordStatus
    conditions: list[PatientConditionResponse] = Field(default_factory=list)
    medications: list[PatientMedicationResponse] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class MedicalRecordListResponse(BaseModel):
    """Response for current-user medical record collections."""

    records: list[MedicalRecordResponse]


class PatientSummaryType(StrEnum):
    """Supported patient status summary types."""

    SELF_REPORT = "self_report"
    DEVICE_SUMMARY = "device_summary"
    CONFIRMED_RECORD_SUMMARY = "confirmed_record_summary"
    SYSTEM_DERIVED = "system_derived"


class PatientDataQuality(StrEnum):
    """Supported patient status data quality codes."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    INSUFFICIENT = "insufficient"


class PatientStatusGeneratedBy(StrEnum):
    """Supported patient status generator types."""

    USER = "user"
    BACKEND_RULE = "backend_rule"
    LLM_SUMMARY = "llm_summary"


class PatientStatusSnapshotCreate(BaseModel):
    """Request body for creating a non-diagnostic patient status snapshot.

    Attributes:
        status_at: Snapshot reference time.
        summary_type: Summary type.
        input_window_start: Start of the summarized input window.
        input_window_end: End of the summarized input window.
        symptom_categories: Stable symptom category codes without free text.
        metric_summary: Bounded numeric summary object.
        medication_summary: Bounded medication count/category summary.
        risk_flags: Non-diagnostic risk or data quality flags.
        data_quality: Snapshot data quality status.
        generated_by: Snapshot generator.
        expires_at: Staleness timestamp.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    status_at: datetime | None = None
    summary_type: PatientSummaryType = PatientSummaryType.SYSTEM_DERIVED
    input_window_start: datetime | None = None
    input_window_end: datetime | None = None
    symptom_categories: list[str] = Field(default_factory=list, max_length=30)
    metric_summary: dict[str, int | float | str | None] = Field(default_factory=dict)
    medication_summary: dict[str, int | float | str | None] = Field(default_factory=dict)
    risk_flags: list[str] = Field(default_factory=list, max_length=30)
    data_quality: PatientDataQuality = PatientDataQuality.INSUFFICIENT
    generated_by: PatientStatusGeneratedBy = PatientStatusGeneratedBy.BACKEND_RULE
    expires_at: datetime | None = None

    @field_validator("symptom_categories", "risk_flags")
    @classmethod
    def validate_code_list(cls, value: list[str]) -> list[str]:
        """Validate status code lists contain stable codes only.

        Args:
            value: Code list.

        Returns:
            Validated code list.

        Raises:
            ValueError: If any value is not a bounded code.
        """
        for code in value:
            if (
                not code
                or len(code) > MAX_PATIENT_STATUS_CODE_LENGTH
                or not code.replace("_", "").replace("-", "").isalnum()
            ):
                raise ValueError("patient status lists must contain stable bounded codes.")
        return value

    @model_validator(mode="after")
    def validate_status_snapshot(self) -> PatientStatusSnapshotCreate:
        """Validate timestamp order and non-diagnostic summary keys.

        Returns:
            Validated snapshot create request.

        Raises:
            ValueError: If timestamp order is invalid or a prohibited key is present.
        """
        now = datetime.now(UTC)
        status_at = self.status_at or now
        expires_at = self.expires_at or status_at + timedelta(hours=24)
        if status_at > now + timedelta(days=1):
            raise ValueError("status_at cannot be more than one day in the future.")
        if (
            self.input_window_start
            and self.input_window_end
            and self.input_window_end < self.input_window_start
        ):
            raise ValueError("input_window_end must be on or after input_window_start.")
        if expires_at <= status_at:
            raise ValueError("expires_at must be after status_at.")
        prohibited_keys = {
            "diagnosis",
            "diagnosis_text",
            "treatment",
            "treatment_instruction",
            "prescription_instruction",
            "raw_text",
            "raw_ocr_text",
            "provider_payload",
        }
        for snapshot in (self.metric_summary, self.medication_summary):
            if prohibited_keys.intersection(snapshot):
                raise ValueError("patient status summaries cannot contain diagnostic/raw keys.")
        return self


class PatientStatusSnapshotResponse(BaseModel):
    """Response for a non-diagnostic patient status snapshot."""

    id: UUID | None = None
    status: Literal["ready", "not_ready"] = "ready"
    status_at: datetime
    summary_type: PatientSummaryType
    input_window_start: datetime | None = None
    input_window_end: datetime | None = None
    symptom_categories: list[str] = Field(default_factory=list)
    metric_summary: dict[str, object] = Field(default_factory=dict)
    medication_summary: dict[str, object] = Field(default_factory=dict)
    risk_flags: list[str] = Field(default_factory=list)
    data_quality: PatientDataQuality
    generated_by: PatientStatusGeneratedBy
    expires_at: datetime
