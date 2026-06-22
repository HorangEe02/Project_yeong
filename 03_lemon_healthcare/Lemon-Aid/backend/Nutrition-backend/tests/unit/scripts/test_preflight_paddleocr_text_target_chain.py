"""Tests for PaddleOCR text target-chain preflight."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

preflight = importlib.import_module("scripts.preflight_paddleocr_text_target_chain")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> Path:
    """Write JSONL rows.

    Args:
        path: Destination path.
        rows: JSON rows.

    Returns:
        Written path.
    """
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    return path


def _metric_row(**overrides: Any) -> dict[str, Any]:
    """Build one redacted metric fixture row.

    Args:
        overrides: Row overrides.

    Returns:
        Metric fixture row.
    """
    row: dict[str, Any] = {
        "schema_version": "supplement-paddleocr-text-metric-fixture-v1",
        "fixture_id": "fixture-1",
        "split": "holdout",
        "leakage_check_passed": True,
        "expected": {
            "verification_status": "human_reviewed",
            "text_ground_truth_present": True,
        },
        "observations": [
            {
                "provider": "paddleocr_local",
                "status": "completed",
                "normalized_text_precision": 0.97,
                "normalized_text_recall": 0.96,
                "normalized_text_f1": 0.965,
                "raw_ocr_text_stored": False,
                "raw_provider_payload_stored": False,
            }
        ],
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
    }
    row.update(overrides)
    return row


def test_preflight_reports_ready_for_complete_holdout_metric_manifest(tmp_path: Path) -> None:
    """Verify scoreable rows with complete metrics can proceed to target gate."""
    manifest = _write_jsonl(
        tmp_path / "metric.jsonl",
        [_metric_row(fixture_id=f"fixture-{index}") for index in range(1, 4)],
    )

    summary = preflight.build_paddleocr_text_target_chain_preflight(
        benchmark_manifest=manifest,
        eval_split="holdout",
        min_fixture_count=3,
    )

    assert summary["status"] == "ready_for_target_gate"
    assert summary["ready_for_target_gate"] is True
    assert summary["scoreable_fixture_count"] == 3
    assert summary["checks"]["all_eval_rows_have_complete_metrics"] is True
    assert summary["raw_ocr_text_stored"] is False
    assert summary["raw_provider_payload_stored"] is False


def test_preflight_blocks_candidate_manifest_before_benchmark_build(tmp_path: Path) -> None:
    """Verify current candidate rows are not mistaken for scoreable fixtures."""
    manifest = _write_jsonl(
        tmp_path / "candidates.jsonl",
        [
            {
                "schema_version": "supplement-review-ocr-ground-truth-candidate-v1",
                "fixture_id": "candidate-1",
                "ground_truth_status": "manual_required",
                "raw_ocr_text_stored": False,
                "raw_provider_payload_stored": False,
            }
        ],
    )

    summary = preflight.build_paddleocr_text_target_chain_preflight(
        benchmark_manifest=manifest,
        eval_split="holdout",
        min_fixture_count=1,
    )

    assert summary["status"] == "blocked_by_candidate_manifest"
    assert summary["ready_for_target_gate"] is False
    assert summary["candidate_schema_count"] == 1
    assert summary["unsupported_schema_count"] == 1
    assert summary["checks"]["candidate_manifest_requires_benchmark_build"] is True
    assert summary["skip_reason_counts"] == {
        "candidate_manifest_requires_benchmark_build": 1,
        "split_mismatch_or_missing": 1,
        "unsupported_row_schema": 1,
    }


def test_preflight_supports_legacy_candidate_schema_status(tmp_path: Path) -> None:
    """Verify older candidate schema names still produce the candidate blocker."""
    manifest = _write_jsonl(
        tmp_path / "legacy-candidates.jsonl",
        [
            {
                "schema_version": "supplement-learning-ocr-ground-truth-candidate-v1",
                "fixture_id": "candidate-legacy",
                "raw_ocr_text_stored": False,
                "raw_provider_payload_stored": False,
            }
        ],
    )

    summary = preflight.build_paddleocr_text_target_chain_preflight(
        benchmark_manifest=manifest,
        eval_split="holdout",
        min_fixture_count=1,
    )

    assert summary["status"] == "blocked_by_candidate_manifest"
    assert summary["candidate_schema_count"] == 1
    assert summary["ready_for_target_gate"] is False


def test_preflight_blocks_rows_without_provider_metrics(tmp_path: Path) -> None:
    """Verify complete GT without numeric metrics is not target-gate ready."""
    row = _metric_row(
        observations=[
            {
                "provider": "paddleocr_local",
                "status": "completed",
                "raw_ocr_text_stored": False,
                "raw_provider_payload_stored": False,
            }
        ]
    )
    manifest = _write_jsonl(tmp_path / "metric.jsonl", [row])

    summary = preflight.build_paddleocr_text_target_chain_preflight(
        benchmark_manifest=manifest,
        eval_split="holdout",
        min_fixture_count=1,
    )

    assert summary["status"] == "blocked_by_missing_provider_metrics"
    assert summary["ready_for_target_gate"] is False
    assert summary["metric_complete_observation_count"] == 0
    assert summary["skip_reason_counts"]["provider_metrics_incomplete"] == 1


def test_preflight_rejects_raw_ocr_text_payload(tmp_path: Path) -> None:
    """Verify raw OCR text cannot enter readiness summaries."""
    manifest = _write_jsonl(
        tmp_path / "unsafe.jsonl",
        [_metric_row(raw_ocr_text="raw text must stay private")],
    )

    try:
        preflight.build_paddleocr_text_target_chain_preflight(
            benchmark_manifest=manifest,
            eval_split="holdout",
            min_fixture_count=1,
        )
    except ValueError as exc:
        assert "raw_ocr_text" in str(exc)
    else:
        raise AssertionError("Expected raw OCR text rejection.")


def test_cli_writes_redacted_json_and_markdown(tmp_path: Path, capsys: Any) -> None:
    """Verify CLI output omits metric values and local temp paths."""
    manifest = _write_jsonl(tmp_path / "metric.jsonl", [_metric_row()])
    output = tmp_path / "preflight.json"
    markdown_output = tmp_path / "preflight.md"

    exit_code = preflight.run_cli(
        [
            "--benchmark-manifest",
            str(manifest),
            "--output",
            str(output),
            "--markdown-output",
            str(markdown_output),
            "--eval-split",
            "holdout",
            "--min-fixtures",
            "1",
        ]
    )

    stdout = capsys.readouterr().out
    written = json.loads(output.read_text(encoding="utf-8"))
    markdown = markdown_output.read_text(encoding="utf-8")
    assert exit_code == 0
    assert written["ready_for_target_gate"] is True
    assert "0.97" not in stdout
    assert str(tmp_path) not in stdout
    assert "0.97" not in markdown
    assert str(tmp_path) not in markdown
