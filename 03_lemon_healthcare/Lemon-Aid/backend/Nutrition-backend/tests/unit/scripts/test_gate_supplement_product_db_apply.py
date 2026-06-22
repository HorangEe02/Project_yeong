"""Tests for reviewed supplement product DB apply gate."""

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

gate = importlib.import_module("scripts.gate_supplement_product_db_apply")


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    """Write a JSON fixture.

    Args:
        path: Destination path.
        payload: JSON payload.

    Returns:
        Written path.
    """
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return path


def _brand_gate(*, ready: bool = True) -> dict[str, Any]:
    """Return a brand DB import gate fixture.

    Args:
        ready: Whether product import manifest creation is ready.

    Returns:
        Gate payload.
    """
    return {
        "schema_version": "supplement-brand-db-import-gate-v1",
        "status": "ready_for_product_import_manifest" if ready else "blocked_by_operator_review",
        "brand_candidate_count": 388,
        "approved_decision_count": 12 if ready else 0,
        "product_import_manifest_allowed": ready,
        "db_import_apply_allowed_now": False,
        "db_import_apply_allowed_after_dry_run": ready,
        "db_write_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "local_path_literals_stored": False,
    }


def _dry_run(*, products: int = 12, require_products: bool = True) -> dict[str, Any]:
    """Return an approved taxonomy import dry-run fixture.

    Args:
        products: Approved product import count.
        require_products: Whether approved products were required.

    Returns:
        Dry-run payload.
    """
    return {
        "schema_version": "supplement-taxonomy-approved-db-import-v1",
        "category_seed_row_count": 43,
        "approved_product_import_row_count": products,
        "planned_category_upsert_count": 43,
        "planned_product_upsert_count": products,
        "planned_product_category_upsert_count": products,
        "product_import_manifest_name": (
            "approved-product-import.current.jsonl" if products else None
        ),
        "product_import_manifest_sha256": "a" * 64 if products else None,
        "apply_requested": False,
        "require_approved_products": require_products,
        "ready_for_db_write": products > 0,
        "preflight_only": True,
        "db_write_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
    }


def _category_verify(*, verified: bool = True, missing: int = 0) -> dict[str, Any]:
    """Return a category DB verification fixture.

    Args:
        verified: Whether DB import was verified.
        missing: Missing category count.

    Returns:
        Verification payload.
    """
    return {
        "schema_version": "supplement-taxonomy-db-import-verification-v1",
        "db_import_verified": verified,
        "db_write_performed": False,
        "expected_category_count": 43,
        "matched_category_count": 43 - missing,
        "missing_category_count": missing,
        "expected_product_count": 0,
        "matched_product_count": 0,
        "expected_product_category_count": 0,
        "matched_product_category_count": 0,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "local_paths_printed": False,
        "product_names_printed": False,
        "manufacturer_names_printed": False,
    }


def _target_preflight(*, ready: bool = True) -> dict[str, Any]:
    """Return a DB target preflight fixture.

    Args:
        ready: Whether local target preflight passed.

    Returns:
        Target preflight payload.
    """
    return {
        "schema_version": "supplement-category-seed-db-target-preflight-v1",
        "status": "ready_for_local_category_seed_apply" if ready else "blocked_by_db_target_safety",
        "category_seed_db_apply_target_allowed": ready,
        "database_host_class": "local" if ready else "remote_or_unknown",
        "db_connection_opened": False,
        "db_write_performed": False,
        "database_url_printed": False,
        "database_credentials_printed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
    }


def _input_paths(
    tmp_path: Path,
    *,
    brand: dict[str, Any] | None = None,
    dry_run: dict[str, Any] | None = None,
    verify: dict[str, Any] | None = None,
    target: dict[str, Any] | None = None,
) -> dict[str, Path]:
    """Write default input fixtures.

    Args:
        tmp_path: Temporary directory.
        brand: Optional brand gate override.
        dry_run: Optional dry-run override.
        verify: Optional verifier override.
        target: Optional target preflight override.

    Returns:
        Input path mapping.
    """
    return {
        "brand_db_import_gate": _write_json(tmp_path / "brand-gate.json", brand or _brand_gate()),
        "approved_import_dry_run": _write_json(tmp_path / "dry-run.json", dry_run or _dry_run()),
        "category_db_verify": _write_json(tmp_path / "verify.json", verify or _category_verify()),
        "db_target_preflight": _write_json(
            tmp_path / "target.json",
            target or _target_preflight(),
        ),
    }


def test_product_db_apply_gate_allows_reviewed_product_apply(tmp_path: Path) -> None:
    """Verify all downstream gates allow reviewed product DB apply."""
    summary = gate.build_product_db_apply_gate(input_paths=_input_paths(tmp_path))

    assert summary["schema_version"] == "supplement-product-db-apply-gate-v1"
    assert summary["status"] == "ready_for_reviewed_product_db_apply"
    assert summary["product_db_apply_allowed"] is True
    assert summary["product_category_db_apply_allowed"] is True
    assert summary["approved_product_import_row_count"] == 12
    assert summary["matched_category_count"] == 43
    assert summary["failed_conditions"] == []
    assert summary["db_write_performed"] is False
    assert summary["database_connection_opened"] is False


def test_product_db_apply_gate_blocks_blank_brand_gate(tmp_path: Path) -> None:
    """Verify incomplete brand review blocks product DB apply."""
    summary = gate.build_product_db_apply_gate(
        input_paths=_input_paths(tmp_path, brand=_brand_gate(ready=False))
    )

    assert summary["status"] == "blocked_by_product_db_apply_preflight"
    assert summary["product_db_apply_allowed"] is False
    assert "brand_gate_ready_for_manifest" in summary["failed_conditions"]
    assert "brand_gate_allows_manifest" in summary["failed_conditions"]


def test_product_db_apply_gate_blocks_empty_product_dry_run(tmp_path: Path) -> None:
    """Verify product DB apply requires a non-empty approved product dry-run."""
    summary = gate.build_product_db_apply_gate(
        input_paths=_input_paths(tmp_path, dry_run=_dry_run(products=0))
    )

    assert summary["status"] == "blocked_by_product_db_apply_preflight"
    assert summary["product_db_apply_allowed"] is False
    assert "dry_run_has_product_manifest" in summary["failed_conditions"]
    assert "dry_run_has_approved_products" in summary["failed_conditions"]
    assert "dry_run_ready_for_db_write" in summary["failed_conditions"]


def test_product_db_apply_gate_blocks_unverified_categories(tmp_path: Path) -> None:
    """Verify category verifier failures block product DB apply."""
    summary = gate.build_product_db_apply_gate(
        input_paths=_input_paths(
            tmp_path,
            verify=_category_verify(verified=False, missing=2),
        )
    )

    assert summary["status"] == "blocked_by_product_db_apply_preflight"
    assert "category_verify_required_categories_present" in summary["failed_conditions"]
    assert "category_verify_counts_match_dry_run" in summary["failed_conditions"]
    assert "category_verify_has_no_missing_categories" in summary["failed_conditions"]


def test_product_db_apply_gate_allows_extra_active_categories(tmp_path: Path) -> None:
    """Verify extra DB categories do not block product apply when required rows exist."""
    verify = _category_verify(verified=False, missing=0)
    verify["blocked_reason_codes"] = ["extra_db_rows:supplement_categories"]

    summary = gate.build_product_db_apply_gate(input_paths=_input_paths(tmp_path, verify=verify))

    assert summary["status"] == "ready_for_reviewed_product_db_apply"
    assert summary["product_db_apply_allowed"] is True
    assert summary["failed_conditions"] == []


def test_product_db_apply_gate_blocks_unsafe_target(tmp_path: Path) -> None:
    """Verify non-local DB target preflight blocks product DB apply."""
    summary = gate.build_product_db_apply_gate(
        input_paths=_input_paths(tmp_path, target=_target_preflight(ready=False))
    )

    assert summary["status"] == "blocked_by_product_db_apply_preflight"
    assert "db_target_preflight_ready" in summary["failed_conditions"]
    assert "db_target_allows_category_seed_apply" in summary["failed_conditions"]
    assert "db_target_is_local" in summary["failed_conditions"]


def test_product_db_apply_gate_rejects_unsafe_payload(tmp_path: Path) -> None:
    """Verify raw provider payloads fail closed."""
    dry_run = _dry_run()
    dry_run["provider_payload"] = {"unsafe": True}

    with pytest.raises(gate.ProductDbApplyGateError, match="unsafe content"):
        gate.build_product_db_apply_gate(input_paths=_input_paths(tmp_path, dry_run=dry_run))


def test_product_db_apply_gate_cli_writes_redacted_reports(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI writes JSON and Markdown without local paths."""
    paths = _input_paths(tmp_path)
    output_path = tmp_path / "product-gate.json"
    markdown_path = tmp_path / "product-gate.md"

    gate.main(
        [
            "--brand-db-import-gate",
            str(paths["brand_db_import_gate"]),
            "--approved-import-dry-run",
            str(paths["approved_import_dry_run"]),
            "--category-db-verify",
            str(paths["category_db_verify"]),
            "--db-target-preflight",
            str(paths["db_target_preflight"]),
            "--output",
            str(output_path),
            "--markdown-output",
            str(markdown_path),
        ]
    )

    stdout = capsys.readouterr().out
    summary = json.loads(output_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    combined = "\n".join([stdout, json.dumps(summary, ensure_ascii=False), markdown])
    assert summary["status"] == "ready_for_reviewed_product_db_apply"
    assert "Supplement Product DB Apply Gate" in markdown
    assert "- `brand_gate_allows_manifest`: `true`" in markdown
    assert str(tmp_path) not in combined
    assert "/private/" not in combined
