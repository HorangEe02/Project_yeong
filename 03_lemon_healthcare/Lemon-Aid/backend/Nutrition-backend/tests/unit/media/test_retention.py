"""Backend-only media retention cleanup tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from src.media.object_storage import MediaObjectReference, MediaObjectStorageError
from src.media.retention import (
    MEDIA_OBJECT_STATUS_DELETED,
    MEDIA_OBJECT_STATUS_FAILED,
    delete_expired_media_objects,
    retry_failed_media_object_deletions,
)
from src.models.db.media import MediaObject


class _FakeScalarResult:
    """Fake SQLAlchemy scalar result for predefined records."""

    def __init__(self, records: list[object]) -> None:
        """Initialize records returned by all()."""
        self._records = records

    def all(self) -> list[object]:
        """Return captured records."""
        return self._records


class _FakeDeletionSession:
    """Fake async session that serves model-specific query results."""

    def __init__(self, records_by_model: dict[type[object], list[object]]) -> None:
        """Initialize model-specific query rows."""
        self.records_by_model = records_by_model
        self.deleted: list[object] = []
        self.commit_count = 0

    async def scalars(self, statement: object) -> _FakeScalarResult:
        """Return rows for the selected ORM entity."""
        model = statement.column_descriptions[0].get("entity")  # type: ignore[attr-defined]
        return _FakeScalarResult(self.records_by_model.get(model, []))

    async def delete(self, record: object) -> None:
        """Capture ORM rows deleted by the helper."""
        self.deleted.append(record)

    async def commit(self) -> None:
        """Track commit calls."""
        self.commit_count += 1


class _FakeMediaObjectStore:
    """Fake media object store with optional delete failures."""

    def __init__(self, *, fail: bool = False) -> None:
        """Initialize the fake object store."""
        self.fail = fail
        self.deleted: list[MediaObjectReference] = []

    async def delete_object(self, reference: MediaObjectReference) -> None:
        """Delete or fail without exposing object details in test output."""
        if self.fail:
            raise MediaObjectStorageError("sensitive object ref should not be printed")
        self.deleted.append(reference)


def _media_object(**overrides: Any) -> MediaObject:
    """Build a retained media object row for cleanup tests."""
    values: dict[str, Any] = {
        "id": uuid4(),
        "owner_subject_hash": "a" * 64,
        "domain": "supplement_label",
        "object_storage_provider": "supabase_s3",
        "object_ref": "supplement/2026/05/object.png",
        "object_version_id": "version-1",
        "image_sha256": "b" * 64,
        "image_mime_type": "image/png",
        "image_size_bytes": 1024,
        "exif_stripped": True,
        "retained_until": datetime.now(UTC) - timedelta(days=1),
        "status": "retained",
        "consent_snapshot": {"consents": []},
    }
    values.update(overrides)
    return MediaObject(**values)


@pytest.mark.asyncio
async def test_delete_expired_media_objects_removes_object_and_row() -> None:
    """Verify expiry cleanup deletes both the private object and DB row."""
    media_object = _media_object()
    session = _FakeDeletionSession({MediaObject: [media_object]})
    object_store = _FakeMediaObjectStore()

    result = await delete_expired_media_objects(
        session=session,  # type: ignore[arg-type]
        object_store=object_store,  # type: ignore[arg-type]
    )

    assert result == {"scanned": 1, "deleted": 1, "failures": 0}
    assert media_object.status == MEDIA_OBJECT_STATUS_DELETED
    assert media_object.deleted_at is not None
    assert object_store.deleted == [
        MediaObjectReference(
            object_storage_provider=media_object.object_storage_provider,
            object_ref=media_object.object_ref,
            object_version_id=media_object.object_version_id,
        )
    ]
    assert session.deleted == [media_object]
    assert session.commit_count == 1


@pytest.mark.asyncio
async def test_delete_expired_media_objects_keeps_row_on_failure() -> None:
    """Verify expiry cleanup failures keep rows queryable for later retries."""
    media_object = _media_object()
    session = _FakeDeletionSession({MediaObject: [media_object]})
    object_store = _FakeMediaObjectStore(fail=True)

    result = await delete_expired_media_objects(
        session=session,  # type: ignore[arg-type]
        object_store=object_store,  # type: ignore[arg-type]
    )

    assert result == {"scanned": 1, "deleted": 0, "failures": 1}
    assert media_object.status == MEDIA_OBJECT_STATUS_FAILED
    assert media_object.deleted_at is None
    assert object_store.deleted == []
    assert session.deleted == []
    assert session.commit_count == 1


@pytest.mark.asyncio
async def test_retry_failed_media_object_deletions_removes_object_and_row() -> None:
    """Verify retry cleanup deletes a previously failed private media object."""
    media_object = _media_object(status=MEDIA_OBJECT_STATUS_FAILED)
    session = _FakeDeletionSession({MediaObject: [media_object]})
    object_store = _FakeMediaObjectStore()

    result = await retry_failed_media_object_deletions(
        session=session,  # type: ignore[arg-type]
        object_store=object_store,  # type: ignore[arg-type]
    )

    assert result == {"scanned": 1, "deleted": 1, "failures": 0}
    assert media_object.status == MEDIA_OBJECT_STATUS_DELETED
    assert media_object.deleted_at is not None
    assert session.deleted == [media_object]
    assert session.commit_count == 1


@pytest.mark.asyncio
async def test_retry_failed_media_object_deletions_keeps_row_on_failure() -> None:
    """Verify retry failures keep the failed row for later operator retries."""
    media_object = _media_object(status=MEDIA_OBJECT_STATUS_FAILED)
    session = _FakeDeletionSession({MediaObject: [media_object]})
    object_store = _FakeMediaObjectStore(fail=True)

    result = await retry_failed_media_object_deletions(
        session=session,  # type: ignore[arg-type]
        object_store=object_store,  # type: ignore[arg-type]
    )

    assert result == {"scanned": 1, "deleted": 0, "failures": 1}
    assert media_object.status == MEDIA_OBJECT_STATUS_FAILED
    assert media_object.deleted_at is None
    assert object_store.deleted == []
    assert session.deleted == []
    assert session.commit_count == 1
