"""Tests for generic supplement operator review batch triage summaries."""

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

triage = importlib.import_module("scripts.build_supplement_operator_review_batch_triage")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> Path:
    """Write JSONL fixture rows.

    Args:
        path: Destination path.
        rows: Row payloads.

    Returns:
        Written path.
    """
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )
    return path


def _pii_row(
    fixture_id: str = "review-ocr-gt-safe",
    *,
    decision: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return one PII review row fixture.

    Args:
        fixture_id: Fixture id that must not be emitted.
        decision: Optional decision object.

    Returns:
        PII review row.
    """
    return {
        "schema_version": "supplement-review-pii-screening-decision-v1",
        "fixture_id": fixture_id,
        "pii_screening_decision": (
            decision
            if decision is not None
            else {
                "decision": "",
                "reviewer_id": "",
                "reviewed_at": "",
                "reason_codes": [],
                "attest_local_screening_completed": False,
                "attest_no_personal_data_visible": False,
                "attest_no_raw_text_copied": False,
                "attest_teacher_ocr_transfer_allowed": False,
            }
        ),
    }


def _cleared_pii_decision() -> dict[str, Any]:
    """Return one valid PII-cleared decision object.

    Returns:
        Valid operator decision.
    """
    return {
        "decision": "cleared_no_personal_data",
        "reviewer_id": "operator_unit",
        "reviewed_at": "operator_reviewed",
        "reason_codes": [],
        "attest_local_screening_completed": True,
        "attest_no_personal_data_visible": True,
        "attest_no_raw_text_copied": True,
        "attest_teacher_ocr_transfer_allowed": True,
    }


def _yolo_row(
    fixture_id: str = "detail-yolo-safe",
    *,
    boxes: list[dict[str, Any]] | None = None,
    accepted: bool = False,
) -> dict[str, Any]:
    """Return one YOLO section annotation row fixture.

    Args:
        fixture_id: Fixture id that must not be emitted.
        boxes: Optional bbox list.
        accepted: Whether the row is marked training-ready.

    Returns:
        YOLO annotation row.
    """
    return {
        "schema_version": "supplement-yolo-annotation-template-row-v1",
        "fixture_id": fixture_id,
        "annotation_status": "accepted_for_training" if accepted else "pending_human_bbox_review",
        "image_path": "images/yolo-section/private.jpg",
        "source_ref": "crawling-image:private-ref",
        "label_snapshot": {
            "schema_version": "supplement-section-yolo-label-candidates-v1",
            "candidate_source": "human_annotation_template",
            "coordinate_space": "source_image",
            "human_review_required": not accepted,
            "training_export_allowed": accepted,
            "text_stored": False,
            "boxes": boxes or [],
        },
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "local_path_literals_stored": False,
        "product_dir_literals_stored": False,
        "db_write_performed": False,
        "external_provider_call_performed": False,
        "training_export_performed": False,
    }


def test_operator_review_batch_triage_reports_pii_priorities_without_fixture_leak(
    tmp_path: Path,
) -> None:
    """Verify PII triage reports blank rows without exposing fixture ids."""
    batch_path = _write_jsonl(
        tmp_path / "review_pii_screening-001.jsonl",
        [
            _pii_row("private-fixture-1"),
            _pii_row("private-fixture-2", decision=_cleared_pii_decision()),
        ],
    )

    summary = triage.build_operator_review_batch_triage(
        queue_key="review_pii_screening",
        input_paths={"batch_file": batch_path},
        max_row_hints=10,
    )
    markdown = triage.build_markdown(summary)
    public_dump = json.dumps({"summary": summary, "markdown": markdown}, ensure_ascii=False)

    assert summary["row_count"] == 2
    assert summary["blank_row_count"] == 1
    assert summary["valid_row_count"] == 1
    assert summary["priority_counts"]["p2_privacy_screening_required"] == 1
    assert summary["priority_counts"]["p4_reviewed"] == 1
    assert summary["row_hints"][0] == {
        "row_index": 1,
        "priority": "p2_privacy_screening_required",
        "reason_code": "blank_decision",
    }
    assert "private-fixture" not in public_dump
    assert str(tmp_path) not in public_dump
    assert summary["external_provider_call_performed"] is False


def test_operator_review_batch_triage_reports_yolo_priorities_without_bbox_leak(
    tmp_path: Path,
) -> None:
    """Verify YOLO triage does not expose image refs or bbox coordinates."""
    batch_path = _write_jsonl(
        tmp_path / "yolo_section_annotation-001.jsonl",
        [
            _yolo_row("private-yolo-1"),
            _yolo_row(
                "private-yolo-2",
                boxes=[
                    {
                        "label": "supplement_facts",
                        "x_center": 0.5,
                        "y_center": 0.5,
                        "width": 0.2,
                        "height": 0.3,
                    }
                ],
            ),
            _yolo_row(
                "private-yolo-3",
                boxes=[
                    {
                        "label": "supplement_facts",
                        "x_center": 0.5,
                        "y_center": 0.5,
                        "width": 0.2,
                        "height": 0.3,
                    }
                ],
                accepted=True,
            ),
        ],
    )

    summary = triage.build_operator_review_batch_triage(
        queue_key="yolo_section_annotation",
        input_paths={"batch_file": batch_path},
        max_row_hints=10,
    )
    markdown = triage.build_markdown(summary)
    public_dump = json.dumps({"summary": summary, "markdown": markdown}, ensure_ascii=False)

    assert summary["row_count"] == 3
    assert summary["blank_row_count"] == 1
    assert summary["pending_row_count"] == 1
    assert summary["valid_row_count"] == 1
    assert summary["priority_counts"]["p2_bbox_annotation_required"] == 1
    assert summary["priority_counts"]["p1_complete_pending_review"] == 1
    assert summary["priority_counts"]["p4_reviewed"] == 1
    assert "private-yolo" not in public_dump
    assert "images/yolo-section" not in public_dump
    assert "crawling-image:" not in public_dump
    assert "x_center" not in public_dump


def test_operator_review_batch_triage_rejects_unsupported_queue(tmp_path: Path) -> None:
    """Verify unsupported queue keys cannot be triaged."""
    batch_path = _write_jsonl(tmp_path / "brand_product_review-001.jsonl", [_pii_row()])

    with pytest.raises(triage.OperatorReviewBatchTriageError, match="Unsupported"):
        triage.build_operator_review_batch_triage(
            queue_key="brand_product_review",
            input_paths={"batch_file": batch_path},
        )


def test_operator_review_batch_triage_marks_unsafe_local_path_invalid(tmp_path: Path) -> None:
    """Verify local paths in operator rows are not emitted and become invalid."""
    batch_path = _write_jsonl(
        tmp_path / "review_pii_screening-001.jsonl",
        [
            _pii_row(
                decision={
                    **_cleared_pii_decision(),
                    "reviewer_id": "/Volumes/Corsair/private",
                }
            )
        ],
    )

    summary = triage.build_operator_review_batch_triage(
        queue_key="review_pii_screening",
        input_paths={"batch_file": batch_path},
    )
    public_dump = json.dumps(summary, ensure_ascii=False)

    assert summary["invalid_row_count"] == 1
    assert summary["priority_counts"]["p0_fix_invalid_row"] == 1
    assert "/Volumes/" not in public_dump
