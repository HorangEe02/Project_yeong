"""Span-grounding guardrail for supplement ingredient amounts ("never guess amount").

The 0.85/0.90 gate redesign (Lever 4) adds a layout-aware gemma4:e4b structuring
head and other extractors that propose ``name | amount | unit`` rows. A live
evaluation showed the vision model can omit or invent amounts, and a JSON schema
only constrains *shape*, not *truth*. The real guardrail is therefore SPAN
GROUNDING: every proposed amount/unit must actually appear as a substring of the
OCR text the extractor was given. Any amount that is not grounded is dropped
(amount nulled, ingredient NAME kept) so recall is preserved while a hallucinated
number can never reach the "review before save" UX.

This module is pure (no I/O, no logging of the OCR text) and decoupled from the
extractor/parser so it can sit between any extractor and the evidence_union merge.
Matching is normalized — NFKC + casefold + whitespace/comma removal — so
``1,000 mg`` grounds ``1000`` and ``µg``/``μg`` (micro sign vs Greek mu) unify.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, replace


@dataclass(frozen=True)
class IngredientAmount:
    """One extractor-proposed ingredient row to be grounded.

    Attributes:
        display_name: Ingredient name (kept even if the amount is dropped).
        amount: Proposed numeric amount, or None when only a name was found.
        unit: Proposed unit (e.g. ``mg``/``mcg``/``IU``), or None.
    """

    display_name: str
    amount: float | None = None
    unit: str | None = None


@dataclass(frozen=True)
class GroundingDecision:
    """Result of grounding one ingredient row against OCR text.

    Attributes:
        item: The (possibly amount/unit-nulled) ingredient row.
        grounded: Whether the proposed amount was found in the OCR text.
        reason: Stable reason code for audit (no raw OCR text included).
    """

    item: IngredientAmount
    grounded: bool
    reason: str


def _normalize(text: str) -> str:
    """Normalize text for substring grounding (NFKC, casefold, no spaces/commas)."""
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return "".join(ch for ch in normalized if not ch.isspace() and ch != ",")


def _amount_str(amount: float) -> str:
    """Render an amount as a plain (non-scientific) decimal string, no trailing zeros."""
    text = f"{amount:.6f}".rstrip("0").rstrip(".")
    return text or "0"


def is_amount_grounded(amount: float | None, unit: str | None, ocr_text: str) -> bool:
    """Return whether the proposed amount (and unit, if any) appear in the OCR text.

    Args:
        amount: Proposed numeric amount (None means nothing to ground).
        unit: Proposed unit, or None.
        ocr_text: The OCR text the extractor was given.

    Returns:
        True when there is no amount to verify, or when the amount string and the
        unit (if present) are both substrings of the normalized OCR text.
    """
    if amount is None:
        return True
    haystack = _normalize(ocr_text)
    if not haystack:
        return False
    if _amount_str(amount) not in haystack:
        return False
    if unit:
        return _normalize(unit) in haystack
    return True


def ground_amount(item: IngredientAmount, ocr_text: str) -> GroundingDecision:
    """Ground one ingredient row, nulling an ungrounded amount but keeping the name.

    Args:
        item: Extractor-proposed ingredient row.
        ocr_text: OCR text to verify against.

    Returns:
        A :class:`GroundingDecision`. When the amount is not grounded, the returned
        item has ``amount``/``unit`` set to None (the ingredient name is retained).
    """
    if item.amount is None:
        return GroundingDecision(item=item, grounded=True, reason="no_amount")
    if is_amount_grounded(item.amount, item.unit, ocr_text):
        return GroundingDecision(item=item, grounded=True, reason="amount_grounded")
    return GroundingDecision(
        item=replace(item, amount=None, unit=None),
        grounded=False,
        reason="amount_not_in_ocr",
    )


def apply_span_grounding(
    items: list[IngredientAmount],
    ocr_text: str,
) -> list[GroundingDecision]:
    """Ground a list of extractor-proposed ingredient rows against OCR text.

    Args:
        items: Extractor-proposed ingredient rows.
        ocr_text: OCR text the extractor was given.

    Returns:
        One :class:`GroundingDecision` per input item, order preserved.
    """
    return [ground_amount(item, ocr_text) for item in items]
