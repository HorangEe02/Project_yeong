"""Tests for the structured-extraction gate, incl. the Step-0 Wilson certification."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

gate = importlib.import_module("scripts.gate_supplement_structured_extraction_target")


def _summary(macro: str, micro: str, recall: str, fixtures: int) -> dict:
    """Build a minimal trusted structured-eval summary."""
    return {
        "schema_version": "supplement-structured-extraction-eval-summary-v1",
        "provider": "paddleocr_local",
        "eval_split": "holdout",
        "fixture_count": fixtures,
        "leakage_check_passed": True,
        "privacy_review_cleared": True,
        "metrics": {
            "field_match_ratio_macro": macro,
            "field_match_ratio_micro": micro,
            "ingredient_recall": recall,
        },
    }


def test_point_above_threshold_but_not_certified_at_small_n() -> None:
    """At n=41 a point estimate over threshold is reached but NOT Wilson-certified."""
    result = gate.build_structured_extraction_gate(_summary("0.92", "0.91", "0.90", 41))
    assert result["structured_target_reached"] is True  # point-based (legacy)
    assert result["certified_target_reached"] is False  # Wilson lower bound rule
    assert all(v is False for v in result["certified_checks"].values())
    assert result["metric_lower_bounds_95"]["field_match_ratio_macro"] < 0.90


def test_certified_when_high_metrics_on_large_split() -> None:
    """High metrics on a large split clear both the point and the Wilson lower bound."""
    result = gate.build_structured_extraction_gate(_summary("0.97", "0.97", "0.95", 400))
    assert result["structured_target_reached"] is True
    assert result["certified_target_reached"] is True
    assert all(result["certified_checks"].values())


def test_below_threshold_blocks_and_is_not_certified() -> None:
    """A current-baseline-like summary is neither reached nor certified."""
    result = gate.build_structured_extraction_gate(_summary("0.781", "0.766", "0.747", 41))
    assert result["structured_target_reached"] is False
    assert result["certified_target_reached"] is False
    assert "field_match_macro_met" in result["blocker_codes"]
