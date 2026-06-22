"""Factories for consent-gated learning adapters."""

from __future__ import annotations

from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import Settings
from src.learning.embedding_runner import SentenceTransformersImageEmbeddingProvider
from src.learning.embeddings import DisabledEmbeddingProvider, EmbeddingProvider
from src.learning.object_storage import (
    DisabledLearningImageObjectStore,
    LearningImageObjectStore,
    LocalLearningImageObjectStore,
    S3LearningImageObjectStore,
)
from src.learning.pgvector_store import PgvectorStore
from src.learning.vector_store import DisabledVectorStore, VectorStore


def build_learning_object_store(settings: Settings) -> LearningImageObjectStore:
    """Build the configured learning image object store.

    Args:
        settings: Runtime settings.

    Returns:
        Object storage adapter. Defaults to a fail-closed disabled adapter.
    """
    if settings.learning_object_storage_provider == "local":
        return LocalLearningImageObjectStore(
            root=settings.learning_object_storage_local_path,
            prefix=settings.learning_object_storage_prefix,
        )
    if settings.learning_object_storage_provider == "s3":
        assert settings.learning_object_storage_bucket is not None
        return S3LearningImageObjectStore(
            bucket=settings.learning_object_storage_bucket,
            prefix=settings.learning_object_storage_prefix,
            endpoint_url=settings.learning_object_storage_endpoint_url,
            region_name=settings.learning_object_storage_region,
            server_side_encryption=settings.learning_object_storage_sse,
        )
    if settings.learning_object_storage_provider == "supabase_s3":
        bucket = settings.learning_object_storage_bucket or settings.supabase_storage_private_bucket
        return S3LearningImageObjectStore(
            bucket=bucket,
            prefix=settings.learning_object_storage_prefix,
            endpoint_url=(
                settings.learning_object_storage_endpoint_url
                or _supabase_storage_s3_endpoint(settings.supabase_project_ref)
            ),
            region_name=settings.learning_object_storage_region,
            server_side_encryption=None,
            access_key_id=_secret_value(settings.supabase_storage_s3_access_key_id),
            secret_access_key=_secret_value(settings.supabase_storage_s3_secret_access_key),
            provider_name="supabase_s3",
            force_path_style=True,
        )
    return DisabledLearningImageObjectStore()


def _supabase_storage_s3_endpoint(project_ref: str | None) -> str:
    """Build the hosted Supabase Storage S3 endpoint.

    Args:
        project_ref: Supabase project reference.

    Returns:
        S3-compatible Storage endpoint URL.

    Raises:
        ValueError: If project ref is missing.
    """
    if not project_ref:
        raise ValueError("SUPABASE_PROJECT_REF is required for hosted Supabase Storage S3.")
    return f"https://{project_ref}.storage.supabase.co/storage/v1/s3"


def _secret_value(secret: SecretStr | None) -> str | None:
    """Return a secret value without logging or formatting it.

    Args:
        secret: Optional Pydantic secret.

    Returns:
        Plain secret string for SDK credential injection.
    """
    return secret.get_secret_value() if secret is not None else None


def build_embedding_provider(settings: Settings) -> EmbeddingProvider:
    """Build the configured embedding provider.

    Args:
        settings: Runtime settings.

    Returns:
        Embedding provider. Defaults to a fail-closed disabled provider.
    """
    if not settings.enable_image_learning_pipeline:
        return DisabledEmbeddingProvider()
    return SentenceTransformersImageEmbeddingProvider(
        model_name=settings.embedding_model,
        expected_dimensions=settings.embedding_dimensions,
    )


def build_vector_store(settings: Settings, session: AsyncSession) -> VectorStore:
    """Build the configured vector store.

    Args:
        settings: Runtime settings.
        session: Async database session.

    Returns:
        Vector store. Defaults to a fail-closed disabled store.
    """
    if not settings.enable_pgvector_storage:
        return DisabledVectorStore()
    return PgvectorStore(session=session, expected_dimensions=settings.embedding_dimensions)
