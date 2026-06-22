"""BMR/TDEE 산출식."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Literal

from src.models.schemas.user import Sex

BMR_WEIGHT_COEFFICIENT = 10.0
BMR_HEIGHT_COEFFICIENT = 6.25
BMR_AGE_COEFFICIENT = 5.0
MALE_BMR_CONSTANT = 5.0
FEMALE_BMR_CONSTANT = -161.0
STEPS_LIGHT_ACTIVITY_CUTOFF = 5000
STEPS_MODERATE_ACTIVITY_CUTOFF = 7500
STEPS_ACTIVE_CUTOFF = 10000
STEPS_VERY_ACTIVE_CUTOFF = 12500
SEDENTARY_FACTOR = 1.200
LIGHT_FACTOR = 1.375
MODERATE_FACTOR = 1.550
ACTIVE_FACTOR = 1.725
VERY_ACTIVE_FACTOR = 1.900
ENERGY_DECIMALS = 0
CADENCE_MODERATE_CUTOFF_STEPS_PER_MIN = 100.0
CADENCE_MODERATE_PLUS_CUTOFF_STEPS_PER_MIN = 110.0
CADENCE_BRISK_CUTOFF_STEPS_PER_MIN = 120.0
CADENCE_VIGOROUS_CUTOFF_STEPS_PER_MIN = 130.0
CADENCE_NO_WALKING_METS = 0.0
CADENCE_LIGHT_WALKING_METS = 2.0
CADENCE_MODERATE_WALKING_METS = 3.0
CADENCE_MODERATE_PLUS_WALKING_METS = 4.0
CADENCE_BRISK_WALKING_METS = 5.0
CADENCE_VIGOROUS_WALKING_METS = 6.0
KEYTEL_KJ_TO_KCAL = 4.184
KEYTEL_MALE_BASE = -55.0969
KEYTEL_MALE_HR_COEFFICIENT = 0.6309
KEYTEL_MALE_WEIGHT_COEFFICIENT = 0.1988
KEYTEL_MALE_AGE_COEFFICIENT = 0.2017
KEYTEL_FEMALE_BASE = -20.4022
KEYTEL_FEMALE_HR_COEFFICIENT = 0.4472
KEYTEL_FEMALE_WEIGHT_COEFFICIENT = -0.1263
KEYTEL_FEMALE_AGE_COEFFICIENT = 0.074
KATCH_MCARDLE_BASE = 370.0
KATCH_MCARDLE_LBM_COEFFICIENT = 21.6
CUNNINGHAM_BASE = 370.0
CUNNINGHAM_FFM_COEFFICIENT = 21.6
MIN_BODY_FAT_PERCENT = 10.0
MAX_BODY_FAT_PERCENT = 55.0
ExerciseActivityCode = Literal[
    "walking_slow",
    "walking_moderate",
    "walking_brisk",
    "walking_very_brisk",
    "jogging_general",
    "running_6mph",
    "cycling_leisure",
    "cycling_commute_self_selected",
    "resistance_training_multiple",
    "resistance_training_squats",
    "yoga_hatha",
]
EXERCISE_ACTIVITY_METS: Mapping[ExerciseActivityCode, float] = MappingProxyType(
    {
        "walking_slow": 3.0,
        "walking_moderate": 3.5,
        "walking_brisk": 4.3,
        "walking_very_brisk": 5.0,
        "jogging_general": 7.0,
        "running_6mph": 9.8,
        "cycling_leisure": 4.0,
        "cycling_commute_self_selected": 6.8,
        "resistance_training_multiple": 3.5,
        "resistance_training_squats": 5.0,
        "yoga_hatha": 2.5,
    }
)


def calculate_mifflin_bmr(weight_kg: float, height_cm: float, age: int, sex: Sex) -> float:
    """Mifflin-St Jeor 공식으로 예상 BMR을 계산한다.

    Args:
        weight_kg: 체중(kg).
        height_cm: 키(cm).
        age: 만 나이.
        sex: "male" 또는 "female".

    Returns:
        예상 BMR(kcal/day).
    """
    base = (
        BMR_WEIGHT_COEFFICIENT * weight_kg
        + BMR_HEIGHT_COEFFICIENT * height_cm
        - BMR_AGE_COEFFICIENT * age
    )
    sex_constant = MALE_BMR_CONSTANT if sex == "male" else FEMALE_BMR_CONSTANT
    return round(base + sex_constant, ENERGY_DECIMALS)


def calculate_lean_body_mass_from_body_fat(weight_kg: float, body_fat_pct: float) -> float:
    """체중과 체지방률로 제지방량을 계산한다.

    Args:
        weight_kg: 체중(kg).
        body_fat_pct: 체지방률(%).

    Returns:
        제지방량(kg).

    Raises:
        ValueError: 체지방률이 적용 가능한 범위를 벗어난 경우.
    """
    if not MIN_BODY_FAT_PERCENT <= body_fat_pct <= MAX_BODY_FAT_PERCENT:
        raise ValueError("body_fat_pct must be between 10 and 55")
    return weight_kg * (1 - (body_fat_pct / 100))


def calculate_cunningham_bmr(lean_body_mass_kg: float) -> float:
    """Cunningham 1991 공식으로 제지방량 기반 예상 BMR을 계산한다.

    Args:
        lean_body_mass_kg: 제지방량(kg).

    Returns:
        예상 BMR(kcal/day).

    Raises:
        ValueError: 제지방량이 음수인 경우.
    """
    if lean_body_mass_kg < 0:
        raise ValueError("lean_body_mass_kg must be non-negative")
    return round(
        CUNNINGHAM_BASE + CUNNINGHAM_FFM_COEFFICIENT * lean_body_mass_kg,
        ENERGY_DECIMALS,
    )


def calculate_katch_mcardle_bmr(weight_kg: float, body_fat_pct: float) -> float:
    """Katch-McArdle 공식으로 체지방률 기반 예상 BMR을 계산한다.

    Args:
        weight_kg: 체중(kg).
        body_fat_pct: 체지방률(%).

    Returns:
        예상 BMR(kcal/day).

    Raises:
        ValueError: 체지방률이 적용 가능한 범위를 벗어난 경우.
    """
    lean_body_mass = calculate_lean_body_mass_from_body_fat(
        weight_kg=weight_kg,
        body_fat_pct=body_fat_pct,
    )
    return round(
        KATCH_MCARDLE_BASE + KATCH_MCARDLE_LBM_COEFFICIENT * lean_body_mass, ENERGY_DECIMALS
    )


def calculate_bmr(
    weight_kg: float,
    height_cm: float,
    age: int,
    sex: Sex,
    body_fat_pct: float | None = None,
) -> float:
    """예상 BMR을 계산한다.

    체지방률이 신뢰 가능한 범위로 입력되면 Katch-McArdle/Cunningham 1991과
    동일한 제지방량 기반 공식을 우선하고, 그렇지 않으면 Mifflin-St Jeor
    공식을 사용한다.

    Args:
        weight_kg: 체중(kg).
        height_cm: 키(cm).
        age: 만 나이.
        sex: "male" 또는 "female".
        body_fat_pct: 체지방률(%). 10~55 범위에서만 Katch-McArdle 적용.

    Returns:
        예상 BMR(kcal/day).
    """
    if body_fat_pct is not None and MIN_BODY_FAT_PERCENT <= body_fat_pct <= MAX_BODY_FAT_PERCENT:
        return calculate_katch_mcardle_bmr(weight_kg=weight_kg, body_fat_pct=body_fat_pct)
    return calculate_mifflin_bmr(weight_kg=weight_kg, height_cm=height_cm, age=age, sex=sex)


def get_activity_factor(daily_steps: int) -> float:
    """일일 걸음수 기반 활동계수를 반환한다.

    Args:
        daily_steps: 일일 걸음수.

    Returns:
        프로젝트 가이드 활동계수.
    """
    if daily_steps < STEPS_LIGHT_ACTIVITY_CUTOFF:
        return SEDENTARY_FACTOR
    if daily_steps < STEPS_MODERATE_ACTIVITY_CUTOFF:
        return LIGHT_FACTOR
    if daily_steps < STEPS_ACTIVE_CUTOFF:
        return MODERATE_FACTOR
    if daily_steps < STEPS_VERY_ACTIVE_CUTOFF:
        return ACTIVE_FACTOR
    return VERY_ACTIVE_FACTOR


def calculate_exercise_kcal_from_mets(mets: float, weight_kg: float, minutes: float) -> float:
    """METs와 운동 시간으로 의도 운동 열량을 계산한다.

    Args:
        mets: 운동 METs 값.
        weight_kg: 체중(kg).
        minutes: 운동 시간(분).

    Returns:
        운동 소비 열량(kcal).

    Raises:
        ValueError: 입력값이 음수인 경우.
    """
    if mets < 0 or weight_kg < 0 or minutes < 0:
        raise ValueError("mets, weight_kg and minutes must be non-negative")
    return mets * 3.5 * weight_kg / 200 * minutes


def lookup_walking_cadence_mets(cadence_steps_per_min: float) -> float:
    """보행 cadence를 Tudor-Locke 2018 휴리스틱 METs로 변환한다.

    Args:
        cadence_steps_per_min: 분당 걸음수.

    Returns:
        Cadence 기반 보행 METs 값.

    Raises:
        ValueError: cadence가 음수인 경우.
    """
    if cadence_steps_per_min < 0:
        raise ValueError("cadence_steps_per_min must be non-negative")
    if cadence_steps_per_min == 0:
        return CADENCE_NO_WALKING_METS
    if cadence_steps_per_min >= CADENCE_VIGOROUS_CUTOFF_STEPS_PER_MIN:
        return CADENCE_VIGOROUS_WALKING_METS
    if cadence_steps_per_min >= CADENCE_BRISK_CUTOFF_STEPS_PER_MIN:
        return CADENCE_BRISK_WALKING_METS
    if cadence_steps_per_min >= CADENCE_MODERATE_PLUS_CUTOFF_STEPS_PER_MIN:
        return CADENCE_MODERATE_PLUS_WALKING_METS
    if cadence_steps_per_min >= CADENCE_MODERATE_CUTOFF_STEPS_PER_MIN:
        return CADENCE_MODERATE_WALKING_METS
    return CADENCE_LIGHT_WALKING_METS


def calculate_exercise_kcal_from_walking_cadence(
    cadence_steps_per_min: float,
    weight_kg: float,
    minutes: float,
) -> float:
    """보행 cadence와 시간으로 wearable 기반 보행 열량을 계산한다.

    Args:
        cadence_steps_per_min: 분당 걸음수.
        weight_kg: 체중(kg).
        minutes: 보행 시간(분).

    Returns:
        보행 소비 열량(kcal).

    Raises:
        ValueError: cadence, 체중 또는 시간이 음수인 경우.
    """
    mets = lookup_walking_cadence_mets(cadence_steps_per_min)
    return calculate_exercise_kcal_from_mets(mets=mets, weight_kg=weight_kg, minutes=minutes)


def calculate_exercise_kcal_from_heart_rate(
    average_heart_rate_bpm: float,
    weight_kg: float,
    age: int,
    sex: Sex,
    minutes: float,
) -> float:
    """평균 운동 심박수로 Keytel 2005 기반 운동 열량을 계산한다.

    Args:
        average_heart_rate_bpm: 운동 구간 평균 심박수(bpm).
        weight_kg: 체중(kg).
        age: 만 나이.
        sex: "male" 또는 "female".
        minutes: 운동 시간(분).

    Returns:
        심박 기반 운동 소비 열량(kcal). 낮은 심박 잡음으로 음수가 나오면 0으로 제한한다.

    Raises:
        ValueError: 평균 심박수, 체중, 나이 또는 시간이 유효하지 않은 경우.
    """
    if average_heart_rate_bpm <= 0:
        raise ValueError("average_heart_rate_bpm must be positive")
    if weight_kg < 0 or age < 0 or minutes < 0:
        raise ValueError("weight_kg, age and minutes must be non-negative")

    if sex == "male":
        kj_per_min = (
            KEYTEL_MALE_BASE
            + KEYTEL_MALE_HR_COEFFICIENT * average_heart_rate_bpm
            + KEYTEL_MALE_WEIGHT_COEFFICIENT * weight_kg
            + KEYTEL_MALE_AGE_COEFFICIENT * age
        )
    else:
        kj_per_min = (
            KEYTEL_FEMALE_BASE
            + KEYTEL_FEMALE_HR_COEFFICIENT * average_heart_rate_bpm
            + KEYTEL_FEMALE_WEIGHT_COEFFICIENT * weight_kg
            + KEYTEL_FEMALE_AGE_COEFFICIENT * age
        )
    return max(0.0, kj_per_min / KEYTEL_KJ_TO_KCAL * minutes)


def lookup_exercise_activity_mets(activity_code: ExerciseActivityCode) -> float:
    """운동 활동 코드에 대응하는 Compendium 2011 METs 값을 반환한다.

    Args:
        activity_code: Lemon-Aid가 지원하는 운동 활동 코드.

    Returns:
        활동 코드에 대응하는 METs 값.

    Raises:
        KeyError: 지원하지 않는 활동 코드인 경우.
    """
    return EXERCISE_ACTIVITY_METS[activity_code]


def calculate_exercise_kcal_from_activity(
    activity_code: ExerciseActivityCode,
    weight_kg: float,
    minutes: float,
) -> float:
    """운동 활동 코드와 시간으로 의도 운동 열량을 계산한다.

    Args:
        activity_code: Lemon-Aid가 지원하는 운동 활동 코드.
        weight_kg: 체중(kg).
        minutes: 운동 시간(분).

    Returns:
        운동 소비 열량(kcal).

    Raises:
        ValueError: 체중 또는 운동 시간이 음수인 경우.
    """
    mets = lookup_exercise_activity_mets(activity_code)
    return calculate_exercise_kcal_from_mets(mets=mets, weight_kg=weight_kg, minutes=minutes)


def calculate_tdee_with_activity_codes(
    estimated_bmr: float,
    daily_steps: int,
    *,
    weight_kg: float,
    intentional_activities: list[tuple[ExerciseActivityCode, float]] | None = None,
) -> float:
    """걸음수 PAL과 활동 코드 기반 의도 운동을 합산한 예상 TDEE를 계산한다.

    Args:
        estimated_bmr: 예상 BMR(kcal/day).
        daily_steps: 일일 걸음수.
        weight_kg: 운동 열량 계산용 체중(kg).
        intentional_activities: (운동 활동 코드, 운동 시간 분) 목록.

    Returns:
        예상 TDEE(kcal/day).
    """
    intentional_exercises = [
        (lookup_exercise_activity_mets(activity_code), minutes)
        for activity_code, minutes in intentional_activities or []
    ]
    return calculate_tdee(
        estimated_bmr=estimated_bmr,
        daily_steps=daily_steps,
        weight_kg=weight_kg,
        intentional_exercises=intentional_exercises,
    )


def calculate_tdee(
    estimated_bmr: float,
    daily_steps: int,
    *,
    weight_kg: float | None = None,
    age: int | None = None,
    sex: Sex | None = None,
    intentional_exercises: list[tuple[float, float]] | None = None,
    walking_cadence_steps_per_min: float | None = None,
    walking_cadence_minutes: float = 0.0,
    exercise_average_heart_rate_bpm: float | None = None,
    heart_rate_exercise_minutes: float = 0.0,
) -> float:
    """예상 BMR과 활동계수로 예상 TDEE를 계산한다.

    Args:
        estimated_bmr: 예상 BMR(kcal/day).
        daily_steps: 일일 걸음수.
        weight_kg: METs 기반 운동 열량 계산용 체중.
        age: 심박 기반 운동 열량 계산용 만 나이.
        sex: 심박 기반 운동 열량 계산용 성별.
        intentional_exercises: (METs, minutes) 목록.
        walking_cadence_steps_per_min: wearable 보행 cadence(steps/min).
        walking_cadence_minutes: cadence가 관측된 보행 시간(분).
        exercise_average_heart_rate_bpm: 운동 구간 평균 심박수(bpm).
        heart_rate_exercise_minutes: 평균 심박수가 관측된 운동 시간(분).

    Returns:
        예상 TDEE(kcal/day).

    Raises:
        ValueError: 의도 운동, cadence, 또는 심박 입력이 불완전한 경우.
    """
    exercise_kcal = 0.0
    if intentional_exercises:
        if weight_kg is None:
            raise ValueError("weight_kg is required when intentional_exercises are provided")
        exercise_kcal = sum(
            calculate_exercise_kcal_from_mets(mets=mets, weight_kg=weight_kg, minutes=minutes)
            for mets, minutes in intentional_exercises
        )
    if walking_cadence_steps_per_min is not None or walking_cadence_minutes > 0:
        if weight_kg is None:
            raise ValueError("weight_kg is required when walking cadence is provided")
        if walking_cadence_steps_per_min is None or walking_cadence_minutes <= 0:
            raise ValueError("walking cadence requires both cadence and positive minutes")
        exercise_kcal += calculate_exercise_kcal_from_walking_cadence(
            cadence_steps_per_min=walking_cadence_steps_per_min,
            weight_kg=weight_kg,
            minutes=walking_cadence_minutes,
        )
    if exercise_average_heart_rate_bpm is not None or heart_rate_exercise_minutes > 0:
        if weight_kg is None or age is None or sex is None:
            raise ValueError("weight_kg, age and sex are required when heart rate is provided")
        if exercise_average_heart_rate_bpm is None or heart_rate_exercise_minutes <= 0:
            raise ValueError("heart rate exercise requires both average heart rate and minutes")
        exercise_kcal += calculate_exercise_kcal_from_heart_rate(
            average_heart_rate_bpm=exercise_average_heart_rate_bpm,
            weight_kg=weight_kg,
            age=age,
            sex=sex,
            minutes=heart_rate_exercise_minutes,
        )
    return round(estimated_bmr * get_activity_factor(daily_steps) + exercise_kcal, ENERGY_DECIMALS)
