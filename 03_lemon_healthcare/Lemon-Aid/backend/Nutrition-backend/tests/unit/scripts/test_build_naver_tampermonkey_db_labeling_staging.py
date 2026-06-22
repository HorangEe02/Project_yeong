"""Tests for Naver Tampermonkey DB-labeling staging export."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import build_naver_tampermonkey_db_labeling_staging as staging


def _manifest_row(**overrides: object) -> dict[str, object]:
    """Return a valid minimal folder-labeled manifest row."""
    row: dict[str, object] = {
        "fixture_id": "naver-tm-detail-000001",
        "source": "naver_tampermonkey",
        "category": "[오메가3]",
        "product_dir": "민감하지 않은 상품명_1234567890",
        "product_id": "1234567890",
        "section": "detail",
        "image_path": "$NAVER_TAMPERMONKEY_SOURCE_ROOT/[오메가3]/민감하지 않은 상품명_1234567890/상세페이지/1.jpg",
        "image_sha256": "a" * 64,
        "contains_personal_data": False,
        "pii_screening_status": "not_required_detail_page",
        "external_transfer_allowed": True,
        "local_processing_allowed": True,
        "fixture_labels": {
            "supplement_category": {
                "category_key": "omega_3",
                "display_name_ko": "오메가3",
                "display_name_en": "Omega-3",
            },
            "language_targets": ["en", "ko"],
        },
        "db_labeling": {
            "status": "pending_human_review",
            "category_key": "omega_3",
            "language_targets": ["ko", "en"],
            "chronic_fixture_tags": ["cardiovascular", "dyslipidemia"],
            "caution_tags": ["anticoagulant_review"],
            "source_urls": [
                "https://ods.od.nih.gov/factsheets/Omega3FattyAcids-HealthProfessional/"
            ],
        },
        "expected": {},
    }
    row.update(overrides)
    return row


def test_build_staging_rows_keep_bilingual_db_labels_without_product_literal(
    tmp_path: Path,
) -> None:
    """Verify staging rows preserve DB labels while hashing product directory literals."""
    manifest_path = tmp_path / "manifest.jsonl"
    row = _manifest_row()
    manifest_path.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")

    rows = staging.build_staging_rows(
        manifest_path=manifest_path,
        source_run_id="stage14-test",
    )

    assert rows == [
        {
            "schema_version": staging.SCHEMA_VERSION,
            "fixture_id": "naver-tm-detail-000001",
            "source": "naver_tampermonkey",
            "section": "detail",
            "image_root_token": "$NAVER_TAMPERMONKEY_SOURCE_ROOT",
            "image_ref_hash": rows[0]["image_ref_hash"],
            "image_sha256": "a" * 64,
            "product_id": "1234567890",
            "product_dir_hash": rows[0]["product_dir_hash"],
            "source_category": "[오메가3]",
            "category_key": "omega_3",
            "display_name_ko": "오메가3",
            "display_name_en": "Omega-3",
            "language_targets": ["en", "ko"],
            "chronic_fixture_tags": ["cardiovascular", "dyslipidemia"],
            "caution_tags": ["anticoagulant_review"],
            "source_urls": [
                "https://ods.od.nih.gov/factsheets/Omega3FattyAcids-HealthProfessional/"
            ],
            "label_status": "pending_human_review",
            "requires_human_review": True,
            "contains_personal_data": False,
            "pii_screening_status": "not_required_detail_page",
            "external_transfer_allowed": True,
            "local_processing_allowed": True,
            "is_clinical_recommendation": False,
            "source_run_id": "stage14-test",
        }
    ]
    serialized = json.dumps(rows, ensure_ascii=False)
    assert "민감하지 않은 상품명" not in serialized
    assert "raw_ocr_text" not in serialized
    assert "provider_payload" not in serialized


def test_build_staging_rows_rejects_raw_fields(tmp_path: Path) -> None:
    """Verify raw OCR/provider keys cannot enter DB-labeling staging."""
    manifest_path = tmp_path / "manifest.jsonl"
    row = _manifest_row(raw_ocr_text="do not persist")
    manifest_path.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="raw_ocr_text"):
        staging.build_staging_rows(manifest_path=manifest_path)


def test_build_staging_rows_rejects_local_absolute_image_path(tmp_path: Path) -> None:
    """Verify staging rows never store operator-local absolute image paths."""
    manifest_path = tmp_path / "manifest.jsonl"
    row = _manifest_row(image_path=str(tmp_path / "detail.jpg"))
    manifest_path.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="local path literal"):
        staging.build_staging_rows(manifest_path=manifest_path)


def test_build_staging_rows_rejects_local_literal_metadata(tmp_path: Path) -> None:
    """Verify local model or media paths cannot be hashed into staging rows."""
    manifest_path = tmp_path / "manifest.jsonl"
    row = _manifest_row(product_dir="/Volumes/Corsair EX400U Media/.ollama/models")
    manifest_path.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="local path literal"):
        staging.build_staging_rows(manifest_path=manifest_path)


def test_build_staging_rows_rejects_review_external_without_pii_clearance(
    tmp_path: Path,
) -> None:
    """Verify review fixtures cannot be staged for external transfer before PII clearance."""
    manifest_path = tmp_path / "manifest.jsonl"
    row = _manifest_row(
        fixture_id="naver-tm-review-000001",
        section="review",
        contains_personal_data=None,
        pii_screening_status="pending_local_screening",
        external_transfer_allowed=True,
    )
    manifest_path.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="PII clearance"):
        staging.build_staging_rows(manifest_path=manifest_path)


def test_build_summary_reports_no_raw_artifacts(tmp_path: Path) -> None:
    """Verify summary exposes only safe counts and raw-storage flags."""
    manifest_path = tmp_path / "manifest.jsonl"
    row = _manifest_row()
    manifest_path.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
    rows = staging.build_staging_rows(manifest_path=manifest_path)

    summary = staging.build_summary(rows=rows, manifest_path=manifest_path)

    assert summary["row_count"] == 1
    assert summary["category_counts"] == {"omega_3": 1}
    assert summary["raw_ocr_text_stored"] is False
    assert summary["product_dir_literals_stored"] is False


def test_build_staging_main_error_is_redacted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI failures print a redacted JSON summary instead of traceback paths."""
    missing_path = tmp_path / "missing.jsonl"
    output_path = tmp_path / "out.jsonl"
    monkeypatch.setattr(
        "sys.argv",
        [
            "build_naver_tampermonkey_db_labeling_staging.py",
            "--manifest",
            str(missing_path),
            "--output",
            str(output_path),
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        staging.main()

    assert exc_info.value.code == 1
    stdout = capsys.readouterr().out
    summary = json.loads(stdout)
    assert summary["status"] == "error"
    assert summary["error_message"] == "Local file operation failed."
    assert str(tmp_path) not in stdout
    assert "/private/" not in stdout
