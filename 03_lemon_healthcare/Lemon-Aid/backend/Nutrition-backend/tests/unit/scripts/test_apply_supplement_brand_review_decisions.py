"""Tests for applying supplement brand review decisions."""

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
template = importlib.import_module("scripts.export_supplement_brand_review_template")
apply = importlib.import_module("scripts.apply_supplement_brand_review_decisions")


def _touch(path: Path) -> None:
    """Create a placeholder image-like file.

    Args:
        path: File path to create.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"placeholder")


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    """Write JSON object rows as JSONL.

    Args:
        path: Destination path.
        rows: JSON object rows.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _staging_manifest(tmp_path: Path) -> tuple[Path, list[dict[str, object]]]:
    """Build and write test taxonomy staging rows.

    Args:
        tmp_path: Pytest temporary directory.

    Returns:
        Staging path and rows.
    """
    root = tmp_path / "crawling-image"
    _touch(root / "[오메가3]" / "나우푸드 오메가3_123456" / "리뷰" / "review.jpg")
    _touch(root / "[비타민C]" / "고려은단 비타민C_789012" / "상세페이지" / "detail.png")
    rows = staging.build_taxonomy_staging_rows(root=root, source_run_id="brand-apply-test")
    staging_path = tmp_path / "taxonomy.jsonl"
    _write_jsonl(staging_path, rows)
    return staging_path, rows


def _decision(
    fixture_id: str,
    *,
    decision: str = "approve",
    manufacturer: str = "NOW Foods",
    product_name: str = "Omega-3 Softgels",
) -> dict[str, object]:
    """Return an operator decision row.

    Args:
        fixture_id: Review fixture id.
        decision: Decision value.
        manufacturer: Reviewed manufacturer.
        product_name: Reviewed product name.

    Returns:
        JSON-safe decision row.
    """
    return {
        "schema_version": apply.DECISION_SCHEMA_VERSION,
        "fixture_id": fixture_id,
        "brand_review_decision": {
            "decision": decision,
            "reviewer_id": "operator_taxonomy",
            "reviewed_at": "2026-06-03T12:00:00Z",
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
        },
    }


def _first_brand_fixture_id(rows: list[dict[str, object]]) -> str:
    """Return the first brand candidate fixture id.

    Args:
        rows: Taxonomy staging rows.

    Returns:
        Fixture id.
    """
    brand_row = next(row for row in rows if row["row_type"] == staging.ROW_TYPE_BRAND_CANDIDATE)
    return template._fixture_id(str(brand_row["product_dir_hash"]))


def test_apply_brand_review_decisions_emits_approved_product_import_row(
    tmp_path: Path,
) -> None:
    """Verify approved decisions become safe supplement product import rows."""
    staging_path, staging_rows = _staging_manifest(tmp_path)
    fixture_id = _first_brand_fixture_id(staging_rows)
    decisions_path = tmp_path / "decisions.jsonl"
    _write_jsonl(decisions_path, [_decision(fixture_id)])

    rows, summary = apply.apply_brand_review_decisions(
        taxonomy_staging=staging_path,
        decisions_path=decisions_path,
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["schema_version"] == apply.OUTPUT_ROW_SCHEMA_VERSION
    assert row["row_type"] == "supplement_product_import"
    assert row["db_target_table"] == "supplement_products"
    assert row["source_provider"] == "crawling_image"
    assert row["manufacturer"] == "NOW Foods"
    assert row["product_name"] == "Omega-3 Softgels"
    assert row["normalized_product_name"] == "omega-3 softgels"
    assert row["category_mapping"]["db_target_table"] == "supplement_product_categories"
    assert row["approved_for_db_write"] is True
    assert row["db_write_performed"] is False
    assert (
        row["source_payload"]["source_payload_policy"] == "hashes_counts_and_review_metadata_only"
    )
    assert "reviewed_by_hash" in row["source_payload"]
    assert summary["approved_import_row_count"] == 1
    assert summary["pending_count"] == 1
    assert summary["db_write_performed"] is False


def test_apply_brand_review_decisions_blocks_non_approved_decision(tmp_path: Path) -> None:
    """Verify rejected or uncertain decisions do not create import rows."""
    staging_path, staging_rows = _staging_manifest(tmp_path)
    fixture_id = _first_brand_fixture_id(staging_rows)
    decisions_path = tmp_path / "decisions.jsonl"
    _write_jsonl(decisions_path, [_decision(fixture_id, decision="needs_review")])

    rows, summary = apply.apply_brand_review_decisions(
        taxonomy_staging=staging_path,
        decisions_path=decisions_path,
    )

    assert rows == []
    assert summary["skip_reason_counts"] == {"needs_review_blocked": 1}
    assert summary["approved_import_row_count"] == 0


def test_apply_brand_review_decisions_rejects_missing_attestation(tmp_path: Path) -> None:
    """Verify approval requires all import attestations."""
    staging_path, staging_rows = _staging_manifest(tmp_path)
    fixture_id = _first_brand_fixture_id(staging_rows)
    decision = _decision(fixture_id)
    decision["brand_review_decision"]["attest_db_import_allowed"] = False
    decisions_path = tmp_path / "decisions.jsonl"
    _write_jsonl(decisions_path, [decision])

    with pytest.raises(ValueError, match="attest_db_import_allowed"):
        apply.apply_brand_review_decisions(
            taxonomy_staging=staging_path,
            decisions_path=decisions_path,
        )


def test_apply_brand_review_decisions_rejects_duplicate_decisions(tmp_path: Path) -> None:
    """Verify duplicate fixture decisions are rejected."""
    staging_path, staging_rows = _staging_manifest(tmp_path)
    fixture_id = _first_brand_fixture_id(staging_rows)
    decisions_path = tmp_path / "decisions.jsonl"
    _write_jsonl(decisions_path, [_decision(fixture_id), _decision(fixture_id)])

    with pytest.raises(ValueError, match="Duplicate supplement brand decision"):
        apply.apply_brand_review_decisions(
            taxonomy_staging=staging_path,
            decisions_path=decisions_path,
        )


def test_apply_brand_review_decisions_rejects_unmatched_decision(tmp_path: Path) -> None:
    """Verify stale decision files fail closed by default."""
    staging_path, _ = _staging_manifest(tmp_path)
    decisions_path = tmp_path / "decisions.jsonl"
    _write_jsonl(decisions_path, [_decision("brand_aaaaaaaaaaaaaaaaaaaaaaaa")])

    with pytest.raises(ValueError, match="not in taxonomy staging"):
        apply.apply_brand_review_decisions(
            taxonomy_staging=staging_path,
            decisions_path=decisions_path,
        )


def test_apply_brand_review_decisions_rejects_unsafe_text(tmp_path: Path) -> None:
    """Verify local paths and URLs cannot enter reviewed product fields."""
    staging_path, staging_rows = _staging_manifest(tmp_path)
    fixture_id = _first_brand_fixture_id(staging_rows)
    decisions_path = tmp_path / "decisions.jsonl"
    _write_jsonl(
        decisions_path,
        [_decision(fixture_id, product_name="https://example.com/raw-product")],
    )

    with pytest.raises(ValueError, match="local path or URL"):
        apply.apply_brand_review_decisions(
            taxonomy_staging=staging_path,
            decisions_path=decisions_path,
        )


def test_apply_brand_review_decisions_omits_product_literals_and_paths(tmp_path: Path) -> None:
    """Verify output manifest does not expose product folder literals or paths."""
    product_literal = "나우푸드 오메가3_123456"
    staging_path, staging_rows = _staging_manifest(tmp_path)
    fixture_id = _first_brand_fixture_id(staging_rows)
    decisions_path = tmp_path / "decisions.jsonl"
    _write_jsonl(decisions_path, [_decision(fixture_id)])

    rows, summary = apply.apply_brand_review_decisions(
        taxonomy_staging=staging_path,
        decisions_path=decisions_path,
    )
    dumped = json.dumps({"rows": rows, "summary": summary}, ensure_ascii=False)

    assert product_literal not in dumped
    assert str(tmp_path) not in dumped
    assert "/private/" not in dumped
    assert "/Volumes/" not in dumped
    assert '"raw_ocr_text":' not in dumped
    assert '"provider_payload":' not in dumped
    assert summary["product_dir_literals_stored"] is False
    assert summary["absolute_paths_stored"] is False


def test_main_writes_import_manifest_and_redacted_summary(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI writes approved import manifest rows and summary."""
    staging_path, staging_rows = _staging_manifest(tmp_path)
    fixture_id = _first_brand_fixture_id(staging_rows)
    decisions_path = tmp_path / "decisions.jsonl"
    output_path = tmp_path / "out" / "product-import.jsonl"
    _write_jsonl(decisions_path, [_decision(fixture_id)])

    apply.main(
        [
            "--taxonomy-staging",
            str(staging_path),
            "--decisions",
            str(decisions_path),
            "--output",
            str(output_path),
        ]
    )

    stdout = capsys.readouterr().out
    summary = json.loads(stdout)
    assert summary["approved_import_row_count"] == 1
    assert output_path.exists()
    assert output_path.with_suffix(".jsonl.summary.json").exists()
    assert str(tmp_path) not in stdout
    assert "/private/" not in stdout
