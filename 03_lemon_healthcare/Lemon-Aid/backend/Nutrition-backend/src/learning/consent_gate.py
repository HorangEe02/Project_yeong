"""Consent and feature-flag gate for image learning data reuse."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from src.config import Settings
from src.models.schemas.privacy import ConsentType

IMAGE_LEARNING_REQUIRED_CONSENTS = (
    ConsentType.OCR_IMAGE_PROCESSING,
    ConsentType.DATA_RETENTION,
    ConsentType.IMAGE_LEARNING_DATASET,
)


@dataclass(frozen=True)
class ImageLearningGateDecision:
    """Decision returned by the image-learning gate.

    Attributes:
        allowed: Whether image reuse for learning/vector storage may proceed.
        required_consents: Consent buckets required for the gate.
        missing_consents: Required consent buckets not currently granted.
        reason: Safe explanation for logs or operator diagnostics.
    """

    allowed: bool
    required_consents: tuple[ConsentType, ...]
    missing_consents: tuple[ConsentType, ...]
    reason: str


def evaluate_image_learning_gate(
    settings: Settings,
    granted_consents: Iterable[ConsentType],
) -> ImageLearningGateDecision:
    """Evaluate whether a user's image may enter the learning dataset pipeline.

    Args:
        settings: Runtime settings containing learning and vector-store feature flags.
        granted_consents: Consent buckets granted by the current user.

    Returns:
        Gate decision. ``allowed=True`` only when both learning flags are enabled,
        retention is positive, and all required consents are granted.
    """
    required = IMAGE_LEARNING_REQUIRED_CONSENTS
    granted = set(granted_consents)
    missing = tuple(consent for consent in required if consent not in granted)

    if not settings.enable_image_learning_pipeline:
        return ImageLearningGateDecision(
            allowed=False,
            required_consents=required,
            missing_consents=missing,
            reason="ENABLE_IMAGE_LEARNING_PIPELINE=false",
        )
    if not settings.enable_pgvector_storage:
        return ImageLearningGateDecision(
            allowed=False,
            required_consents=required,
            missing_consents=missing,
            reason="ENABLE_PGVECTOR_STORAGE=false",
        )
    if settings.image_retention_days <= 0:
        return ImageLearningGateDecision(
            allowed=False,
            required_consents=required,
            missing_consents=missing,
            reason="IMAGE_RETENTION_DAYS must be positive for learning reuse.",
        )
    if missing:
        return ImageLearningGateDecision(
            allowed=False,
            required_consents=required,
            missing_consents=missing,
            reason="Required image-learning consent is missing.",
        )
    return ImageLearningGateDecision(
        allowed=True,
        required_consents=required,
        missing_consents=(),
        reason="Image-learning gate passed.",
    )
