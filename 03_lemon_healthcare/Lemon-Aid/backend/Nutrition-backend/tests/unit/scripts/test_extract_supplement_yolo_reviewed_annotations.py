"""Tests for reviewed-only supplement YOLO annotation extraction."""

from __future__ import annotations

import hashlib
import importlib
import json
import sys
from pathlib import Path
from typing import Any

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

extractor = importlib.import_module("scripts.extract_supplement_yolo_reviewed_annotations")
promoter = importlib.import_module("scripts.promote_supplement_yolo_annotation_template")


def _sha256(value: bytes) -> str:
    """Return a SHA-256 digest for fixture bytes.

    Args:
        value: Fixture bytes.

    Returns:
        Hex digest.
    """
    return hashlib.sha256(value).hexdigest()


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> Path:
    """Write JSONL rows.

    Args:
        path: Destination file.
        rows: Rows to write.

    Returns:
        Written path.
    """
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    return path


def _write_template_and_annotations(
    tmp_path: Path,
    *,
    template_rows: list[dict[str, Any]],
    annotation_rows: list[dict[str, Any]],
) -> tuple[Path, Path]:
    """Write template and mixed annotation fixtures.

    Args:
        tmp_path: Temporary directory.
        template_rows: Source template rows.
        annotation_rows: Mixed annotation rows.

    Returns:
        Template and annotation paths.
    """
    image_dir = tmp_path / "images"
    image_dir.mkdir()
    (image_dir / "detail.jpg").write_bytes(b"detail-page-image")
    template_path = _write_jsonl(tmp_path / "annotation.todo.jsonl", template_rows)
    annotations_path = _write_jsonl(tmp_path / "annotation.reconciled.jsonl", annotation_rows)
    return template_path, annotations_path


def _pending_row(*, fixture_id: str = "detail-yolo-abc123") -> dict[str, Any]:
    """Build one blank pending supplement section annotation row.

    Args:
        fixture_id: Safe fixture id.

    Returns:
        Pending annotation row.
    """
    return {
        "schema_version": "supplement-yolo-annotation-template-row-v1",
        "fixture_id": fixture_id,
        "source_ref": f"crawling-image:{'a' * 32}",
        "image_ref_hash": "a" * 64,
        "image_sha256": _sha256(b"detail-page-image"),
        "image_mime_type": "image/jpeg",
        "category_key": "omega3",
        "source_kind": "detail_page",
        "annotation_task_type": "supplement_roi_box",
        "annotation_status": "pending_human_bbox_review",
        "coordinate_space": "source_image",
        "allowed_labels": list(promoter.SUPPLEMENT_SECTION_CLASS_NAMES),
        "image_path": "images/detail.jpg",
        "label_snapshot": {
            "schema_version": "supplement-section-yolo-label-candidates-v1",
            "candidate_source": "human_annotation_template",
            "coordinate_space": "source_image",
            "human_review_required": True,
            "text_stored": False,
            "training_export_allowed": False,
            "boxes": [],
        },
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
    }


def _accepted_row(*, fixture_id: str = "detail-yolo-abc123") -> dict[str, Any]:
    """Build one accepted supplement section annotation row.

    Args:
        fixture_id: Safe fixture id.

    Returns:
        Accepted annotation row.
    """
    row = _pending_row(fixture_id=fixture_id)
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


def test_extract_reviewed_yolo_annotations_ignores_blank_rows(tmp_path: Path) -> None:
    """Verify blank pending rows do not become dataset preview rows."""
    pending = _pending_row()
    template_path, annotations_path = _write_template_and_annotations(
        tmp_path,
        template_rows=[pending],
        annotation_rows=[pending],
    )

    rows, summary = extractor.extract_reviewed_yolo_annotations(
        template_path=template_path,
        annotations_path=annotations_path,
        output_path=tmp_path / "annotation.reviewed-only.jsonl",
        source_map_path=tmp_path / "annotation.reviewed-only.source-map.json",
    )

    assert rows == []
    assert summary["reviewed_annotation_count"] == 0
    assert summary["blank_annotation_ignored_count"] == 1
    assert summary["ready_for_partial_promotion"] is False
    assert summary["ready_for_strict_promotion"] is False


def test_extract_reviewed_yolo_annotations_writes_only_accepted_rows(
    tmp_path: Path,
) -> None:
    """Verify accepted rows are separated from untouched queue stubs."""
    accepted = _accepted_row(fixture_id="detail-yolo-abc123")
    pending = _pending_row(fixture_id="detail-yolo-def456")
    template_path, annotations_path = _write_template_and_annotations(
        tmp_path,
        template_rows=[
            _pending_row(fixture_id="detail-yolo-abc123"),
            _pending_row(fixture_id="detail-yolo-def456"),
        ],
        annotation_rows=[accepted, pending],
    )

    rows, summary = extractor.extract_reviewed_yolo_annotations(
        template_path=template_path,
        annotations_path=annotations_path,
        output_path=tmp_path / "annotation.reviewed-only.jsonl",
        source_map_path=tmp_path / "annotation.reviewed-only.source-map.json",
    )

    assert len(rows) == 1
    assert rows[0]["fixture_id"] == "detail-yolo-abc123"
    assert rows[0]["image_path"] == "images/detail.jpg"
    assert summary["reviewed_annotation_count"] == 1
    assert summary["blank_annotation_ignored_count"] == 1
    assert summary["missing_annotation_count"] == 0
    assert summary["ready_for_partial_promotion"] is True
    assert summary["ready_for_strict_promotion"] is False
    assert summary["source_doc_urls"] == list(promoter.SOURCE_DOC_URLS)


def test_extract_reviewed_yolo_annotations_rejects_unaccepted_boxes(
    tmp_path: Path,
) -> None:
    """Verify boxes without acceptance flags fail closed."""
    row = _accepted_row()
    row["annotation_status"] = "pending_human_bbox_review"
    row["label_snapshot"] = {
        **row["label_snapshot"],
        "human_review_required": True,
        "training_export_allowed": False,
    }
    template_path, annotations_path = _write_template_and_annotations(
        tmp_path,
        template_rows=[_pending_row()],
        annotation_rows=[row],
    )

    with pytest.raises(ValueError, match="not accepted"):
        extractor.extract_reviewed_yolo_annotations(
            template_path=template_path,
            annotations_path=annotations_path,
            output_path=tmp_path / "annotation.reviewed-only.jsonl",
            source_map_path=tmp_path / "annotation.reviewed-only.source-map.json",
        )


def test_extract_reviewed_yolo_annotations_rejects_unmatched_rows(
    tmp_path: Path,
) -> None:
    """Verify rows that are not in the source template fail closed."""
    template_path, annotations_path = _write_template_and_annotations(
        tmp_path,
        template_rows=[_pending_row(fixture_id="detail-yolo-abc123")],
        annotation_rows=[_accepted_row(fixture_id="detail-yolo-def456")],
    )

    with pytest.raises(ValueError, match="source template"):
        extractor.extract_reviewed_yolo_annotations(
            template_path=template_path,
            annotations_path=annotations_path,
            output_path=tmp_path / "annotation.reviewed-only.jsonl",
            source_map_path=tmp_path / "annotation.reviewed-only.source-map.json",
        )


def test_extract_reviewed_yolo_annotations_requires_output_beside_template(
    tmp_path: Path,
) -> None:
    """Verify reviewed-only output cannot break relative fixture refs."""
    template_path, annotations_path = _write_template_and_annotations(
        tmp_path,
        template_rows=[_pending_row()],
        annotation_rows=[_pending_row()],
    )
    outside_dir = tmp_path / "out"
    outside_dir.mkdir()

    with pytest.raises(ValueError, match="beside"):
        extractor.extract_reviewed_yolo_annotations(
            template_path=template_path,
            annotations_path=annotations_path,
            output_path=outside_dir / "annotation.reviewed-only.jsonl",
            source_map_path=outside_dir / "annotation.reviewed-only.source-map.json",
        )


def test_extract_reviewed_yolo_annotations_cli_redacts_stdout(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI output hides image paths, source refs, and labels."""
    template_path, annotations_path = _write_template_and_annotations(
        tmp_path,
        template_rows=[_pending_row()],
        annotation_rows=[_accepted_row()],
    )
    output_path = tmp_path / "annotation.reviewed-only.jsonl"
    summary_path = tmp_path / "annotation.reviewed-only.summary.json"

    extractor.main(
        [
            "--template",
            str(template_path),
            "--annotations",
            str(annotations_path),
            "--output",
            str(output_path),
            "--summary",
            str(summary_path),
        ]
    )

    captured = capsys.readouterr().out
    written_rows = output_path.read_text(encoding="utf-8")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["output_rows_written"] == 1
    assert "images/detail.jpg" not in captured
    assert "supplement_facts" not in captured
    assert "crawling-image" not in captured
    assert str(tmp_path) not in captured
    assert "images/detail.jpg" in written_rows
    assert "supplement_facts" in written_rows
