"""``src.nutrition.mfds_matcher`` 단위 테스트."""

from __future__ import annotations

from src.llm.schemas import ParsedIngredient
from src.nutrition.mfds_matcher import (
    _load_alias_map,
    _normalize_name,
    match_to_nutrient_code,
    to_nutrient_intakes,
)


def _ing(name_ko: str, name_en: str | None = None) -> ParsedIngredient:
    return ParsedIngredient(name_ko=name_ko, name_en=name_en, amount=100, unit="mg")


class TestNormalizeName:
    def test_strips_whitespace(self) -> None:
        assert _normalize_name("Vitamin C") == "vitaminc"

    def test_strips_parens_and_hyphens(self) -> None:
        assert _normalize_name("Vitamin (C)-100") == "vitaminc100"

    def test_lowers_case(self) -> None:
        assert _normalize_name("VITAMIN C") == "vitaminc"

    def test_empty(self) -> None:
        assert _normalize_name("") == ""


class TestMatchToNutrientCode:
    def test_korean_exact_match(self) -> None:
        assert match_to_nutrient_code(_ing("비타민 C")) == "vitamin_c_mg"

    def test_english_match_when_korean_missing(self) -> None:
        ing = ParsedIngredient(
            name_ko="unknown korean name",
            name_en="Vitamin C",
            amount=100,
            unit="mg",
        )
        assert match_to_nutrient_code(ing) == "vitamin_c_mg"

    def test_alias_match_korean(self) -> None:
        """alias '아스코르브산' 도 vitamin_c_mg 로 매칭."""
        assert match_to_nutrient_code(_ing("아스코르브산")) == "vitamin_c_mg"

    def test_alias_match_english(self) -> None:
        ing = ParsedIngredient(
            name_ko="unknown",
            name_en="Ascorbic Acid",
            amount=100,
            unit="mg",
        )
        assert match_to_nutrient_code(ing) == "vitamin_c_mg"

    def test_whitespace_robust(self) -> None:
        assert match_to_nutrient_code(_ing("비타민  C")) == "vitamin_c_mg"

    def test_case_robust(self) -> None:
        ing = ParsedIngredient(name_ko="unknown", name_en="VITAMIN C", amount=1, unit="mg")
        assert match_to_nutrient_code(ing) == "vitamin_c_mg"

    def test_unknown_returns_none(self) -> None:
        assert match_to_nutrient_code(_ing("Unobtainium")) is None

    def test_alias_load_includes_thirty_entries(self) -> None:
        """기본 ≥30 원료 매핑이 로드된다."""
        mapping = _load_alias_map()
        # alias 포함 항목 수가 30보다 훨씬 많아야 한다
        assert len(mapping) >= 30


class TestToNutrientIntakes:
    def test_matched_and_unmatched_split(self) -> None:
        ingredients = [
            ParsedIngredient(name_ko="비타민 C", amount=1000, unit="mg"),
            ParsedIngredient(name_ko="Unobtainium", amount=50, unit="mg"),
            ParsedIngredient(name_ko="비타민 D", amount=25, unit="μg"),
        ]
        intakes, unmatched = to_nutrient_intakes(ingredients)
        assert len(intakes) == 2
        assert unmatched == ["Unobtainium"]
        assert {i.code for i in intakes} == {"vitamin_c_mg", "vitamin_d_ug"}

    def test_unit_lowercased_and_micro_normalized(self) -> None:
        ingredients = [
            ParsedIngredient(name_ko="비타민 D", amount=25, unit="μG"),
        ]
        intakes, _ = to_nutrient_intakes(ingredients)
        assert intakes[0].unit == "ug"

    def test_source_is_supplement(self) -> None:
        ingredients = [ParsedIngredient(name_ko="비타민 C", amount=1, unit="mg")]
        intakes, _ = to_nutrient_intakes(ingredients)
        assert intakes[0].source == "supplement"

    def test_empty_input(self) -> None:
        intakes, unmatched = to_nutrient_intakes([])
        assert intakes == []
        assert unmatched == []
