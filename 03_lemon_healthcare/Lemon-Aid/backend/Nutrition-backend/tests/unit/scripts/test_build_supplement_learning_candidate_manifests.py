"""Tests for supplement OCR/YOLO learning candidate manifest builder."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

builder = importlib.import_module("scripts.build_supplement_learning_candidate_manifests")


def _touch_image(path: Path, content: bytes = b"placeholder") -> None:
    """Create a small image-like fixture file.

    Args:
        path: Target path.
        content: Bytes used for deterministic hashing.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def test_build_manifests_splits_review_ocr_and_detail_yolo_candidates(
    tmp_path: Path,
) -> None:
    """Verify review images and detail-page images are routed to separate tasks."""
    root = tmp_path / "crawling-image"
    _touch_image(root / "[오메가3]" / "나우푸드 오메가3_123456" / "리뷰" / "review.jpg")
    _touch_image(
        root / "[오메가3]" / "나우푸드 오메가3_123456" / "상세페이지" / "detail.png",
        b"detail",
    )

    ocr_rows, yolo_rows, summary = builder.build_learning_candidate_manifests(
        root=root,
        source_run_id="learning-candidates-test",
    )

    assert len(ocr_rows) == 1
    assert len(yolo_rows) == 1
    assert summary["ocr_candidate_count"] == 1
    assert summary["yolo_candidate_count"] == 1
    assert summary["source_run_id"] == "learning-candidates-test"

    ocr_row = ocr_rows[0]
    assert ocr_row["source_run_id"] == "learning-candidates-test"
    assert ocr_row["candidate_purpose"] == "ocr_ground_truth_review"
    assert ocr_row["source_kind"] == "review"
    assert ocr_row["ground_truth_status"] == "pending_pii_screening"
    assert ocr_row["contains_personal_data"] is None
    assert ocr_row["external_transfer_allowed"] is False
    assert ocr_row["teacher_ocr_allowed"] is False
    assert ocr_row["manual_ground_truth_required"] is True
    assert ocr_row["teacher_ocr_providers"] == ["clova", "google_vision"]

    yolo_row = yolo_rows[0]
    assert yolo_row["source_run_id"] == "learning-candidates-test"
    assert yolo_row["candidate_purpose"] == "supplement_section_bbox_annotation"
    assert yolo_row["source_kind"] == "detail_page"
    assert yolo_row["annotation_status"] == "pending_section_bbox_human_annotation"
    assert yolo_row["contains_personal_data"] is False
    assert yolo_row["external_transfer_allowed"] is False
    assert yolo_row["coco_pretrained_allowed_for_final_labels"] is False
    assert yolo_row["custom_section_model_required"] is True
    assert "supplement_facts" in yolo_row["section_class_names"]
    assert "precautions" in yolo_row["section_class_names"]


def test_review_personal_data_clearance_unlocks_teacher_ocr(tmp_path: Path) -> None:
    """Verify review rows stay transfer-blocked until operator PII clearance."""
    root = tmp_path / "crawling-image"
    _touch_image(root / "[비타민C]" / "고려은단 비타민C_789012" / "리뷰" / "review.jpg")

    ocr_rows, yolo_rows, summary = builder.build_learning_candidate_manifests(
        root=root,
        review_personal_data_cleared=True,
    )

    assert yolo_rows == []
    assert summary["ocr_external_transfer_allowed_count"] == 1
    assert summary["yolo_external_transfer_allowed_count"] == 0
    assert ocr_rows[0]["contains_personal_data"] is False
    assert ocr_rows[0]["pii_screening_status"] == "operator_cleared_no_personal_data"
    assert ocr_rows[0]["ground_truth_status"] == "pending_manual_transcription"
    assert ocr_rows[0]["external_transfer_allowed"] is True
    assert ocr_rows[0]["teacher_ocr_allowed"] is True


def test_candidate_manifests_omit_product_literals_local_paths_and_raw_payloads(
    tmp_path: Path,
) -> None:
    """Verify candidate artifacts do not expose local paths or raw data keys."""
    root = tmp_path / "crawling-image"
    product_literal = "나우푸드 오메가3_123456"
    _touch_image(root / "[오메가3]" / product_literal / "리뷰" / "review.jpg")
    _touch_image(root / "[오메가3]" / product_literal / "상세페이지" / "detail.png")

    ocr_rows, yolo_rows, summary = builder.build_learning_candidate_manifests(root=root)
    dumped = json.dumps(
        {"ocr_rows": ocr_rows, "yolo_rows": yolo_rows, "summary": summary},
        ensure_ascii=False,
    )

    assert product_literal not in dumped
    assert str(tmp_path) not in dumped
    assert "/private/" not in dumped
    assert "/Volumes/" not in dumped
    assert '"raw_ocr_text":' not in dumped
    assert '"provider_payload":' not in dumped
    assert summary["absolute_paths_stored"] is False
    assert summary["product_dir_literals_stored"] is False
    assert summary["raw_ocr_text_stored"] is False
    assert summary["raw_provider_payload_stored"] is False


def test_sampling_limits_are_applied_per_category(tmp_path: Path) -> None:
    """Verify deterministic category-balanced caps are enforced."""
    root = tmp_path / "crawling-image"
    _touch_image(root / "[오메가3]" / "나우푸드 오메가3_123456" / "리뷰" / "a.jpg", b"a")
    _touch_image(root / "[오메가3]" / "나우푸드 오메가3_123456" / "리뷰" / "b.jpg", b"b")
    _touch_image(root / "[오메가3]" / "나우푸드 오메가3_123456" / "상세페이지" / "a.png", b"c")
    _touch_image(root / "[오메가3]" / "나우푸드 오메가3_123456" / "상세페이지" / "b.png", b"d")

    ocr_rows, yolo_rows, summary = builder.build_learning_candidate_manifests(
        root=root,
        max_review_per_category=1,
        max_detail_per_category=1,
    )

    assert len(ocr_rows) == 1
    assert len(yolo_rows) == 1
    assert summary["ocr_category_counts"] == {"오메가3": 1}
    assert summary["yolo_category_counts"] == {"오메가3": 1}


def test_reject_unsafe_payload_blocks_raw_keys() -> None:
    """Verify raw OCR/provider fields cannot be emitted."""
    with pytest.raises(ValueError, match="raw_ocr_text"):
        builder._reject_unsafe_payload({"raw_ocr_text": "do not emit"})


def test_main_writes_jsonl_outputs_and_redacted_summary(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI writes separate OCR/YOLO outputs plus a safe summary."""
    root = tmp_path / "crawling-image"
    _touch_image(root / "[오메가3]" / "나우푸드 오메가3_123456" / "리뷰" / "review.jpg")
    _touch_image(root / "[오메가3]" / "나우푸드 오메가3_123456" / "상세페이지" / "detail.png")
    ocr_output = tmp_path / "out" / "ocr.jsonl"
    yolo_output = tmp_path / "out" / "yolo.jsonl"

    builder.main(
        [
            "--root",
            str(root),
            "--ocr-output",
            str(ocr_output),
            "--yolo-output",
            str(yolo_output),
            "--source-run-id",
            "cli-test",
        ]
    )

    stdout = capsys.readouterr().out
    summary = json.loads(stdout)
    assert summary["source_run_id"] == "cli-test"
    assert summary["ocr_candidate_count"] == 1
    assert summary["yolo_candidate_count"] == 1
    assert ocr_output.exists()
    assert yolo_output.exists()
    assert ocr_output.with_suffix(".jsonl.summary.json").exists()
    assert "나우푸드 오메가3_123456" not in stdout
    assert str(tmp_path) not in stdout
    assert "/private/" not in stdout
