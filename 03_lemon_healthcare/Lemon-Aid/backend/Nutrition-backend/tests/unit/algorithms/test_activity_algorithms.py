"""활동점수 알고리즘 테스트."""

from __future__ import annotations

import pytest
from src.algorithms.activity import (
    calculate_activity_score,
    calculate_disease_multiplier,
    calculate_hr_factor,
    calculate_percentile_bonus,
    calculate_recommended_steps,
    calculate_resting_hr_moving_median,
    calculate_target_hr_range,
    calculate_v1_score,
    calculate_v2_score,
    calculate_v3_score,
    calculate_v4_score,
)
from src.algorithms.bmi import calculate_bmi, classify_bmi, evaluate_bmi
from src.models.schemas.algorithm import ActivityScoreRequest, BMICategory
from src.models.schemas.user import UserProfile


@pytest.mark.parametrize(
    ("weight_kg", "height_cm", "expected_bmi", "expected_category"),
    [
        (50.0, 170.0, 17.3, BMICategory.UNDERWEIGHT),
        (60.0, 170.0, 20.8, BMICategory.NORMAL),
        (70.0, 170.0, 24.2, BMICategory.OVERWEIGHT),
        (80.0, 170.0, 27.7, BMICategory.OBESE_1),
        (90.0, 170.0, 31.1, BMICategory.OBESE_2),
        (105.0, 170.0, 36.3, BMICategory.OBESE_3),
        (53.4, 170.0, 18.5, BMICategory.NORMAL),
        (66.4, 170.0, 23.0, BMICategory.OVERWEIGHT),
    ],
)
def test_bmi_classification(
    weight_kg: float,
    height_cm: float,
    expected_bmi: float,
    expected_category: BMICategory,
) -> None:
    """BMI 경계값과 한국·아시아 기준 분류를 검증한다."""
    bmi = calculate_bmi(weight_kg=weight_kg, height_cm=height_cm)

    assert bmi == pytest.approx(expected_bmi, abs=0.1)
    assert classify_bmi(bmi) == expected_category


def test_bmi_classification_supports_who_standard_region() -> None:
    """WHO 기준을 선택하면 동일 BMI도 다른 기준으로 분류할 수 있다."""
    assert classify_bmi(32.0, region="who_standard") == BMICategory.OBESE_1


def test_bmi_evaluation_flags_ksso_waist_circumference_obesity() -> None:
    """성별 허리둘레 기준 복부비만 flag를 WHtR와 별도로 노출한다."""
    male = evaluate_bmi(weight_kg=62.0, height_cm=170.0, sex="male", waist_cm=90.0)
    female = evaluate_bmi(weight_kg=55.0, height_cm=165.0, sex="female", waist_cm=85.0)
    without_sex = evaluate_bmi(weight_kg=55.0, height_cm=165.0, waist_cm=85.0)

    assert male.waist_circumference_obesity is True
    assert female.waist_circumference_obesity is True
    assert without_sex.waist_circumference_obesity is None
    assert any("성별 허리둘레 기준" in note for note in male.notes)


def test_bmi_evaluation_recommends_waist_input_for_audit_kr_risk() -> None:
    """AUDIT-KR 위험 범위에서 허리둘레가 없으면 WHtR 보조 입력을 안내한다."""
    result = evaluate_bmi(
        weight_kg=72.0,
        height_cm=170.0,
        sex="male",
        audit_kr_score=3,
    )

    assert any("허리둘레 입력" in note for note in result.notes)
    assert result.waist_to_height_ratio is None


def test_bmi_evaluation_skips_alcohol_waist_prompt_when_waist_exists() -> None:
    """음주 위험이어도 허리둘레가 있으면 중복 입력 안내를 반복하지 않는다."""
    result = evaluate_bmi(
        weight_kg=72.0,
        height_cm=170.0,
        sex="male",
        waist_cm=82.0,
        audit_kr_score=3,
    )

    assert not any("허리둘레 입력" in note for note in result.notes)
    assert result.waist_to_height_ratio == pytest.approx(0.482, abs=0.001)


def test_v1_recommended_steps_50f_obese1() -> None:
    """50대 여성 비만1단계 권장 걸음수 예시를 재현한다."""
    steps = calculate_recommended_steps("female", 50, BMICategory.OBESE_1)

    assert steps == 7980


def test_v1_score_caps_at_120_percent() -> None:
    """권장 걸음수 대비 120% 초과 달성은 100점으로 제한된다."""
    score = calculate_v1_score(actual_steps=15960, recommended_steps=7980)

    assert score == pytest.approx(100.0, abs=0.01)


def test_v2_heart_rate_fallback_and_score() -> None:
    """웨어러블 미착용 fallback과 심박수 가중 점수를 검증한다."""
    assert calculate_hr_factor(None) == 0.7
    assert calculate_hr_factor(20) == pytest.approx(0.667, abs=0.01)

    target_range = calculate_target_hr_range(age=50)
    assert (target_range.low_bpm, target_range.high_bpm) == (111, 131)
    guide_range = calculate_target_hr_range(age=50, formula="guide_220_age")
    assert (guide_range.low_bpm, guide_range.high_bpm) == (109, 129)

    score = calculate_v2_score(v1_score=77.5, hr_factor=0.667)
    assert score == pytest.approx(69.7, abs=0.5)


def test_v2_target_hr_uses_karvonen_when_resting_hr_is_available() -> None:
    """HRrest 입력이 있으면 ACSM HRR 범위로 목표 심박을 계산한다."""
    target_range = calculate_target_hr_range(age=50, resting_heart_rate_bpm=68)

    assert (target_range.low_bpm, target_range.high_bpm) == (110, 130)
    assert target_range.method == "karvonen_hrr"
    assert target_range.resting_heart_rate_bpm == 68


def test_resting_hr_moving_median_excludes_drinking_next_day_outliers() -> None:
    """음주 다음날 HRrest flag는 7일 이동 중앙값 계산에서 제외한다."""
    median = calculate_resting_hr_moving_median(
        [60, 61, 90, 62, 63, 64, 65],
        drinking_next_day_flags=[False, False, True, False, False, False, False],
    )

    assert median == 63


def test_v3_percentile_bonus_requires_minimum_sample() -> None:
    """비교군 표본이 100명 미만이면 백분위 보너스를 주지 않는다."""
    assert calculate_percentile_bonus(70.0, [50.0] * 99) == 0


def test_v3_percentile_bonus_and_cap() -> None:
    """상위 10% 보너스와 v3 100점 상한을 검증한다."""
    group = [50.0] * 95 + [80.0] * 5

    assert calculate_percentile_bonus(80.0, group) == 10
    assert calculate_v3_score(95.0, 10) == 100.0


def test_v3_percentile_bonus_filters_invalid_peer_outliers() -> None:
    """0-100 범위 밖의 비교군 v2 점수는 outlier로 제외한다."""
    group = [50.0] * 100 + [-1.0, 120.0, 999.0]

    assert calculate_percentile_bonus(80.0, group) == 10


def test_v4_disease_multiplier_ignores_unknown_codes() -> None:
    """미정의 질환 코드는 만성질환 프로젝트 가중치에서 무시한다."""
    assert calculate_disease_multiplier(["covid", "diabetes"]) == 1.10
    assert calculate_disease_multiplier(["diabetes", "hypertension"]) == 1.20
    assert calculate_v4_score(72.7, 1.20) == pytest.approx(87.2, abs=0.1)


def test_v4_smoking_multiplier_uses_max_not_stacked() -> None:
    """흡연 가중치는 만성질환 가중치와 중복 합산하지 않고 더 큰 값을 사용한다."""
    assert calculate_disease_multiplier(["diabetes"], "current_heavy") == 1.10
    assert calculate_disease_multiplier(["cardiovascular"], "current_heavy") == 1.15
    assert (
        calculate_disease_multiplier(
            ["diabetes", "hypertension", "cardiovascular"],
            "current_heavy",
        )
        == 1.30
    )


def test_chronic_condition_recommended_steps_override_general_target() -> None:
    """만성질환 권장 걸음수는 일반 나이/BMI 목표보다 보수적인 값을 사용한다."""
    steps = calculate_recommended_steps(
        "female",
        50,
        BMICategory.OBESE_1,
        chronic_diseases=["diabetes", "hypertension"],
    )

    assert steps == 7500


def test_activity_score_50f_obese1_example() -> None:
    """50대 여성 비만1단계 활동점수 v1-v4 흐름을 검증한다."""
    request = ActivityScoreRequest(
        profile=UserProfile(
            age=50,
            sex="female",
            height_cm=160,
            weight_kg=68,
            chronic_diseases=["diabetes", "hypertension"],
            resting_heart_rate_bpm=68,
        ),
        daily_steps=7000,
        target_hr_minutes=20,
    )

    response = calculate_activity_score(request)

    assert response.bmi.category == BMICategory.OBESE_1
    assert response.recommended_steps == 7500
    assert response.v1_score == pytest.approx(77.78, abs=0.1)
    assert response.v2_score == pytest.approx(70.0, abs=0.1)
    assert response.percentile_bonus == 0
    assert response.v4_score == pytest.approx(84.0, abs=0.2)
    assert response.score_label == "활동 동기 점수"
    assert response.target_hr_range.method == "karvonen_hrr"


def test_activity_score_surfaces_smoking_and_alcohol_guardrails() -> None:
    """흡연·음주 맥락은 점수 변경과 별개로 안전 안내에 노출한다."""
    request = ActivityScoreRequest(
        profile=UserProfile(
            age=45,
            sex="male",
            height_cm=175,
            weight_kg=82,
            smoking_status="current_heavy",
            audit_kr_score=3,
        ),
        daily_steps=8000,
        target_hr_minutes=None,
    )

    response = calculate_activity_score(request)

    assert response.disease_multiplier == 1.10
    assert len(response.safety_messages) == 2
    assert "금연 상담" in response.safety_messages[0]
    assert "활동 점수 가중치를 추가하지 않고" in response.safety_messages[1]


def test_activity_score_surfaces_recent_cessation_weight_message() -> None:
    """금연 1년 이내 사용자는 흡연 중 문구 대신 금연 유지·체중 변화 안내를 받는다."""
    request = ActivityScoreRequest(
        profile=UserProfile(
            age=45,
            sex="male",
            height_cm=175,
            weight_kg=82,
            smoking_status="former_lt_1y",
        ),
        daily_steps=8000,
        target_hr_minutes=None,
    )

    response = calculate_activity_score(request)

    assert response.disease_multiplier == 1.05
    assert len(response.safety_messages) == 1
    assert "금연 후 1년 이내" in response.safety_messages[0]
    assert "흡연 상태" not in response.safety_messages[0]
