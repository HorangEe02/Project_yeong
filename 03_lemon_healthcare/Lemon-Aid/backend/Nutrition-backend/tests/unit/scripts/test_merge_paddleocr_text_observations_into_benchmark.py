"""Tests for merging redacted PaddleOCR observations into benchmark rows."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

merger = importlib.import_module("scripts.merge_paddleocr_text_observations_into_benchmark")
summary_builder = importlib.import_module("scripts.build_paddleocr_text_extraction_eval_summary")
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


def _benchmark_row(**overrides: Any) -> dict[str, Any]:
    """Build one benchmark fixture row."""
    row: dict[str, Any] = {
        "schema_version": "supplement-ocr-provider-benchmark-fixture-v1",
        "fixture_id": "fixture-1",
        "split": "holdout",
        "leakage_check_passed": True,
        "expected": {
            "verification_status": "human_reviewed",
            "ingredients": [{"display_name": "Vitamin C"}],
        },
    }
    row.update(overrides)
    return row


def _observation_row(**overrides: Any) -> dict[str, Any]:
    """Build one redacted flat provider observation row."""
    row: dict[str, Any] = {
        "fixture_id": "fixture-1",
        "provider": "paddleocr_local",
        "status": "completed",
        "text_non_empty": True,
        "normalized_text_precision": 0.98,
        "normalized_text_recall": 0.97,
        "normalized_text_f1": 0.975,
    }
    row.update(overrides)
    return row


def test_merge_outputs_summary_builder_and_target_gate_compatible_rows(tmp_path: Path) -> None:
    """Verify flat collector observations can feed the 95 percent gate chain."""
    benchmark = _write_jsonl(tmp_path / "benchmark.jsonl", [_benchmark_row()])
    observations = _write_jsonl(tmp_path / "observations.jsonl", [_observation_row()])

    rows, merge_summary = merger.merge_observations_into_benchmark(
        benchmark_manifest=benchmark,
        observation_paths=(observations,),
    )
    merged_manifest = _write_jsonl(tmp_path / "merged.jsonl", rows)
    eval_summary = summary_builder.build_paddleocr_text_extraction_eval_summary(
        benchmark_manifest=merged_manifest,
        provider="paddleocr_local",
        eval_split="holdout",
        leakage_check_passed=True,
        privacy_review_cleared=True,
    )
    eval_summary_path = tmp_path / "eval-summary.json"
    eval_summary_path.write_text(json.dumps(eval_summary, ensure_ascii=False), encoding="utf-8")
    gate = target_gate.build_paddleocr_text_extraction_target_gate(
        eval_summary_path=eval_summary_path,
        min_fixture_count=1,
    )

    assert merge_summary["observation_count"] == 1
    assert merge_summary["fixtures_with_observations"] == 1
    assert rows[0]["observations"][0]["provider"] == "paddleocr_local"
    assert eval_summary["metrics"] == {
        "normalized_text_f1": 0.975,
        "normalized_text_precision": 0.98,
        "normalized_text_recall": 0.97,
    }
    assert gate["paddleocr_target_reached"] is True


def test_merge_rejects_unmatched_observation_by_default(tmp_path: Path) -> None:
    """Verify unmatched provider observations cannot disappear silently."""
    benchmark = _write_jsonl(tmp_path / "benchmark.jsonl", [_benchmark_row()])
    observations = _write_jsonl(
        tmp_path / "observations.jsonl",
        [_observation_row(fixture_id="missing-fixture")],
    )

    try:
        merger.merge_observations_into_benchmark(
            benchmark_manifest=benchmark,
            observation_paths=(observations,),
        )
    except ValueError as exc:
        assert "fixture_id not found" in str(exc)
    else:
        raise AssertionError("Expected unmatched observation rejection.")


def test_merge_can_ignore_unmatched_observation_explicitly(tmp_path: Path) -> None:
    """Verify unmatched observations are ignored only with an explicit flag."""
    benchmark = _write_jsonl(tmp_path / "benchmark.jsonl", [_benchmark_row()])
    observations = _write_jsonl(
        tmp_path / "observations.jsonl",
        [_observation_row(fixture_id="missing-fixture")],
    )

    rows, summary = merger.merge_observations_into_benchmark(
        benchmark_manifest=benchmark,
        observation_paths=(observations,),
        allow_unmatched_observations=True,
    )

    assert rows[0]["observations"] == []
    assert summary["unmatched_observation_count"] == 1
    assert summary["observation_count"] == 0


def test_merge_rejects_raw_observation_text(tmp_path: Path) -> None:
    """Verify raw OCR text cannot be merged into benchmark artifacts."""
    benchmark = _write_jsonl(tmp_path / "benchmark.jsonl", [_benchmark_row()])
    observations = _write_jsonl(
        tmp_path / "observations.jsonl",
        [_observation_row(raw_ocr_text="secret text")],
    )

    try:
        merger.merge_observations_into_benchmark(
            benchmark_manifest=benchmark,
            observation_paths=(observations,),
        )
    except ValueError as exc:
        assert "raw_ocr_text" in str(exc)
    else:
        raise AssertionError("Expected raw OCR text rejection.")


def test_merge_cli_writes_redacted_artifacts(tmp_path: Path, capsys: Any) -> None:
    """Verify CLI output hides local paths and raw metric values."""
    benchmark = _write_jsonl(tmp_path / "benchmark.jsonl", [_benchmark_row()])
    observations = _write_jsonl(tmp_path / "observations.jsonl", [_observation_row()])
    output = tmp_path / "merged.jsonl"
    summary = tmp_path / "summary.json"

    exit_code = merger.run_cli(
        [
            "--benchmark-manifest",
            str(benchmark),
            "--observations",
            str(observations),
            "--output",
            str(output),
            "--summary",
            str(summary),
        ]
    )

    stdout = capsys.readouterr().out
    assert exit_code == 0
    assert "0.98" not in stdout
    assert str(tmp_path) not in stdout
    assert json.loads(summary.read_text(encoding="utf-8"))["observation_count"] == 1
    assert json.loads(output.read_text(encoding="utf-8").splitlines()[0])["observations"]
