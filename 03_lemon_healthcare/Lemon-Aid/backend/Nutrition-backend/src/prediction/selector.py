"""Safe model selector for weight prediction."""

from __future__ import annotations

from enum import StrEnum
from typing import Final

from src.models.schemas.algorithm import (
    WeightPredictionCheckIn,
    WeightPredictionResponse,
    WeightPredictionStep,
)
from src.models.schemas.user import Sex
from src.prediction.hall import HallLiteResult, predict_with_hall
from src.prediction.weight import (
    ALCOHOL_STORAGE_KCAL_FACTOR,
    KCAL_PER_KG_FAT,
    build_disabled_weight_prediction_response,
    evaluate_weight_prediction_mismatch,
    predict_weight_n_days,
    predict_weight_periods,
    should_disable_weight_prediction,
)

LONG_TERM_HALL_CANDIDATE_DAYS: Final[int] = 90
HALL_LITE_MIN_AGE_YEARS: Final[int] = 18
ROUND_KCAL_DECIMALS: Final[int] = 1
ROUND_CHANGE_DECIMALS: Final[int] = 3
HALL_LITE_WARNING = "Hall-lite 동적 시뮬레이션 참고값입니다. 실제 체중 변화는 개인 상태와 측정 오차에 따라 달라질 수 있습니다."


class WeightPredictionEngine(StrEnum):
    """Supported internal weight prediction engines.

    Attributes:
        STATIC_7STEP: Existing static 7-step fallback model.
        HALL_LITE: Hall-lite dynamic simulator.
        AUTO: Static model for short periods and Hall-lite for long-period candidates.
    """

    STATIC_7STEP = "static_7step"
    HALL_LITE = "hall_lite"
    AUTO = "auto"


def _coerce_engine(engine: str | WeightPredictionEngine) -> WeightPredictionEngine:
    """Coerce a settings value into a prediction engine enum.

    Args:
        engine: Raw engine value from settings or tests.

    Returns:
        Parsed prediction engine.

    Raises:
        ValueError: If the engine value is unsupported.
    """
    if isinstance(engine, WeightPredictionEngine):
        return engine
    return WeightPredictionEngine(engine)


def _should_use_hall_lite(
    *,
    feature_hall_lite_weight_prediction: bool,
    engine: WeightPredictionEngine,
    age: int,
    days: int,
) -> bool:
    """Decide whether a period should use Hall-lite.

    Args:
        feature_hall_lite_weight_prediction: Hall-lite feature flag.
        engine: Configured prediction engine.
        age: User age in years.
        days: Prediction period in days.

    Returns:
        True when Hall-lite is enabled and appropriate for the input.
    """
    if not feature_hall_lite_weight_prediction:
        return False
    if age < HALL_LITE_MIN_AGE_YEARS:
        return False
    if engine == WeightPredictionEngine.HALL_LITE:
        return True
    return engine == WeightPredictionEngine.AUTO and days >= LONG_TERM_HALL_CANDIDATE_DAYS


def _hall_result_to_weight_step(
    *,
    result: HallLiteResult,
    daily_intake_kcal: float,
    days: int,
) -> WeightPredictionStep:
    """Map an internal Hall-lite result to the existing response step shape.

    Args:
        result: Internal Hall-lite simulation result.
        daily_intake_kcal: Scenario intake in kcal/day.
        days: Prediction period in days.

    Returns:
        Existing API-compatible weight prediction step.
    """
    initial_daily_balance_kcal = daily_intake_kcal - result.initial_tdee_kcal
    initial_cumulative_balance_kcal = initial_daily_balance_kcal * days
    theoretical_change_kg = initial_cumulative_balance_kcal / KCAL_PER_KG_FAT
    range_band_kg = abs(result.weight_change_kg) * 0.10

    return WeightPredictionStep(
        days=days,
        estimated_bmr=result.initial_bmr_kcal,
        estimated_tdee=result.initial_tdee_kcal,
        daily_balance_kcal=round(initial_daily_balance_kcal, ROUND_KCAL_DECIMALS),
        cumulative_balance_kcal=round(
            result.cumulative_energy_balance_kcal,
            ROUND_KCAL_DECIMALS,
        ),
        theoretical_change_kg=round(theoretical_change_kg, ROUND_CHANGE_DECIMALS),
        corrected_change_kg=round(result.weight_change_kg, ROUND_CHANGE_DECIMALS),
        predicted_weight_kg=result.predicted_weight_kg,
        expected_weight_range_kg=(
            round(result.predicted_weight_kg - range_band_kg, 2),
            round(result.predicted_weight_kg + range_band_kg, 2),
        ),
        model_name="hall_lite",
        confidence="low" if days >= LONG_TERM_HALL_CANDIDATE_DAYS else "medium",
        warning=HALL_LITE_WARNING,
    )


def _predict_one_period(
    *,
    weight_kg: float,
    height_cm: float,
    age: int,
    sex: Sex,
    daily_steps: int,
    daily_intake_kcal: float,
    days: int,
    body_fat_pct: float | None,
    alcohol_kcal: float,
    walking_cadence_steps_per_min: float | None,
    walking_cadence_minutes: float,
    exercise_average_heart_rate_bpm: float | None,
    heart_rate_exercise_minutes: float,
    chronic_diseases: list[str] | None,
    feature_hall_lite_weight_prediction: bool,
    engine: WeightPredictionEngine,
) -> WeightPredictionStep:
    """Predict one period using Hall-lite when enabled, otherwise 7-step.

    Args:
        weight_kg: Current body weight in kilograms.
        height_cm: Height in centimeters.
        age: Age in years.
        sex: Biological sex accepted by the current algorithm schemas.
        daily_steps: Daily step count.
        daily_intake_kcal: Daily intake in kcal/day.
        days: Prediction period in days.
        body_fat_pct: Optional body-fat percentage.
        alcohol_kcal: Alcohol kcal added separately to intake.
        walking_cadence_steps_per_min: Optional walking cadence in steps/min.
        walking_cadence_minutes: Minutes observed at the walking cadence.
        exercise_average_heart_rate_bpm: Optional average exercise heart rate in bpm.
        heart_rate_exercise_minutes: Minutes observed at that average heart rate.
        chronic_diseases: User condition codes for safety routing.
        feature_hall_lite_weight_prediction: Hall-lite feature flag.
        engine: Configured prediction engine.

    Returns:
        API-compatible weight prediction step.
    """
    if _should_use_hall_lite(
        feature_hall_lite_weight_prediction=feature_hall_lite_weight_prediction,
        engine=engine,
        age=age,
        days=days,
    ):
        try:
            effective_intake_kcal = daily_intake_kcal + alcohol_kcal * ALCOHOL_STORAGE_KCAL_FACTOR
            result = predict_with_hall(
                weight_kg=weight_kg,
                height_cm=height_cm,
                age=age,
                sex=sex,
                daily_steps=daily_steps,
                daily_intake_kcal=effective_intake_kcal,
                n_days=days,
                measured_body_fat_pct=body_fat_pct,
                walking_cadence_steps_per_min=walking_cadence_steps_per_min,
                walking_cadence_minutes=walking_cadence_minutes,
                exercise_average_heart_rate_bpm=exercise_average_heart_rate_bpm,
                heart_rate_exercise_minutes=heart_rate_exercise_minutes,
            )
            return _hall_result_to_weight_step(
                result=result,
                daily_intake_kcal=effective_intake_kcal,
                days=days,
            )
        except ValueError:
            pass

    return predict_weight_n_days(
        weight_kg=weight_kg,
        height_cm=height_cm,
        age=age,
        sex=sex,
        daily_steps=daily_steps,
        daily_intake_kcal=daily_intake_kcal,
        days=days,
        body_fat_pct=body_fat_pct,
        alcohol_kcal=alcohol_kcal,
        walking_cadence_steps_per_min=walking_cadence_steps_per_min,
        walking_cadence_minutes=walking_cadence_minutes,
        exercise_average_heart_rate_bpm=exercise_average_heart_rate_bpm,
        heart_rate_exercise_minutes=heart_rate_exercise_minutes,
        chronic_diseases=chronic_diseases,
    )


def predict_weight_periods_selected(
    *,
    weight_kg: float,
    height_cm: float,
    age: int,
    sex: Sex,
    daily_steps: int,
    daily_intake_kcal: float,
    periods_days: list[int],
    body_fat_pct: float | None = None,
    alcohol_kcal: float = 0.0,
    walking_cadence_steps_per_min: float | None = None,
    walking_cadence_minutes: float = 0.0,
    exercise_average_heart_rate_bpm: float | None = None,
    heart_rate_exercise_minutes: float = 0.0,
    chronic_diseases: list[str] | None = None,
    prediction_checkins: list[WeightPredictionCheckIn] | None = None,
    feature_hall_lite_weight_prediction: bool = False,
    weight_prediction_engine: str | WeightPredictionEngine = WeightPredictionEngine.STATIC_7STEP,
) -> WeightPredictionResponse:
    """Predict periods through the configured safe model selector.

    Args:
        weight_kg: Current body weight in kilograms.
        height_cm: Height in centimeters.
        age: Age in years.
        sex: Biological sex accepted by the current algorithm schemas.
        daily_steps: Daily step count.
        daily_intake_kcal: Daily intake in kcal/day.
        periods_days: Prediction periods in days.
        body_fat_pct: Optional body-fat percentage.
        alcohol_kcal: Alcohol kcal added separately to intake.
        walking_cadence_steps_per_min: Optional walking cadence in steps/min.
        walking_cadence_minutes: Minutes observed at the walking cadence.
        exercise_average_heart_rate_bpm: Optional average exercise heart rate in bpm.
        heart_rate_exercise_minutes: Minutes observed at that average heart rate.
        chronic_diseases: User condition codes for safety routing.
        prediction_checkins: Weekly measured-weight follow-up values for mismatch warning.
        feature_hall_lite_weight_prediction: Hall-lite feature flag.
        weight_prediction_engine: Configured prediction engine.

    Returns:
        Existing API-compatible response.

    Raises:
        ValueError: If the configured prediction engine is unsupported.
    """
    if should_disable_weight_prediction(chronic_diseases):
        return build_disabled_weight_prediction_response(chronic_diseases or [])

    engine = _coerce_engine(weight_prediction_engine)
    if not feature_hall_lite_weight_prediction or engine == WeightPredictionEngine.STATIC_7STEP:
        return predict_weight_periods(
            weight_kg=weight_kg,
            height_cm=height_cm,
            age=age,
            sex=sex,
            daily_steps=daily_steps,
            daily_intake_kcal=daily_intake_kcal,
            periods_days=periods_days,
            body_fat_pct=body_fat_pct,
            alcohol_kcal=alcohol_kcal,
            walking_cadence_steps_per_min=walking_cadence_steps_per_min,
            walking_cadence_minutes=walking_cadence_minutes,
            exercise_average_heart_rate_bpm=exercise_average_heart_rate_bpm,
            heart_rate_exercise_minutes=heart_rate_exercise_minutes,
            chronic_diseases=chronic_diseases,
            prediction_checkins=prediction_checkins,
        )

    predictions = [
        _predict_one_period(
            weight_kg=weight_kg,
            height_cm=height_cm,
            age=age,
            sex=sex,
            daily_steps=daily_steps,
            daily_intake_kcal=daily_intake_kcal,
            days=days,
            body_fat_pct=body_fat_pct,
            alcohol_kcal=alcohol_kcal,
            walking_cadence_steps_per_min=walking_cadence_steps_per_min,
            walking_cadence_minutes=walking_cadence_minutes,
            exercise_average_heart_rate_bpm=exercise_average_heart_rate_bpm,
            heart_rate_exercise_minutes=heart_rate_exercise_minutes,
            chronic_diseases=chronic_diseases,
            feature_hall_lite_weight_prediction=feature_hall_lite_weight_prediction,
            engine=engine,
        )
        for days in periods_days
    ]
    safety_warnings: list[str] = []
    if alcohol_kcal > 0:
        safety_warnings.append("알코올 열량을 일일 섭취 열량에 별도 합산했습니다.")
    if walking_cadence_steps_per_min is not None and walking_cadence_minutes > 0:
        safety_warnings.append(
            "보행 cadence 기반 운동 열량을 Tudor-Locke 휴리스틱 METs로 환산해 TDEE에 반영했습니다."
        )
    if exercise_average_heart_rate_bpm is not None and heart_rate_exercise_minutes > 0:
        safety_warnings.append(
            "평균 운동 심박 기반 운동 열량을 Keytel 2005 회귀식으로 환산해 TDEE에 반영했습니다."
        )
    return WeightPredictionResponse(
        predictions=predictions,
        safety_warnings=safety_warnings,
        mismatch_warning=evaluate_weight_prediction_mismatch(prediction_checkins),
    )
