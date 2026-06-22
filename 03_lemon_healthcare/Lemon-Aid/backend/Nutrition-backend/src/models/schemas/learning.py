"""Schemas for consent-gated learning data pipeline metadata."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.models.schemas.privacy import ConsentType


class ImageLearningGateStatus(BaseModel):
    """Serializable image-learning gate decision.

    Attributes:
        allowed: Whether learning reuse may proceed.
        required_consents: Consent buckets required by the gate.
        missing_consents: Required consent buckets not currently granted.
        reason: Safe diagnostic reason.
    """

    model_config = ConfigDict(extra="forbid")

    allowed: bool
    required_consents: list[ConsentType]
    missing_consents: list[ConsentType]
    reason: str = Field(min_length=1, max_length=240)


class ImageEmbeddingRecordPreview(BaseModel):
    """Metadata preview for a vector-store image embedding record.

    Attributes:
        analysis_id: Supplement analysis preview identifier.
        image_sha256: Source image SHA-256 hash.
        embedding_model: Embedding model identifier.
        dimensions: Embedding dimensionality.
        raw_image_stored: Whether raw image bytes are retained.
        raw_ocr_text_stored: Whether raw OCR text is retained.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    analysis_id: UUID
    image_sha256: str = Field(min_length=64, max_length=64)
    embedding_model: str = Field(min_length=1, max_length=120)
    dimensions: int = Field(ge=1)
    raw_image_stored: bool = False
    raw_ocr_text_stored: bool = False
