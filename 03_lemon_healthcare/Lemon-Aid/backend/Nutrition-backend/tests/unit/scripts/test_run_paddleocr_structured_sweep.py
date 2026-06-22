"""Tests for the PaddleOCR structured sweep runner."""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

sweep = importlib.import_module("scripts.run_paddleocr_structured_sweep")


def _write_bundle(bundle_dir: Path) -> None:
    """Write a minimal ready benchmark bundle."""
    bundle_dir.mkdir()
    (bundle_dir / "ground-truth.todo.jsonl").write_text(
        json.dumps(
            {
                "fixture_id": "fixture-1",
                "image_path": "image.jpg",
                "ready_for_benchmark_after_review": True,
                "expected": {"ingredients": [{"display_name": "비타민 C"}]},
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


def _fake_eval(**_: Any) -> dict[str, Any]:
    """Return a redacted fake PaddleOCR eval payload."""
    return {
        "schema_version": "paddleocr-clova-eval-v3",
        "recognition_model_dir_present": True,
        "per_image": [
            {
                "fixture_id": "fixture-1",
                "field_match_ratio": 1.0,
                "field_matched": 1,
                "field_total": 1,
                "ingredient_found": 1,
                "ingredient_total": 1,
            }
        ],
        "observations": [
            {
                "fixture_id": "fixture-1",
                "provider": "paddleocr_local",
                "status": "completed",
            }
        ],
    }


def test_run_sweep_writes_redacted_gate_artifacts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Verify quick sweep creates summaries and best metric selectors."""
    bundle_dir = tmp_path / "bundle"
    output_dir = tmp_path / "out"
    splits = tmp_path / "splits.jsonl"
    _write_bundle(bundle_dir)
    splits.write_text(
        json.dumps({"fixture_id": "fixture-1", "split": "holdout"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(sweep, "evaluate", _fake_eval)
    args = argparse.Namespace(
        bundle_dir=bundle_dir,
        splits=splits,
        output_dir=output_dir,
        profile="server_detection",
        det_model=None,
        rec_model=None,
        rec_model_dir="/private/model",
        max_side=None,
        post_pass="ingredient_alias_amount_unit",
        preset="quick",
        eval_split="holdout",
        provider="paddleocr_local",
        target_threshold="0.90",
        min_ingredient_recall="0.85",
        min_fixtures=1,
        limit=None,
        apply=True,
    )

    result = sweep.run_sweep(args)

    assert result["best_by"]["field_match_ratio_macro"]["config"] == "baseline"
    assert (output_dir / "structured-extraction-gate.baseline.json").is_file()
    assert (output_dir / "structured-extraction-summary.box04.json").is_file()
    assert "/private/model" not in json.dumps(result, ensure_ascii=False)
    assert "/private/model" not in (output_dir / "paddleocr-eval.baseline.json").read_text(
        encoding="utf-8"
    )
