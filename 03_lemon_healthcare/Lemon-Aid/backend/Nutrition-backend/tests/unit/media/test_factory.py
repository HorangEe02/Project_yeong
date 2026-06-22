"""Backend-only media adapter factory tests."""

from __future__ import annotations

from typing import Any

from src.config import Settings
from src.media import factory


def test_build_media_object_store_uses_supabase_storage_endpoint(
    monkeypatch: Any,
) -> None:
    """Verify Supabase Storage S3 config is derived without committing secrets."""
    captured: dict[str, object] = {}

    class FakeS3MediaObjectStore:
        """Capture factory arguments for Supabase Storage S3 construction."""

        def __init__(self, **kwargs: object) -> None:
            """Capture constructor keyword arguments.

            Args:
                **kwargs: Constructor settings from the factory.
            """
            captured.update(kwargs)

    monkeypatch.setattr(factory, "S3MediaObjectStore", FakeS3MediaObjectStore)
    settings = Settings(
        _env_file=None,
        media_object_storage_provider="supabase_s3",
        supabase_project_ref="projectref",
        media_object_storage_region="ap-northeast-2",
        supabase_storage_s3_access_key_id="access",
        supabase_storage_s3_secret_access_key="secret",  # pragma: allowlist secret
    )

    store = factory.build_media_object_store(settings)

    assert isinstance(store, FakeS3MediaObjectStore)
    assert captured["bucket"] == "learning-images"
    assert captured["endpoint_url"] == "https://projectref.storage.supabase.co/storage/v1/s3"
    assert captured["region_name"] == "ap-northeast-2"
    assert captured["provider_name"] == "supabase_s3"
    assert captured["force_path_style"] is True
    assert captured["access_key_id"] == "access"
    assert captured["secret_access_key"] == "secret"  # pragma: allowlist secret
