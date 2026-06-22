"""Privacy, consent, deletion, and audit API schemas."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ConsentType(StrEnum):
    """Supported user consent buckets.

    Attributes:
        SENSITIVE_HEALTH_ANALYSIS: Consent for storing and processing health analysis data.
        HEALTH_DEVICE_DATA: Consent for future wearable or device data intake.
        OCR_IMAGE_PROCESSING: Consent for future OCR image processing.
        EXTERNAL_OCR_PROCESSING: Consent for sending label images to external OCR providers.
        FOOD_IMAGE_PROCESSING: Consent for processing food images into meal previews.
        PRESCRIPTION_OCR_INTAKE: Consent for prescription document OCR intake.
        LAB_RESULT_OCR_INTAKE: Consent for lab result document OCR intake.
        DATA_RETENTION: Consent for retaining user analysis history.
        IMAGE_LEARNING_DATASET: Separate opt-in for pseudonymized image reuse in learning datasets.
        RAW_OCR_TEXT_RETENTION: Separate opt-in to temporarily retain OCR source text for review.
    """

    SENSITIVE_HEALTH_ANALYSIS = "sensitive_health_analysis"
    HEALTH_DEVICE_DATA = "health_device_data"
    OCR_IMAGE_PROCESSING = "ocr_image_processing"
    EXTERNAL_OCR_PROCESSING = "external_ocr_processing"
    FOOD_IMAGE_PROCESSING = "food_image_processing"
    PRESCRIPTION_OCR_INTAKE = "prescription_ocr_intake"
    LAB_RESULT_OCR_INTAKE = "lab_result_ocr_intake"
    DATA_RETENTION = "data_retention"
    IMAGE_LEARNING_DATASET = "image_learning_dataset"
    RAW_OCR_TEXT_RETENTION = "raw_ocr_text_retention"


class ConsentStatus(BaseModel):
    """Current consent state for one consent bucket.

    Attributes:
        consent_type: Consent bucket.
        policy_version: Active policy version.
        title: Human-readable policy title.
        required: Whether the policy gates a protected feature.
        granted: Whether the active policy version is currently granted.
        occurred_at: Timestamp of the latest consent event for this bucket.
        revoked_at: Revocation timestamp when the latest event is a revocation.
    """

    consent_type: ConsentType
    policy_version: str
    title: str
    required: bool
    granted: bool
    occurred_at: datetime | None
    revoked_at: datetime | None


class ConsentStateResponse(BaseModel):
    """Current consent state response.

    Attributes:
        consents: Current consent states for all active policy buckets.
    """

    consents: list[ConsentStatus]


class ConsentActionResponse(BaseModel):
    """Consent grant or revocation response.

    Attributes:
        consent_type: Consent bucket.
        policy_version: Policy version used for the action.
        granted: New granted state.
        occurred_at: Timestamp of the consent event.
    """

    consent_type: ConsentType
    policy_version: str
    granted: bool
    occurred_at: datetime


class DeletionRequestType(StrEnum):
    """Supported deletion request scopes.

    Attributes:
        ALL_USER_DATA: Delete the current user's analysis results and consent records.
    """

    ALL_USER_DATA = "all_user_data"


class DeletionRequestStatus(StrEnum):
    """Deletion request processing status.

    Attributes:
        COMPLETED: Request was processed immediately.
        FAILED: Request failed with a sanitized reason.
    """

    COMPLETED = "completed"
    FAILED = "failed"


class DeletionRequestCreate(BaseModel):
    """Deletion request creation payload.

    Attributes:
        request_type: Deletion scope requested by the current user.
    """

    request_type: DeletionRequestType = DeletionRequestType.ALL_USER_DATA


class DeletionRequestResponse(BaseModel):
    """Deletion request response.

    Attributes:
        id: Deletion request identifier.
        request_type: Deletion scope.
        status: Processing status.
        requested_at: Time when the request was received.
        completed_at: Completion time for immediately processed requests.
        deleted_counts: Counts of deleted rows by resource type.
        failure_reason: Sanitized failure reason when failed.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    request_type: DeletionRequestType
    status: DeletionRequestStatus
    requested_at: datetime
    completed_at: datetime | None
    deleted_counts: dict[str, Any]
    failure_reason: str | None
