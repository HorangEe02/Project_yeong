"""Embedding provider contracts for consent-gated image learning records."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


class EmbeddingError(RuntimeError):
    """Raised when embedding generation fails or returns invalid dimensions."""


@dataclass(frozen=True)
class EmbeddingInput:
    """Input payload for an embedding provider.

    Attributes:
        image_bytes: Normalized image bytes or an empty byte string for text-only embeddings.
        text: Optional user-confirmed structured text paired with the image. Raw OCR text
            must not be passed to learning providers.
        model: Embedding model identifier.
    """

    image_bytes: bytes
    text: str | None
    model: str


@dataclass(frozen=True)
class EmbeddingResult:
    """Embedding vector and model metadata.

    Attributes:
        vector: Dense vector values produced by the embedding model.
        model: Embedding model identifier.
        dimensions: Vector dimensionality.
    """

    vector: tuple[float, ...]
    model: str
    dimensions: int


class EmbeddingProvider(ABC):
    """Abstract embedding provider used by the learning pipeline."""

    @abstractmethod
    async def embed(self, payload: EmbeddingInput) -> EmbeddingResult:
        """Create an embedding for a consent-gated image/text payload.

        Args:
            payload: Image/text payload and model identifier.

        Returns:
            Embedding vector with dimensionality metadata.

        Raises:
            EmbeddingError: If the provider fails or returns an empty vector.
        """
        ...


class DisabledEmbeddingProvider(EmbeddingProvider):
    """Fail-closed embedding provider used when learning is disabled."""

    async def embed(self, payload: EmbeddingInput) -> EmbeddingResult:
        """Reject embedding generation in disabled environments.

        Args:
            payload: Embedding payload that will not be processed.

        Returns:
            Never returns.

        Raises:
            EmbeddingError: Always raised.
        """
        _ = payload
        raise EmbeddingError("Embedding generation is disabled until the learning gate passes.")
