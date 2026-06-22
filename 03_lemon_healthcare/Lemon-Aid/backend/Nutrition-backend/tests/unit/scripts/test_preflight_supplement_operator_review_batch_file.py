"""Tests for one supplement operator review batch file preflight."""

from __future__ import annotations

import csv
import importlib
import json
import sys
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

batch_file = importlib.import_module("scripts.preflight_supplement_operator_review_batch_file")


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    """Write a JSON fixture.

    Args:
        path: Destination path.
        payload: JSON payload.

    Returns:
        Written path.
    """
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return path


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> Path:
    """Write JSONL fixture rows.

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


def _write_csv(path: Path, rows: list[dict[str, str]]) -> Path:
    """Write CSV fixture rows.

    Args:
        path: Destination path.
        rows: CSV rows.

    Returns:
        Written path.
    """
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return path


def _batch_plan() -> dict[str, Any]:
    """Return a minimal redacted batch plan fixture.

    Returns:
        Batch plan payload.
    """
    return {
        "schema_version": "supplement-operator-review-batch-plan-v1",
        "batches": [
            {
                "batch_key": "brand_product_review:001",
                "queue_key": "brand_product_review",
                "row_index_start": 1,
                "row_index_end": 2,
                "editable_file_name": "decisions.todo.jsonl",
                "db_write_performed": False,
                "external_provider_call_performed": False,
                "llm_call_performed": False,
                "training_execution_performed_by_script": False,
                "source_image_read_performed": False,
                "raw_ocr_text_stored": False,
                "raw_provider_payload_stored": False,
                "absolute_paths_stored": False,
                "product_dir_literals_stored": False,
                "local_path_literals_stored": False,
            }
        ],
        "db_write_performed": False,
        "external_provider_call_performed": False,
        "llm_call_performed": False,
        "training_execution_performed_by_script": False,
        "source_image_read_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "local_path_literals_stored": False,
    }


def _blank_brand_row(fixture_id: str) -> dict[str, Any]:
    """Return a blank brand decision row.

    Args:
        fixture_id: Fixture id.

    Returns:
        Decision row.
    """
    return {
        "schema_version": "supplement-brand-review-decision-v1",
        "fixture_id": fixture_id,
        "brand_review_decision": {
            "decision": "",
            "reviewer_id": "",
            "reviewed_at": "",
            "reviewed_manufacturer": "",
            "reviewed_product_name": "",
            "reason_codes": [],
            "attest_brand_product_review_completed": False,
            "attest_not_using_product_folder_literal_as_manufacturer": False,
            "attest_product_name_reviewed_from_label_or_safe_catalog": False,
            "attest_no_raw_ocr_or_provider_payload_copied": False,
            "attest_db_import_allowed": False,
        },
    }


def _valid_brand_row(fixture_id: str) -> dict[str, Any]:
    """Return a valid approved brand decision row.

    Args:
        fixture_id: Fixture id.

    Returns:
        Decision row.
    """
    row = _blank_brand_row(fixture_id)
    row["brand_review_decision"] = {
        "decision": "approve",
        "reviewer_id": "operator_batch",
        "reviewed_at": "2026-06-04T00:00:00Z",
        "reviewed_manufacturer": "Safe Maker",
        "reviewed_product_name": "Safe Product",
        "reason_codes": ["reviewed_label_or_catalog"],
        "attest_brand_product_review_completed": True,
        "attest_not_using_product_folder_literal_as_manufacturer": True,
        "attest_product_name_reviewed_from_label_or_safe_catalog": True,
        "attest_no_raw_ocr_or_provider_payload_copied": True,
        "attest_db_import_allowed": True,
    }
    return row


def _review_csv_row(fixture_id: str, product_name: str) -> dict[str, str]:
    """Return one batch review CSV row.

    Args:
        fixture_id: Fixture id.
        product_name: Product text used to verify redaction.

    Returns:
        CSV row.
    """
    return {
        "fixture_id": fixture_id,
        "category_key": "supplement_category",
        "brand_candidate_display_name": "Visible Brand",
        "reviewed_product_name": product_name,
        "decision": "",
    }


def _input_paths(
    tmp_path: Path,
    rows: list[dict[str, Any]],
    *,
    review_csv_rows: list[dict[str, str]] | None = None,
) -> dict[str, Path]:
    """Write default input fixtures.

    Args:
        tmp_path: Temporary directory.
        rows: Batch rows.
        review_csv_rows: Optional batch-local review CSV rows.

    Returns:
        Input path mapping.
    """
    paths = {
        "batch_plan": _write_json(tmp_path / "batch-plan.json", _batch_plan()),
        "batch_file": _write_jsonl(tmp_path / "brand_product_review-001.jsonl", rows),
    }
    if review_csv_rows is not None:
        paths["batch_review_csv"] = _write_csv(
            tmp_path / "brand_product_review-001.review.csv", review_csv_rows
        )
    return paths


def test_batch_file_preflight_reports_blank_batch(tmp_path: Path) -> None:
    """Verify untouched batch rows stay pending before reconcile."""
    summary = batch_file.preflight_operator_review_batch_file(
        input_paths=_input_paths(
            tmp_path,
            [_blank_brand_row("brand_review_1"), _blank_brand_row("brand_review_2")],
        ),
        batch_key="brand_product_review:001",
    )

    assert summary["batch_status"] == "pending"
    assert summary["ready_for_reconcile"] is False
    assert summary["blank_row_count"] == 2
    assert summary["valid_row_count"] == 0
    assert summary["reason_counts"] == {"blank_decision": 2}


def test_batch_file_preflight_allows_complete_batch(tmp_path: Path) -> None:
    """Verify a fully reviewed batch can move to reconciliation."""
    summary = batch_file.preflight_operator_review_batch_file(
        input_paths=_input_paths(
            tmp_path,
            [_valid_brand_row("brand_review_1"), _valid_brand_row("brand_review_2")],
        ),
        batch_key="brand_product_review:001",
    )

    assert summary["batch_status"] == "complete"
    assert summary["ready_for_reconcile"] is True
    assert summary["valid_row_count"] == 2
    assert summary["blank_row_count"] == 0
    assert summary["next_steps"][0] == "run_reconcile_operator_batch_files"


def test_batch_file_preflight_validates_matching_review_csv(tmp_path: Path) -> None:
    """Verify paired review CSV row order is validated without leaking text."""
    paths = _input_paths(
        tmp_path,
        [_blank_brand_row("brand_review_1"), _blank_brand_row("brand_review_2")],
        review_csv_rows=[
            _review_csv_row("brand_review_1", "Visible Product A"),
            _review_csv_row("brand_review_2", "Visible Product B"),
        ],
    )

    summary = batch_file.preflight_operator_review_batch_file(
        input_paths=paths,
        batch_key="brand_product_review:001",
    )
    markdown = batch_file.build_markdown(summary)
    dumped = json.dumps(summary, ensure_ascii=False) + markdown

    assert summary["batch_review_csv_name"] == "brand_product_review-001.review.csv"
    assert summary["batch_review_csv_status"] == "matched"
    assert summary["batch_review_csv_row_count"] == 2
    assert summary["batch_review_csv_matches_batch"] is True
    assert "Visible Product A" not in dumped
    assert "brand_review_1" not in dumped
    assert str(tmp_path) not in dumped


def test_batch_file_preflight_rejects_mismatched_review_csv(tmp_path: Path) -> None:
    """Verify CSV context must match the batch JSONL row order."""
    paths = _input_paths(
        tmp_path,
        [_blank_brand_row("brand_review_1"), _blank_brand_row("brand_review_2")],
        review_csv_rows=[
            _review_csv_row("brand_review_2", "Visible Product B"),
            _review_csv_row("brand_review_1", "Visible Product A"),
        ],
    )

    try:
        batch_file.preflight_operator_review_batch_file(
            input_paths=paths,
            batch_key="brand_product_review:001",
        )
    except batch_file.BatchFilePreflightError as exc:
        assert "fixture order" in str(exc).casefold()
    else:
        raise AssertionError("mismatched CSV context should fail closed")


def test_batch_file_preflight_blocks_extra_rows(tmp_path: Path) -> None:
    """Verify row count drift blocks reconciliation."""
    summary = batch_file.preflight_operator_review_batch_file(
        input_paths=_input_paths(
            tmp_path,
            [
                _valid_brand_row("brand_review_1"),
                _valid_brand_row("brand_review_2"),
                _valid_brand_row("brand_review_3"),
            ],
        ),
        batch_key="brand_product_review:001",
    )

    assert summary["batch_status"] == "invalid"
    assert summary["ready_for_reconcile"] is False
    assert summary["extra_row_count"] == 1
    assert summary["reason_counts"]["extra_rows"] == 1


def test_batch_file_preflight_cli_writes_redacted_markdown(
    tmp_path: Path,
    capsys: Any,
) -> None:
    """Verify CLI output is aggregate-only and Markdown is well formed."""
    paths = _input_paths(
        tmp_path,
        [_valid_brand_row("brand_review_1"), _valid_brand_row("brand_review_2")],
    )
    output_path = tmp_path / "summary.json"
    markdown_path = tmp_path / "summary.md"

    batch_file.main(
        [
            "--batch-plan",
            str(paths["batch_plan"]),
            "--batch-key",
            "brand_product_review:001",
            "--batch-file",
            str(paths["batch_file"]),
            "--batch-review-csv",
            str(
                _write_csv(
                    tmp_path / "brand_product_review-001.review.csv",
                    [
                        _review_csv_row("brand_review_1", "Visible Product A"),
                        _review_csv_row("brand_review_2", "Visible Product B"),
                    ],
                )
            ),
            "--output",
            str(output_path),
            "--markdown-output",
            str(markdown_path),
        ]
    )

    stdout = capsys.readouterr().out
    summary = json.loads(output_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    combined = "\n".join([stdout, json.dumps(summary, ensure_ascii=False), markdown])
    assert summary["ready_for_reconcile"] is True
    assert summary["batch_review_csv_matches_batch"] is True
    assert "- Batch: `brand_product_review:001`" in markdown
    assert "Visible Product A" not in combined
    assert str(tmp_path) not in combined
    assert "/private/" not in combined
