"""Tests for OCR provider benchmark manifest builder."""

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
benchmark = importlib.import_module("scripts.build_supplement_ocr_benchmark_manifest")


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


def _candidate_rows(tmp_path: Path, *, pii_cleared: bool) -> list[dict[str, Any]]:
    """Build OCR candidate fixture rows.

    Args:
        tmp_path: Test temp directory.
        pii_cleared: Whether review candidates are teacher OCR eligible.

    Returns:
        OCR candidate rows.
    """
    root = tmp_path / "crawling-image"
    _touch_image(root / "[오메가3]" / "나우푸드 오메가3_123456" / "리뷰" / "review.jpg")
    rows, _, _ = candidate_builder.build_learning_candidate_manifests(
        root=root,
        review_personal_data_cleared=pii_cleared,
    )
    return rows


def _approved_ground_truth_row(candidate: dict[str, Any]) -> dict[str, Any]:
    """Return one approved manual GT row.

    Args:
        candidate: OCR candidate row.

    Returns:
        Human-reviewed ground-truth row.
    """
    return {
        "fixture_id": candidate["fixture_id"],
        "ground_truth_status": "human_reviewed",
        "contains_personal_data": False,
        "expected": {
            "verification_status": "human_reviewed",
            "product_name": "Omega 3",
            "manufacturer": "Now Foods",
            "ingredients": [
                {
                    "display_name": "EPA",
                    "amount": 180,
                    "unit": "mg",
                    "nutrient_code": "epa",
                },
                {
                    "display_name": "DHA",
                    "amount": 120,
                    "unit": "mg",
                    "nutrient_code": "dha",
                },
            ],
            "intake_method": {"text": "Take 1 softgel daily with food."},
            "precautions": [{"text": "Consult a physician if pregnant or nursing."}],
            "allergen_warnings": [{"text": "Contains fish and soy."}],
            "functional_claims": [{"text": "Supports heart health."}],
            "label_sections": [
                {"section_type": "supplement_facts"},
                {"section_type": "precautions"},
                {"section_type": "allergen_warning"},
            ],
        },
    }


def test_build_benchmark_manifest_promotes_only_pii_cleared_human_gt(
    tmp_path: Path,
) -> None:
    """Verify approved manual GT and PII-cleared candidate become scoreable."""
    candidates = _candidate_rows(tmp_path, pii_cleared=True)
    candidate_manifest = tmp_path / "candidates.jsonl"
    ground_truth_manifest = tmp_path / "gt.jsonl"
    _write_jsonl(candidate_manifest, candidates)
    _write_jsonl(ground_truth_manifest, [_approved_ground_truth_row(candidates[0])])

    rows, summary = benchmark.build_ocr_benchmark_manifest(
        candidate_manifest=candidate_manifest,
        ground_truth_manifest=ground_truth_manifest,
        source_run_id="benchmark-test",
    )

    assert len(rows) == 1
    assert summary["benchmark_fixture_count"] == 1
    assert summary["scoreable_fixture_count"] == 1
    assert summary["skip_reason_counts"] == {}
    assert summary["required_expected_sections"] == ["ingredient_amounts"]
    assert summary["missing_required_section_counts"] == {}

    row = rows[0]
    assert row["source_run_id"] == "benchmark-test"
    assert row["fixture_id"] == candidates[0]["fixture_id"]
    assert row["product_dir_hash"] == candidates[0]["product_dir_hash"]
    assert row["teacher_providers"] == ["clova_ocr", "google_vision_document"]
    assert row["target_provider"] == "paddleocr_local"
    assert row["external_transfer_allowed"] is True
    assert row["teacher_ocr_allowed"] is True
    assert row["ocr_provider_call_performed"] is False
    assert row["paddleocr_training_performed"] is False
    assert row["expected"]["verification_status"] == "human_reviewed"
    assert row["required_expected_sections"] == ["ingredient_amounts"]
    assert row["expected"]["ingredients"][0] == {
        "display_name": "EPA",
        "amount": 180.0,
        "unit": "mg",
        "nutrient_code": "epa",
    }
    assert row["expected"]["intake_method"]["text"] == "Take 1 softgel daily with food."
    assert row["expected"]["precautions"] == [
        {"text": "Consult a physician if pregnant or nursing."}
    ]
    assert row["expected"]["allergen_warnings"] == [{"text": "Contains fish and soy."}]
    assert row["expected"]["label_sections"] == [
        {"section_type": "supplement_facts"},
        {"section_type": "precautions"},
        {"section_type": "allergen_warning"},
    ]


def test_benchmark_manifest_skips_candidates_without_pii_clearance(tmp_path: Path) -> None:
    """Verify review images pending PII screening cannot enter teacher benchmark."""
    candidates = _candidate_rows(tmp_path, pii_cleared=False)
    candidate_manifest = tmp_path / "candidates.jsonl"
    ground_truth_manifest = tmp_path / "gt.jsonl"
    _write_jsonl(candidate_manifest, candidates)
    _write_jsonl(ground_truth_manifest, [_approved_ground_truth_row(candidates[0])])

    rows, summary = benchmark.build_ocr_benchmark_manifest(
        candidate_manifest=candidate_manifest,
        ground_truth_manifest=ground_truth_manifest,
    )

    assert rows == []
    assert summary["benchmark_fixture_count"] == 0
    assert summary["skip_reason_counts"] == {
        "candidate_pii_or_teacher_gate_not_cleared": 1,
    }


def test_benchmark_manifest_skips_unreviewed_ground_truth(tmp_path: Path) -> None:
    """Verify provisional/manual-pending GT is not scoreable."""
    candidates = _candidate_rows(tmp_path, pii_cleared=True)
    candidate_manifest = tmp_path / "candidates.jsonl"
    ground_truth_manifest = tmp_path / "gt.jsonl"
    gt = _approved_ground_truth_row(candidates[0])
    gt["ground_truth_status"] = "pending_manual_review"
    _write_jsonl(candidate_manifest, candidates)
    _write_jsonl(ground_truth_manifest, [gt])

    rows, summary = benchmark.build_ocr_benchmark_manifest(
        candidate_manifest=candidate_manifest,
        ground_truth_manifest=ground_truth_manifest,
    )

    assert rows == []
    assert summary["skip_reason_counts"] == {
        "manual_ground_truth_not_human_reviewed": 1,
    }


def test_benchmark_manifest_skips_gt_not_marked_ready_for_benchmark(
    tmp_path: Path,
) -> None:
    """Verify reviewed template rows need an explicit benchmark-ready flag."""
    candidates = _candidate_rows(tmp_path, pii_cleared=True)
    candidate_manifest = tmp_path / "candidates.jsonl"
    ground_truth_manifest = tmp_path / "gt.jsonl"
    gt = _approved_ground_truth_row(candidates[0])
    gt["ready_for_benchmark_after_review"] = False
    _write_jsonl(candidate_manifest, candidates)
    _write_jsonl(ground_truth_manifest, [gt])

    rows, summary = benchmark.build_ocr_benchmark_manifest(
        candidate_manifest=candidate_manifest,
        ground_truth_manifest=ground_truth_manifest,
    )

    assert rows == []
    assert summary["skip_reason_counts"] == {
        "manual_ground_truth_not_marked_ready_for_benchmark": 1,
    }


def test_benchmark_manifest_can_require_intake_and_precaution_sections(
    tmp_path: Path,
) -> None:
    """Verify operation runs can require all user-facing OCR sections."""
    candidates = _candidate_rows(tmp_path, pii_cleared=True)
    candidate_manifest = tmp_path / "candidates.jsonl"
    ground_truth_manifest = tmp_path / "gt.jsonl"
    gt = _approved_ground_truth_row(candidates[0])
    gt["expected"]["intake_method"] = {}
    gt["expected"]["precautions"] = []
    _write_jsonl(candidate_manifest, candidates)
    _write_jsonl(ground_truth_manifest, [gt])

    rows, summary = benchmark.build_ocr_benchmark_manifest(
        candidate_manifest=candidate_manifest,
        ground_truth_manifest=ground_truth_manifest,
        required_expected_sections=(
            "ingredient_amounts",
            "intake_method",
            "precautions",
        ),
    )

    assert rows == []
    assert summary["required_expected_sections"] == [
        "ingredient_amounts",
        "intake_method",
        "precautions",
    ]
    assert summary["skip_reason_counts"] == {
        "manual_ground_truth_missing_required_sections": 1,
    }
    assert summary["missing_required_section_counts"] == {
        "intake_method": 1,
        "precautions": 1,
    }


def test_benchmark_manifest_can_require_allergen_warning_section(
    tmp_path: Path,
) -> None:
    """Verify allergen warning text can be required separately from precautions."""
    candidates = _candidate_rows(tmp_path, pii_cleared=True)
    candidate_manifest = tmp_path / "candidates.jsonl"
    ground_truth_manifest = tmp_path / "gt.jsonl"
    gt = _approved_ground_truth_row(candidates[0])
    gt["expected"]["allergen_warnings"] = []
    _write_jsonl(candidate_manifest, candidates)
    _write_jsonl(ground_truth_manifest, [gt])

    rows, summary = benchmark.build_ocr_benchmark_manifest(
        candidate_manifest=candidate_manifest,
        ground_truth_manifest=ground_truth_manifest,
        required_expected_sections=("ingredient_amounts", "allergen_warnings"),
    )

    assert rows == []
    assert summary["required_expected_sections"] == [
        "ingredient_amounts",
        "allergen_warnings",
    ]
    assert summary["missing_required_section_counts"] == {"allergen_warnings": 1}


def test_benchmark_manifest_promotes_when_required_sections_are_present(
    tmp_path: Path,
) -> None:
    """Verify stricter section requirements still promote complete GT rows."""
    candidates = _candidate_rows(tmp_path, pii_cleared=True)
    candidate_manifest = tmp_path / "candidates.jsonl"
    ground_truth_manifest = tmp_path / "gt.jsonl"
    _write_jsonl(candidate_manifest, candidates)
    _write_jsonl(ground_truth_manifest, [_approved_ground_truth_row(candidates[0])])

    rows, summary = benchmark.build_ocr_benchmark_manifest(
        candidate_manifest=candidate_manifest,
        ground_truth_manifest=ground_truth_manifest,
        required_expected_sections=(
            "product_identity",
            "ingredient_amounts",
            "intake_method",
            "precautions",
        ),
    )

    assert len(rows) == 1
    assert summary["benchmark_fixture_count"] == 1
    assert summary["missing_required_section_counts"] == {}
    assert rows[0]["required_expected_sections"] == [
        "product_identity",
        "ingredient_amounts",
        "intake_method",
        "precautions",
    ]


def test_benchmark_manifest_omits_paths_product_literals_and_raw_payloads(
    tmp_path: Path,
) -> None:
    """Verify benchmark output is redacted and raw-key guarded."""
    candidates = _candidate_rows(tmp_path, pii_cleared=True)
    product_literal = "나우푸드 오메가3_123456"
    candidate_manifest = tmp_path / "candidates.jsonl"
    ground_truth_manifest = tmp_path / "gt.jsonl"
    _write_jsonl(candidate_manifest, candidates)
    _write_jsonl(ground_truth_manifest, [_approved_ground_truth_row(candidates[0])])

    rows, summary = benchmark.build_ocr_benchmark_manifest(
        candidate_manifest=candidate_manifest,
        ground_truth_manifest=ground_truth_manifest,
    )
    dumped = json.dumps({"rows": rows, "summary": summary}, ensure_ascii=False)

    assert product_literal not in dumped
    assert str(tmp_path) not in dumped
    assert "/private/" not in dumped
    assert "/Volumes/" not in dumped
    assert '"raw_ocr_text":' not in dumped
    assert '"provider_payload":' not in dumped
    assert rows[0]["product_dir_hash"] == candidates[0]["product_dir_hash"]
    assert rows[0]["absolute_paths_stored"] is False
    assert rows[0]["product_dir_literals_stored"] is False
    assert summary["raw_ocr_text_stored"] is False
    assert summary["raw_provider_payload_stored"] is False


def test_benchmark_manifest_can_materialize_private_hashed_image_fixture(
    tmp_path: Path,
) -> None:
    """Verify provider-runnable manifests use hashed relative image paths."""
    source_root = tmp_path / "crawling-image"
    source_image = source_root / "[오메가3]" / "나우푸드 오메가3_123456" / "리뷰" / "review.jpg"
    _touch_image(source_image, b"review-image")
    candidates, _, _ = candidate_builder.build_learning_candidate_manifests(
        root=source_root,
        review_personal_data_cleared=True,
    )
    candidate_manifest = tmp_path / "candidates.jsonl"
    ground_truth_manifest = tmp_path / "gt.jsonl"
    output_path = tmp_path / "out" / "benchmark.jsonl"
    image_dir = tmp_path / "out" / "images"
    _write_jsonl(candidate_manifest, candidates)
    _write_jsonl(ground_truth_manifest, [_approved_ground_truth_row(candidates[0])])

    rows, summary = benchmark.build_ocr_benchmark_manifest(
        candidate_manifest=candidate_manifest,
        ground_truth_manifest=ground_truth_manifest,
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
    assert rows[0]["image_materialization_required"] is False
    assert rows[0]["image_materialization_policy"] == "private_hashed_fixture_copy_materialized"


def test_benchmark_manifest_rejects_raw_ground_truth_keys(tmp_path: Path) -> None:
    """Verify raw OCR text cannot be smuggled through manual GT rows."""
    candidates = _candidate_rows(tmp_path, pii_cleared=True)
    candidate_manifest = tmp_path / "candidates.jsonl"
    ground_truth_manifest = tmp_path / "gt.jsonl"
    _write_jsonl(candidate_manifest, candidates)
    gt = _approved_ground_truth_row(candidates[0])
    gt["raw_ocr_text"] = "do not store"
    _write_jsonl(ground_truth_manifest, [gt])

    with pytest.raises(ValueError, match="raw_ocr_text"):
        benchmark.build_ocr_benchmark_manifest(
            candidate_manifest=candidate_manifest,
            ground_truth_manifest=ground_truth_manifest,
        )


def test_main_writes_benchmark_manifest_and_summary(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI writes benchmark JSONL and summary."""
    candidates = _candidate_rows(tmp_path, pii_cleared=True)
    candidate_manifest = tmp_path / "candidates.jsonl"
    ground_truth_manifest = tmp_path / "gt.jsonl"
    output_path = tmp_path / "out" / "benchmark.jsonl"
    _write_jsonl(candidate_manifest, candidates)
    _write_jsonl(ground_truth_manifest, [_approved_ground_truth_row(candidates[0])])

    benchmark.main(
        [
            "--candidate-manifest",
            str(candidate_manifest),
            "--ground-truth",
            str(ground_truth_manifest),
            "--output",
            str(output_path),
            "--source-run-id",
            "cli-test",
            "--required-expected-section",
            "ingredient_amounts",
            "--required-expected-section",
            "intake_method",
        ]
    )

    stdout = capsys.readouterr().out
    summary = json.loads(stdout)
    assert summary["source_run_id"] == "cli-test"
    assert summary["benchmark_fixture_count"] == 1
    assert summary["required_expected_sections"] == ["ingredient_amounts", "intake_method"]
    assert output_path.exists()
    assert output_path.with_suffix(".jsonl.summary.json").exists()
    assert str(tmp_path) not in stdout
    assert "/private/" not in stdout
