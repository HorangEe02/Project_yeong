"""Factories for backend-only media object storage adapters."""

from __future__ import annotations

from pydantic import SecretStr

from src.config import Settings
from src.media.object_storage import (
    DisabledMediaObjectStore,
    LocalMediaObjectStore,
    MediaObjectStore,
    S3MediaObjectStore,
)


def build_media_object_store(settings: Settings) -> MediaObjectStore:
    """Build the configured media object store.

    Args:
        settings: Runtime settings.

    Returns:
        Media object store. Defaults to a fail-closed disabled adapter.
    """
    if settings.media_object_storage_provider == "local":
        return LocalMediaObjectStore(root=settings.media_object_storage_local_path)
    if settings.media_object_storage_provider == "s3":
        assert settings.media_object_storage_bucket is not None
        return S3MediaObjectStore(
            bucket=settings.media_object_storage_bucket,
            endpoint_url=settings.media_object_storage_endpoint_url,
            region_name=settings.media_object_storage_region,
        )
    if settings.media_object_storage_provider == "supabase_s3":
        bucket = settings.media_object_storage_bucket or settings.supabase_storage_private_bucket
        return S3MediaObjectStore(
            bucket=bucket,
            endpoint_url=(
                settings.media_object_storage_endpoint_url
                or _supabase_storage_s3_endpoint(settings.supabase_project_ref)
            ),
            region_name=settings.media_object_storage_region,
            access_key_id=_secret_value(settings.supabase_storage_s3_access_key_id),
            secret_access_key=_secret_value(settings.supabase_storage_s3_secret_access_key),
            provider_name="supabase_s3",
            force_path_style=True,
        )
    return DisabledMediaObjectStore()


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
