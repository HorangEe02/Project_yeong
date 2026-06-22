"""Persisted analysis result service tests."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any, Self, cast
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.tx import REQUEST_MANAGED_TX
from src.models.db.analysis_result import AnalysisResult
from src.models.schemas.algorithm import ActivityScoreRequest
from src.models.schemas.analysis_result import AnalysisType
from src.models.schemas.user import UserProfile
from src.security.auth import AuthenticatedUser
from src.services.analysis_results import (
    analysis_result_to_response,
    analysis_result_to_summary,
    build_owner_subject,
    get_analysis_result,
    store_activity_score_result,
)


class _TransactionContext:
    """Async context manager used by the fake session transaction."""

    async def __aenter__(self) -> Self:
        """Enter the fake transaction.

        Returns:
            Context manager instance.
        """
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        """Exit the fake transaction.

        Args:
            *_exc_info: Exception information ignored by the fake context.

        Returns:
            None.
        """


class _FakeWriteSession:
    """Fake async session for service write tests."""

    def __init__(self, *, request_managed: bool = False) -> None:
        self.added: AnalysisResult | None = None
        self.commits = 0
        # A real AsyncSession always exposes ``.info``; persist_scope reads it.
        self.info: dict[str, object] = {REQUEST_MANAGED_TX: True} if request_managed else {}

    def begin(self) -> _TransactionContext:
        """Return a fake transaction context.

        Returns:
            Fake async transaction context.
        """
        return _TransactionContext()

    async def flush(self) -> None:
        """No-op flush (persist_scope flushes pending writes)."""

    async def commit(self) -> None:
        """Count commits (own-mode must commit exactly once)."""
        self.commits += 1

    async def rollback(self) -> None:
        """No-op rollback (own-mode rolls back on exception)."""

    def add(self, record: object) -> None:
        """Capture the ORM record being added.

        Args:
            record: ORM object passed by the service.

        Returns:
            None.
        """
        self.added = cast(AnalysisResult, record)

    async def refresh(self, record: object) -> None:
        """Populate server-generated fields after fake persistence.

        Args:
            record: ORM object to refresh.

        Returns:
            None.
        """
        analysis_result = cast(AnalysisResult, record)
        analysis_result.id = uuid4()
        analysis_result.created_at = datetime.now(UTC)
        analysis_result.updated_at = datetime.now(UTC)


class _FakeReadSession:
    """Fake async session that records the select statement."""

    def __init__(self) -> None:
        self.statement: Any | None = None

    async def scalar(self, statement: Any) -> None:
        """Capture a scalar select statement.

        Args:
            statement: SQLAlchemy select statement.

        Returns:
            None to simulate a not-found row.
        """
        self.statement = statement


async def _fake_session_dependency() -> AsyncIterator[object]:
    """Yield a fake session object for route tests.

    Yields:
        Fake session object.
    """
    yield object()


def _user(
    subject: str = "user_123", issuer: str = "https://auth.example.com/"
) -> AuthenticatedUser:
    """Return an authenticated user fixture.

    Args:
        subject: JWT subject.
        issuer: JWT issuer.

    Returns:
        Authenticated user model.
    """
    return AuthenticatedUser(subject=subject, issuer=issuer, claims={"sub": subject, "iss": issuer})


def _activity_request() -> ActivityScoreRequest:
    """Return an activity score request fixture.

    Returns:
        Activity score request.
    """
    return ActivityScoreRequest(
        profile=UserProfile(
            age=50,
            sex="female",
            height_cm=160,
            weight_kg=68,
            chronic_diseases=["diabetes"],
        ),
        daily_steps=7000,
        target_hr_minutes=20,
    )


def test_build_owner_subject_uses_issuer_and_subject() -> None:
    """Verify owner keys are issuer-qualified to avoid subject collisions."""
    assert build_owner_subject(_user()) == "https://auth.example.com/::user_123"


def test_analysis_result_response_omits_owner_and_input_snapshot() -> None:
    """Verify public responses do not expose owner IDs or raw input snapshots."""
    record = AnalysisResult(
        id=uuid4(),
        owner_subject="https://auth.example.com/::user_123",
        analysis_type=AnalysisType.ACTIVITY_SCORE.value,
        algorithm_version="activity-v1.0.0",
        input_snapshot={"daily_steps": 7000},
        result_snapshot={"v4_score": 90.0},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    response = analysis_result_to_response(record)
    body = response.model_dump()

    assert "owner_subject" not in body
    assert "input_snapshot" not in body
    assert body["result_snapshot"] == {"v4_score": 90.0}


def test_summary_extracts_daily_health_score_trend_fields() -> None:
    """Verify daily health score list items expose score/measured_date/label (guide 06 §4.1)."""
    record = AnalysisResult(
        id=uuid4(),
        owner_subject="https://auth.example.com/::user_123",
        analysis_type=AnalysisType.DAILY_HEALTH_SCORE.value,
        algorithm_version="daily-health-score-v1.0.0",
        input_snapshot={"summary_date": "2026-06-12"},
        result_snapshot={
            "data_status": "ready",
            "score": 78,
            "label": "good",
            "label_text": "양호",
            "measured_date": "2026-06-12",
        },
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    summary = analysis_result_to_summary(record)

    assert summary.score == 78
    assert summary.measured_date == "2026-06-12"
    assert summary.label == "good"


def test_summary_trend_fields_stay_null_for_other_types_and_malformed_snapshots() -> None:
    """Verify trend summary fields stay None for non-score rows and malformed snapshots."""
    activity = AnalysisResult(
        id=uuid4(),
        owner_subject="https://auth.example.com/::user_123",
        analysis_type=AnalysisType.ACTIVITY_SCORE.value,
        algorithm_version="activity-v1.0.0",
        input_snapshot={"daily_steps": 7000},
        # 동명 키가 있어도 daily_health_score 타입이 아니면 추출하지 않는다.
        result_snapshot={"v4_score": 90.0, "score": 90, "measured_date": "2026-06-12"},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    malformed = AnalysisResult(
        id=uuid4(),
        owner_subject="https://auth.example.com/::user_123",
        analysis_type=AnalysisType.DAILY_HEALTH_SCORE.value,
        algorithm_version="daily-health-score-v1.0.0",
        input_snapshot={"summary_date": "2026-06-12"},
        result_snapshot={"score": "78", "measured_date": 20260612, "label": 3},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    activity_summary = analysis_result_to_summary(activity)
    malformed_summary = analysis_result_to_summary(malformed)

    assert activity_summary.score is None
    assert activity_summary.measured_date is None
    assert activity_summary.label is None
    assert malformed_summary.score is None
    assert malformed_summary.measured_date is None
    assert malformed_summary.label is None


@pytest.mark.asyncio
async def test_store_activity_result_persists_server_computed_snapshot() -> None:
    """Verify stored result snapshots come from server computation, not client-provided output."""
    fake_session = _FakeWriteSession()

    record = await store_activity_score_result(
        cast(AsyncSession, fake_session),
        _user(),
        _activity_request(),
    )

    assert record is fake_session.added
    assert record.owner_subject == "https://auth.example.com/::user_123"
    assert record.analysis_type == AnalysisType.ACTIVITY_SCORE.value
    assert record.input_snapshot["daily_steps"] == 7000
    assert record.result_snapshot["recommended_steps"] == 7500
    assert "owner_subject" not in record.input_snapshot


@pytest.mark.asyncio
async def test_persist_result_owns_transaction_in_legacy_mode() -> None:
    """Verify legacy (get_async_session) sessions commit the result exactly once.

    persist_scope OWN mode reproduces the historical ``add + commit`` behavior, so
    an un-migrated route's session must see exactly one commit.
    """
    fake_session = _FakeWriteSession()  # no REQUEST_MANAGED_TX marker → OWN mode

    await store_activity_score_result(
        cast(AsyncSession, fake_session),
        _user(),
        _activity_request(),
    )

    assert fake_session.commits == 1


@pytest.mark.asyncio
async def test_persist_result_participates_in_request_managed_transaction() -> None:
    """Verify RLS (get_rls_context_session) sessions never commit mid-request.

    The request dependency owns begin + commit so the transaction-local RLS GUCs
    survive to dependency exit; persist_scope must only flush.
    """
    fake_session = _FakeWriteSession(request_managed=True)

    await store_activity_score_result(
        cast(AsyncSession, fake_session),
        _user(),
        _activity_request(),
    )

    assert fake_session.commits == 0


@pytest.mark.asyncio
async def test_get_analysis_result_filters_by_id_and_owner() -> None:
    """Verify detail lookup uses both result ID and owner subject in the SQL predicate."""
    fake_session = _FakeReadSession()
    result_id = uuid4()

    await get_analysis_result(cast(AsyncSession, fake_session), _user(), result_id)

    assert fake_session.statement is not None
    compiled = str(fake_session.statement)
    assert "analysis_results.id" in compiled
    assert "analysis_results.owner_subject" in compiled
