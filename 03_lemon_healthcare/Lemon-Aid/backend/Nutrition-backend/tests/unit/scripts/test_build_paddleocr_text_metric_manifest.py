"""Tests for private PaddleOCR text metric manifest builder."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

metric_builder = importlib.import_module("scripts.build_paddleocr_text_metric_manifest")
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


def _private_row(**overrides: Any) -> dict[str, Any]:
    """Build one private text metric fixture.

    Args:
        overrides: Row overrides.

    Returns:
        Private input row.
    """
    row: dict[str, Any] = {
        "fixture_id": "fixture-1",
        "split": "holdout",
        "leakage_check_passed": True,
        "expected": {
            "verification_status": "human_reviewed",
            "text": "Vitamin C 500 mg",
        },
        "observations": [
            {
                "provider": "paddleocr_local",
                "status": "completed",
                "text": "Vitamin C 500 mg",
            }
        ],
    }
    row.update(overrides)
    return row


def test_metric_manifest_feeds_summary_builder_and_target_gate(tmp_path: Path) -> None:
    """Verify exact private text scores pass the full 95 percent gate chain."""
    private_manifest = _write_jsonl(tmp_path / "private.jsonl", [_private_row()])

    rows, metric_summary = metric_builder.build_paddleocr_text_metric_manifest(
        private_text_manifest=private_manifest,
        provider="paddleocr_local",
        eval_split="holdout",
        leakage_check_passed=True,
    )
    metric_manifest = _write_jsonl(tmp_path / "metric.jsonl", rows)
    eval_summary = summary_builder.build_paddleocr_text_extraction_eval_summary(
        benchmark_manifest=metric_manifest,
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

    assert metric_summary["output_fixture_count"] == 1
    assert rows[0]["observations"][0]["normalized_text_precision"] == 1.0
    assert rows[0]["observations"][0]["normalized_text_recall"] == 1.0
    assert rows[0]["observations"][0]["normalized_text_f1"] == 1.0
    assert eval_summary["fixture_count"] == 1
    assert gate["paddleocr_target_reached"] is True
    assert "Vitamin" not in json.dumps(rows, ensure_ascii=False)


def test_metric_manifest_penalizes_extra_hypothesis_text(tmp_path: Path) -> None:
    """Verify hallucinated OCR characters reduce precision."""
    private_manifest = _write_jsonl(
        tmp_path / "private.jsonl",
        [
            _private_row(
                expected={"verification_status": "human_reviewed", "text": "abc"},
                observations=[
                    {
                        "provider": "paddleocr_local",
                        "text": "abcxyz",
                    }
                ],
            )
        ],
    )

    rows, _summary = metric_builder.build_paddleocr_text_metric_manifest(
        private_text_manifest=private_manifest,
        provider="paddleocr_local",
        eval_split="holdout",
        leakage_check_passed=True,
    )
    metrics = rows[0]["observations"][0]

    assert metrics["matched_char_count"] == 3
    assert metrics["reference_char_count"] == 3
    assert metrics["hypothesis_char_count"] == 6
    assert metrics["normalized_text_precision"] == 0.5
    assert metrics["normalized_text_recall"] == 1.0
    assert metrics["normalized_text_f1"] == 0.6667


def test_metric_manifest_penalizes_missing_reference_characters(tmp_path: Path) -> None:
    """Verify omitted OCR characters reduce recall."""
    private_manifest = _write_jsonl(
        tmp_path / "private.jsonl",
        [
            _private_row(
                expected={"verification_status": "human_reviewed", "text": "abcde"},
                observations=[
                    {
                        "provider": "paddleocr_local",
                        "text": "abde",
                    }
                ],
            )
        ],
    )

    rows, _summary = metric_builder.build_paddleocr_text_metric_manifest(
        private_text_manifest=private_manifest,
        provider="paddleocr_local",
        eval_split="holdout",
        leakage_check_passed=True,
    )
    metrics = rows[0]["observations"][0]

    assert metrics["matched_char_count"] == 4
    assert metrics["normalized_text_precision"] == 1.0
    assert metrics["normalized_text_recall"] == 0.8
    assert metrics["normalized_text_f1"] == 0.8889


def test_metric_manifest_filters_split_and_unreviewed_expected(tmp_path: Path) -> None:
    """Verify only requested split and human-reviewed GT are emitted."""
    private_manifest = _write_jsonl(
        tmp_path / "private.jsonl",
        [
            _private_row(split="train"),
            _private_row(
                fixture_id="fixture-2",
                expected={"verification_status": "provisional", "text": "Vitamin C"},
            ),
            _private_row(fixture_id="fixture-3"),
        ],
    )

    rows, summary = metric_builder.build_paddleocr_text_metric_manifest(
        private_text_manifest=private_manifest,
        provider="paddleocr_local",
        eval_split="holdout",
        leakage_check_passed=True,
    )

    assert len(rows) == 1
    assert rows[0]["fixture_id"] == "fixture-3"
    assert summary["skip_reason_counts"] == {
        "expected_not_human_reviewed": 1,
        "split_mismatch": 1,
    }


def test_metric_manifest_uses_structured_expected_text_fallback(tmp_path: Path) -> None:
    """Verify structured expected fields can form a private reference string."""
    private_manifest = _write_jsonl(
        tmp_path / "private.jsonl",
        [
            _private_row(
                expected={
                    "verification_status": "human_reviewed",
                    "product_name": "ZMA",
                    "ingredients": [
                        {"display_name": "Magnesium", "amount": 100, "unit": "mg"},
                    ],
                    "intake_method": {"text": "Take daily"},
                    "precautions": [{"text": "Consult pharmacist"}],
                },
                observations=[
                    {
                        "provider": "paddleocr_local",
                        "text": "ZMA Magnesium 100 mg Take daily Consult pharmacist",
                    }
                ],
            )
        ],
    )

    rows, summary = metric_builder.build_paddleocr_text_metric_manifest(
        private_text_manifest=private_manifest,
        provider="paddleocr_local",
        eval_split="holdout",
        leakage_check_passed=True,
    )

    assert rows[0]["expected"]["text_source"] == "expected.structured_sections"
    assert rows[0]["observations"][0]["normalized_text_f1"] == 1.0
    assert summary["expected_text_source_counts"] == {"expected.structured_sections": 1}


def test_metric_manifest_marks_row_leakage_failure(tmp_path: Path) -> None:
    """Verify row-level leakage failures are preserved for downstream gates."""
    private_manifest = _write_jsonl(
        tmp_path / "private.jsonl",
        [_private_row(leakage_check_passed=False)],
    )

    rows, summary = metric_builder.build_paddleocr_text_metric_manifest(
        private_text_manifest=private_manifest,
        provider="paddleocr_local",
        eval_split="holdout",
        leakage_check_passed=True,
    )

    assert rows[0]["leakage_check_passed"] is False
    assert summary["leakage_check_passed"] is True


def test_metric_manifest_rejects_unsafe_fixture_id(tmp_path: Path) -> None:
    """Verify local paths cannot become fixture identifiers in output."""
    private_manifest = _write_jsonl(
        tmp_path / "private.jsonl",
        [_private_row(fixture_id="/Users/example/private.png")],
    )

    try:
        metric_builder.build_paddleocr_text_metric_manifest(
            private_text_manifest=private_manifest,
            provider="paddleocr_local",
            eval_split="holdout",
            leakage_check_passed=True,
        )
    except ValueError as exc:
        assert "fixture_id" in str(exc)
    else:
        raise AssertionError("Expected unsafe fixture id rejection.")


def test_metric_manifest_cli_writes_no_raw_text(tmp_path: Path, capsys: Any) -> None:
    """Verify CLI output and artifacts are redacted."""
    private_manifest = _write_jsonl(tmp_path / "private.jsonl", [_private_row()])
    output = tmp_path / "metric.jsonl"
    summary = tmp_path / "summary.json"

    exit_code = metric_builder.run_cli(
        [
            "--private-text-manifest",
            str(private_manifest),
            "--output",
            str(output),
            "--summary",
            str(summary),
            "--eval-split",
            "holdout",
            "--leakage-check-passed",
        ]
    )

    stdout = capsys.readouterr().out
    written = output.read_text(encoding="utf-8")
    assert exit_code == 0
    assert "Vitamin" not in stdout
    assert "Vitamin" not in written
    assert str(tmp_path) not in stdout
    assert json.loads(summary.read_text(encoding="utf-8"))["output_fixture_count"] == 1
