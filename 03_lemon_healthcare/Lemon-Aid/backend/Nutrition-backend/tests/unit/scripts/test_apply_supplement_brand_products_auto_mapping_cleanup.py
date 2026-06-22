"""Tests for stale auto supplement product-category mapping cleanup."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

auto_import = importlib.import_module("scripts.import_supplement_brand_products_auto")
cleanup = importlib.import_module("scripts.apply_supplement_brand_products_auto_mapping_cleanup")


def _source_root(tmp_path: Path) -> Path:
    """Create a small crawling-image tree fixture.

    Args:
        tmp_path: Temporary directory.

    Returns:
        Crawling-image root path.
    """
    root = tmp_path / "crawling-image"
    (root / "[비타민C]" / "Sample Brand Product_123456").mkdir(parents=True)
    return root


@pytest.mark.asyncio
async def test_auto_mapping_cleanup_dry_run_reports_stale_hash_only(
    tmp_path: Path,
) -> None:
    """Verify dry-run identifies stale mappings without leaking source literals."""
    root = _source_root(tmp_path)
    rows = auto_import.build_rows(root)
    expected_row = rows[0]
    repository = _FakeAutoMappingCleanupRepository(
        rows=[
            _mapping_row(
                source_product_id=str(expected_row["source_product_id"]),
                category_key=str(expected_row["category"]),
            ),
            _mapping_row(
                source_product_id=str(expected_row["source_product_id"]),
                category_key="legacy-extra",
            ),
        ]
    )

    summary = await cleanup.apply_auto_mapping_cleanup(
        root=root,
        dsn=None,
        repository=repository,
    )
    dumped = json.dumps(summary, ensure_ascii=False)

    assert summary["status"] == "ready_for_manual_auto_mapping_cleanup"
    assert summary["expected_product_count"] == 1
    assert summary["expected_product_category_count"] == 1
    assert summary["db_auto_mapping_count_for_expected_products"] == 2
    assert summary["stale_product_category_mapping_count"] == 1
    assert summary["unexpected_category_mapping_count"] == 1
    assert len(summary["stale_product_category_key_hashes"]) == 1
    assert summary["db_write_performed"] is False
    assert summary["db_delete_performed"] is False
    assert "legacy-extra" not in dumped
    assert str(expected_row["source_product_id"]) not in dumped
    assert str(tmp_path) not in dumped


@pytest.mark.asyncio
async def test_auto_mapping_cleanup_reports_no_cleanup_when_exact(
    tmp_path: Path,
) -> None:
    """Verify exact auto mappings produce a no-cleanup summary."""
    root = _source_root(tmp_path)
    rows = auto_import.build_rows(root)
    expected_row = rows[0]
    repository = _FakeAutoMappingCleanupRepository(
        rows=[
            _mapping_row(
                source_product_id=str(expected_row["source_product_id"]),
                category_key=str(expected_row["category"]),
            )
        ]
    )

    summary = await cleanup.apply_auto_mapping_cleanup(
        root=root,
        dsn=None,
        repository=repository,
    )

    assert summary["status"] == "no_cleanup_required"
    assert summary["stale_product_category_mapping_count"] == 0
    assert summary["cleanup_required"] is False


@pytest.mark.asyncio
async def test_auto_mapping_cleanup_apply_requires_confirmation(
    tmp_path: Path,
) -> None:
    """Verify stale mapping delete cannot run without manual confirmation."""
    root = _source_root(tmp_path)
    rows = auto_import.build_rows(root)
    repository = _FakeAutoMappingCleanupRepository(
        rows=[
            _mapping_row(
                source_product_id=str(rows[0]["source_product_id"]),
                category_key="legacy-extra",
            )
        ]
    )

    with pytest.raises(cleanup.AutoMappingCleanupError, match="confirmation"):
        await cleanup.apply_auto_mapping_cleanup(
            root=root,
            dsn=None,
            repository=repository,
            apply_changes=True,
            confirm_manual_cleanup=False,
        )

    assert repository.deleted_batches == []


@pytest.mark.asyncio
async def test_auto_mapping_cleanup_apply_deletes_and_commits(
    tmp_path: Path,
) -> None:
    """Verify confirmed cleanup deletes only planned stale mappings."""
    root = _source_root(tmp_path)
    rows = auto_import.build_rows(root)
    expected_row = rows[0]
    stale = _mapping_row(
        source_product_id=str(expected_row["source_product_id"]),
        category_key="legacy-extra",
    )
    repository = _FakeAutoMappingCleanupRepository(
        rows=[
            _mapping_row(
                source_product_id=str(expected_row["source_product_id"]),
                category_key=str(expected_row["category"]),
            ),
            stale,
        ]
    )

    summary = await cleanup.apply_auto_mapping_cleanup(
        root=root,
        dsn=None,
        repository=repository,
        apply_changes=True,
        confirm_manual_cleanup=True,
    )

    assert summary["status"] == "manual_auto_mapping_cleanup_applied"
    assert summary["db_write_performed"] is True
    assert summary["db_delete_performed"] is True
    assert summary["deleted_product_category_mapping_count"] == 1
    assert repository.deleted_batches == [[stale.mapping_id]]
    assert repository.commit_count == 1
    assert repository.rollback_count == 0


@pytest.mark.asyncio
async def test_auto_mapping_cleanup_apply_rolls_back_on_delete_failure(
    tmp_path: Path,
) -> None:
    """Verify cleanup rolls back repository failures."""
    root = _source_root(tmp_path)
    rows = auto_import.build_rows(root)
    repository = _FakeAutoMappingCleanupRepository(
        rows=[
            _mapping_row(
                source_product_id=str(rows[0]["source_product_id"]),
                category_key="legacy-extra",
            )
        ],
        raise_on_delete=True,
    )

    with pytest.raises(RuntimeError, match="delete failed"):
        await cleanup.apply_auto_mapping_cleanup(
            root=root,
            dsn=None,
            repository=repository,
            apply_changes=True,
            confirm_manual_cleanup=True,
        )

    assert repository.commit_count == 0
    assert repository.rollback_count == 1


class _FakeAutoMappingCleanupRepository:
    """Repository double for stale auto mapping cleanup tests.

    Args:
        rows: Auto mapping rows returned by the fake DB.
        raise_on_delete: Whether delete should fail.
    """

    def __init__(
        self,
        *,
        rows: list[Any],
        raise_on_delete: bool = False,
    ) -> None:
        """Initialize the fake repository.

        Args:
            rows: Auto mapping rows.
            raise_on_delete: Whether delete should fail.
        """
        self.rows = rows
        self.raise_on_delete = raise_on_delete
        self.deleted_batches: list[list[UUID]] = []
        self.commit_count = 0
        self.rollback_count = 0

    async def auto_mappings_for_products(
        self,
        product_keys: set[tuple[str, str]],
    ) -> list[Any]:
        """Return fake mapping rows for the requested source products.

        Args:
            product_keys: Expected product source keys.

        Returns:
            Matching fake rows.
        """
        return [row for row in self.rows if row.key[:2] in product_keys]

    async def delete_mappings(self, mapping_ids: list[UUID]) -> int:
        """Record mapping delete batches.

        Args:
            mapping_ids: Mapping IDs selected by cleanup.

        Returns:
            Deleted count.

        Raises:
            RuntimeError: When configured to simulate DB failure.
        """
        if self.raise_on_delete:
            raise RuntimeError("delete failed")
        self.deleted_batches.append(mapping_ids)
        return len(mapping_ids)

    async def commit(self) -> None:
        """Record commit calls."""
        self.commit_count += 1

    async def rollback(self) -> None:
        """Record rollback calls."""
        self.rollback_count += 1


def _mapping_row(
    *,
    source_product_id: str,
    category_key: str,
    category_is_active: bool = True,
) -> Any:
    """Build an auto mapping row fixture.

    Args:
        source_product_id: Source product ID.
        category_key: Category key.
        category_is_active: Whether category is active.

    Returns:
        Auto mapping row.
    """
    return cleanup.AutoMappingRow(
        mapping_id=uuid4(),
        source_provider=auto_import.SOURCE_PROVIDER,
        source_product_id=source_product_id,
        category_key=category_key,
        category_is_active=category_is_active,
    )
