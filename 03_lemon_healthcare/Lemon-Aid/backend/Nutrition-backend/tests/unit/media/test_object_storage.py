"""Backend-only media object storage adapter tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from src.media.object_storage import (
    LocalMediaObjectStore,
    MediaObjectReference,
    MediaObjectStorageError,
    S3MediaObjectStore,
)


@pytest.mark.asyncio
async def test_local_media_object_store_deletes_relative_private_ref(tmp_path: Path) -> None:
    """Verify local media deletion resolves only private relative refs."""
    target = tmp_path / "supplement" / "object.png"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"image-bytes")
    store = LocalMediaObjectStore(tmp_path)

    await store.delete_object(
        MediaObjectReference(
            object_storage_provider="local",
            object_ref="supplement/object.png",
        )
    )

    assert not target.exists()


@pytest.mark.parametrize(
    "object_ref",
    (
        "https://example.com/object.png",
        "/absolute/object.png",
        "../outside/object.png",
        "safe/../../outside.png",
        r"safe\windows-path.png",
    ),
)
@pytest.mark.asyncio
async def test_local_media_object_store_rejects_public_or_traversing_refs(
    tmp_path: Path,
    object_ref: str,
) -> None:
    """Verify local deletion fails closed for refs that could escape the private root."""
    store = LocalMediaObjectStore(tmp_path)

    with pytest.raises(MediaObjectStorageError, match="Invalid media object reference"):
        await store.delete_object(
            MediaObjectReference(
                object_storage_provider="local",
                object_ref=object_ref,
            )
        )


@pytest.mark.asyncio
async def test_local_media_object_store_rejects_provider_mismatch(tmp_path: Path) -> None:
    """Verify provider mismatches cannot delete from the wrong backend."""
    store = LocalMediaObjectStore(tmp_path)

    with pytest.raises(MediaObjectStorageError, match="provider is not configured"):
        await store.delete_object(
            MediaObjectReference(
                object_storage_provider="supabase_s3",
                object_ref="supplement/object.png",
            )
        )


class _FakeS3Client:
    """Minimal fake S3 client used by media storage adapter tests."""

    def __init__(self) -> None:
        """Initialize call tracking."""
        self.calls: list[dict[str, Any]] = []

    def delete_object(self, **kwargs: Any) -> dict[str, object]:
        """Record a delete_object call.

        Args:
            **kwargs: S3 delete_object keyword arguments.

        Returns:
            Empty S3-like response.
        """
        self.calls.append(kwargs)
        return {}


@pytest.mark.asyncio
async def test_s3_media_object_store_deletes_private_key_with_version() -> None:
    """Verify S3 delete uses configured bucket and does not accept URL refs."""
    client = _FakeS3Client()
    store = S3MediaObjectStore(
        bucket="private-media",
        provider_name="supabase_s3",
        client=client,
    )

    await store.delete_object(
        MediaObjectReference(
            object_storage_provider="supabase_s3",
            object_ref="supplement/2026/05/object.png",
            object_version_id="version-1",
        )
    )

    assert client.calls == [
        {
            "Bucket": "private-media",
            "Key": "supplement/2026/05/object.png",
            "VersionId": "version-1",
        }
    ]


@pytest.mark.asyncio
async def test_s3_media_object_store_rejects_public_url_ref() -> None:
    """Verify S3 deletion refuses public URLs instead of parsing them."""
    client = _FakeS3Client()
    store = S3MediaObjectStore(bucket="private-media", client=client)

    with pytest.raises(MediaObjectStorageError, match="Invalid media object reference"):
        await store.delete_object(
            MediaObjectReference(
                object_storage_provider="s3",
                object_ref="https://example.com/private-media/object.png",
            )
        )

    assert client.calls == []
