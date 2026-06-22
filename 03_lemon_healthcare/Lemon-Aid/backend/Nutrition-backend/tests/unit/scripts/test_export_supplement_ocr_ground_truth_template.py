"""Tests for supplement OCR manual ground-truth template export."""

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
template_exporter = importlib.import_module("scripts.export_supplement_ocr_ground_truth_template")


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


def _candidate_rows(tmp_path: Path, *, pii_cleared: bool) -> tuple[Path, list[dict[str, Any]]]:
    """Build OCR candidate fixture rows.

    Args:
        tmp_path: Test temp directory.
        pii_cleared: Whether review candidates are teacher OCR eligible.

    Returns:
        Source root and OCR candidate rows.
    """
    root = tmp_path / "crawling-image"
    _touch_image(root / "[오메가3]" / "나우푸드 오메가3_123456" / "리뷰" / "review.jpg")
    rows, _, _ = candidate_builder.build_learning_candidate_manifests(
        root=root,
        review_personal_data_cleared=pii_cleared,
    )
    return root, rows


def test_export_template_includes_only_pii_cleared_review_candidates(tmp_path: Path) -> None:
    """Verify PII-cleared review candidates become manual GT template rows."""
    _, candidates = _candidate_rows(tmp_path, pii_cleared=True)
    candidate_manifest = tmp_path / "candidates.jsonl"
    _write_jsonl(candidate_manifest, candidates)

    rows, summary = template_exporter.export_ground_truth_template(
        candidate_manifest=candidate_manifest,
        source_run_id="gt-template-test",
    )

    assert len(rows) == 1
    assert summary["template_row_count"] == 1
    assert summary["manual_review_required_count"] == 1
    assert summary["skip_reason_counts"] == {}

    row = rows[0]
    assert row["source_run_id"] == "gt-template-test"
    assert row["fixture_id"] == candidates[0]["fixture_id"]
    assert row["decision"] == "pending"
    assert row["ground_truth_status"] == "pending_manual_review"
    assert row["contains_personal_data"] is False
    assert row["teacher_ocr_allowed"] is True
    assert row["expected"]["verification_status"] == "pending_manual_review"
    assert row["expected"]["product_name"] == ""
    assert row["expected"]["allergen_warnings"] == [{"text": ""}]
    assert row["expected"]["ingredients"] == [
        {
            "display_name": "",
            "amount": None,
            "unit": "",
            "nutrient_code": "",
        }
    ]
    assert "supplement_facts" in row["allowed_label_sections"]
    assert "allergen_warning" in row["allowed_label_sections"]
    assert row["ready_for_benchmark_after_review"] is False
    assert row["ocr_provider_call_performed"] is False
    assert row["paddleocr_training_performed"] is False


def test_export_template_skips_candidates_without_pii_clearance(tmp_path: Path) -> None:
    """Verify PII-pending review candidates do not become manual GT templates."""
    _, candidates = _candidate_rows(tmp_path, pii_cleared=False)
    candidate_manifest = tmp_path / "candidates.jsonl"
    _write_jsonl(candidate_manifest, candidates)

    rows, summary = template_exporter.export_ground_truth_template(
        candidate_manifest=candidate_manifest,
    )

    assert rows == []
    assert summary["template_row_count"] == 0
    assert summary["skip_reason_counts"] == {
        "candidate_pii_or_teacher_gate_not_cleared": 1,
    }


def test_export_template_materializes_relative_private_hashed_image_path(
    tmp_path: Path,
) -> None:
    """Verify optional materialization writes private hashed image copies."""
    source_root = tmp_path / "crawling-image"
    source_image = source_root / "[오메가3]" / "나우푸드 오메가3_123456" / "리뷰" / "review.jpg"
    _touch_image(source_image, b"review-image")
    candidates, _, _ = candidate_builder.build_learning_candidate_manifests(
        root=source_root,
        review_personal_data_cleared=True,
    )
    candidate_manifest = tmp_path / "candidates.jsonl"
    output_path = tmp_path / "out" / "gt-template.jsonl"
    image_dir = tmp_path / "out" / "images"
    _write_jsonl(candidate_manifest, candidates)

    rows, summary = template_exporter.export_ground_truth_template(
        candidate_manifest=candidate_manifest,
        source_root=source_root,
        materialized_image_dir=image_dir,
        output_manifest_path=output_path,
    )

    assert len(rows) == 1
    assert summary["image_materialization_requested"] is True
    assert summary["image_materialized_count"] == 1
    image_path = rows[0]["image_path"]
    assert isinstance(image_path, str)
    assert image_path.startswith("images/review-ocr-gt-")
    assert "나우푸드 오메가3_123456" not in image_path
    assert (output_path.parent / image_path).read_bytes() == b"review-image"
    assert rows[0]["image_materialization_policy"] == "private_hashed_fixture_copy_materialized"


def test_export_template_omits_paths_product_literals_and_raw_payloads(
    tmp_path: Path,
) -> None:
    """Verify template output is redacted and raw-key guarded."""
    _, candidates = _candidate_rows(tmp_path, pii_cleared=True)
    product_literal = "나우푸드 오메가3_123456"
    candidate_manifest = tmp_path / "candidates.jsonl"
    _write_jsonl(candidate_manifest, candidates)

    rows, summary = template_exporter.export_ground_truth_template(
        candidate_manifest=candidate_manifest,
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


def test_export_template_rejects_raw_candidate_keys(tmp_path: Path) -> None:
    """Verify raw OCR text cannot be smuggled through candidate rows."""
    _, candidates = _candidate_rows(tmp_path, pii_cleared=True)
    candidates[0]["raw_ocr_text"] = "do not store"
    candidate_manifest = tmp_path / "candidates.jsonl"
    _write_jsonl(candidate_manifest, candidates)

    with pytest.raises(ValueError, match="raw_ocr_text"):
        template_exporter.export_ground_truth_template(candidate_manifest=candidate_manifest)


def test_main_writes_template_and_summary(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI writes template JSONL and summary."""
    _, candidates = _candidate_rows(tmp_path, pii_cleared=True)
    candidate_manifest = tmp_path / "candidates.jsonl"
    output_path = tmp_path / "out" / "gt-template.jsonl"
    _write_jsonl(candidate_manifest, candidates)

    template_exporter.main(
        [
            "--candidate-manifest",
            str(candidate_manifest),
            "--output",
            str(output_path),
            "--source-run-id",
            "cli-test",
        ]
    )

    stdout = capsys.readouterr().out
    summary = json.loads(stdout)
    assert summary["source_run_id"] == "cli-test"
    assert summary["template_row_count"] == 1
    assert output_path.exists()
    assert output_path.with_suffix(".jsonl.summary.json").exists()
    assert str(tmp_path) not in stdout
    assert "/private/" not in stdout
