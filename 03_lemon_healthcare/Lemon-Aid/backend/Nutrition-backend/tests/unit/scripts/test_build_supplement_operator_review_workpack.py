"""Tests for supplement operator review workpack export."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

workpack = importlib.import_module("scripts.build_supplement_operator_review_workpack")


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    """Write a JSON fixture.

    Args:
        path: Destination path.
        payload: JSON payload.

    Returns:
        Written path.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return path


def _batch(batch_key: str, queue_key: str, start: int, end: int) -> dict[str, Any]:
    """Return one batch plan row.

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
        "editable_file_name": (
            "annotation.todo.jsonl"
            if queue_key == "yolo_section_annotation"
            else "decisions.todo.jsonl"
        ),
        "row_index_start": start,
        "row_index_end": end,
        "pending_row_count": end - start + 1,
        "operator_checklist": ["fill_decision", "run_preflight"],
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


def _plan() -> dict[str, Any]:
    """Return a batch plan fixture.

    Returns:
        Batch plan payload.
    """
    return {
        "schema_version": "supplement-operator-review-batch-plan-v1",
        "next_queue_key": "brand_product_review",
        "batch_count": 3,
        "batches": [
            _batch("brand_product_review:001", "brand_product_review", 1, 2),
            _batch("review_pii_screening:001", "review_pii_screening", 1, 1),
            _batch("yolo_section_annotation:001", "yolo_section_annotation", 1, 1),
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


def _export_summary() -> dict[str, Any]:
    """Return a batch export summary fixture.

    Returns:
        Export summary payload.
    """
    return {
        "schema_version": "supplement-operator-review-batch-file-export-v1",
        "batch_file_count": 3,
        "batch_review_file_count": 1,
        "batch_files": [
            _export_row(
                "brand_product_review:001",
                "brand_product_review",
                "brand_product_review-001.jsonl",
                1,
                2,
                batch_review_file_name="brand_product_review-001.review.csv",
            ),
            _export_row(
                "review_pii_screening:001",
                "review_pii_screening",
                "review_pii_screening-001.jsonl",
                1,
                1,
            ),
            _export_row(
                "yolo_section_annotation:001",
                "yolo_section_annotation",
                "yolo_section_annotation-001.jsonl",
                1,
                1,
            ),
        ],
        "batch_review_files": [
            {
                "batch_key": "brand_product_review:001",
                "queue_key": "brand_product_review",
                "batch_review_file_name": "brand_product_review-001.review.csv",
                "source_review_csv_name": "review.csv",
                "exported_review_row_count": 2,
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


def _export_row(
    batch_key: str,
    queue_key: str,
    file_name: str,
    start: int,
    end: int,
    *,
    batch_review_file_name: str | None = None,
) -> dict[str, Any]:
    """Return one batch export row.

    Args:
        batch_key: Batch key.
        queue_key: Queue key.
        file_name: Batch file name.
        start: One-based start row.
        end: One-based end row.
        batch_review_file_name: Optional batch-local review CSV name.

    Returns:
        Export row.
    """
    return {
        "batch_key": batch_key,
        "queue_key": queue_key,
        "batch_file_name": file_name,
        "batch_review_file_name": batch_review_file_name,
        "source_editable_file_name": (
            "annotation.todo.jsonl"
            if queue_key == "yolo_section_annotation"
            else "decisions.todo.jsonl"
        ),
        "row_index_start": start,
        "row_index_end": end,
        "exported_row_count": end - start + 1,
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


def _bundle_summary(schema: str, editable_field: str, editable_name: str) -> dict[str, Any]:
    """Return a review bundle summary fixture.

    Args:
        schema: Schema version.
        editable_field: Editable file field name.
        editable_name: Editable file name.

    Returns:
        Bundle summary.
    """
    return {
        "schema_version": schema,
        editable_field: editable_name,
        "html_index_name": "review-index.html",
        "readme_name": "README.md",
        "csv_name": "review.csv",
        "label_studio_tasks_name": "label-studio-tasks.json",
        "reviewable_row_count": 2,
        "image_copied_count": 2,
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


def _brand_contact_sheet_summary(review_csv_name: str) -> dict[str, Any]:
    """Return a redacted brand detail contact-sheet summary fixture.

    Args:
        review_csv_name: Batch review CSV connected to the contact sheet.

    Returns:
        Contact-sheet summary.
    """
    return {
        "schema_version": "supplement-brand-detail-contact-sheet-v1",
        "review_csv_name": review_csv_name,
        "reviewable_row_count": 2,
        "rows_with_thumbnails": 2,
        "rows_without_thumbnails": 0,
        "thumbnail_count": 5,
        "source_image_read_performed": True,
        "full_size_source_images_copied": False,
        "db_write_performed": False,
        "external_provider_call_performed": False,
        "llm_call_performed": False,
        "paddleocr_training_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "local_path_literals_stored": False,
    }


def _input_paths(tmp_path: Path) -> dict[str, Path]:
    """Write default input fixtures.

    Args:
        tmp_path: Temporary directory.

    Returns:
        Input paths.
    """
    return {
        "batch_plan": _write_json(tmp_path / "plan.json", _plan()),
        "batch_export_summary": _write_json(tmp_path / "export.json", _export_summary()),
        "brand_bundle_summary": _write_json(
            tmp_path / "brand-summary.json",
            _bundle_summary(
                "supplement-brand-review-bundle-v1",
                "decision_template_name",
                "decisions.todo.jsonl",
            ),
        ),
        "pii_bundle_summary": _write_json(
            tmp_path / "pii-summary.json",
            _bundle_summary(
                "supplement-review-pii-screening-review-bundle-v1",
                "decision_template_name",
                "decisions.todo.jsonl",
            ),
        ),
        "yolo_bundle_summary": _write_json(
            tmp_path / "yolo-summary.json",
            _bundle_summary(
                "supplement-yolo-annotation-review-bundle-v1",
                "annotation_template_name",
                "annotation.todo.jsonl",
            ),
        ),
    }


def _contact_sheet_path(tmp_path: Path) -> Path:
    """Write a contact-sheet summary fixture.

    Args:
        tmp_path: Temporary directory.

    Returns:
        Contact-sheet summary path.
    """
    return _write_json(
        tmp_path / "brand-detail-contact-sheet-001" / "brand-detail-contact-sheet.summary.json",
        _brand_contact_sheet_summary("brand_product_review-001.review.csv"),
    )


def _assert_visual_index_guidance(
    summary: dict[str, Any],
    pii_markdown: str,
    yolo_markdown: str,
) -> None:
    """Assert visual-index guidance is available for PII and YOLO batches.

    Args:
        summary: Generated workpack summary.
        pii_markdown: PII workpack Markdown.
        yolo_markdown: YOLO workpack Markdown.
    """
    assert summary["batch_workpacks"][1]["visual_index_available"] is True
    assert summary["batch_workpacks"][1]["visual_index_file_name"] == "review-index.html"
    assert summary["batch_workpacks"][2]["bundle_file_names"] == [
        "annotation.todo.jsonl",
        "review-index.html",
        "README.md",
        "label-studio-tasks.json",
    ]
    assert "## Visual Review Index" in pii_markdown
    assert "HTML index: `review-index.html`" in pii_markdown
    assert "Copied review images: `2`" in pii_markdown
    assert "use the Visual Review Index above" in pii_markdown
    assert "label-studio-tasks.json" in yolo_markdown
    assert "## Visual Review Index" in yolo_markdown


def test_build_operator_review_workpack_writes_batch_guides_and_index(
    tmp_path: Path,
) -> None:
    """Verify workpack files are generated without row payload leakage."""
    output_dir = tmp_path / "workpack"

    summary = workpack.build_operator_review_workpack(
        input_paths=_input_paths(tmp_path),
        output_dir=output_dir,
        brand_contact_sheet_summary_paths=[_contact_sheet_path(tmp_path)],
    )

    assert summary["schema_version"] == "supplement-operator-review-workpack-v1"
    assert summary["status"] == "ok"
    assert summary["batch_count"] == 3
    assert summary["workpack_file_count"] == 4
    assert summary["queue_workpack_counts"] == {
        "brand_product_review": 1,
        "review_pii_screening": 1,
        "yolo_section_annotation": 1,
    }
    assert (output_dir / "index.md").is_file()
    brand_markdown = (output_dir / "brand_product_review-001.md").read_text(encoding="utf-8")
    assert "brand_product_review-001.jsonl" in brand_markdown
    assert "brand_product_review-001.review.csv" in brand_markdown
    assert summary["batch_workpacks"][0]["batch_review_file_name"] == (
        "brand_product_review-001.review.csv"
    )
    assert summary["batch_workpacks"][0]["contact_sheet_available"] is True
    assert summary["batch_workpacks"][0]["contact_sheet_dir_name"] == (
        "brand-detail-contact-sheet-001"
    )
    assert summary["batch_workpacks"][0]["contact_sheet_file_names"] == [
        "brand-detail-contact-sheet.html",
        "README.md",
        "brand-detail-contact-sheet.summary.json",
    ]
    assert summary["batch_workpacks"][0]["contact_sheet_rows_with_thumbnails"] == 2
    assert "## Visual Review Contact Sheet" in brand_markdown
    assert "## Visual Review Index" in brand_markdown
    assert "brand-detail-contact-sheet-001" in brand_markdown
    assert "brand-detail-contact-sheet.html" in brand_markdown
    assert "#row-001" in brand_markdown
    index_markdown = (output_dir / "index.md").read_text(encoding="utf-8")
    assert "Batch review CSV" in index_markdown
    assert "brand_product_review-001.review.csv" in index_markdown
    assert "review-index.html" in brand_markdown
    assert "## Decision Schema Guide" in brand_markdown
    assert "`brand_review_decision`" in brand_markdown
    assert "`attest_no_raw_ocr_or_provider_payload_copied`" in brand_markdown
    assert "`reviewed_label_or_catalog`" in brand_markdown
    assert "reviewed-only extract" in brand_markdown
    assert "부분 manifest preview" in brand_markdown
    pii_markdown = (output_dir / "review_pii_screening-001.md").read_text(encoding="utf-8")
    assert "reviewed-only extract" in pii_markdown
    assert "teacher OCR preview" in pii_markdown
    yolo_markdown = (output_dir / "yolo_section_annotation-001.md").read_text(encoding="utf-8")
    _assert_visual_index_guidance(summary, pii_markdown, yolo_markdown)
    assert "reviewed-only extract" in yolo_markdown
    assert "YOLO dataset preview" in yolo_markdown
    assert "dataset promotion" in yolo_markdown
    dumped = json.dumps(summary, ensure_ascii=False) + brand_markdown + pii_markdown + yolo_markdown
    assert "fixture" not in dumped
    assert "raw provider" not in dumped.casefold()
    assert str(tmp_path) not in dumped
    assert "/private/" not in dumped
    assert summary["source_image_read_performed"] is False


def test_build_operator_review_workpack_rejects_missing_bundle_summary(
    tmp_path: Path,
) -> None:
    """Verify every queued batch needs a source bundle summary."""
    paths = _input_paths(tmp_path)
    del paths["brand_bundle_summary"]

    try:
        workpack.build_operator_review_workpack(
            input_paths=paths,
            output_dir=tmp_path / "workpack",
        )
    except workpack.WorkpackError as exc:
        assert "missing" in str(exc).casefold()
    else:
        raise AssertionError("missing bundle summary should fail closed")


def test_build_operator_review_workpack_rejects_duplicate_export_batch(
    tmp_path: Path,
) -> None:
    """Verify duplicate batch keys in export summary fail closed."""
    paths = _input_paths(tmp_path)
    payload = _export_summary()
    payload["batch_files"].append(payload["batch_files"][0])
    _write_json(paths["batch_export_summary"], payload)

    try:
        workpack.build_operator_review_workpack(
            input_paths=paths,
            output_dir=tmp_path / "workpack",
        )
    except workpack.WorkpackError as exc:
        assert "duplicate" in str(exc).casefold()
    else:
        raise AssertionError("duplicate batch export should fail closed")


def test_build_operator_review_workpack_rejects_unsafe_bundle_summary(
    tmp_path: Path,
) -> None:
    """Verify unsafe summary fields are rejected before guide generation."""
    paths = _input_paths(tmp_path)
    payload = _bundle_summary(
        "supplement-brand-review-bundle-v1",
        "decision_template_name",
        "decisions.todo.jsonl",
    )
    payload["raw_ocr_text"] = "unsafe"
    _write_json(paths["brand_bundle_summary"], payload)

    try:
        workpack.build_operator_review_workpack(
            input_paths=paths,
            output_dir=tmp_path / "workpack",
        )
    except workpack.WorkpackError as exc:
        assert "unsafe" in str(exc).casefold()
    else:
        raise AssertionError("unsafe bundle summary should fail closed")


def test_operator_review_workpack_cli_writes_summary(tmp_path: Path, capsys: Any) -> None:
    """Verify CLI writes workpack summary and guides."""
    paths = _input_paths(tmp_path)
    output_dir = tmp_path / "workpack"
    summary_path = tmp_path / "summary.json"

    workpack.main(
        [
            "--batch-plan",
            str(paths["batch_plan"]),
            "--batch-export-summary",
            str(paths["batch_export_summary"]),
            "--brand-bundle-summary",
            str(paths["brand_bundle_summary"]),
            "--pii-bundle-summary",
            str(paths["pii_bundle_summary"]),
            "--yolo-bundle-summary",
            str(paths["yolo_bundle_summary"]),
            "--brand-contact-sheet-summary",
            str(_contact_sheet_path(tmp_path)),
            "--output-dir",
            str(output_dir),
            "--summary-output",
            str(summary_path),
        ]
    )

    captured = capsys.readouterr().out
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["status"] == "ok"
    assert summary["workpack_file_count"] == 4
    assert (output_dir / "yolo_section_annotation-001.md").is_file()
    assert '"workpack_file_count": 4' in captured
    assert str(tmp_path) not in captured
