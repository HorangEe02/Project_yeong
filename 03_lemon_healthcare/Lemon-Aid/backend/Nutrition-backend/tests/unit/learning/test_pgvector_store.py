"""pgvector store validation tests."""

from __future__ import annotations

import math
from uuid import uuid4

import pytest
from src.learning.pgvector_store import validate_vector_record, vector_literal
from src.learning.vector_store import VectorRecord, VectorStoreError


def _record(**metadata: object) -> VectorRecord:
    """Build a valid vector record for tests."""
    return VectorRecord(
        owner_subject_hash="a" * 64,
        analysis_id=uuid4(),
        image_object_id=uuid4(),
        image_sha256="b" * 64,
        embedding=(0.1, 0.2),
        embedding_model="clip-ViT-B-32",
        metadata=dict(metadata) or {"display_name": "Vitamin C"},
    )


def test_vector_literal_serializes_finite_values() -> None:
    """Verify vectors are serialized for pgvector casts."""
    assert vector_literal((1.0, 2.5)) == "[1.0,2.5]"


@pytest.mark.parametrize("vector", [(), (math.nan,), (math.inf,)])
def test_vector_literal_rejects_invalid_values(vector: tuple[float, ...]) -> None:
    """Verify invalid values are rejected before DB execution."""
    with pytest.raises(VectorStoreError):
        vector_literal(vector)


def test_validate_vector_record_rejects_forbidden_metadata_keys() -> None:
    """Verify raw OCR text cannot be placed in vector metadata."""
    with pytest.raises(VectorStoreError):
        validate_vector_record(_record(raw_ocr_text="label text"))


def test_validate_vector_record_rejects_dimension_mismatch() -> None:
    """Verify configured dimensions are enforced before persistence."""
    with pytest.raises(VectorStoreError):
        validate_vector_record(_record(), expected_dimensions=3)
