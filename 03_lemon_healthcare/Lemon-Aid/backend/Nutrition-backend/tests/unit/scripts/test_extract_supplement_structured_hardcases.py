"""Tests for structured OCR hard-case fixture extraction."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

hardcases = importlib.import_module("scripts.extract_supplement_structured_hardcases")


def test_extract_hardcases_filters_split_and_reports_fixture_ids() -> None:
    """Verify redacted hard-case fixture lists are extracted from per-image counts."""
    result = hardcases.extract_hardcases(
        eval_json={
            "schema_version": "paddleocr-clova-eval-v3",
            "per_image": [
                {
                    "fixture_id": "fixture-a",
                    "field_match_ratio": 0.0,
                    "ingredient_found": 0,
                    "ingredient_total": 2,
                },
                {
                    "fixture_id": "fixture-b",
                    "field_match_ratio": 0.75,
                    "ingredient_found": 1,
                    "ingredient_total": 1,
                },
                {
                    "fixture_id": "fixture-c",
                    "field_match_ratio": 0.0,
                    "ingredient_found": 0,
                    "ingredient_total": 1,
                },
            ],
        },
        split_by_fixture={"fixture-a": "holdout", "fixture-b": "holdout", "fixture-c": "train"},
        eval_split="holdout",
    )

    assert result["counts"] == {
        "field_zero": 1,
        "field_lt50": 1,
        "ingredient_all_missed": 1,
    }
    assert result["fixture_ids"]["field_zero"] == ["fixture-a"]
    assert result["fixture_ids"]["ingredient_all_missed"] == ["fixture-a"]
    assert result["raw_ocr_text_stored"] is False
