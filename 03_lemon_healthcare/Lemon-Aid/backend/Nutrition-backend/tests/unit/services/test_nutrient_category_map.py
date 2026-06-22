"""Unit tests for nutrient/ingredient -> supplement category_key mapping."""

from __future__ import annotations

from src.services.nutrient_category_map import (
    category_keys_for_ingredient_texts,
    category_keys_for_nutrient_codes,
)


def test_nutrient_codes_with_units_map_to_categories() -> None:
    """KDRIs codes with unit suffixes resolve to the right category keys."""
    keys = category_keys_for_nutrient_codes(
        ["calcium_mg", "vitamin_d_ug", "epa_dha_mg", "magnesium_mg", "iron_mg"]
    )
    assert set(keys) == {"칼슘", "비타민D", "오메가3", "마그네슘", "철분"}


def test_nutrient_codes_without_units_also_map() -> None:
    """Unit-less nutrient codes resolve identically to suffixed codes."""
    assert category_keys_for_nutrient_codes(["calcium"]) == ("칼슘",)
    assert category_keys_for_nutrient_codes(["vitamin_d"]) == ("비타민D",)


def test_nutrient_codes_b_complex_and_eaa_collapse() -> None:
    """B-complex nutrients collapse to 비타민B; EAAs to BCAA_EAA; deduped."""
    keys = category_keys_for_nutrient_codes(
        ["niacin_mg", "folate_ug", "vitamin_b12_ug", "leucine_g", "valine_g"]
    )
    assert keys.count("비타민B") == 1
    assert keys.count("BCAA_EAA") == 1
    assert set(keys) == {"비타민B", "BCAA_EAA"}


def test_unmapped_nutrient_codes_yield_no_keys() -> None:
    """Nutrients without a dedicated category produce no entity key."""
    assert category_keys_for_nutrient_codes(["sodium_mg", "energy_kcal", "water_ml", ""]) == ()


def test_ingredient_texts_keyword_match() -> None:
    """Korean and ASCII ingredient keywords map to category keys (deduped)."""
    keys = category_keys_for_ingredient_texts(
        ["마그네슘 산화물 200mg", "오메가3 피쉬오일", "CoQ10 100mg", "유산균 100억"]
    )
    assert set(keys) == {"마그네슘", "오메가3", "코엔자임Q10", "유산균_프로바이오틱"}


def test_ingredient_texts_no_match_is_empty() -> None:
    """Unrecognized ingredient text yields no category keys."""
    assert category_keys_for_ingredient_texts(["기타 부형제", "", "정제수"]) == ()
