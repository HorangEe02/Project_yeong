"""Learning image object storage adapter tests."""

from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from src.learning.object_storage import (
    LearningImageObjectInput,
    LearningObjectStorageError,
    LocalLearningImageObjectStore,
    S3LearningImageObjectStore,
)


def _payload() -> LearningImageObjectInput:
    """Build a small object storage payload for tests."""
    return LearningImageObjectInput(
        image_bytes=b"image-bytes",
        image_sha256="a" * 64,
        mime_type="image/png",
        owner_subject_hash="b" * 64,
        retained_until=datetime(2026, 5, 16, tzinfo=UTC),
        metadata={"analysis_id": "analysis-1"},
    )


@pytest.mark.asyncio
async def test_local_learning_image_object_store_round_trip(tmp_path: Path) -> None:
    """Verify local object store can put, read, and delete an image."""
    store = LocalLearningImageObjectStore(tmp_path)

    stored = await store.put_image(_payload())

    assert stored.object_uri.startswith("local://learning/images/")
    assert await store.get_image(stored.object_uri) == b"image-bytes"

    await store.delete_image(stored.object_uri)

    assert not any(tmp_path.rglob("*-*"))


@pytest.mark.asyncio
async def test_local_learning_image_object_store_rejects_unsafe_metadata(tmp_path: Path) -> None:
    """Verify local retention also fails closed for unsafe metadata."""
    store = LocalLearningImageObjectStore(tmp_path)
    payload = _payload()
    unsafe_payload = LearningImageObjectInput(
        image_bytes=payload.image_bytes,
        image_sha256=payload.image_sha256,
        mime_type=payload.mime_type,
        owner_subject_hash=payload.owner_subject_hash,
        retained_until=payload.retained_until,
        metadata={"raw_ocr_text": "vitamin c 1000mg"},
    )

    with pytest.raises(LearningObjectStorageError, match="forbidden key"):
        await store.put_image(unsafe_payload)

    assert not any(tmp_path.rglob("*"))


class _FakeS3Client:
    """Minimal fake S3 client used by storage adapter tests."""

    def __init__(self) -> None:
        """Initialize call tracking."""
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.body = b""

    def put_object(self, **kwargs: Any) -> dict[str, str]:
        """Record a put_object call."""
        self.calls.append(("put_object", kwargs))
        self.body = bytes(kwargs["Body"])
        return {"VersionId": "version-1"}

    def get_object(self, **kwargs: Any) -> dict[str, BytesIO]:
        """Record a get_object call."""
        self.calls.append(("get_object", kwargs))
        return {"Body": BytesIO(self.body)}

    def delete_object(self, **kwargs: Any) -> dict[str, object]:
        """Record a delete_object call."""
        self.calls.append(("delete_object", kwargs))
        return {}


@pytest.mark.asyncio
async def test_s3_learning_image_object_store_uses_safe_object_calls() -> None:
    """Verify S3 adapter wraps put/get/delete without storing raw data in metadata."""
    client = _FakeS3Client()
    store = S3LearningImageObjectStore(bucket="bucket", client=client)

    stored = await store.put_image(_payload())
    loaded = await store.get_image(stored.object_uri, stored.version_id)
    await store.delete_image(stored.object_uri, stored.version_id)

    assert loaded == b"image-bytes"
    assert stored.object_uri.startswith("s3://bucket/learning/images/")
    assert client.calls[0][0] == "put_object"
    assert client.calls[0][1]["ContentType"] == "image/png"
    assert client.calls[0][1]["ServerSideEncryption"] == "AES256"
    assert "raw_ocr_text" not in client.calls[0][1]["Metadata"]
    assert client.calls[1][1]["VersionId"] == "version-1"
    assert client.calls[2][1]["VersionId"] == "version-1"


@pytest.mark.asyncio
async def test_s3_learning_image_object_store_can_label_supabase_provider() -> None:
    """Verify Supabase S3 objects are marked with a distinct private provider."""
    client = _FakeS3Client()
    store = S3LearningImageObjectStore(
        bucket="learning-images",
        provider_name="supabase_s3",
        client=client,
    )

    stored = await store.put_image(_payload())

    assert stored.provider == "supabase_s3"
    assert stored.object_uri.startswith("s3://learning-images/learning/images/")


@pytest.mark.asyncio
async def test_s3_learning_image_object_store_can_disable_sse_header() -> None:
    """Verify Supabase-compatible construction can omit unsupported SSE headers."""
    client = _FakeS3Client()
    store = S3LearningImageObjectStore(
        bucket="learning-images",
        server_side_encryption=None,
        client=client,
    )

    await store.put_image(_payload())

    assert "ServerSideEncryption" not in client.calls[0][1]


@pytest.mark.asyncio
async def test_s3_learning_image_object_store_rejects_forbidden_metadata_key() -> None:
    """Verify raw OCR/image fields cannot become object metadata headers."""
    client = _FakeS3Client()
    store = S3LearningImageObjectStore(bucket="bucket", client=client)
    payload = _payload()
    unsafe_payload = LearningImageObjectInput(
        image_bytes=payload.image_bytes,
        image_sha256=payload.image_sha256,
        mime_type=payload.mime_type,
        owner_subject_hash=payload.owner_subject_hash,
        retained_until=payload.retained_until,
        metadata={"provider_payload": "{}"},
    )

    with pytest.raises(LearningObjectStorageError, match="forbidden key"):
        await store.put_image(unsafe_payload)

    assert client.calls == []


@pytest.mark.asyncio
async def test_s3_learning_image_object_store_rejects_secret_like_metadata_value() -> None:
    """Verify credential-like values cannot become object metadata headers."""
    client = _FakeS3Client()
    store = S3LearningImageObjectStore(bucket="bucket", client=client)
    payload = _payload()
    unsafe_payload = LearningImageObjectInput(
        image_bytes=payload.image_bytes,
        image_sha256=payload.image_sha256,
        mime_type=payload.mime_type,
        owner_subject_hash=payload.owner_subject_hash,
        retained_until=payload.retained_until,
        metadata={"operator_note": "Bearer token-value"},
    )

    with pytest.raises(LearningObjectStorageError, match="forbidden value"):
        await store.put_image(unsafe_payload)

    assert client.calls == []
