"""Tests for read-only supplement taxonomy DB import verification."""

from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path
from typing import Any

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

staging = importlib.import_module("scripts.build_supplement_taxonomy_db_staging")
template = importlib.import_module("scripts.export_supplement_brand_review_template")
brand_apply = importlib.import_module("scripts.apply_supplement_brand_review_decisions")
verifier = importlib.import_module("scripts.verify_supplement_taxonomy_db_import")


def _touch(path: Path) -> None:
    """Create a placeholder image-like file.

    Args:
        path: File path to create.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"placeholder")


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    """Write JSONL rows.

    Args:
        path: Destination path.
        rows: Rows to write.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _decision(fixture_id: str) -> dict[str, object]:
    """Build an approved brand/product review decision.

    Args:
        fixture_id: Brand review fixture id.

    Returns:
        Approved decision row.
    """
    return {
        "schema_version": brand_apply.DECISION_SCHEMA_VERSION,
        "fixture_id": fixture_id,
        "brand_review_decision": {
            "decision": "approve",
            "reviewer_id": "operator_taxonomy",
            "reviewed_at": "2026-06-03T12:00:00Z",
            "reviewed_manufacturer": "NOW Foods",
            "reviewed_product_name": "Omega-3 Softgels",
            "reason_codes": ["reviewed_label_or_catalog"],
            "attest_brand_product_review_completed": True,
            "attest_not_using_product_folder_literal_as_manufacturer": True,
            "attest_product_name_reviewed_from_label_or_safe_catalog": True,
            "attest_no_raw_ocr_or_provider_payload_copied": True,
            "attest_db_import_allowed": True,
        },
    }


def _artifacts(tmp_path: Path) -> tuple[Path, Path, list[dict[str, Any]]]:
    """Build taxonomy staging and approved product import fixtures.

    Args:
        tmp_path: Temporary directory.

    Returns:
        Taxonomy staging path, product import path, and product rows.
    """
    root = tmp_path / "crawling-image"
    _touch(root / "[오메가3]" / "나우푸드 오메가3_123456" / "리뷰" / "review.jpg")
    _touch(root / "[비타민C]" / "고려은단 비타민C_789012" / "상세페이지" / "detail.png")
    staging_rows = staging.build_taxonomy_staging_rows(root=root, source_run_id="verify-test")
    staging_path = tmp_path / "taxonomy.jsonl"
    _write_jsonl(staging_path, staging_rows)

    brand_row = next(
        row for row in staging_rows if row["row_type"] == staging.ROW_TYPE_BRAND_CANDIDATE
    )
    fixture_id = template._fixture_id(str(brand_row["product_dir_hash"]))
    decisions_path = tmp_path / "decisions.jsonl"
    _write_jsonl(decisions_path, [_decision(fixture_id)])
    product_rows, _summary = brand_apply.apply_brand_review_decisions(
        taxonomy_staging=staging_path,
        decisions_path=decisions_path,
    )
    product_path = tmp_path / "approved-products.jsonl"
    _write_jsonl(product_path, product_rows)
    return staging_path, product_path, product_rows


class _FakeVerificationRepository:
    """Read-only repository double for taxonomy verification tests."""

    def __init__(
        self,
        *,
        category_keys: set[str],
        product_source_keys: set[tuple[str, str]],
        product_category_keys: set[tuple[str, str, str]],
    ) -> None:
        """Initialize present DB keys.

        Args:
            category_keys: Category keys present in the fake DB.
            product_source_keys: Product source keys present in the fake DB.
            product_category_keys: Product-category keys present in the fake DB.
        """
        self.category_keys = category_keys
        self.product_source_keys = product_source_keys
        self.product_category_keys = product_category_keys

    async def present_category_keys(self, category_keys: list[str]) -> set[str]:
        """Return present category keys."""
        return self.category_keys.intersection(set(category_keys))

    async def active_category_keys(self) -> set[str]:
        """Return all active category keys."""
        return set(self.category_keys)

    async def present_product_source_keys(
        self,
        source_keys: list[tuple[str, str]],
    ) -> set[tuple[str, str]]:
        """Return present product source keys."""
        return self.product_source_keys.intersection(set(source_keys))

    async def present_product_category_keys(
        self,
        source_category_keys: list[tuple[str, str, str]],
    ) -> set[tuple[str, str, str]]:
        """Return present product-category keys."""
        return self.product_category_keys.intersection(set(source_category_keys))


def _present_repository(
    *,
    category_keys: set[str],
    product_rows: list[dict[str, Any]],
    omit_mapping: bool = False,
) -> _FakeVerificationRepository:
    """Build a fake repository matching product rows.

    Args:
        category_keys: Category keys present in DB.
        product_rows: Product import rows.
        omit_mapping: Whether to omit product-category mappings.

    Returns:
        Repository double.
    """
    product_source_keys = {
        (str(row["source_provider"]), str(row["source_product_id"])) for row in product_rows
    }
    product_category_keys = {
        (str(row["source_provider"]), str(row["source_product_id"]), str(row["category_key"]))
        for row in product_rows
    }
    return _FakeVerificationRepository(
        category_keys=category_keys,
        product_source_keys=product_source_keys,
        product_category_keys=set() if omit_mapping else product_category_keys,
    )


@pytest.mark.asyncio
async def test_verify_taxonomy_db_import_reports_all_rows_present(tmp_path: Path) -> None:
    """Verify category/product/mapping matches produce a verified summary."""
    staging_path, product_path, product_rows = _artifacts(tmp_path)
    category_keys = {"오메가3", "비타민c"}
    repository = _present_repository(category_keys=category_keys, product_rows=product_rows)

    summary = await verifier.verify_supplement_taxonomy_db_import(
        taxonomy_staging=staging_path,
        product_import_manifest=product_path,
        repository=repository,
    )

    assert summary["db_import_verified"] is True
    assert summary["status"] == "verified"
    assert summary["verification_scope"] == "category_and_reviewed_products"
    assert summary["category_import_verified"] is True
    assert summary["product_import_verified"] is True
    assert summary["expected_category_count"] == 2
    assert summary["active_db_category_count"] == 2
    assert summary["matched_category_count"] == 2
    assert summary["extra_active_category_count"] == 0
    assert summary["expected_product_count"] == 1
    assert summary["matched_product_count"] == 1
    assert summary["expected_product_category_count"] == 1
    assert summary["matched_product_category_count"] == 1
    assert summary["db_write_performed"] is False
    dumped = json.dumps(summary, ensure_ascii=False)
    assert "NOW Foods" not in dumped
    assert "Omega-3 Softgels" not in dumped
    assert str(tmp_path) not in dumped


@pytest.mark.asyncio
async def test_verify_taxonomy_db_import_reports_missing_mapping(tmp_path: Path) -> None:
    """Verify missing product-category mappings are counted without printing product text."""
    staging_path, product_path, product_rows = _artifacts(tmp_path)
    repository = _present_repository(
        category_keys={"오메가3", "비타민c"},
        product_rows=product_rows,
        omit_mapping=True,
    )

    summary = await verifier.verify_supplement_taxonomy_db_import(
        taxonomy_staging=staging_path,
        product_import_manifest=product_path,
        repository=repository,
    )

    assert summary["db_import_verified"] is False
    assert summary["status"] == "not_verified_missing_db_rows"
    assert summary["missing_product_category_count"] == 1
    assert summary["blocked_reason_codes"] == ["missing_db_rows:supplement_product_categories"]
    assert len(summary["missing_product_category_key_hashes"]) == 1
    dumped = json.dumps(summary, ensure_ascii=False)
    assert "source_product_id" not in dumped
    assert "NOW Foods" not in dumped


@pytest.mark.asyncio
async def test_verify_taxonomy_db_import_can_verify_category_only_state(tmp_path: Path) -> None:
    """Verify category-only imports are supported when product rows are not required."""
    staging_path, _product_path, _product_rows = _artifacts(tmp_path)
    repository = _FakeVerificationRepository(
        category_keys={"오메가3", "비타민c"},
        product_source_keys=set(),
        product_category_keys=set(),
    )

    summary = await verifier.verify_supplement_taxonomy_db_import(
        taxonomy_staging=staging_path,
        repository=repository,
    )

    assert summary["db_import_verified"] is True
    assert summary["status"] == "verified"
    assert summary["verification_scope"] == "category_seed_only"
    assert summary["category_import_verified"] is True
    assert summary["product_import_verified"] is False
    assert summary["expected_product_count"] == 0
    assert summary["expected_product_category_count"] == 0


@pytest.mark.asyncio
async def test_verify_taxonomy_db_import_blocks_extra_active_categories(
    tmp_path: Path,
) -> None:
    """Verify active DB categories outside staging block category-only proof."""
    staging_path, _product_path, _product_rows = _artifacts(tmp_path)
    repository = _FakeVerificationRepository(
        category_keys={"오메가3", "비타민c", "legacy_duplicate"},
        product_source_keys=set(),
        product_category_keys=set(),
    )

    summary = await verifier.verify_supplement_taxonomy_db_import(
        taxonomy_staging=staging_path,
        repository=repository,
    )

    assert summary["db_import_verified"] is False
    assert summary["status"] == "not_verified_missing_db_rows"
    assert summary["category_import_verified"] is False
    assert summary["expected_category_count"] == 2
    assert summary["active_db_category_count"] == 3
    assert summary["matched_category_count"] == 2
    assert summary["missing_category_count"] == 0
    assert summary["extra_active_category_count"] == 1
    assert summary["blocked_reason_codes"] == ["extra_db_rows:supplement_categories"]
    assert len(summary["extra_active_category_key_hashes"]) == 1
    dumped = json.dumps(summary, ensure_ascii=False)
    assert "legacy_duplicate" not in dumped


@pytest.mark.asyncio
async def test_verify_taxonomy_db_import_blocks_when_required_manifest_is_missing(
    tmp_path: Path,
) -> None:
    """Verify required product verification records an explicit blocker."""
    staging_path, _product_path, _product_rows = _artifacts(tmp_path)
    repository = _FakeVerificationRepository(
        category_keys={"오메가3", "비타민c"},
        product_source_keys=set(),
        product_category_keys=set(),
    )

    summary = await verifier.verify_supplement_taxonomy_db_import(
        taxonomy_staging=staging_path,
        require_approved_products=True,
        repository=repository,
    )

    assert summary["status"] == "blocked_missing_product_import_manifest"
    assert summary["db_import_verified"] is False
    assert summary["category_import_verified"] is False
    assert summary["product_import_manifest_present"] is False
    assert summary["approved_product_rows_required"] is True
    assert summary["approved_product_rows_available"] is False
    assert summary["active_db_category_count"] is None
    assert summary["extra_active_category_count"] is None
    assert summary["blocked_reason_codes"] == ["missing_required:approved_product_import"]
    dumped = json.dumps(summary, ensure_ascii=False)
    assert str(tmp_path) not in dumped


@pytest.mark.asyncio
async def test_verify_taxonomy_db_import_cli_fail_on_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI can fail non-zero when expected rows are missing."""
    staging_path, product_path, _product_rows = _artifacts(tmp_path)

    async def _fake_verify(**_kwargs: object) -> dict[str, object]:
        """Return a missing-row summary without opening a DB session."""
        return {
            "schema_version": verifier.SCHEMA_VERSION,
            "db_import_verified": False,
            "db_write_performed": False,
        }

    monkeypatch.setattr(verifier, "verify_supplement_taxonomy_db_import", _fake_verify)

    exit_code = await verifier.run_cli(
        [
            "--taxonomy-staging",
            str(staging_path),
            "--product-import-manifest",
            str(product_path),
            "--fail-on-missing",
        ]
    )

    stdout = capsys.readouterr().out
    assert exit_code == 1
    assert str(tmp_path) not in stdout
    assert "NOW Foods" not in stdout


@pytest.mark.asyncio
async def test_verify_taxonomy_db_import_error_summary_is_redacted(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI failure summary omits artifact paths and product text."""
    missing = tmp_path / "missing.jsonl"
    output_path = tmp_path / "summary.json"

    exit_code = await verifier.run_cli(
        [
            "--taxonomy-staging",
            str(missing),
            "--summary",
            str(output_path),
        ]
    )

    stdout = capsys.readouterr().out
    summary = json.loads(output_path.read_text(encoding="utf-8"))
    assert exit_code == 1
    assert summary["status"] == "error"
    assert str(tmp_path) not in stdout
    assert str(tmp_path) not in json.dumps(summary, ensure_ascii=False)


@pytest.mark.asyncio
async def test_verify_taxonomy_db_import_cli_loads_env_file_without_printing_database_url(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify verifier CLI can use env-file while keeping DB values redacted.

    Args:
        tmp_path: Pytest temporary directory.
        monkeypatch: Pytest monkeypatch fixture.
        capsys: Pytest stdout/stderr capture fixture.
    """
    monkeypatch.delenv("DATABASE_URL", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DATABASE_URL='postgresql+asyncpg://example:secret@example.invalid/db'\n",
        encoding="utf-8",
    )
    summary_path = tmp_path / "summary.json"
    seen_database_url: list[str] = []

    async def _fake_verify_supplement_taxonomy_db_import(
        **_kwargs: object,
    ) -> dict[str, object]:
        """Return count-only summary after checking env loading.

        Returns:
            Redacted fake verifier summary.
        """
        seen_database_url.append(os.environ["DATABASE_URL"])
        return {
            "schema_version": verifier.SCHEMA_VERSION,
            "db_import_verified": True,
            "db_write_performed": False,
        }

    monkeypatch.setattr(
        verifier,
        "verify_supplement_taxonomy_db_import",
        _fake_verify_supplement_taxonomy_db_import,
    )

    exit_code = await verifier.run_cli(
        [
            "--taxonomy-staging",
            str(tmp_path / "taxonomy.jsonl"),
            "--env-file",
            str(env_file),
            "--summary",
            str(summary_path),
        ]
    )

    stdout = capsys.readouterr().out
    summary_text = summary_path.read_text(encoding="utf-8")
    assert exit_code == 0
    assert seen_database_url == ["postgresql+asyncpg://example:secret@example.invalid/db"]
    assert "secret" not in stdout
    assert "example.invalid" not in stdout
    assert "secret" not in summary_text
    assert "example.invalid" not in summary_text
