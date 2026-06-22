"""활동점수 v1-v4 산출식."""

from __future__ import annotations

from src.algorithms.bmi import evaluate_bmi
from src.models.schemas.algorithm import (
    ActivityScoreRequest,
    ActivityScoreResponse,
    BMICategory,
    HRMaxFormula,
    TargetHeartRateRange,
)

BASE_STEPS = 8000
FEMALE_STEP_FACTOR = 0.95
MALE_STEP_FACTOR = 1.0
AGE_40_CUTOFF = 40
AGE_60_CUTOFF = 60
AGE_75_CUTOFF = 75
AGE_BASE_STEPS_UNDER_40 = 9000
AGE_BASE_STEPS_40_TO_59 = 8000
AGE_BASE_STEPS_60_TO_74 = 7000
AGE_BASE_STEPS_75_PLUS = 6000
ACHIEVEMENT_CAP = 1.2
MAX_V1_SCORE_AT_CAP = 83.33
GUIDE_HR_MAX_BASE = 220.0
TANAKA_HR_MAX_BASE = 208.0
TANAKA_AGE_COEFFICIENT = 0.7
GELLISH_HR_MAX_BASE = 207.0
GELLISH_AGE_COEFFICIENT = 0.7
NES_HR_MAX_BASE = 211.0
NES_AGE_COEFFICIENT = 0.64
TARGET_HR_LOW_RATIO = 0.64
TARGET_HR_HIGH_RATIO = 0.76
TARGET_HRR_LOW_RATIO = 0.40
TARGET_HRR_HIGH_RATIO = 0.59
TARGET_HR_FULL_CREDIT_MINUTES = 30.0
NO_WEARABLE_HR_FACTOR = 0.7
V2_BASE_MULTIPLIER = 0.7
V2_HR_MULTIPLIER_WEIGHT = 0.3
MIN_PERCENTILE_SAMPLE_SIZE = 100
MIN_VALID_PEER_SCORE = 0.0
MAX_VALID_PEER_SCORE = 100.0
TOP_10_PERCENT = 10.0
TOP_20_PERCENT = 20.0
TOP_30_PERCENT = 30.0
BONUS_TOP_10 = 10
BONUS_TOP_20 = 5
BONUS_TOP_30 = 3
MAX_SCORE = 100.0
MAX_DISEASE_MULTIPLIER = 1.3
ACTIVITY_ALGORITHM_VERSION = "activity-v1.0.0"
AUDIT_KR_RISK_CUTOFF = 3

BMI_STEP_FACTORS = {
    BMICategory.UNDERWEIGHT: 1.0,
    BMICategory.NORMAL: 1.0,
    BMICategory.OVERWEIGHT: 1.05,
    BMICategory.OBESE_1: 1.05,
    BMICategory.OBESE_2: 1.05,
    BMICategory.OBESE_3: 1.05,
}

DISEASE_WEIGHTS = {
    "diabetes": 0.10,
    "diabetes_t2": 0.10,
    "t2dm": 0.10,
    "hypertension": 0.10,
    "htn": 0.10,
    "cardiovascular": 0.15,
    "cad": 0.15,
    "joint": 0.15,
    "osteoarthritis": 0.15,
    "oa": 0.15,
    "respiratory": 0.10,
    "copd": 0.10,
}
CONDITION_RECOMMENDED_STEPS = {
    "diabetes": 7500,
    "diabetes_t2": 7500,
    "t2dm": 7500,
    "hypertension": 7500,
    "htn": 7500,
    "cardiovascular": 6500,
    "cad": 6500,
    "joint": 6000,
    "osteoarthritis": 6000,
    "oa": 6000,
    "respiratory": 5000,
    "copd": 5000,
}
MAX_DISEASE_WEIGHT_SUM = 0.30
SMOKING_MULTIPLIERS = {
    "former_lt_1y": 1.05,
    "current_light": 1.05,
    "current_heavy": 1.10,
}
CURRENT_SMOKING_STATUSES = {"current_light", "current_heavy"}
SMOKING_ACTIVITY_MESSAGE = (
    "흡연 상태는 활동 동기 가중치에만 반영되며 흡연 위해를 상쇄하지 않습니다. "
    "금연 상담 또는 지원 정보를 함께 확인하세요."
)
RECENT_CESSATION_ACTIVITY_MESSAGE = (
    "금연 후 1년 이내에는 체중 변화가 흔할 수 있어, 금연 유지와 활동 루틴을 함께 확인하세요."
)
AUDIT_KR_ACTIVITY_MESSAGE = (
    "AUDIT-KR 위험 음주 범위에서는 활동 점수 가중치를 추가하지 않고, "
    "음주 다음날 안정시 심박 변동과 절주·금주 상담 정보를 함께 확인하세요."
)


def get_sex_factor(sex: str) -> float:
    """권장 걸음수 성별 계수를 반환한다.

    Args:
        sex: "male" 또는 "female".

    Returns:
        성별 계수.
    """
    return FEMALE_STEP_FACTOR if sex == "female" else MALE_STEP_FACTOR


def get_age_base_steps(age: int) -> int:
    """연령대별 권장 걸음수 기준값을 반환한다.

    Args:
        age: 만 나이.

    Returns:
        연령대별 기준 걸음수.
    """
    if age < AGE_40_CUTOFF:
        return AGE_BASE_STEPS_UNDER_40
    if age < AGE_60_CUTOFF:
        return AGE_BASE_STEPS_40_TO_59
    if age < AGE_75_CUTOFF:
        return AGE_BASE_STEPS_60_TO_74
    return AGE_BASE_STEPS_75_PLUS


def calculate_recommended_steps(
    sex: str,
    age: int,
    bmi_category: BMICategory,
    chronic_diseases: list[str] | None = None,
) -> int:
    """사용자별 권장 걸음수를 계산한다.

    Args:
        sex: "male" 또는 "female".
        age: 만 나이.
        bmi_category: BMI 기준 분류.
        chronic_diseases: 질환별 안전 권장량을 적용할 코드 목록.

    Returns:
        반올림한 권장 걸음수.
    """
    condition_steps = [
        CONDITION_RECOMMENDED_STEPS[disease.casefold()]
        for disease in chronic_diseases or []
        if disease.casefold() in CONDITION_RECOMMENDED_STEPS
    ]
    if condition_steps:
        return min(condition_steps)
    return round(get_age_base_steps(age) * get_sex_factor(sex) * BMI_STEP_FACTORS[bmi_category])


def calculate_v1_score(actual_steps: int, recommended_steps: int) -> float:
    """권장 걸음수 대비 v1 기본 활동점수를 계산한다.

    Args:
        actual_steps: 실제 일일 걸음수.
        recommended_steps: 사용자별 권장 걸음수.

    Returns:
        v1 점수.

    Raises:
        ValueError: 권장 걸음수가 0 이하인 경우.
    """
    if recommended_steps <= 0:
        raise ValueError("recommended_steps must be greater than 0")
    achievement = min(actual_steps / recommended_steps, ACHIEVEMENT_CAP)
    return round(achievement * MAX_V1_SCORE_AT_CAP, 2)


def calculate_estimated_hr_max(age: int, formula: HRMaxFormula = "tanaka_2001") -> float:
    """HRmax 추정값을 계산한다.

    Args:
        age: 만 나이.
        formula: 회사 가이드 호환식 또는 Tanaka 2001 식.

    Returns:
        HRmax 추정값.
    """
    if formula == "tanaka_2001":
        return TANAKA_HR_MAX_BASE - TANAKA_AGE_COEFFICIENT * age
    if formula == "gellish_2007":
        return GELLISH_HR_MAX_BASE - GELLISH_AGE_COEFFICIENT * age
    if formula == "nes_2013":
        return NES_HR_MAX_BASE - NES_AGE_COEFFICIENT * age
    return GUIDE_HR_MAX_BASE - age


def calculate_target_hr_range(
    age: int,
    formula: HRMaxFormula = "tanaka_2001",
    resting_heart_rate_bpm: int | None = None,
) -> TargetHeartRateRange:
    """목표 심박 구간을 계산한다.

    Args:
        age: 만 나이.
        formula: HRmax 추정식.
        resting_heart_rate_bpm: 안정시 심박수. 있으면 Karvonen HRR 방식을 사용한다.

    Returns:
        목표 심박 하한/상한.
    """
    hr_max = calculate_estimated_hr_max(age=age, formula=formula)
    if resting_heart_rate_bpm is not None and resting_heart_rate_bpm < hr_max:
        hrr = hr_max - resting_heart_rate_bpm
        return TargetHeartRateRange(
            low_bpm=round(hrr * TARGET_HRR_LOW_RATIO + resting_heart_rate_bpm),
            high_bpm=round(hrr * TARGET_HRR_HIGH_RATIO + resting_heart_rate_bpm),
            formula=formula,
            method="karvonen_hrr",
            resting_heart_rate_bpm=resting_heart_rate_bpm,
        )
    return TargetHeartRateRange(
        low_bpm=round(hr_max * TARGET_HR_LOW_RATIO),
        high_bpm=round(hr_max * TARGET_HR_HIGH_RATIO),
        formula=formula,
    )


def calculate_resting_hr_moving_median(
    resting_hr_readings: list[int],
    *,
    drinking_next_day_flags: list[bool] | None = None,
    window_days: int = 7,
) -> int | None:
    """안정시 심박 7일 이동 중앙값을 계산한다.

    음주 다음날 HRrest outlier를 직접 점수 보정에 쓰지 않도록 flag가 있는
    날짜를 제외한다.

    Args:
        resting_hr_readings: 오래된 값부터 최신 값까지의 안정시 심박수 목록.
        drinking_next_day_flags: 같은 길이의 음주 다음날 여부 목록. True인 값은 제외한다.
        window_days: 중앙값 계산에 사용할 최근 일수.

    Returns:
        중앙값 bpm. 유효 값이 없으면 None.

    Raises:
        ValueError: flags 길이가 readings와 다르거나 window_days가 1 미만인 경우.
    """
    if window_days < 1:
        raise ValueError("window_days must be greater than or equal to 1")
    if drinking_next_day_flags is not None and len(drinking_next_day_flags) != len(
        resting_hr_readings
    ):
        raise ValueError("drinking_next_day_flags must match resting_hr_readings length")
    recent_readings = resting_hr_readings[-window_days:]
    recent_flags = (
        drinking_next_day_flags[-window_days:]
        if drinking_next_day_flags is not None
        else [False] * len(recent_readings)
    )
    filtered = sorted(
        reading for reading, skip in zip(recent_readings, recent_flags, strict=True) if not skip
    )
    if not filtered:
        return None
    middle = len(filtered) // 2
    if len(filtered) % 2:
        return filtered[middle]
    return int(((filtered[middle - 1] + filtered[middle]) / 2) + 0.5)


def calculate_hr_factor(target_hr_minutes: float | None) -> float:
    """심박수 가중 계수를 계산한다.

    Args:
        target_hr_minutes: 목표 심박 구간 유지 시간. None이면 웨어러블 미착용 fallback.

    Returns:
        0.0-1.0 범위의 심박수 가중 계수.
    """
    if target_hr_minutes is None:
        return NO_WEARABLE_HR_FACTOR
    return min(target_hr_minutes / TARGET_HR_FULL_CREDIT_MINUTES, 1.0)


def calculate_v2_score(v1_score: float, hr_factor: float) -> float:
    """심박수 가중 v2 점수를 계산한다.

    Args:
        v1_score: v1 기본 활동점수.
        hr_factor: 심박수 가중 계수.

    Returns:
        v2 점수.
    """
    multiplier = V2_BASE_MULTIPLIER + V2_HR_MULTIPLIER_WEIGHT * hr_factor
    return round(v1_score * multiplier, 2)


def calculate_percentile_bonus(user_v2: float, group_v2_scores: list[float]) -> int:
    """동일 그룹 내 백분위 보너스를 계산한다.

    Args:
        user_v2: 사용자 v2 점수.
        group_v2_scores: 비교군 v2 점수 목록. 0-100 범위 밖의 값은 outlier로 제외한다.

    Returns:
        백분위 보너스. 표본이 부족하면 0.
    """
    filtered_scores = [
        score for score in group_v2_scores if MIN_VALID_PEER_SCORE <= score <= MAX_VALID_PEER_SCORE
    ]
    if len(filtered_scores) < MIN_PERCENTILE_SAMPLE_SIZE:
        return 0

    higher_count = sum(1 for score in filtered_scores if score > user_v2)
    percentile_rank = (higher_count / len(filtered_scores)) * MAX_SCORE

    if percentile_rank <= TOP_10_PERCENT:
        return BONUS_TOP_10
    if percentile_rank <= TOP_20_PERCENT:
        return BONUS_TOP_20
    if percentile_rank <= TOP_30_PERCENT:
        return BONUS_TOP_30
    return 0


def calculate_v3_score(v2_score: float, bonus: int) -> float:
    """백분위 보너스를 반영한 v3 점수를 계산한다.

    Args:
        v2_score: v2 점수.
        bonus: 백분위 보너스.

    Returns:
        100점 상한이 적용된 v3 점수.
    """
    return round(min(MAX_SCORE, v2_score + bonus), 2)


def calculate_disease_multiplier(diseases: list[str], smoking_status: str = "never") -> float:
    """활동 동기 점수 가중치를 계산한다.

    Args:
        diseases: 만성질환 코드 목록.
        smoking_status: 흡연 상태. 만성질환 가중과 중복하지 않고 max 규칙을 적용한다.

    Returns:
        1.0-1.3 범위의 가중치.
    """
    total_addon = sum(DISEASE_WEIGHTS.get(disease.casefold(), 0.0) for disease in diseases)
    chronic_multiplier = min(1.0 + min(total_addon, MAX_DISEASE_WEIGHT_SUM), MAX_DISEASE_MULTIPLIER)
    smoking_multiplier = SMOKING_MULTIPLIERS.get(smoking_status, 1.0)
    return round(max(chronic_multiplier, smoking_multiplier), 3)


def calculate_v4_score(v3_score: float, multiplier: float) -> float:
    """만성질환 프로젝트 가중치를 반영한 v4 점수를 계산한다.

    Args:
        v3_score: v3 점수.
        multiplier: 만성질환 프로젝트 가중치.

    Returns:
        100점 상한이 적용된 v4 점수.
    """
    return round(min(MAX_SCORE, v3_score * multiplier), 2)


def build_activity_safety_messages(request: ActivityScoreRequest) -> list[str]:
    """활동점수 해석에 필요한 생활습관 안전 메시지를 구성한다.

    Args:
        request: 활동점수 요청 모델.

    Returns:
        사용자 노출용 안전 메시지 목록.
    """
    messages: list[str] = []
    if request.profile.smoking_status in CURRENT_SMOKING_STATUSES:
        messages.append(SMOKING_ACTIVITY_MESSAGE)
    elif request.profile.smoking_status == "former_lt_1y":
        messages.append(RECENT_CESSATION_ACTIVITY_MESSAGE)
    if (
        request.profile.audit_kr_score is not None
        and request.profile.audit_kr_score >= AUDIT_KR_RISK_CUTOFF
    ):
        messages.append(AUDIT_KR_ACTIVITY_MESSAGE)
    return messages


def calculate_activity_score(request: ActivityScoreRequest) -> ActivityScoreResponse:
    """활동점수 v1-v4 전체 결과를 계산한다.

    Args:
        request: 활동점수 요청 모델.

    Returns:
        BMI, 권장 걸음수, v1-v4 점수를 포함한 응답 모델.
    """
    bmi = evaluate_bmi(
        weight_kg=request.profile.weight_kg,
        height_cm=request.profile.height_cm,
        age=request.profile.age,
        sex=request.profile.sex,
        waist_cm=request.profile.waist_cm,
        body_fat_pct=request.profile.body_fat_pct,
        chronic_diseases=request.profile.chronic_diseases,
        audit_kr_score=request.profile.audit_kr_score,
    )
    recommended_steps = calculate_recommended_steps(
        sex=request.profile.sex,
        age=request.profile.age,
        bmi_category=bmi.category,
        chronic_diseases=request.profile.chronic_diseases,
    )
    v1_score = calculate_v1_score(
        actual_steps=request.daily_steps,
        recommended_steps=recommended_steps,
    )
    target_hr_range = calculate_target_hr_range(
        age=request.profile.age,
        formula=request.hrmax_formula,
        resting_heart_rate_bpm=request.profile.resting_heart_rate_bpm,
    )
    hr_factor = calculate_hr_factor(request.target_hr_minutes)
    v2_score = calculate_v2_score(v1_score=v1_score, hr_factor=hr_factor)
    percentile_bonus = calculate_percentile_bonus(
        user_v2=v2_score,
        group_v2_scores=request.group_v2_scores,
    )
    v3_score = calculate_v3_score(v2_score=v2_score, bonus=percentile_bonus)
    disease_multiplier = calculate_disease_multiplier(
        request.profile.chronic_diseases,
        smoking_status=request.profile.smoking_status,
    )
    v4_score = calculate_v4_score(v3_score=v3_score, multiplier=disease_multiplier)

    return ActivityScoreResponse(
        bmi=bmi,
        recommended_steps=recommended_steps,
        target_hr_range=target_hr_range,
        hr_factor=round(hr_factor, 3),
        percentile_bonus=percentile_bonus,
        disease_multiplier=disease_multiplier,
        v1_score=v1_score,
        v2_score=v2_score,
        v3_score=v3_score,
        v4_score=v4_score,
        safety_messages=build_activity_safety_messages(request),
    )
