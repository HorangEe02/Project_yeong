"""Retention cleanup helpers for backend-only media objects."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.media.object_storage import MediaObjectReference, MediaObjectStorageError, MediaObjectStore
from src.models.db.media import MediaObject

MEDIA_OBJECT_STATUS_DELETED = "deleted"
MEDIA_OBJECT_STATUS_FAILED = "failed"


async def delete_expired_media_objects(
    *,
    session: AsyncSession,
    object_store: MediaObjectStore,
    now: datetime | None = None,
    limit: int = 100,
) -> dict[str, int]:
    """Delete retained media objects past their retention deadline.

    Args:
        session: Worker-scoped async database session.
        object_store: Object storage adapter.
        now: Optional current time override.
        limit: Maximum expired objects to process.

    Returns:
        Sanitized cleanup counts.
    """
    cutoff = now or datetime.now(UTC)
    media_objects = list(
        (
            await session.scalars(
                select(MediaObject)
                .where(
                    MediaObject.retained_until <= cutoff,
                    MediaObject.deleted_at.is_(None),
                    MediaObject.status != MEDIA_OBJECT_STATUS_DELETED,
                )
                .limit(limit)
            )
        ).all()
    )
    deleted = 0
    failures = 0
    for media_object in media_objects:
        try:
            await object_store.delete_object(_reference_from_media_object(media_object))
        except MediaObjectStorageError:
            failures += 1
            media_object.status = MEDIA_OBJECT_STATUS_FAILED
            continue
        media_object.status = MEDIA_OBJECT_STATUS_DELETED
        media_object.deleted_at = cutoff
        await session.delete(media_object)
        deleted += 1
    await session.commit()
    return {
        "scanned": len(media_objects),
        "deleted": deleted,
        "failures": failures,
    }


async def retry_failed_media_object_deletions(
    *,
    session: AsyncSession,
    object_store: MediaObjectStore,
    now: datetime | None = None,
    limit: int = 100,
) -> dict[str, int]:
    """Retry deletion for media objects retained after private object failures.

    Args:
        session: Worker-scoped async database session.
        object_store: Object storage adapter.
        now: Optional current time override.
        limit: Maximum failed objects to process.

    Returns:
        Sanitized retry counts.
    """
    cutoff = now or datetime.now(UTC)
    media_objects = list(
        (
            await session.scalars(
                select(MediaObject)
                .where(
                    MediaObject.status == MEDIA_OBJECT_STATUS_FAILED,
                    MediaObject.deleted_at.is_(None),
                )
                .limit(limit)
            )
        ).all()
    )
    deleted = 0
    failures = 0
    for media_object in media_objects:
        try:
            await object_store.delete_object(_reference_from_media_object(media_object))
        except MediaObjectStorageError:
            failures += 1
            continue
        media_object.status = MEDIA_OBJECT_STATUS_DELETED
        media_object.deleted_at = cutoff
        await session.delete(media_object)
        deleted += 1
    await session.commit()
    return {
        "scanned": len(media_objects),
        "deleted": deleted,
        "failures": failures,
    }


def _reference_from_media_object(media_object: MediaObject) -> MediaObjectReference:
    """Build a private object-store reference from a media row.

    Args:
        media_object: Retained media object row.

    Returns:
        Private object-store reference.
    """
    return MediaObjectReference(
        object_storage_provider=media_object.object_storage_provider,
        object_ref=media_object.object_ref,
        object_version_id=media_object.object_version_id,
    )
