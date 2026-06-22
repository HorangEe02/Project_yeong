"""Tests for supplement brand/product local review bundle generation."""

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

review_bundle = importlib.import_module("scripts.build_supplement_brand_review_bundle")


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
    fixture_id: str = "brand_fixture_001",
    approved_for_db_write: bool = False,
    brand_display_name: str = "나우푸드",
) -> dict[str, Any]:
    """Return a minimal brand review template row.

    Args:
        fixture_id: Review fixture id.
        approved_for_db_write: Whether the row is already approved.
        brand_display_name: Operator-facing brand candidate display name.

    Returns:
        Template row.
    """
    return {
        "schema_version": review_bundle.EXPECTED_TEMPLATE_ROW_SCHEMA_VERSION,
        "source_run_id": "brand-template-test",
        "fixture_id": fixture_id,
        "category_key": "bcaa_eaa",
        "category_display_name": "BCAA_EAA",
        "source_product_id": "10356752201",
        "brand_candidate": {
            "brand_key": "나우푸드",
            "display_name": brand_display_name,
            "verification_status": "requires_human_review",
            "needs_human_review": True,
        },
        "image_count": 503,
        "source_kind_counts": {
            "detail_page": 3,
            "review": 500,
        },
        "operator_decision_required": True,
        "approved_for_db_write": approved_for_db_write,
        "decision_stub": {
            "schema_version": "supplement-brand-review-decision-v1",
            "fixture_id": fixture_id,
            "brand_review_decision": {
                "decision": "",
                "reviewer_id": "",
                "reviewed_at": "",
                "reviewed_manufacturer": "",
                "reviewed_product_name": "",
                "reason_codes": [],
                "attest_brand_product_review_completed": False,
                "attest_not_using_product_folder_literal_as_manufacturer": False,
                "attest_product_name_reviewed_from_label_or_safe_catalog": False,
                "attest_no_raw_ocr_or_provider_payload_copied": False,
                "attest_db_import_allowed": False,
            },
        },
        "db_write_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
    }


def test_build_bundle_writes_html_csv_decisions_and_summary(tmp_path: Path) -> None:
    """Verify the bundle exports review aids without approving DB writes."""
    template_path = tmp_path / "template" / "brand-template.jsonl"
    output_dir = tmp_path / "bundle"
    _write_jsonl(template_path, [_template_row()])

    summary = review_bundle.build_review_bundle(
        template_path=template_path,
        output_dir=output_dir,
        source_run_id="brand-bundle-test",
    )

    assert summary["schema_version"] == review_bundle.SCHEMA_VERSION
    assert summary["reviewable_row_count"] == 1
    assert summary["decision_template_row_count"] == 1
    assert summary["operator_decision_required_count"] == 1
    assert summary["approved_for_db_write_rows"] == 0
    assert summary["db_write_performed"] is False
    assert summary["raw_ocr_text_stored"] is False
    assert (output_dir / review_bundle.HTML_INDEX_NAME).exists()
    assert (output_dir / review_bundle.CSV_NAME).exists()
    assert (output_dir / review_bundle.README_NAME).exists()
    assert (
        json.loads((output_dir / review_bundle.SUMMARY_NAME).read_text(encoding="utf-8"))[
            "source_run_id"
        ]
        == "brand-bundle-test"
    )

    csv_text = (output_dir / review_bundle.CSV_NAME).read_text(encoding="utf-8")
    html_text = (output_dir / review_bundle.HTML_INDEX_NAME).read_text(encoding="utf-8")
    decision_rows = [
        json.loads(line)
        for line in (output_dir / review_bundle.DECISION_TEMPLATE_NAME)
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]

    assert "brand_fixture_001" in csv_text
    assert "나우푸드" in html_text
    assert str(tmp_path) not in csv_text
    assert str(tmp_path) not in html_text
    assert decision_rows[0]["fixture_id"] == "brand_fixture_001"
    assert decision_rows[0]["brand_review_decision"]["decision"] == ""
    assert decision_rows[0]["brand_review_decision"]["attest_db_import_allowed"] is False


def test_build_bundle_rejects_duplicate_fixture_ids(tmp_path: Path) -> None:
    """Verify duplicate review rows cannot create ambiguous operator decisions."""
    template_path = tmp_path / "template" / "brand-template.jsonl"
    _write_jsonl(template_path, [_template_row(), _template_row()])

    with pytest.raises(ValueError, match="Duplicate supplement brand template fixture_id"):
        review_bundle.build_review_bundle(
            template_path=template_path,
            output_dir=tmp_path / "bundle",
        )


def test_build_bundle_rejects_preapproved_rows(tmp_path: Path) -> None:
    """Verify bundle generation cannot carry pre-approved DB rows."""
    template_path = tmp_path / "template" / "brand-template.jsonl"
    _write_jsonl(template_path, [_template_row(approved_for_db_write=True)])

    with pytest.raises(ValueError, match="pre-approved rows"):
        review_bundle.build_review_bundle(
            template_path=template_path,
            output_dir=tmp_path / "bundle",
        )


def test_build_bundle_rejects_path_or_url_literals(tmp_path: Path) -> None:
    """Verify unsafe local paths and URLs are rejected before export."""
    template_path = tmp_path / "template" / "brand-template.jsonl"
    _write_jsonl(template_path, [_template_row(brand_display_name="/Volumes/private-brand")])

    with pytest.raises(ValueError, match="local path"):
        review_bundle.build_review_bundle(
            template_path=template_path,
            output_dir=tmp_path / "bundle",
        )


def test_cli_writes_redacted_summary(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI output omits local paths while reporting safe counts."""
    template_path = tmp_path / "template" / "brand-template.jsonl"
    output_dir = tmp_path / "bundle"
    _write_jsonl(template_path, [_template_row()])

    review_bundle.main(
        [
            "--template",
            str(template_path),
            "--output-dir",
            str(output_dir),
            "--source-run-id",
            "brand-cli-test",
        ]
    )

    printed = capsys.readouterr().out
    printed_summary = json.loads(printed)
    saved_summary = json.loads(
        (output_dir / review_bundle.SUMMARY_NAME).read_text(encoding="utf-8")
    )

    assert printed_summary["source_run_id"] == "brand-cli-test"
    assert saved_summary["reviewable_row_count"] == 1
    assert str(tmp_path) not in printed
    assert str(tmp_path) not in json.dumps(saved_summary, ensure_ascii=False)
