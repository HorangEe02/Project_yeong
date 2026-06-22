"""Verify taxo59 food catalog and nutrition rows in PostgreSQL.

This verifier is intentionally read-only. It checks whether the teammate-provided
taxo59 CSV has been represented in the Lemon-Aid catalog tables without printing
food names, database URLs, local paths, raw OCR text, or provider payloads.

References:
    https://www.postgresql.org/docs/current/sql-select.html
    https://magicstack.github.io/asyncpg/current/usage.html
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import asyncpg

SCHEMA_VERSION = "food-taxo59-db-verification-v1"
EXPECTED_TAXO59_ROW_COUNT = 59
SOURCE = "aihub_taxo59_csv"
SOURCE_DOC_URLS = (
    "https://www.postgresql.org/docs/current/sql-select.html",
    "https://magicstack.github.io/asyncpg/current/usage.html",
)
LOCAL_PATH_MARKERS = (
    "/private/",
    "/Users/",
    "/Volumes/",
    "file://",
    "\\Users\\",
    "\\Volumes\\",
)
RAW_FORBIDDEN_KEYS = frozenset(
    {
        "api_key",
        "authorization",
        "database_url",
        "image_bytes",
        "ocr_text",
        "owner_hash",
        "owner_subject",
        "provider_payload",
        "raw_image",
        "raw_ocr_text",
        "request_headers",
        "service_key",
    }
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed CLI namespace.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=None)
    parser.add_argument("--summary", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Run the read-only verifier CLI.

    Args:
        argv: Optional argument list for tests.
    """
    raise SystemExit(asyncio.run(run_cli(argv)))


async def run_cli(argv: list[str] | None = None) -> int:
    """Execute verification and write a redacted summary.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Process exit code.
    """
    args = parse_args(argv)
    try:
        if args.env_file is not None:
            _load_env_file(args.env_file.expanduser().resolve())
        summary = await verify_food_taxo59_db_import()
    except (OSError, RuntimeError, asyncpg.PostgresError) as exc:
        summary = _failure_summary(exc)
        _write_summary(args.summary.expanduser().resolve(), summary)
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
        return 1

    _write_summary(args.summary.expanduser().resolve(), summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["status"] in {"verified", "catalog_verified_typed_table_missing"} else 1


async def verify_food_taxo59_db_import() -> dict[str, object]:
    """Read current DB counts for taxo59 food catalog/nutrition storage.

    Returns:
        Redacted verification summary.

    Raises:
        RuntimeError: If no database URL is configured.
        asyncpg.PostgresError: If PostgreSQL rejects a read-only query.
    """
    conn = await asyncpg.connect(_database_url())
    try:
        food_nutrition_exists = bool(await conn.fetchval("""
                SELECT EXISTS(
                    SELECT 1
                      FROM information_schema.tables
                     WHERE table_schema = 'public'
                       AND table_name = 'food_nutrition'
                )
                """))
        catalog_count = int(
            await conn.fetchval(
                """
                SELECT count(*)
                  FROM food_catalog_items
                 WHERE source = $1
                   AND is_active = true
                """,
                SOURCE,
            )
        )
        catalog_with_nutrition_count = int(
            await conn.fetchval(
                """
                SELECT count(*)
                  FROM food_catalog_items
                 WHERE source = $1
                   AND is_active = true
                   AND nutrition_reference <> '{}'::jsonb
                """,
                SOURCE,
            )
        )
        typed_active_count = 0
        typed_linked_count = 0
        if food_nutrition_exists:
            typed_active_count = int(
                await conn.fetchval(
                    """
                    SELECT count(*)
                      FROM food_nutrition
                     WHERE source = $1
                       AND is_active = true
                    """,
                    SOURCE,
                )
            )
            typed_linked_count = int(
                await conn.fetchval(
                    """
                    SELECT count(*)
                      FROM food_nutrition
                     WHERE source = $1
                       AND is_active = true
                       AND food_catalog_item_id IS NOT NULL
                    """,
                    SOURCE,
                )
            )
    finally:
        await conn.close()

    catalog_verified = (
        catalog_count == EXPECTED_TAXO59_ROW_COUNT
        and catalog_with_nutrition_count == EXPECTED_TAXO59_ROW_COUNT
    )
    typed_verified = (
        food_nutrition_exists
        and typed_active_count == EXPECTED_TAXO59_ROW_COUNT
        and typed_linked_count == EXPECTED_TAXO59_ROW_COUNT
    )
    status = _status(catalog_verified=catalog_verified, typed_verified=typed_verified)
    summary: dict[str, object] = {
        "catalog_db_import_verified": catalog_verified,
        "catalog_with_nutrition_reference_count": catalog_with_nutrition_count,
        "database_url_printed": False,
        "db_write_performed": False,
        "expected_taxo59_row_count": EXPECTED_TAXO59_ROW_COUNT,
        "food_catalog_active_count": catalog_count,
        "food_nutrition_active_count": typed_active_count,
        "food_nutrition_linked_catalog_count": typed_linked_count,
        "food_nutrition_table_exists": food_nutrition_exists,
        "generated_at": datetime.now(UTC).isoformat(),
        "local_paths_printed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "schema_version": SCHEMA_VERSION,
        "source_doc_urls": list(SOURCE_DOC_URLS),
        "source_provider": SOURCE,
        "status": status,
        "typed_food_nutrition_verified": typed_verified,
    }
    _reject_unsafe_payload(summary)
    return summary


def _status(*, catalog_verified: bool, typed_verified: bool) -> str:
    """Classify verification without conflating catalog and typed table state."""
    if catalog_verified and typed_verified:
        return "verified"
    if catalog_verified:
        return "catalog_verified_typed_table_missing"
    return "not_verified"


def _database_url() -> str:
    """Return a driver-compatible database URL without printing it.

    Raises:
        RuntimeError: If no supported DB URL variable exists.
    """
    value = (
        os.environ.get("DATABASE_URL_PLAIN")
        or os.environ.get("DATABASE_URL")
        or os.environ.get("SUPABASE_DB_URL")
    )
    if not value:
        raise RuntimeError("database_url_missing")
    return value.replace("postgresql+asyncpg://", "postgresql://", 1)


def _load_env_file(path: Path) -> None:
    """Load simple KEY=VALUE lines from an env file without echoing values."""
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def _failure_summary(error: BaseException) -> dict[str, object]:
    """Build a redacted failure summary.

    Args:
        error: Exception that prevented verification.

    Returns:
        Redacted failure summary.
    """
    return {
        "database_url_printed": False,
        "db_write_performed": False,
        "error_type": type(error).__name__,
        "generated_at": datetime.now(UTC).isoformat(),
        "local_paths_printed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "schema_version": SCHEMA_VERSION,
        "source_doc_urls": list(SOURCE_DOC_URLS),
        "status": "error",
    }


def _write_summary(path: Path, summary: dict[str, object]) -> None:
    """Write a redacted JSON summary."""
    _reject_unsafe_payload(summary)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _reject_unsafe_payload(value: Any) -> None:
    """Fail closed if a summary would leak local paths, secrets, or raw payloads."""
    if isinstance(value, dict):
        for key, item in value.items():
            if key in RAW_FORBIDDEN_KEYS:
                raise ValueError(f"unsafe summary key: {key}")
            _reject_unsafe_payload(item)
        return
    if isinstance(value, list | tuple):
        for item in value:
            _reject_unsafe_payload(item)
        return
    if isinstance(value, str) and any(marker in value for marker in LOCAL_PATH_MARKERS):
        raise ValueError("unsafe local path in summary")


if __name__ == "__main__":
    main()
