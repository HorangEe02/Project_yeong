"""Tests for deterministic English->Korean ingredient display-name localization."""

from __future__ import annotations

import pytest
from src.services.nutrient_display_name_localizer import (
    is_english_dominant,
    korean_display_name,
    localize_ingredient_display_names,
)


@pytest.mark.parametrize(
    ("english", "korean"),
    [
        ("Iodine", "요오드"),
        ("Riboflavin", "리보플라빈"),
        ("Folate", "엽산"),
        ("Folate (DFE)", "엽산"),  # parenthetical qualifier dropped
        ("Vitamin C", "비타민 C"),
        ("vitamin c", "비타민 C"),  # case-insensitive
        ("  Zinc  ", "아연"),  # whitespace
        ("Folic acid", "엽산"),  # synonym
        ("Ascorbic acid", "비타민 C"),  # synonym
        ("CoQ10", "코엔자임Q10"),  # supplement extension
        ("Milk Thistle", "밀크씨슬"),
        ("Omega-3", "오메가-3"),
        ("Lutein + Zeaxanthin", "루테인+지아잔틴"),  # compound
    ],
)
def test_korean_display_name_maps_known_nutrients(english: str, korean: str) -> None:
    assert korean_display_name(english) == korean


@pytest.mark.parametrize("name", ["Milk", "Complex", "Proprietary Blend", "", "   ", "Xyzzyne"])
def test_korean_display_name_returns_none_for_unknown(name: str) -> None:
    assert korean_display_name(name) is None


def test_is_english_dominant() -> None:
    assert is_english_dominant("Iodine") is True
    assert is_english_dominant("Vitamin C") is True
    assert is_english_dominant("요오드") is False
    assert is_english_dominant("아연") is False
    assert is_english_dominant("") is False


def test_localize_translates_english_and_preserves_english_source() -> None:
    snapshot = {
        "ingredient_candidates": [
            {"display_name": "Iodine", "original_name": "Iodine", "amount": 150.0, "unit": "ug"},
        ]
    }
    out = localize_ingredient_display_names(snapshot)
    cand = out["ingredient_candidates"][0]
    assert cand["display_name"] == "요오드"
    assert cand["original_name"] == "Iodine"  # English preserved for 한글(영문)


def test_localize_backfills_missing_original_name() -> None:
    snapshot = {"ingredient_candidates": [{"display_name": "Riboflavin"}]}
    cand = localize_ingredient_display_names(snapshot)["ingredient_candidates"][0]
    assert cand["display_name"] == "리보플라빈"
    assert cand["original_name"] == "Riboflavin"  # back-filled so English survives


def test_localize_leaves_korean_names_untouched() -> None:
    snapshot = {"ingredient_candidates": [{"display_name": "아연", "original_name": "아연"}]}
    cand = localize_ingredient_display_names(snapshot)["ingredient_candidates"][0]
    assert cand["display_name"] == "아연"
    assert cand["original_name"] == "아연"


def test_localize_leaves_unknown_english_untouched() -> None:
    snapshot = {"ingredient_candidates": [{"display_name": "Milk", "original_name": "Milk"}]}
    cand = localize_ingredient_display_names(snapshot)["ingredient_candidates"][0]
    assert cand["display_name"] == "Milk"


def test_localize_handles_mixed_and_malformed_candidates() -> None:
    snapshot = {
        "ingredient_candidates": [
            {"display_name": "Vitamin D", "original_name": "Vitamin D"},
            {"display_name": "", "original_name": ""},  # empty
            "not-a-dict",  # malformed
            {"amount": 10.0},  # no display_name
            {"display_name": "셀레늄"},  # already Korean
        ]
    }
    out = localize_ingredient_display_names(snapshot)
    cands = out["ingredient_candidates"]
    assert cands[0]["display_name"] == "비타민 D"
    assert cands[1]["display_name"] == ""
    assert cands[2] == "not-a-dict"
    assert "display_name" not in cands[3]
    assert cands[4]["display_name"] == "셀레늄"


def test_localize_no_ingredient_candidates_is_noop() -> None:
    assert localize_ingredient_display_names({}) == {}
    assert localize_ingredient_display_names({"ingredient_candidates": None}) == {
        "ingredient_candidates": None
    }
