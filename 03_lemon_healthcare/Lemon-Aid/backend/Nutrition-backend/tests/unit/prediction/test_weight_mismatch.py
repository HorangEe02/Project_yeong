"""Weight prediction mismatch warning tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from src.models.schemas.algorithm import WeightPredictionCheckIn, WeightPredictionRequest
from src.prediction.selector import WeightPredictionEngine, predict_weight_periods_selected
from src.prediction.weight import (
    evaluate_weight_prediction_mismatch,
    is_weight_checkin_outside_expected_range,
    predict_weight_periods,
)


def _checkin(
    week_index: int,
    measured_weight_kg: float,
    expected_range: tuple[float, float] = (66.8, 67.2),
) -> WeightPredictionCheckIn:
    """Build a weekly prediction check-in fixture.

    Args:
        week_index: 1-based week index after prediction.
        measured_weight_kg: Measured body weight for the week.
        expected_range: Expected body-weight range for the same week.

    Returns:
        Weight prediction check-in schema.
    """
    return WeightPredictionCheckIn(
        week_index=week_index,
        measured_weight_kg=measured_weight_kg,
        expected_weight_range_kg=expected_range,
    )


def test_weight_checkin_range_is_inclusive() -> None:
    """Verify boundary values are not treated as mismatch."""
    assert not is_weight_checkin_outside_expected_range(_checkin(1, 66.8))
    assert not is_weight_checkin_outside_expected_range(_checkin(1, 67.2))
    assert is_weight_checkin_outside_expected_range(_checkin(1, 67.3))


def test_prediction_mismatch_triggers_after_two_consecutive_recent_weeks() -> None:
    """Verify two latest consecutive out-of-range weeks trigger the warning."""
    warning = evaluate_weight_prediction_mismatch(
        [
            _checkin(1, 67.0),
            _checkin(2, 67.5),
            _checkin(3, 67.6),
        ]
    )

    assert warning is not None
    assert warning.triggered
    assert warning.consecutive_out_of_range_weeks == 2
    assert warning.out_of_range_count == 2
    assert warning.message is not None
    assert warning.recommended_actions


def test_prediction_mismatch_requires_latest_consecutive_weeks() -> None:
    """Verify older or non-consecutive mismatches do not trigger the two-week warning."""
    warning = evaluate_weight_prediction_mismatch(
        [
            _checkin(1, 67.5),
            _checkin(3, 67.6),
        ]
    )

    assert warning is not None
    assert not warning.triggered
    assert warning.consecutive_out_of_range_weeks == 1
    assert warning.out_of_range_count == 2


def test_weight_prediction_response_includes_mismatch_warning_when_checkins_are_supplied() -> None:
    """Verify static prediction response can include the mismatch warning block."""
    response = predict_weight_periods(
        weight_kg=68.0,
        height_cm=160.0,
        age=50,
        sex="female",
        daily_steps=6500,
        daily_intake_kcal=1500.0,
        periods_days=[7, 30],
        prediction_checkins=[_checkin(1, 67.5), _checkin(2, 67.6)],
    )

    assert response.mismatch_warning is not None
    assert response.mismatch_warning.triggered


def test_selector_preserves_mismatch_warning_with_hall_lite() -> None:
    """Verify selected Hall-lite responses use the same mismatch warning contract."""
    response = predict_weight_periods_selected(
        weight_kg=68.0,
        height_cm=160.0,
        age=50,
        sex="female",
        daily_steps=6500,
        daily_intake_kcal=1500.0,
        periods_days=[90],
        prediction_checkins=[_checkin(1, 67.5), _checkin(2, 67.6)],
        feature_hall_lite_weight_prediction=True,
        weight_prediction_engine=WeightPredictionEngine.HALL_LITE,
    )

    assert response.predictions[0].model_name == "hall_lite"
    assert response.mismatch_warning is not None
    assert response.mismatch_warning.triggered


def test_weight_prediction_request_rejects_duplicate_checkin_weeks() -> None:
    """Verify duplicate weekly check-ins are rejected before mismatch evaluation."""
    with pytest.raises(ValidationError, match="duplicate week_index"):
        WeightPredictionRequest(
            age=50,
            sex="female",
            height_cm=160,
            weight_kg=68,
            daily_steps=6500,
            daily_intake_kcal=1500,
            prediction_checkins=[_checkin(1, 67.5), _checkin(1, 67.6)],
        )
