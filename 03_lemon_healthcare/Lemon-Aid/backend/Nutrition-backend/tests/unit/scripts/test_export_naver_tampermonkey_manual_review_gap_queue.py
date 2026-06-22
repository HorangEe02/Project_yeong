"""Tests for manual-review gap queue export."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import export_naver_tampermonkey_manual_review_gap_queue as exporter


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    """Write JSONL rows for tests."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _review_ingest_row(**overrides: object) -> dict[str, object]:
    """Return one safe review ingest row."""
    row: dict[str, object] = {
        "schema_version": "naver-tampermonkey-review-ingest-v1",
        "review_task_id": "review-task-1",
        "fixture_id": "naver-tm-detail-000001",
        "category_key": "zinc",
        "category_display": {"ko": "아연", "en": "Zinc"},
        "category_reference_urls": ["https://ods.od.nih.gov/factsheets/Zinc-HealthProfessional/"],
        "language_targets": ["ko", "en"],
        "chronic_fixture_tags": ["immune_health"],
        "caution_tags": ["copper_deficiency_review"],
        "product": {
            "product_id": "123456",
            "product_dir_hash": "a" * 64,
        },
        "image": {
            "root_token": "$NAVER_TAMPERMONKEY_SOURCE_ROOT",
            "image_ref_hash": "b" * 64,
            "image_sha256": "c" * 64,
        },
        "ingredient_candidate_count": 0,
        "ingredient_candidates": [],
        "ocr_observation_count": 1,
        "ocr_provider_summaries": [
            {
                "provider": "paddleocr_local",
                "status": "completed",
                "text_non_empty": True,
                "char_count": 200,
                "parser_success": True,
                "llm_parse_status": "completed",
                "llm_parsed_ingredient_count": 0,
            }
        ],
        "review_task": {
            "status": "needs_human_review",
            "priority": "normal",
            "db_import_ready": False,
            "reasons": ["ocr_observation_available"],
            "blocked_reasons": ["human_review_required"],
        },
        "requires_human_review": True,
        "is_clinical_recommendation": False,
        "clinical_recommendation_forbidden": True,
    }
    row.update(overrides)
    return row


def test_export_gap_queue_selects_rows_without_candidates(tmp_path: Path) -> None:
    """Verify rows without ingredient candidates become manual-review gaps."""
    input_path = tmp_path / "review-ingest.jsonl"
    _write_jsonl(
        input_path,
        [
            _review_ingest_row(),
            _review_ingest_row(
                review_task_id="review-task-2",
                fixture_id="naver-tm-detail-000002",
                ingredient_candidate_count=1,
                ingredient_candidates=[{"display_name": "Zinc"}],
                ocr_provider_summaries=[
                    {
                        "provider": "paddleocr_local",
                        "status": "completed",
                        "text_non_empty": True,
                        "char_count": 100,
                        "parser_success": True,
                        "llm_parse_status": "completed",
                        "llm_parsed_ingredient_count": 1,
                    }
                ],
            ),
        ],
    )

    rows, summary = exporter.export_gap_queue(
        input_path=input_path,
        output_dir=tmp_path / "out",
    )

    assert len(rows) == 1
    assert rows[0]["fixture_id"] == "naver-tm-detail-000001"
    assert rows[0]["gap_reasons"] == [
        "ingredient_candidate_count_zero",
        "llm_zero_ingredient_candidates",
    ]
    assert rows[0]["db_write_performed"] is False
    assert summary["input_row_count"] == 2
    assert summary["gap_row_count"] == 1
    serialized = json.dumps({"rows": rows, "summary": summary}, ensure_ascii=False)
    assert "image_path" not in serialized
    assert '"product_dir"' not in serialized
    assert "/Volumes/" not in serialized


def test_export_gap_queue_selects_ocr_error_rows(tmp_path: Path) -> None:
    """Verify OCR error rows are included even without LLM candidates."""
    input_path = tmp_path / "review-ingest.jsonl"
    row = _review_ingest_row(
        ocr_provider_summaries=[
            {
                "provider": "paddleocr_local",
                "status": "error",
                "error_code": "ocr_low_confidence",
                "text_non_empty": False,
                "char_count": 0,
                "parser_success": False,
            }
        ],
    )
    _write_jsonl(input_path, [row])

    rows, summary = exporter.export_gap_queue(
        input_path=input_path,
        output_dir=tmp_path / "out",
    )

    assert len(rows) == 1
    assert rows[0]["gap_reasons"] == [
        "ingredient_candidate_count_zero",
        "ocr_provider_error",
    ]
    assert summary["reason_counts"]["ocr_provider_error"] == 1


def test_export_gap_queue_rejects_raw_input_field(tmp_path: Path) -> None:
    """Verify raw OCR fields cannot enter the queue."""
    input_path = tmp_path / "review-ingest.jsonl"
    row = _review_ingest_row(raw_ocr_text="forbidden")
    _write_jsonl(input_path, [row])

    with pytest.raises(ValueError, match="raw_ocr_text"):
        exporter.export_gap_queue(input_path=input_path, output_dir=tmp_path / "out")


def test_export_gap_queue_rejects_local_path_literal(tmp_path: Path) -> None:
    """Verify local path literals cannot enter the queue."""
    input_path = tmp_path / "review-ingest.jsonl"
    row = _review_ingest_row(product={"product_id": "123", "product_dir_hash": "/Volumes/x"})
    _write_jsonl(input_path, [row])

    with pytest.raises(ValueError, match="local path"):
        exporter.export_gap_queue(input_path=input_path, output_dir=tmp_path / "out")


def test_write_outputs_are_redacted(tmp_path: Path) -> None:
    """Verify writer creates queue and summary without unsafe literals."""
    input_path = tmp_path / "review-ingest.jsonl"
    _write_jsonl(input_path, [_review_ingest_row()])
    rows, summary = exporter.export_gap_queue(input_path=input_path, output_dir=tmp_path / "out")

    exporter._write_outputs(
        rows=rows,
        summary=summary,
        output_dir=tmp_path / "out",
        queue_name=exporter.DEFAULT_QUEUE_NAME,
        summary_name=exporter.DEFAULT_SUMMARY_NAME,
    )

    queue_text = (tmp_path / "out" / exporter.DEFAULT_QUEUE_NAME).read_text(encoding="utf-8")
    assert "naver-tm-detail-000001" in queue_text
    assert "forbidden" not in queue_text
    assert "image_path" not in queue_text
