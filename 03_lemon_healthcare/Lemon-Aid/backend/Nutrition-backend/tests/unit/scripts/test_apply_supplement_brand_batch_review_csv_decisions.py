"""Tests for applying brand review batch CSV rows to JSONL decisions."""

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

applier = importlib.import_module("scripts.apply_supplement_brand_batch_review_csv_decisions")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> Path:
    """Write JSONL test rows.

    Args:
        path: Destination file.
        rows: JSON rows.

    Returns:
        Written path.
    """
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    return path


def _write_csv(path: Path, rows: list[dict[str, str]]) -> Path:
    """Write operator CSV rows.

    Args:
        path: Destination CSV file.
        rows: CSV rows.

    Returns:
        Written path.
    """
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return path


def _blank_brand_row(fixture_id: str) -> dict[str, Any]:
    """Return a blank brand review decision row.

    Args:
        fixture_id: Safe fixture id.

    Returns:
        Brand decision row.
    """
    return {
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
    }


def _csv_row(
    fixture_id: str,
    *,
    decision: str = "",
    manufacturer: str = "",
    product: str = "",
    reason_codes: str = "",
) -> dict[str, str]:
    """Return one operator review CSV row.

    Args:
        fixture_id: Safe fixture id.
        decision: Review decision.
        manufacturer: Reviewed manufacturer text.
        product: Reviewed product text.
        reason_codes: Delimited reason codes.

    Returns:
        CSV row.
    """
    return {
        "fixture_id": fixture_id,
        "decision": decision,
        "reviewed_manufacturer": manufacturer,
        "reviewed_product_name": product,
        "reason_codes": reason_codes,
    }


def _input_paths(
    tmp_path: Path,
    *,
    batch_rows: list[dict[str, Any]],
    csv_rows: list[dict[str, str]],
) -> dict[str, Path]:
    """Write paired batch and CSV fixtures.

    Args:
        tmp_path: Temporary directory.
        batch_rows: Batch JSONL rows.
        csv_rows: CSV rows.

    Returns:
        Input path mapping.
    """
    return {
        "batch_file": _write_jsonl(tmp_path / "brand_product_review-001.jsonl", batch_rows),
        "batch_review_csv": _write_csv(
            tmp_path / "brand_product_review-001.review.csv",
            csv_rows,
        ),
    }


def _approval_attestations() -> dict[str, bool]:
    """Return all approval attestations enabled.

    Returns:
        Approval attestation mapping.
    """
    return {
        "attest_brand_product_review_completed": True,
        "attest_not_using_product_folder_literal_as_manufacturer": True,
        "attest_product_name_reviewed_from_label_or_safe_catalog": True,
        "attest_no_raw_ocr_or_provider_payload_copied": True,
        "attest_db_import_allowed": True,
    }


def test_apply_brand_batch_review_csv_decisions_updates_approved_rows_and_redacts_summary(
    tmp_path: Path,
) -> None:
    """Verify approved CSV rows become JSONL decisions without summary leakage."""
    product_text = "Reviewed Product Name"
    paths = _input_paths(
        tmp_path,
        batch_rows=[_blank_brand_row("brand_review_1"), _blank_brand_row("brand_review_2")],
        csv_rows=[
            _csv_row(
                "brand_review_1",
                decision="approve",
                manufacturer="Reviewed Maker",
                product=product_text,
                reason_codes="reviewed_label_or_catalog",
            ),
            _csv_row("brand_review_2"),
        ],
    )

    rows, summary = applier.apply_brand_batch_review_csv_decisions(
        input_paths=paths,
        reviewer_id="operator_batch",
        reviewed_at_safe_token="2026-06-04T00:00:00Z",
        approval_attestations=_approval_attestations(),
    )
    markdown = applier.build_markdown(summary)

    decision = rows[0]["brand_review_decision"]
    assert decision["decision"] == "approve"
    assert decision["reviewed_manufacturer"] == "Reviewed Maker"
    assert decision["reviewed_product_name"] == product_text
    assert rows[1]["brand_review_decision"]["decision"] == ""
    assert summary["changed_row_count"] == 1
    assert summary["unchanged_row_count"] == 1
    assert summary["decision_counts"] == {"approve": 1, "blank": 1}
    assert summary["approved_for_db_write_rows"] == 1
    assert summary["db_write_performed"] is False
    public_dump = json.dumps({"summary": summary, "markdown": markdown}, ensure_ascii=False)
    assert product_text not in public_dump
    assert str(tmp_path) not in public_dump


def test_apply_brand_batch_review_csv_decisions_preserves_all_blank_csv(
    tmp_path: Path,
) -> None:
    """Verify an untouched CSV produces no changed rows."""
    paths = _input_paths(
        tmp_path,
        batch_rows=[_blank_brand_row("brand_review_1"), _blank_brand_row("brand_review_2")],
        csv_rows=[_csv_row("brand_review_1"), _csv_row("brand_review_2")],
    )

    rows, summary = applier.apply_brand_batch_review_csv_decisions(
        input_paths=paths,
        reviewer_id="operator_batch",
        reviewed_at_safe_token="2026-06-04T00:00:00Z",
        approval_attestations=_approval_attestations(),
    )

    assert [row["brand_review_decision"]["decision"] for row in rows] == ["", ""]
    assert summary["changed_row_count"] == 0
    assert summary["decision_counts"] == {"blank": 2}
    assert summary["input_path_fingerprints"]["batch_file"].startswith("fp-")
    assert "input_path_hashes" not in summary


def test_apply_brand_batch_review_csv_decisions_requires_all_reviewed_gate(
    tmp_path: Path,
) -> None:
    """Verify workflow mode refuses to apply blank CSV rows."""
    paths = _input_paths(
        tmp_path,
        batch_rows=[_blank_brand_row("brand_review_1"), _blank_brand_row("brand_review_2")],
        csv_rows=[_csv_row("brand_review_1"), _csv_row("brand_review_2")],
    )

    with pytest.raises(applier.BrandBatchCsvApplyError, match="blank decisions"):
        applier.apply_brand_batch_review_csv_decisions(
            input_paths=paths,
            reviewer_id="operator_batch",
            reviewed_at_safe_token="2026-06-04T00:00:00Z",
            approval_attestations=_approval_attestations(),
            require_all_reviewed=True,
        )


def test_apply_brand_batch_review_csv_decisions_rejects_fixture_order_mismatch(
    tmp_path: Path,
) -> None:
    """Verify CSV rows must stay in the same order as the batch JSONL."""
    paths = _input_paths(
        tmp_path,
        batch_rows=[_blank_brand_row("brand_review_1"), _blank_brand_row("brand_review_2")],
        csv_rows=[_csv_row("brand_review_2"), _csv_row("brand_review_1")],
    )

    with pytest.raises(applier.BrandBatchCsvApplyError, match="fixture order"):
        applier.apply_brand_batch_review_csv_decisions(
            input_paths=paths,
            reviewer_id="operator_batch",
            reviewed_at_safe_token="2026-06-04T00:00:00Z",
            approval_attestations=_approval_attestations(),
        )


def test_apply_brand_batch_review_csv_decisions_requires_approval_attestations(
    tmp_path: Path,
) -> None:
    """Verify approved rows require every explicit attestation."""
    attestations = _approval_attestations()
    attestations["attest_db_import_allowed"] = False
    paths = _input_paths(
        tmp_path,
        batch_rows=[_blank_brand_row("brand_review_1")],
        csv_rows=[
            _csv_row(
                "brand_review_1",
                decision="approve",
                manufacturer="Reviewed Maker",
                product="Reviewed Product",
                reason_codes="reviewed_label_or_catalog",
            )
        ],
    )

    with pytest.raises(applier.BrandBatchCsvApplyError, match="attest_db_import_allowed"):
        applier.apply_brand_batch_review_csv_decisions(
            input_paths=paths,
            reviewer_id="operator_batch",
            reviewed_at_safe_token="2026-06-04T00:00:00Z",
            approval_attestations=attestations,
        )


def test_apply_brand_batch_review_csv_decisions_rejects_partial_blank_csv_row(
    tmp_path: Path,
) -> None:
    """Verify rows cannot contain review text without an explicit decision."""
    paths = _input_paths(
        tmp_path,
        batch_rows=[_blank_brand_row("brand_review_1")],
        csv_rows=[
            _csv_row(
                "brand_review_1",
                manufacturer="Reviewed Maker",
                product="Reviewed Product",
            )
        ],
    )

    with pytest.raises(applier.BrandBatchCsvApplyError, match="review fields but no decision"):
        applier.apply_brand_batch_review_csv_decisions(
            input_paths=paths,
            reviewer_id="operator_batch",
            reviewed_at_safe_token="2026-06-04T00:00:00Z",
            approval_attestations=_approval_attestations(),
        )


def test_main_writes_output_summary_and_markdown(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI writes redacted artifacts and output JSONL."""
    paths = _input_paths(
        tmp_path,
        batch_rows=[_blank_brand_row("brand_review_1")],
        csv_rows=[_csv_row("brand_review_1")],
    )
    output = tmp_path / "out" / "brand_product_review-001.from-csv.jsonl"
    summary = tmp_path / "out" / "summary.json"
    markdown = tmp_path / "out" / "summary.md"

    applier.main(
        [
            "--batch-file",
            str(paths["batch_file"]),
            "--batch-review-csv",
            str(paths["batch_review_csv"]),
            "--output",
            str(output),
            "--summary-output",
            str(summary),
            "--markdown-output",
            str(markdown),
            "--reviewer-id",
            "operator_batch",
            "--reviewed-at-safe-token",
            "2026-06-04T00:00:00Z",
            "--attest-brand-product-review-completed",
            "--attest-not-using-product-folder-literal-as-manufacturer",
            "--attest-product-name-reviewed-from-label-or-safe-catalog",
            "--attest-no-raw-ocr-or-provider-payload-copied",
            "--attest-db-import-allowed",
        ]
    )

    cli = json.loads(capsys.readouterr().out)
    summary_payload = json.loads(summary.read_text(encoding="utf-8"))
    assert output.exists()
    assert markdown.exists()
    assert cli["status"] == "ok"
    assert summary_payload["output_batch_file_written"] is True
    assert summary_payload["db_write_performed"] is False
    assert str(tmp_path) not in json.dumps(summary_payload, ensure_ascii=False)
