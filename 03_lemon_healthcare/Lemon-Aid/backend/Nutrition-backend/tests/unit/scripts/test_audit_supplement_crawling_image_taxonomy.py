"""Tests for crawling-image taxonomy audit tooling."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

audit = importlib.import_module("scripts.audit_supplement_crawling_image_taxonomy")


def _touch(path: Path) -> None:
    """Create a placeholder file for suffix-only image scanning.

    Args:
        path: File path to create.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"placeholder")


def test_audit_summarizes_category_product_and_source_kind_counts(tmp_path: Path) -> None:
    """Verify category/product counts and review-required brand candidates."""
    root = tmp_path / "crawling-image"
    _touch(root / "[오메가3]" / "나우푸드 오메가3_123" / "리뷰" / "review.jpg")
    _touch(root / "[오메가3]" / "나우푸드 오메가3_123" / "상세페이지" / "detail.png")
    _touch(root / "[비타민C]" / "[특가] 고려은단 비타민C_999" / "상세페이지" / "detail.webp")
    _touch(root / "[비타민C]" / "[특가] 고려은단 비타민C_999" / ".DS_Store")

    summary = audit.audit_crawling_image_taxonomy(root=root, sample_products_per_category=2)

    assert summary["category_count"] == 2
    assert summary["product_count"] == 2
    assert summary["image_count"] == 3
    assert summary["product_layout_counts"] == {
        "with_detail_page_dir": 2,
        "with_review_and_detail_page_dirs": 1,
        "with_review_dir": 1,
        "with_single_expected_source_dir": 1,
        "without_review_dir": 1,
    }
    assert summary["source_kind_counts"] == {
        "detail_page": 2,
        "review": 1,
    }
    assert summary["brand_candidate_counts"] == {
        "고려은단": 1,
        "나우푸드": 1,
    }
    assert summary["db_seed_contract"]["requires_brand_review_before_db_write"] is True
    assert summary["ground_truth_contract"]["teacher_ocr_providers"] == [
        "clova",
        "google_vision",
    ]


def test_audit_output_redacts_local_paths_and_product_folder_literals(tmp_path: Path) -> None:
    """Verify operator output omits absolute paths and product directory names."""
    root = tmp_path / "crawling-image"
    product_literal = "나우푸드 오메가3_123"
    _touch(root / "[오메가3]" / product_literal / "리뷰" / "review.jpg")

    summary = audit.audit_crawling_image_taxonomy(root=root, sample_products_per_category=1)
    dumped = json.dumps(summary, ensure_ascii=False, sort_keys=True)

    assert str(tmp_path) not in dumped
    assert "/private/" not in dumped
    assert "/Volumes/" not in dumped
    assert product_literal not in dumped
    assert '"raw_ocr_text_stored": false' in dumped
    assert '"raw_provider_payload_stored": false' in dumped
    assert summary["absolute_paths_stored"] is False
    assert summary["product_dir_literals_stored"] is False


def test_audit_reports_structure_issues_for_unreviewable_product_folders(
    tmp_path: Path,
) -> None:
    """Verify issue counts catch missing source ids and expected subfolders."""
    root = tmp_path / "crawling-image"
    _touch(root / "[기타]" / "제품명" / "unknown.jpg")

    summary = audit.audit_crawling_image_taxonomy(root=root, sample_products_per_category=1)

    assert summary["issue_counts"] == {
        "missing_detail_page_dir": 1,
        "missing_review_dir": 1,
        "missing_trailing_product_id": 1,
        "unknown_source_kind_images": 1,
    }
    assert summary["product_layout_counts"] == {
        "with_no_expected_source_dirs": 1,
        "without_detail_page_dir": 1,
        "without_review_dir": 1,
    }
    assert "structure_issues_present" in summary["observations"]
    product_sample = summary["categories"][0]["product_samples"][0]
    assert product_sample["source_product_id"] is None
    assert product_sample["has_review_dir"] is False
    assert product_sample["has_detail_page_dir"] is False
    assert product_sample["brand_candidate"]["verification_status"] == "requires_human_review"


def test_failure_summary_redacts_requested_root(tmp_path: Path) -> None:
    """Verify failure payload does not disclose local root values."""
    root = tmp_path / "missing-crawling-image"
    failure = audit._failure_summary(
        error=ValueError(f"{root} is not a directory."),
        root=root,
    )
    dumped = json.dumps(failure, ensure_ascii=False, sort_keys=True)

    assert failure["ok"] is False
    assert failure["error_type"] == "ValueError"
    assert str(root) not in dumped
    assert "<redacted-root>" in dumped
    assert failure["absolute_paths_stored"] is False
