"""Tests for PaddleOCR improvement candidate manifest builder."""

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

builder = importlib.import_module("scripts.build_paddleocr_improvement_candidates")


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


def _fixture_row(*, observations: list[dict[str, Any]]) -> dict[str, Any]:
    """Build one benchmark fixture row.

    Args:
        observations: Provider observation rows.

    Returns:
        Benchmark fixture row.
    """
    return {
        "schema_version": "supplement-ocr-provider-benchmark-fixture-v1",
        "fixture_id": "fixture-1",
        "source_ref": "ocr-fixture-1",
        "image_ref_hash": "a" * 64,
        "image_sha256": "b" * 64,
        "category_key": "omega3",
        "source_kind": "review",
        "image_path": "images/review-ocr-gt-a.jpg",
        "expected": {
            "verification_status": "human_reviewed",
            "product_name": "Omega 3",
            "manufacturer": "Now Foods",
            "ingredients": [
                {"display_name": "EPA", "amount": 180, "unit": "mg"},
                {"display_name": "DHA", "amount": 120, "unit": "mg"},
            ],
            "intake_method": {"text": "Take 1 softgel daily with food."},
            "precautions": [{"text": "Consult a physician if pregnant or nursing."}],
            "label_sections": [
                {"section_type": "supplement_facts"},
                {"section_type": "precautions"},
            ],
        },
        "observations": observations,
    }


def test_build_candidates_flags_paddleocr_misses_without_raw_payloads(tmp_path: Path) -> None:
    """Verify PaddleOCR misses become manual training candidates."""
    manifest = tmp_path / "benchmark.jsonl"
    _write_jsonl(
        manifest,
        [
            _fixture_row(
                observations=[
                    {
                        "provider": "clova_ocr",
                        "status": "completed",
                        "text_non_empty": True,
                        "parser_success": True,
                        "parsed_ingredients": [
                            {"display_name": "EPA", "amount": 180, "unit": "mg"},
                            {"display_name": "DHA", "amount": 120, "unit": "mg"},
                        ],
                    },
                    {
                        "provider": "paddleocr_local",
                        "status": "completed",
                        "text_non_empty": True,
                        "parser_success": True,
                        "parsed_ingredients": [
                            {"display_name": "EPA", "amount": 180, "unit": "mg"}
                        ],
                        "label_sections": [{"section_type": "supplement_facts"}],
                    },
                ]
            )
        ],
    )

    rows, summary = builder.build_paddleocr_improvement_candidates(
        benchmark_manifest=manifest,
        source_run_id="improve-test",
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["source_run_id"] == "improve-test"
    assert row["target_provider"] == "paddleocr_local"
    assert row["recommended_next_step"] == "paddleocr_detection_manual_review"
    assert row["training_task_suggestions"] == [
        "paddleocr_detection",
        "paddleocr_recognition",
    ]
    assert row["failure_codes"] == [
        "ingredient_amount_unit_miss",
        "ingredient_name_miss",
        "intake_method_miss",
        "precaution_miss",
        "section_type_miss",
    ]
    assert row["score_snapshot"]["teacher_expected_match_count"] == 1
    assert row["score_snapshot"]["missed_ingredient_count"] == 1
    assert row["expected"]["ingredients"][1]["display_name"] == "DHA"

    serialized_summary = json.dumps(summary, ensure_ascii=False)
    assert "DHA" not in serialized_summary
    assert "EPA" not in serialized_summary
    assert "ocr-fixture-1" not in serialized_summary
    assert summary["improvement_candidate_count"] == 1
    assert summary["expected_text_printed"] is False
    assert summary["raw_ocr_text_stored"] is False


def test_build_candidates_skips_clean_paddleocr_result(tmp_path: Path) -> None:
    """Verify fully matching PaddleOCR observations are skipped."""
    manifest = tmp_path / "benchmark.jsonl"
    _write_jsonl(
        manifest,
        [
            _fixture_row(
                observations=[
                    {
                        "provider": "paddleocr_local",
                        "status": "completed",
                        "text_non_empty": True,
                        "parser_success": True,
                        "parsed_ingredients": [
                            {"display_name": "EPA", "amount": 180, "unit": "mg"},
                            {"display_name": "DHA", "amount": 120, "unit": "mg"},
                        ],
                        "intake_method": {"text": "Take 1 softgel daily with food."},
                        "precautions": [{"text": "Consult a physician if pregnant or nursing."}],
                        "label_sections": [
                            {"section_type": "supplement_facts"},
                            {"section_type": "precautions"},
                        ],
                    }
                ]
            )
        ],
    )

    rows, summary = builder.build_paddleocr_improvement_candidates(
        benchmark_manifest=manifest,
    )

    assert rows == []
    assert summary["skip_reason_counts"] == {"paddleocr_no_improvement_issue": 1}


def test_build_candidates_classifies_empty_text_as_detection_candidate(
    tmp_path: Path,
) -> None:
    """Verify empty OCR text is routed to detection manual review."""
    manifest = tmp_path / "benchmark.jsonl"
    _write_jsonl(
        manifest,
        [
            _fixture_row(
                observations=[
                    {
                        "provider": "paddleocr_local",
                        "status": "error",
                        "error_code": "ocr_empty_text",
                        "text_non_empty": False,
                    }
                ]
            )
        ],
    )

    rows, summary = builder.build_paddleocr_improvement_candidates(
        benchmark_manifest=manifest,
    )

    assert len(rows) == 1
    assert rows[0]["recommended_next_step"] == "paddleocr_detection_manual_review"
    assert rows[0]["training_task_suggestions"] == [
        "paddleocr_detection",
        "paddleocr_recognition",
    ]
    assert "paddleocr_empty_text" in rows[0]["failure_codes"]
    assert "paddleocr_runtime_error" in rows[0]["failure_codes"]
    assert summary["failure_code_counts"]["paddleocr_empty_text"] == 1


def test_build_candidates_rejects_raw_ocr_text(tmp_path: Path) -> None:
    """Verify raw OCR text cannot enter improvement manifests."""
    manifest = tmp_path / "benchmark.jsonl"
    row = _fixture_row(
        observations=[
            {
                "provider": "paddleocr_local",
                "status": "completed",
                "raw_ocr_text": "secret",
            }
        ]
    )
    _write_jsonl(manifest, [row])

    with pytest.raises(ValueError, match="raw_ocr_text"):
        builder.build_paddleocr_improvement_candidates(benchmark_manifest=manifest)


def test_build_candidates_rejects_absolute_image_path(tmp_path: Path) -> None:
    """Verify local image paths are rejected."""
    manifest = tmp_path / "benchmark.jsonl"
    row = _fixture_row(
        observations=[
            {
                "provider": "paddleocr_local",
                "status": "error",
                "text_non_empty": False,
            }
        ]
    )
    row["image_path"] = "/private/tmp/image.jpg"
    _write_jsonl(manifest, [row])

    with pytest.raises(ValueError, match="local path literal"):
        builder.build_paddleocr_improvement_candidates(benchmark_manifest=manifest)


def test_main_writes_candidate_and_redacted_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify CLI writes JSONL candidates and a summary."""
    manifest = tmp_path / "benchmark.jsonl"
    output = tmp_path / "out" / "candidates.jsonl"
    summary_path = tmp_path / "out" / "summary.json"
    _write_jsonl(
        manifest,
        [
            _fixture_row(
                observations=[
                    {
                        "provider": "paddleocr_local",
                        "status": "completed",
                        "text_non_empty": True,
                        "parser_success": True,
                        "parsed_ingredients": [
                            {"display_name": "EPA", "amount": 180, "unit": "mg"}
                        ],
                    }
                ]
            )
        ],
    )

    builder.main(
        [
            "--benchmark-manifest",
            str(manifest),
            "--output",
            str(output),
            "--summary",
            str(summary_path),
        ]
    )

    printed = capsys.readouterr().out
    assert "DHA" not in printed
    assert output.exists()
    assert summary_path.exists()
    written_rows = [
        json.loads(line) for line in output.read_text(encoding="utf-8").splitlines() if line
    ]
    written_summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert len(written_rows) == 1
    assert written_rows[0]["schema_version"] == "supplement-paddleocr-improvement-candidate-v1"
    assert written_summary["improvement_candidate_count"] == 1
    assert written_summary["paddleocr_training_performed"] is False
