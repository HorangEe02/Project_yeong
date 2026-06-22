"""Phase D extractor-recall coverage and false-positive guards.

Encodes the ingredient-recall redesign pattern table
(docs/ocr_baseline_reports/2026-06-17-ingredient-recall-085-redesign.md, Phase D)
as direct tests of the deterministic OCR amount-pattern fallback. Testing the pure
extractor keeps the cases fast and focused on parser recall/false-positive behavior
without the holdout27 dataset (which is operator-held and not in the repo), and
serves as the standing regression spec for the recall-first parser.

Two invariants the redesign mandates are asserted throughout:
  * no amount/unit is emitted unless a number AND unit are literally visible, and
  * recall additions must not increase false positives (precautions, headings,
    packaging counts, serving sizes, and comparison qualifiers stay out).
"""

from __future__ import annotations

from src.services.supplement_parser import _extract_ocr_pattern_ingredient_candidates


def _candidates(text: str) -> list[dict[str, object]]:
    return _extract_ocr_pattern_ingredient_candidates(text)


def _names(text: str) -> list[str]:
    return [str(candidate["display_name"]) for candidate in _candidates(text)]


def _by_name(text: str, name: str) -> dict[str, object] | None:
    return next((c for c in _candidates(text) if c["display_name"] == name), None)


# --- Coverage: patterns the recall-first parser must extract -----------------


def test_same_line_name_amount_unit() -> None:
    candidate = _by_name("비타민C 100 mg", "비타민C")
    assert candidate is not None
    assert candidate["amount"] == 100
    assert candidate["unit"] == "mg"


def test_comma_separated_mixed_facts_extracts_every_ingredient() -> None:
    names = _names("마그네슘 160 mg, 비타민B6 12 mg, 아연 8.5 mg")
    assert "마그네슘" in names
    assert "비타민B6" in names
    assert "아연" in names


def test_split_two_line_name_then_amount_unit() -> None:
    candidate = _by_name("비타민C\n100 mg", "비타민C")
    assert candidate is not None
    assert candidate["amount"] == 100
    assert candidate["unit"] == "mg"


def test_split_three_line_name_number_unit() -> None:
    candidate = _by_name("비타민C\n100\nmg 167%", "비타민C")
    assert candidate is not None
    assert candidate["amount"] == 100
    assert candidate["unit"] == "mg"


def test_english_ingredient_name_is_captured() -> None:
    assert "Vitamin C" in _names("Vitamin C 100 mg")


def test_table_row_without_percent_sign_keeps_ingredient() -> None:
    candidate = _by_name("비타민C 100 mg 167", "비타민C")
    assert candidate is not None
    assert candidate["amount"] == 100
    assert candidate["unit"] == "mg"


def test_korean_unit_word_variants_normalize() -> None:
    candidate = _by_name("엽산 400 마이크로그램", "엽산")
    assert candidate is not None
    assert candidate["unit"] == "ug"


# --- Gap (Phase D): amount-first ordering -----------------------------------
# `100 mg 비타민C` puts the amount before the name; the name-first regex cannot
# match it, so the ingredient is dropped today. The recall-first parser recovers
# it while still requiring a literally-visible number + unit.


def test_amount_first_ordering_recovers_ingredient() -> None:
    candidate = _by_name("100 mg 비타민C", "비타민C")
    assert candidate is not None
    assert candidate["amount"] == 100
    assert candidate["unit"] == "mg"


def test_amount_first_with_percent_dv_captures_daily_value() -> None:
    candidate = _by_name("12 mg 100% 비타민B6", "비타민B6")
    assert candidate is not None
    assert candidate["amount"] == 12
    assert candidate["unit"] == "mg"
    assert candidate["daily_value_percent"] == 100


# --- False-positive guards: these must NOT yield ingredient candidates -------


def test_intake_instruction_line_is_not_an_ingredient() -> None:
    assert _names("1일 1회 2정을 물과 함께 섭취하세요") == []


def test_storage_precaution_line_is_not_an_ingredient() -> None:
    assert _names("어린이 손에 닿지 않는 곳에 보관하십시오") == []


def test_packaging_count_line_is_not_an_ingredient() -> None:
    assert _names("30정 30일분") == []


def test_amount_first_comparison_qualifier_is_not_an_ingredient() -> None:
    # `100 mg 이상` ("100 mg or more") must not surface "이상" as an ingredient.
    assert "이상" not in _names("100 mg 이상")
    assert "미만" not in _names("50 mg 미만")


def test_amount_first_does_not_invent_amounts_without_a_unit() -> None:
    # A bare number before a name (no unit) must not fabricate an amount.
    assert _names("100 비타민C") == []


def test_amount_first_percent_only_unit_is_not_an_ingredient() -> None:
    # "100% 일일권장량" is a %DV header, not an ingredient amount.
    assert _names("100% 일일권장량") == []
    assert _names("50% 영양성분기준치") == []


def test_amount_first_does_not_displace_name_first_same_line() -> None:
    # A normal name-first row stays name-first (amount-first must not hijack it).
    candidate = _by_name("비타민C 100 mg", "비타민C")
    assert candidate is not None
    assert candidate["amount"] == 100


def test_percent_only_dv_row_is_not_a_dosed_ingredient() -> None:
    # "나트륨 14 %" is a %DV-only facts column; emitting amount=14 unit='%' would
    # fabricate a dose. No path may mine a "%"-as-amount ingredient.
    for line in ("나트륨 14 %", "칼슘 35 %", "단백질 20 %", "엽산 400 80 %"):
        cands = _candidates(line)
        assert all(c["unit"] != "%" for c in cands), line
        assert _names(line) == [], line


def test_amount_first_multiword_qualifier_phrase_is_not_an_ingredient() -> None:
    # A multi-word phrase starting with a qualifier must be skipped (leading-token guard).
    assert _names("100 mg 이상 섭취 금지") == []
    assert "이상 비타민C" not in _names("100 mg 이상 비타민C")


# --- CFU magnitude counters (억/조/billion) ----------------------------------
# "100억 CFU" puts a Korean myriad counter (or English magnitude) between the count
# and the CFU unit, which the standard amount grammar misses. 100억 = 10^10 exceeds
# the amount field bound (le=1_000_000), so the magnitude is kept in the unit
# ("억 CFU") rather than multiplied out — nothing is fabricated.


def test_cfu_amount_first_korean_myriad_counter() -> None:
    candidate = _by_name("100억 CFU 유산균", "유산균")
    assert candidate is not None
    assert candidate["amount"] == 100
    assert candidate["unit"] == "억 CFU"


def test_cfu_name_first_korean_myriad_counter() -> None:
    candidate = _by_name("유산균 100억 CFU", "유산균")
    assert candidate is not None
    assert candidate["amount"] == 100
    assert candidate["unit"] == "억 CFU"


def test_cfu_jo_counter() -> None:
    candidate = _by_name("프로바이오틱스 5조 CFU", "프로바이오틱스")
    assert candidate is not None
    assert candidate["amount"] == 5
    assert candidate["unit"] == "조 CFU"


def test_cfu_english_billion_magnitude() -> None:
    candidate = _by_name("프로바이오틱스 10 billion CFU", "프로바이오틱스")
    assert candidate is not None
    assert candidate["amount"] == 10
    assert candidate["unit"] == "billion CFU"


def test_cfu_thousands_separated_count() -> None:
    candidate = _by_name("유산균 1,000억 CFU", "유산균")
    assert candidate is not None
    assert candidate["amount"] == 1000
    assert candidate["unit"] == "억 CFU"


def test_cfu_name_first_with_trailing_text() -> None:
    candidate = _by_name("유산균 100억 CFU 함유", "유산균")
    assert candidate is not None
    assert candidate["amount"] == 100
    assert candidate["unit"] == "억 CFU"


def test_plain_cfu_without_magnitude_still_works() -> None:
    # Regression: "유산균 100 CFU" (no magnitude) is already handled by the grammar.
    candidate = _by_name("유산균 100 CFU", "유산균")
    assert candidate is not None
    assert candidate["amount"] == 100
    assert candidate["unit"] == "CFU"


def test_cfu_magnitude_requires_the_cfu_unit() -> None:
    # "10억 원 할인" (10억 won discount) has a myriad counter but no CFU -> not mined.
    assert _names("10억 원 할인 이벤트") == []
    assert _names("30억 마리 유산균") == []
