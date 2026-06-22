"""Tests for catalog-based supplement brand review CSV autofill."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from scripts import autofill_supplement_brand_review_csv as autofill


def test_autofill_approves_high_confidence_catalog_rows(tmp_path: Path) -> None:
    """Verify high-confidence catalog rows become approve decisions.

    Args:
        tmp_path: Pytest temporary directory.
    """
    root = tmp_path / "crawling-image"
    (root / "[VitaminC]" / "YDY Sample Vitamin_111111").mkdir(parents=True)
    brand_draft = tmp_path / "brand-draft.jsonl"
    brand_draft.write_text(
        json.dumps(
            {
                "source_product_id": "111111",
                "proposed_brand": "YDY",
                "needs_human_review": False,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    input_csv = _write_review_csv(
        tmp_path, [{"fixture_id": "brand_a", "source_product_id": "111111"}]
    )
    output_dir = tmp_path / "autofill"

    summary = autofill.autofill_brand_review_csvs(
        crawling_root=root,
        brand_draft=brand_draft,
        batch_review_csvs=[input_csv],
        output_dir=output_dir,
    )

    rows = _read_review_csv(output_dir / input_csv.name)
    assert summary["decision_counts"] == {"approve": 1}
    assert summary["reason_counts"] == {"reviewed_label_or_catalog": 1}
    assert rows[0]["decision"] == "approve"
    assert rows[0]["reviewed_manufacturer"] == "YDY"
    assert rows[0]["reviewed_product_name"] == "YDY Sample Vitamin"
    assert rows[0]["reason_codes"] == "reviewed_label_or_catalog"
    assert "YDY Sample Vitamin" not in json.dumps(summary, ensure_ascii=False)


def test_autofill_marks_low_confidence_rows_needs_review(tmp_path: Path) -> None:
    """Verify low-confidence rows stay out of approved DB import manifests.

    Args:
        tmp_path: Pytest temporary directory.
    """
    root = tmp_path / "crawling-image"
    (root / "[VitaminC]" / "Unknown Sample Vitamin_222222").mkdir(parents=True)
    brand_draft = tmp_path / "brand-draft.jsonl"
    brand_draft.write_text(
        json.dumps(
            {
                "source_product_id": "222222",
                "proposed_brand": "",
                "needs_human_review": True,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    input_csv = _write_review_csv(
        tmp_path, [{"fixture_id": "brand_b", "source_product_id": "222222"}]
    )

    summary = autofill.autofill_brand_review_csvs(
        crawling_root=root,
        brand_draft=brand_draft,
        batch_review_csvs=[input_csv],
        output_dir=tmp_path / "autofill",
    )

    rows = _read_review_csv(tmp_path / "autofill" / input_csv.name)
    assert summary["decision_counts"] == {"needs_review": 1}
    assert summary["reason_counts"] == {"unclear_brand": 1}
    assert rows[0]["decision"] == "needs_review"
    assert rows[0]["reviewed_manufacturer"] == ""
    assert rows[0]["reviewed_product_name"] == ""
    assert rows[0]["reason_codes"] == "unclear_brand"


def test_autofill_marks_duplicate_source_ids_needs_review(tmp_path: Path) -> None:
    """Verify duplicated source product ids are not auto-approved.

    Args:
        tmp_path: Pytest temporary directory.
    """
    root = tmp_path / "crawling-image"
    (root / "[VitaminC]" / "YDY Sample One_333333").mkdir(parents=True)
    (root / "[Omega3]" / "YDY Sample Two_333333").mkdir(parents=True)
    brand_draft = tmp_path / "brand-draft.jsonl"
    brand_draft.write_text(
        "\n".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True)
            for row in [
                {
                    "source_product_id": "333333",
                    "proposed_brand": "YDY",
                    "needs_human_review": False,
                },
                {
                    "source_product_id": "333333",
                    "proposed_brand": "YDY",
                    "needs_human_review": False,
                },
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    input_csv = _write_review_csv(
        tmp_path, [{"fixture_id": "brand_c", "source_product_id": "333333"}]
    )

    summary = autofill.autofill_brand_review_csvs(
        crawling_root=root,
        brand_draft=brand_draft,
        batch_review_csvs=[input_csv],
        output_dir=tmp_path / "autofill",
    )

    rows = _read_review_csv(tmp_path / "autofill" / input_csv.name)
    assert summary["decision_counts"] == {"needs_review": 1}
    assert summary["reason_counts"] == {"duplicate_product": 1}
    assert rows[0]["decision"] == "needs_review"
    assert rows[0]["reason_codes"] == "duplicate_product"


def _write_review_csv(tmp_path: Path, rows: list[dict[str, str]]) -> Path:
    """Write a review CSV fixture.

    Args:
        tmp_path: Pytest temporary directory.
        rows: Partial CSV rows.

    Returns:
        CSV path.
    """
    path = tmp_path / "brand_product_review-001.review.csv"
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
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            payload = dict.fromkeys(fieldnames, "")
            payload.update(row)
            writer.writerow(payload)
    return path


def _read_review_csv(path: Path) -> list[dict[str, str]]:
    """Read a review CSV fixture.

    Args:
        path: CSV path.

    Returns:
        CSV rows.
    """
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))
