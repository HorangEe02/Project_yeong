"""5-card 종합 분석 산출 로직 단위 테스트."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from src.config import get_settings
from src.models.schemas.supplement_comprehensive import ComprehensiveAnalysisRequest
from src.nutrition.comprehensive import compute_comprehensive

FORBIDDEN_USER_TERMS = ("진단", "치료", "처방", "복용량 변경", "효능")


@pytest.fixture(autouse=True)
def _pin_kdris_2025(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Pin comprehensive analysis to the official 2025 KDRIs.

    Production requires ``KDRIS_DATA_VERSION=2025``; the 2020-sample fixture omits
    some upper limits (e.g. magnesium), so without pinning these tests would depend
    on the ambient default and be non-hermetic — green locally (.env sets 2025) but
    red on CI defaults (2020-sample). Mirrors test_kdris_analysis.py: the cached
    Settings singleton must be reset so the env override actually takes effect.
    """
    monkeypatch.setenv("KDRIS_DATA_VERSION", "2025")
    monkeypatch.setenv("KDRIS_DATA_PATH", "data/nutrition_reference/kdris/kdris_2025.csv")
    monkeypatch.setenv("ALLOW_SAMPLE_KDRIS", "false")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _complete_kdris_ingredients(*, vitamin_c_mg: float) -> list[dict[str, object]]:
    """비타민 C 외 부족 항목이 상위 카드 산출을 가리지 않도록 기준량 입력을 만든다."""
    return [
        {
            "display_name": "Vitamin A",
            "nutrient_code": "vitamin_a_ug",
            "amount": 750,
            "unit": "ug",
        },
        {
            "display_name": "Vitamin B1",
            "nutrient_code": "vitamin_b1_mg",
            "amount": 1.2,
            "unit": "mg",
        },
        {
            "display_name": "Vitamin B6",
            "nutrient_code": "vitamin_b6_mg",
            "amount": 1.4,
            "unit": "mg",
        },
        {
            "display_name": "Vitamin B12",
            "nutrient_code": "vitamin_b12_ug",
            "amount": 2.4,
            "unit": "ug",
        },
        {
            "display_name": "Vitamin C",
            "nutrient_code": "vitamin_c_mg",
            "amount": vitamin_c_mg,
            "unit": "mg",
        },
        {
            "display_name": "Vitamin D",
            "nutrient_code": "vitamin_d_ug",
            "amount": 10,
            "unit": "ug",
        },
        {
            "display_name": "Vitamin E",
            "nutrient_code": "vitamin_e_mg",
            "amount": 12,
            "unit": "mg",
        },
        {
            "display_name": "Vitamin K",
            "nutrient_code": "vitamin_k_ug",
            "amount": 75,
            "unit": "ug",
        },
        {
            "display_name": "Calcium",
            "nutrient_code": "calcium_mg",
            "amount": 800,
            "unit": "mg",
        },
        {
            "display_name": "Magnesium",
            "nutrient_code": "magnesium_mg",
            "amount": 350,
            "unit": "mg",
        },
        {
            "display_name": "Iron",
            "nutrient_code": "iron_mg",
            "amount": 10,
            "unit": "mg",
        },
        {
            "display_name": "Zinc",
            "nutrient_code": "zinc_mg",
            "amount": 10,
            "unit": "mg",
        },
        {
            "display_name": "Omega-3",
            "nutrient_code": "omega3_mg",
            "amount": 1000,
            "unit": "mg",
        },
    ]


def _make_request(
    *,
    ingredients: list[dict[str, object]],
    chronic_conditions: list[str] | None = None,
    persona: str = "B",
    age: int = 52,
    sex: str = "male",
    smoking_status: str = "never",
    audit_kr_score: int | None = None,
    medications: list[str] | None = None,
) -> ComprehensiveAnalysisRequest:
    """테스트용 요청 생성 헬퍼."""
    return ComprehensiveAnalysisRequest.model_validate(
        {
            "analysis_id": "test-001",
            "persona": persona,
            "user_profile": {
                "age": age,
                "sex": sex,
                "chronic_conditions": chronic_conditions or [],
                "smoking_status": smoking_status,
                "audit_kr_score": audit_kr_score,
                "medications": medications or [],
            },
            "ingredients": ingredients,
        }
    )


class TestComputeComprehensive:
    """compute_comprehensive 산출 로직 검증."""

    def test_empty_ingredients_returns_warning(self) -> None:
        """빈 ingredient 입력 시 모든 카드가 비고 warning 발생."""
        result = compute_comprehensive(_make_request(ingredients=[]))
        assert result.warnings == ["no_recognized_nutrient_codes"]
        assert result.deficient_nutrients  # KDRIs 권장량 0 섭취 → 모두 부족
        assert result.excessive_nutrients == []
        assert result.cautionary_components == []
        assert result.diet_score < 100

    def test_omega3_high_dose_triggers_cautions(self) -> None:
        """오메가3 + 만성질환자 페르소나 시 high-severity caution(출혈 위험) 포함."""
        result = compute_comprehensive(
            _make_request(
                ingredients=[
                    {
                        "display_name": "Omega-3 Fish Oil",
                        "nutrient_code": "omega3_mg",
                        "amount": 1800,
                        "unit": "mg",
                    },
                ],
                chronic_conditions=["cardiovascular"],
                persona="B",
            )
        )
        severities = {c.severity for c in result.cautionary_components}
        assert (
            "high" in severities
        ), f"오메가3 → bleeding risk 'high' 누락: {result.cautionary_components}"

    def test_chronic_disease_indications_auto_mapped(self) -> None:
        """오메가3 ingredient → cardiovascular/dyslipidemia 등 자동 매핑."""
        result = compute_comprehensive(
            _make_request(
                ingredients=[
                    {
                        "display_name": "오메가-3 (EPA + DHA)",
                        "nutrient_code": "omega3_mg",
                        "amount": 1800,
                        "unit": "mg",
                    },
                ],
            )
        )
        assert "cardiovascular" in result.chronic_disease_indications
        assert "dyslipidemia" in result.chronic_disease_indications

    def test_persona_b_user_condition_boosts_relevance(self) -> None:
        """사용자가 명시한 condition 의 relevance_score 가 +0.15 가중치 적용."""
        result_a = compute_comprehensive(
            _make_request(
                ingredients=[
                    {
                        "display_name": "오메가-3",
                        "nutrient_code": "omega3_mg",
                        "amount": 1800,
                        "unit": "mg",
                    },
                ],
                chronic_conditions=[],  # 사용자 미지정
            )
        )
        result_b = compute_comprehensive(
            _make_request(
                ingredients=[
                    {
                        "display_name": "오메가-3",
                        "nutrient_code": "omega3_mg",
                        "amount": 1800,
                        "unit": "mg",
                    },
                ],
                chronic_conditions=["cardiovascular"],  # 사용자 지정 → boost
            )
        )
        score_a = next(
            t.relevance_score for t in result_a.purpose_targets if t.condition == "cardiovascular"
        )
        score_b = next(
            t.relevance_score for t in result_b.purpose_targets if t.condition == "cardiovascular"
        )
        assert score_b > score_a, f"user condition boost 실패: {score_a} vs {score_b}"

    def test_diet_score_in_valid_range(self) -> None:
        """diet_score 는 0~100 범위 안에 있다."""
        result = compute_comprehensive(
            _make_request(
                ingredients=[
                    {
                        "display_name": "비타민 C",
                        "nutrient_code": "vitamin_c_mg",
                        "amount": 100,
                        "unit": "mg",
                    },
                    {
                        "display_name": "비타민 D",
                        "nutrient_code": "vitamin_d_ug",
                        "amount": 10,
                        "unit": "ug",
                    },
                ],
            )
        )
        assert 0 <= result.diet_score <= 100
        assert result.diet_score_label in {"excellent", "good", "moderate", "warning", "critical"}

    def test_excessive_nutrient_detected_when_above_upper_limit(self) -> None:
        """KDRIs 상한 초과 영양소가 excessive_nutrients 에 포함된다."""
        # 마그네슘 upper_limit 350mg → 1000mg 입력 → 약 2.86배 초과
        result = compute_comprehensive(
            _make_request(
                ingredients=[
                    {
                        "display_name": "Magnesium",
                        "nutrient_code": "magnesium_mg",
                        "amount": 1000,
                        "unit": "mg",
                    },
                ],
            )
        )
        assert any(e.nutrient_code == "magnesium_mg" for e in result.excessive_nutrients)
        mg_entry = next(e for e in result.excessive_nutrients if e.nutrient_code == "magnesium_mg")
        assert mg_entry.excess_ratio == pytest.approx(1000 / 350, abs=0.02)

    def test_water_soluble_vitamin_without_kdris_upper_limit_is_not_excessive(self) -> None:
        """공식 KDRIs에 상한이 없는 수용성 비타민(B1=thiamin)은 과다로 분류하지 않는다.

        KDRIs 모듈 조회가 실제로 작동함을 검증한다: 분석기 코드 `vitamin_b1_mg`는
        CSV의 `thiamin_mg`로 alias 되며, thiamin은 KDRIs 상한이 없으므로 인라인
        baseline의 임시 상한(1000mg)을 적용하지 않는다.
        """
        result = compute_comprehensive(
            _make_request(
                ingredients=[
                    {
                        "display_name": "Vitamin B1",
                        "nutrient_code": "vitamin_b1_mg",
                        "amount": 5000,
                        "unit": "mg",
                    },
                ],
            )
        )
        assert all(e.nutrient_code != "vitamin_b1_mg" for e in result.excessive_nutrients)

    def test_omega3_without_kdris_reference_falls_back_to_inline_upper_limit(self) -> None:
        """KDRIs에 단일 기준이 없는 오메가-3는 인라인 baseline 상한(3000mg)으로 폴백한다.

        KDRIs는 오메가-3를 EPA+DHA/ALA로 분리해 단일 스칼라 기준이 없으므로, 분석기는
        인라인 baseline 상한을 사용해야 하며 5000mg 입력은 과다로 분류된다.
        """
        result = compute_comprehensive(
            _make_request(
                ingredients=[
                    {
                        "display_name": "Omega-3",
                        "nutrient_code": "omega3_mg",
                        "amount": 5000,
                        "unit": "mg",
                    },
                ],
            )
        )
        omega3 = next(
            (e for e in result.excessive_nutrients if e.nutrient_code == "omega3_mg"), None
        )
        assert omega3 is not None
        assert omega3.upper_limit == 3000

    def test_unknown_ingredient_does_not_crash(self) -> None:
        """nutrient_code 가 없는 ingredient 도 안전하게 처리된다."""
        result = compute_comprehensive(
            _make_request(
                ingredients=[
                    {
                        "display_name": "Mystery Extract",
                        "nutrient_code": None,
                        "amount": 100,
                        "unit": "mg",
                    },
                ],
            )
        )
        assert isinstance(result.deficient_nutrients, list)
        assert "no_recognized_nutrient_codes" in result.warnings

    def test_algorithm_version_recorded(self) -> None:
        """algorithm_version 이 응답에 포함된다."""
        result = compute_comprehensive(_make_request(ingredients=[]))
        assert result.algorithm_version == "comprehensive-v1"

    def test_smoker_high_beta_carotene_triggers_high_caution(self) -> None:
        """흡연자에게 베타카로틴 고함량 자동 경고를 노출한다."""
        result = compute_comprehensive(
            _make_request(
                ingredients=[
                    {
                        "display_name": "Beta Carotene",
                        "nutrient_code": "beta_carotene_mg",
                        "amount": 6,
                        "unit": "mg",
                    }
                ],
                smoking_status="current_heavy",
            )
        )

        assert any(
            caution.reason == "smoker_beta_carotene_vitamin_a_risk" and caution.severity == "high"
            for caution in result.cautionary_components
        )

    def test_current_smoker_vitamin_c_card_uses_iom_plus_35mg_reference(self) -> None:
        """현재 흡연자는 종합 부족 카드의 비타민 C 기준도 +35mg로 보정한다."""
        result = compute_comprehensive(
            _make_request(
                ingredients=_complete_kdris_ingredients(vitamin_c_mg=120),
                smoking_status="current_light",
            )
        )

        vitamin_c = next(
            nutrient
            for nutrient in result.deficient_nutrients
            if nutrient.nutrient_code == "vitamin_c_mg"
        )
        assert vitamin_c.recommended_intake == 135
        assert vitamin_c.deficit_ratio == pytest.approx((135 - 120) / 135, abs=0.0001)
        assert "smoker_vitamin_c_reference_iom_plus_35mg" in result.warnings

    def test_recent_former_smoker_does_not_raise_vitamin_c_card_reference(self) -> None:
        """금연 1년 이내는 안전 경고에는 포함하되 비타민 C +35mg 기준은 적용하지 않는다."""
        result = compute_comprehensive(
            _make_request(
                ingredients=_complete_kdris_ingredients(vitamin_c_mg=100),
                smoking_status="former_lt_1y",
            )
        )

        assert all(
            nutrient.nutrient_code != "vitamin_c_mg" for nutrient in result.deficient_nutrients
        )
        assert "smoker_vitamin_c_reference_iom_plus_35mg" not in result.warnings

    def test_audit_kr_vitamin_a_and_acetaminophen_trigger_cautions(self) -> None:
        """AUDIT-KR 위험 범위에서는 Vit A와 아세트아미노펜 경고를 분리한다."""
        result = compute_comprehensive(
            _make_request(
                ingredients=[
                    {
                        "display_name": "Vitamin A",
                        "nutrient_code": "vitamin_a_ug",
                        "amount": 3000,
                        "unit": "ug",
                    }
                ],
                audit_kr_score=8,
                medications=["acetaminophen"],
            )
        )
        reasons = {caution.reason for caution in result.cautionary_components}

        assert "alcohol_vitamin_a_liver_risk" in reasons
        assert "alcohol_acetaminophen_liver_risk" in reasons

    def test_audit_kr_dependence_pauses_supplement_recommendation(self) -> None:
        """AUDIT-KR 의존 cut-off 이상에서는 추천 중단 warning을 남긴다."""
        result = compute_comprehensive(
            _make_request(
                ingredients=[
                    {
                        "display_name": "Vitamin C",
                        "nutrient_code": "vitamin_c_mg",
                        "amount": 100,
                        "unit": "mg",
                    }
                ],
                sex="female",
                audit_kr_score=8,
            )
        )

        assert "supplement_recommendation_paused_audit_kr" in result.warnings
        dependence_caution = next(
            caution
            for caution in result.cautionary_components
            if caution.reason == "audit_kr_dependence_cutoff"
        )
        assert "1577-0199" in dependence_caution.message
        assert "중독관리통합지원센터" in dependence_caution.message

    def test_wellness_goal_targets_include_extended_goal_matrix(self) -> None:
        """면역·수면·장 건강 목적별 매트릭스를 응답에 별도 노출한다."""
        result = compute_comprehensive(
            _make_request(
                ingredients=[
                    {
                        "display_name": "Vitamin C",
                        "nutrient_code": "vitamin_c_mg",
                        "amount": 100,
                        "unit": "mg",
                    },
                    {
                        "display_name": "Magnesium",
                        "nutrient_code": "magnesium_mg",
                        "amount": 200,
                        "unit": "mg",
                    },
                    {
                        "display_name": "Probiotic blend",
                        "nutrient_code": None,
                        "amount": 1,
                        "unit": "capsule",
                    },
                ],
            )
        )

        goals = {target.goal for target in result.wellness_goal_targets}
        assert {"immune_support", "sleep_support", "gut_health"}.issubset(goals)
        assert all(
            not any(term in target.message for term in FORBIDDEN_USER_TERMS)
            for target in result.wellness_goal_targets
        )

    def test_specific_drug_supplement_interactions_are_prioritized(self) -> None:
        """와파린·레보티록신 조합은 일반 경고보다 구체적 상호작용을 우선 표시한다."""
        result = compute_comprehensive(
            _make_request(
                ingredients=[
                    {
                        "display_name": "Vitamin K",
                        "nutrient_code": "vitamin_k_ug",
                        "amount": 120,
                        "unit": "ug",
                    },
                    {
                        "display_name": "Calcium",
                        "nutrient_code": "calcium_mg",
                        "amount": 500,
                        "unit": "mg",
                    },
                    {
                        "display_name": "Omega-3",
                        "nutrient_code": "omega3_mg",
                        "amount": 1800,
                        "unit": "mg",
                    },
                ],
                medications=["warfarin", "levothyroxine"],
            )
        )
        reasons = [caution.reason for caution in result.cautionary_components]

        assert reasons[0] == "warfarin_vitamin_k_consistency_review"
        assert "drug_absorption_spacing:levothyroxine" in reasons
        assert "warfarin_omega3_bleeding_risk" in reasons

    def test_warfarin_botanical_bleeding_interactions_are_flagged(self) -> None:
        """와파린 복용 중 은행잎·마늘 보충제는 botanical 출혈 위험으로 표시한다."""
        result = compute_comprehensive(
            _make_request(
                ingredients=[
                    {
                        "display_name": "Ginkgo Biloba",
                        "nutrient_code": "ginkgo_biloba_mg",
                        "amount": 120,
                        "unit": "mg",
                    },
                    {
                        "display_name": "마늘 추출물",
                        "nutrient_code": None,
                        "amount": 500,
                        "unit": "mg",
                    },
                ],
                medications=["warfarin"],
            )
        )
        botanical_cautions = [
            caution
            for caution in result.cautionary_components
            if caution.reason == "warfarin_botanical_bleeding_risk"
        ]

        assert len(botanical_cautions) == 2
        assert all(caution.severity == "high" for caution in botanical_cautions)

    def test_liver_goal_alcohol_risk_and_nac_are_consult_routed(self) -> None:
        """음주 위험·간질환 프로필에서는 간 건강 보조제 상담 분기를 강화한다."""
        result = compute_comprehensive(
            _make_request(
                ingredients=[
                    {
                        "display_name": "Milk Thistle",
                        "nutrient_code": None,
                        "amount": 130,
                        "unit": "mg",
                    },
                    {
                        "display_name": "NAC",
                        "nutrient_code": None,
                        "amount": 600,
                        "unit": "mg",
                    },
                ],
                chronic_conditions=["liver_disease"],
                audit_kr_score=8,
            )
        )
        reasons = {caution.reason for caution in result.cautionary_components}
        goals = {target.goal for target in result.wellness_goal_targets}

        assert "liver_health" in goals
        assert "alcohol_liver_supplement_consult" in reasons
        assert "nac_medicine_class_review" in reasons
        assert "liver_disease_supplement_consult" in reasons

    def test_pregnancy_high_vitamin_a_triggers_high_caution(self) -> None:
        """임신 중 고함량 레티놀형 비타민 A는 별도 high caution으로 분기한다."""
        request = _make_request(
            ingredients=[
                {
                    "display_name": "Vitamin A (retinol)",
                    "nutrient_code": "retinol_ug",
                    "amount": 10000,
                    "unit": "IU",
                }
            ],
            sex="female",
        )
        payload = request.model_dump()
        payload["user_profile"]["is_pregnant"] = True

        result = compute_comprehensive(ComprehensiveAnalysisRequest.model_validate(payload))

        assert any(
            caution.reason == "pregnancy_vitamin_a_ul_risk" and caution.severity == "high"
            for caution in result.cautionary_components
        )

    def test_pregnancy_beta_carotene_does_not_trigger_retinol_ul_caution(self) -> None:
        """임신 중 베타카로틴 표기는 레티놀형 vitamin A high caution으로 분류하지 않는다."""
        request = _make_request(
            ingredients=[
                {
                    "display_name": "Vitamin A (as beta-carotene)",
                    "nutrient_code": "vitamin_a_ug",
                    "amount": 3000,
                    "unit": "ug",
                }
            ],
            sex="female",
        )
        payload = request.model_dump()
        payload["user_profile"]["is_pregnant"] = True

        result = compute_comprehensive(ComprehensiveAnalysisRequest.model_validate(payload))
        pregnancy_cautions = {
            caution.reason
            for caution in result.cautionary_components
            if "pregnancy" in caution.reason
        }

        assert "pregnancy_vitamin_a_ul_risk" not in pregnancy_cautions
        assert "pregnancy_vitamin_a_form_review" not in pregnancy_cautions

    def test_pregnancy_generic_high_vitamin_a_requests_form_review(self) -> None:
        """임신 중 vitamin A 형태가 불명확하면 high가 아니라 label review caution을 반환한다."""
        request = _make_request(
            ingredients=[
                {
                    "display_name": "Vitamin A",
                    "nutrient_code": "vitamin_a_ug",
                    "amount": 3000,
                    "unit": "ug",
                }
            ],
            sex="female",
        )
        payload = request.model_dump()
        payload["user_profile"]["is_pregnant"] = True

        result = compute_comprehensive(ComprehensiveAnalysisRequest.model_validate(payload))
        caution_by_reason = {caution.reason: caution for caution in result.cautionary_components}

        assert "pregnancy_vitamin_a_ul_risk" not in caution_by_reason
        assert caution_by_reason["pregnancy_vitamin_a_form_review"].severity == "medium"

    def test_user_visible_messages_avoid_medical_claim_terms(self) -> None:
        """종합 분석 사용자 노출 문구는 의료 단정 어휘를 피한다."""
        result = compute_comprehensive(
            _make_request(
                ingredients=[
                    {
                        "display_name": "Vitamin K",
                        "nutrient_code": "vitamin_k_ug",
                        "amount": 120,
                        "unit": "ug",
                    },
                    {
                        "display_name": "Vitamin E",
                        "nutrient_code": "vitamin_e_mg",
                        "amount": 120,
                        "unit": "mg",
                    },
                    {
                        "display_name": "Calcium",
                        "nutrient_code": "calcium_mg",
                        "amount": 500,
                        "unit": "mg",
                    },
                ],
                chronic_conditions=["cardiovascular"],
                medications=["warfarin", "chemo"],
            )
        )
        messages = [
            result.diet_score_message,
            *[caution.message for caution in result.cautionary_components],
            *[target.message for target in result.purpose_targets],
            *[target.message for target in result.wellness_goal_targets],
        ]

        assert not any(term in message for term in FORBIDDEN_USER_TERMS for message in messages)
