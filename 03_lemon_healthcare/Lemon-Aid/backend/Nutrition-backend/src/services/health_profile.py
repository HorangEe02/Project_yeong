"""Current-user body profile and point-in-time health metric services."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import cast

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.tx import persist_scope
from src.models.db.health import BodyProfileSnapshot, HealthDailySummary, HealthMetricSample
from src.models.schemas.health import (
    BodyProfileSnapshotCreate,
    BodyProfileSnapshotResponse,
    HealthDailySummaryListResponse,
    HealthDailySummaryResponse,
    HealthMetricSampleCreate,
    HealthMetricSampleResponse,
)
from src.security.auth import AuthenticatedUser
from src.security.subjects import build_owner_subject


class HealthProfileConflictError(ValueError):
    """Raised when an idempotent metric sample conflicts with an existing row."""


async def create_body_profile_snapshot(
    session: AsyncSession,
    user: AuthenticatedUser,
    request: BodyProfileSnapshotCreate,
) -> BodyProfileSnapshot:
    """Create a versioned body profile snapshot for the current user.

    Args:
        session: Request-scoped async database session.
        user: Authenticated owner.
        request: Validated profile snapshot payload.

    Returns:
        Persisted profile snapshot row.

    Raises:
        ValueError: If owner identity cannot be persisted safely.
    """
    owner_subject = build_owner_subject(user)
    effective_at = request.effective_at or datetime.now(UTC)
    existing_active = await _latest_active_profile(session, owner_subject)
    if existing_active is not None and existing_active.effective_at <= effective_at:
        existing_active.superseded_at = effective_at

    snapshot = BodyProfileSnapshot(
        owner_subject=owner_subject,
        effective_at=effective_at,
        source=request.source.value,
        sex=request.sex.value if request.sex is not None else None,
        birth_year=request.birth_year,
        height_cm=request.height_cm,
        weight_kg=request.weight_kg,
        waist_cm=request.waist_cm,
        pregnancy_status=(
            request.pregnancy_status.value if request.pregnancy_status is not None else None
        ),
        lactation_status=(
            request.lactation_status.value if request.lactation_status is not None else None
        ),
        activity_level=request.activity_level.value if request.activity_level is not None else None,
        consent_snapshot={"consent_type": "sensitive_health_analysis"},
    )
    async with persist_scope(session):
        session.add(snapshot)
        await session.flush()
        await session.refresh(snapshot)
    return snapshot


async def get_latest_body_profile_snapshot(
    session: AsyncSession,
    user: AuthenticatedUser,
) -> BodyProfileSnapshot | None:
    """Load the latest current-user body profile snapshot.

    Args:
        session: Request-scoped async database session.
        user: Authenticated owner.

    Returns:
        Latest profile snapshot or None.

    Raises:
        ValueError: If owner identity cannot be persisted safely.
    """
    return await _latest_active_profile(session, build_owner_subject(user))


async def create_health_metric_sample(
    session: AsyncSession,
    user: AuthenticatedUser,
    request: HealthMetricSampleCreate,
) -> HealthMetricSample:
    """Create or reuse one current-user point-in-time health metric sample.

    Args:
        session: Request-scoped async database session.
        user: Authenticated owner.
        request: Validated metric sample payload.

    Returns:
        Persisted metric sample row.

    Raises:
        HealthProfileConflictError: If source_record_hash is reused for a different value.
        ValueError: If owner identity cannot be persisted safely.
    """
    owner_subject = build_owner_subject(user)
    existing = await _find_metric_by_source_hash(session, owner_subject, request)
    if existing is not None:
        if not _same_metric(existing, request):
            raise HealthProfileConflictError(
                "source_record_hash was already used for a different health metric."
            )
        return existing

    sample = HealthMetricSample(
        owner_subject=owner_subject,
        metric_type=request.metric_type.value,
        measured_at=request.measured_at,
        value_numeric=request.value_numeric,
        unit=request.unit.value,
        source_platform=request.source_platform.value,
        source_record_hash=(
            request.source_record_hash.lower() if request.source_record_hash else None
        ),
        quality_flags=request.quality_flags,
    )
    async with persist_scope(session):
        session.add(sample)
        await session.flush()
        await session.refresh(sample)
    return sample


async def list_health_daily_summaries(
    session: AsyncSession,
    user: AuthenticatedUser,
    *,
    start_date: date | None,
    end_date: date | None,
    limit: int,
) -> list[HealthDailySummary]:
    """List bounded current-user daily health summaries.

    Args:
        session: Request-scoped async database session.
        user: Authenticated owner.
        start_date: Optional inclusive start date.
        end_date: Optional inclusive end date.
        limit: Maximum rows to return.

    Returns:
        Daily summaries ordered newest first.

    Raises:
        ValueError: If owner identity or date bounds are invalid.
    """
    if start_date is not None and end_date is not None and start_date > end_date:
        raise ValueError("start_date must be on or before end_date.")
    bounded_end = end_date or datetime.now(UTC).date()
    bounded_start = start_date or bounded_end - timedelta(days=30)
    owner_subject = build_owner_subject(user)
    statement = (
        select(HealthDailySummary)
        .where(
            HealthDailySummary.owner_subject == owner_subject,
            HealthDailySummary.measured_date >= bounded_start,
            HealthDailySummary.measured_date <= bounded_end,
        )
        .order_by(desc(HealthDailySummary.measured_date), desc(HealthDailySummary.created_at))
        .limit(limit)
    )
    result = await session.scalars(statement)
    return list(result.all())


def body_profile_to_response(snapshot: BodyProfileSnapshot) -> BodyProfileSnapshotResponse:
    """Convert a profile snapshot ORM row into an API response.

    Args:
        snapshot: Persisted profile snapshot.

    Returns:
        API response without owner identifiers or consent snapshots.
    """
    return BodyProfileSnapshotResponse.model_validate(snapshot)


def metric_sample_to_response(sample: HealthMetricSample) -> HealthMetricSampleResponse:
    """Convert a metric sample ORM row into an API response.

    Args:
        sample: Persisted metric sample.

    Returns:
        API response without owner identifiers or source hashes.
    """
    return HealthMetricSampleResponse.model_validate(sample)


def daily_summaries_to_response(
    summaries: list[HealthDailySummary],
) -> HealthDailySummaryListResponse:
    """Convert daily summary ORM rows into an API response.

    Args:
        summaries: Current-user daily summary rows.

    Returns:
        API response without owner identifiers or source record hashes.
    """
    return HealthDailySummaryListResponse(
        summaries=[
            HealthDailySummaryResponse(
                measured_date=summary.measured_date,
                source_platform=summary.source_platform,
                steps=summary.steps,
                weight_kg=summary.weight_kg,
                resting_heart_rate_bpm=summary.resting_heart_rate_bpm,
                active_energy_kcal=summary.active_energy_kcal,
                synced_at=summary.synced_at,
            )
            for summary in summaries
        ]
    )


async def _latest_active_profile(
    session: AsyncSession,
    owner_subject: str,
) -> BodyProfileSnapshot | None:
    """Load the latest non-superseded profile for one owner.

    Args:
        session: Request-scoped async database session.
        owner_subject: Issuer-qualified owner subject.

    Returns:
        Latest profile snapshot or None.
    """
    statement = (
        select(BodyProfileSnapshot)
        .where(
            BodyProfileSnapshot.owner_subject == owner_subject,
            BodyProfileSnapshot.superseded_at.is_(None),
        )
        .order_by(desc(BodyProfileSnapshot.effective_at), desc(BodyProfileSnapshot.created_at))
        .limit(1)
    )
    return cast(BodyProfileSnapshot | None, await session.scalar(statement))


async def _find_metric_by_source_hash(
    session: AsyncSession,
    owner_subject: str,
    request: HealthMetricSampleCreate,
) -> HealthMetricSample | None:
    """Find an existing metric sample by source hash when provided.

    Args:
        session: Request-scoped async database session.
        owner_subject: Issuer-qualified owner subject.
        request: Metric sample create request.

    Returns:
        Existing metric sample or None.
    """
    if request.source_record_hash is None:
        return None
    return cast(
        HealthMetricSample | None,
        await session.scalar(
            select(HealthMetricSample).where(
                HealthMetricSample.owner_subject == owner_subject,
                HealthMetricSample.source_platform == request.source_platform.value,
                HealthMetricSample.source_record_hash == request.source_record_hash.lower(),
            )
        ),
    )


def _same_metric(existing: HealthMetricSample, request: HealthMetricSampleCreate) -> bool:
    """Check whether an existing idempotent metric row matches the request.

    Args:
        existing: Existing metric sample.
        request: New create request.

    Returns:
        True when the existing row can be reused.
    """
    return (
        existing.metric_type == request.metric_type.value
        and existing.measured_at == request.measured_at
        and Decimal(existing.value_numeric) == request.value_numeric
        and existing.unit == request.unit.value
        and existing.quality_flags == request.quality_flags
    )
