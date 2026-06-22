"""Tests for supplement operator review batch file export."""

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

exporter = importlib.import_module("scripts.export_supplement_operator_review_batch_files")


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
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _batch_plan() -> dict[str, Any]:
    """Return a small redacted batch plan fixture.

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
            _batch(
                "brand_product_review:001", "brand_product_review", "decisions.todo.jsonl", 1, 2
            ),
            _batch(
                "brand_product_review:002", "brand_product_review", "decisions.todo.jsonl", 3, 3
            ),
            _batch(
                "review_pii_screening:001", "review_pii_screening", "decisions.todo.jsonl", 1, 2
            ),
            _batch(
                "yolo_section_annotation:001",
                "yolo_section_annotation",
                "annotation.todo.jsonl",
                1,
                2,
            ),
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


def _batch(
    batch_key: str,
    queue_key: str,
    editable_file_name: str,
    start: int,
    end: int,
) -> dict[str, Any]:
    """Return one redacted batch plan row.

    Args:
        batch_key: Batch key.
        queue_key: Queue key.
        editable_file_name: Source editable file name.
        start: One-based start row.
        end: One-based end row.

    Returns:
        Batch row.
    """
    return {
        "batch_key": batch_key,
        "queue_key": queue_key,
        "editable_file_name": editable_file_name,
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


def _brand_row(fixture_id: str, product_name: str) -> dict[str, Any]:
    """Return a brand decision row.

    Args:
        fixture_id: Fixture id.
        product_name: Product text used to verify summary redaction.

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
            "reviewed_product_name": product_name,
            "reason_codes": [],
            "attest_brand_product_review_completed": False,
            "attest_not_using_product_folder_literal_as_manufacturer": False,
            "attest_product_name_reviewed_from_label_or_safe_catalog": False,
            "attest_no_raw_ocr_or_provider_payload_copied": False,
            "attest_db_import_allowed": False,
        },
    }


def _brand_review_csv_row(fixture_id: str, product_name: str) -> dict[str, str]:
    """Return a brand review CSV row.

    Args:
        fixture_id: Fixture id.
        product_name: Product text used to verify summary redaction.

    Returns:
        CSV row.
    """
    return {
        "fixture_id": fixture_id,
        "category_key": "supplement_category",
        "category_display_name": "Supplement Category",
        "brand_candidate_display_name": "Visible Brand",
        "brand_candidate_key": "visible_brand",
        "source_product_id": "source-product-token",
        "image_count": "3",
        "detail_page_count": "1",
        "review_count": "2",
        "decision": "",
        "reviewed_manufacturer": "",
        "reviewed_product_name": product_name,
        "reason_codes": "",
    }


def _pii_row(fixture_id: str) -> dict[str, Any]:
    """Return a PII decision row.

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


def _yolo_row(fixture_id: str, image_path: str) -> dict[str, Any]:
    """Return a YOLO annotation row.

    Args:
        fixture_id: Fixture id.
        image_path: Relative image path for local operator use.

    Returns:
        Annotation row.
    """
    return {
        "schema_version": "supplement-yolo-annotation-template-row-v1",
        "fixture_id": fixture_id,
        "annotation_status": "pending_human_bbox_review",
        "image_path": image_path,
        "source_ref": "crawling-image:redacted-test-ref",
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
            [
                _brand_row("brand-secret-a", "Visible Product A"),
                _brand_row("brand-secret-b", "Visible Product B"),
                _brand_row("brand-secret-c", "Visible Product C"),
            ],
        ),
        "pii_decisions": _write_jsonl(
            tmp_path / "pii.jsonl",
            [_pii_row("pii-secret-a"), _pii_row("pii-secret-b")],
        ),
        "yolo_annotations": _write_jsonl(
            tmp_path / "yolo.jsonl",
            [
                _yolo_row("yolo-secret-a", "images/a.webp"),
                _yolo_row("yolo-secret-b", "images/b.webp"),
            ],
        ),
    }


def _input_paths_with_brand_review_csv(tmp_path: Path) -> dict[str, Path]:
    """Write input fixtures including operator-local brand review CSV context.

    Args:
        tmp_path: Temporary directory.

    Returns:
        Input paths.
    """
    paths = _input_paths(tmp_path)
    paths["brand_review_csv"] = _write_csv(
        tmp_path / "review.csv",
        [
            _brand_review_csv_row("brand-secret-a", "Visible Product A"),
            _brand_review_csv_row("brand-secret-b", "Visible Product B"),
            _brand_review_csv_row("brand-secret-c", "Visible Product C"),
        ],
    )
    return paths


def test_export_operator_review_batch_files_writes_ranges_and_redacted_summary(
    tmp_path: Path,
) -> None:
    """Verify exported batch files are correct and summary stays redacted."""
    paths = _input_paths(tmp_path)
    output_dir = tmp_path / "batches"

    summary = exporter.export_operator_review_batch_files(
        input_paths=paths,
        output_dir=output_dir,
    )

    assert summary["schema_version"] == "supplement-operator-review-batch-file-export-v1"
    assert summary["batch_file_count"] == 4
    assert summary["exported_row_count"] == 7
    assert summary["queue_batch_counts"] == {
        "brand_product_review": 2,
        "review_pii_screening": 1,
        "yolo_section_annotation": 1,
    }
    assert summary["queue_row_counts"] == {
        "brand_product_review": 3,
        "review_pii_screening": 2,
        "yolo_section_annotation": 2,
    }
    first_batch_rows = [
        json.loads(line)
        for line in (output_dir / "brand_product_review-001.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert [row["fixture_id"] for row in first_batch_rows] == [
        "brand-secret-a",
        "brand-secret-b",
    ]
    assert "Visible Product A" in json.dumps(first_batch_rows, ensure_ascii=False)
    dumped = json.dumps(summary, ensure_ascii=False)
    assert "brand-secret-a" not in dumped
    assert "Visible Product A" not in dumped
    assert "images/a.webp" not in dumped
    assert "crawling-image" not in dumped
    assert str(tmp_path) not in dumped


def test_export_operator_review_batch_files_writes_brand_review_csv_context(
    tmp_path: Path,
) -> None:
    """Verify brand review CSV context is batch-local and summary-redacted."""
    paths = _input_paths_with_brand_review_csv(tmp_path)
    output_dir = tmp_path / "batches"

    summary = exporter.export_operator_review_batch_files(
        input_paths=paths,
        output_dir=output_dir,
    )

    first_review_path = output_dir / "brand_product_review-001.review.csv"
    assert first_review_path.is_file()
    with first_review_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert [row["fixture_id"] for row in rows] == ["brand-secret-a", "brand-secret-b"]
    assert rows[0]["reviewed_product_name"] == "Visible Product A"
    assert summary["batch_review_file_count"] == 2
    assert summary["operator_local_batch_review_files_written"] is True
    assert summary["batch_files"][0]["batch_review_file_name"] == (
        "brand_product_review-001.review.csv"
    )
    assert summary["batch_review_files"] == [
        {
            "batch_key": "brand_product_review:001",
            "queue_key": "brand_product_review",
            "batch_review_file_name": "brand_product_review-001.review.csv",
            "source_review_csv_name": "review.csv",
            "exported_review_row_count": 2,
        },
        {
            "batch_key": "brand_product_review:002",
            "queue_key": "brand_product_review",
            "batch_review_file_name": "brand_product_review-002.review.csv",
            "source_review_csv_name": "review.csv",
            "exported_review_row_count": 1,
        },
    ]
    dumped = json.dumps(summary, ensure_ascii=False)
    assert "Visible Product A" not in dumped
    assert "brand-secret-a" not in dumped
    assert str(tmp_path) not in dumped


def test_export_operator_review_batch_files_rejects_missing_brand_review_csv_row(
    tmp_path: Path,
) -> None:
    """Verify brand review CSV context must cover every brand batch row."""
    paths = _input_paths(tmp_path)
    paths["brand_review_csv"] = _write_csv(
        tmp_path / "review.csv",
        [_brand_review_csv_row("brand-secret-a", "Visible Product A")],
    )

    try:
        exporter.export_operator_review_batch_files(
            input_paths=paths,
            output_dir=tmp_path / "batches",
        )
    except exporter.BatchFileExportError as exc:
        assert "missing review csv context" in str(exc).casefold()
    else:
        raise AssertionError("missing review CSV context should fail closed")


def test_export_operator_review_batch_files_rejects_missing_editable_file(
    tmp_path: Path,
) -> None:
    """Verify queued batches require their source editable files."""
    paths = _input_paths(tmp_path)
    del paths["brand_decisions"]

    try:
        exporter.export_operator_review_batch_files(
            input_paths=paths,
            output_dir=tmp_path / "batches",
        )
    except exporter.BatchFileExportError as exc:
        assert "missing" in str(exc).casefold()
    else:
        raise AssertionError("missing editable file should fail closed")


def test_export_operator_review_batch_files_rejects_unsafe_editable_row(
    tmp_path: Path,
) -> None:
    """Verify raw OCR/provider fields are not copied into batch files."""
    paths = _input_paths(tmp_path)
    unsafe_row = _brand_row("brand-secret-a", "Visible Product A")
    unsafe_row["raw_ocr_text"] = "must not be copied"
    _write_jsonl(paths["brand_decisions"], [unsafe_row])

    try:
        exporter.export_operator_review_batch_files(
            input_paths=paths,
            output_dir=tmp_path / "batches",
        )
    except exporter.BatchFileExportError as exc:
        assert "unsafe" in str(exc).casefold()
    else:
        raise AssertionError("unsafe editable row should fail closed")


def test_build_batch_file_export_markdown_is_redacted(tmp_path: Path) -> None:
    """Verify Markdown index does not include row payloads."""
    summary = exporter.export_operator_review_batch_files(
        input_paths=_input_paths(tmp_path),
        output_dir=tmp_path / "batches",
    )

    markdown = exporter.build_batch_file_export_markdown(summary)

    assert "brand_product_review-001.jsonl" in markdown
    assert "Visible Product A" not in markdown
    assert "brand-secret-a" not in markdown
    assert "images/a.webp" not in markdown
    assert str(tmp_path) not in markdown
    assert "/private/" not in markdown


def test_batch_file_export_cli_writes_summary_and_markdown(
    tmp_path: Path,
    capsys: Any,
) -> None:
    """Verify CLI writes batch files and compact redacted output."""
    paths = _input_paths(tmp_path)
    output_dir = tmp_path / "batches"
    summary_path = tmp_path / "out" / "summary.json"
    markdown_path = tmp_path / "out" / "summary.md"

    exporter.main(
        [
            "--batch-plan",
            str(paths["batch_plan"]),
            "--brand-decisions",
            str(paths["brand_decisions"]),
            "--pii-decisions",
            str(paths["pii_decisions"]),
            "--yolo-annotations",
            str(paths["yolo_annotations"]),
            "--output-dir",
            str(output_dir),
            "--summary-output",
            str(summary_path),
            "--markdown-output",
            str(markdown_path),
        ]
    )

    captured = capsys.readouterr().out
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["batch_file_count"] == 4
    assert markdown_path.is_file()
    assert (output_dir / "yolo_section_annotation-001.jsonl").is_file()
    assert '"exported_row_count": 7' in captured
    assert "Visible Product A" not in captured
    assert str(tmp_path) not in captured
