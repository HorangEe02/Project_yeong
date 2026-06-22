"""Image learning consent gate tests."""

from __future__ import annotations

from src.config import Settings
from src.learning.consent_gate import evaluate_image_learning_gate
from src.models.schemas.privacy import ConsentType


def test_image_learning_gate_defaults_to_disabled() -> None:
    """Verify image learning reuse is disabled by default."""
    decision = evaluate_image_learning_gate(Settings(), [])

    assert decision.allowed is False
    assert decision.reason == "ENABLE_IMAGE_LEARNING_PIPELINE=false"
    assert ConsentType.IMAGE_LEARNING_DATASET in decision.required_consents


def test_image_learning_gate_requires_all_consents_and_retention() -> None:
    """Verify learning reuse requires flags, retention, and separate consent."""
    settings = Settings(
        enable_image_learning_pipeline=True,
        enable_pgvector_storage=True,
        image_retention_days=30,
    )

    blocked = evaluate_image_learning_gate(settings, [ConsentType.OCR_IMAGE_PROCESSING])

    assert blocked.allowed is False
    assert blocked.missing_consents == (
        ConsentType.DATA_RETENTION,
        ConsentType.IMAGE_LEARNING_DATASET,
    )

    allowed = evaluate_image_learning_gate(
        settings,
        [
            ConsentType.OCR_IMAGE_PROCESSING,
            ConsentType.DATA_RETENTION,
            ConsentType.IMAGE_LEARNING_DATASET,
        ],
    )

    assert allowed.allowed is True
    assert allowed.missing_consents == ()
