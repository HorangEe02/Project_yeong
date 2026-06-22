"""Regulated prescription and lab OCR intake schemas."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RegulatedDocumentType(StrEnum):
    """Supported regulated document intake types.

    Attributes:
        PRESCRIPTION: Prescription or dispensing document held by the user.
        LAB_RESULT: Clinical lab result sheet held by the user.
    """

    PRESCRIPTION = "prescription"
    LAB_RESULT = "lab_result"


class RegulatedDocumentStatus(StrEnum):
    """Lifecycle states for regulated OCR intake previews.

    Attributes:
        REQUIRES_CONFIRMATION: OCR preview must be reviewed by the user.
        CONFIRMED: User confirmed structured fields.
        EXPIRED: Preview can no longer be confirmed.
        FAILED: Intake failed before user confirmation.
    """

    REQUIRES_CONFIRMATION = "requires_confirmation"
    CONFIRMED = "confirmed"
    EXPIRED = "expired"
    FAILED = "failed"


class ConsultProfessionalCTA(BaseModel):
    """Safe call-to-action that routes regulated decisions to professionals.

    Attributes:
        type: CTA category.
        title: CTA display title.
        message: Safe non-diagnostic message.
        action: Client action identifier.
    """

    type: Literal["consult_professional"] = "consult_professional"
    title: str = Field(default="전문가 상담이 필요한 정보입니다.", max_length=120)
    message: str = Field(
        default="복용량 변경, 약 중단, 검사 결과 해석은 담당 의료진 또는 약사와 상담하세요.",
        max_length=240,
    )
    action: Literal["contact_clinician_or_pharmacist", "contact_clinician"] = (
        "contact_clinician_or_pharmacist"
    )


class PrescriptionItemPreview(BaseModel):
    """Prescription OCR item shown only as a user-confirmation preview.

    Attributes:
        medication_name_text: Medication name text supported by visible OCR text.
        dose_text: Dose text supported by visible OCR text.
        frequency_text: Frequency text supported by visible OCR text.
        period_text: Period text supported by visible OCR text.
        route_text: Route text supported by visible OCR text.
        prescribed_date_text: Prescription or dispensing date text.
        confidence: OCR/provider confidence from 0.0 to 1.0.
        source: Source marker for the preview item.
        requires_user_confirmation: Always true for OCR preview output.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    medication_name_text: str | None = Field(default=None, max_length=160)
    dose_text: str | None = Field(default=None, max_length=80)
    frequency_text: str | None = Field(default=None, max_length=120)
    period_text: str | None = Field(default=None, max_length=80)
    route_text: str | None = Field(default=None, max_length=80)
    prescribed_date_text: str | None = Field(default=None, max_length=40)
    confidence: float | None = Field(default=None, ge=0, le=1)
    source: Literal["ocr_preview", "manual_entry"] = "ocr_preview"
    requires_user_confirmation: Literal[True] = True


class LabResultItemPreview(BaseModel):
    """Lab result OCR item shown only as a user-confirmation preview.

    Attributes:
        test_name_text: Test name supported by visible OCR text.
        value_text: Measured value text supported by visible OCR text.
        unit_text: Unit text supported by visible OCR text.
        reference_range_text: Reference range text supported by visible OCR text.
        measured_at_text: Measurement date text.
        confidence: OCR/provider confidence from 0.0 to 1.0.
        source: Source marker for the preview item.
        requires_user_confirmation: Always true for OCR preview output.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    test_name_text: str | None = Field(default=None, max_length=160)
    value_text: str | None = Field(default=None, max_length=80)
    unit_text: str | None = Field(default=None, max_length=40)
    reference_range_text: str | None = Field(default=None, max_length=120)
    measured_at_text: str | None = Field(default=None, max_length=40)
    confidence: float | None = Field(default=None, ge=0, le=1)
    source: Literal["ocr_preview", "manual_entry"] = "ocr_preview"
    requires_user_confirmation: Literal[True] = True


class RegulatedOCRPreviewBase(BaseModel):
    """Common regulated OCR preview response fields.

    Attributes:
        document_id: Temporary regulated document identifier.
        document_type: Regulated document type.
        status: Preview lifecycle status.
        warnings: Safe warning messages for user review.
        warning_codes: Stable warning codes for clients and audit records.
        consult_professional_cta: Professional-consultation CTA.
        raw_image_stored: Always false for MVP memory-only image processing.
        raw_ocr_text_stored: Always false because raw OCR text is hashed only.
        expires_at: Preview expiration timestamp.
    """

    document_id: UUID
    document_type: RegulatedDocumentType
    status: RegulatedDocumentStatus
    warnings: list[str] = Field(default_factory=list)
    warning_codes: list[str] = Field(default_factory=list)
    consult_professional_cta: ConsultProfessionalCTA
    raw_image_stored: Literal[False] = False
    raw_ocr_text_stored: Literal[False] = False
    expires_at: datetime


class PrescriptionOCRPreviewResponse(RegulatedOCRPreviewBase):
    """Prescription OCR preview response requiring user confirmation.

    Attributes:
        recognized_items: Prescription fields parsed from OCR text.
    """

    document_type: Literal[RegulatedDocumentType.PRESCRIPTION] = RegulatedDocumentType.PRESCRIPTION
    recognized_items: list[PrescriptionItemPreview] = Field(default_factory=list)


class LabResultOCRPreviewResponse(RegulatedOCRPreviewBase):
    """Lab result OCR preview response requiring user confirmation.

    Attributes:
        recognized_items: Lab result fields parsed from OCR text.
    """

    document_type: Literal[RegulatedDocumentType.LAB_RESULT] = RegulatedDocumentType.LAB_RESULT
    recognized_items: list[LabResultItemPreview] = Field(default_factory=list)


class PrescriptionItemConfirm(BaseModel):
    """User-confirmed prescription intake item.

    Attributes:
        medication_name_text: User-confirmed medication name text.
        dose_text: User-confirmed dose text copied from the document.
        frequency_text: User-confirmed frequency text copied from the document.
        period_text: User-confirmed period text copied from the document.
        route_text: User-confirmed route text copied from the document.
        prescribed_date_text: User-confirmed prescription or dispensing date text.
        confidence: Confidence retained from OCR, or 1.0 for manual entry.
        source: Confirmation source marker.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    medication_name_text: str = Field(min_length=1, max_length=160)
    dose_text: str | None = Field(default=None, max_length=80)
    frequency_text: str | None = Field(default=None, max_length=120)
    period_text: str | None = Field(default=None, max_length=80)
    route_text: str | None = Field(default=None, max_length=80)
    prescribed_date_text: str | None = Field(default=None, max_length=40)
    confidence: float = Field(default=1.0, ge=0, le=1)
    source: Literal["user_confirmed", "ocr_preview"] = "user_confirmed"


class LabResultItemConfirm(BaseModel):
    """User-confirmed lab result intake item.

    Attributes:
        test_name_text: User-confirmed test name text.
        value_text: User-confirmed measured value text.
        unit_text: User-confirmed unit text.
        reference_range_text: User-confirmed reference range text.
        measured_at_text: User-confirmed measurement date text.
        confidence: Confidence retained from OCR, or 1.0 for manual entry.
        source: Confirmation source marker.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    test_name_text: str = Field(min_length=1, max_length=160)
    value_text: str | None = Field(default=None, max_length=80)
    unit_text: str | None = Field(default=None, max_length=40)
    reference_range_text: str | None = Field(default=None, max_length=120)
    measured_at_text: str | None = Field(default=None, max_length=40)
    confidence: float = Field(default=1.0, ge=0, le=1)
    source: Literal["user_confirmed", "ocr_preview"] = "user_confirmed"


class RegulatedDocumentConfirmRequest(BaseModel):
    """Confirm a regulated OCR preview after user review.

    Attributes:
        document_type: Expected document type for the preview being confirmed.
        prescription_items: User-confirmed prescription items.
        lab_result_items: User-confirmed lab result items.
        user_confirmed: Must be true to prevent silent OCR-to-final promotion.
        consult_professional_acknowledged: Must be true to record CTA acknowledgement.
    """

    model_config = ConfigDict(extra="forbid")

    document_type: RegulatedDocumentType
    prescription_items: list[PrescriptionItemConfirm] = Field(default_factory=list, max_length=80)
    lab_result_items: list[LabResultItemConfirm] = Field(default_factory=list, max_length=120)
    user_confirmed: Literal[True] = True
    consult_professional_acknowledged: Literal[True] = True


class RegulatedDocumentConfirmResponse(BaseModel):
    """Response returned after a regulated OCR preview is confirmed.

    Attributes:
        document_id: Confirmed regulated document identifier.
        document_type: Regulated document type.
        status: Confirmed lifecycle status.
        confirmed_at: Confirmation timestamp.
        consult_professional_cta: Professional-consultation CTA retained for UI display.
    """

    document_id: UUID
    document_type: RegulatedDocumentType
    status: Literal[RegulatedDocumentStatus.CONFIRMED] = RegulatedDocumentStatus.CONFIRMED
    confirmed_at: datetime
    consult_professional_cta: ConsultProfessionalCTA
