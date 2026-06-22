"""Concrete embedding runners for consent-gated image learning."""

from __future__ import annotations

import math
from importlib import import_module
from io import BytesIO
from typing import Any

from src.learning.embeddings import (
    EmbeddingError,
    EmbeddingInput,
    EmbeddingProvider,
    EmbeddingResult,
)


class SentenceTransformersImageEmbeddingProvider(EmbeddingProvider):
    """Local Sentence Transformers image embedding provider.

    The model is loaded lazily so default application startup remains independent
    of optional learning dependencies.
    """

    def __init__(self, model_name: str, expected_dimensions: int | None = None) -> None:
        """Initialize the provider.

        Args:
            model_name: Sentence Transformers model identifier.
            expected_dimensions: Optional dimension guard from runtime settings.
        """
        self._model_name = model_name
        self._expected_dimensions = expected_dimensions
        self._model: Any | None = None

    async def embed(self, payload: EmbeddingInput) -> EmbeddingResult:
        """Create an embedding from an image or confirmed structured text.

        Args:
            payload: Image/text payload and model identifier.

        Returns:
            Validated embedding result.

        Raises:
            EmbeddingError: If dependencies are missing, model ids differ, or the
                model returns an invalid vector.
        """
        if payload.model != self._model_name:
            raise EmbeddingError("Embedding payload model does not match the configured model.")
        model = self._load_model()
        model_input = self._build_model_input(payload)
        try:
            raw_embedding = model.encode(model_input)
        except Exception as exc:
            raise EmbeddingError("Embedding model failed to encode the payload.") from exc
        vector = coerce_embedding_vector(raw_embedding, self._expected_dimensions)
        return EmbeddingResult(
            vector=vector,
            model=self._model_name,
            dimensions=len(vector),
        )

    def _load_model(self) -> Any:
        """Load the configured Sentence Transformers model lazily.

        Returns:
            Loaded model instance.

        Raises:
            EmbeddingError: If the optional dependency is unavailable.
        """
        if self._model is not None:
            return self._model
        try:
            module = import_module("sentence_transformers")
        except ImportError as exc:
            raise EmbeddingError(
                "sentence-transformers is required for the learning embedding provider."
            ) from exc
        model_cls = module.SentenceTransformer
        self._model = model_cls(self._model_name)
        return self._model

    def _build_model_input(self, payload: EmbeddingInput) -> Any:
        """Build a Sentence Transformers input object.

        Args:
            payload: Embedding payload.

        Returns:
            PIL image for image embeddings, or text for structured text embeddings.

        Raises:
            EmbeddingError: If no valid input is available or PIL fails to decode the image.
        """
        if payload.image_bytes:
            try:
                pil_module = import_module("PIL.Image")
                return pil_module.open(BytesIO(payload.image_bytes))
            except Exception as exc:
                raise EmbeddingError("Embedding image bytes cannot be decoded.") from exc
        if payload.text and payload.text.strip():
            return payload.text
        raise EmbeddingError("Embedding payload must contain image bytes or confirmed text.")


def coerce_embedding_vector(
    raw_embedding: Any,
    expected_dimensions: int | None = None,
) -> tuple[float, ...]:
    """Coerce model output into a finite float tuple.

    Args:
        raw_embedding: Model output. NumPy arrays and nested single-vector lists
            are accepted.
        expected_dimensions: Optional expected vector length.

    Returns:
        Dense finite vector values.

    Raises:
        EmbeddingError: If the vector is empty, non-numeric, non-finite, or has
            unexpected dimensionality.
    """
    values = raw_embedding.tolist() if hasattr(raw_embedding, "tolist") else raw_embedding
    if isinstance(values, list) and values and isinstance(values[0], list):
        values = values[0]
    try:
        vector = tuple(float(value) for value in values)
    except (TypeError, ValueError) as exc:
        raise EmbeddingError("Embedding model returned a non-numeric vector.") from exc
    if not vector:
        raise EmbeddingError("Embedding model returned an empty vector.")
    if not all(math.isfinite(value) for value in vector):
        raise EmbeddingError("Embedding model returned a non-finite vector.")
    if expected_dimensions is not None and len(vector) != expected_dimensions:
        raise EmbeddingError("Embedding vector dimensions do not match settings.")
    return vector
