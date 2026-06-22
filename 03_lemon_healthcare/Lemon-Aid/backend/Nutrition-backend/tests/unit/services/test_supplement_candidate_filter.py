"""Tests for the non-ingredient OCR pattern-fallback candidate filter."""

from __future__ import annotations

import pytest
from src.services.supplement_candidate_filter import (
    filter_non_ingredient_ocr_fallback_candidates,
    is_non_ingredient_candidate,
)


def _cand(name: str) -> dict[str, object]:
    return {"display_name": name, "original_name": name, "amount": None, "unit": None}


@pytest.mark.parametrize(
    "name",
    [
        # nutrition-facts headers + "기준치에 대한 비율" split fragments
        "영양성분",
        "기준치에",
        "대한",
        "비율",
        "기준치에 대한 비율",
        "1일 영양성분 기준치",
        # label boilerplate
        "별도",
        "표기일까지",
        "품목보고번호",
        # units / measure words (incl. OCR 'g)')
        "g",
        "g)",
        "mg",
        "kcal",
        "%",
        "g 당",
        # energy
        "열량",
        "energy",
        # ultra-short Latin OCR fragments
        "MI",
        "CA",
    ],
)
def test_drops_non_ingredient_tokens(name: str) -> None:
    assert is_non_ingredient_candidate(_cand(name)) is True


@pytest.mark.parametrize(
    "name",
    [
        # real nutrition-facts nutrients (Korean) — must survive
        "탄수화물",
        "단백질",
        "나트륨",
        "당류",
        "콜레스테롤",
        "트랜스지방",
        "포화지방",
        "비타민 C",
        # real ingredients (Korean declaration list)
        "팔라티노스",
        "알룰로스",
        "난소화성말토덱스트린",
        # real English nutrients (English labels are often ALL CAPS)
        "SUGAR",
        "IRON",
        "ZINC",
        "CARBOHYDRATE",
        "MSM",
        "EPA",
    ],
)
def test_keeps_real_ingredients(name: str) -> None:
    assert is_non_ingredient_candidate(_cand(name)) is False


def test_drops_nameless_candidate() -> None:
    assert is_non_ingredient_candidate({"display_name": "", "original_name": None}) is True
    assert is_non_ingredient_candidate({"amount": 1.0}) is True


def test_falls_back_to_original_name_when_display_missing() -> None:
    assert is_non_ingredient_candidate({"original_name": "영양성분"}) is True
    assert is_non_ingredient_candidate({"original_name": "팔라티노스"}) is False


def test_filter_removes_garbage_keeps_real() -> None:
    candidates = [
        _cand("영양성분"),
        _cand("탄수화물"),
        _cand("기준치에"),
        _cand("팔라티노스"),
        _cand("MI"),
        _cand("CARBOHYDRATE"),
        "not-a-dict",  # malformed
        _cand("g)"),
    ]
    out = filter_non_ingredient_ocr_fallback_candidates(candidates)
    names = [c["display_name"] for c in out]
    assert names == ["탄수화물", "팔라티노스", "CARBOHYDRATE"]


def test_filter_empty_list_is_noop() -> None:
    assert filter_non_ingredient_ocr_fallback_candidates([]) == []
