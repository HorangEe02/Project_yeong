"""Unit tests for multi-column (Men/Women) table base-name merge in the OCR parser.

On a multi-column Supplement Facts table the LLM emits a nutrient with its full
parenthetical form and no amount (the interleaved Men/Women columns break its
name-to-amount pairing) — e.g. ``Zinc (zinc mono-L-methionine, aspartate)`` with
``amount=None`` — while the deterministic OCR amount-pattern fallback mines the
plain name with the amount (``Zinc 30 mg``). Without a base-name match key the two
survive as a duplicate pair (one named, no amount; one with the amount). These
tests pin the base-name merge: the parenthetical candidate is *enriched* with the
amount and the plain candidate is *not* appended as a duplicate, while genuinely
distinct nutrients are never merged.

The functions under test are pure, so these need no DB session, mirroring
``test_supplement_parser_fallback_sanitization.py``.
"""

from __future__ import annotations

from typing import Any

from src.models.schemas.supplement_parser import SupplementStructuredParseResult
from src.services.supplement_parser import (
    _ingredient_base_name_key,
    _merge_ocr_pattern_fallbacks,
)


def _llm_candidate(
    display_name: str,
    original_name: str,
    *,
    amount: float | None = None,
    unit: str | None = None,
) -> dict[str, Any]:
    """Build a structured (LLM-source) candidate dict for the merge under test."""
    return {
        "display_name": display_name,
        "original_name": original_name,
        "nutrient_code": None,
        "amount": amount,
        "unit": unit,
        "daily_value_percent": None,
        "confidence": 0.6,
        "source": "ollama_structured",
    }


class TestMultiColumnBaseNameMerge:
    """Base-name key merges the full parenthetical LLM form with the plain OCR name."""

    def test_parenthetical_llm_candidate_is_enriched_not_duplicated(self) -> None:
        parse_result = SupplementStructuredParseResult.model_validate(
            {
                "ingredient_candidates": [
                    _llm_candidate("아연", "Zinc (zinc mono-L-methionine, aspartate)")
                ]
            }
        )

        merged = _merge_ocr_pattern_fallbacks(parse_result, "Zinc 30 mg")

        # Exactly one zinc row: the parenthetical candidate, now carrying the amount.
        assert len(merged.ingredient_candidates) == 1
        candidate = merged.ingredient_candidates[0]
        assert candidate.display_name == "아연"
        assert candidate.original_name == "Zinc (zinc mono-L-methionine, aspartate)"
        assert candidate.amount == 30
        assert candidate.unit == "mg"

    def test_distinct_base_names_are_not_merged(self) -> None:
        parse_result = SupplementStructuredParseResult.model_validate(
            {"ingredient_candidates": [_llm_candidate("크롬", "Chromium")]}
        )

        merged = _merge_ocr_pattern_fallbacks(parse_result, "Selenium 55 mcg")

        # A different nutrient must NOT be enriched/deduped into the LLM candidate.
        originals = {c.original_name for c in merged.ingredient_candidates}
        assert originals == {"Chromium", "Selenium"}
        chromium = next(c for c in merged.ingredient_candidates if c.original_name == "Chromium")
        assert chromium.amount is None

    def test_ambiguous_same_base_forms_are_not_broadcast(self) -> None:
        # Two distinct chemical forms share base "vitamin a"; a single OCR amount must
        # NOT be broadcast to both (that would fabricate a shared dose across forms).
        parse_result = SupplementStructuredParseResult.model_validate(
            {
                "ingredient_candidates": [
                    _llm_candidate("비타민 A (레티놀)", "Vitamin A (as retinol)"),
                    _llm_candidate("비타민 A (베타카로틴)", "Vitamin A (as beta-carotene)"),
                ]
            }
        )

        merged = _merge_ocr_pattern_fallbacks(parse_result, "Vitamin A 900 mcg")

        forms = [
            c for c in merged.ingredient_candidates if c.original_name and "as " in c.original_name
        ]
        assert len(forms) == 2
        assert all(form.amount is None for form in forms)
        # The single OCR amount appears at most once (its own row), never broadcast.
        assert len([c for c in merged.ingredient_candidates if c.amount == 900]) == 1

    def test_distinct_same_base_amount_is_not_suppressed(self) -> None:
        # An LLM row that already carries an amount must not suppress a genuinely
        # distinct same-base amount the OCR pattern mined; both rows survive.
        parse_result = SupplementStructuredParseResult.model_validate(
            {
                "ingredient_candidates": [
                    _llm_candidate("나이아신", "Niacin (as niacinamide)", amount=20, unit="mg")
                ]
            }
        )

        merged = _merge_ocr_pattern_fallbacks(parse_result, "Niacin 35 mg")

        assert len(merged.ingredient_candidates) == 2
        assert sorted(c.amount for c in merged.ingredient_candidates) == [20, 35]


class TestIngredientBaseNameKey:
    """Trailing form/source qualifier stripping for the base nutrient name key."""

    def test_strips_trailing_parenthetical_qualifier(self) -> None:
        assert _ingredient_base_name_key("Zinc (zinc mono-L-methionine, aspartate)") == "zinc"
        assert _ingredient_base_name_key("Vitamin B6 (as pyridoxineHCI)") == "vitamin b6"

    def test_plain_name_is_unchanged(self) -> None:
        assert _ingredient_base_name_key("Calcium") == "calcium"

    def test_distinct_vitamins_keep_distinct_base_keys(self) -> None:
        # Stripping the parenthetical must not collapse B6 and B12 into one key.
        assert _ingredient_base_name_key("Vitamin B6") != _ingredient_base_name_key("Vitamin B12")

    def test_leading_parenthesis_returns_empty(self) -> None:
        # Stripping would leave nothing → empty key (callers never add an empty key).
        assert _ingredient_base_name_key("(something) X") == ""

    def test_stray_closing_paren_is_not_stripped(self) -> None:
        # A lone closing paren (OCR fragment) is not a qualifier; keep the name.
        assert _ingredient_base_name_key("magnesium oxide)") == "magnesium oxide)"
