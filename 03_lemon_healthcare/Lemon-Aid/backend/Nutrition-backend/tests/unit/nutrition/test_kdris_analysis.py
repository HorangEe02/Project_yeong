"""KDRIs 2025 룩업과 영양 분석 테스트."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from src.config import get_settings
from src.models.schemas.nutrition import NutrientIntake, NutrientStatus
from src.models.schemas.user import UserProfile
from src.nutrition.deficiency_analysis import analyze_nutrient_intakes, contains_forbidden_terms
from src.nutrition.kdris import get_dataset_status, get_kdris_for_profile, lookup_kdris_reference
from src.nutrition.unit_converter import convert_amount


@pytest.fixture(autouse=True)
def use_kdris_2025_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Pin this module to the promoted KDRIs 2025 dataset.

    Args:
        monkeypatch: Pytest environment patch helper.

    Yields:
        None after the cached Settings object has been reset.
    """
    monkeypatch.setenv("KDRIS_DATA_VERSION", "2025")
    monkeypatch.setenv("KDRIS_DATA_PATH", "data/nutrition_reference/kdris/kdris_2025.csv")
    monkeypatch.setenv("ALLOW_SAMPLE_KDRIS", "false")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_kdris_2025_loads_official_adult_male_references() -> None:
    """성인 남성 기본 조건에서 승인된 KDRIs 2025 기준값을 로드한다."""
    references = get_kdris_for_profile(age=30, sex="male")
    nutrient_codes = {reference.nutrient_code for reference in references}

    assert len(references) == 81
    assert len(nutrient_codes) == 49
    assert get_dataset_status() == "official_2025_approved"
    assert {reference.dataset_version for reference in references} == {"2025"}
    assert {reference.review_status for reference in references} == {"approved"}
    assert references[0].source_manifest_version == "2.0"
    assert {"vitamin_c_mg", "vitamin_a_ug", "potassium_mg", "magnesium_mg"}.issubset(nutrient_codes)


def test_kdris_lookup_by_nutrient_code() -> None:
    """영양소 코드로 기준값을 조회한다."""
    reference = lookup_kdris_reference("vitamin_c_mg", age=30, sex="female")

    assert reference is not None
    assert reference.reference_amount == 100
    assert reference.reference_unit == "mg"


def test_pregnancy_specific_references_append_without_dropping_baseline() -> None:
    """임신 조건에서는 baseline 기준값과 임신 추가 기준값을 함께 반환한다."""
    references = get_kdris_for_profile(age=30, sex="female", pregnancy_status="pregnant")
    baseline_vitamin_c = [
        reference
        for reference in references
        if reference.nutrient_code == "vitamin_c_mg"
        and reference.pregnancy_status == "none"
        and reference.reference_type == "RNI"
    ]
    baseline_protein = [
        reference
        for reference in references
        if reference.nutrient_code == "protein_g"
        and reference.pregnancy_status == "none"
        and reference.reference_type == "RNI"
    ]
    pregnant_vitamin_a = [
        reference
        for reference in references
        if reference.nutrient_code == "vitamin_a_ug"
        and reference.pregnancy_status == "pregnant"
        and reference.reference_type == "RNI"
    ]
    pregnant_protein = [
        reference
        for reference in references
        if reference.nutrient_code == "protein_g"
        and reference.pregnancy_status == "pregnant"
        and reference.reference_type == "RNI"
    ]

    assert len(references) == 137
    assert len({reference.nutrient_code for reference in references}) == 49
    assert {reference.reference_amount for reference in baseline_vitamin_c} == {100}
    assert {reference.reference_amount for reference in baseline_protein} == {50}
    assert {reference.reference_amount for reference in pregnant_vitamin_a} == {70}
    assert {reference.condition_detail for reference in pregnant_protein} == {
        "pregnancy_trimester_2_additional",
        "pregnancy_trimester_3_additional",
    }


def test_elderly_profile_uses_older_adult_vitamin_d_reference() -> None:
    """65세 이상 프로필은 노인 연령대 비타민 D 기준값을 사용한다."""
    adult_references = get_kdris_for_profile(age=64, sex="female")
    elderly_references = get_kdris_for_profile(age=75, sex="female")

    adult_vitamin_d = next(
        reference
        for reference in adult_references
        if reference.nutrient_code == "vitamin_d_ug" and reference.reference_type == "AI"
    )
    elderly_vitamin_d = next(
        reference
        for reference in elderly_references
        if reference.nutrient_code == "vitamin_d_ug" and reference.reference_type == "AI"
    )

    assert adult_vitamin_d.reference_amount == 10
    assert elderly_vitamin_d.reference_amount == 15
    assert elderly_vitamin_d.age_min == 75
    assert elderly_vitamin_d.source_id == "kns_2025_kdris_publication"


def test_unit_conversion_supports_mass_and_vitamin_d_iu() -> None:
    """질량 단위와 비타민D IU 환산을 검증한다."""
    assert convert_amount(1, "g", "mg") == 1000
    assert convert_amount(1000, "ug", "mg") == 1
    assert convert_amount(400, "iu", "ug", nutrient_code="vitamin_d_ug") == 10
    assert convert_amount(5000, "ug", "ug RAE", nutrient_code="vitamin_a_ug") == 5000
    assert convert_amount(350, "mg supplemental", "mg", nutrient_code="magnesium_mg") == 350


def test_nutrient_analysis_flags_deficient_and_risky() -> None:
    """비타민C 부족 가능성과 비타민A UL 초과 가능성을 분류한다."""
    profile = UserProfile(age=30, sex="male", height_cm=170, weight_kg=70)
    response = analyze_nutrient_intakes(
        profile=profile,
        intakes=[
            NutrientIntake(nutrient_code="vitamin_c_mg", amount=30, unit="mg"),
            NutrientIntake(nutrient_code="vitamin_a_ug", amount=5000, unit="ug"),
        ],
    )

    by_code = {result.nutrient_code: result for result in response.results}

    assert by_code["vitamin_c_mg"].status == NutrientStatus.AT_RISK_INADEQUATE
    assert by_code["vitamin_c_mg"].reference_type == "RNI"
    assert by_code["vitamin_c_mg"].source_id == "kns_2025_kdris_publication"
    assert by_code["vitamin_c_mg"].priority == 1
    assert by_code["vitamin_a_ug"].status == NutrientStatus.RISKY
    assert response.dataset_status == "official_2025_approved"
    assert response.dataset_version == "2025"
    assert response.source_manifest_version == "2.0"
    assert not contains_forbidden_terms([result.user_message for result in response.results])


def test_chronic_priority_boosts_only_low_or_deficient_nutrients() -> None:
    """만성질환 룩업은 이미 낮음/부족인 영양소의 확인 순서에만 반영한다."""
    profile = UserProfile(
        age=30,
        sex="male",
        height_cm=170,
        weight_kg=70,
        chronic_diseases=["htn"],
    )
    response = analyze_nutrient_intakes(
        profile=profile,
        intakes=[
            NutrientIntake(nutrient_code="vitamin_c_mg", amount=20, unit="mg"),
            NutrientIntake(nutrient_code="potassium_mg", amount=2000, unit="mg"),
            NutrientIntake(nutrient_code="magnesium_mg", amount=350, unit="mg"),
        ],
    )

    by_code = {result.nutrient_code: result for result in response.results}

    assert by_code["vitamin_c_mg"].status == NutrientStatus.AT_RISK_INADEQUATE
    assert by_code["vitamin_c_mg"].ratio == 0.2
    assert by_code["vitamin_c_mg"].priority == 2
    assert by_code["potassium_mg"].status == NutrientStatus.AT_RISK_INADEQUATE
    assert by_code["potassium_mg"].ratio == 0.57
    assert by_code["potassium_mg"].priority == 1
    assert by_code["potassium_mg"].priority_context == ["hypertension"]
    assert by_code["potassium_mg"].priority_source_ids == ["nhlbi_dash"]
    assert by_code["potassium_mg"].user_message == (
        "현재 입력과 만성질환 정보를 함께 볼 때 우선 확인 대상입니다."
    )
    assert by_code["magnesium_mg"].status == NutrientStatus.EXCESSIVE_NEAR_UL
    assert by_code["magnesium_mg"].priority == 0
    assert by_code["magnesium_mg"].priority_context == []
    guide_keys = {guide.guide_key for guide in response.condition_nutrition_guides}
    assert "dash_hypertension" in guide_keys


def test_unknown_chronic_disease_keeps_ratio_based_priority() -> None:
    """미정의 만성질환 코드는 무시하고 기존 ratio 기반 우선순위를 유지한다."""
    profile = UserProfile(
        age=30,
        sex="male",
        height_cm=170,
        weight_kg=70,
        chronic_diseases=["unknown-condition"],
    )
    response = analyze_nutrient_intakes(
        profile=profile,
        intakes=[
            NutrientIntake(nutrient_code="vitamin_c_mg", amount=20, unit="mg"),
            NutrientIntake(nutrient_code="potassium_mg", amount=2000, unit="mg"),
        ],
    )

    by_code = {result.nutrient_code: result for result in response.results}

    assert by_code["vitamin_c_mg"].priority == 1
    assert by_code["potassium_mg"].priority == 2
    assert by_code["potassium_mg"].priority_context == []


def test_ckd_caution_nutrients_do_not_receive_priority_boost() -> None:
    """신장질환은 일반 KDRIs 자동 평가 대신 referral route로 분기한다."""
    profile = UserProfile(
        age=30,
        sex="male",
        height_cm=170,
        weight_kg=70,
        chronic_diseases=["ckd"],
    )
    response = analyze_nutrient_intakes(
        profile=profile,
        intakes=[
            NutrientIntake(nutrient_code="vitamin_c_mg", amount=20, unit="mg"),
            NutrientIntake(nutrient_code="potassium_mg", amount=2000, unit="mg"),
        ],
    )

    assert response.routing_status == "referral_required"
    assert response.results == []
    assert response.safety_messages
    assert response.condition_nutrition_guides[0].guide_key == "kdoqi_ckd_nutrition"
    assert response.condition_nutrition_guides[0].referral_required is True


def test_condition_nutrition_guides_surface_diabetes_and_hypertension_routes() -> None:
    """당뇨·고혈압 입력은 질환별 공식 영양 가이드 route를 함께 반환한다."""
    profile = UserProfile(
        age=30,
        sex="male",
        height_cm=170,
        weight_kg=70,
        chronic_diseases=["type-2 diabetes", "HTN"],
    )
    response = analyze_nutrient_intakes(
        profile=profile,
        intakes=[
            NutrientIntake(nutrient_code="fiber_g", amount=10, unit="g"),
            NutrientIntake(nutrient_code="potassium_mg", amount=2000, unit="mg"),
        ],
    )

    guides = {guide.guide_key: guide for guide in response.condition_nutrition_guides}
    assert response.routing_status == "ok"
    assert set(guides) == {"ada_diabetes_nutrition", "dash_hypertension"}
    assert guides["ada_diabetes_nutrition"].source_id == "ada_standards_of_care"
    assert guides["dash_hypertension"].source_id == "nhlbi_dash"
    assert guides["ada_diabetes_nutrition"].referral_required is False
    assert not contains_forbidden_terms(
        [guide.user_message for guide in response.condition_nutrition_guides]
    )


def test_pregnancy_routes_to_referral_required() -> None:
    """임신 상태에서는 일반 KDRIs 자동 평가를 보류하고 상담 경로로 분기한다."""
    profile = UserProfile(
        age=30,
        sex="female",
        height_cm=165,
        weight_kg=60,
        pregnancy_status="pregnant",
    )
    response = analyze_nutrient_intakes(
        profile=profile,
        intakes=[NutrientIntake(nutrient_code="folate_ug", amount=400, unit="ug")],
    )

    assert response.routing_status == "referral_required"
    assert response.results == []
    assert any("임신·수유" in message for message in response.safety_messages)
    assert not contains_forbidden_terms(response.safety_messages)


def test_pediatric_profile_routes_to_referral_required() -> None:
    """소아·청소년은 일반 성인 자동 평가를 보류하고 상담 경로로 분기한다."""
    profile = UserProfile(age=16, sex="female", height_cm=160, weight_kg=55)
    response = analyze_nutrient_intakes(
        profile=profile,
        intakes=[NutrientIntake(nutrient_code="vitamin_c_mg", amount=80, unit="mg")],
    )

    assert response.routing_status == "referral_required"
    assert response.results == []
    assert any("소아·청소년" in message for message in response.safety_messages)
    assert not contains_forbidden_terms(response.safety_messages)


def test_medications_route_to_referral_required() -> None:
    """약물 입력이 있으면 약물-영양소 상호작용 확인 경로로 분기한다."""
    profile = UserProfile(
        age=30,
        sex="male",
        height_cm=170,
        weight_kg=70,
        medications=["warfarin"],
    )
    response = analyze_nutrient_intakes(
        profile=profile,
        intakes=[NutrientIntake(nutrient_code="vitamin_k_ug", amount=75, unit="ug")],
    )

    assert response.routing_status == "referral_required"
    assert response.results == []
    assert any("약물-영양소 상호작용" in message for message in response.safety_messages)
    assert not contains_forbidden_terms(response.safety_messages)


def test_current_smoker_vitamin_c_reference_adds_iom_margin() -> None:
    """현재 흡연자는 비타민 C 기준에 +35mg 참고치를 반영한다."""
    profile = UserProfile(
        age=30,
        sex="male",
        height_cm=170,
        weight_kg=70,
        smoking_status="current_light",
    )
    response = analyze_nutrient_intakes(
        profile=profile,
        intakes=[NutrientIntake(nutrient_code="vitamin_c_mg", amount=100, unit="mg")],
    )

    result = response.results[0]
    assert result.reference_amount == 135
    assert result.status == NutrientStatus.BELOW_RDA
    assert response.safety_messages


def test_audit_kr_risk_prioritizes_alcohol_support_nutrients() -> None:
    """AUDIT-KR 위험 범위에서는 B1·엽산·마그네슘·아연 확인을 우선한다."""
    profile = UserProfile(
        age=30,
        sex="male",
        height_cm=170,
        weight_kg=70,
        audit_kr_score=8,
    )
    response = analyze_nutrient_intakes(
        profile=profile,
        intakes=[
            NutrientIntake(nutrient_code="thiamin_mg", amount=0.4, unit="mg"),
            NutrientIntake(nutrient_code="zinc_mg", amount=3, unit="mg"),
        ],
    )

    by_code = {result.nutrient_code: result for result in response.results}
    assert by_code["thiamin_mg"].priority_context == ["audit_kr_risk"]
    assert by_code["zinc_mg"].priority_context == ["audit_kr_risk"]
    assert response.safety_messages


def test_nutrient_interaction_messages_flag_balance_review() -> None:
    """Ca/Mg, Vit D/Mg, Zn/Cu, Ca/Fe 상호작용 확인 메시지를 생성한다."""
    profile = UserProfile(age=30, sex="male", height_cm=170, weight_kg=70)
    response = analyze_nutrient_intakes(
        profile=profile,
        intakes=[
            NutrientIntake(nutrient_code="calcium_mg", amount=1000, unit="mg"),
            NutrientIntake(nutrient_code="magnesium_mg", amount=100, unit="mg"),
            NutrientIntake(nutrient_code="vitamin_d_ug", amount=15, unit="ug"),
            NutrientIntake(nutrient_code="zinc_mg", amount=55, unit="mg"),
            NutrientIntake(nutrient_code="iron_mg", amount=5, unit="mg"),
        ],
    )

    messages = "\n".join(response.safety_messages)

    assert "칼슘:마그네슘" in messages
    assert "비타민 D" in messages
    assert "아연 50mg/day 초과" in messages
    assert "칼슘과 철분" in messages
    assert not contains_forbidden_terms(response.safety_messages)


def test_chronic_priority_messages_do_not_contain_forbidden_terms() -> None:
    """만성질환 우선 확인 문구가 치료·처방 표현을 포함하지 않는지 검증한다."""
    profile = UserProfile(
        age=30,
        sex="male",
        height_cm=170,
        weight_kg=70,
        chronic_diseases=["diabetes", "hypertension"],
    )
    response = analyze_nutrient_intakes(
        profile=profile,
        intakes=[
            NutrientIntake(nutrient_code="fiber_g", amount=10, unit="g"),
            NutrientIntake(nutrient_code="potassium_mg", amount=2000, unit="mg"),
        ],
    )

    messages = [result.user_message for result in response.results]
    assert all("우선 확인 대상" in result.user_message for result in response.results)
    assert not contains_forbidden_terms(messages)


def test_unknown_nutrient_reference_raises() -> None:
    """기준값이 없는 영양소는 명확한 오류로 처리한다."""
    profile = UserProfile(age=30, sex="male", height_cm=170, weight_kg=70)

    with pytest.raises(ValueError, match="KDRIs reference not found"):
        analyze_nutrient_intakes(
            profile=profile,
            intakes=[NutrientIntake(nutrient_code="unknown", amount=1, unit="mg")],
        )
