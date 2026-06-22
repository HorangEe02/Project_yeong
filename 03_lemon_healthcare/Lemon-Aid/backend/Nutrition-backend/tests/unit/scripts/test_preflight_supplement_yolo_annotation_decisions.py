"""Tests for supplement YOLO annotation decision preflight."""

from __future__ import annotations

import hashlib
import importlib
import json
import sys
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

preflight = importlib.import_module("scripts.preflight_supplement_yolo_annotation_decisions")
promoter = importlib.import_module("scripts.promote_supplement_yolo_annotation_template")


def _sha256(value: bytes) -> str:
    """Return a SHA-256 digest for fixture bytes.

    Args:
        value: Fixture bytes.

    Returns:
        Hex digest.
    """
    return hashlib.sha256(value).hexdigest()


def _write_template(tmp_path: Path, rows: list[dict[str, Any]]) -> tuple[Path, Path]:
    """Write template rows and a fixture image.

    Args:
        tmp_path: Temporary test root.
        rows: Template rows.

    Returns:
        Template path and source-map path.
    """
    image_dir = tmp_path / "images"
    image_dir.mkdir()
    (image_dir / "detail.jpg").write_bytes(b"detail-page-image")
    template_path = tmp_path / "annotation.todo.jsonl"
    template_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    return template_path, tmp_path / "source-map.json"


def _pending_row(*, fixture_id: str = "detail-yolo-abc123") -> dict[str, Any]:
    """Build one pending annotation row.

    Args:
        fixture_id: Fixture id.

    Returns:
        Pending template row.
    """
    return {
        "schema_version": "supplement-yolo-annotation-template-row-v1",
        "fixture_id": fixture_id,
        "source_ref": f"crawling-image:{'a' * 32}",
        "image_ref_hash": "a" * 64,
        "image_sha256": _sha256(b"detail-page-image"),
        "image_mime_type": "image/jpeg",
        "category_key": "오메가3",
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
        "training_export_performed": False,
    }


def _accepted_row(*, fixture_id: str = "detail-yolo-abc123") -> dict[str, Any]:
    """Build one accepted annotation row.

    Args:
        fixture_id: Fixture id.

    Returns:
        Accepted template row.
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


def test_preflight_reports_blank_pending_annotation_rows(tmp_path: Path) -> None:
    """Verify untouched annotation stubs are not promotion-ready."""
    template_path, source_map_path = _write_template(tmp_path, [_pending_row()])

    summary = preflight.preflight_yolo_annotation_decisions(
        template_path=template_path,
        source_map_path=source_map_path,
        require_all_reviewed=True,
    )

    assert summary["template_row_count"] == 1
    assert summary["blank_box_row_count"] == 1
    assert summary["pending_review_row_count"] == 1
    assert summary["valid_accepted_row_count"] == 0
    assert summary["pending_operator_action_count"] == 1
    assert summary["ready_for_requested_promotion"] is False
    assert summary["next_operator_action"] == "complete_supplement_section_bbox_review"


def test_preflight_allows_reviewed_annotation_promotion(tmp_path: Path) -> None:
    """Verify one accepted row is promotion-ready."""
    template_path, source_map_path = _write_template(tmp_path, [_accepted_row()])

    summary = preflight.preflight_yolo_annotation_decisions(
        template_path=template_path,
        source_map_path=source_map_path,
    )

    assert summary["valid_accepted_row_count"] == 1
    assert summary["reviewed_box_row_count"] == 1
    assert summary["ready_for_partial_promotion"] is True
    assert summary["ready_for_requested_promotion"] is True
    assert summary["next_operator_action"] == "run_yolo_annotation_template_promotion"
    dumped = json.dumps(summary, ensure_ascii=False)
    assert "supplement_facts" not in dumped
    assert str(tmp_path) not in dumped


def test_preflight_strict_mode_blocks_mixed_pending_rows(tmp_path: Path) -> None:
    """Verify strict mode requires every row to be accepted."""
    template_path, source_map_path = _write_template(
        tmp_path,
        [
            _accepted_row(fixture_id="detail-yolo-abc123"),
            _pending_row(fixture_id="detail-yolo-def456"),
        ],
    )

    summary = preflight.preflight_yolo_annotation_decisions(
        template_path=template_path,
        source_map_path=source_map_path,
        require_all_reviewed=True,
    )

    assert summary["valid_accepted_row_count"] == 1
    assert summary["pending_review_row_count"] == 1
    assert summary["ready_for_partial_promotion"] is True
    assert summary["ready_for_requested_promotion"] is False


def test_preflight_counts_invalid_box_without_leaking_payload(tmp_path: Path) -> None:
    """Verify unsafe or invalid boxes are reported as aggregate codes only."""
    row = _accepted_row()
    row["label_snapshot"]["boxes"][0]["width"] = 0
    template_path, source_map_path = _write_template(tmp_path, [row])

    summary = preflight.preflight_yolo_annotation_decisions(
        template_path=template_path,
        source_map_path=source_map_path,
    )

    assert summary["invalid_row_count"] == 1
    assert summary["invalid_reason_counts"] == {"invalid_box_area": 1}
    assert summary["ready_for_requested_promotion"] is False


def test_preflight_rejects_raw_ocr_text_without_leaking_value(tmp_path: Path) -> None:
    """Verify raw OCR text cannot enter annotation preflight output."""
    row = _accepted_row()
    row["label_snapshot"]["raw_ocr_text"] = "visible sensitive text"
    template_path, source_map_path = _write_template(tmp_path, [row])

    summary = preflight.preflight_yolo_annotation_decisions(
        template_path=template_path,
        source_map_path=source_map_path,
    )

    assert summary["invalid_row_count"] == 1
    assert summary["invalid_reason_counts"] == {"unsafe_raw_field": 1}
    dumped = json.dumps(summary, ensure_ascii=False)
    assert "visible sensitive text" not in dumped
    assert '"raw_ocr_text":' not in dumped


def test_preflight_cli_writes_redacted_summary(tmp_path: Path, capsys: Any) -> None:
    """Verify CLI writes a redacted side-effect-free summary."""
    template_path, source_map_path = _write_template(tmp_path, [_pending_row()])
    output_path = tmp_path / "out" / "preflight.json"

    preflight.main(
        [
            "--template",
            str(template_path),
            "--source-map",
            str(source_map_path),
            "--output",
            str(output_path),
            "--require-all-reviewed",
        ]
    )

    captured = capsys.readouterr().out
    summary = json.loads(output_path.read_text(encoding="utf-8"))
    assert summary["schema_version"] == "supplement-yolo-annotation-decision-preflight-v1"
    assert summary["db_write_performed"] is False
    assert summary["training_performed"] is False
    assert summary["source_ref_printed"] is False
    assert "detail-yolo-abc123" not in captured
    assert str(tmp_path) not in captured
