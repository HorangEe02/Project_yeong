"""Embedding runner validation tests."""

from __future__ import annotations

import math

import pytest
from src.learning.embedding_runner import coerce_embedding_vector
from src.learning.embeddings import EmbeddingError


def test_coerce_embedding_vector_accepts_single_vector() -> None:
    """Verify embedding output is converted to a float tuple."""
    assert coerce_embedding_vector([1, 2.5, "3"], expected_dimensions=3) == (1.0, 2.5, 3.0)


def test_coerce_embedding_vector_accepts_nested_single_vector() -> None:
    """Verify model outputs shaped like one batched vector are accepted."""
    assert coerce_embedding_vector([[1, 2]], expected_dimensions=2) == (1.0, 2.0)


@pytest.mark.parametrize("raw_embedding", [[], [math.nan], [math.inf], ["not-a-number"]])
def test_coerce_embedding_vector_rejects_invalid_output(raw_embedding: object) -> None:
    """Verify invalid model outputs fail before pgvector persistence."""
    with pytest.raises(EmbeddingError):
        coerce_embedding_vector(raw_embedding)


def test_coerce_embedding_vector_rejects_dimension_mismatch() -> None:
    """Verify configured dimensions are enforced when provided."""
    with pytest.raises(EmbeddingError):
        coerce_embedding_vector([1, 2, 3], expected_dimensions=2)
