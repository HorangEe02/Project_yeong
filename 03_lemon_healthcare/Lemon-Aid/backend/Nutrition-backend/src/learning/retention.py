"""Retention helpers for consent-gated image learning records."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from src.config import Settings


def should_retain_learning_image(settings: Settings) -> bool:
    """Return whether images may be retained for learning reuse.

    Args:
        settings: Runtime settings containing image retention policy.

    Returns:
        True only when the learning pipeline is enabled and retention days are positive.
    """
    return settings.enable_image_learning_pipeline and settings.image_retention_days > 0


def image_retention_deadline(settings: Settings, *, now: datetime | None = None) -> datetime | None:
    """Calculate the deletion deadline for retained learning images.

    Args:
        settings: Runtime settings containing image retention policy.
        now: Optional current time override for tests.

    Returns:
        Retention deadline, or None when images must not be retained.
    """
    if not should_retain_learning_image(settings):
        return None
    base_time = now or datetime.now(UTC)
    return base_time + timedelta(days=settings.image_retention_days)
