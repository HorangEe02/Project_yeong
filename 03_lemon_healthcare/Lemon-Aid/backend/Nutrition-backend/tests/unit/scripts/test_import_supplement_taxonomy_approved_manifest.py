"""Tests for approved supplement taxonomy DB manifest importer."""

from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path
from uuid import UUID, uuid4

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

staging = importlib.import_module("scripts.build_supplement_taxonomy_db_staging")
template = importlib.import_module("scripts.export_supplement_brand_review_template")
brand_apply = importlib.import_module("scripts.apply_supplement_brand_review_decisions")
importer = importlib.import_module("scripts.import_supplement_taxonomy_approved_manifest")


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


def _decision(fixture_id: str) -> dict[str, object]:
    """Return an approved brand/product review decision.

    Args:
        fixture_id: Brand review fixture id.

    Returns:
        JSON-safe decision row.
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


def _artifacts(tmp_path: Path) -> tuple[Path, Path, list[dict[str, object]]]:
    """Build taxonomy staging and approved product manifest fixtures.

    Args:
        tmp_path: Pytest temporary directory.

    Returns:
        Taxonomy staging path, product import path, and product import rows.
    """
    root = tmp_path / "crawling-image"
    _touch(root / "[오메가3]" / "나우푸드 오메가3_123456" / "리뷰" / "review.jpg")
    _touch(root / "[비타민C]" / "고려은단 비타민C_789012" / "상세페이지" / "detail.png")
    staging_rows = staging.build_taxonomy_staging_rows(root=root, source_run_id="import-test")
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


class _FakeTaxonomyRepository:
    """Repository double for approved taxonomy importer tests."""

    def __init__(self, *, preexisting: bool = False, fail_on_product: bool = False) -> None:
        """Initialize fake repository state.

        Args:
            preexisting: Whether upserts should report update actions.
            fail_on_product: Whether product upsert should fail.
        """
        self.preexisting = preexisting
        self.fail_on_product = fail_on_product
        self.category_ids: dict[str, UUID] = {}
        self.product_ids: dict[tuple[str, str], UUID] = {}
        self.mappings: set[tuple[UUID, UUID]] = set()
        self.category_rows: list[dict[str, object]] = []
        self.product_rows: list[dict[str, object]] = []
        self.mapping_rows: list[dict[str, object]] = []
        self.commit_count = 0
        self.rollback_count = 0

    async def upsert_category(self, row: dict[str, object]) -> tuple[str, UUID]:
        """Record category upsert calls."""
        key = str(row["category_key"])
        row_id = self.category_ids.setdefault(key, uuid4())
        self.category_rows.append(row)
        action = (
            importer.WRITE_ACTION_UPDATED if self.preexisting else importer.WRITE_ACTION_INSERTED
        )
        return action, row_id

    async def upsert_product(self, row: dict[str, object]) -> tuple[str, UUID]:
        """Record product upsert calls."""
        if self.fail_on_product:
            raise ValueError("forced product failure")
        key = (str(row["source_provider"]), str(row["source_product_id"]))
        row_id = self.product_ids.setdefault(key, uuid4())
        self.product_rows.append(row)
        action = (
            importer.WRITE_ACTION_UPDATED if self.preexisting else importer.WRITE_ACTION_INSERTED
        )
        return action, row_id

    async def upsert_product_category(
        self,
        *,
        product_id: UUID,
        category_id: UUID,
        row: dict[str, object],
    ) -> str:
        """Record product-category upsert calls."""
        self.mappings.add((product_id, category_id))
        self.mapping_rows.append(row)
        return importer.WRITE_ACTION_UPDATED if self.preexisting else importer.WRITE_ACTION_INSERTED

    async def commit(self) -> None:
        """Record commit calls."""
        self.commit_count += 1

    async def rollback(self) -> None:
        """Record rollback calls."""
        self.rollback_count += 1


@pytest.mark.asyncio
async def test_import_approved_taxonomy_manifest_defaults_to_dry_run_without_db_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify preflight does not open a DB session or write rows."""
    staging_path, product_path, _rows = _artifacts(tmp_path)

    def _raise_if_called() -> object:
        raise AssertionError("DB sessionmaker must not be called during dry-run")

    monkeypatch.setattr(importer, "get_sessionmaker", _raise_if_called)

    summary = await importer.import_approved_taxonomy_manifest(
        taxonomy_staging=staging_path,
        product_import_manifest=product_path,
    )

    assert summary["category_seed_row_count"] == 2
    assert summary["approved_product_import_row_count"] == 1
    assert summary["planned_product_category_upsert_count"] == 1
    assert summary["ready_for_db_write"] is True
    assert summary["preflight_only"] is True
    assert summary["db_write_performed"] is False
    dumped = json.dumps(summary, ensure_ascii=False)
    assert "나우푸드 오메가3_123456" not in dumped
    assert str(tmp_path) not in dumped
    assert "source_doc_urls" in summary


@pytest.mark.asyncio
async def test_import_approved_taxonomy_manifest_applies_categories_products_and_mappings(
    tmp_path: Path,
) -> None:
    """Verify apply mode writes category, product, and mapping rows."""
    staging_path, product_path, _rows = _artifacts(tmp_path)
    repository = _FakeTaxonomyRepository()

    summary = await importer.import_approved_taxonomy_manifest(
        taxonomy_staging=staging_path,
        product_import_manifest=product_path,
        apply_changes=True,
        repository=repository,
    )

    assert summary["db_write_performed"] is True
    assert summary["preflight_only"] is False
    assert summary["inserted_category_count"] == 2
    assert summary["inserted_product_count"] == 1
    assert summary["inserted_product_category_count"] == 1
    assert repository.commit_count == 1
    assert repository.rollback_count == 0
    assert repository.product_rows[0]["manufacturer"] == "NOW Foods"


@pytest.mark.asyncio
async def test_import_approved_taxonomy_manifest_reports_updates_for_existing_rows(
    tmp_path: Path,
) -> None:
    """Verify repository update actions are surfaced in the summary."""
    staging_path, product_path, _rows = _artifacts(tmp_path)
    repository = _FakeTaxonomyRepository(preexisting=True)

    summary = await importer.import_approved_taxonomy_manifest(
        taxonomy_staging=staging_path,
        product_import_manifest=product_path,
        apply_changes=True,
        repository=repository,
    )

    assert summary["updated_category_count"] == 2
    assert summary["updated_product_count"] == 1
    assert summary["updated_product_category_count"] == 1
    assert summary["inserted_product_count"] == 0


@pytest.mark.asyncio
async def test_import_approved_taxonomy_manifest_rolls_back_on_repository_failure(
    tmp_path: Path,
) -> None:
    """Verify apply mode rolls back if a product write fails."""
    staging_path, product_path, _rows = _artifacts(tmp_path)
    repository = _FakeTaxonomyRepository(fail_on_product=True)

    with pytest.raises(ValueError, match="forced product failure"):
        await importer.import_approved_taxonomy_manifest(
            taxonomy_staging=staging_path,
            product_import_manifest=product_path,
            apply_changes=True,
            repository=repository,
        )

    assert repository.commit_count == 0
    assert repository.rollback_count == 1


@pytest.mark.asyncio
async def test_import_approved_taxonomy_manifest_rejects_unknown_product_category(
    tmp_path: Path,
) -> None:
    """Verify stale category filters fail closed before DB write."""
    staging_path, product_path, rows = _artifacts(tmp_path)
    rows[0]["category_key"] = "missing-category"
    _write_jsonl(product_path, rows)

    with pytest.raises(ValueError, match="unknown category_key"):
        await importer.import_approved_taxonomy_manifest(
            taxonomy_staging=staging_path,
            product_import_manifest=product_path,
        )


@pytest.mark.asyncio
async def test_import_approved_taxonomy_manifest_rejects_empty_required_product_manifest(
    tmp_path: Path,
) -> None:
    """Verify product import can be required by operator policy."""
    staging_path, _product_path, _rows = _artifacts(tmp_path)

    with pytest.raises(ValueError, match="contains no importable rows"):
        await importer.import_approved_taxonomy_manifest(
            taxonomy_staging=staging_path,
            require_approved_products=True,
        )


@pytest.mark.asyncio
async def test_import_approved_taxonomy_manifest_rejects_duplicate_product_source_key(
    tmp_path: Path,
) -> None:
    """Verify duplicate product source identities are rejected."""
    staging_path, product_path, rows = _artifacts(tmp_path)
    _write_jsonl(product_path, [rows[0], rows[0]])

    with pytest.raises(ValueError, match="Duplicate source_provider"):
        await importer.import_approved_taxonomy_manifest(
            taxonomy_staging=staging_path,
            product_import_manifest=product_path,
        )


@pytest.mark.asyncio
async def test_import_approved_taxonomy_manifest_rejects_unsafe_raw_payload_key(
    tmp_path: Path,
) -> None:
    """Verify raw OCR/provider payloads cannot enter import manifests."""
    staging_path, product_path, rows = _artifacts(tmp_path)
    rows[0]["source_payload"] = {"raw_ocr_text": "unsafe"}
    _write_jsonl(product_path, rows)

    with pytest.raises(ValueError, match="forbidden raw"):
        await importer.import_approved_taxonomy_manifest(
            taxonomy_staging=staging_path,
            product_import_manifest=product_path,
        )


@pytest.mark.asyncio
async def test_run_cli_writes_summary_and_keeps_stdout_redacted(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI writes a count-only preflight summary."""
    staging_path, product_path, _rows = _artifacts(tmp_path)
    summary_path = tmp_path / "out" / "summary.json"

    exit_code = await importer.run_cli(
        [
            "--taxonomy-staging",
            str(staging_path),
            "--product-import-manifest",
            str(product_path),
            "--summary",
            str(summary_path),
        ]
    )

    stdout = capsys.readouterr().out
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert summary["db_write_performed"] is False
    assert "나우푸드 오메가3_123456" not in stdout
    assert str(tmp_path) not in stdout
    assert "/private/" not in stdout


@pytest.mark.asyncio
async def test_run_cli_loads_env_file_without_printing_database_url(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI env-file loading keeps DB connection values out of output.

    Args:
        tmp_path: Pytest temporary directory.
        monkeypatch: Pytest monkeypatch fixture.
        capsys: Pytest stdout/stderr capture fixture.
    """
    monkeypatch.delenv("DATABASE_URL", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "export DATABASE_URL='postgresql+asyncpg://example:secret@example.invalid/db'\n",
        encoding="utf-8",
    )
    summary_path = tmp_path / "summary.json"
    seen_database_url: list[str] = []

    async def _fake_import_approved_taxonomy_manifest(**_kwargs: object) -> dict[str, object]:
        """Return count-only summary after checking env loading.

        Returns:
            Redacted fake importer summary.
        """
        seen_database_url.append(os.environ["DATABASE_URL"])
        return {
            "schema_version": importer.SCHEMA_VERSION,
            "db_write_performed": False,
            "preflight_only": True,
        }

    monkeypatch.setattr(
        importer,
        "import_approved_taxonomy_manifest",
        _fake_import_approved_taxonomy_manifest,
    )

    exit_code = await importer.run_cli(
        [
            "--taxonomy-staging",
            str(tmp_path / "taxonomy.jsonl"),
            "--env-file",
            str(env_file),
            "--summary",
            str(summary_path),
            "--apply",
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
