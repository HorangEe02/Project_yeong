"""Weight prediction selector tests."""

from __future__ import annotations

from typing import Any

from src.prediction.selector import (
    HALL_LITE_WARNING,
    WeightPredictionEngine,
    predict_weight_periods_selected,
)
from src.prediction.weight import predict_weight_periods


def _base_kwargs() -> dict[str, Any]:
    """Return the shared 50F weight prediction fixture.

    Returns:
        Keyword arguments accepted by the selector and static predictor.
    """
    return {
        "weight_kg": 68.0,
        "height_cm": 160.0,
        "age": 50,
        "sex": "female",
        "daily_steps": 6500,
        "daily_intake_kcal": 1500.0,
        "periods_days": [7, 30, 90],
    }


def test_selector_default_matches_static_7step_response() -> None:
    """Verify the selector is API-compatible by default."""
    kwargs = _base_kwargs()

    selected = predict_weight_periods_selected(**kwargs)
    static = predict_weight_periods(**kwargs)

    assert selected == static


def test_selector_feature_flag_false_forces_static_even_when_engine_is_hall() -> None:
    """Verify Hall-lite cannot run when the feature flag is disabled."""
    kwargs = _base_kwargs()

    selected = predict_weight_periods_selected(
        **kwargs,
        feature_hall_lite_weight_prediction=False,
        weight_prediction_engine=WeightPredictionEngine.HALL_LITE,
    )
    static = predict_weight_periods(**kwargs)

    assert selected == static


def test_selector_static_engine_forces_static_when_feature_enabled() -> None:
    """Verify explicit static engine preserves existing fallback behavior."""
    kwargs = _base_kwargs()

    selected = predict_weight_periods_selected(
        **kwargs,
        feature_hall_lite_weight_prediction=True,
        weight_prediction_engine=WeightPredictionEngine.STATIC_7STEP,
    )
    static = predict_weight_periods(**kwargs)

    assert selected == static


def test_selector_static_preserves_walking_cadence_inputs() -> None:
    """Verify cadence inputs reach the static fallback path."""
    kwargs = _base_kwargs()
    kwargs["walking_cadence_steps_per_min"] = 120.0
    kwargs["walking_cadence_minutes"] = 30.0

    selected = predict_weight_periods_selected(**kwargs)
    static = predict_weight_periods(**kwargs)

    assert selected == static
    assert selected.safety_warnings


def test_selector_static_preserves_heart_rate_inputs() -> None:
    """Verify exercise heart-rate inputs reach the static fallback path."""
    kwargs = _base_kwargs()
    kwargs["exercise_average_heart_rate_bpm"] = 130.0
    kwargs["heart_rate_exercise_minutes"] = 30.0

    selected = predict_weight_periods_selected(**kwargs)
    static = predict_weight_periods(**kwargs)

    assert selected == static
    assert selected.safety_warnings


def test_selector_auto_uses_hall_only_for_long_term_candidate() -> None:
    """Verify auto mode keeps short periods static and upgrades long periods."""
    kwargs = _base_kwargs()

    selected = predict_weight_periods_selected(
        **kwargs,
        feature_hall_lite_weight_prediction=True,
        weight_prediction_engine=WeightPredictionEngine.AUTO,
    )
    static = predict_weight_periods(**kwargs)

    assert selected.predictions[0] == static.predictions[0]
    assert selected.predictions[1] == static.predictions[1]
    assert selected.predictions[2].warning == HALL_LITE_WARNING
    assert selected.predictions[2].predicted_weight_kg != static.predictions[2].predicted_weight_kg


def test_selector_underage_falls_back_to_static() -> None:
    """Verify Hall-lite adult approximation is not used for underage inputs."""
    kwargs = _base_kwargs()
    kwargs["age"] = 17

    selected = predict_weight_periods_selected(
        **kwargs,
        feature_hall_lite_weight_prediction=True,
        weight_prediction_engine=WeightPredictionEngine.HALL_LITE,
    )
    static = predict_weight_periods(**kwargs)

    assert selected == static


def test_selector_hall_lite_applies_alcohol_storage_factor() -> None:
    """Verify Hall-lite receives the same alcohol kcal adjustment contract."""
    base_kwargs = _base_kwargs()
    base_kwargs["periods_days"] = [90]
    with_alcohol = predict_weight_periods_selected(
        **base_kwargs,
        alcohol_kcal=100,
        feature_hall_lite_weight_prediction=True,
        weight_prediction_engine=WeightPredictionEngine.HALL_LITE,
    )
    without_alcohol = predict_weight_periods_selected(
        **base_kwargs,
        feature_hall_lite_weight_prediction=True,
        weight_prediction_engine=WeightPredictionEngine.HALL_LITE,
    )

    assert with_alcohol.safety_warnings
    assert with_alcohol.predictions[0].daily_balance_kcal == (
        without_alcohol.predictions[0].daily_balance_kcal + 130
    )


def test_selector_hall_lite_uses_measured_body_fat_for_partitioning() -> None:
    """Verify body-fat input reaches Hall-lite FM/FFM partitioning."""
    base_kwargs = {
        "weight_kg": 80.0,
        "height_cm": 175.0,
        "age": 40,
        "sex": "male",
        "daily_steps": 6500,
        "daily_intake_kcal": 1800.0,
        "periods_days": [90],
        "feature_hall_lite_weight_prediction": True,
        "weight_prediction_engine": WeightPredictionEngine.HALL_LITE,
    }

    lower_body_fat = predict_weight_periods_selected(**base_kwargs, body_fat_pct=15.0)
    higher_body_fat = predict_weight_periods_selected(**base_kwargs, body_fat_pct=35.0)
    estimated_body_fat = predict_weight_periods_selected(**base_kwargs)

    assert lower_body_fat.predictions[0].model_name == "hall_lite"
    assert lower_body_fat.predictions[0].predicted_weight_kg < (
        estimated_body_fat.predictions[0].predicted_weight_kg
    )
    assert higher_body_fat.predictions[0].predicted_weight_kg > (
        estimated_body_fat.predictions[0].predicted_weight_kg
    )


def test_selector_hall_lite_preserves_walking_cadence_baseline() -> None:
    """Verify cadence inputs also reach Hall-lite baseline TDEE."""
    kwargs = _base_kwargs()
    kwargs["periods_days"] = [90]

    without_cadence = predict_weight_periods_selected(
        **kwargs,
        feature_hall_lite_weight_prediction=True,
        weight_prediction_engine=WeightPredictionEngine.HALL_LITE,
    )
    with_cadence = predict_weight_periods_selected(
        **kwargs,
        walking_cadence_steps_per_min=120.0,
        walking_cadence_minutes=30.0,
        feature_hall_lite_weight_prediction=True,
        weight_prediction_engine=WeightPredictionEngine.HALL_LITE,
    )

    assert with_cadence.predictions[0].model_name == "hall_lite"
    assert (
        with_cadence.predictions[0].estimated_tdee > without_cadence.predictions[0].estimated_tdee
    )
    assert with_cadence.safety_warnings


def test_selector_hall_lite_preserves_heart_rate_baseline() -> None:
    """Verify exercise heart-rate inputs also reach Hall-lite baseline TDEE."""
    kwargs = _base_kwargs()
    kwargs["periods_days"] = [90]

    without_heart_rate = predict_weight_periods_selected(
        **kwargs,
        feature_hall_lite_weight_prediction=True,
        weight_prediction_engine=WeightPredictionEngine.HALL_LITE,
    )
    with_heart_rate = predict_weight_periods_selected(
        **kwargs,
        exercise_average_heart_rate_bpm=130.0,
        heart_rate_exercise_minutes=30.0,
        feature_hall_lite_weight_prediction=True,
        weight_prediction_engine=WeightPredictionEngine.HALL_LITE,
    )

    assert with_heart_rate.predictions[0].model_name == "hall_lite"
    assert (
        with_heart_rate.predictions[0].estimated_tdee
        > without_heart_rate.predictions[0].estimated_tdee
    )
    assert with_heart_rate.safety_warnings
