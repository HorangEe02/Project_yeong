"""BMI 산출식과 보완 지표 flag."""

from __future__ import annotations

from typing import Final

from src.models.schemas.algorithm import BMICategory, BMIRegion, BMIResult
from src.models.schemas.user import Sex

UNDERWEIGHT_CUTOFF = 18.5
CM_PER_METER = 100
BMI_DECIMALS = 1
WHR_DECIMALS = 3
WAIST_TO_HEIGHT_RISK_CUTOFF = 0.5
MALE_WAIST_OBESITY_CUTOFF_CM = 90.0
FEMALE_WAIST_OBESITY_CUTOFF_CM = 85.0
MALE_BODY_FAT_HIGH_CUTOFF = 26.0
FEMALE_BODY_FAT_HIGH_CUTOFF = 36.0
SENIOR_AGE_CUTOFF = 65
AUDIT_KR_RISK_CUTOFF = 3

_CUTOFFS: Final[dict[BMIRegion, tuple[tuple[float, BMICategory], ...]]] = {
    "asia_kr": (
        (UNDERWEIGHT_CUTOFF, BMICategory.UNDERWEIGHT),
        (23.0, BMICategory.NORMAL),
        (25.0, BMICategory.OVERWEIGHT),
        (30.0, BMICategory.OBESE_1),
        (35.0, BMICategory.OBESE_2),
    ),
    "who_standard": (
        (UNDERWEIGHT_CUTOFF, BMICategory.UNDERWEIGHT),
        (25.0, BMICategory.NORMAL),
        (30.0, BMICategory.OVERWEIGHT),
        (35.0, BMICategory.OBESE_1),
        (40.0, BMICategory.OBESE_2),
    ),
}

_CRITERIA_SOURCES: Final[dict[BMIRegion, str]] = {
    "asia_kr": "KSSO 2022",
    "who_standard": "WHO 2000 / Lancet 2004",
}


def calculate_bmi(weight_kg: float, height_cm: float) -> float:
    """BMI를 계산한다.

    Args:
        weight_kg: 체중(kg).
        height_cm: 키(cm).

    Returns:
        소수점 1자리로 반올림한 BMI.

    Raises:
        ValueError: 키 또는 체중이 0 이하인 경우.
    """
    if weight_kg <= 0:
        raise ValueError("weight_kg must be greater than 0")
    if height_cm <= 0:
        raise ValueError("height_cm must be greater than 0")

    height_m = height_cm / CM_PER_METER
    return round(weight_kg / (height_m**2), BMI_DECIMALS)


def classify_bmi(bmi: float, region: BMIRegion = "asia_kr") -> BMICategory:
    """선택 기준으로 BMI를 분류한다.

    Args:
        bmi: BMI 값.
        region: BMI 기준 체계.

    Returns:
        BMI 기준 분류.
    """
    for cutoff, category in _CUTOFFS[region]:
        if bmi < cutoff:
            return category
    return BMICategory.OBESE_3


def _body_fat_flag(body_fat_pct: float | None, sex: Sex | None) -> str | None:
    """체지방률 참고 flag를 반환한다.

    Args:
        body_fat_pct: 체지방률(%).
        sex: 성별. None이면 flag를 계산하지 않는다.

    Returns:
        "high", "normal" 또는 None.
    """
    if body_fat_pct is None or sex is None:
        return None
    threshold = MALE_BODY_FAT_HIGH_CUTOFF if sex == "male" else FEMALE_BODY_FAT_HIGH_CUTOFF
    return "high" if body_fat_pct >= threshold else "normal"


def _waist_circumference_obesity(waist_cm: float | None, sex: Sex | None) -> bool | None:
    """KSSO 성별 허리둘레 기준 복부비만 여부를 반환한다.

    Args:
        waist_cm: 허리둘레(cm).
        sex: 성별. None이면 성별별 기준을 계산하지 않는다.

    Returns:
        성별 기준 복부비만 여부. 허리둘레나 성별이 없으면 None.
    """
    if waist_cm is None or sex is None:
        return None
    cutoff = MALE_WAIST_OBESITY_CUTOFF_CM if sex == "male" else FEMALE_WAIST_OBESITY_CUTOFF_CM
    return waist_cm >= cutoff


def evaluate_bmi(
    weight_kg: float,
    height_cm: float,
    *,
    region: BMIRegion = "asia_kr",
    age: int | None = None,
    sex: Sex | None = None,
    waist_cm: float | None = None,
    body_fat_pct: float | None = None,
    chronic_diseases: list[str] | None = None,
    audit_kr_score: int | None = None,
) -> BMIResult:
    """BMI 값과 분류를 함께 반환한다.

    Args:
        weight_kg: 체중(kg).
        height_cm: 키(cm).
        region: BMI 기준 체계.
        age: 고령자 안내문 판별용 나이.
        sex: 체지방률 flag 판별용 성별.
        waist_cm: 허리-신장비 산출용 허리둘레.
        body_fat_pct: 체지방률(%).
        chronic_diseases: 만성질환 맥락 안내용 코드 목록.
        audit_kr_score: 위험 음주 맥락의 허리둘레 보조 입력 안내용 점수.

    Returns:
        BMI 계산 결과.

    Raises:
        ValueError: 키 또는 체중이 0 이하인 경우.
    """
    bmi = calculate_bmi(weight_kg=weight_kg, height_cm=height_cm)
    category = classify_bmi(bmi, region=region)
    notes: list[str] = []
    waist_to_height_ratio: float | None = None
    central_obesity: bool | None = None
    waist_circumference_obesity = _waist_circumference_obesity(waist_cm=waist_cm, sex=sex)

    if waist_cm is not None:
        waist_to_height_ratio = round(waist_cm / height_cm, WHR_DECIMALS)
        central_obesity = waist_to_height_ratio >= WAIST_TO_HEIGHT_RISK_CUTOFF
        if category in {BMICategory.UNDERWEIGHT, BMICategory.NORMAL} and central_obesity:
            notes.append("BMI 분류는 낮지만 허리-신장비가 높아 복부 비만 위험 신호가 있습니다.")
        if waist_circumference_obesity:
            notes.append("성별 허리둘레 기준상 복부 비만 위험 신호가 있어 BMI와 함께 확인하세요.")

    body_fat_flag = _body_fat_flag(body_fat_pct=body_fat_pct, sex=sex)
    if body_fat_flag == "high" and category in {BMICategory.UNDERWEIGHT, BMICategory.NORMAL}:
        notes.append("BMI 분류는 낮지만 체지방률이 높은 편입니다. 근육량 점검을 권장합니다.")
    if body_fat_flag == "normal" and category in {
        BMICategory.OBESE_1,
        BMICategory.OBESE_2,
        BMICategory.OBESE_3,
    }:
        notes.append("BMI는 높지만 체지방률이 정상 범위라 근육량에 따른 상승 가능성이 있습니다.")

    sarcopenic_obesity_suspected = False
    if age is not None and age >= SENIOR_AGE_CUTOFF:
        if category == BMICategory.OBESE_1:
            notes.append("65세 이상은 단순 BMI보다 근육량과 허리둘레를 함께 보는 것이 좋습니다.")
        if category == BMICategory.NORMAL and body_fat_flag == "high":
            sarcopenic_obesity_suspected = True
            notes.append("고령·정상 BMI·높은 체지방률 조합은 근감소성 비만 가능성을 시사합니다.")

    normalized_diseases = {disease.casefold() for disease in chronic_diseases or []}
    if normalized_diseases and category == BMICategory.OVERWEIGHT:
        notes.append(
            "만성질환이 있으면 BMI 23 미만 유지가 더 유익할 수 있어 전문가 상담을 권장합니다."
        )

    if audit_kr_score is not None and audit_kr_score >= AUDIT_KR_RISK_CUTOFF and waist_cm is None:
        notes.append(
            "음주 위험 범위에서는 BMI만으로 복부 지방을 보기 어려워 허리둘레 입력을 권장합니다."
        )

    return BMIResult(
        bmi=bmi,
        category=category,
        region=region,
        criteria_source=_CRITERIA_SOURCES[region],
        notes=notes,
        waist_to_height_ratio=waist_to_height_ratio,
        central_obesity=central_obesity,
        waist_circumference_obesity=waist_circumference_obesity,
        body_fat_flag=body_fat_flag,  # type: ignore[arg-type]
        sarcopenic_obesity_suspected=sarcopenic_obesity_suspected or None,
    )
