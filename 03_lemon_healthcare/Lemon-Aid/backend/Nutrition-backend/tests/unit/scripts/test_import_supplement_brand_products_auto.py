"""Tests for auto supplement brand product imports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from scripts import import_supplement_brand_products_auto as importer


def test_build_rows_plans_product_and_category_mapping_without_source_paths(
    tmp_path: Path,
) -> None:
    """Verify crawling-image folders become sanitized auto import rows.

    Args:
        tmp_path: Pytest temporary directory.
    """
    root = tmp_path / "crawling-image"
    (root / "[비타민C]" / "Sample Brand Product_123456").mkdir(parents=True)

    rows = importer.build_rows(root)

    assert len(rows) == 1
    row = rows[0]
    assert row["source_provider"] == importer.SOURCE_PROVIDER
    assert row["source_product_id"] == "123456"
    assert row["category"] == "비타민c"
    assert str(tmp_path) not in json.dumps(row, ensure_ascii=False, default=str)


def test_build_rows_uses_taxonomy_staging_category_key_contract(tmp_path: Path) -> None:
    """Verify auto product mappings use the same category keys as seed staging.

    Args:
        tmp_path: Pytest temporary directory.
    """
    root = tmp_path / "crawling-image"
    (root / "[관절_MSM_콘드로 이친]" / "Sample Brand Product_123456").mkdir(parents=True)

    rows = importer.build_rows(root)

    assert {row["category"] for row in rows} == {"관절_msm_콘드로_이친"}


def test_load_env_file_converts_asyncpg_database_url(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Verify env-file loading supports the repo's SQLAlchemy-style DB URL.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Pytest temporary directory.
    """
    monkeypatch.delenv("DATABASE_URL_PLAIN", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_DB_URL", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DATABASE_URL='postgresql+asyncpg://example:secret@example.invalid/db'\n",
        encoding="utf-8",
    )

    importer._load_env_file(env_file)

    assert importer._database_url() == "postgresql://example:secret@example.invalid/db"


def test_main_apply_uses_env_file_without_printing_database_url(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify apply mode can use env-file DSN while keeping output count-only.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Pytest temporary directory.
        capsys: Pytest stdout/stderr capture fixture.
    """
    root = tmp_path / "crawling-image"
    (root / "[비타민C]" / "Sample Brand Product_123456").mkdir(parents=True)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DATABASE_URL='postgresql+asyncpg://example:secret@example.invalid/db'\n",
        encoding="utf-8",
    )
    summary_path = tmp_path / "summary.json"
    captured_dsn: list[str] = []

    async def _fake_apply_rows(dsn: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
        """Return a fake count-only DB write summary.

        Args:
            dsn: Database URL passed by the CLI.
            rows: Auto import rows from the crawling-image fixture.

        Returns:
            Count-only fake apply summary.
        """
        captured_dsn.append(dsn)
        return {
            "rows_before": 0,
            "rows_after": len(rows),
            "distinct_brands_in_db": 1,
            "product_category_rows_before": 0,
            "product_category_rows_after": len(rows),
            "product_category_mapping_upsert_count": len(rows),
            "category_lookup_attempt_count": len(rows),
            "missing_category_mapping_count": 0,
        }

    monkeypatch.delenv("DATABASE_URL_PLAIN", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_DB_URL", raising=False)
    monkeypatch.setattr(importer, "apply_rows", _fake_apply_rows)

    assert (
        importer.main(
            [
                "--root",
                str(root),
                "--env-file",
                str(env_file),
                "--summary",
                str(summary_path),
                "--apply",
            ]
        )
        == 0
    )

    output = capsys.readouterr().out
    summary_text = summary_path.read_text(encoding="utf-8")
    assert captured_dsn == ["postgresql://example:secret@example.invalid/db"]
    assert "secret" not in output
    assert "example.invalid" not in output
    assert "secret" not in summary_text
    assert "example.invalid" not in summary_text


@pytest.mark.asyncio
async def test_apply_rows_upserts_products_and_category_mappings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify apply writes product-category mappings in the same transaction."""
    fake_conn = _FakeAsyncpgConnection()
    monkeypatch.setattr(importer.asyncpg, "connect", fake_conn.connect)
    rows = [_row("123", "vitamin-c"), _row("456", "omega-3")]

    summary = await importer.apply_rows("postgresql://example", rows)

    assert summary["rows_before"] == 0
    assert summary["rows_after"] == 2
    assert summary["product_category_rows_before"] == 0
    assert summary["product_category_rows_after"] == 2
    assert summary["product_category_mapping_upsert_count"] == 2
    assert summary["category_lookup_attempt_count"] == 2
    assert summary["missing_category_mapping_count"] == 0
    assert fake_conn.transaction.entered is True
    assert fake_conn.transaction.rolled_back is False
    assert fake_conn.closed is True
    assert len(fake_conn.mapping_execute_args) == 2

    for args in fake_conn.mapping_execute_args:
        payload = json.loads(args[6])
        assert payload["source_provider"] == importer.SOURCE_PROVIDER
        assert payload["mapping_method"] == "folder_category"
        dumped = json.dumps(payload, ensure_ascii=False)
        assert "Example Product" not in dumped
        assert "Example Manufacturer" not in dumped
        assert "/tmp" not in dumped


@pytest.mark.asyncio
async def test_apply_rows_rolls_back_when_active_category_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify missing category mappings fail closed before partial mapping writes."""
    fake_conn = _FakeAsyncpgConnection(missing_categories={"vitamin-c"})
    monkeypatch.setattr(importer.asyncpg, "connect", fake_conn.connect)

    with pytest.raises(ValueError, match="Active supplement category missing"):
        await importer.apply_rows("postgresql://example", [_row("123", "vitamin-c")])

    assert fake_conn.transaction.entered is True
    assert fake_conn.transaction.rolled_back is True
    assert fake_conn.mapping_execute_args == []
    assert fake_conn.closed is True


class _FakeAsyncpgConnection:
    """asyncpg connection double for the auto importer.

    Args:
        missing_categories: Category keys that should not resolve to an active DB row.
    """

    def __init__(self, *, missing_categories: set[str] | None = None) -> None:
        """Initialize fake connection state.

        Args:
            missing_categories: Category keys that return no active category id.
        """
        self.missing_categories = missing_categories or set()
        self.product_ids: dict[tuple[str, str], Any] = {}
        self.category_ids: dict[str, Any] = {}
        self.mapping_execute_args: list[tuple[Any, ...]] = []
        self.closed = False
        self.transaction = _FakeTransaction()

    async def connect(self, *, dsn: str) -> _FakeAsyncpgConnection:
        """Return the fake connection.

        Args:
            dsn: Ignored database URL.

        Returns:
            This fake connection.
        """
        assert dsn == "postgresql://example"
        return self

    async def fetchval(self, sql: str, *args: Any) -> Any:
        """Return deterministic query results for importer SQL.

        Args:
            sql: SQL string.
            args: Query arguments.

        Returns:
            Count or id value matching the importer query.
        """
        if "count(*) from supplement_products" in sql:
            return len(self.product_ids)
        if "count(*) from supplement_product_categories" in sql:
            return len(self.mapping_execute_args)
        if "count(distinct manufacturer)" in sql:
            return 1
        if "INSERT INTO supplement_products" in sql:
            key = (str(args[1]), str(args[2]))
            return self.product_ids.setdefault(key, args[0])
        if "FROM supplement_categories" in sql:
            category_key = str(args[0])
            if category_key in self.missing_categories:
                return None
            return self.category_ids.setdefault(category_key, uuid4())
        raise AssertionError(f"Unexpected SQL: {sql}")

    async def execute(self, sql: str, *args: Any) -> str:
        """Record product-category upsert calls.

        Args:
            sql: SQL string.
            args: Query arguments.

        Returns:
            asyncpg-style command tag.
        """
        assert "INSERT INTO supplement_product_categories" in sql
        self.mapping_execute_args.append(args)
        return "INSERT 0 1"

    async def close(self) -> None:
        """Record connection close."""
        self.closed = True


class _FakeTransaction:
    """Async transaction context manager double."""

    def __init__(self) -> None:
        """Initialize transaction state."""
        self.entered = False
        self.rolled_back = False

    def __call__(self) -> _FakeTransaction:
        """Return this transaction when asyncpg-style ``transaction()`` is called.

        Returns:
            This transaction double.
        """
        return self

    async def __aenter__(self) -> _FakeTransaction:
        """Record transaction entry.

        Returns:
            This transaction double.
        """
        self.entered = True
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        """Record rollback on exception.

        Args:
            exc_type: Exception type, if any.
            exc: Exception instance, if any.
            traceback: Traceback object, if any.
        """
        if exc_type is not None:
            self.rolled_back = True


def _row(source_product_id: str, category: str) -> dict[str, Any]:
    """Return a sanitized auto import row.

    Args:
        source_product_id: Source product id.
        category: Category key.

    Returns:
        Auto import row fixture.
    """
    return {
        "id": uuid4(),
        "source_provider": importer.SOURCE_PROVIDER,
        "source_product_id": source_product_id,
        "product_name": "Example Product",
        "normalized_product_name": "example product",
        "manufacturer": "Example Manufacturer",
        "category": category,
        "source_manifest_version": importer.SOURCE_MANIFEST_VERSION,
        "is_active": True,
    }
