"""Tests for supplement YOLO annotation template export."""

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

candidate_builder = importlib.import_module("scripts.build_supplement_learning_candidate_manifests")
template_exporter = importlib.import_module("scripts.export_supplement_yolo_annotation_template")


def _touch_image(path: Path, content: bytes = b"placeholder") -> None:
    """Create a small image-like fixture file.

    Args:
        path: Target path.
        content: Bytes used for deterministic hashing.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


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


def _candidate_rows(tmp_path: Path) -> tuple[Path, list[dict[str, Any]]]:
    """Build detail-page YOLO candidate rows.

    Args:
        tmp_path: Test temp directory.

    Returns:
        Source root and candidate rows.
    """
    source_root = tmp_path / "crawling-image"
    _touch_image(
        source_root / "[오메가3]" / "나우푸드 오메가3_123456" / "상세페이지" / "detail.png",
        b"detail-image",
    )
    _, yolo_rows, _ = candidate_builder.build_learning_candidate_manifests(root=source_root)
    return source_root, yolo_rows


def test_export_yolo_annotation_template_from_detail_candidates(tmp_path: Path) -> None:
    """Verify detail-page candidates become human bbox review templates."""
    _source_root, candidates = _candidate_rows(tmp_path)
    candidate_manifest = tmp_path / "yolo-candidates.jsonl"
    _write_jsonl(candidate_manifest, candidates)

    rows, summary = template_exporter.export_yolo_annotation_template(
        candidate_manifest=candidate_manifest,
        source_run_id="annotation-template-test",
    )

    assert len(rows) == 1
    assert summary["source_run_id"] == "annotation-template-test"
    assert summary["template_row_count"] == 1
    assert summary["required_human_review_count"] == 1
    row = rows[0]
    assert row["fixture_id"] == candidates[0]["fixture_id"]
    assert row["annotation_task_type"] == "supplement_roi_box"
    assert row["annotation_status"] == "pending_human_bbox_review"
    assert row["coordinate_space"] == "source_image"
    assert "supplement_facts" in row["allowed_labels"]
    assert "precautions" in row["allowed_labels"]
    assert row["label_snapshot"] == {
        "schema_version": "supplement-section-yolo-label-candidates-v1",
        "candidate_source": "human_annotation_template",
        "coordinate_space": "source_image",
        "human_review_required": True,
        "text_stored": False,
        "training_export_allowed": False,
        "boxes": [],
    }
    assert row["image_materialization_required"] is True
    assert row["db_write_performed"] is False
    assert row["training_export_performed"] is False


def test_export_yolo_annotation_template_materializes_private_hashed_images(
    tmp_path: Path,
) -> None:
    """Verify reviewer fixtures use relative hashed paths, not source literals."""
    source_root, candidates = _candidate_rows(tmp_path)
    candidate_manifest = tmp_path / "yolo-candidates.jsonl"
    output_path = tmp_path / "out" / "annotation-template.jsonl"
    image_dir = tmp_path / "out" / "images"
    _write_jsonl(candidate_manifest, candidates)

    rows, summary = template_exporter.export_yolo_annotation_template(
        candidate_manifest=candidate_manifest,
        output_path=output_path,
        source_root=source_root,
        materialized_image_dir=image_dir,
    )

    assert len(rows) == 1
    assert summary["image_materialization_requested"] is True
    assert summary["image_materialized_count"] == 1
    image_path = rows[0]["image_path"]
    assert isinstance(image_path, str)
    assert image_path.startswith("images/detail-yolo-")
    assert "나우푸드 오메가3_123456" not in image_path
    assert (output_path.parent / image_path).read_bytes() == b"detail-image"
    assert rows[0]["image_materialization_required"] is False
    assert rows[0]["image_materialization_policy"] == "private_hashed_fixture_copy_materialized"


def test_export_yolo_annotation_template_skips_non_detail_rows(tmp_path: Path) -> None:
    """Verify review OCR candidates cannot become bbox annotation templates."""
    source_root = tmp_path / "crawling-image"
    _touch_image(source_root / "[비타민C]" / "고려은단 비타민C_789012" / "리뷰" / "review.jpg")
    ocr_rows, _yolo_rows, _summary = candidate_builder.build_learning_candidate_manifests(
        root=source_root,
        review_personal_data_cleared=True,
    )
    candidate_manifest = tmp_path / "ocr-candidates.jsonl"
    _write_jsonl(candidate_manifest, ocr_rows)

    rows, summary = template_exporter.export_yolo_annotation_template(
        candidate_manifest=candidate_manifest,
    )

    assert rows == []
    assert summary["template_row_count"] == 0
    assert summary["skip_reason_counts"] == {"candidate_not_annotation_ready": 1}


def test_export_yolo_annotation_template_omits_paths_product_literals_and_raw_payloads(
    tmp_path: Path,
) -> None:
    """Verify output redaction for product names, local paths, and raw fields."""
    source_root, candidates = _candidate_rows(tmp_path)
    product_literal = "나우푸드 오메가3_123456"
    candidate_manifest = tmp_path / "yolo-candidates.jsonl"
    output_path = tmp_path / "out" / "annotation-template.jsonl"
    image_dir = tmp_path / "out" / "images"
    _write_jsonl(candidate_manifest, candidates)

    rows, summary = template_exporter.export_yolo_annotation_template(
        candidate_manifest=candidate_manifest,
        output_path=output_path,
        source_root=source_root,
        materialized_image_dir=image_dir,
    )
    dumped = json.dumps({"rows": rows, "summary": summary}, ensure_ascii=False)

    assert product_literal not in dumped
    assert str(tmp_path) not in dumped
    assert "/private/" not in dumped
    assert "/Volumes/" not in dumped
    assert '"raw_ocr_text":' not in dumped
    assert '"provider_payload":' not in dumped
    assert rows[0]["absolute_paths_stored"] is False
    assert rows[0]["product_dir_literals_stored"] is False
    assert summary["raw_ocr_text_stored"] is False
    assert summary["raw_provider_payload_stored"] is False


def test_export_yolo_annotation_template_main_writes_outputs(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI writes JSONL rows and a redacted summary."""
    source_root, candidates = _candidate_rows(tmp_path)
    candidate_manifest = tmp_path / "yolo-candidates.jsonl"
    output_path = tmp_path / "out" / "annotation-template.jsonl"
    image_dir = tmp_path / "out" / "images"
    _write_jsonl(candidate_manifest, candidates)

    template_exporter.main(
        [
            "--candidate-manifest",
            str(candidate_manifest),
            "--output",
            str(output_path),
            "--source-root",
            str(source_root),
            "--materialized-image-dir",
            str(image_dir),
            "--source-run-id",
            "cli-template-test",
        ]
    )

    stdout = capsys.readouterr().out
    summary = json.loads(stdout)
    rows = [
        json.loads(line)
        for line in output_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert summary["source_run_id"] == "cli-template-test"
    assert summary["template_row_count"] == 1
    assert output_path.exists()
    assert output_path.with_suffix(".jsonl.summary.json").exists()
    assert rows[0]["image_path"].startswith("images/detail-yolo-")
    assert "나우푸드 오메가3_123456" not in stdout
    assert str(tmp_path) not in stdout
