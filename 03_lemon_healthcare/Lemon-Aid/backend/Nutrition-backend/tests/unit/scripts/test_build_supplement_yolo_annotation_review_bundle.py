"""Tests for supplement YOLO annotation local review bundle generation."""

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

yolo_bundle = importlib.import_module("scripts.build_supplement_yolo_annotation_review_bundle")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write JSONL rows.

    Args:
        path: Destination path.
        rows: Rows to write.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _template_row(
    *,
    fixture_id: str = "detail-yolo-001",
    image_path: str | None = "images/detail-yolo-001.webp",
) -> dict[str, Any]:
    """Return a minimal YOLO annotation template row.

    Args:
        fixture_id: Fixture id.
        image_path: Optional relative materialized image path.

    Returns:
        Template row.
    """
    row: dict[str, Any] = {
        "schema_version": yolo_bundle.template_export.ROW_SCHEMA_VERSION,
        "source_run_id": "yolo-template-test",
        "fixture_id": fixture_id,
        "source_ref": "crawling-image:" + "a" * 32,
        "image_ref_hash": "a" * 64,
        "image_sha256": "b" * 64,
        "image_mime_type": "image/webp",
        "category_key": "omega3",
        "source_kind": "detail_page",
        "annotation_task_type": "supplement_roi_box",
        "annotation_status": "pending_human_bbox_review",
        "coordinate_space": "source_image",
        "allowed_labels": list(yolo_bundle.template_export.SUPPLEMENT_SECTION_CLASS_NAMES),
        "label_snapshot": {
            "schema_version": "supplement-section-yolo-label-candidates-v1",
            "candidate_source": "human_annotation_template",
            "coordinate_space": "source_image",
            "human_review_required": True,
            "text_stored": False,
            "training_export_allowed": False,
            "boxes": [],
        },
        "review_checklist": ["bbox uses normalized xywh"],
        "review_notes_code": "pending_section_bbox_human_annotation",
        "image_materialization_required": image_path is None,
        "image_materialization_policy": (
            "private_operator_source_required"
            if image_path is None
            else "private_hashed_fixture_copy_materialized"
        ),
        "db_write_performed": False,
        "training_export_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
    }
    if image_path is not None:
        row["image_path"] = image_path
    return row


def test_build_bundle_writes_html_annotation_template_and_label_studio_tasks(
    tmp_path: Path,
) -> None:
    """Verify local YOLO annotation bundle files and image copies are written."""
    template_dir = tmp_path / "template"
    image_path = template_dir / "images" / "detail-yolo-001.webp"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"detail-page")
    template_path = template_dir / "annotation-template.jsonl"
    output_dir = tmp_path / "bundle"
    _write_jsonl(template_path, [_template_row()])

    summary = yolo_bundle.build_review_bundle(
        template_path=template_path,
        output_dir=output_dir,
        source_run_id="bundle-test",
    )

    assert summary["schema_version"] == yolo_bundle.SCHEMA_VERSION
    assert summary["reviewable_row_count"] == 1
    assert summary["annotation_template_row_count"] == 1
    assert summary["label_studio_task_count"] == 1
    assert summary["image_copied_count"] == 1
    assert summary["training_export_allowed_rows"] == 0
    assert (output_dir / "images" / "detail-yolo-001.webp").read_bytes() == b"detail-page"
    html_text = (output_dir / yolo_bundle.HTML_INDEX_NAME).read_text(encoding="utf-8")
    assert 'src="images/detail-yolo-001.webp"' in html_text
    assert "Box Format" in html_text
    assert "Section Guide" in html_text
    assert "supplement_facts" in html_text
    assert str(tmp_path) not in html_text
    annotation_rows = [
        json.loads(line)
        for line in (output_dir / yolo_bundle.ANNOTATION_TEMPLATE_NAME)
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    assert annotation_rows[0]["fixture_id"] == "detail-yolo-001"
    assert annotation_rows[0]["label_snapshot"]["boxes"] == []
    assert annotation_rows[0]["box_schema_example"] == yolo_bundle.BOX_SCHEMA_EXAMPLE
    assert annotation_rows[0]["section_label_guide"]["supplement_facts"].startswith("The full")
    tasks = json.loads(
        (output_dir / yolo_bundle.LABEL_STUDIO_TASKS_NAME).read_text(encoding="utf-8")
    )
    assert tasks[0]["data"]["image"] == "images/detail-yolo-001.webp"
    assert "supplement_facts" in tasks[0]["meta"]["allowed_labels"]
    assert tasks[0]["meta"]["box_schema_example"] == yolo_bundle.BOX_SCHEMA_EXAMPLE
    assert "precautions" in tasks[0]["meta"]["section_label_guide"]
    assert "allergen_warning" in tasks[0]["meta"]["section_label_guide"]
    readme_text = (output_dir / yolo_bundle.README_NAME).read_text(encoding="utf-8")
    assert '"label":"supplement_facts"' in readme_text
    assert "allergen_warning" in readme_text
    assert "All coordinate values must be between 0 and 1" in readme_text


def test_build_bundle_skips_rows_without_materialized_images(tmp_path: Path) -> None:
    """Verify unmaterialized or missing images stay out of the bundle."""
    template_path = tmp_path / "template" / "annotation-template.jsonl"
    _write_jsonl(
        template_path,
        [
            _template_row(fixture_id="missing-path", image_path=None),
            _template_row(fixture_id="missing-file", image_path="images/missing.webp"),
        ],
    )

    summary = yolo_bundle.build_review_bundle(
        template_path=template_path,
        output_dir=tmp_path / "bundle",
    )

    assert summary["reviewable_row_count"] == 0
    assert summary["annotation_template_row_count"] == 0
    assert summary["skip_reason_counts"] == {
        "materialized_image_file_not_found": 1,
        "missing_materialized_image_path": 1,
    }


def test_build_bundle_rejects_absolute_image_paths(tmp_path: Path) -> None:
    """Verify absolute local image paths cannot enter the bundle."""
    template_path = tmp_path / "template" / "annotation-template.jsonl"
    _write_jsonl(template_path, [_template_row(image_path="/private/tmp/detail.webp")])

    with pytest.raises(ValueError, match=r"local path literal|relative image paths"):
        yolo_bundle.build_review_bundle(
            template_path=template_path,
            output_dir=tmp_path / "bundle",
        )


def test_build_bundle_rejects_unknown_labels(tmp_path: Path) -> None:
    """Verify unknown class names cannot enter the local task bundle."""
    template_dir = tmp_path / "template"
    image_path = template_dir / "images" / "detail-yolo-001.webp"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"detail-page")
    row = _template_row()
    row["allowed_labels"] = ["not_a_section"]
    template_path = template_dir / "annotation-template.jsonl"
    _write_jsonl(template_path, [row])

    with pytest.raises(ValueError, match="unknown allowed label"):
        yolo_bundle.build_review_bundle(
            template_path=template_path,
            output_dir=tmp_path / "bundle",
        )


def test_cli_writes_summary_without_path_leaks(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI summary remains redacted."""
    template_dir = tmp_path / "template"
    image_path = template_dir / "images" / "detail-yolo-001.webp"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"detail-page")
    template_path = template_dir / "annotation-template.jsonl"
    output_dir = tmp_path / "bundle"
    _write_jsonl(template_path, [_template_row()])

    yolo_bundle.main(
        [
            "--template",
            str(template_path),
            "--output-dir",
            str(output_dir),
            "--source-run-id",
            "bundle-cli",
        ]
    )

    printed = capsys.readouterr().out
    summary = json.loads((output_dir / yolo_bundle.SUMMARY_NAME).read_text(encoding="utf-8"))
    assert json.loads(printed)["source_run_id"] == "bundle-cli"
    assert summary["source_run_id"] == "bundle-cli"
    assert summary["db_write_performed"] is False
    assert summary["training_export_performed"] is False
    assert str(tmp_path) not in printed
    assert str(tmp_path) not in json.dumps(summary, ensure_ascii=False)
