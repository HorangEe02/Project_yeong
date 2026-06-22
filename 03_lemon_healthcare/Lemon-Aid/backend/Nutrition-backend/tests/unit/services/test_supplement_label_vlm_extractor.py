"""Tests for the gemma structuring head + span-grounding (Lever 4)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import pytest
from src.services.supplement_label_vlm_extractor import (
    build_chat_payload,
    extract_label_ingredients,
    parse_rows,
)


def _chat_returning(content: str):
    """Build a fake async chat callable that returns the given message content."""

    async def _chat(_payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return {"message": {"content": content}}

    return _chat


def test_build_payload_includes_ocr_text_and_json_mode() -> None:
    """The payload is JSON-mode, temperature 0, and carries the OCR text."""
    payload = build_chat_payload(ocr_text="Vitamin C 1000 mg", image_b64=None)
    assert payload["format"] == "json"
    assert payload["options"]["temperature"] == 0
    assert "Vitamin C 1000 mg" in payload["messages"][0]["content"]
    assert "images" not in payload["messages"][0]


def test_build_payload_attaches_roi_crop_when_present() -> None:
    """A provided ROI crop is attached as an image for layout context."""
    payload = build_chat_payload(ocr_text="x", image_b64="ZmFrZQ==")
    assert payload["messages"][0]["images"] == ["ZmFrZQ=="]


def test_parse_rows_reads_ingredients_and_skips_unnamed() -> None:
    """Rows parse from the ingredients key; rows without a name are skipped."""
    content = json.dumps(
        {
            "ingredients": [
                {"display_name": "Vitamin C", "amount": 1000, "unit": "mg"},
                {"display_name": "", "amount": 5, "unit": "mg"},  # skipped
                {"amount": 9, "unit": "mg"},  # skipped (no name)
            ]
        }
    )
    rows = parse_rows(content)
    assert [r.display_name for r in rows] == ["Vitamin C"]
    assert rows[0].amount == 1000


def test_parse_rows_malformed_json_returns_empty() -> None:
    """Malformed JSON yields no rows (the head is a non-critical candidate)."""
    assert parse_rows("not json at all") == []


@pytest.mark.asyncio
async def test_extract_grounds_visible_amounts() -> None:
    """Amounts visible in the OCR text survive grounding."""
    content = json.dumps(
        {
            "ingredients": [
                {"display_name": "Vitamin C", "amount": 1000, "unit": "mg"},
                {"display_name": "Zinc", "amount": 15, "unit": "mg"},
            ]
        }
    )
    result = await extract_label_ingredients(
        ocr_text="Supplement Facts Vitamin C 1000 mg Zinc 15 mg",
        chat=_chat_returning(content),
    )
    assert result.raw_row_count == 2
    assert result.dropped_amount_count == 0
    assert result.grounded_amount_count == 2
    assert [c.amount for c in result.candidates] == [1000, 15]


@pytest.mark.asyncio
async def test_extract_drops_hallucinated_amount_keeps_name() -> None:
    """A model-invented amount not in the OCR text is dropped; the name is kept."""
    content = json.dumps(
        {
            "ingredients": [
                {"display_name": "Vitamin C", "amount": 1000, "unit": "mg"},
                {"display_name": "Selenium", "amount": 200, "unit": "mcg"},  # not on label
            ]
        }
    )
    result = await extract_label_ingredients(
        ocr_text="Vitamin C 1000 mg",
        chat=_chat_returning(content),
    )
    assert result.dropped_amount_count == 1
    selenium = next(c for c in result.candidates if c.display_name == "Selenium")
    assert selenium.amount is None  # hallucinated amount dropped
    assert selenium.unit is None
    vitamin_c = next(c for c in result.candidates if c.display_name == "Vitamin C")
    assert vitamin_c.amount == 1000  # grounded amount kept


@pytest.mark.asyncio
async def test_extract_malformed_model_output_is_safe() -> None:
    """A non-JSON model response yields zero candidates, not an error."""
    result = await extract_label_ingredients(
        ocr_text="Vitamin C 1000 mg",
        chat=_chat_returning("```sorry, no json```"),
    )
    assert result.candidates == []
    assert result.raw_row_count == 0
