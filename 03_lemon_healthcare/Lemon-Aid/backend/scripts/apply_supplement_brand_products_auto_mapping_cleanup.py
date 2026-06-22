"""Dry-run and optionally delete stale auto supplement product-category mappings.

The cleanup scope is intentionally narrow: only rows in
``supplement_product_categories`` tagged with the auto crawling-image mapping
source and attached to current auto-import products are considered. Expected
rows come from the current crawling-image folder taxonomy. Stale rows are auto
mappings whose product/category triple is no longer expected, or whose category
row is inactive.

Operator-facing summaries are count-only and hash-only. They never print source
folder labels, category keys, product names, manufacturer names, raw OCR text,
provider payloads, database URLs, local paths, or mapping UUIDs.

References:
    https://www.postgresql.org/docs/current/sql-select.html
    https://www.postgresql.org/docs/current/sql-delete.html
    https://magicstack.github.io/asyncpg/current/usage.html
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import asyncpg

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts import import_supplement_brand_products_auto as auto_import  # noqa: E402
from scripts import verify_supplement_brand_products_auto_db_import as verifier  # noqa: E402

SCHEMA_VERSION = "supplement-brand-products-auto-mapping-cleanup-v1"
CONFIRMATION_TOKEN = "delete-stale-auto-supplement-product-category-mappings"
SOURCE_DOC_URLS = (
    "https://www.postgresql.org/docs/current/sql-select.html",
    "https://www.postgresql.org/docs/current/sql-delete.html",
    "https://magicstack.github.io/asyncpg/current/usage.html",
)
LOCAL_PATH_MARKERS = verifier.LOCAL_PATH_MARKERS
RAW_FORBIDDEN_KEYS = verifier.RAW_FORBIDDEN_KEYS.union(
    {
        "category_key",
        "category_keys",
        "database_url",
        "display_name",
        "mapping_id",
        "mapping_ids",
        "product_id",
        "source_folder_name",
        "source_product_id",
    }
)

AUTO_MAPPINGS_FOR_PRODUCTS_SQL = """
SELECT pc.id, p.source_provider, p.source_product_id, c.category_key, c.is_active AS category_is_active
FROM supplement_product_categories AS pc
JOIN supplement_products AS p
  ON p.id = pc.product_id
JOIN supplement_categories AS c
  ON c.id = pc.category_id
WHERE p.source_provider=$1
  AND pc.source=$2
  AND p.source_product_id = ANY($3::text[])
  AND p.is_active=true
"""

DELETE_MAPPINGS_SQL = """
DELETE FROM supplement_product_categories
WHERE source=$1
  AND id = ANY($2::uuid[])
"""


class AutoMappingCleanupError(ValueError):
    """Raised when stale auto mapping cleanup cannot be safely applied."""


@dataclass(frozen=True)
class AutoMappingRow:
    """One redaction-safe auto mapping row kept inside the cleanup boundary.

    Args:
        mapping_id: Database mapping UUID, never printed in summaries.
        source_provider: Product source provider.
        source_product_id: Source product id, never printed in summaries.
        category_key: Category key, never printed in summaries.
        category_is_active: Whether the mapped category row is active.
    """

    mapping_id: UUID
    source_provider: str
    source_product_id: str
    category_key: str
    category_is_active: bool

    @property
    def key(self) -> tuple[str, str, str]:
        """Return the product/category triple used for expected-set comparison.

        Returns:
            Source provider, source product id, and category key.
        """
        return (self.source_provider, self.source_product_id, self.category_key)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed CLI namespace.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=auto_import.DEFAULT_ROOT)
    parser.add_argument("--dsn", default=None)
    parser.add_argument(
        "--env-file",
        type=Path,
        default=None,
        help="Optional env file used only to read DATABASE_URL_PLAIN or DATABASE_URL.",
    )
    parser.add_argument("--summary", type=Path, default=None)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--confirm-manual-cleanup",
        default="",
        help=f"Required with --apply. Exact value: {CONFIRMATION_TOKEN}",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run CLI entrypoint.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Process exit code.
    """
    return asyncio.run(run_cli(argv))


async def run_cli(argv: list[str] | None = None) -> int:
    """Build or apply the stale auto mapping cleanup plan.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Process exit code.
    """
    args = parse_args(argv)
    try:
        summary = await apply_auto_mapping_cleanup(
            root=args.root.expanduser().resolve(),
            dsn=verifier._resolve_dsn(dsn=args.dsn, env_file=args.env_file),
            apply_changes=bool(args.apply),
            confirm_manual_cleanup=args.confirm_manual_cleanup == CONFIRMATION_TOKEN,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        summary = _failure_summary(root=args.root, apply_requested=bool(args.apply), error=exc)
        if args.summary is not None:
            _write_summary(args.summary.expanduser().resolve(), summary)
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
        return 1

    if args.summary is not None:
        _write_summary(args.summary.expanduser().resolve(), summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


async def apply_auto_mapping_cleanup(
    *,
    root: Path,
    dsn: str | None,
    apply_changes: bool = False,
    confirm_manual_cleanup: bool = False,
    repository: Any | None = None,
) -> dict[str, object]:
    """Dry-run or apply stale auto product-category mapping cleanup.

    Args:
        root: Crawling-image taxonomy root.
        dsn: asyncpg-compatible database URL. Required unless repository is supplied.
        apply_changes: Whether to delete stale mapping rows.
        confirm_manual_cleanup: Explicit confirmation token check result.
        repository: Optional repository double for tests.

    Returns:
        Redacted cleanup summary.

    Raises:
        AutoMappingCleanupError: If cleanup inputs or write conditions are unsafe.
        ValueError: If a database URL is required but absent.
    """
    rows = auto_import.build_rows(root)
    if not rows:
        raise ValueError("Auto mapping cleanup requires at least one source row.")
    expected_product_keys = verifier._expected_product_keys(rows)
    expected_product_category_keys = verifier._expected_product_category_keys(rows)

    if repository is not None:
        return await _cleanup_with_repository(
            root=root,
            expected_product_keys=expected_product_keys,
            expected_product_category_keys=expected_product_category_keys,
            repository=repository,
            apply_changes=apply_changes,
            confirm_manual_cleanup=confirm_manual_cleanup,
        )
    if not dsn:
        raise ValueError("DATABASE_URL_PLAIN or --dsn is required for DB cleanup.")

    conn = await asyncpg.connect(dsn=dsn)
    try:
        repository = _AsyncpgAutoMappingCleanupRepository(conn=conn)
        if apply_changes:
            async with conn.transaction():
                return await _cleanup_with_repository(
                    root=root,
                    expected_product_keys=expected_product_keys,
                    expected_product_category_keys=expected_product_category_keys,
                    repository=repository,
                    apply_changes=apply_changes,
                    confirm_manual_cleanup=confirm_manual_cleanup,
                )
        return await _cleanup_with_repository(
            root=root,
            expected_product_keys=expected_product_keys,
            expected_product_category_keys=expected_product_category_keys,
            repository=repository,
            apply_changes=apply_changes,
            confirm_manual_cleanup=confirm_manual_cleanup,
        )
    finally:
        await conn.close()


async def _cleanup_with_repository(
    *,
    root: Path,
    expected_product_keys: set[tuple[str, str]],
    expected_product_category_keys: set[tuple[str, str, str]],
    repository: Any,
    apply_changes: bool,
    confirm_manual_cleanup: bool,
) -> dict[str, object]:
    """Run cleanup through a repository boundary.

    Args:
        root: Crawling-image taxonomy root.
        expected_product_keys: Expected auto product source keys.
        expected_product_category_keys: Expected product/category triples.
        repository: DB repository or test double.
        apply_changes: Whether to delete stale rows.
        confirm_manual_cleanup: Explicit confirmation token check result.

    Returns:
        Redacted cleanup summary.

    Raises:
        AutoMappingCleanupError: If apply is requested without confirmation, or
            if delete counts do not match the approved plan.
    """
    actual_rows = await repository.auto_mappings_for_products(expected_product_keys)
    stale_rows = _stale_rows(
        actual_rows=actual_rows,
        expected_product_category_keys=expected_product_category_keys,
    )
    summary = _summary(
        root=root,
        expected_product_count=len(expected_product_keys),
        expected_product_category_count=len(expected_product_category_keys),
        actual_rows=actual_rows,
        stale_rows=stale_rows,
        apply_requested=apply_changes,
        confirm_manual_cleanup=confirm_manual_cleanup,
    )
    if not apply_changes:
        _reject_unsafe_payload(summary)
        return summary
    if stale_rows and not confirm_manual_cleanup:
        raise AutoMappingCleanupError("Manual cleanup confirmation token is required.")
    if not stale_rows:
        summary["status"] = "no_cleanup_required"
        summary["preflight_only"] = False
        _reject_unsafe_payload(summary)
        return summary

    try:
        deleted_count = await repository.delete_mappings([row.mapping_id for row in stale_rows])
        await repository.commit()
    except Exception:
        await repository.rollback()
        raise
    if deleted_count != len(stale_rows):
        raise AutoMappingCleanupError("Cleanup delete count did not match the approved plan.")
    summary["status"] = "manual_auto_mapping_cleanup_applied"
    summary["preflight_only"] = False
    summary["db_write_performed"] = True
    summary["db_delete_performed"] = True
    summary["deleted_product_category_mapping_count"] = deleted_count
    _reject_unsafe_payload(summary)
    return summary


class _AsyncpgAutoMappingCleanupRepository:
    """asyncpg repository for stale auto mapping cleanup.

    Args:
        conn: Open asyncpg connection.
    """

    def __init__(self, *, conn: Any) -> None:
        """Initialize repository.

        Args:
            conn: Open asyncpg connection.
        """
        self._conn = conn

    async def auto_mappings_for_products(
        self,
        product_keys: set[tuple[str, str]],
    ) -> list[AutoMappingRow]:
        """Return auto mappings for current expected source products.

        Args:
            product_keys: Expected source product keys.

        Returns:
            Auto mapping rows.
        """
        source_product_ids = [product_id for _provider, product_id in product_keys]
        rows = await self._conn.fetch(
            AUTO_MAPPINGS_FOR_PRODUCTS_SQL,
            auto_import.SOURCE_PROVIDER,
            auto_import.PRODUCT_CATEGORY_SOURCE,
            source_product_ids,
        )
        return [
            AutoMappingRow(
                mapping_id=row["id"],
                source_provider=str(row["source_provider"]),
                source_product_id=str(row["source_product_id"]),
                category_key=str(row["category_key"]),
                category_is_active=bool(row["category_is_active"]),
            )
            for row in rows
        ]

    async def delete_mappings(self, mapping_ids: list[UUID]) -> int:
        """Delete approved stale auto mapping rows.

        Args:
            mapping_ids: Mapping ids selected by the approved plan.

        Returns:
            Number of deleted rows.
        """
        result = await self._conn.execute(
            DELETE_MAPPINGS_SQL,
            auto_import.PRODUCT_CATEGORY_SOURCE,
            mapping_ids,
        )
        return _parse_command_row_count(result)

    async def commit(self) -> None:
        """Commit the current transaction when available."""
        # asyncpg autocommits outside transaction blocks. This method keeps the
        # repository protocol aligned with test doubles and future transactions.

    async def rollback(self) -> None:
        """Rollback the current transaction when available."""
        # asyncpg autocommits outside transaction blocks. Delete is one command.


def _stale_rows(
    *,
    actual_rows: list[AutoMappingRow],
    expected_product_category_keys: set[tuple[str, str, str]],
) -> list[AutoMappingRow]:
    """Return stale auto mapping rows.

    Args:
        actual_rows: Actual auto mappings for expected products.
        expected_product_category_keys: Current expected product/category triples.

    Returns:
        Stale mapping rows.
    """
    return sorted(
        [
            row
            for row in actual_rows
            if row.key not in expected_product_category_keys or not row.category_is_active
        ],
        key=lambda row: _hash_mapping_key(row.key),
    )


def _summary(
    *,
    root: Path,
    expected_product_count: int,
    expected_product_category_count: int,
    actual_rows: list[AutoMappingRow],
    stale_rows: list[AutoMappingRow],
    apply_requested: bool,
    confirm_manual_cleanup: bool,
) -> dict[str, object]:
    """Build a redacted cleanup summary.

    Args:
        root: Crawling-image taxonomy root.
        expected_product_count: Expected product count.
        expected_product_category_count: Expected product/category mapping count.
        actual_rows: DB auto mapping rows.
        stale_rows: Stale DB auto mapping rows.
        apply_requested: Whether apply mode was requested.
        confirm_manual_cleanup: Whether explicit confirmation was supplied.

    Returns:
        Count-only and hash-only summary.
    """
    stale_count = len(stale_rows)
    status = "no_cleanup_required" if not stale_count else "ready_for_manual_auto_mapping_cleanup"
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": status,
        "source_provider": auto_import.SOURCE_PROVIDER,
        "mapping_source": auto_import.PRODUCT_CATEGORY_SOURCE,
        "source_manifest_version": auto_import.SOURCE_MANIFEST_VERSION,
        "source_root_name": root.name,
        "source_root_hash": _sha256_text(str(root.expanduser())),
        "expected_product_count": expected_product_count,
        "expected_product_category_count": expected_product_category_count,
        "db_auto_mapping_count_for_expected_products": len(actual_rows),
        "stale_product_category_mapping_count": stale_count,
        "inactive_category_mapping_count": sum(
            1 for row in stale_rows if not row.category_is_active
        ),
        "unexpected_category_mapping_count": sum(1 for row in stale_rows if row.category_is_active),
        "stale_product_category_key_hashes": [_hash_mapping_key(row.key) for row in stale_rows],
        "cleanup_required": bool(stale_rows),
        "cleanup_plan": {
            "target_table": "supplement_product_categories",
            "operation": "delete_stale_auto_product_category_mappings",
            "selector": "stale_product_category_key_hashes",
            "manual_approval_required": bool(stale_rows),
            "safe_without_operator_review": False,
        },
        "apply_requested": apply_requested,
        "manual_cleanup_confirmation_provided": confirm_manual_cleanup,
        "preflight_only": not apply_requested,
        "db_write_performed": False,
        "db_delete_performed": False,
        "deleted_product_category_mapping_count": 0,
        "database_url_printed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "local_paths_printed": False,
        "category_literals_printed": False,
        "product_names_printed": False,
        "manufacturer_names_printed": False,
        "source_doc_urls": list(SOURCE_DOC_URLS),
    }


def _failure_summary(*, root: Path, apply_requested: bool, error: Exception) -> dict[str, object]:
    """Build a redacted failure summary.

    Args:
        root: Requested crawling-image root.
        apply_requested: Whether apply was requested.
        error: Raised exception.

    Returns:
        Count-only failure summary.
    """
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "error",
        "source_root_name": root.name,
        "source_root_hash": _sha256_text(str(root.expanduser())),
        "apply_requested": apply_requested,
        "error_type": type(error).__name__,
        "public_error_code": _safe_error_code(error),
        "db_write_performed": False,
        "db_delete_performed": False,
        "database_url_printed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "local_paths_printed": False,
        "category_literals_printed": False,
        "source_doc_urls": list(SOURCE_DOC_URLS),
    }
    _reject_unsafe_payload(summary)
    return summary


def _parse_command_row_count(command_tag: str) -> int:
    """Parse an asyncpg command tag row count.

    Args:
        command_tag: Command tag such as ``DELETE 3``.

    Returns:
        Parsed row count, or zero when no count is present.
    """
    parts = command_tag.split()
    if not parts:
        return 0
    try:
        return int(parts[-1])
    except ValueError:
        return 0


def _safe_error_code(error: Exception) -> str:
    """Return a bounded public error code.

    Args:
        error: Raised exception.

    Returns:
        Public error code.
    """
    if isinstance(error, OSError):
        return "local_file_operation_error"
    if isinstance(error, json.JSONDecodeError):
        return "json_decode_error"
    return "validation_error"


def _write_summary(path: Path, summary: dict[str, object]) -> None:
    """Write summary JSON.

    Args:
        path: Destination path.
        summary: Summary payload.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _hash_mapping_key(value: tuple[str, str, str]) -> str:
    """Return a short hash for a product/category mapping key."""
    return _sha256_text("::".join(value))[:16]


def _sha256_text(value: str) -> str:
    """Return SHA-256 digest for text."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _reject_unsafe_payload(value: Any) -> None:
    """Reject summaries that expose local paths or raw/private keys.

    Args:
        value: JSON-like payload.

    Raises:
        ValueError: If unsafe values are found.
    """
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True)
    for marker in LOCAL_PATH_MARKERS:
        if marker in serialized:
            raise ValueError("Auto mapping cleanup summary contains a local path.")
    _reject_raw_keys(value)


def _reject_raw_keys(value: Any) -> None:
    """Recursively reject raw/private payload keys."""
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).casefold() in RAW_FORBIDDEN_KEYS:
                raise ValueError(f"Auto mapping cleanup summary contains raw key: {key}")
            _reject_raw_keys(child)
    elif isinstance(value, list):
        for child in value:
            _reject_raw_keys(child)


if __name__ == "__main__":
    raise SystemExit(main())
