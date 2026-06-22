"""Tests for supplement OCR ground-truth manifest preflight."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

preflight = importlib.import_module("scripts.preflight_supplement_ocr_ground_truth_manifest")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> Path:
    """Write JSONL rows.

    Args:
        path: Destination path.
        rows: Rows to write.

    Returns:
        Written path.
    """
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    return path


def _ground_truth_row(**overrides: Any) -> dict[str, Any]:
    """Return one human-reviewed ground-truth row.

    Args:
        overrides: Row overrides.

    Returns:
        Ground-truth row.
    """
    row: dict[str, Any] = {
        "schema_version": "supplement-ocr-ground-truth-template-row-v1",
        "fixture_id": "review-ocr-gt-001",
        "ground_truth_status": "human_reviewed",
        "contains_personal_data": False,
        "ready_for_benchmark_after_review": True,
        "expected": {
            "verification_status": "human_reviewed",
            "product_name": "Omega 3",
            "manufacturer": "Now Foods",
            "ingredients": [{"display_name": "EPA", "amount": 180, "unit": "mg"}],
            "intake_method": {"text": "Take 1 softgel daily with food."},
            "precautions": [{"text": "Consult a physician before use."}],
            "allergen_warnings": [{"text": "Contains fish."}],
        },
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
    }
    row.update(overrides)
    return row


def test_preflight_reports_ready_for_reviewed_complete_rows(tmp_path: Path) -> None:
    """Verify complete human-reviewed rows can proceed to benchmark build."""
    manifest = _write_jsonl(tmp_path / "gt.jsonl", [_ground_truth_row()])

    summary = preflight.build_ground_truth_preflight(
        ground_truth_manifest=manifest,
        required_expected_sections=("ingredient_amounts", "intake_method", "precautions"),
    )

    assert summary["status"] == "ready_for_benchmark_build"
    assert summary["ready_for_benchmark_build"] is True
    assert summary["benchmark_ready_row_count"] == 1
    assert summary["issue_counts"] == {}
    assert summary["missing_required_section_counts"] == {}


def test_preflight_blocks_rows_not_marked_ready_after_review(tmp_path: Path) -> None:
    """Verify template rows need the explicit ready flag after double-checking."""
    manifest = _write_jsonl(
        tmp_path / "gt.jsonl",
        [_ground_truth_row(ready_for_benchmark_after_review=False)],
    )

    summary = preflight.build_ground_truth_preflight(ground_truth_manifest=manifest)

    assert summary["status"] == "blocked_by_manual_review"
    assert summary["ready_for_benchmark_build"] is False
    assert summary["issue_counts"] == {
        "manual_ground_truth_not_marked_ready_for_benchmark": 1,
    }


def test_preflight_counts_missing_required_sections_without_text_output(tmp_path: Path) -> None:
    """Verify missing intake, precautions, and allergen sections are counted only."""
    row = _ground_truth_row()
    row["expected"]["intake_method"] = {}
    row["expected"]["precautions"] = []
    row["expected"]["allergen_warnings"] = []
    manifest = _write_jsonl(tmp_path / "gt.jsonl", [row])

    summary = preflight.build_ground_truth_preflight(
        ground_truth_manifest=manifest,
        required_expected_sections=(
            "ingredient_amounts",
            "intake_method",
            "precautions",
            "allergen_warnings",
        ),
    )

    assert summary["status"] == "blocked_by_missing_required_sections"
    assert summary["benchmark_ready_row_count"] == 0
    assert summary["missing_required_section_counts"] == {
        "allergen_warnings": 1,
        "intake_method": 1,
        "precautions": 1,
    }


def test_preflight_rejects_raw_ocr_payload(tmp_path: Path) -> None:
    """Verify raw OCR text cannot enter the preflight report."""
    row = _ground_truth_row(raw_ocr_text="raw text must stay private")
    manifest = _write_jsonl(tmp_path / "gt.jsonl", [row])

    with pytest.raises(ValueError, match="raw_ocr_text"):
        preflight.build_ground_truth_preflight(ground_truth_manifest=manifest)


def test_cli_writes_redacted_json_and_markdown(tmp_path: Path, capsys: Any) -> None:
    """Verify CLI artifacts omit local temp paths and raw expected text."""
    manifest = _write_jsonl(tmp_path / "gt.jsonl", [_ground_truth_row()])
    output = tmp_path / "preflight.json"
    markdown_output = tmp_path / "preflight.md"

    exit_code = preflight.run_cli(
        [
            "--ground-truth",
            str(manifest),
            "--output",
            str(output),
            "--markdown-output",
            str(markdown_output),
        ]
    )

    stdout = capsys.readouterr().out
    written = output.read_text(encoding="utf-8")
    markdown = markdown_output.read_text(encoding="utf-8")
    assert exit_code == 0
    assert str(tmp_path) not in stdout
    assert str(tmp_path) not in written
    assert str(tmp_path) not in markdown
    assert "Take 1 softgel" not in written
    assert "Contains fish" not in markdown
