"""Current-user HealthKit and Health Connect aggregate sync services."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.tx import persist_scope
from src.models.db.health import HealthDailySummary, HealthSyncBatch
from src.models.schemas.health import HealthDailyAggregate, HealthSyncRequest, HealthSyncResponse
from src.security.auth import AuthenticatedUser
from src.security.subjects import build_owner_subject


@dataclass(frozen=True)
class HealthSyncResult:
    """Persisted health sync result.

    Attributes:
        batch: Persisted or reused sync batch row.
        accepted_count: Number of accepted daily aggregate records.
        rejected_count: Number of rejected aggregate records.
        synced_at: Server-side sync timestamp.
        reused_existing: Whether the response came from an idempotent retry.
    """

    batch: HealthSyncBatch
    accepted_count: int
    rejected_count: int
    synced_at: datetime
    reused_existing: bool = False


class HealthSyncError(ValueError):
    """Base error for health sync failures."""


class HealthSyncConflictError(HealthSyncError):
    """Raised when a client batch id is reused for a different payload."""


async def sync_health_daily_aggregates(
    session: AsyncSession,
    user: AuthenticatedUser,
    request: HealthSyncRequest,
) -> HealthSyncResult:
    """Persist current-user daily health aggregates.

    Args:
        session: Request-scoped async database session.
        user: Authenticated owner.
        request: Validated health sync request.

    Returns:
        Persisted sync result. If `client_batch_id` is an exact retry, the existing batch is
        returned without writing duplicate daily summary rows.

    Raises:
        HealthSyncConflictError: If a client batch id is reused with a different payload.
        ValueError: If owner identity cannot be persisted safely.
    """
    owner_subject = build_owner_subject(user)
    request_fingerprint = _request_fingerprint(request)
    existing_batch = await _find_existing_batch(session, owner_subject, request.client_batch_id)
    if existing_batch is not None:
        if existing_batch.input_snapshot.get("request_fingerprint") != request_fingerprint:
            raise HealthSyncConflictError("client_batch_id was already used for different records.")
        return HealthSyncResult(
            batch=existing_batch,
            accepted_count=existing_batch.accepted_count,
            rejected_count=existing_batch.rejected_count,
            synced_at=existing_batch.synced_at,
            reused_existing=True,
        )

    synced_at = datetime.now(UTC)
    accepted_count = len(request.records)
    rejected_count = 0
    batch = HealthSyncBatch(
        owner_subject=owner_subject,
        client_batch_id=request.client_batch_id,
        source_platform=_batch_source_platform(request.records),
        record_count=len(request.records),
        accepted_count=accepted_count,
        rejected_count=rejected_count,
        input_snapshot=_build_input_snapshot(request, request_fingerprint),
        result_snapshot={
            "accepted_count": accepted_count,
            "rejected_count": rejected_count,
            "upserted_count": accepted_count,
            "skipped_count": rejected_count,
        },
        synced_at=synced_at,
    )
    async with persist_scope(session):
        session.add(batch)
        await session.flush()
        for record in request.records:
            await _upsert_daily_summary(session, owner_subject, record, synced_at)
        await session.flush()
        await session.refresh(batch)
    return HealthSyncResult(
        batch=batch,
        accepted_count=accepted_count,
        rejected_count=rejected_count,
        synced_at=batch.synced_at,
    )


def health_sync_result_to_response(result: HealthSyncResult) -> HealthSyncResponse:
    """Convert a service result into the public API response.

    Args:
        result: Persisted sync result.

    Returns:
        API response model without owner identifiers or raw snapshots.
    """
    return HealthSyncResponse(
        batch_id=result.batch.id,
        accepted_count=result.accepted_count,
        rejected_count=result.rejected_count,
        synced_at=result.synced_at,
    )


def health_sync_result_audit_metadata(result: HealthSyncResult) -> dict[str, object]:
    """Build audit metadata that excludes raw metric values.

    Args:
        result: Persisted sync result.

    Returns:
        Sanitized audit metadata.
    """
    input_snapshot = result.batch.input_snapshot or {}
    return {
        "record_count": result.batch.record_count,
        "accepted_count": result.accepted_count,
        "rejected_count": result.rejected_count,
        "date_min": input_snapshot.get("date_min"),
        "date_max": input_snapshot.get("date_max"),
        "source_platform_counts": input_snapshot.get("source_platform_counts", {}),
        "metric_presence_counts": input_snapshot.get("metric_presence_counts", {}),
        "client_batch_id_present": result.batch.client_batch_id is not None,
        "reused_existing": result.reused_existing,
    }


async def _find_existing_batch(
    session: AsyncSession,
    owner_subject: str,
    client_batch_id: str | None,
) -> HealthSyncBatch | None:
    """Find an existing sync batch for idempotent retry handling.

    Args:
        session: Request-scoped async database session.
        owner_subject: Issuer-qualified authenticated subject.
        client_batch_id: Optional client idempotency key.

    Returns:
        Existing sync batch or None.
    """
    if client_batch_id is None:
        return None
    return cast(
        HealthSyncBatch | None,
        await session.scalar(
            select(HealthSyncBatch).where(
                HealthSyncBatch.owner_subject == owner_subject,
                HealthSyncBatch.client_batch_id == client_batch_id,
            )
        ),
    )


async def _upsert_daily_summary(
    session: AsyncSession,
    owner_subject: str,
    record: HealthDailyAggregate,
    synced_at: datetime,
) -> HealthDailySummary:
    """Insert or replace one owner/date/platform health summary.

    Args:
        session: Request-scoped async database session.
        owner_subject: Issuer-qualified authenticated subject.
        record: Validated daily aggregate.
        synced_at: Server-side sync timestamp.

    Returns:
        Inserted or updated daily summary row.
    """
    existing = await session.scalar(
        select(HealthDailySummary).where(
            HealthDailySummary.owner_subject == owner_subject,
            HealthDailySummary.measured_date == record.measured_date,
            HealthDailySummary.source_platform == record.source_platform.value,
        )
    )
    if existing is None:
        existing = HealthDailySummary(
            owner_subject=owner_subject,
            measured_date=record.measured_date,
            source_platform=record.source_platform.value,
        )
        session.add(existing)

    existing.steps = record.steps
    existing.weight_kg = _decimal_or_none(record.weight_kg)
    existing.resting_heart_rate_bpm = record.resting_heart_rate_bpm
    existing.active_energy_kcal = _decimal_or_none(record.active_energy_kcal)
    existing.source_record_hash = (
        record.source_record_hash.lower() if record.source_record_hash else None
    )
    existing.synced_at = synced_at
    return existing


def _request_fingerprint(request: HealthSyncRequest) -> str:
    """Build a deterministic fingerprint for idempotency checks.

    Args:
        request: Validated health sync request.

    Returns:
        Hex-encoded SHA-256 digest of the canonical request payload.
    """
    payload = {
        "records": [
            record.model_dump(mode="json", exclude_none=True)
            for record in sorted(
                request.records,
                key=lambda item: (item.measured_date.isoformat(), item.source_platform.value),
            )
        ]
    }
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _build_input_snapshot(
    request: HealthSyncRequest,
    request_fingerprint: str,
) -> dict[str, object]:
    """Build a sanitized sync request snapshot without raw health metric values.

    Args:
        request: Validated health sync request.
        request_fingerprint: Deterministic idempotency fingerprint.

    Returns:
        Sanitized request metadata.
    """
    sorted_dates = sorted(record.measured_date for record in request.records)
    return {
        "date_min": sorted_dates[0].isoformat(),
        "date_max": sorted_dates[-1].isoformat(),
        "record_count": len(request.records),
        "source_platform_counts": _source_platform_counts(request.records),
        "metric_presence_counts": _metric_presence_counts(request.records),
        "client_batch_id_present": request.client_batch_id is not None,
        "request_fingerprint": request_fingerprint,
    }


def _source_platform_counts(records: list[HealthDailyAggregate]) -> dict[str, int]:
    """Count sync records by source platform.

    Args:
        records: Daily aggregate records.

    Returns:
        Source platform value to record count mapping.
    """
    counts: dict[str, int] = {}
    for record in records:
        counts[record.source_platform.value] = counts.get(record.source_platform.value, 0) + 1
    return counts


def _metric_presence_counts(records: list[HealthDailyAggregate]) -> dict[str, int]:
    """Count non-null metric fields without exposing their values.

    Args:
        records: Daily aggregate records.

    Returns:
        Metric name to non-null count mapping.
    """
    return {
        "steps": sum(1 for record in records if record.steps is not None),
        "weight_kg": sum(1 for record in records if record.weight_kg is not None),
        "resting_heart_rate_bpm": sum(
            1 for record in records if record.resting_heart_rate_bpm is not None
        ),
        "active_energy_kcal": sum(1 for record in records if record.active_energy_kcal is not None),
    }


def _batch_source_platform(records: list[HealthDailyAggregate]) -> str:
    """Return a batch-level source platform.

    Args:
        records: Daily aggregate records.

    Returns:
        Single source platform value, or `mixed` when a batch contains multiple sources.
    """
    platforms = {record.source_platform.value for record in records}
    if len(platforms) == 1:
        return next(iter(platforms))
    return "mixed"


def _decimal_or_none(value: float | None) -> Decimal | None:
    """Convert an optional float to Decimal for database storage.

    Args:
        value: Optional numeric metric value.

    Returns:
        Decimal value or None.
    """
    if value is None:
        return None
    return Decimal(str(value))
