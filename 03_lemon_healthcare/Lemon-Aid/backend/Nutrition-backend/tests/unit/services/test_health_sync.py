"""Health sync service tests."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Self, cast
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.tx import REQUEST_MANAGED_TX
from src.models.db.health import HealthDailySummary, HealthSyncBatch
from src.models.schemas.health import HealthSyncRequest
from src.security.auth import AuthenticatedUser
from src.services.health_sync import (
    HealthSyncConflictError,
    _request_fingerprint,
    sync_health_daily_aggregates,
)


class _TransactionContext:
    """Async context manager used by fake sessions."""

    async def __aenter__(self) -> Self:
        """Enter the fake transaction.

        Returns:
            Context manager instance.
        """
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        """Exit the fake transaction.

        Args:
            *_exc_info: Exception details ignored by the fake context.

        Returns:
            None.
        """


class _FakeHealthSyncSession:
    """Fake async session for health sync service tests."""

    def __init__(
        self,
        scalar_results: list[object | None] | None = None,
        *,
        request_managed: bool = False,
    ) -> None:
        self.scalar_results = list(scalar_results or [])
        self.added: list[object] = []
        self.commit_count = 0
        self.refreshed: object | None = None
        self.flushed = False
        # A real AsyncSession always exposes ``.info``; persist_scope reads it.
        self.info: dict[str, object] = {REQUEST_MANAGED_TX: True} if request_managed else {}

    @property
    def committed(self) -> bool:
        """Whether at least one commit happened (kept for existing assertions)."""
        return self.commit_count > 0

    def begin(self) -> _TransactionContext:
        """Return a fake transaction context.

        Returns:
            Fake transaction context.
        """
        return _TransactionContext()

    async def scalar(self, _statement: object) -> object | None:
        """Return the next configured scalar row.

        Args:
            _statement: SQLAlchemy select statement.

        Returns:
            Configured scalar row or None.
        """
        return self.scalar_results.pop(0) if self.scalar_results else None

    def add(self, record: object) -> None:
        """Capture a persisted ORM object.

        Args:
            record: ORM object passed to the session.

        Returns:
            None.
        """
        self.added.append(record)

    async def flush(self) -> None:
        """Assign fake identifiers before response conversion.

        Returns:
            None.
        """
        self.flushed = True
        for record in self.added:
            if isinstance(record, HealthSyncBatch) and cast(object | None, record.id) is None:
                record.id = uuid4()

    async def commit(self) -> None:
        """Count fake commits (own-mode must commit exactly once).

        Returns:
            None.
        """
        self.commit_count += 1

    async def refresh(self, record: object) -> None:
        """Populate server-generated timestamps.

        Args:
            record: ORM object being refreshed.

        Returns:
            None.
        """
        if isinstance(record, HealthSyncBatch):
            if cast(object | None, record.id) is None:
                record.id = uuid4()
            if cast(object | None, record.created_at) is None:
                record.created_at = datetime.now(UTC)
            if cast(object | None, record.updated_at) is None:
                record.updated_at = datetime.now(UTC)
        self.refreshed = record


def _user() -> AuthenticatedUser:
    """Return an authenticated user fixture.

    Returns:
        Authenticated user model.
    """
    return AuthenticatedUser(
        subject="user_123",
        issuer="https://auth.example.com/",
        claims={"sub": "user_123"},
    )


def _request(client_batch_id: str | None = "batch-1") -> HealthSyncRequest:
    """Return a valid health sync request.

    Args:
        client_batch_id: Optional idempotency key.

    Returns:
        Health sync request model.
    """
    return HealthSyncRequest.model_validate(
        {
            "client_batch_id": client_batch_id,
            "records": [
                {
                    "measured_date": "2026-05-11",
                    "source_platform": "ios_healthkit",
                    "steps": 7000,
                    "active_energy_kcal": 420,
                },
                {
                    "measured_date": "2026-05-12",
                    "source_platform": "ios_healthkit",
                    "steps": 7200,
                    "weight_kg": 68.4,
                    "resting_heart_rate_bpm": 68,
                    "source_record_hash": "a" * 64,
                },
            ],
        }
    )


def _existing_batch(request: HealthSyncRequest) -> HealthSyncBatch:
    """Return an existing batch row matching a request.

    Args:
        request: Request whose fingerprint should match the batch.

    Returns:
        Existing sync batch row.
    """
    now = datetime.now(UTC)
    return HealthSyncBatch(
        id=uuid4(),
        owner_subject="https://auth.example.com/::user_123",
        client_batch_id=request.client_batch_id,
        source_platform="ios_healthkit",
        record_count=len(request.records),
        accepted_count=len(request.records),
        rejected_count=0,
        input_snapshot={"request_fingerprint": _request_fingerprint(request)},
        result_snapshot={"accepted_count": len(request.records), "rejected_count": 0},
        synced_at=now,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_sync_health_daily_aggregates_inserts_batch_and_summaries() -> None:
    """Verify valid daily aggregates are persisted without raw metric snapshots."""
    session = _FakeHealthSyncSession(scalar_results=[None, None, None])

    result = await sync_health_daily_aggregates(cast(AsyncSession, session), _user(), _request())

    batch = result.batch
    summaries = [record for record in session.added if isinstance(record, HealthDailySummary)]
    assert session.flushed is True
    assert session.committed is True
    assert batch in session.added
    assert len(summaries) == 2
    assert result.accepted_count == 2
    assert result.rejected_count == 0
    assert batch.owner_subject == "https://auth.example.com/::user_123"
    assert batch.source_platform == "ios_healthkit"
    assert batch.input_snapshot["date_min"] == "2026-05-11"
    assert batch.input_snapshot["date_max"] == "2026-05-12"
    assert batch.input_snapshot["metric_presence_counts"] == {
        "steps": 2,
        "weight_kg": 1,
        "resting_heart_rate_bpm": 1,
        "active_energy_kcal": 1,
    }
    assert "steps" not in batch.input_snapshot
    assert len(cast(str, batch.input_snapshot["request_fingerprint"])) == 64
    assert summaries[1].source_record_hash == "a" * 64


@pytest.mark.asyncio
async def test_sync_health_daily_aggregates_reuses_matching_client_batch() -> None:
    """Verify an exact idempotent retry returns the existing batch."""
    request = _request()
    existing_batch = _existing_batch(request)
    session = _FakeHealthSyncSession(scalar_results=[existing_batch])

    result = await sync_health_daily_aggregates(cast(AsyncSession, session), _user(), request)

    assert result.batch is existing_batch
    assert result.reused_existing is True
    assert session.added == []
    assert session.committed is False


@pytest.mark.asyncio
async def test_sync_health_daily_aggregates_rejects_conflicting_client_batch() -> None:
    """Verify reused client batch ids cannot carry different payloads."""
    request = _request()
    existing_batch = _existing_batch(request)
    existing_batch.input_snapshot["request_fingerprint"] = "0" * 64
    session = _FakeHealthSyncSession(scalar_results=[existing_batch])

    with pytest.raises(HealthSyncConflictError):
        await sync_health_daily_aggregates(cast(AsyncSession, session), _user(), request)

    assert session.added == []
    assert session.committed is False


@pytest.mark.asyncio
async def test_sync_health_daily_aggregates_updates_existing_daily_summary() -> None:
    """Verify date/platform collisions replace the stored daily aggregate."""
    existing_summary = HealthDailySummary(
        id=uuid4(),
        owner_subject="https://auth.example.com/::user_123",
        measured_date=date(2026, 5, 11),
        source_platform="ios_healthkit",
        steps=3000,
        weight_kg=Decimal("70.00"),
        synced_at=datetime.now(UTC),
    )
    request = HealthSyncRequest.model_validate(
        {
            "client_batch_id": "batch-upsert",
            "records": [
                {
                    "measured_date": "2026-05-11",
                    "source_platform": "ios_healthkit",
                    "steps": 8100,
                    "weight_kg": 69.5,
                }
            ],
        }
    )
    session = _FakeHealthSyncSession(scalar_results=[None, existing_summary])

    await sync_health_daily_aggregates(cast(AsyncSession, session), _user(), request)

    summaries = [record for record in session.added if isinstance(record, HealthDailySummary)]
    assert summaries == []
    assert existing_summary.steps == 8100
    assert existing_summary.weight_kg == Decimal("69.5")
    assert session.committed is True


# --- persist_scope transaction-ownership contract (ambient-tx Step 4) ----------
#
# Under a request-managed (RLS) session the write path must PARTICIPATE (flush
# only, never commit) so the transaction-local owner GUCs survive to the
# dependency's commit-on-exit; under a legacy session it must OWN the
# transaction (commit exactly once), reproducing today's add+commit behavior.


@pytest.mark.asyncio
async def test_sync_health_participates_without_commit_when_request_managed() -> None:
    session = _FakeHealthSyncSession(scalar_results=[None, None, None], request_managed=True)
    result = await sync_health_daily_aggregates(cast(AsyncSession, session), _user(), _request())
    assert session.committed is False  # GUCs must survive to the dependency commit
    assert session.flushed is True
    assert result.batch.id is not None


@pytest.mark.asyncio
async def test_sync_health_commits_once_in_legacy_own_mode() -> None:
    session = _FakeHealthSyncSession(scalar_results=[None, None, None], request_managed=False)
    await sync_health_daily_aggregates(cast(AsyncSession, session), _user(), _request())
    assert session.commit_count == 1  # exactly once (re-entrancy/double-commit guard)
