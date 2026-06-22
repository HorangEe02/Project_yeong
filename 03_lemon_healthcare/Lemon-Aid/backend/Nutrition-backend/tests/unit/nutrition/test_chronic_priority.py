"""Chronic-condition nutrient priority lookup tests."""

from __future__ import annotations

from src.nutrition.chronic_priority import (
    canonicalize_conditions,
    get_chronic_priority_match,
    load_chronic_priority_table,
)


def test_chronic_priority_maps_aliases_to_canonical_conditions() -> None:
    """Verify user-provided disease aliases resolve to canonical condition codes."""
    condition_codes = canonicalize_conditions(
        ["HTN", "type-2 diabetes", "unknown-condition", "high blood pressure"]
    )

    assert condition_codes == ("hypertension", "diabetes")


def test_chronic_priority_returns_source_backed_match() -> None:
    """Verify a known condition and nutrient produce source-backed boost context."""
    match = get_chronic_priority_match("potassium_mg", ["hypertension"])

    assert match is not None
    assert match.boost_score == 30
    assert match.condition_codes == ("hypertension",)
    assert match.source_ids == ("nhlbi_dash",)
    assert match.message == "현재 입력과 만성질환 정보를 함께 볼 때 우선 확인 대상입니다."


def test_chronic_priority_ignores_unknown_disease_codes() -> None:
    """Verify unknown disease codes do not create a priority match."""
    assert canonicalize_conditions(["unknown-condition"]) == ()
    assert get_chronic_priority_match("potassium_mg", ["unknown-condition"]) is None


def test_chronic_priority_does_not_boost_ckd_caution_nutrients() -> None:
    """Verify CKD caution nutrients remain non-boosted because care plans vary."""
    table = load_chronic_priority_table()

    assert get_chronic_priority_match("potassium_mg", ["ckd"], table) is None
    assert table.conditions["chronic_kidney_disease"].caution_nutrients[0].nutrient_code == (
        "potassium_mg"
    )
