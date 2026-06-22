"""Condition-specific nutrition guide routing tests."""

from __future__ import annotations

from src.nutrition.chronic_nutrition_guidance import get_condition_nutrition_guides


def test_condition_nutrition_guides_are_deduplicated_and_source_backed() -> None:
    """Alias 입력을 canonical condition과 공식 guide route로 정규화한다."""
    guides = get_condition_nutrition_guides(
        ["HTN", "high blood pressure", "type-2 diabetes", "unknown"]
    )

    guide_by_key = {guide.guide_key: guide for guide in guides}

    assert set(guide_by_key) == {"ada_diabetes_nutrition", "dash_hypertension"}
    assert guide_by_key["dash_hypertension"].condition_codes == ["hypertension"]
    assert guide_by_key["dash_hypertension"].source_id == "nhlbi_dash"
    assert guide_by_key["ada_diabetes_nutrition"].source_id == "ada_standards_of_care"


def test_condition_nutrition_guides_mark_ckd_and_liver_routes_as_referral() -> None:
    """CKD·간질환 guide는 일반 KDRIs 자동 분석 보류 route로 표시한다."""
    guides = get_condition_nutrition_guides(["kidney disease", "liver cirrhosis"])
    guide_by_key = {guide.guide_key: guide for guide in guides}

    assert guide_by_key["kdoqi_ckd_nutrition"].referral_required is True
    assert guide_by_key["easl_liver_nutrition"].referral_required is True
    assert "phosphorus_mg" in guide_by_key["kdoqi_ckd_nutrition"].focus_nutrients
    assert "protein_g" in guide_by_key["easl_liver_nutrition"].focus_nutrients
