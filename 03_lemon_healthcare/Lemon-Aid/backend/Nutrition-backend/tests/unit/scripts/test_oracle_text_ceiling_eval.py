"""Tests for the oracle text-ceiling rung (Step-2 binding-constraint diagnostic)."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

oracle = importlib.import_module("scripts.oracle_text_ceiling_eval")


def _expected(name: str) -> dict[str, Any]:
    """A self-consistent GT `expected` object (every field unit is its own text)."""
    return {
        "product_name": name,
        "ingredients": [
            {"display_name": "마그네슘", "amount": "400", "unit": "mg"},
            {"display_name": "비타민D", "amount": "1000", "unit": "IU"},
        ],
        "intake_method": "1일 1정 섭취",
    }


def _write_bundle(tmp_path: Path, rows: list[dict[str, Any]]) -> Path:
    """Write a minimal GT bundle with the given rows; return the bundle dir."""
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    with (bundle / "ground-truth.todo.jsonl").open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return bundle


def _ready_rows(count: int) -> list[dict[str, Any]]:
    """`count` benchmark-ready, self-consistent GT rows."""
    return [
        {
            "fixture_id": f"p{i}",
            "ready_for_benchmark_after_review": True,
            "expected": _expected(f"제품{i}"),
        }
        for i in range(count)
    ]


def test_load_ready_rows_filters_unreviewed_and_non_dict(tmp_path: Path) -> None:
    """Only reviewed-ready rows with a structured expected object are loaded."""
    rows = [
        {"fixture_id": "ok", "ready_for_benchmark_after_review": True, "expected": _expected("A")},
        {
            "fixture_id": "draft",
            "ready_for_benchmark_after_review": False,
            "expected": _expected("B"),
        },
        {"fixture_id": "noexp", "ready_for_benchmark_after_review": True, "expected": "not-a-dict"},
    ]
    loaded = oracle.load_ready_rows(_write_bundle(tmp_path, rows))
    assert [r["fixture_id"] for r in loaded] == ["ok"]


def test_ceiling_is_perfect_for_self_consistent_gt() -> None:
    """Feeding the GT reference text back in matches every field unit (ceiling 1.0)."""
    report = oracle.score_ceiling(_ready_rows(5))
    assert report["field_match_ratio_macro"] == 1.0
    assert report["field_match_ratio_micro"] == 1.0
    assert report["ingredient_recall"] == 1.0
    assert report["rows_scored"] == 5
    matched, total = report["field_matched_total"]
    assert total > 0 and matched == total  # every GT field unit matches its own text


def test_small_holdout_cannot_certify_even_a_perfect_ceiling() -> None:
    """A 3-row holdout has a Wilson lower bound below 0.85 despite a 1.0 point."""
    gate = oracle.score_ceiling(_ready_rows(3))["gates"]["0.85"]["field_match_macro"]
    assert gate["point"] == 1.0
    assert gate["point_met"] is True
    assert gate["certified"] is False  # lower bound < 0.85: n too small to certify
    assert gate["lower_bound"] < 0.85


def test_large_holdout_certifies_perfect_ceiling() -> None:
    """A 50-row perfect ceiling clears the 0.85 gate on the Wilson lower bound."""
    gate = oracle.score_ceiling(_ready_rows(50))["gates"]["0.85"]["field_match_macro"]
    assert gate["certified"] is True
    assert gate["lower_bound"] >= 0.85


def test_main_writes_report(tmp_path: Path) -> None:
    """The CLI writes a schema-tagged ceiling report for the bundle."""
    bundle = _write_bundle(tmp_path, _ready_rows(4))
    out = tmp_path / "ceiling.json"
    oracle.main(["--bundle-dir", str(bundle), "--output", str(out)])
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["schema_version"] == "oracle-text-ceiling-v1"
    assert report["rows_scored"] == 4
    assert "0.90" in report["gates"]
