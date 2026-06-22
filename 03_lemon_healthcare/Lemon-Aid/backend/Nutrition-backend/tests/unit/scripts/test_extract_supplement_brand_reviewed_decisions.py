"""Tests for extracting reviewed supplement brand decisions."""

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

staging = importlib.import_module("scripts.build_supplement_taxonomy_db_staging")
template = importlib.import_module("scripts.export_supplement_brand_review_template")
extract = importlib.import_module("scripts.extract_supplement_brand_reviewed_decisions")


def _touch(path: Path) -> None:
    """Create a placeholder source image.

    Args:
        path: File path to create.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"placeholder")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write JSONL fixture rows.

    Args:
        path: Destination path.
        rows: JSON object rows.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _staging_manifest(tmp_path: Path) -> tuple[Path, list[dict[str, Any]]]:
    """Build and write a compact taxonomy staging fixture.

    Args:
        tmp_path: Temporary directory.

    Returns:
        Staging path and rows.
    """
    root = tmp_path / "crawling-image"
    _touch(root / "[오메가3]" / "나우푸드 오메가3_123456" / "리뷰" / "review.jpg")
    _touch(root / "[비타민C]" / "고려은단 비타민C_789012" / "상세페이지" / "detail.png")
    rows = staging.build_taxonomy_staging_rows(root=root, source_run_id="brand-extract-test")
    staging_path = tmp_path / "taxonomy.jsonl"
    _write_jsonl(staging_path, rows)
    return staging_path, rows


def _brand_fixture_ids(rows: list[dict[str, Any]]) -> list[str]:
    """Return brand candidate fixture ids.

    Args:
        rows: Taxonomy staging rows.

    Returns:
        Fixture ids.
    """
    return [
        template._fixture_id(str(row["product_dir_hash"]))
        for row in rows
        if row["row_type"] == staging.ROW_TYPE_BRAND_CANDIDATE
    ]


def _decision_row(
    fixture_id: str,
    *,
    decision: str = "approve",
    manufacturer: str = "NOW Foods",
    product_name: str = "Omega-3 Softgels",
    **overrides: Any,
) -> dict[str, Any]:
    """Return a reviewed brand decision row.

    Args:
        fixture_id: Brand fixture id.
        decision: Decision value.
        manufacturer: Reviewed manufacturer.
        product_name: Reviewed product name.
        overrides: Extra decision field overrides.

    Returns:
        Decision row.
    """
    payload: dict[str, Any] = {
        "decision": decision,
        "reviewer_id": "operator_taxonomy",
        "reviewed_at": "2026-06-04T12:00:00Z",
        "reviewed_manufacturer": manufacturer,
        "reviewed_product_name": product_name,
        "reason_codes": (
            ["reviewed_label_or_catalog"] if decision == "approve" else ["unclear_brand"]
        ),
        "attest_brand_product_review_completed": decision == "approve",
        "attest_not_using_product_folder_literal_as_manufacturer": decision == "approve",
        "attest_product_name_reviewed_from_label_or_safe_catalog": decision == "approve",
        "attest_no_raw_ocr_or_provider_payload_copied": decision == "approve",
        "attest_db_import_allowed": decision == "approve",
    }
    payload.update(overrides)
    return {
        "schema_version": extract.applier.DECISION_SCHEMA_VERSION,
        "fixture_id": fixture_id,
        "brand_review_decision": payload,
    }


def _blank_decision_row(fixture_id: str) -> dict[str, Any]:
    """Return an untouched brand decision stub.

    Args:
        fixture_id: Brand fixture id.

    Returns:
        Blank decision row.
    """
    return {
        "schema_version": extract.applier.DECISION_SCHEMA_VERSION,
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
    }


def test_extract_reviewed_brand_decisions_ignores_blank_stubs(tmp_path: Path) -> None:
    """Verify reviewed-only extraction can consume mixed queue files."""
    staging_path, rows = _staging_manifest(tmp_path)
    fixture_ids = _brand_fixture_ids(rows)
    decisions_path = tmp_path / "brand.queue.jsonl"
    _write_jsonl(
        decisions_path,
        [_decision_row(fixture_ids[0]), _blank_decision_row(fixture_ids[1])],
    )

    extracted_rows, summary = extract.extract_reviewed_brand_decisions(
        taxonomy_staging=staging_path,
        decisions_path=decisions_path,
    )

    assert len(extracted_rows) == 1
    assert extracted_rows[0]["fixture_id"] == fixture_ids[0]
    assert summary["input_decision_row_count"] == 2
    assert summary["reviewed_decision_count"] == 1
    assert summary["blank_decision_ignored_count"] == 1
    assert summary["decision_counts"] == {"approve": 1, "blank": 1}
    assert summary["ready_for_partial_apply"] is True
    assert summary["ready_for_strict_apply"] is False
    assert summary["taxonomy_staging_hash"].startswith("fp-")
    assert len(summary["taxonomy_staging_hash"]) == 15
    assert summary["decisions_hash"].startswith("fp-")
    assert len(summary["decisions_hash"]) == 15
    assert summary["db_write_performed"] is False


def test_extract_reviewed_brand_decisions_all_blank_is_controlled_noop(
    tmp_path: Path,
) -> None:
    """Verify all-blank queues create an empty reviewed-only file."""
    staging_path, rows = _staging_manifest(tmp_path)
    fixture_ids = _brand_fixture_ids(rows)
    decisions_path = tmp_path / "brand.queue.jsonl"
    _write_jsonl(decisions_path, [_blank_decision_row(fixture_id) for fixture_id in fixture_ids])

    extracted_rows, summary = extract.extract_reviewed_brand_decisions(
        taxonomy_staging=staging_path,
        decisions_path=decisions_path,
    )

    assert extracted_rows == []
    assert summary["reviewed_decision_count"] == 0
    assert summary["blank_decision_ignored_count"] == 2
    assert summary["ready_for_partial_apply"] is False
    assert summary["output_rows_written"] == 0


def test_extract_reviewed_brand_decisions_rejects_nonblank_invalid_row(
    tmp_path: Path,
) -> None:
    """Verify malformed reviewed rows fail closed instead of being ignored."""
    staging_path, rows = _staging_manifest(tmp_path)
    fixture_id = _brand_fixture_ids(rows)[0]
    decisions_path = tmp_path / "brand.queue.jsonl"
    invalid = _decision_row(fixture_id, attest_db_import_allowed=False)
    _write_jsonl(decisions_path, [invalid])

    with pytest.raises(ValueError, match="attest_db_import_allowed"):
        extract.extract_reviewed_brand_decisions(
            taxonomy_staging=staging_path,
            decisions_path=decisions_path,
        )


def test_extract_reviewed_brand_decisions_rejects_unmatched_row(tmp_path: Path) -> None:
    """Verify stale reviewed rows cannot be copied into partial apply input."""
    staging_path, _ = _staging_manifest(tmp_path)
    decisions_path = tmp_path / "brand.queue.jsonl"
    _write_jsonl(decisions_path, [_decision_row("brand_aaaaaaaaaaaaaaaaaaaaaaaa")])

    with pytest.raises(ValueError, match="not in taxonomy staging"):
        extract.extract_reviewed_brand_decisions(
            taxonomy_staging=staging_path,
            decisions_path=decisions_path,
        )


def test_extract_reviewed_brand_decisions_cli_writes_redacted_outputs(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI output stays aggregate-only and path-redacted."""
    staging_path, rows = _staging_manifest(tmp_path)
    fixture_ids = _brand_fixture_ids(rows)
    decisions_path = tmp_path / "brand.queue.jsonl"
    output_path = tmp_path / "out" / "reviewed.jsonl"
    _write_jsonl(
        decisions_path,
        [_decision_row(fixture_ids[0]), _blank_decision_row(fixture_ids[1])],
    )

    extract.main(
        [
            "--taxonomy-staging",
            str(staging_path),
            "--decisions",
            str(decisions_path),
            "--output",
            str(output_path),
        ]
    )

    printed = capsys.readouterr().out
    summary = json.loads(output_path.with_suffix(".jsonl.summary.json").read_text(encoding="utf-8"))
    assert output_path.exists()
    assert summary["reviewed_decision_count"] == 1
    assert str(tmp_path) not in printed
    assert str(tmp_path) not in json.dumps(summary, ensure_ascii=False)
    assert "나우푸드 오메가3_123456" not in printed
