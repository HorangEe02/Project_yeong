"""Tests for supplement brand/product review decision preflight."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

staging = importlib.import_module("scripts.build_supplement_taxonomy_db_staging")
template = importlib.import_module("scripts.export_supplement_brand_review_template")
applier = importlib.import_module("scripts.apply_supplement_brand_review_decisions")
preflight = importlib.import_module("scripts.preflight_supplement_brand_review_decisions")


def _touch(path: Path) -> None:
    """Create a placeholder source image.

    Args:
        path: File path to create.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"placeholder")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write JSONL rows.

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
    """Build a small taxonomy staging manifest with two brand candidates.

    Args:
        tmp_path: Temporary directory.

    Returns:
        Staging path and rows.
    """
    root = tmp_path / "crawling-image"
    _touch(root / "[오메가3]" / "나우푸드 오메가3_123456" / "리뷰" / "review.jpg")
    _touch(root / "[비타민C]" / "고려은단 비타민C_789012" / "상세페이지" / "detail.png")
    rows = staging.build_taxonomy_staging_rows(root=root, source_run_id="brand-preflight-test")
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
    """Return a brand review decision row.

    Args:
        fixture_id: Brand fixture id.
        decision: Decision value.
        manufacturer: Reviewed manufacturer.
        product_name: Reviewed product name.
        overrides: Additional decision fields.

    Returns:
        Decision row.
    """
    payload: dict[str, Any] = {
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
    }
    payload.update(overrides)
    return {
        "schema_version": applier.DECISION_SCHEMA_VERSION,
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
        "schema_version": applier.DECISION_SCHEMA_VERSION,
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


def test_preflight_reports_blank_brand_stubs_as_pending(tmp_path: Path) -> None:
    """Verify untouched brand bundle rows are not apply-ready."""
    staging_path, rows = _staging_manifest(tmp_path)
    decisions_path = tmp_path / "decisions.jsonl"
    fixture_ids = _brand_fixture_ids(rows)
    _write_jsonl(decisions_path, [_blank_decision_row(fixture_id) for fixture_id in fixture_ids])

    summary = preflight.preflight_brand_review_decisions(
        taxonomy_staging=staging_path,
        decisions_path=decisions_path,
        require_all_reviewed=True,
    )

    assert summary["blank_decision_count"] == 2
    assert summary["valid_decision_count"] == 0
    assert summary["approved_decision_count"] == 0
    assert summary["ready_for_requested_apply"] is False
    assert summary["next_operator_action"] == "complete_operator_brand_review"


def test_preflight_allows_partial_brand_apply_without_strict_completion(
    tmp_path: Path,
) -> None:
    """Verify partial apply readiness is separate from strict completion."""
    staging_path, rows = _staging_manifest(tmp_path)
    decisions_path = tmp_path / "decisions.jsonl"
    fixture_ids = _brand_fixture_ids(rows)
    _write_jsonl(decisions_path, [_decision_row(fixture_ids[0])])

    summary = preflight.preflight_brand_review_decisions(
        taxonomy_staging=staging_path,
        decisions_path=decisions_path,
    )

    assert summary["valid_decision_count"] == 1
    assert summary["approved_decision_count"] == 1
    assert summary["missing_decision_count"] == 1
    assert summary["ready_for_partial_apply"] is True
    assert summary["ready_for_strict_apply"] is False
    assert summary["ready_for_requested_apply"] is True


def test_preflight_requires_all_brand_rows_when_strict(tmp_path: Path) -> None:
    """Verify strict preflight blocks partial brand decision sets."""
    staging_path, rows = _staging_manifest(tmp_path)
    decisions_path = tmp_path / "decisions.jsonl"
    fixture_ids = _brand_fixture_ids(rows)
    _write_jsonl(decisions_path, [_decision_row(fixture_ids[0])])

    summary = preflight.preflight_brand_review_decisions(
        taxonomy_staging=staging_path,
        decisions_path=decisions_path,
        require_all_reviewed=True,
    )

    assert summary["ready_for_partial_apply"] is True
    assert summary["ready_for_requested_apply"] is False
    assert summary["next_operator_action"] == "complete_operator_brand_review"


def test_preflight_counts_brand_invalid_and_blocking_decisions(tmp_path: Path) -> None:
    """Verify invalid and non-approved rows are aggregate-only."""
    staging_path, rows = _staging_manifest(tmp_path)
    decisions_path = tmp_path / "decisions.jsonl"
    fixture_ids = _brand_fixture_ids(rows)
    _write_jsonl(
        decisions_path,
        [
            _decision_row(fixture_ids[0], decision="needs_review"),
            _decision_row(fixture_ids[1], attest_db_import_allowed=False),
            _decision_row("brand_aaaaaaaaaaaaaaaaaaaaaaaa"),
        ],
    )

    summary = preflight.preflight_brand_review_decisions(
        taxonomy_staging=staging_path,
        decisions_path=decisions_path,
    )

    assert summary["blocked_decision_count"] == 1
    assert summary["invalid_decision_count"] == 1
    assert summary["unmatched_decision_count"] == 1
    assert summary["invalid_reason_counts"] == {"missing_required_attestation": 1}
    assert summary["ready_for_requested_apply"] is False
    assert summary["next_operator_action"] == "fix_invalid_brand_decision_rows"
    dumped = json.dumps(summary, ensure_ascii=False)
    assert "나우푸드 오메가3_123456" not in dumped
    assert str(tmp_path) not in dumped


def test_preflight_counts_unsafe_brand_payload_without_leaking_value(
    tmp_path: Path,
) -> None:
    """Verify raw fields and values are not emitted."""
    staging_path, rows = _staging_manifest(tmp_path)
    decisions_path = tmp_path / "decisions.jsonl"
    fixture_id = _brand_fixture_ids(rows)[0]
    _write_jsonl(
        decisions_path,
        [_decision_row(fixture_id, raw_ocr_text="visible sensitive text")],
    )

    summary = preflight.preflight_brand_review_decisions(
        taxonomy_staging=staging_path,
        decisions_path=decisions_path,
    )

    assert summary["invalid_decision_count"] == 1
    assert summary["invalid_reason_counts"] == {"unsafe_raw_field": 1}
    dumped = json.dumps(summary, ensure_ascii=False)
    assert "visible sensitive text" not in dumped
    assert '"raw_ocr_text":' not in dumped


def test_preflight_brand_cli_writes_redacted_summary(
    tmp_path: Path,
    capsys: Any,
) -> None:
    """Verify CLI writes a redacted side-effect-free summary."""
    staging_path, rows = _staging_manifest(tmp_path)
    decisions_path = tmp_path / "decisions.jsonl"
    output_path = tmp_path / "out" / "brand-preflight.json"
    fixture_ids = _brand_fixture_ids(rows)
    _write_jsonl(decisions_path, [_blank_decision_row(fixture_id) for fixture_id in fixture_ids])

    preflight.main(
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
    summary = json.loads(output_path.read_text(encoding="utf-8"))
    assert json.loads(printed)["schema_version"] == preflight.SCHEMA_VERSION
    assert summary["db_write_performed"] is False
    assert summary["approved_for_db_write_rows"] == 0
    assert summary["ocr_provider_call_performed"] is False
    assert str(tmp_path) not in printed
    assert str(tmp_path) not in json.dumps(summary, ensure_ascii=False)
