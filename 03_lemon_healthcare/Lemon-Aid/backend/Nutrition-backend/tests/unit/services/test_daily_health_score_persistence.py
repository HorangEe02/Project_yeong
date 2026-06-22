"""Daily health score persistence (opt-in store) unit tests."""

from __future__ import annotations

from datetime import date
from typing import Any

from src.models.schemas.analysis_result import AnalysisType
from src.models.schemas.dashboard import (
    DashboardHealthScoreSummary,
    DashboardScoreComponent,
    DashboardScoreComponents,
)
from src.security.auth import AuthenticatedUser
from src.services.analysis_results import store_daily_health_score_result
from src.services.daily_health_score import DAILY_HEALTH_SCORE_ALGORITHM_VERSION

FORBIDDEN_USER_TERMS = ("진단", "치료", "처방", "복용량 변경", "효능")


class _FakeSession:
    """Minimal async-session stand-in for the dedup/store code path."""

    def __init__(self, existing_id: Any = None) -> None:
        self.existing_id = existing_id
        self.added: list[Any] = []
        self.commits = 0

    async def scalar(self, _statement: Any) -> Any:
        return self.existing_id

    def add(self, record: Any) -> None:
        self.added.append(record)

    async def commit(self) -> None:
        self.commits += 1


def _user() -> AuthenticatedUser:
    return AuthenticatedUser(
        subject="local-dev-user",
        issuer="local-development",
        claims={"sub": "local-dev-user", "iss": "local-development"},
    )


def _ready_summary(*, score: int = 78) -> DashboardHealthScoreSummary:
    return DashboardHealthScoreSummary(
        data_status="ready",
        score=score,
        label="good",
        label_text="양호",
        message="전반적으로 좋아요. 한두 가지만 더 신경 써보세요.",
        components=DashboardScoreComponents(
            activity=DashboardScoreComponent(available=True, subscore=82.0, weight=0.6),
            nutrition=DashboardScoreComponent(available=True, subscore=72.0, weight=0.4),
        ),
        disclaimers=["이 점수는 건강 관리 참고용이며 의학적 진단이 아닙니다."],
        algorithm_version=DAILY_HEALTH_SCORE_ALGORITHM_VERSION,
        measured_date=date(2026, 6, 12),
    )


def _not_ready_summary() -> DashboardHealthScoreSummary:
    return DashboardHealthScoreSummary(
        data_status="not_ready",
        score=None,
        label=None,
        label_text=None,
        message=None,
        components=DashboardScoreComponents(
            activity=DashboardScoreComponent(available=False, subscore=None, weight=0.0),
            nutrition=DashboardScoreComponent(available=False, subscore=None, weight=0.0),
        ),
        algorithm_version=DAILY_HEALTH_SCORE_ALGORITHM_VERSION,
        measured_date=None,
    )


async def test_store_skips_not_ready_score() -> None:
    """Verify a not_ready score is never persisted (no fabricated rows)."""
    session = _FakeSession()

    stored = await store_daily_health_score_result(
        session,  # type: ignore[arg-type]
        _user(),
        date(2026, 6, 12),
        _not_ready_summary(),
    )

    assert stored is None
    assert session.added == []
    assert session.commits == 0


async def test_store_dedups_same_owner_and_summary_date() -> None:
    """Verify an existing same-day row short-circuits without a new insert."""
    session = _FakeSession(existing_id="existing-row-id")

    stored = await store_daily_health_score_result(
        session,  # type: ignore[arg-type]
        _user(),
        date(2026, 6, 12),
        _ready_summary(),
    )

    assert stored is None
    assert session.added == []
    assert session.commits == 0


async def test_store_persists_ready_score_with_expected_fields() -> None:
    """Verify the stored row carries type, version, and snapshot contracts."""
    session = _FakeSession()
    summary_date = date(2026, 6, 12)

    stored = await store_daily_health_score_result(
        session,  # type: ignore[arg-type]
        _user(),
        summary_date,
        _ready_summary(score=84),
    )

    assert stored is not None
    assert session.commits == 1
    assert [stored] == session.added
    assert stored.analysis_type == AnalysisType.DAILY_HEALTH_SCORE.value
    assert stored.algorithm_version == DAILY_HEALTH_SCORE_ALGORITHM_VERSION
    assert stored.input_snapshot["summary_date"] == summary_date.isoformat()
    assert stored.input_snapshot["weights"] == {"activity": 0.6, "nutrition": 0.4}
    assert stored.result_snapshot["score"] == 84
    assert stored.result_snapshot["data_status"] == "ready"


async def test_stored_snapshot_messages_are_free_of_forbidden_terms() -> None:
    """Verify persisted user-facing copy stays inside the medical-law guard."""
    session = _FakeSession()

    stored = await store_daily_health_score_result(
        session,  # type: ignore[arg-type]
        _user(),
        date(2026, 6, 12),
        _ready_summary(),
    )

    assert stored is not None
    surfaced = " ".join(
        str(stored.result_snapshot.get(key) or "") for key in ("message", "label_text")
    )
    for term in FORBIDDEN_USER_TERMS:
        assert term not in surfaced
