"""Dashboard service helper tests."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from src.models.db.analysis_result import AnalysisResult
from src.models.db.health import HealthDailySummary
from src.models.schemas.analysis_result import AnalysisType
from src.services import dashboard


def _analysis_result(
    analysis_type: AnalysisType, result_snapshot: dict[str, object]
) -> AnalysisResult:
    """Return an analysis result fixture.

    Args:
        analysis_type: Analysis result type.
        result_snapshot: Result snapshot payload.

    Returns:
        Analysis result ORM object.
    """
    now = datetime.now(UTC)
    return AnalysisResult(
        id=uuid4(),
        owner_subject="local-development::local-dev-user",
        analysis_type=analysis_type.value,
        algorithm_version="test-v1",
        input_snapshot={},
        result_snapshot=result_snapshot,
        created_at=now,
        updated_at=now,
    )


def test_dashboard_activity_summary_prefers_latest_steps_and_activity_score() -> None:
    """Verify activity summary combines synced health aggregates and activity result."""
    health_row = HealthDailySummary(
        id=uuid4(),
        owner_subject="local-development::local-dev-user",
        measured_date=date(2026, 5, 12),
        source_platform="manual",
        steps=7200,
        weight_kg=None,
        resting_heart_rate_bpm=68,
        active_energy_kcal=Decimal("430.25"),
        synced_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    record = _analysis_result(AnalysisType.ACTIVITY_SCORE, {"v4_score": 84.2})

    summary = dashboard._dashboard_activity_summary([health_row], record)

    assert summary.data_status == "ready"
    assert summary.latest_steps == 7200
    assert summary.latest_resting_heart_rate_bpm == 68
    assert summary.latest_active_energy_kcal == 430.25
    assert summary.latest_activity_score == 84.2
    assert summary.measured_date == date(2026, 5, 12)


def test_dashboard_activity_summary_uses_health_sync_metrics_without_steps() -> None:
    """Verify HealthKit or Health Connect non-step activity metrics make the dashboard ready."""
    health_row = HealthDailySummary(
        id=uuid4(),
        owner_subject="local-development::local-dev-user",
        measured_date=date(2026, 5, 12),
        source_platform="ios_healthkit",
        steps=None,
        weight_kg=None,
        resting_heart_rate_bpm=64,
        active_energy_kcal=Decimal("390.50"),
        synced_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    summary = dashboard._dashboard_activity_summary([health_row], None)

    assert summary.data_status == "ready"
    assert summary.latest_steps is None
    assert summary.latest_resting_heart_rate_bpm == 64
    assert summary.latest_active_energy_kcal == 390.5
    assert summary.measured_date == date(2026, 5, 12)


def test_dashboard_weight_summary_uses_shortest_prediction_period() -> None:
    """Verify weight summary uses the shortest-period prediction for dashboard display."""
    health_row = HealthDailySummary(
        id=uuid4(),
        owner_subject="local-development::local-dev-user",
        measured_date=date(2026, 5, 12),
        source_platform="manual",
        steps=None,
        weight_kg=Decimal("68.40"),
        synced_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    record = _analysis_result(
        AnalysisType.WEIGHT_PREDICTION,
        {
            "predictions": [
                {"days": 30, "predicted_weight_kg": 67.19},
                {"days": 7, "predicted_weight_kg": 67.81},
            ]
        },
    )

    summary = dashboard._dashboard_weight_summary([health_row], record)

    assert summary.data_status == "ready"
    assert summary.latest_weight_kg == 68.4
    assert summary.predicted_weight_kg == 67.81


def test_dashboard_nutrition_summary_handles_missing_result() -> None:
    """Verify dashboard nutrition summary is safe when no analysis exists."""
    summary = dashboard._dashboard_nutrition_summary(None)

    assert summary.data_status == "not_ready"
    assert summary.low_count == 0
    assert summary.high_count == 0
    assert summary.latest_result_id is None
