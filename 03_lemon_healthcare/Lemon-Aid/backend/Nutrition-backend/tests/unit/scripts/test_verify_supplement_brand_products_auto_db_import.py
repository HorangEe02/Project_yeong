"""Tests for auto supplement brand product DB verification."""

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

auto_import = importlib.import_module("scripts.import_supplement_brand_products_auto")
verifier = importlib.import_module("scripts.verify_supplement_brand_products_auto_db_import")


def _source_root(tmp_path: Path) -> Path:
    """Create a small crawling-image tree fixture.

    Args:
        tmp_path: Temporary directory.

    Returns:
        Fixture root path.
    """
    root = tmp_path / "crawling-image"
    (root / "[비타민C]" / "Sample Brand Product_123456").mkdir(parents=True)
    (root / "[오메가3]" / "Second Brand Product_789012").mkdir(parents=True)
    return root


@pytest.mark.asyncio
async def test_verify_auto_brand_products_reports_verified_counts(tmp_path: Path) -> None:
    """Verify all expected auto products and mappings can be proven present."""
    root = _source_root(tmp_path)
    rows = auto_import.build_rows(root)
    repository = _FakeAutoBrandProductRepository.from_rows(rows)

    summary = await verifier.verify_auto_brand_product_db_import(
        root=root,
        dsn=None,
        repository=repository,
    )

    assert summary["schema_version"] == verifier.SCHEMA_VERSION
    assert summary["status"] == "verified"
    assert summary["db_import_verified"] is True
    assert summary["expected_category_count"] == 2
    assert summary["matched_category_count"] == 2
    assert summary["expected_product_count"] == 2
    assert summary["matched_product_count"] == 2
    assert summary["expected_product_category_count"] == 2
    assert summary["matched_product_category_count"] == 2
    assert summary["actual_auto_product_category_count_for_expected_products"] == 2
    assert summary["stale_product_category_mapping_count"] == 0
    assert summary["cleanup_recommended"] is False
    assert summary["blocked_reason_codes"] == []
    assert summary["db_write_performed"] is False
    dumped = json.dumps(summary, ensure_ascii=False)
    assert "Sample Brand Product" not in dumped
    assert "Second Brand Product" not in dumped
    assert str(tmp_path) not in dumped


@pytest.mark.asyncio
async def test_verify_auto_brand_products_reports_stale_mapping_hash_only(
    tmp_path: Path,
) -> None:
    """Verify stale auto mappings are counted without exposing category literals."""
    root = _source_root(tmp_path)
    rows = auto_import.build_rows(root)
    repository = _FakeAutoBrandProductRepository.from_rows(
        rows,
        extra_mappings={
            (
                auto_import.SOURCE_PROVIDER,
                str(rows[0]["source_product_id"]),
                "legacy-extra",
            )
        },
    )

    summary = await verifier.verify_auto_brand_product_db_import(
        root=root,
        dsn=None,
        repository=repository,
    )
    dumped = json.dumps(summary, ensure_ascii=False)

    assert summary["status"] == "verified_with_stale_auto_mappings"
    assert summary["db_import_verified"] is True
    assert summary["expected_product_category_count"] == 2
    assert summary["matched_product_category_count"] == 2
    assert summary["actual_auto_product_category_count_for_expected_products"] == 3
    assert summary["stale_product_category_mapping_count"] == 1
    assert len(summary["stale_product_category_key_hashes"]) == 1
    assert summary["cleanup_recommended"] is True
    assert summary["cleanup_plan"]["target_table"] == "supplement_product_categories"
    assert "legacy-extra" not in dumped
    assert str(rows[0]["source_product_id"]) not in dumped


@pytest.mark.asyncio
async def test_verify_auto_brand_products_reports_missing_mapping_hash_only(
    tmp_path: Path,
) -> None:
    """Verify missing auto product-category rows are redacted and counted."""
    root = _source_root(tmp_path)
    rows = auto_import.build_rows(root)
    repository = _FakeAutoBrandProductRepository.from_rows(rows, omit_mappings=True)

    summary = await verifier.verify_auto_brand_product_db_import(
        root=root,
        dsn=None,
        repository=repository,
    )

    assert summary["status"] == "not_verified_missing_db_rows"
    assert summary["db_import_verified"] is False
    assert summary["missing_product_category_count"] == 2
    assert summary["blocked_reason_codes"] == ["missing_db_rows:supplement_product_categories"]
    assert len(summary["missing_product_category_key_hashes"]) == 2
    dumped = json.dumps(summary, ensure_ascii=False)
    assert "source_product_id" not in dumped
    assert "Sample Brand Product" not in dumped


@pytest.mark.asyncio
async def test_verify_auto_brand_products_requires_dsn_without_repository(
    tmp_path: Path,
) -> None:
    """Verify live DB verification fails closed when no DSN is available."""
    root = _source_root(tmp_path)

    with pytest.raises(ValueError, match="DATABASE_URL_PLAIN"):
        await verifier.verify_auto_brand_product_db_import(
            root=root,
            dsn=None,
        )


def test_resolve_dsn_loads_env_file_without_printing_secret(tmp_path: Path) -> None:
    """Verify dotenv DSNs are normalized for asyncpg without exposing values."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "DATABASE_URL='postgresql+asyncpg://user:secret@localhost:5432/app'",
                "SUPABASE_SECRET_KEY=must-not-be-used",
            ]
        ),
        encoding="utf-8",
    )

    resolved = verifier._resolve_dsn(dsn=None, env_file=env_file)

    assert resolved == "postgresql://user:secret@localhost:5432/app"


def test_resolve_dsn_prefers_explicit_plain_dsn(tmp_path: Path) -> None:
    """Verify explicit DSN wins over dotenv values."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        'DATABASE_URL="postgresql+asyncpg://user:secret@localhost:5432/app"\n',
        encoding="utf-8",
    )

    resolved = verifier._resolve_dsn(
        dsn="postgresql://explicit:secret@localhost:5432/app",
        env_file=env_file,
    )

    assert resolved == "postgresql://explicit:secret@localhost:5432/app"


class _FakeAutoBrandProductRepository:
    """Read-only repository double for auto brand product verification.

    Args:
        category_keys: Category keys present in the fake DB.
        product_keys: Product source keys present in the fake DB.
        product_category_keys: Product-category triples present in the fake DB.
    """

    def __init__(
        self,
        *,
        category_keys: set[str],
        product_keys: set[tuple[str, str]],
        product_category_keys: set[tuple[str, str, str]],
    ) -> None:
        """Initialize repository state.

        Args:
            category_keys: Category keys present in the fake DB.
            product_keys: Product source keys present in the fake DB.
            product_category_keys: Product-category triples present in the fake DB.
        """
        self.category_keys = category_keys
        self.product_keys = product_keys
        self.product_category_keys = product_category_keys

    @classmethod
    def from_rows(
        cls,
        rows: list[dict[str, Any]],
        *,
        omit_mappings: bool = False,
        extra_mappings: set[tuple[str, str, str]] | None = None,
    ) -> _FakeAutoBrandProductRepository:
        """Build a repository double from auto import rows.

        Args:
            rows: Auto import rows.
            omit_mappings: Whether to omit product-category rows.
            extra_mappings: Additional product-category triples present in the fake DB.

        Returns:
            Repository double.
        """
        category_keys = {str(row["category"]) for row in rows}
        product_keys = {
            (str(row["source_provider"]), str(row["source_product_id"])) for row in rows
        }
        product_category_keys = {
            (str(row["source_provider"]), str(row["source_product_id"]), str(row["category"]))
            for row in rows
        }
        return cls(
            category_keys=category_keys,
            product_keys=product_keys,
            product_category_keys=(
                set() if omit_mappings else product_category_keys | (extra_mappings or set())
            ),
        )

    async def present_category_keys(self, category_keys: set[str]) -> set[str]:
        """Return present active category keys.

        Args:
            category_keys: Expected category keys.

        Returns:
            Present category keys.
        """
        return self.category_keys.intersection(category_keys)

    async def present_product_keys(
        self,
        product_keys: set[tuple[str, str]],
    ) -> set[tuple[str, str]]:
        """Return present product source keys.

        Args:
            product_keys: Expected product source keys.

        Returns:
            Present product keys.
        """
        return self.product_keys.intersection(product_keys)

    async def present_product_category_keys(
        self,
        product_category_keys: set[tuple[str, str, str]],
    ) -> set[tuple[str, str, str]]:
        """Return present product-category triples.

        Args:
            product_category_keys: Expected product-category triples.

        Returns:
            Present product-category triples.
        """
        return self.product_category_keys.intersection(product_category_keys)

    async def auto_product_category_keys_for_products(
        self,
        product_keys: set[tuple[str, str]],
    ) -> set[tuple[str, str, str]]:
        """Return all auto product-category triples for the expected products.

        Args:
            product_keys: Expected product source keys.

        Returns:
            Product-category triples attached to those products.
        """
        return {
            product_category_key
            for product_category_key in self.product_category_keys
            if product_category_key[:2] in product_keys
        }
