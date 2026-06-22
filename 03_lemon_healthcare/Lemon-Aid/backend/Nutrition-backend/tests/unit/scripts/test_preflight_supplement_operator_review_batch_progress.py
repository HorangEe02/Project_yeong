"""Tests for supplement operator review batch progress preflight."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

progress = importlib.import_module("scripts.preflight_supplement_operator_review_batch_progress")


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


def _batch_plan() -> dict[str, Any]:
    """Return a small batch plan fixture.

    Returns:
        Batch plan payload.
    """
    return {
        "schema_version": "supplement-operator-review-batch-plan-v1",
        "batch_count": 4,
        "batch_size": 2,
        "pending_queue_count": 3,
        "total_pending_operator_action_count": 7,
        "batches": [
            _batch("brand_product_review:001", "brand_product_review", 1, 2),
            _batch("brand_product_review:002", "brand_product_review", 3, 3),
            _batch("review_pii_screening:001", "review_pii_screening", 1, 2),
            _batch("yolo_section_annotation:001", "yolo_section_annotation", 1, 2),
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


def _batch(batch_key: str, queue_key: str, start: int, end: int) -> dict[str, Any]:
    """Return one batch row fixture.

    Args:
        batch_key: Batch key.
        queue_key: Queue key.
        start: One-based start row.
        end: One-based end row.

    Returns:
        Batch row.
    """
    return {
        "batch_key": batch_key,
        "queue_key": queue_key,
        "batch_status": "pending",
        "row_index_start": start,
        "row_index_end": end,
        "pending_row_count": end - start + 1,
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
        "reviewed_at": "2026-06-03T00:00:00Z",
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


def _blank_pii_row(fixture_id: str) -> dict[str, Any]:
    """Return a blank PII decision row.

    Args:
        fixture_id: Fixture id.

    Returns:
        Decision row.
    """
    return {
        "schema_version": "supplement-review-pii-screening-decision-v1",
        "fixture_id": fixture_id,
        "pii_screening_decision": {
            "decision": "",
            "reviewer_id": "",
            "reviewed_at": "",
            "reason_codes": [],
            "attest_local_screening_completed": False,
            "attest_no_personal_data_visible": False,
            "attest_no_raw_text_copied": False,
            "attest_teacher_ocr_transfer_allowed": False,
        },
    }


def _valid_pii_row(fixture_id: str) -> dict[str, Any]:
    """Return a valid PII cleared decision row.

    Args:
        fixture_id: Fixture id.

    Returns:
        Decision row.
    """
    row = _blank_pii_row(fixture_id)
    row["pii_screening_decision"] = {
        "decision": "cleared_no_personal_data",
        "reviewer_id": "operator_batch",
        "reviewed_at": "2026-06-03T00:00:00Z",
        "reason_codes": ["no_personal_data_visible"],
        "attest_local_screening_completed": True,
        "attest_no_personal_data_visible": True,
        "attest_no_raw_text_copied": True,
        "attest_teacher_ocr_transfer_allowed": True,
    }
    return row


def _blank_yolo_row(fixture_id: str) -> dict[str, Any]:
    """Return a blank YOLO annotation row.

    Args:
        fixture_id: Fixture id.

    Returns:
        Annotation row.
    """
    return {
        "schema_version": "supplement-yolo-annotation-template-row-v1",
        "fixture_id": fixture_id,
        "annotation_status": "pending_human_bbox_review",
        "image_path": "images/example.webp",
        "label_snapshot": {
            "schema_version": "supplement-section-yolo-label-candidates-v1",
            "human_review_required": True,
            "training_export_allowed": False,
            "boxes": [],
            "text_stored": False,
        },
        "db_write_performed": False,
        "training_export_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
    }


def _valid_yolo_row(fixture_id: str) -> dict[str, Any]:
    """Return a valid accepted YOLO annotation row.

    Args:
        fixture_id: Fixture id.

    Returns:
        Annotation row.
    """
    row = _blank_yolo_row(fixture_id)
    row["annotation_status"] = "accepted_for_training"
    row["label_snapshot"] = {
        **row["label_snapshot"],
        "human_review_required": False,
        "training_export_allowed": True,
        "boxes": [
            {
                "label": "supplement_facts",
                "x_center": 0.5,
                "y_center": 0.5,
                "width": 0.6,
                "height": 0.3,
            }
        ],
    }
    return row


def _input_paths(tmp_path: Path) -> dict[str, Path]:
    """Write default input fixtures.

    Args:
        tmp_path: Temporary directory.

    Returns:
        Input paths.
    """
    return {
        "batch_plan": _write_json(tmp_path / "plan.json", _batch_plan()),
        "brand_decisions": _write_jsonl(
            tmp_path / "brand.jsonl",
            [_valid_brand_row("brand-a"), _valid_brand_row("brand-b"), _blank_brand_row("brand-c")],
        ),
        "pii_decisions": _write_jsonl(
            tmp_path / "pii.jsonl",
            [_valid_pii_row("pii-a"), _blank_pii_row("pii-b")],
        ),
        "yolo_annotations": _write_jsonl(
            tmp_path / "yolo.jsonl",
            [_valid_yolo_row("yolo-a"), _blank_yolo_row("yolo-b")],
        ),
    }


def test_preflight_operator_review_batch_progress_counts_by_batch(tmp_path: Path) -> None:
    """Verify batch progress is counted without row payload leakage."""
    summary = progress.preflight_operator_review_batch_progress(
        input_paths=_input_paths(tmp_path),
    )

    assert summary["batch_count"] == 4
    assert summary["complete_batch_count"] == 1
    assert summary["pending_batch_count"] == 3
    assert summary["invalid_batch_count"] == 0
    assert summary["next_incomplete_batch_key"] == "brand_product_review:002"
    assert summary["total_valid_row_count"] == 4
    assert summary["total_blank_row_count"] == 3
    assert summary["batches"][0]["batch_status"] == "complete"
    assert summary["batches"][1]["blank_row_count"] == 1
    assert all(
        value.startswith("fp-") and len(value) == 15
        for value in summary["input_path_hashes"].values()
    )
    dumped = json.dumps(summary, ensure_ascii=False)
    assert "Safe Product" not in dumped
    assert "brand-a" not in dumped
    assert str(tmp_path) not in dumped


def test_preflight_operator_review_batch_progress_marks_invalid_rows(tmp_path: Path) -> None:
    """Verify invalid edited rows make only the relevant batch invalid."""
    paths = _input_paths(tmp_path)
    _write_jsonl(
        paths["brand_decisions"],
        [
            _valid_brand_row("brand-a"),
            {**_valid_brand_row("brand-b"), "raw_ocr_text": "leak"},
            _blank_brand_row("brand-c"),
        ],
    )

    summary = progress.preflight_operator_review_batch_progress(input_paths=paths)

    assert summary["invalid_batch_count"] == 1
    assert summary["batches"][0]["batch_status"] == "invalid"
    assert summary["batches"][0]["invalid_row_count"] == 1
    assert "unsafe_field" in summary["batches"][0]["reason_counts"]
    dumped = json.dumps(summary, ensure_ascii=False)
    assert "leak" not in dumped


def test_preflight_operator_review_batch_progress_marks_yolo_boxes_without_accept_pending(
    tmp_path: Path,
) -> None:
    """Verify YOLO rows with boxes still need accepted training flags."""
    row = _valid_yolo_row("yolo-a")
    row["annotation_status"] = "pending_human_bbox_review"
    row["label_snapshot"]["training_export_allowed"] = False
    row["label_snapshot"]["human_review_required"] = True
    paths = _input_paths(tmp_path)
    _write_jsonl(paths["yolo_annotations"], [row, _valid_yolo_row("yolo-b")])

    summary = progress.preflight_operator_review_batch_progress(input_paths=paths)
    yolo_batch = summary["batches"][3]

    assert yolo_batch["batch_status"] == "pending"
    assert yolo_batch["pending_row_count"] == 1
    assert yolo_batch["reason_counts"]["boxes_not_accepted"] == 1


def test_preflight_operator_review_batch_progress_rejects_missing_editable_file(
    tmp_path: Path,
) -> None:
    """Verify queued batches require their editable files."""
    paths = _input_paths(tmp_path)
    del paths["brand_decisions"]

    try:
        progress.preflight_operator_review_batch_progress(input_paths=paths)
    except progress.BatchProgressError as exc:
        assert "Editable file" in str(exc)
    else:
        raise AssertionError("missing editable file should fail closed")


def test_build_batch_progress_markdown_is_redacted(tmp_path: Path) -> None:
    """Verify Markdown progress output is aggregate-only."""
    summary = progress.preflight_operator_review_batch_progress(
        input_paths=_input_paths(tmp_path),
    )

    markdown = progress.build_batch_progress_markdown(summary)

    assert "brand_product_review:001" in markdown
    assert "Safe Product" not in markdown
    assert "brand-a" not in markdown
    assert str(tmp_path) not in markdown
    assert "/private/" not in markdown


def test_batch_progress_cli_writes_json_and_markdown(tmp_path: Path, capsys: Any) -> None:
    """Verify CLI writes progress artifacts and compact output."""
    paths = _input_paths(tmp_path)
    output_path = tmp_path / "out" / "progress.json"
    markdown_path = tmp_path / "out" / "progress.md"

    progress.main(
        [
            "--batch-plan",
            str(paths["batch_plan"]),
            "--brand-decisions",
            str(paths["brand_decisions"]),
            "--pii-decisions",
            str(paths["pii_decisions"]),
            "--yolo-annotations",
            str(paths["yolo_annotations"]),
            "--output",
            str(output_path),
            "--markdown-output",
            str(markdown_path),
        ]
    )

    captured = capsys.readouterr().out
    summary = json.loads(output_path.read_text(encoding="utf-8"))
    assert summary["schema_version"] == "supplement-operator-review-batch-progress-preflight-v1"
    assert all(
        value.startswith("fp-") and len(value) == 15
        for value in summary["input_path_hashes"].values()
    )
    assert markdown_path.is_file()
    assert '"complete_batch_count": 1' in captured
    assert "Safe Product" not in captured
    assert str(tmp_path) not in captured
