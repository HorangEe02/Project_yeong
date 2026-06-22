"""Tests for PaddleOCR text extraction eval summary builder."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

builder = importlib.import_module("scripts.build_paddleocr_text_extraction_eval_summary")
target_gate = importlib.import_module("scripts.gate_paddleocr_text_extraction_target")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> Path:
    """Write JSONL rows.

    Args:
        path: Destination path.
        rows: JSON object rows.

    Returns:
        Written path.
    """
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    return path


def _fixture_row(**overrides: Any) -> dict[str, Any]:
    """Build one benchmark row.

    Args:
        overrides: Row overrides.

    Returns:
        Benchmark row.
    """
    row: dict[str, Any] = {
        "fixture_id": "fixture-1",
        "split": "holdout",
        "leakage_check_passed": True,
        "expected": {
            "verification_status": "human_reviewed",
            "ingredients": [{"display_name": "Vitamin C"}],
        },
        "observations": [
            {
                "provider": "paddleocr_local",
                "status": "completed",
                "normalized_text_precision": 0.97,
                "normalized_text_recall": 0.96,
                "normalized_text_f1": 0.965,
            }
        ],
    }
    row.update(overrides)
    return row


def test_builder_outputs_target_gate_compatible_summary(tmp_path: Path) -> None:
    """Verify complete observation metrics can feed the target gate."""
    manifest = _write_jsonl(tmp_path / "benchmark.jsonl", [_fixture_row()])

    summary = builder.build_paddleocr_text_extraction_eval_summary(
        benchmark_manifest=manifest,
        eval_split="holdout",
        leakage_check_passed=True,
        privacy_review_cleared=True,
    )
    summary_path = tmp_path / "summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False), encoding="utf-8")
    gate = target_gate.build_paddleocr_text_extraction_target_gate(
        eval_summary_path=summary_path,
        min_fixture_count=1,
    )

    assert summary["schema_version"] == "supplement-paddleocr-text-extraction-eval-summary-v1"
    assert summary["provider"] == "paddleocr_local"
    assert summary["fixture_count"] == 1
    assert summary["privacy_review_cleared"] is True
    assert summary["metric_complete_observation_count"] == 1
    assert summary["metrics"] == {
        "normalized_text_f1": 0.965,
        "normalized_text_precision": 0.97,
        "normalized_text_recall": 0.96,
    }
    assert gate["paddleocr_target_reached"] is True


def test_builder_counts_missing_metrics_as_zero_contribution(tmp_path: Path) -> None:
    """Verify absent metric evidence fails closed."""
    manifest = _write_jsonl(
        tmp_path / "benchmark.jsonl",
        [
            _fixture_row(),
            _fixture_row(
                fixture_id="fixture-2",
                observations=[
                    {
                        "provider": "paddleocr_local",
                        "status": "completed",
                    }
                ],
            ),
        ],
    )

    summary = builder.build_paddleocr_text_extraction_eval_summary(
        benchmark_manifest=manifest,
        eval_split="holdout",
        leakage_check_passed=True,
        privacy_review_cleared=True,
    )

    assert summary["fixture_count"] == 2
    assert summary["metric_complete_observation_count"] == 1
    assert summary["metric_missing_observation_count"] == 1
    assert summary["metrics"]["normalized_text_precision"] == 0.485


def test_builder_filters_non_holdout_rows_and_unreviewed_expected(tmp_path: Path) -> None:
    """Verify only requested split and human-reviewed GT count."""
    manifest = _write_jsonl(
        tmp_path / "benchmark.jsonl",
        [
            _fixture_row(split="train"),
            _fixture_row(
                fixture_id="fixture-2",
                expected={"verification_status": "provisional"},
            ),
            _fixture_row(fixture_id="fixture-3"),
        ],
    )

    summary = builder.build_paddleocr_text_extraction_eval_summary(
        benchmark_manifest=manifest,
        eval_split="holdout",
        leakage_check_passed=True,
        privacy_review_cleared=True,
    )

    assert summary["fixture_count"] == 1
    assert summary["skip_reason_counts"] == {
        "expected_not_human_reviewed": 1,
        "split_mismatch": 1,
    }


def test_builder_fails_leakage_flag_when_row_leakage_fails(tmp_path: Path) -> None:
    """Verify row-level leakage failure propagates to summary."""
    manifest = _write_jsonl(
        tmp_path / "benchmark.jsonl",
        [_fixture_row(leakage_check_passed=False)],
    )

    summary = builder.build_paddleocr_text_extraction_eval_summary(
        benchmark_manifest=manifest,
        eval_split="holdout",
        leakage_check_passed=True,
        privacy_review_cleared=True,
    )

    assert summary["row_leakage_checks_passed"] is False
    assert summary["leakage_check_passed"] is False


def test_builder_rejects_raw_ocr_text(tmp_path: Path) -> None:
    """Verify raw OCR text cannot enter the builder."""
    manifest = _write_jsonl(
        tmp_path / "benchmark.jsonl",
        [
            _fixture_row(
                observations=[
                    {
                        "provider": "paddleocr_local",
                        "raw_ocr_text": "secret",
                    }
                ]
            )
        ],
    )

    try:
        builder.build_paddleocr_text_extraction_eval_summary(
            benchmark_manifest=manifest,
            eval_split="holdout",
            leakage_check_passed=True,
            privacy_review_cleared=True,
        )
    except ValueError as exc:
        assert "raw_ocr_text" in str(exc)
    else:
        raise AssertionError("Expected raw OCR text rejection.")


def test_cli_writes_redacted_summary(tmp_path: Path, capsys: Any) -> None:
    """Verify CLI output hides metric values and local paths."""
    manifest = _write_jsonl(tmp_path / "benchmark.jsonl", [_fixture_row()])
    output = tmp_path / "summary.json"

    exit_code = builder.run_cli(
        [
            "--benchmark-manifest",
            str(manifest),
            "--output",
            str(output),
            "--eval-split",
            "holdout",
            "--leakage-check-passed",
            "--privacy-review-cleared",
        ]
    )

    stdout = capsys.readouterr().out
    written = json.loads(output.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert written["fixture_count"] == 1
    assert written["privacy_review_cleared"] is True
    assert "0.97" not in stdout
    assert str(tmp_path) not in stdout
