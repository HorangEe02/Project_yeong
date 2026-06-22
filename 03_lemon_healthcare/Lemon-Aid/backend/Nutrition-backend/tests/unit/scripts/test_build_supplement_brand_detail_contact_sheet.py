"""Tests for supplement brand detail-page contact-sheet generation."""

from __future__ import annotations

import csv
import importlib
import json
import sys
from pathlib import Path
from typing import Any

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

contact_sheet = importlib.import_module("scripts.build_supplement_brand_detail_contact_sheet")


def _write_review_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write brand/product review CSV rows.

    Args:
        path: Destination path.
        rows: CSV rows.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "fixture_id",
        "category_key",
        "category_display_name",
        "brand_candidate_display_name",
        "brand_candidate_key",
        "source_product_id",
        "image_count",
        "detail_page_count",
        "review_count",
        "decision",
        "reviewed_manufacturer",
        "reviewed_product_name",
        "reason_codes",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _review_row(
    *,
    fixture_id: str = "brand_fixture_001",
    category_key: str = "bcaa_eaa",
    source_product_id: str = "10356752201",
    detail_page_count: int = 2,
) -> dict[str, Any]:
    """Return a minimal existing operator CSV review row.

    Args:
        fixture_id: Review fixture id.
        category_key: Category key.
        source_product_id: Source product id.
        detail_page_count: Detail-page image count.

    Returns:
        CSV row.
    """
    return {
        "fixture_id": fixture_id,
        "category_key": category_key,
        "category_display_name": "BCAA_EAA",
        "brand_candidate_display_name": "나우푸드",
        "brand_candidate_key": "나우푸드",
        "source_product_id": source_product_id,
        "image_count": "3",
        "detail_page_count": str(detail_page_count),
        "review_count": "1",
        "decision": "",
        "reviewed_manufacturer": "",
        "reviewed_product_name": "",
        "reason_codes": "",
    }


def _write_image(path: Path) -> None:
    """Write a small JPEG test image.

    Args:
        path: Destination path.
    """
    image_module = pytest.importorskip("PIL.Image")
    path.parent.mkdir(parents=True, exist_ok=True)
    image = image_module.new("RGB", (60, 40), color=(255, 240, 120))
    image.save(path, format="JPEG")


def test_build_contact_sheet_materializes_redacted_thumbnails(tmp_path: Path) -> None:
    """Verify source detail pages become thumbnails without leaking source paths."""
    root = tmp_path / "crawling-image"
    product_dir = root / "[BCAA_EAA]" / "나우푸드 테스트 제품_10356752201"
    _write_image(product_dir / "상세페이지" / "detail-a.jpg")
    _write_image(product_dir / "상세페이지" / "detail-b.jpg")
    _write_image(product_dir / "리뷰" / "review-a.jpg")
    review_csv = tmp_path / "operator" / "brand_product_review-001.review.csv"
    output_dir = tmp_path / "contact"
    _write_review_csv(review_csv, [_review_row()])

    summary = contact_sheet.build_detail_contact_sheet(
        root=root,
        review_csv=review_csv,
        output_dir=output_dir,
        source_run_id="detail-contact-test",
        max_images_per_row=2,
    )

    assert summary["schema_version"] == contact_sheet.SCHEMA_VERSION
    assert summary["reviewable_row_count"] == 1
    assert summary["rows_with_thumbnails"] == 1
    assert summary["thumbnail_count"] == 2
    assert summary["db_write_performed"] is False
    assert summary["ocr_provider_call_performed"] is False
    assert summary["source_image_read_performed"] is True
    assert summary["full_size_source_images_copied"] is False
    assert summary["contact_rows"][0]["source_detail_page_image_count"] == 2
    assert summary["contact_rows"][0]["matched_product_count"] == 1
    assert summary["contact_rows"][0]["contact_sheet_anchor"] == "row-001"
    assert summary["contact_rows"][0]["operator_decision_required"] is True
    assert summary["contact_rows"][0]["db_write_allowed"] is False

    html_text = (output_dir / contact_sheet.HTML_INDEX_NAME).read_text(encoding="utf-8")
    saved_summary = json.loads(
        (output_dir / contact_sheet.SUMMARY_NAME).read_text(encoding="utf-8")
    )
    thumbnail_names = summary["contact_rows"][0]["thumbnail_filenames"]

    assert len(thumbnail_names) == 2
    for thumbnail_name in thumbnail_names:
        assert (output_dir / thumbnail_name).is_file()
        assert f'src="{thumbnail_name}"' in html_text
    assert 'id="row-001"' in html_text
    assert "brand-detail-contact-sheet.html#row-001" in (
        output_dir / contact_sheet.README_NAME
    ).read_text(encoding="utf-8")
    assert saved_summary["source_run_id"] == "detail-contact-test"
    assert str(tmp_path) not in html_text
    assert str(tmp_path) not in json.dumps(saved_summary, ensure_ascii=False)
    assert "나우푸드 테스트 제품_10356752201" not in html_text
    assert "나우푸드 테스트 제품_10356752201" not in json.dumps(
        saved_summary,
        ensure_ascii=False,
    )
    assert "상세페이지" not in html_text
    assert "리뷰" not in html_text


def test_build_contact_sheet_reports_unmatched_rows_without_paths(tmp_path: Path) -> None:
    """Verify missing products are reported as redacted unresolved counts."""
    root = tmp_path / "crawling-image"
    (root / "[BCAA_EAA]").mkdir(parents=True)
    review_csv = tmp_path / "operator" / "brand_product_review-001.review.csv"
    output_dir = tmp_path / "contact"
    _write_review_csv(review_csv, [_review_row(source_product_id="000000")])

    summary = contact_sheet.build_detail_contact_sheet(
        root=root,
        review_csv=review_csv,
        output_dir=output_dir,
    )

    assert summary["rows_with_thumbnails"] == 0
    assert summary["rows_without_thumbnails"] == 1
    assert summary["thumbnail_count"] == 0
    assert summary["unresolved_reason_counts"] == {"product_not_found": 1}
    assert str(tmp_path) not in json.dumps(summary, ensure_ascii=False)


def test_build_contact_sheet_rejects_unsafe_csv_values(tmp_path: Path) -> None:
    """Verify review CSV values cannot carry local path literals."""
    root = tmp_path / "crawling-image"
    (root / "[BCAA_EAA]").mkdir(parents=True)
    review_csv = tmp_path / "operator" / "brand_product_review-001.review.csv"
    _write_review_csv(
        review_csv,
        [
            {
                **_review_row(),
                "brand_candidate_display_name": "/Volumes/private-brand",
            }
        ],
    )

    with pytest.raises(ValueError, match="local path"):
        contact_sheet.build_detail_contact_sheet(
            root=root,
            review_csv=review_csv,
            output_dir=tmp_path / "contact",
        )


def test_cli_prints_redacted_summary(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Verify CLI output contains counts but no local source path."""
    root = tmp_path / "crawling-image"
    product_dir = root / "[BCAA_EAA]" / "나우푸드 테스트 제품_10356752201"
    _write_image(product_dir / "상세페이지" / "detail-a.jpg")
    review_csv = tmp_path / "operator" / "brand_product_review-001.review.csv"
    output_dir = tmp_path / "contact"
    _write_review_csv(review_csv, [_review_row(detail_page_count=1)])

    contact_sheet.main(
        [
            "--root",
            str(root),
            "--review-csv",
            str(review_csv),
            "--output-dir",
            str(output_dir),
            "--source-run-id",
            "detail-contact-cli-test",
        ]
    )

    printed = capsys.readouterr().out
    printed_summary = json.loads(printed)

    assert printed_summary["thumbnail_count"] == 1
    assert printed_summary["source_run_id"] == "detail-contact-cli-test"
    assert str(tmp_path) not in printed
