"""7-step 체중 예측 산출식."""

from __future__ import annotations

from src.algorithms.metabolism import calculate_bmr, calculate_tdee
from src.models.schemas.algorithm import (
    WeightPredictionCheckIn,
    WeightPredictionMismatchWarning,
    WeightPredictionResponse,
    WeightPredictionStep,
)
from src.models.schemas.user import Sex

KCAL_PER_KG_FAT = 7700.0
SHORT_TERM_LOSS_KCAL_FACTOR = 0.55
LOSS_CORRECTION = 0.85
GAIN_CORRECTION = 0.95
ALCOHOL_STORAGE_KCAL_FACTOR = 1.30
ALCOHOL_DENSITY_G_PER_ML = 0.789
ALCOHOL_KCAL_PER_G = 7.0
MAX_ABV_PERCENT = 100.0
SHORT_TERM_DAYS = 7
LONG_TERM_WARNING_DAYS = 90
ROUND_KCAL_DECIMALS = 1
ROUND_CHANGE_DECIMALS = 3
ROUND_WEIGHT_DECIMALS = 2
WEIGHT_PREDICTION_ALGORITHM_VERSION = "weight-v1.0.0"
BLOCKING_CONDITIONS = {
    "hypothyroidism",
    "hypothyroid",
    "hyperthyroidism",
    "hyperthyroid",
    "ckd",
    "chronic_kidney_disease",
    "dialysis",
    "heart_failure",
    "heart_failure_edema",
    "cirrhosis",
    "liver_cirrhosis",
    "corticosteroid",
    "steroid",
    "prednisone",
}
LOW_CONFIDENCE_CONDITIONS = {"pcos", "diabetes_on_insulin", "diabetes_on_glp1"}
MISMATCH_WARNING_CONSECUTIVE_WEEKS = 2
MISMATCH_WARNING_MESSAGE = (
    "최근 실측 체중이 기대 체중 범위를 2주 연속 벗어났습니다. "
    "알고리즘 한계, 측정 조건 변화, 질환 또는 약물 영향 가능성을 다시 확인해주세요."
)
MISMATCH_RECOMMENDED_ACTIONS = [
    "최근 식사·활동·음주 기록과 체중 측정 조건을 다시 확인합니다.",
    "갑상선·신장·심부전·간질환·스테로이드 등 만성질환/약물 체크리스트를 갱신합니다.",
    "차이가 계속되면 주치의 또는 임상영양사 상담을 권장합니다.",
]


def calculate_alcohol_kcal_from_volume(volume_ml: float, abv_percent: float) -> float:
    """주류 용량과 도수로 알코올 kcal을 계산한다.

    Args:
        volume_ml: 주류 용량(ml).
        abv_percent: 알코올 도수(% ABV).

    Returns:
        알코올 유래 열량(kcal).

    Raises:
        ValueError: 음수 입력 또는 100% 초과 ABV인 경우.
    """
    if volume_ml < 0:
        raise ValueError("volume_ml must be non-negative")
    if not 0 <= abv_percent <= MAX_ABV_PERCENT:
        raise ValueError("abv_percent must be between 0 and 100")
    alcohol_grams = volume_ml * (abv_percent / MAX_ABV_PERCENT) * ALCOHOL_DENSITY_G_PER_ML
    return round(alcohol_grams * ALCOHOL_KCAL_PER_G, ROUND_KCAL_DECIMALS)


def _normalized_conditions(chronic_diseases: list[str] | None) -> set[str]:
    """Normalize condition codes for safety routing.

    Args:
        chronic_diseases: Raw condition codes.

    Returns:
        Case-folded condition code set.
    """
    return {condition.casefold() for condition in chronic_diseases or []}


def build_disabled_weight_prediction_response(
    chronic_diseases: list[str],
) -> WeightPredictionResponse:
    """Build a fail-closed response when automatic weight prediction is unsafe.

    Args:
        chronic_diseases: User-provided chronic disease codes.

    Returns:
        Disabled response without numeric projections.
    """
    normalized = sorted(_normalized_conditions(chronic_diseases) & BLOCKING_CONDITIONS)
    return WeightPredictionResponse(
        predictions=[],
        prediction_status="disabled",
        safety_warnings=[
            "만성질환 또는 약물 영향으로 일반 체중 변화 공식 자동 계산을 보류합니다.",
            (
                f"blocked_conditions={','.join(normalized)}"
                if normalized
                else "blocked_conditions=unknown"
            ),
        ],
        note="체중 변화는 체액·대사율·약물 영향이 클 수 있어 주치의 또는 임상영양사 상담을 권장합니다.",
    )


def should_disable_weight_prediction(chronic_diseases: list[str] | None) -> bool:
    """Return whether automatic weight prediction should be disabled.

    Args:
        chronic_diseases: User-provided chronic disease codes.

    Returns:
        True when a high-risk condition is present.
    """
    return bool(_normalized_conditions(chronic_diseases) & BLOCKING_CONDITIONS)


def is_weight_checkin_outside_expected_range(checkin: WeightPredictionCheckIn) -> bool:
    """주간 실측 체중이 해당 주차 기대 범위를 벗어났는지 판정한다.

    Args:
        checkin: 주간 실측 체중과 해당 주차 기대 체중 범위.

    Returns:
        실측 체중이 기대 범위 밖이면 True.
    """
    lower, upper = checkin.expected_weight_range_kg
    return checkin.measured_weight_kg < lower or checkin.measured_weight_kg > upper


def evaluate_weight_prediction_mismatch(
    prediction_checkins: list[WeightPredictionCheckIn] | None,
) -> WeightPredictionMismatchWarning | None:
    """예측-실측 체중이 최근 2주 연속 기대 범위를 벗어났는지 평가한다.

    Args:
        prediction_checkins: 예측 후 주차별 실측 체중 확인값.

    Returns:
        입력 check-in 이 있으면 mismatch 평가 결과, 없으면 None.
    """
    if not prediction_checkins:
        return None

    ordered_checkins = sorted(prediction_checkins, key=lambda checkin: checkin.week_index)
    out_of_range_count = sum(
        1 for checkin in ordered_checkins if is_weight_checkin_outside_expected_range(checkin)
    )
    expected_week = ordered_checkins[-1].week_index
    consecutive_out_of_range_weeks = 0
    for checkin in reversed(ordered_checkins):
        if checkin.week_index != expected_week:
            break
        if not is_weight_checkin_outside_expected_range(checkin):
            break
        consecutive_out_of_range_weeks += 1
        expected_week -= 1

    triggered = consecutive_out_of_range_weeks >= MISMATCH_WARNING_CONSECUTIVE_WEEKS
    return WeightPredictionMismatchWarning(
        triggered=triggered,
        consecutive_out_of_range_weeks=consecutive_out_of_range_weeks,
        out_of_range_count=out_of_range_count,
        message=MISMATCH_WARNING_MESSAGE if triggered else None,
        recommended_actions=list(MISMATCH_RECOMMENDED_ACTIONS) if triggered else [],
    )


def predict_weight_n_days(
    weight_kg: float,
    height_cm: float,
    age: int,
    sex: Sex,
    daily_steps: int,
    daily_intake_kcal: float,
    days: int,
    body_fat_pct: float | None = None,
    alcohol_kcal: float = 0.0,
    walking_cadence_steps_per_min: float | None = None,
    walking_cadence_minutes: float = 0.0,
    exercise_average_heart_rate_bpm: float | None = None,
    heart_rate_exercise_minutes: float = 0.0,
    chronic_diseases: list[str] | None = None,
) -> WeightPredictionStep:
    """N일 후 체중을 7-step 정적 근사로 예측한다.

    Args:
        weight_kg: 현재 체중(kg).
        height_cm: 키(cm).
        age: 만 나이.
        sex: "male" 또는 "female".
        daily_steps: 일일 걸음수.
        daily_intake_kcal: 일일 섭취 열량.
        days: 예측 기간(일).
        body_fat_pct: 체지방률(%). 10~55 범위에서 BMR 보조 공식에 사용한다.
        alcohol_kcal: 별도 입력된 알코올 열량.
        walking_cadence_steps_per_min: wearable 보행 cadence(steps/min).
        walking_cadence_minutes: cadence가 관측된 보행 시간(분).
        exercise_average_heart_rate_bpm: 운동 구간 평균 심박수(bpm).
        heart_rate_exercise_minutes: 평균 심박수가 관측된 운동 시간(분).
        chronic_diseases: 신뢰도 저하 또는 자동 계산 보류 조건.

    Returns:
        기간별 체중 예측 결과.

    Raises:
        ValueError: 예측 기간이 1일 미만인 경우.
    """
    if days < 1:
        raise ValueError("days must be greater than or equal to 1")
    if should_disable_weight_prediction(chronic_diseases):
        raise ValueError("automatic weight prediction is disabled for the supplied conditions")

    estimated_bmr = calculate_bmr(
        weight_kg=weight_kg,
        height_cm=height_cm,
        age=age,
        sex=sex,
        body_fat_pct=body_fat_pct,
    )
    estimated_tdee = calculate_tdee(
        estimated_bmr=estimated_bmr,
        daily_steps=daily_steps,
        weight_kg=weight_kg,
        age=age,
        sex=sex,
        walking_cadence_steps_per_min=walking_cadence_steps_per_min,
        walking_cadence_minutes=walking_cadence_minutes,
        exercise_average_heart_rate_bpm=exercise_average_heart_rate_bpm,
        heart_rate_exercise_minutes=heart_rate_exercise_minutes,
    )
    effective_alcohol_kcal = alcohol_kcal * ALCOHOL_STORAGE_KCAL_FACTOR
    daily_balance = daily_intake_kcal + effective_alcohol_kcal - estimated_tdee
    cumulative_balance = daily_balance * days
    theoretical_change = cumulative_balance / KCAL_PER_KG_FAT

    if daily_balance < 0:
        kcal_factor = SHORT_TERM_LOSS_KCAL_FACTOR if days <= SHORT_TERM_DAYS else LOSS_CORRECTION
        corrected_change = cumulative_balance / (KCAL_PER_KG_FAT * kcal_factor)
    elif daily_balance > 0:
        corrected_change = cumulative_balance / (KCAL_PER_KG_FAT * GAIN_CORRECTION)
    else:
        corrected_change = theoretical_change

    confidence = "high" if days <= SHORT_TERM_DAYS else "medium"
    normalized_conditions = _normalized_conditions(chronic_diseases)
    if days >= LONG_TERM_WARNING_DAYS or normalized_conditions & LOW_CONFIDENCE_CONDITIONS:
        confidence = "low"

    predicted_weight = weight_kg + corrected_change
    band = abs(corrected_change) * 0.10
    warning = (
        "90일 이상 기대 체중 범위는 대사 적응을 반영하는 동적 모델 검토가 필요합니다."
        if days >= LONG_TERM_WARNING_DAYS
        else None
    )

    return WeightPredictionStep(
        days=days,
        estimated_bmr=estimated_bmr,
        estimated_tdee=estimated_tdee,
        daily_balance_kcal=round(daily_balance, ROUND_KCAL_DECIMALS),
        cumulative_balance_kcal=round(cumulative_balance, ROUND_KCAL_DECIMALS),
        theoretical_change_kg=round(theoretical_change, ROUND_CHANGE_DECIMALS),
        corrected_change_kg=round(corrected_change, ROUND_CHANGE_DECIMALS),
        predicted_weight_kg=round(predicted_weight, ROUND_WEIGHT_DECIMALS),
        expected_weight_range_kg=(
            round(predicted_weight - band, ROUND_WEIGHT_DECIMALS),
            round(predicted_weight + band, ROUND_WEIGHT_DECIMALS),
        ),
        confidence=confidence,  # type: ignore[arg-type]
        warning=warning,
    )


def predict_weight_periods(
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
) -> WeightPredictionResponse:
    """여러 기간에 대한 체중 예측을 일괄 계산한다.

    Args:
        weight_kg: 현재 체중(kg).
        height_cm: 키(cm).
        age: 만 나이.
        sex: "male" 또는 "female".
        daily_steps: 일일 걸음수.
        daily_intake_kcal: 일일 섭취 열량.
        periods_days: 예측 기간 목록.
        body_fat_pct: 체지방률(%).
        alcohol_kcal: 별도 입력된 알코올 열량.
        walking_cadence_steps_per_min: wearable 보행 cadence(steps/min).
        walking_cadence_minutes: cadence가 관측된 보행 시간(분).
        exercise_average_heart_rate_bpm: 운동 구간 평균 심박수(bpm).
        heart_rate_exercise_minutes: 평균 심박수가 관측된 운동 시간(분).
        chronic_diseases: 신뢰도 저하 또는 자동 계산 보류 조건.
        prediction_checkins: 예측 후 주차별 실측 체중 확인값.

    Returns:
        기간별 체중 예측 API 응답.

    Raises:
        ValueError: 예측 기간 중 1일 미만 값이 있는 경우.
    """
    if should_disable_weight_prediction(chronic_diseases):
        return build_disabled_weight_prediction_response(chronic_diseases or [])

    predictions = [
        predict_weight_n_days(
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
        for days in periods_days
    ]
    safety_warnings: list[str] = []
    if _normalized_conditions(chronic_diseases) & LOW_CONFIDENCE_CONDITIONS:
        safety_warnings.append("일부 대사/약물 관련 조건으로 장기 예측 신뢰도를 낮게 표시합니다.")
    if alcohol_kcal > 0:
        safety_warnings.append(
            "알코올 열량은 지방 저장 보정 계수를 적용해 일일 섭취 열량에 합산했습니다."
        )
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
