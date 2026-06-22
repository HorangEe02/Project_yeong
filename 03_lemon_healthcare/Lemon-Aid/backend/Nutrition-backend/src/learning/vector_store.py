"""Vector-store contracts for pgvector-backed learning datasets."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any
from uuid import UUID


class VectorStoreError(RuntimeError):
    """Raised when vector persistence or lookup fails."""


@dataclass(frozen=True)
class VectorRecord:
    """Metadata stored with a consent-gated image embedding.

    Attributes:
        owner_subject_hash: HMAC or pseudonymous owner identifier.
        analysis_id: Supplement analysis preview that produced the record.
        image_object_id: Retained learning image object identifier.
        image_sha256: SHA-256 hash of the source image bytes.
        embedding: Dense vector values.
        embedding_model: Embedding model identifier.
        metadata: Sanitized metadata. Raw image bytes and raw OCR text are forbidden.
    """

    owner_subject_hash: str
    analysis_id: UUID
    image_object_id: UUID
    image_sha256: str
    embedding: tuple[float, ...]
    embedding_model: str
    metadata: dict[str, Any]


class VectorStore(ABC):
    """Abstract vector storage interface.

    Concrete implementations may use pgvector, but callers should depend on this
    interface so tests and disabled environments can fail closed without importing
    optional database extensions.
    """

    @abstractmethod
    async def upsert_image_embedding(self, record: VectorRecord) -> None:
        """Persist or update one consent-gated image embedding.

        Args:
            record: Sanitized vector record.

        Raises:
            VectorStoreError: If the vector cannot be persisted safely.
        """
        ...


class DisabledVectorStore(VectorStore):
    """Fail-closed vector store used before pgvector storage is approved."""

    async def upsert_image_embedding(self, record: VectorRecord) -> None:
        """Reject vector persistence in disabled environments.

        Args:
            record: Vector record that will not be persisted.

        Raises:
            VectorStoreError: Always raised.
        """
        _ = record
        raise VectorStoreError("pgvector storage is disabled until the learning gate passes.")
