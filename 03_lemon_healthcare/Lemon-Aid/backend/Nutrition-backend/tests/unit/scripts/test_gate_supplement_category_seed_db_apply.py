"""Tests for supplement category seed DB apply gate."""

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

gate = importlib.import_module("scripts.gate_supplement_category_seed_db_apply")


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    """Write a JSON object fixture.

    Args:
        path: Destination path.
        payload: JSON payload.

    Returns:
        Written path.
    """
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return path


def _staging_summary(*, category_count: int = 43) -> dict[str, Any]:
    """Return a redacted taxonomy staging summary fixture.

    Args:
        category_count: Category seed row count.

    Returns:
        Staging summary payload.
    """
    return {
        "schema_version": "supplement-taxonomy-db-staging-v1",
        "row_count": category_count + 388,
        "category_seed_row_count": category_count,
        "brand_candidate_row_count": 388,
        "review_required_row_count": 388,
        "approved_for_db_write_row_count": category_count,
        "db_write_contract": {
            "category_rows_seedable": True,
            "brand_candidate_rows_seedable_without_review": False,
            "requires_approved_brand_review_manifest": True,
        },
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
    }


def _dry_run(*, category_count: int = 43, product_count: int = 0) -> dict[str, Any]:
    """Return a redacted category-only import dry-run fixture.

    Args:
        category_count: Category seed count.
        product_count: Approved product row count.

    Returns:
        Dry-run summary payload.
    """
    return {
        "schema_version": "supplement-taxonomy-approved-db-import-v1",
        "category_seed_row_count": category_count,
        "approved_product_import_row_count": product_count,
        "planned_category_upsert_count": category_count,
        "planned_product_upsert_count": product_count,
        "planned_product_category_upsert_count": product_count,
        "product_import_manifest_name": None,
        "apply_requested": False,
        "require_approved_products": False,
        "ready_for_db_write": True,
        "preflight_only": True,
        "db_write_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
    }


def _input_paths(tmp_path: Path, *, dry_run: dict[str, Any] | None = None) -> dict[str, Path]:
    """Write default gate inputs.

    Args:
        tmp_path: Temporary directory.
        dry_run: Optional dry-run payload override.

    Returns:
        Input path mapping.
    """
    return {
        "taxonomy_staging_summary": _write_json(
            tmp_path / "staging-summary.json", _staging_summary()
        ),
        "category_only_import_dry_run": _write_json(
            tmp_path / "dry-run.json",
            dry_run if dry_run is not None else _dry_run(),
        ),
    }


def test_category_seed_apply_gate_allows_category_only_apply_after_dry_run(
    tmp_path: Path,
) -> None:
    """Verify category-only dry-run allows category seed apply readiness only."""
    summary = gate.build_category_seed_apply_gate(input_paths=_input_paths(tmp_path))

    assert summary["schema_version"] == "supplement-category-seed-db-apply-gate-v1"
    assert summary["status"] == "ready_for_category_seed_db_apply"
    assert summary["category_seed_db_apply_allowed"] is True
    assert summary["product_db_apply_allowed"] is False
    assert summary["product_category_db_apply_allowed"] is False
    assert summary["category_seed_row_count"] == 43
    assert summary["planned_category_upsert_count"] == 43
    assert summary["failed_conditions"] == []
    assert summary["db_write_performed"] is False
    assert summary["database_connection_opened"] is False
    assert summary["source_rows_read"] is False


def test_category_seed_apply_gate_blocks_when_dry_run_contains_products(
    tmp_path: Path,
) -> None:
    """Verify product rows block category-only apply readiness."""
    summary = gate.build_category_seed_apply_gate(
        input_paths=_input_paths(tmp_path, dry_run=_dry_run(product_count=2))
    )

    assert summary["status"] == "blocked_by_category_seed_preflight"
    assert summary["category_seed_db_apply_allowed"] is False
    assert "dry_run_has_no_product_rows" in summary["failed_conditions"]
    assert "dry_run_plans_only_category_upserts" in summary["failed_conditions"]


def test_category_seed_apply_gate_rejects_unsafe_payload(tmp_path: Path) -> None:
    """Verify unsafe raw OCR keys fail closed."""
    staging_summary = _staging_summary()
    staging_summary["raw_ocr_text"] = "unsafe"
    inputs = {
        "taxonomy_staging_summary": _write_json(tmp_path / "staging-summary.json", staging_summary),
        "category_only_import_dry_run": _write_json(tmp_path / "dry-run.json", _dry_run()),
    }

    with pytest.raises(gate.CategorySeedApplyGateError, match="raw key"):
        gate.build_category_seed_apply_gate(input_paths=inputs)


def test_category_seed_apply_gate_cli_writes_json_and_markdown(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI writes redacted JSON and Markdown reports."""
    inputs = _input_paths(tmp_path)
    output_path = tmp_path / "gate.json"
    markdown_path = tmp_path / "gate.md"

    gate.main(
        [
            "--taxonomy-staging-summary",
            str(inputs["taxonomy_staging_summary"]),
            "--category-only-import-dry-run",
            str(inputs["category_only_import_dry_run"]),
            "--output",
            str(output_path),
            "--markdown-output",
            str(markdown_path),
        ]
    )

    stdout = capsys.readouterr().out
    summary = json.loads(output_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    assert summary["status"] == "ready_for_category_seed_db_apply"
    assert "ready_for_category_seed_db_apply" in stdout
    assert "Supplement Category Seed DB Apply Gate" in markdown
    assert str(tmp_path) not in stdout
    assert str(tmp_path) not in json.dumps(summary, ensure_ascii=False)
