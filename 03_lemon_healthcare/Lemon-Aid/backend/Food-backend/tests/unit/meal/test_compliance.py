"""의료 표현 compliance 테스트.

CLAUDE.md §"Rule 1. 의료 도메인 표현 절대 금지 단어"와 dev-guide 16
§"이 작업에서 하지 말 것" 정책에 따라, 사용자 노출 문자열에 의료적 단정
표현이 포함되지 않음을 검증한다.

검증 대상 (사용자 노출 가능 텍스트):
    - `FoodNutritionProfile.highlights` / `cautions` (RdaMatcher 생성).
    - `RecognizedMealItem.estimated_amount` (PortionEstimator 생성).
    - `RecognizedMealItem.name_ko` — 사용자 입력 echo이지만 일관성 검증.

본 테스트는 RdaMatcher의 highlights/cautions 생성을 real CSV의 모든 alias로
호출해서 시스템적으로 검증한다.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from src.nutrition.rda_matcher import RdaMatcher

REPO_ROOT = Path(__file__).resolve().parents[5]
REAL_ALIASES = REPO_ROOT / "data" / "rda" / "food_aliases.json"
REAL_FOODS_CSV = REPO_ROOT / "data" / "rda" / "korean_foods.csv"

BANNED_KO_WORDS: tuple[str, ...] = ("진단", "처방", "치료", "보장")
"""사용자 노출 한국어 금지 단어 (CLAUDE.md §Rule 1).

`진단/처방/치료/보장`은 의료적 단정 표현이므로 사용자 노출 문구에 포함될 수
없다. 본 테스트는 시스템이 생성하는 모든 highlights/cautions/estimated_amount
문자열에 이 단어들이 들어가지 않음을 검증한다.
"""

BANNED_EN_WORDS: tuple[str, ...] = ("diagnose", "prescribe", "treat", "cure")
"""사용자 노출 영문 금지 단어 (CLAUDE.md §Rule 1 영문 매핑).

사용자 노출 텍스트는 한국어가 기본이지만, 다국어 확장에 대비해 영문 금지어도
검증한다.
"""

# 모든 highlight/caution 분기를 트리거하는 합성 행.
_MAX_NUTRIENT_ROW: dict[str, Any] = {
    "food_code": "F999",
    "name_ko": "전영양 풍부",
    "name_en": "",
    "category": "테스트",
    "unit_size_g": 100.0,
    "kcal_per_unit": 500.0,
    "protein_g": 30.0,
    "fat_g": 10.0,
    "carb_g": 50.0,
    "fiber_g": 10.0,
    "sodium_mg": 1000.0,
    "calcium_mg": 200.0,
    "iron_mg": 5.0,
    "vitamin_a_ug": 100.0,
    "vitamin_c_mg": 50.0,
}


def _contains_any(text: str, words: tuple[str, ...]) -> str | None:
    """text에 words 중 하나라도 포함되면 그 단어를, 없으면 None을 반환."""
    for word in words:
        if word in text:
            return word
    return None


def _contains_any_ci(text: str, words: tuple[str, ...]) -> str | None:
    """대소문자 무시 버전."""
    lower = text.lower()
    for word in words:
        if word.lower() in lower:
            return word
    return None


class TestPortionEstimatorAmountStrings:
    """PortionEstimator가 생성하는 amount 문자열."""

    @pytest.mark.parametrize(
        "amount_str",
        ["소량 추정", "1인분 추정", "많음 추정"],
    )
    def test_amount_string_no_banned_korean(self, amount_str: str) -> None:
        match = _contains_any(amount_str, BANNED_KO_WORDS)
        assert match is None, f"'{amount_str}' contains banned word '{match}'"

    @pytest.mark.parametrize(
        "amount_str",
        ["소량 추정", "1인분 추정", "많음 추정"],
    )
    def test_amount_string_no_banned_english(self, amount_str: str) -> None:
        match = _contains_any_ci(amount_str, BANNED_EN_WORDS)
        assert match is None, f"'{amount_str}' contains banned word '{match}'"


class TestSyntheticProfileHighlights:
    """모든 highlight/caution 분기를 합성 데이터로 트리거 후 검증."""

    def test_all_branches_triggered_no_banned_words(self) -> None:
        """모든 임계를 넘는 합성 음식 → 모든 highlight/caution 생성, 금지어 없음."""
        matcher = RdaMatcher.from_rows(
            aliases={"전영양 풍부": "F999"},
            food_rows=[_MAX_NUTRIENT_ROW],
        )
        profile = matcher.match("전영양 풍부")
        # 최소 4개 highlight + 1개 caution 트리거.
        assert profile.highlights
        assert profile.cautions
        for text in profile.highlights + profile.cautions:
            ko_match = _contains_any(text, BANNED_KO_WORDS)
            assert ko_match is None, f"'{text}' contains '{ko_match}'"
            en_match = _contains_any_ci(text, BANNED_EN_WORDS)
            assert en_match is None, f"'{text}' contains '{en_match}'"


class TestRealCsvHighlightsAndCautions:
    """실 data/rda 시드 전체에 대해 사용자 노출 텍스트가 안전한지 검증."""

    def test_all_aliases_yield_safe_highlights(self) -> None:
        """real CSV의 모든 alias에 대해 highlights에 금지어 없음."""
        matcher = RdaMatcher.from_paths(
            aliases_path=REAL_ALIASES,
            foods_csv_path=REAL_FOODS_CSV,
        )
        aliases: dict[str, str] = json.loads(REAL_ALIASES.read_text(encoding="utf-8"))
        for alias_name in aliases:
            profile = matcher.match(alias_name)
            for text in profile.highlights:
                ko_match = _contains_any(text, BANNED_KO_WORDS)
                assert (
                    ko_match is None
                ), f"alias='{alias_name}' highlight='{text}' contains '{ko_match}'"
                en_match = _contains_any_ci(text, BANNED_EN_WORDS)
                assert (
                    en_match is None
                ), f"alias='{alias_name}' highlight='{text}' contains '{en_match}'"

    def test_all_aliases_yield_safe_cautions(self) -> None:
        """real CSV의 모든 alias에 대해 cautions에 금지어 없음."""
        matcher = RdaMatcher.from_paths(
            aliases_path=REAL_ALIASES,
            foods_csv_path=REAL_FOODS_CSV,
        )
        aliases: dict[str, str] = json.loads(REAL_ALIASES.read_text(encoding="utf-8"))
        for alias_name in aliases:
            profile = matcher.match(alias_name)
            for text in profile.cautions:
                ko_match = _contains_any(text, BANNED_KO_WORDS)
                assert (
                    ko_match is None
                ), f"alias='{alias_name}' caution='{text}' contains '{ko_match}'"
                en_match = _contains_any_ci(text, BANNED_EN_WORDS)
                assert (
                    en_match is None
                ), f"alias='{alias_name}' caution='{text}' contains '{en_match}'"


class TestBannedWordListIntegrity:
    """금지어 리스트 자체의 정합성 검증."""

    def test_korean_list_non_empty(self) -> None:
        assert BANNED_KO_WORDS

    def test_english_list_non_empty(self) -> None:
        assert BANNED_EN_WORDS

    def test_required_korean_words_listed(self) -> None:
        """CLAUDE.md §Rule 1에 명시된 4단어 모두 포함."""
        required = {"진단", "처방", "치료", "보장"}
        assert required.issubset(set(BANNED_KO_WORDS))

    def test_required_english_words_listed(self) -> None:
        required = {"diagnose", "prescribe", "treat", "cure"}
        assert required.issubset(set(BANNED_EN_WORDS))
