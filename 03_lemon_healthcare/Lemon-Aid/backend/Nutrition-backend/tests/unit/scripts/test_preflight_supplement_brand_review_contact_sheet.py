"""Tests for brand review CSV/contact sheet preflight."""

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

preflight = importlib.import_module("scripts.preflight_supplement_brand_review_contact_sheet")


def _write_csv(path: Path, fixture_ids: list[str]) -> Path:
    """Write a brand review CSV fixture.

    Args:
        path: Destination path.
        fixture_ids: Fixture ids to write in row order.

    Returns:
        Written path.
    """
    fieldnames = [
        "fixture_id",
        "category_key",
        "brand_candidate_display_name",
        "brand_candidate_key",
        "source_product_id",
        "decision",
        "reviewed_manufacturer",
        "reviewed_product_name",
        "reason_codes",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for index, fixture_id in enumerate(fixture_ids, start=1):
            writer.writerow(
                {
                    "fixture_id": fixture_id,
                    "category_key": "vitamin",
                    "brand_candidate_display_name": f"Visible Brand {index}",
                    "brand_candidate_key": f"candidate_{index}",
                    "source_product_id": f"source_product_{index}",
                    "decision": "",
                    "reviewed_manufacturer": "",
                    "reviewed_product_name": "",
                    "reason_codes": "",
                }
            )
    return path


def _write_contact_summary(
    path: Path,
    *,
    review_csv_name: str,
    fixture_ids: list[str],
    thumbnail_counts: list[int] | None = None,
    row_index_offset: int = 0,
) -> Path:
    """Write a redaction-sensitive contact sheet summary fixture.

    Args:
        path: Destination path.
        review_csv_name: Expected review CSV name.
        fixture_ids: Fixture ids to include in contact row order.
        thumbnail_counts: Per-row thumbnail counts.
        row_index_offset: Offset added to row_index for mismatch tests.

    Returns:
        Written path.
    """
    counts = thumbnail_counts or [1 for _ in fixture_ids]
    rows = [
        {
            "auto_decision_performed": False,
            "brand_candidate_display_name": f"Visible Brand {index}",
            "category_display_name": "Vitamin",
            "category_key": "vitamin",
            "db_write_allowed": False,
            "fixture_id": fixture_id,
            "operator_decision_required": True,
            "row_index": index + row_index_offset,
            "source_product_id": f"source_product_{index}",
            "thumbnail_count": thumbnail_count,
            "thumbnail_filenames": [f"{fixture_id}-detail-01.jpg"] if thumbnail_count else [],
        }
        for index, (fixture_id, thumbnail_count) in enumerate(
            zip(fixture_ids, counts, strict=True),
            start=1,
        )
    ]
    payload: dict[str, Any] = {
        "schema_version": preflight.CONTACT_SHEET_SCHEMA,
        "review_csv_name": review_csv_name,
        "reviewable_row_count": len(fixture_ids),
        "rows_with_thumbnails": sum(1 for count in counts if count > 0),
        "rows_without_thumbnails": sum(1 for count in counts if count == 0),
        "thumbnail_count": sum(counts),
        "contact_rows": rows,
        "auto_decision_performed": False,
        "db_import_allowed": False,
        "db_write_performed": False,
        "external_provider_call_performed": False,
        "full_size_source_images_copied": False,
        "llm_call_performed": False,
        "ocr_provider_call_performed": False,
        "paddleocr_training_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "source_image_read_performed": True,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_brand_review_contact_sheet_preflight_passes_without_text_leak(
    tmp_path: Path,
) -> None:
    """Verify matching CSV/contact sheet rows pass without leaking row text."""
    csv_path = _write_csv(tmp_path / "brand_product_review-001.review.csv", ["brand_a", "brand_b"])
    summary_path = _write_contact_summary(
        tmp_path / "brand-detail-contact-sheet.summary.json",
        review_csv_name=csv_path.name,
        fixture_ids=["brand_a", "brand_b"],
    )

    summary = preflight.preflight_brand_review_contact_sheet(
        input_paths={"batch_review_csv": csv_path, "contact_sheet_summary": summary_path},
        require_all_rows_with_thumbnails=True,
    )
    markdown = preflight.build_markdown(summary)
    public_dump = json.dumps({"summary": summary, "markdown": markdown}, ensure_ascii=False)

    assert summary["status"] == "passed"
    assert summary["row_count"] == 2
    assert summary["contact_row_count"] == 2
    assert summary["issue_counts"] == {}
    assert summary["row_hints"] == []
    assert summary["db_write_performed"] is False
    assert "Visible Brand" not in public_dump
    assert "source_product_1" not in public_dump
    assert "brand_a" not in public_dump
    assert str(tmp_path) not in public_dump


def test_brand_review_contact_sheet_preflight_reports_csv_name_mismatch(
    tmp_path: Path,
) -> None:
    """Verify stale contact sheets fail when their CSV name differs."""
    csv_path = _write_csv(tmp_path / "brand_product_review-001.review.csv", ["brand_a"])
    summary_path = _write_contact_summary(
        tmp_path / "brand-detail-contact-sheet.summary.json",
        review_csv_name="other.review.csv",
        fixture_ids=["brand_a"],
    )

    summary = preflight.preflight_brand_review_contact_sheet(
        input_paths={"batch_review_csv": csv_path, "contact_sheet_summary": summary_path},
    )

    assert summary["status"] == "failed"
    assert summary["issue_counts"]["review_csv_name_mismatch"] == 1


def test_brand_review_contact_sheet_preflight_reports_order_mismatch(
    tmp_path: Path,
) -> None:
    """Verify fixture order mismatch is exposed only as row-index hints."""
    csv_path = _write_csv(tmp_path / "brand_product_review-001.review.csv", ["brand_a", "brand_b"])
    summary_path = _write_contact_summary(
        tmp_path / "brand-detail-contact-sheet.summary.json",
        review_csv_name=csv_path.name,
        fixture_ids=["brand_b", "brand_a"],
    )

    summary = preflight.preflight_brand_review_contact_sheet(
        input_paths={"batch_review_csv": csv_path, "contact_sheet_summary": summary_path},
    )

    assert summary["status"] == "failed"
    assert summary["issue_counts"]["fixture_order_mismatch"] == 2
    assert summary["row_hints"][0] == {
        "row_index": 1,
        "issue_codes": ["fixture_order_mismatch"],
    }


def test_brand_review_contact_sheet_preflight_requires_thumbnails(
    tmp_path: Path,
) -> None:
    """Verify zero-thumbnail rows can fail preflight."""
    csv_path = _write_csv(tmp_path / "brand_product_review-001.review.csv", ["brand_a", "brand_b"])
    summary_path = _write_contact_summary(
        tmp_path / "brand-detail-contact-sheet.summary.json",
        review_csv_name=csv_path.name,
        fixture_ids=["brand_a", "brand_b"],
        thumbnail_counts=[1, 0],
    )

    summary = preflight.preflight_brand_review_contact_sheet(
        input_paths={"batch_review_csv": csv_path, "contact_sheet_summary": summary_path},
        require_all_rows_with_thumbnails=True,
    )

    assert summary["status"] == "failed"
    assert summary["issue_counts"]["required_thumbnail_missing"] == 1
    assert summary["row_hints"] == [{"row_index": 2, "issue_codes": ["row_without_thumbnail"]}]


def test_brand_review_contact_sheet_preflight_rejects_unsafe_csv_values(
    tmp_path: Path,
) -> None:
    """Verify local paths cannot enter contact sheet preflight inputs."""
    csv_path = _write_csv(tmp_path / "brand_product_review-001.review.csv", ["brand_a"])
    text = csv_path.read_text(encoding="utf-8")
    csv_path.write_text(
        text.replace("source_product_1", "/Volumes/Corsair EX400U Media/private.png"),
        encoding="utf-8",
    )
    summary_path = _write_contact_summary(
        tmp_path / "brand-detail-contact-sheet.summary.json",
        review_csv_name=csv_path.name,
        fixture_ids=["brand_a"],
    )

    with pytest.raises(
        preflight.BrandReviewContactSheetPreflightError,
        match="Unsafe local path",
    ):
        preflight.preflight_brand_review_contact_sheet(
            input_paths={"batch_review_csv": csv_path, "contact_sheet_summary": summary_path},
        )
