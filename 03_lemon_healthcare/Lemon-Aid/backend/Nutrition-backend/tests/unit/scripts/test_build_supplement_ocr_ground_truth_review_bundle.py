"""Tests for supplement OCR ground-truth local review bundle generation."""

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

review_bundle = importlib.import_module("scripts.build_supplement_ocr_ground_truth_review_bundle")


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


def _template_row(
    *,
    fixture_id: str = "review-ocr-gt-001",
    image_path: str | None = "images/review-ocr-gt-001.jpg",
    contains_personal_data: bool = False,
    teacher_ocr_allowed: bool = True,
) -> dict[str, Any]:
    """Return a minimal manual OCR ground-truth template row.

    Args:
        fixture_id: Fixture id.
        image_path: Optional relative materialized image path.
        contains_personal_data: Whether personal data is visible.
        teacher_ocr_allowed: Whether teacher OCR comparison is allowed.

    Returns:
        Template row.
    """
    row: dict[str, Any] = {
        "schema_version": review_bundle.EXPECTED_TEMPLATE_ROW_SCHEMA_VERSION,
        "source_run_id": "gt-template-test",
        "fixture_id": fixture_id,
        "source_ref": "review:a" + ("1" * 63),
        "image_ref_hash": "a" * 64,
        "image_sha256": "b" * 64,
        "image_size_bytes": 17,
        "image_mime_type": "image/jpeg",
        "category_key": "omega3",
        "source_kind": "review",
        "decision": "pending",
        "ground_truth_status": "pending_manual_review",
        "contains_personal_data": contains_personal_data,
        "pii_screening_status": "operator_cleared_no_personal_data",
        "external_transfer_allowed": True,
        "teacher_ocr_allowed": teacher_ocr_allowed,
        "expected": {
            "verification_status": "pending_manual_review",
            "expected_source": "manual_review_template",
            "product_name": "",
            "manufacturer": "",
            "ingredients": [
                {
                    "display_name": "",
                    "amount": None,
                    "unit": "",
                    "nutrient_code": "",
                }
            ],
            "intake_method": {"text": "", "structured": {"frequency": "", "time_of_day": []}},
            "precautions": [{"text": ""}],
            "allergen_warnings": [{"text": ""}],
            "functional_claims": [{"text": ""}],
            "label_sections": [{"section_type": ""}],
        },
        "allowed_label_sections": [
            "product_identity",
            "supplement_facts",
            "ingredient_amounts",
            "intake_method",
            "precautions",
            "allergen_warning",
        ],
        "review_instructions": ["fill_product_name_and_manufacturer_if_visible"],
        "ready_for_benchmark_after_review": False,
        "db_write_performed": False,
        "ocr_provider_call_performed": False,
        "paddleocr_training_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "image_materialization_policy": "private_hashed_fixture_copy_materialized",
    }
    if image_path is not None:
        row["image_path"] = image_path
    return row


def test_build_bundle_writes_html_gt_template_and_copies_images(tmp_path: Path) -> None:
    """Verify reviewable template rows become local HTML and editable JSONL."""
    template_dir = tmp_path / "template"
    image_path = template_dir / "images" / "review-ocr-gt-001.jpg"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"local-review-image")
    template_path = template_dir / "gt-template.jsonl"
    output_dir = tmp_path / "bundle"
    _write_jsonl(template_path, [_template_row()])

    summary = review_bundle.build_review_bundle(
        template_path=template_path,
        output_dir=output_dir,
        source_run_id="gt-bundle-test",
    )

    assert summary["schema_version"] == review_bundle.SCHEMA_VERSION
    assert summary["reviewable_row_count"] == 1
    assert summary["ground_truth_template_row_count"] == 1
    assert summary["manual_review_required_count"] == 1
    assert summary["ready_for_benchmark_rows"] == 0
    assert summary["image_copied_count"] == 1
    assert summary["ocr_provider_call_performed"] is False
    assert summary["paddleocr_training_performed"] is False
    assert (output_dir / "images" / "review-ocr-gt-001.jpg").read_bytes() == b"local-review-image"

    html_text = (output_dir / review_bundle.HTML_INDEX_NAME).read_text(encoding="utf-8")
    gt_rows = [
        json.loads(line)
        for line in (output_dir / review_bundle.GROUND_TRUTH_TEMPLATE_NAME)
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    assert 'src="images/review-ocr-gt-001.jpg"' in html_text
    assert str(tmp_path) not in html_text
    assert gt_rows[0]["fixture_id"] == "review-ocr-gt-001"
    assert gt_rows[0]["expected"]["verification_status"] == "pending_manual_review"
    assert gt_rows[0]["review_bundle_hint"]["set_ready_for_benchmark_after_review"] is True


def test_build_bundle_skips_rows_without_materialized_images(tmp_path: Path) -> None:
    """Verify rows without local images stay out of the operator bundle."""
    template_path = tmp_path / "template" / "gt-template.jsonl"
    _write_jsonl(
        template_path,
        [
            _template_row(fixture_id="missing-path", image_path=None),
            _template_row(fixture_id="missing-file", image_path="images/missing.jpg"),
        ],
    )

    summary = review_bundle.build_review_bundle(
        template_path=template_path,
        output_dir=tmp_path / "bundle",
    )

    assert summary["reviewable_row_count"] == 0
    assert summary["ground_truth_template_row_count"] == 0
    assert summary["skip_reason_counts"] == {
        "materialized_image_file_not_found": 1,
        "missing_materialized_image_path": 1,
    }
    assert (tmp_path / "bundle" / review_bundle.GROUND_TRUTH_TEMPLATE_NAME).read_text(
        encoding="utf-8"
    ) == ""


def test_build_bundle_rejects_non_pii_cleared_rows(tmp_path: Path) -> None:
    """Verify rows must be PII-cleared before manual OCR ground-truth review."""
    template_path = tmp_path / "template" / "gt-template.jsonl"
    _write_jsonl(template_path, [_template_row(contains_personal_data=True)])

    with pytest.raises(ValueError, match="PII-cleared"):
        review_bundle.build_review_bundle(
            template_path=template_path,
            output_dir=tmp_path / "bundle",
        )


def test_build_bundle_rejects_teacher_ocr_blocked_rows(tmp_path: Path) -> None:
    """Verify teacher-OCR blocked rows cannot enter manual benchmark review."""
    template_path = tmp_path / "template" / "gt-template.jsonl"
    _write_jsonl(template_path, [_template_row(teacher_ocr_allowed=False)])

    with pytest.raises(ValueError, match="teacher-OCR eligible"):
        review_bundle.build_review_bundle(
            template_path=template_path,
            output_dir=tmp_path / "bundle",
        )


def test_build_bundle_rejects_absolute_image_paths(tmp_path: Path) -> None:
    """Verify local absolute paths cannot enter the generated HTML or JSONL."""
    template_path = tmp_path / "template" / "gt-template.jsonl"
    _write_jsonl(template_path, [_template_row(image_path="/private/tmp/review.jpg")])

    with pytest.raises(ValueError, match=r"local path|relative image paths"):
        review_bundle.build_review_bundle(
            template_path=template_path,
            output_dir=tmp_path / "bundle",
        )


def test_cli_writes_redacted_summary(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI output omits local paths and raw fields."""
    template_dir = tmp_path / "template"
    image_path = template_dir / "images" / "review-ocr-gt-001.jpg"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"local-review-image")
    template_path = template_dir / "gt-template.jsonl"
    output_dir = tmp_path / "bundle"
    _write_jsonl(template_path, [_template_row()])

    review_bundle.main(
        [
            "--template",
            str(template_path),
            "--output-dir",
            str(output_dir),
            "--source-run-id",
            "gt-cli-test",
        ]
    )

    printed = capsys.readouterr().out
    printed_summary = json.loads(printed)
    saved_summary = json.loads(
        (output_dir / review_bundle.SUMMARY_NAME).read_text(encoding="utf-8")
    )

    assert printed_summary["source_run_id"] == "gt-cli-test"
    assert saved_summary["reviewable_row_count"] == 1
    assert str(tmp_path) not in printed
    assert str(tmp_path) not in json.dumps(saved_summary, ensure_ascii=False)
