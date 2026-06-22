"""Health profile and metric sample service tests."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.tx import REQUEST_MANAGED_TX
from src.models.db.health import BodyProfileSnapshot, HealthDailySummary, HealthMetricSample
from src.models.schemas.health import (
    BodyProfileSnapshotCreate,
    HealthMetricSampleCreate,
)
from src.security.auth import AuthenticatedUser
from src.services.health_profile import (
    HealthProfileConflictError,
    body_profile_to_response,
    create_body_profile_snapshot,
    create_health_metric_sample,
    daily_summaries_to_response,
    metric_sample_to_response,
)


class _FakeScalarResult:
    """Fake SQLAlchemy scalar result for service tests."""

    def __init__(self, rows: list[object]) -> None:
        """Initialize with rows.

        Args:
            rows: Rows returned by `all`.
        """
        self._rows = rows

    def all(self) -> list[object]:
        """Return rows.

        Returns:
            Stored fake rows.
        """
        return self._rows


class _FakeSession:
    """Fake async session for health profile service tests."""

    def __init__(
        self,
        *,
        scalar_rows: list[object | None] | None = None,
        request_managed: bool = False,
    ) -> None:
        """Initialize fake session.

        Args:
            scalar_rows: Ordered values returned by `scalar`.
            request_managed: When True, stamp the marker so ``persist_scope``
                participates (flush only) instead of owning the transaction.
        """
        self.scalar_rows = list(scalar_rows or [])
        self.added: list[object] = []
        self.commits = 0
        self.refreshed: list[object] = []
        # A real AsyncSession always exposes ``.info``; persist_scope reads it.
        self.info: dict[str, object] = {REQUEST_MANAGED_TX: True} if request_managed else {}

    async def scalar(self, _statement: object) -> object | None:
        """Return the next scalar row.

        Args:
            _statement: SQLAlchemy statement ignored by the fake.

        Returns:
            Next configured row or None.
        """
        if not self.scalar_rows:
            return None
        return self.scalar_rows.pop(0)

    async def scalars(self, _statement: object) -> _FakeScalarResult:
        """Return empty scalar result.

        Args:
            _statement: SQLAlchemy statement ignored by the fake.

        Returns:
            Empty fake scalar result.
        """
        return _FakeScalarResult([])

    def add(self, record: object) -> None:
        """Capture added records.

        Args:
            record: ORM row.
        """
        self.added.append(record)

    async def flush(self) -> None:
        """No-op flush."""

    async def commit(self) -> None:
        """Capture commit count."""
        self.commits += 1

    async def refresh(self, record: object) -> None:
        """Populate minimal generated fields.

        Args:
            record: ORM row to refresh.
        """
        if getattr(record, "id", None) is None:
            record.id = uuid4()
        if getattr(record, "created_at", None) is None:
            record.created_at = datetime.now(UTC)
        self.refreshed.append(record)


def _user() -> AuthenticatedUser:
    """Return an authenticated user fixture.

    Returns:
        Authenticated user.
    """
    return AuthenticatedUser(
        subject="user-1",
        issuer="https://auth.example.com/",
        claims={"sub": "user-1"},
    )


@pytest.mark.asyncio
async def test_create_body_profile_snapshot_supersedes_existing_without_leaking_owner() -> None:
    """Verify profile creation stores bounded fields and response hides owner data."""
    old = BodyProfileSnapshot(
        id=uuid4(),
        owner_subject="https://auth.example.com/::user-1",
        effective_at=datetime(2026, 5, 1, tzinfo=UTC),
        source="manual",
        weight_kg=Decimal("70.0"),
        consent_snapshot={"consent_type": "sensitive_health_analysis"},
    )
    fake_session = _FakeSession(scalar_rows=[old])
    request = BodyProfileSnapshotCreate(
        effective_at=datetime(2026, 5, 27, tzinfo=UTC),
        source="manual",
        height_cm=Decimal("172.5"),
        weight_kg=Decimal("68.4"),
    )

    snapshot = await create_body_profile_snapshot(
        cast(AsyncSession, fake_session),
        _user(),
        request,
    )
    response = body_profile_to_response(snapshot)

    assert old.superseded_at == request.effective_at
    assert snapshot.owner_subject == "https://auth.example.com/::user-1"
    assert snapshot.consent_snapshot == {"consent_type": "sensitive_health_analysis"}
    serialized = response.model_dump(mode="json")
    assert "owner_subject" not in serialized
    assert "consent_snapshot" not in serialized
    assert response.height_cm == Decimal("172.5")


@pytest.mark.asyncio
async def test_create_health_metric_sample_reuses_matching_source_hash() -> None:
    """Verify source hashes are used only for idempotency and not returned."""
    now = datetime(2026, 5, 27, 9, 30, tzinfo=UTC)
    existing = HealthMetricSample(
        id=uuid4(),
        owner_subject="https://auth.example.com/::user-1",
        metric_type="weight_kg",
        measured_at=now,
        value_numeric=Decimal("68.4000"),
        unit="kg",
        source_platform="manual",
        source_record_hash="a" * 64,
        quality_flags=["manual_entry"],
    )
    fake_session = _FakeSession(scalar_rows=[existing])
    request = HealthMetricSampleCreate(
        metric_type="weight_kg",
        measured_at=now,
        value_numeric=Decimal("68.4000"),
        unit="kg",
        source_platform="manual",
        source_record_hash="a" * 64,
        quality_flags=["manual_entry"],
    )

    sample = await create_health_metric_sample(cast(AsyncSession, fake_session), _user(), request)
    response = metric_sample_to_response(sample)

    assert sample is existing
    assert fake_session.added == []
    serialized = response.model_dump(mode="json")
    assert "owner_subject" not in serialized
    assert "source_record_hash" not in serialized


@pytest.mark.asyncio
async def test_create_health_metric_sample_rejects_source_hash_conflict() -> None:
    """Verify source_record_hash cannot be reused for different metric values."""
    now = datetime(2026, 5, 27, 9, 30, tzinfo=UTC)
    existing = HealthMetricSample(
        id=uuid4(),
        owner_subject="https://auth.example.com/::user-1",
        metric_type="weight_kg",
        measured_at=now,
        value_numeric=Decimal("68.4000"),
        unit="kg",
        source_platform="manual",
        source_record_hash="a" * 64,
        quality_flags=[],
    )
    fake_session = _FakeSession(scalar_rows=[existing])
    request = HealthMetricSampleCreate(
        metric_type="weight_kg",
        measured_at=now,
        value_numeric=Decimal("69.1000"),
        unit="kg",
        source_platform="manual",
        source_record_hash="a" * 64,
    )

    with pytest.raises(HealthProfileConflictError):
        await create_health_metric_sample(cast(AsyncSession, fake_session), _user(), request)


def test_daily_summaries_response_hides_source_hash() -> None:
    """Verify daily summary responses omit owner and source hashes."""
    summary = HealthDailySummary(
        id=uuid4(),
        owner_subject="https://auth.example.com/::user-1",
        measured_date=date(2026, 5, 27),
        source_platform="manual",
        steps=7000,
        source_record_hash="b" * 64,
        synced_at=datetime(2026, 5, 27, tzinfo=UTC),
    )

    response = daily_summaries_to_response([summary])

    serialized = response.model_dump(mode="json")
    assert "owner_subject" not in serialized
    assert "source_record_hash" not in serialized
    assert serialized["summaries"][0]["steps"] == 7000


# --- persist_scope transaction-ownership contract (ambient-tx Step 4) ----------
#
# Under a request-managed (RLS) session the write services must PARTICIPATE
# (flush only, never commit) so the transaction-local owner GUCs survive to the
# dependency's commit-on-exit; under a legacy session they must OWN the
# transaction (commit exactly once), reproducing today's add+commit behavior.


def _profile_create_request() -> BodyProfileSnapshotCreate:
    """Return a minimal body profile create request."""
    return BodyProfileSnapshotCreate(
        effective_at=datetime(2026, 5, 27, tzinfo=UTC),
        source="manual",
        height_cm=Decimal("172.5"),
        weight_kg=Decimal("68.4"),
    )


def _metric_create_request() -> HealthMetricSampleCreate:
    """Return a metric sample create request without an idempotency hash."""
    return HealthMetricSampleCreate(
        metric_type="weight_kg",
        measured_at=datetime(2026, 5, 27, 9, 30, tzinfo=UTC),
        value_numeric=Decimal("68.4000"),
        unit="kg",
        source_platform="manual",
    )


@pytest.mark.asyncio
async def test_create_body_profile_participates_without_commit_when_request_managed() -> None:
    session = _FakeSession(scalar_rows=[None], request_managed=True)
    snapshot = await create_body_profile_snapshot(
        cast(AsyncSession, session), _user(), _profile_create_request()
    )
    assert session.commits == 0  # GUCs must survive to the dependency commit
    assert snapshot.id is not None


@pytest.mark.asyncio
async def test_create_body_profile_commits_once_in_legacy_own_mode() -> None:
    session = _FakeSession(scalar_rows=[None], request_managed=False)
    await create_body_profile_snapshot(
        cast(AsyncSession, session), _user(), _profile_create_request()
    )
    assert session.commits == 1


@pytest.mark.asyncio
async def test_create_metric_sample_participates_without_commit_when_request_managed() -> None:
    session = _FakeSession(scalar_rows=[None], request_managed=True)
    sample = await create_health_metric_sample(
        cast(AsyncSession, session), _user(), _metric_create_request()
    )
    assert session.commits == 0
    assert sample.id is not None


@pytest.mark.asyncio
async def test_create_metric_sample_commits_once_in_legacy_own_mode() -> None:
    session = _FakeSession(scalar_rows=[None], request_managed=False)
    await create_health_metric_sample(
        cast(AsyncSession, session), _user(), _metric_create_request()
    )
    assert session.commits == 1
