"""Tests for LLM polish slot helpers."""

from __future__ import annotations

from lemon_ai_agent.polish_slots import (
    build_deterministic_slot_contract,
    slot_value_sets_match,
    slot_values_are_preserved,
)


def test_build_deterministic_slot_contract_lists_slots_for_prompting() -> None:
    """Verify prompt slot contracts are compact and explicit."""
    contract = build_deterministic_slot_contract(
        source_basis="KDRIs 영양 기준",
        specific_examples=["국물", "소스"],
        caution_conditions=["신장질환"],
        expert_check_points=["장류", "가공육"],
    )

    assert contract == (
        "source_basis=KDRIs 영양 기준\n"
        "specific_examples=국물; 소스\n"
        "caution_conditions=신장질환\n"
        "expert_check_points=장류; 가공육"
    )


def test_slot_values_are_preserved_requires_candidate_subset() -> None:
    """Verify small-model slots are accepted only when they preserve deterministic values."""
    assert slot_values_are_preserved(["국물", "소스"], ["국물", "소스", "장류"]) is True
    assert slot_values_are_preserved(["자몽"], ["국물", "소스", "장류"]) is False


def test_slot_values_are_preserved_accepts_display_suffix_and_delimiters() -> None:
    """Verify harmless SGLang formatting does not create polish drift warnings."""
    assert (
        slot_values_are_preserved(
            ["국물 확인; 소스 확인; 장류 확인"],
            ["국물", "소스", "장류", "가공육"],
        )
        is True
    )


def test_slot_value_sets_match_accepts_source_order_and_delimiter_changes() -> None:
    """Verify source slots may vary formatting but must keep the full source set."""
    assert (
        slot_value_sets_match(
            ["KDRIs 영양 기준; 질병관리청 건강정보"],
            ["질병관리청 건강정보, KDRIs 영양 기준"],
        )
        is True
    )
    assert (
        slot_value_sets_match(
            ["KDRIs 영양 기준"],
            ["질병관리청 건강정보, KDRIs 영양 기준"],
        )
        is False
    )
    assert (
        slot_values_are_preserved(
            ["신장질환; 칼륨 제한; 심부전"],
            ["신장질환", "칼륨 제한", "심부전"],
        )
        is True
    )
