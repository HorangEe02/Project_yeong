"""Tests for the span-grounding guardrail ("never guess amount")."""

from __future__ import annotations

from src.services.supplement_span_grounding import (
    IngredientAmount,
    apply_span_grounding,
    ground_amount,
    is_amount_grounded,
)


def test_amount_present_in_ocr_is_grounded() -> None:
    """An amount+unit visible in the OCR text is kept."""
    item = IngredientAmount("Vitamin C", 1000, "mg")
    decision = ground_amount(item, "Supplement Facts Vitamin C 1000 mg (1000%)")
    assert decision.grounded is True
    assert decision.item.amount == 1000
    assert decision.item.unit == "mg"


def test_comma_and_space_normalized_grounding() -> None:
    """Comma-grouped / spaced numbers in OCR still ground the amount."""
    assert is_amount_grounded(1000, "mg", "Magnesium 1,000 mg per serving") is True


def test_ungrounded_amount_is_dropped_name_kept() -> None:
    """An amount NOT in the OCR text is nulled, but the ingredient name is kept."""
    item = IngredientAmount("Vitamin C", 777, "mg")
    decision = ground_amount(item, "Supplement Facts Vitamin C 1000 mg")
    assert decision.grounded is False
    assert decision.reason == "amount_not_in_ocr"
    assert decision.item.display_name == "Vitamin C"
    assert decision.item.amount is None
    assert decision.item.unit is None


def test_unit_hallucination_is_rejected() -> None:
    """A correct number with a unit that is not on the label is rejected."""
    # "1000" is visible but the label says mg, not mcg.
    item = IngredientAmount("Vitamin C", 1000, "mcg")
    decision = ground_amount(item, "Vitamin C 1000 mg")
    assert decision.grounded is False
    assert decision.item.amount is None


def test_micro_sign_and_greek_mu_unify_under_nfkc() -> None:
    """µg (micro sign U+00B5) grounds against μg (Greek mu U+03BC)."""
    assert is_amount_grounded(25, "µg", "Vitamin D 25 μg") is True


def test_no_amount_is_passed_through() -> None:
    """A name-only row (no amount) is grounded trivially and unchanged."""
    item = IngredientAmount("Magnesium", None, None)
    decision = ground_amount(item, "Other ingredients: magnesium stearate")
    assert decision.grounded is True
    assert decision.reason == "no_amount"
    assert decision.item == item


def test_empty_ocr_text_grounds_nothing() -> None:
    """With no OCR text, any proposed amount is ungrounded."""
    assert is_amount_grounded(100, "mg", "") is False


def test_apply_span_grounding_over_list() -> None:
    """A mixed list keeps grounded amounts and drops ungrounded ones."""
    ocr = "Supplement Facts Vitamin C 1000 mg Zinc 15 mg"
    items = [
        IngredientAmount("Vitamin C", 1000, "mg"),
        IngredientAmount("Zinc", 15, "mg"),
        IngredientAmount("Selenium", 200, "mcg"),  # not on the label
    ]
    decisions = apply_span_grounding(items, ocr)
    assert [d.grounded for d in decisions] == [True, True, False]
    assert decisions[2].item.display_name == "Selenium"
    assert decisions[2].item.amount is None
