"""Tests for exporting Naver Tampermonkey DB staging rows to review ingest."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from scripts import export_naver_tampermonkey_review_ingest as review_ingest


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    """Write JSONL test rows."""
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _input_row(**overrides: object) -> dict[str, object]:
    """Return a minimal DB-labeling-with-OCR row."""
    row: dict[str, object] = {
        "schema_version": "naver-tampermonkey-db-labeling-with-ocr-v1",
        "fixture_id": "naver-tm-detail-000001",
        "source": "naver_tampermonkey",
        "section": "detail",
        "image_root_token": "$NAVER_TAMPERMONKEY_SOURCE_ROOT",
        "image_ref_hash": "b" * 64,
        "image_sha256": "a" * 64,
        "product_id": "1234567890",
        "product_dir_hash": "c" * 64,
        "category_key": "omega_3",
        "display_name_ko": "오메가3",
        "display_name_en": "Omega-3",
        "language_targets": ["ko", "en"],
        "chronic_fixture_tags": ["cardiovascular"],
        "caution_tags": ["anticoagulant_review"],
        "source_urls": ["https://ods.od.nih.gov/factsheets/Omega3FattyAcids-HealthProfessional/"],
        "requires_human_review": True,
        "contains_personal_data": False,
        "pii_screening_status": "not_required_detail_page",
        "external_transfer_allowed": True,
        "local_processing_allowed": True,
        "is_clinical_recommendation": False,
        "ocr_observation_count": 1,
        "ocr_observation_summaries": [
            {
                "provider": "paddleocr_local",
                "status": "completed",
                "text_non_empty": True,
                "parser_success": True,
                "char_count": 182,
                "line_count": 12,
                "latency_ms": 1234.5,
                "text_hash": "abc123",
                "llm_parse_status": "completed",
                "llm_parse_attempt_count": 2,
                "llm_parse_retry_count": 1,
                "llm_parsed_ingredients": [
                    {
                        "display_name": "오메가3",
                        "nutrient_code": "omega_3",
                        "amount": 1000,
                        "unit": "mg",
                        "confidence": 0.92,
                        "source": "ollama_structured",
                    }
                ],
            }
        ],
    }
    row.update(overrides)
    return row


def test_export_review_ingest_keeps_safe_review_task_contract(tmp_path: Path) -> None:
    """Verify review ingest exposes bounded OCR/LLM fields and no raw literals."""
    input_path = tmp_path / "with-ocr.jsonl"
    _write_jsonl(input_path, [_input_row()])

    rows, summary = review_ingest.export_review_ingest_rows(
        input_path=input_path,
        source_run_id="stage14-review-test",
    )

    assert summary["schema_version"] == review_ingest.SCHEMA_VERSION
    assert summary["row_count"] == 1
    assert summary["rows_with_llm_ingredient_candidates"] == 1
    assert summary["total_ingredient_candidates"] == 1
    assert summary["db_import_ready_rows"] == 0
    row = rows[0]
    assert row["schema_version"] == review_ingest.SCHEMA_VERSION
    assert row["source_run_id"] == "stage14-review-test"
    assert row["requires_human_review"] is True
    assert row["is_clinical_recommendation"] is False
    assert row["clinical_recommendation_forbidden"] is True
    assert row["category_display"] == {"ko": "오메가3", "en": "Omega-3"}
    assert row["ingredient_candidates"] == [
        {
            "display_name": "오메가3",
            "nutrient_code": "omega_3",
            "amount": 1000.0,
            "unit": "mg",
            "confidence": 0.92,
            "source": "ollama_structured",
            "provider": "paddleocr_local",
        }
    ]
    review_task = row["review_task"]
    assert isinstance(review_task, dict)
    assert review_task["status"] == "needs_human_review"
    assert review_task["db_import_ready"] is False
    assert review_task["blocked_reasons"] == ["human_review_required"]
    serialized = json.dumps(rows, ensure_ascii=False).lower()
    assert "raw_ocr_text" not in serialized
    assert "provider_payload" not in serialized
    assert "/volumes/" not in serialized
    assert "제품명_1234567890" not in serialized


def test_export_review_ingest_rejects_raw_fields(tmp_path: Path) -> None:
    """Verify raw OCR/provider keys cannot enter review ingest rows."""
    input_path = tmp_path / "with-ocr.jsonl"
    _write_jsonl(input_path, [_input_row(raw_ocr_text="do not persist")])

    with pytest.raises(ValueError, match="raw_ocr_text"):
        review_ingest.export_review_ingest_rows(input_path=input_path)


def test_export_review_ingest_rejects_local_path_literals(tmp_path: Path) -> None:
    """Verify local operator path literals cannot enter review ingest rows."""
    input_path = tmp_path / "with-ocr.jsonl"
    _write_jsonl(input_path, [_input_row(notes="/Volumes/Corsair EX400U Media/image.jpg")])

    with pytest.raises(ValueError, match="local path literal"):
        review_ingest.export_review_ingest_rows(input_path=input_path)

    _write_jsonl(input_path, [_input_row(notes="/private/tmp/image.jpg")])
    with pytest.raises(ValueError, match="local path literal"):
        review_ingest.export_review_ingest_rows(input_path=input_path)


def test_export_review_ingest_rejects_product_dir_literal_key(tmp_path: Path) -> None:
    """Verify product directory literals are rejected even when they are relative."""
    input_path = tmp_path / "with-ocr.jsonl"
    _write_jsonl(input_path, [_input_row(product_dir="제품명_1234567890")])

    with pytest.raises(ValueError, match="product_dir"):
        review_ingest.export_review_ingest_rows(input_path=input_path)


def test_export_review_ingest_rejects_pii_pending_review_with_llm_candidates(
    tmp_path: Path,
) -> None:
    """Verify review images cannot expose LLM ingredients before local PII clearance."""
    input_path = tmp_path / "with-ocr.jsonl"
    _write_jsonl(
        input_path,
        [
            _input_row(
                fixture_id="naver-tm-review-000001",
                section="review",
                contains_personal_data=None,
                pii_screening_status="pending_local_screening",
                external_transfer_allowed=False,
            )
        ],
    )

    with pytest.raises(ValueError, match="PII-pending review"):
        review_ingest.export_review_ingest_rows(input_path=input_path)


def test_export_review_ingest_allows_pii_pending_review_without_llm_candidates(
    tmp_path: Path,
) -> None:
    """Verify PII-pending review rows can be queued without ingredient exposure."""
    input_path = tmp_path / "with-ocr.jsonl"
    row = _input_row(
        fixture_id="naver-tm-review-000001",
        section="review",
        contains_personal_data=None,
        pii_screening_status="pending_local_screening",
        external_transfer_allowed=False,
        ocr_observation_summaries=[
            {
                "provider": "paddleocr_local",
                "status": "completed",
                "text_non_empty": True,
                "parser_success": False,
                "llm_parse_status": "skipped_pii_screening_required",
                "pii_candidate_flags": ["face_candidate"],
            }
        ],
    )
    _write_jsonl(input_path, [row])

    rows, summary = review_ingest.export_review_ingest_rows(input_path=input_path)

    assert summary["pii_pending_review_rows"] == 1
    assert rows[0]["ingredient_candidates"] == []
    review_task = rows[0]["review_task"]
    assert isinstance(review_task, dict)
    assert review_task["blocked_reasons"] == [
        "human_review_required",
        "ingredient_candidates_need_review",
        "pii_pending_local_screening",
        "pii_status_not_cleared",
    ]
    assert "pii_screening_required" in review_task["reasons"]


def test_main_error_is_redacted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI failures do not print tracebacks or local paths."""
    output_path = tmp_path / "review-ingest.jsonl"
    summary_path = tmp_path / "review-ingest.summary.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "export_naver_tampermonkey_review_ingest.py",
            "--input",
            str(tmp_path / "missing-input.jsonl"),
            "--output",
            str(output_path),
            "--summary",
            str(summary_path),
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        review_ingest.main()

    printed = capsys.readouterr().out
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert exc_info.value.code == 1
    assert "Traceback" not in printed
    assert str(tmp_path) not in printed
    assert str(tmp_path) not in json.dumps(summary, ensure_ascii=False)
    assert summary["status"] == "error"
    assert summary["error_code"] == "local_file_error"
    assert summary["input_name"] == "missing-input.jsonl"
    assert summary["output_name"] == "review-ingest.jsonl"
    assert summary["raw_ocr_text_stored"] is False
    assert summary["local_path_literals_stored"] is False
