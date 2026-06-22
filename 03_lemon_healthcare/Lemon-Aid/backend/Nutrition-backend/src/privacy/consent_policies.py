"""Active consent policy definitions."""

from __future__ import annotations

import hashlib

from pydantic import BaseModel

from src.models.schemas.privacy import ConsentType


class ConsentPolicyDefinition(BaseModel):
    """Runtime definition for an active consent policy.

    Attributes:
        consent_type: Consent bucket.
        version: Active policy version.
        title: Human-readable policy title.
        required: Whether the policy gates a protected feature.
        content_hash: SHA-256 hash of the reviewed policy text.
    """

    consent_type: ConsentType
    version: str
    title: str
    required: bool
    content_hash: str


def _policy_hash(policy_text: str) -> str:
    """Return a SHA-256 hash for reviewed policy text.

    Args:
        policy_text: Canonical policy text.

    Returns:
        Hex-encoded SHA-256 digest.
    """
    return hashlib.sha256(policy_text.encode("utf-8")).hexdigest()


ACTIVE_CONSENT_POLICIES: dict[ConsentType, ConsentPolicyDefinition] = {
    ConsentType.SENSITIVE_HEALTH_ANALYSIS: ConsentPolicyDefinition(
        consent_type=ConsentType.SENSITIVE_HEALTH_ANALYSIS,
        version="2026-05-11",
        title="Sensitive health analysis storage",
        required=True,
        content_hash=_policy_hash(
            "Consent to process and store validated health analysis inputs and computed outputs."
        ),
    ),
    ConsentType.HEALTH_DEVICE_DATA: ConsentPolicyDefinition(
        consent_type=ConsentType.HEALTH_DEVICE_DATA,
        version="2026-05-11",
        title="Health device data intake",
        required=False,
        content_hash=_policy_hash("Consent to collect future wearable and health device data."),
    ),
    ConsentType.OCR_IMAGE_PROCESSING: ConsentPolicyDefinition(
        consent_type=ConsentType.OCR_IMAGE_PROCESSING,
        version="2026-05-11",
        title="OCR image processing",
        required=False,
        content_hash=_policy_hash(
            "Consent to process future prescription or lab images for intake."
        ),
    ),
    ConsentType.EXTERNAL_OCR_PROCESSING: ConsentPolicyDefinition(
        consent_type=ConsentType.EXTERNAL_OCR_PROCESSING,
        version="2026-05-15",
        title="External OCR processing",
        required=False,
        content_hash=_policy_hash(
            "Consent to send supplement label images to an external OCR provider for "
            "text extraction preview. Raw images and raw OCR text are not stored by "
            "the service database."
        ),
    ),
    ConsentType.FOOD_IMAGE_PROCESSING: ConsentPolicyDefinition(
        consent_type=ConsentType.FOOD_IMAGE_PROCESSING,
        version="2026-05-27",
        title="Food image processing",
        required=True,
        content_hash=_policy_hash(
            "Separate consent to process food images into meal preview records. The service "
            "does not store raw food images, location metadata, provider payloads, or "
            "household context from the image."
        ),
    ),
    ConsentType.PRESCRIPTION_OCR_INTAKE: ConsentPolicyDefinition(
        consent_type=ConsentType.PRESCRIPTION_OCR_INTAKE,
        version="2026-05-15",
        title="Prescription OCR intake",
        required=True,
        content_hash=_policy_hash(
            "Separate consent to process prescription document images for intake-only "
            "OCR preview. The service does not store raw images, raw OCR text, or "
            "generate medication dose-change instructions."
        ),
    ),
    ConsentType.LAB_RESULT_OCR_INTAKE: ConsentPolicyDefinition(
        consent_type=ConsentType.LAB_RESULT_OCR_INTAKE,
        version="2026-05-15",
        title="Lab result OCR intake",
        required=True,
        content_hash=_policy_hash(
            "Separate consent to process lab result document images for intake-only "
            "OCR preview. The service does not store raw images, raw OCR text, "
            "diagnoses, or treatment recommendations."
        ),
    ),
    ConsentType.DATA_RETENTION: ConsentPolicyDefinition(
        consent_type=ConsentType.DATA_RETENTION,
        version="2026-05-11",
        title="Analysis history retention",
        required=False,
        content_hash=_policy_hash("Consent to retain analysis history for user review."),
    ),
    ConsentType.IMAGE_LEARNING_DATASET: ConsentPolicyDefinition(
        consent_type=ConsentType.IMAGE_LEARNING_DATASET,
        version="2026-05-13",
        title="Pseudonymized image learning dataset reuse",
        required=False,
        content_hash=_policy_hash(
            "Separate opt-in consent to reuse pseudonymized supplement images and labels "
            "for model evaluation or learning datasets."
        ),
    ),
    ConsentType.RAW_OCR_TEXT_RETENTION: ConsentPolicyDefinition(
        consent_type=ConsentType.RAW_OCR_TEXT_RETENTION,
        version="2026-06-21",
        title="OCR source text retention",
        required=False,
        content_hash=_policy_hash(
            "Separate opt-in to temporarily retain the recognized OCR source text from "
            "your supplement label. It is kept owner-scoped, only in the short-lived "
            "analysis preview, so you can review the original text during analysis."
        ),
    ),
}


def get_active_policy(consent_type: ConsentType) -> ConsentPolicyDefinition:
    """Return the active policy definition for a consent bucket.

    Args:
        consent_type: Consent bucket.

    Returns:
        Active consent policy definition.

    Raises:
        KeyError: If the consent bucket is not configured.
    """
    return ACTIVE_CONSENT_POLICIES[consent_type]
