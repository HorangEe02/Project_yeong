"""pgvector-backed vector store adapter."""

from __future__ import annotations

import json
import math
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.learning.vector_store import VectorRecord, VectorStore, VectorStoreError

FORBIDDEN_METADATA_KEYS = frozenset(
    {
        "raw_image",
        "raw_image_bytes",
        "image_base64",
        "raw_ocr_text",
        "ocr_text",
        "raw_llm_response",
        "access_token",
        "credential",
        "credentials",
    }
)
SHA256_HEX_LENGTH = 64


class PgvectorStore(VectorStore):
    """Persist consent-gated image embeddings with pgvector."""

    def __init__(self, session: AsyncSession, expected_dimensions: int | None = None) -> None:
        """Initialize the store.

        Args:
            session: Request or worker scoped async session.
            expected_dimensions: Optional dimension guard from runtime settings.
        """
        self._session = session
        self._expected_dimensions = expected_dimensions

    async def upsert_image_embedding(self, record: VectorRecord) -> None:
        """Persist or update one consent-gated image embedding.

        Args:
            record: Sanitized vector record.

        Raises:
            VectorStoreError: If validation or persistence fails.
        """
        validate_vector_record(record, self._expected_dimensions)
        embedding_literal = vector_literal(record.embedding)
        metadata_json = json.dumps(record.metadata, ensure_ascii=False, sort_keys=True)
        statement = text("""
            INSERT INTO image_embedding_records (
                owner_subject_hash,
                analysis_id,
                image_object_id,
                image_sha256,
                embedding_model,
                embedding_dimensions,
                embedding,
                metadata
            )
            VALUES (
                :owner_subject_hash,
                :analysis_id,
                :image_object_id,
                :image_sha256,
                :embedding_model,
                :embedding_dimensions,
                CAST(:embedding AS extensions.vector),
                CAST(:metadata AS jsonb)
            )
            ON CONFLICT (
                owner_subject_hash,
                analysis_id,
                embedding_model,
                image_sha256
            )
            DO UPDATE SET
                image_object_id = EXCLUDED.image_object_id,
                embedding_dimensions = EXCLUDED.embedding_dimensions,
                embedding = EXCLUDED.embedding,
                metadata = EXCLUDED.metadata,
                deleted_at = NULL,
                updated_at = now()
            """)
        try:
            await self._session.execute(
                statement,
                {
                    "owner_subject_hash": record.owner_subject_hash,
                    "analysis_id": record.analysis_id,
                    "image_object_id": record.image_object_id,
                    "image_sha256": record.image_sha256,
                    "embedding_model": record.embedding_model,
                    "embedding_dimensions": len(record.embedding),
                    "embedding": embedding_literal,
                    "metadata": metadata_json,
                },
            )
            await self._session.commit()
        except Exception as exc:
            await self._session.rollback()
            raise VectorStoreError("Failed to upsert pgvector image embedding.") from exc


def validate_vector_record(record: VectorRecord, expected_dimensions: int | None = None) -> None:
    """Validate a vector record before persistence.

    Args:
        record: Candidate vector record.
        expected_dimensions: Optional expected vector length.

    Raises:
        VectorStoreError: If the record is unsafe or invalid.
    """
    if len(record.owner_subject_hash) != SHA256_HEX_LENGTH:
        raise VectorStoreError("owner_subject_hash must be a 64-character HMAC hex string.")
    if len(record.image_sha256) != SHA256_HEX_LENGTH:
        raise VectorStoreError("image_sha256 must be a 64-character SHA-256 hex string.")
    if not record.embedding_model.strip():
        raise VectorStoreError("embedding_model is required.")
    if not record.embedding:
        raise VectorStoreError("embedding vector must not be empty.")
    if expected_dimensions is not None and len(record.embedding) != expected_dimensions:
        raise VectorStoreError("embedding vector dimensions do not match settings.")
    if not all(math.isfinite(value) for value in record.embedding):
        raise VectorStoreError("embedding vector contains non-finite values.")
    validate_vector_metadata(record.metadata)


def validate_vector_metadata(metadata: dict[str, Any]) -> None:
    """Reject metadata that could contain raw images, raw OCR text, or secrets.

    Args:
        metadata: Candidate metadata payload.

    Raises:
        VectorStoreError: If forbidden keys are present.
    """
    for key, value in metadata.items():
        if key.casefold() in FORBIDDEN_METADATA_KEYS:
            raise VectorStoreError(f"Forbidden vector metadata key: {key}")
        if isinstance(value, dict):
            validate_vector_metadata(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    validate_vector_metadata(item)


def vector_literal(vector: tuple[float, ...]) -> str:
    """Serialize a finite vector for PostgreSQL pgvector casts.

    Args:
        vector: Dense vector values.

    Returns:
        pgvector text literal.

    Raises:
        VectorStoreError: If vector values are non-finite.
    """
    if not vector:
        raise VectorStoreError("embedding vector must not be empty.")
    if not all(math.isfinite(value) for value in vector):
        raise VectorStoreError("embedding vector contains non-finite values.")
    return "[" + ",".join(str(float(value)) for value in vector) + "]"
