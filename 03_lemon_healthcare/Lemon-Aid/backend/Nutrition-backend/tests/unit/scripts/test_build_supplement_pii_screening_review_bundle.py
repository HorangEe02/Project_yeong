"""Tests for supplement PII screening local review bundle generation."""

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

review_bundle = importlib.import_module("scripts.build_supplement_pii_screening_review_bundle")


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
) -> dict[str, Any]:
    """Return a minimal PII screening template row.

    Args:
        fixture_id: Fixture id.
        image_path: Optional relative materialized image path.

    Returns:
        Template row.
    """
    row: dict[str, Any] = {
        "schema_version": review_bundle.template_export.ROW_SCHEMA_VERSION,
        "source_run_id": "pii-template-test",
        "fixture_id": fixture_id,
        "image_ref_hash": "a" * 64,
        "image_sha256": "b" * 64,
        "image_size_bytes": 17,
        "image_mime_type": "image/jpeg",
        "category_key": "omega3",
        "source_kind": "review",
        "contains_personal_data": None,
        "pii_screening_status": "pending_local_screening",
        "external_transfer_allowed": False,
        "teacher_ocr_allowed": False,
        "local_processing_allowed": True,
        "operator_decision_required": True,
        "decision_stub": {
            "schema_version": review_bundle.template_export.decision_apply.DECISION_SCHEMA_VERSION,
            "fixture_id": fixture_id,
            "pii_screening_decision": {
                "decision": "",
                "reviewer_id": "",
                "reviewed_at": "",
                "reason_codes": [],
                "attest_local_screening_completed": False,
                "attest_no_personal_data_visible": False,
                "attest_no_raw_text_copied": False,
                "attest_teacher_ocr_transfer_allowed": False,
            },
        },
        "screening_instructions": ["inspect_local_image_only"],
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


def test_build_bundle_writes_html_decisions_and_copies_images(tmp_path: Path) -> None:
    """Verify the local bundle links and copies only relative image fixtures."""
    template_dir = tmp_path / "template"
    image_path = template_dir / "images" / "review-ocr-gt-001.jpg"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"local-review-image")
    template_path = template_dir / "pii-template.jsonl"
    _write_jsonl(template_path, [_template_row()])

    summary = review_bundle.build_review_bundle(
        template_path=template_path,
        output_dir=tmp_path / "bundle",
        source_run_id="bundle-test",
    )

    assert summary["schema_version"] == review_bundle.SCHEMA_VERSION
    assert summary["reviewable_row_count"] == 1
    assert summary["decision_template_row_count"] == 1
    assert summary["image_copied_count"] == 1
    assert summary["external_transfer_allowed_rows"] == 0
    assert summary["teacher_ocr_allowed_rows"] == 0
    assert (
        tmp_path / "bundle" / "images" / "review-ocr-gt-001.jpg"
    ).read_bytes() == b"local-review-image"
    html_text = (tmp_path / "bundle" / review_bundle.HTML_INDEX_NAME).read_text(encoding="utf-8")
    assert 'src="images/review-ocr-gt-001.jpg"' in html_text
    assert "Decision Guide" in html_text
    assert "cleared_no_personal_data" in html_text
    assert "Cleared Row Attestations" in html_text
    assert str(tmp_path) not in html_text
    decision_rows = [
        json.loads(line)
        for line in (tmp_path / "bundle" / review_bundle.DECISION_TEMPLATE_NAME)
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    assert decision_rows[0]["fixture_id"] == "review-ocr-gt-001"
    assert decision_rows[0]["pii_screening_decision"]["decision"] == ""
    assert "contains_personal_data" in decision_rows[0]["decision_guide"]
    assert "no_personal_data_visible" in decision_rows[0]["reason_code_guide"]
    assert (
        "attest_teacher_ocr_transfer_allowed" in decision_rows[0]["cleared_required_attestations"]
    )
    readme_text = (tmp_path / "bundle" / review_bundle.README_NAME).read_text(encoding="utf-8")
    assert "## Decision Guide" in readme_text
    assert "Rows with `decision=cleared_no_personal_data`" in readme_text


def test_build_bundle_skips_unmaterialized_or_missing_images(tmp_path: Path) -> None:
    """Verify rows without reviewable local image fixtures stay out of the bundle."""
    template_path = tmp_path / "template" / "pii-template.jsonl"
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
    assert summary["decision_template_row_count"] == 0
    assert summary["skip_reason_counts"] == {
        "materialized_image_file_not_found": 1,
        "missing_materialized_image_path": 1,
    }
    assert (tmp_path / "bundle" / review_bundle.DECISION_TEMPLATE_NAME).read_text(
        encoding="utf-8"
    ) == ""


def test_build_bundle_rejects_absolute_image_paths(tmp_path: Path) -> None:
    """Verify local absolute path literals cannot enter the review bundle."""
    template_path = tmp_path / "template" / "pii-template.jsonl"
    _write_jsonl(template_path, [_template_row(image_path="/private/tmp/review.jpg")])

    with pytest.raises(ValueError, match=r"local path literal|relative image paths"):
        review_bundle.build_review_bundle(
            template_path=template_path,
            output_dir=tmp_path / "bundle",
        )


def test_cli_writes_summary_without_path_leaks(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI output remains redacted."""
    template_dir = tmp_path / "template"
    image_path = template_dir / "images" / "review-ocr-gt-001.jpg"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"local-review-image")
    template_path = template_dir / "pii-template.jsonl"
    output_dir = tmp_path / "bundle"
    _write_jsonl(template_path, [_template_row()])

    review_bundle.main(
        [
            "--template",
            str(template_path),
            "--output-dir",
            str(output_dir),
            "--source-run-id",
            "bundle-cli",
        ]
    )

    printed = capsys.readouterr().out
    summary = json.loads((output_dir / review_bundle.SUMMARY_NAME).read_text(encoding="utf-8"))
    assert json.loads(printed)["source_run_id"] == "bundle-cli"
    assert summary["source_run_id"] == "bundle-cli"
    assert summary["db_write_performed"] is False
    assert str(tmp_path) not in printed
    assert str(tmp_path) not in json.dumps(summary, ensure_ascii=False)
