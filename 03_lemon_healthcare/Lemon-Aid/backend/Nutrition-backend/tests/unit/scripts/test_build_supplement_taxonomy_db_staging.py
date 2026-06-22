"""Tests for crawling-image supplement taxonomy DB staging."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

staging = importlib.import_module("scripts.build_supplement_taxonomy_db_staging")


def _touch(path: Path) -> None:
    """Create a placeholder image-like file.

    Args:
        path: File path to create.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"placeholder")


def test_build_taxonomy_staging_rows_separates_seedable_categories_and_review_brands(
    tmp_path: Path,
) -> None:
    """Verify category rows are seedable while brand candidates are review-gated."""
    root = tmp_path / "crawling-image"
    _touch(root / "[오메가3]" / "나우푸드 오메가3_123456" / "리뷰" / "review.jpg")
    _touch(root / "[오메가3]" / "나우푸드 오메가3_123456" / "상세페이지" / "detail.png")
    _touch(root / "[비타민C]" / "[특가] 고려은단 비타민C_789012" / "상세페이지" / "detail.webp")

    rows = staging.build_taxonomy_staging_rows(root=root, source_run_id="taxonomy-test")

    category_rows = [row for row in rows if row["row_type"] == staging.ROW_TYPE_CATEGORY]
    brand_rows = [row for row in rows if row["row_type"] == staging.ROW_TYPE_BRAND_CANDIDATE]
    assert len(category_rows) == 2
    assert len(brand_rows) == 2
    assert {row["category_key"] for row in category_rows} == {"비타민c", "오메가3"}
    assert all(row["approved_for_db_write"] is True for row in category_rows)
    assert all(row["requires_human_review"] is False for row in category_rows)
    assert all(row["approved_for_db_write"] is False for row in brand_rows)
    assert all(row["requires_human_review"] is True for row in brand_rows)
    assert all(row["store_as_manufacturer_without_review"] is False for row in brand_rows)
    assert {row["brand_candidate"]["display_name"] for row in brand_rows} == {
        "고려은단",
        "나우푸드",
    }


def test_build_taxonomy_staging_rows_omits_product_literals_and_local_paths(
    tmp_path: Path,
) -> None:
    """Verify staging output does not expose product folder literals or paths."""
    root = tmp_path / "crawling-image"
    product_literal = "나우푸드 오메가3_123456"
    _touch(root / "[오메가3]" / product_literal / "리뷰" / "review.jpg")

    rows = staging.build_taxonomy_staging_rows(root=root)
    summary = staging.build_summary(rows=rows, root=root)
    dumped = json.dumps({"rows": rows, "summary": summary}, ensure_ascii=False)

    assert product_literal not in dumped
    assert str(tmp_path) not in dumped
    assert "/private/" not in dumped
    assert "/Volumes/" not in dumped
    assert '"raw_ocr_text":' not in dumped
    assert '"provider_payload":' not in dumped
    assert summary["product_dir_literals_stored"] is False
    assert summary["absolute_paths_stored"] is False


def test_build_summary_reports_review_contract_and_counts(tmp_path: Path) -> None:
    """Verify summary makes the DB write gate explicit."""
    root = tmp_path / "crawling-image"
    _touch(root / "[오메가3]" / "나우푸드 오메가3_123456" / "리뷰" / "review.jpg")
    _touch(root / "[오메가3]" / "나우푸드 오메가3_123456" / "상세페이지" / "detail.png")

    rows = staging.build_taxonomy_staging_rows(root=root)
    summary = staging.build_summary(rows=rows, root=root)

    assert summary["row_count"] == 2
    assert summary["category_seed_row_count"] == 1
    assert summary["brand_candidate_row_count"] == 1
    assert summary["review_required_row_count"] == 1
    assert summary["approved_for_db_write_row_count"] == 1
    assert summary["category_key_counts"] == {"오메가3": 1}
    assert summary["source_kind_counts"] == {"detail_page": 1, "review": 1}
    assert summary["db_write_contract"] == {
        "brand_candidate_rows_seedable_without_review": False,
        "category_rows_seedable": True,
        "requires_approved_brand_review_manifest": True,
    }


def test_reject_unsafe_payload_blocks_raw_keys() -> None:
    """Verify raw OCR/provider fields cannot be emitted."""
    with pytest.raises(ValueError, match="raw_ocr_text"):
        staging._reject_unsafe_payload({"raw_ocr_text": "do not emit"})


def test_main_writes_jsonl_and_redacted_summary(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI writes safe staging rows and summary files."""
    root = tmp_path / "crawling-image"
    _touch(root / "[오메가3]" / "나우푸드 오메가3_123456" / "리뷰" / "review.jpg")
    output_path = tmp_path / "out" / "taxonomy.jsonl"

    staging.main(["--root", str(root), "--output", str(output_path)])

    stdout = capsys.readouterr().out
    summary = json.loads(stdout)
    assert summary["row_count"] == 2
    assert output_path.exists()
    assert output_path.with_suffix(".jsonl.summary.json").exists()
    dumped = output_path.read_text(encoding="utf-8")
    assert "나우푸드 오메가3_123456" not in dumped
    assert str(tmp_path) not in stdout
    assert "/private/" not in stdout
