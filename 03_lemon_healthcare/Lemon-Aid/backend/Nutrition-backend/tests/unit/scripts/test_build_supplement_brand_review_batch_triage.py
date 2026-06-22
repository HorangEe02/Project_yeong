"""Tests for supplement brand review batch triage summaries."""

from __future__ import annotations

import csv
import importlib
import json
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

triage = importlib.import_module("scripts.build_supplement_brand_review_batch_triage")


def _write_csv(path: Path, rows: list[dict[str, str]]) -> Path:
    """Write brand review CSV fixture rows.

    Args:
        path: Destination CSV path.
        rows: CSV rows.

    Returns:
        Written path.
    """
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return path


def _csv_row(
    fixture_id: str,
    *,
    decision: str = "",
    reviewed_manufacturer: str = "",
    reviewed_product_name: str = "",
    reason_codes: str = "",
    category_key: str = "vitamin",
    brand_candidate_key: str = "candidate_a",
    review_count: str = "1",
    detail_page_count: str = "1",
    image_count: str = "2",
    brand_candidate_display_name: str = "Visible Brand",
    source_product_id: str = "visible_product",
) -> dict[str, str]:
    """Return one operator-local CSV row.

    Args:
        fixture_id: Fixture id.
        decision: Review decision.
        reviewed_manufacturer: Reviewed manufacturer text.
        reviewed_product_name: Reviewed product text.
        reason_codes: Delimited reason code text.
        category_key: Category token.
        brand_candidate_key: Candidate brand token.
        review_count: Review image count.
        detail_page_count: Detail-page image count.
        image_count: Total image count.
        brand_candidate_display_name: Candidate display text.
        source_product_id: Source product token.

    Returns:
        CSV row.
    """
    return {
        "fixture_id": fixture_id,
        "category_key": category_key,
        "brand_candidate_display_name": brand_candidate_display_name,
        "brand_candidate_key": brand_candidate_key,
        "source_product_id": source_product_id,
        "image_count": image_count,
        "detail_page_count": detail_page_count,
        "review_count": review_count,
        "decision": decision,
        "reviewed_manufacturer": reviewed_manufacturer,
        "reviewed_product_name": reviewed_product_name,
        "reason_codes": reason_codes,
    }


def test_build_brand_review_batch_triage_reports_priorities_without_text_leak(
    tmp_path: Path,
) -> None:
    """Verify triage ranks blank rows while redacting operator product text."""
    product_text = "Reviewed Product Name"
    csv_path = _write_csv(
        tmp_path / "brand_product_review-001.review.csv",
        [
            _csv_row("brand_review_1", reviewed_product_name=product_text),
            _csv_row("brand_review_2", review_count="0", detail_page_count="0", image_count="0"),
            _csv_row("brand_review_3"),
            _csv_row(
                "brand_review_4",
                decision="approve",
                reviewed_manufacturer="Reviewed Maker",
                reviewed_product_name="Approved Product",
                reason_codes="reviewed_label_or_catalog",
            ),
        ],
    )

    summary = triage.build_brand_review_batch_triage(
        input_paths={"batch_review_csv": csv_path},
        max_row_hints=10,
    )
    markdown = triage.build_markdown(summary)
    public_dump = json.dumps({"summary": summary, "markdown": markdown}, ensure_ascii=False)

    assert summary["row_count"] == 4
    assert summary["blank_decision_row_count"] == 3
    assert summary["partial_review_without_decision_count"] == 1
    assert summary["reviewed_row_count"] == 1
    assert summary["priority_counts"]["p0_partial_review_fix"] == 1
    assert summary["priority_counts"]["p1_evidence_check"] == 1
    assert summary["priority_counts"]["p2_duplicate_candidate_review"] == 1
    assert summary["priority_counts"]["p4_reviewed"] == 1
    assert summary["row_hints"][0]["row_index"] == 1
    assert summary["row_hints"][0]["contact_sheet_anchor"] == "row-001"
    assert summary["row_hints"][0]["priority"] == "p0_partial_review_fix"
    assert "#row-001" in markdown
    assert summary["input_path_hashes"]["batch_review_csv"].startswith("fp-")
    assert len(summary["input_path_hashes"]["batch_review_csv"]) == 15
    assert summary["db_write_performed"] is False
    assert summary["automatic_decision_performed"] is False
    assert product_text not in public_dump
    assert "Visible Brand" not in public_dump
    assert "Reviewed Maker" not in public_dump
    assert str(tmp_path) not in public_dump


def test_build_brand_review_batch_triage_rejects_unsafe_raw_column(tmp_path: Path) -> None:
    """Verify raw/provider columns cannot enter the triage input."""
    csv_path = _write_csv(
        tmp_path / "unsafe.review.csv",
        [
            {
                **_csv_row("brand_review_1"),
                "raw_ocr_text": "unsafe",
            }
        ],
    )

    with pytest.raises(triage.BrandReviewBatchTriageError, match="Unsafe raw/provider"):
        triage.build_brand_review_batch_triage(input_paths={"batch_review_csv": csv_path})


def test_build_brand_review_batch_triage_flags_descriptor_like_candidates(
    tmp_path: Path,
) -> None:
    """Verify descriptor-like brand candidates are prioritized without leaking text."""
    descriptor_candidate = "수용성"
    csv_path = _write_csv(
        tmp_path / "descriptor.review.csv",
        [
            _csv_row(
                "brand_review_1",
                brand_candidate_key=descriptor_candidate,
                brand_candidate_display_name=descriptor_candidate,
            ),
            _csv_row("brand_review_2", brand_candidate_key="candidate_b"),
        ],
    )

    summary = triage.build_brand_review_batch_triage(
        input_paths={"batch_review_csv": csv_path},
        max_row_hints=10,
    )
    markdown = triage.build_markdown(summary)
    public_dump = json.dumps({"summary": summary, "markdown": markdown}, ensure_ascii=False)

    assert summary["priority_counts"]["p1_candidate_quality_check"] == 1
    assert summary["reason_counts"]["descriptor_like_brand_candidate"] == 1
    assert summary["row_hints"][0]["priority"] == "p1_candidate_quality_check"
    assert "descriptor_like_brand_candidate" in summary["row_hints"][0]["reason_codes"]
    assert (
        "review_descriptor_like_brand_candidates_as_not_a_brand_or_needs_review"
        in summary["operator_next_steps"]
    )
    assert descriptor_candidate not in public_dump


def test_build_brand_review_batch_triage_rejects_local_path_values(tmp_path: Path) -> None:
    """Verify local paths cannot be copied into operator CSV cells."""
    csv_path = _write_csv(
        tmp_path / "path.review.csv",
        [
            _csv_row(
                "brand_review_1",
                reviewed_product_name="/Volumes/Corsair EX400U Media/private.png",
            )
        ],
    )

    with pytest.raises(triage.BrandReviewBatchTriageError, match="local path"):
        triage.build_brand_review_batch_triage(input_paths={"batch_review_csv": csv_path})


def test_build_brand_review_batch_triage_limits_row_hints(tmp_path: Path) -> None:
    """Verify row hints can be bounded for compact operator reports."""
    csv_path = _write_csv(
        tmp_path / "brand_product_review-001.review.csv",
        [_csv_row(f"brand_review_{index}") for index in range(1, 4)],
    )

    summary = triage.build_brand_review_batch_triage(
        input_paths={"batch_review_csv": csv_path},
        max_row_hints=2,
    )

    assert len(summary["row_hints"]) == 2
    assert summary["row_hints_truncated"] is True
