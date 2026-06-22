"""Verify auto supplement brand product imports against reference DB tables.

This read-only verifier checks the AUTO import path produced by
``import_supplement_brand_products_auto.py``. It confirms that expected
``supplement_products`` rows and their ``supplement_product_categories``
mappings exist without printing product names, manufacturer names, database
URLs, local paths, raw OCR text, or provider payloads.

References:
    https://www.postgresql.org/docs/current/sql-select.html
    https://magicstack.github.io/asyncpg/current/usage.html
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import asyncpg

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts import import_supplement_brand_products_auto as auto_import  # noqa: E402

SCHEMA_VERSION = "supplement-brand-products-auto-db-verification-v1"
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
        "object_uri",
        "ocr_text",
        "owner_hash",
        "owner_subject",
        "provider_payload",
        "raw_image",
        "raw_ocr",
        "raw_ocr_text",
        "request_headers",
        "service_key",
    }
)
MIN_QUOTED_VALUE_LENGTH = 2
AUTO_PRODUCT_KEYS_SQL = """
SELECT source_provider, source_product_id
FROM supplement_products
WHERE source_provider=$1
  AND source_product_id = ANY($2::text[])
  AND is_active=true
"""
AUTO_PRODUCT_CATEGORY_KEYS_SQL = """
SELECT p.source_provider, p.source_product_id, c.category_key
FROM supplement_products AS p
JOIN supplement_product_categories AS pc
  ON pc.product_id = p.id
JOIN supplement_categories AS c
  ON c.id = pc.category_id
WHERE p.source_provider=$1
  AND pc.source=$2
  AND p.source_product_id = ANY($3::text[])
  AND c.category_key = ANY($4::text[])
  AND p.is_active=true
  AND c.is_active=true
"""
AUTO_PRODUCT_CATEGORY_KEYS_FOR_PRODUCTS_SQL = """
SELECT p.source_provider, p.source_product_id, c.category_key
FROM supplement_products AS p
JOIN supplement_product_categories AS pc
  ON pc.product_id = p.id
JOIN supplement_categories AS c
  ON c.id = pc.category_id
WHERE p.source_provider=$1
  AND pc.source=$2
  AND p.source_product_id = ANY($3::text[])
  AND p.is_active=true
"""
ACTIVE_CATEGORY_KEYS_SQL = """
SELECT category_key
FROM supplement_categories
WHERE category_key = ANY($1::text[])
  AND is_active=true
"""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional argument vector for tests.

    Returns:
        Parsed CLI namespace.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=auto_import.DEFAULT_ROOT)
    parser.add_argument("--dsn", default=os.environ.get("DATABASE_URL_PLAIN"))
    parser.add_argument(
        "--env-file",
        type=Path,
        default=None,
        help="Optional env file used only to read DATABASE_URL_PLAIN or DATABASE_URL.",
    )
    parser.add_argument("--summary", type=Path, default=None)
    parser.add_argument(
        "--fail-on-missing",
        action="store_true",
        help="Exit non-zero if expected products or mappings are missing.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run CLI entrypoint.

    Args:
        argv: Optional argument vector for tests.

    Returns:
        Process exit code.
    """
    return asyncio.run(run_cli(argv))


async def run_cli(argv: list[str] | None = None) -> int:
    """Verify auto import state and print a redacted summary.

    Args:
        argv: Optional argument vector for tests.

    Returns:
        Process exit code.
    """
    args = parse_args(argv)
    try:
        summary = await verify_auto_brand_product_db_import(
            root=args.root.expanduser().resolve(),
            dsn=_resolve_dsn(dsn=args.dsn, env_file=args.env_file),
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        summary = _failure_summary(root=args.root, error=exc)
        if args.summary is not None:
            _write_summary(args.summary.expanduser().resolve(), summary)
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
        return 1

    if args.summary is not None:
        _write_summary(args.summary.expanduser().resolve(), summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if args.fail_on_missing and not summary["db_import_verified"]:
        return 1
    return 0


async def verify_auto_brand_product_db_import(
    *,
    root: Path,
    dsn: str | None,
    repository: Any | None = None,
) -> dict[str, object]:
    """Verify expected auto product and product-category DB rows.

    Args:
        root: Crawling-image root.
        dsn: asyncpg-compatible database URL. Required unless repository is supplied.
        repository: Optional read-only repository double for tests.

    Returns:
        Count-only verification summary.

    Raises:
        ValueError: If no DSN is available, source rows are empty, or output is unsafe.
    """
    rows = auto_import.build_rows(root)
    if not rows:
        raise ValueError("Auto brand product verification requires at least one source row.")
    expected_product_keys = _expected_product_keys(rows)
    expected_category_keys = _expected_category_keys(rows)
    expected_product_category_keys = _expected_product_category_keys(rows)

    repo = repository
    if repo is None:
        if not dsn:
            raise ValueError(
                "DATABASE_URL_PLAIN or --dsn is required for read-only DB verification."
            )
        conn = await asyncpg.connect(dsn=dsn)
        try:
            repo = _AsyncpgAutoBrandProductVerificationRepository(conn=conn)
            return await _verify_with_repository(
                root=root,
                rows=rows,
                expected_product_keys=expected_product_keys,
                expected_category_keys=expected_category_keys,
                expected_product_category_keys=expected_product_category_keys,
                repository=repo,
            )
        finally:
            await conn.close()

    return await _verify_with_repository(
        root=root,
        rows=rows,
        expected_product_keys=expected_product_keys,
        expected_category_keys=expected_category_keys,
        expected_product_category_keys=expected_product_category_keys,
        repository=repo,
    )


async def _verify_with_repository(
    *,
    root: Path,
    rows: list[dict[str, Any]],
    expected_product_keys: set[tuple[str, str]],
    expected_category_keys: set[str],
    expected_product_category_keys: set[tuple[str, str, str]],
    repository: Any,
) -> dict[str, object]:
    """Verify source rows through a read-only repository boundary.

    Args:
        root: Crawling-image root.
        rows: Auto import source rows.
        expected_product_keys: Expected product source keys.
        expected_category_keys: Expected category keys.
        expected_product_category_keys: Expected source product/category triples.
        repository: Read-only DB repository.

    Returns:
        Redacted verification summary.
    """
    present_category_keys = await repository.present_category_keys(expected_category_keys)
    present_product_keys = await repository.present_product_keys(expected_product_keys)
    present_product_category_keys = await repository.present_product_category_keys(
        expected_product_category_keys
    )
    actual_product_category_keys = await repository.auto_product_category_keys_for_products(
        expected_product_keys
    )

    missing_category_keys = sorted(expected_category_keys - present_category_keys)
    missing_product_keys = sorted(expected_product_keys - present_product_keys)
    missing_product_category_keys = sorted(
        expected_product_category_keys - present_product_category_keys
    )
    stale_product_category_keys = sorted(
        actual_product_category_keys - expected_product_category_keys
    )
    blocker_codes = _blocked_reason_codes(
        missing_category_keys=missing_category_keys,
        missing_product_keys=missing_product_keys,
        missing_product_category_keys=missing_product_category_keys,
    )
    verified = not blocker_codes
    cleanup_recommended = bool(stale_product_category_keys)
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": _status(
            verified=verified,
            cleanup_recommended=cleanup_recommended,
        ),
        "source_provider": auto_import.SOURCE_PROVIDER,
        "mapping_source": auto_import.PRODUCT_CATEGORY_SOURCE,
        "source_manifest_version": auto_import.SOURCE_MANIFEST_VERSION,
        "source_root_name": root.name,
        "source_root_hash": _sha256_text(str(root.expanduser())),
        "expected_category_count": len(expected_category_keys),
        "matched_category_count": len(present_category_keys),
        "missing_category_count": len(missing_category_keys),
        "missing_category_key_hashes": [_sha256_text(key) for key in missing_category_keys],
        "expected_product_count": len(expected_product_keys),
        "matched_product_count": len(present_product_keys),
        "missing_product_count": len(missing_product_keys),
        "missing_product_key_hashes": [
            _sha256_text("::".join(source_key)) for source_key in missing_product_keys
        ],
        "expected_product_category_count": len(expected_product_category_keys),
        "matched_product_category_count": len(present_product_category_keys),
        "actual_auto_product_category_count_for_expected_products": len(
            actual_product_category_keys
        ),
        "missing_product_category_count": len(missing_product_category_keys),
        "missing_product_category_key_hashes": [
            _sha256_text("::".join(source_category_key))
            for source_category_key in missing_product_category_keys
        ],
        "stale_product_category_mapping_count": len(stale_product_category_keys),
        "stale_product_category_key_hashes": [
            _sha256_text("::".join(source_category_key))
            for source_category_key in stale_product_category_keys
        ],
        "cleanup_recommended": cleanup_recommended,
        "cleanup_plan": {
            "target_table": "supplement_product_categories",
            "operation": "delete_stale_auto_product_category_mappings",
            "selector": "stale_product_category_key_hashes",
            "manual_approval_required": cleanup_recommended,
            "safe_without_operator_review": False,
        },
        "product_row_count": len(rows),
        "with_manufacturer": sum(1 for row in rows if row.get("manufacturer")),
        "manufacturer_null_needs_review": sum(1 for row in rows if not row.get("manufacturer")),
        "db_import_verified": verified,
        "blocked_reason_codes": blocker_codes,
        "db_write_performed": False,
        "database_url_printed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "local_paths_printed": False,
        "product_names_printed": False,
        "manufacturer_names_printed": False,
        "source_doc_urls": list(SOURCE_DOC_URLS),
    }
    _reject_unsafe_payload(summary)
    return summary


class _AsyncpgAutoBrandProductVerificationRepository:
    """asyncpg read-only repository for auto brand product verification.

    Args:
        conn: Open asyncpg connection.
    """

    def __init__(self, *, conn: Any) -> None:
        """Initialize repository.

        Args:
            conn: Open asyncpg connection.
        """
        self._conn = conn

    async def present_category_keys(self, category_keys: set[str]) -> set[str]:
        """Return active category keys present in the DB.

        Args:
            category_keys: Expected category keys.

        Returns:
            Present active category keys.
        """
        rows = await self._conn.fetch(ACTIVE_CATEGORY_KEYS_SQL, list(category_keys))
        return {str(row["category_key"]) for row in rows}

    async def present_product_keys(
        self,
        product_keys: set[tuple[str, str]],
    ) -> set[tuple[str, str]]:
        """Return active auto product source keys present in the DB.

        Args:
            product_keys: Expected product source keys.

        Returns:
            Present source key pairs.
        """
        source_product_ids = [product_id for _provider, product_id in product_keys]
        rows = await self._conn.fetch(
            AUTO_PRODUCT_KEYS_SQL,
            auto_import.SOURCE_PROVIDER,
            source_product_ids,
        )
        return {(str(row["source_provider"]), str(row["source_product_id"])) for row in rows}

    async def present_product_category_keys(
        self,
        product_category_keys: set[tuple[str, str, str]],
    ) -> set[tuple[str, str, str]]:
        """Return auto product-category keys present in the DB.

        Args:
            product_category_keys: Expected source product/category triples.

        Returns:
            Present triples intersected with expected keys.
        """
        source_product_ids = [
            product_id for _provider, product_id, _category in product_category_keys
        ]
        category_keys = [category for _provider, _product_id, category in product_category_keys]
        rows = await self._conn.fetch(
            AUTO_PRODUCT_CATEGORY_KEYS_SQL,
            auto_import.SOURCE_PROVIDER,
            auto_import.PRODUCT_CATEGORY_SOURCE,
            source_product_ids,
            category_keys,
        )
        present = {
            (str(row["source_provider"]), str(row["source_product_id"]), str(row["category_key"]))
            for row in rows
        }
        return present.intersection(product_category_keys)

    async def auto_product_category_keys_for_products(
        self,
        product_keys: set[tuple[str, str]],
    ) -> set[tuple[str, str, str]]:
        """Return all auto product-category keys for expected source products.

        Args:
            product_keys: Expected source product keys.

        Returns:
            Source provider, source product id, and category key triples.
        """
        source_product_ids = [product_id for _provider, product_id in product_keys]
        rows = await self._conn.fetch(
            AUTO_PRODUCT_CATEGORY_KEYS_FOR_PRODUCTS_SQL,
            auto_import.SOURCE_PROVIDER,
            auto_import.PRODUCT_CATEGORY_SOURCE,
            source_product_ids,
        )
        return {
            (str(row["source_provider"]), str(row["source_product_id"]), str(row["category_key"]))
            for row in rows
        }


def _expected_product_keys(rows: list[dict[str, Any]]) -> set[tuple[str, str]]:
    """Return expected source product keys.

    Args:
        rows: Auto import rows.

    Returns:
        Source provider/product id pairs.
    """
    return {(str(row["source_provider"]), str(row["source_product_id"])) for row in rows}


def _expected_category_keys(rows: list[dict[str, Any]]) -> set[str]:
    """Return expected category keys.

    Args:
        rows: Auto import rows.

    Returns:
        Category keys.
    """
    return {str(row["category"]) for row in rows}


def _expected_product_category_keys(rows: list[dict[str, Any]]) -> set[tuple[str, str, str]]:
    """Return expected source product/category triples.

    Args:
        rows: Auto import rows.

    Returns:
        Source provider, source product id, and category key triples.
    """
    return {
        (str(row["source_provider"]), str(row["source_product_id"]), str(row["category"]))
        for row in rows
    }


def _blocked_reason_codes(
    *,
    missing_category_keys: list[str],
    missing_product_keys: list[tuple[str, str]],
    missing_product_category_keys: list[tuple[str, str, str]],
) -> list[str]:
    """Return redacted DB verification blocker codes.

    Args:
        missing_category_keys: Missing category keys.
        missing_product_keys: Missing product source keys.
        missing_product_category_keys: Missing product-category triples.

    Returns:
        Stable blocker codes.
    """
    blockers: list[str] = []
    if missing_category_keys:
        blockers.append("missing_db_rows:supplement_categories")
    if missing_product_keys:
        blockers.append("missing_db_rows:supplement_products")
    if missing_product_category_keys:
        blockers.append("missing_db_rows:supplement_product_categories")
    return blockers


def _status(*, verified: bool, cleanup_recommended: bool) -> str:
    """Return a stable verification status.

    Args:
        verified: Whether all expected DB rows are present.
        cleanup_recommended: Whether stale auto mappings remain.

    Returns:
        Status code for operator summaries.
    """
    if not verified:
        return "not_verified_missing_db_rows"
    if cleanup_recommended:
        return "verified_with_stale_auto_mappings"
    return "verified"


def _failure_summary(*, root: Path, error: Exception) -> dict[str, object]:
    """Build a redacted failure summary.

    Args:
        root: Requested crawling-image root.
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
        "error_type": type(error).__name__,
        "db_import_verified": False,
        "db_write_performed": False,
        "database_url_printed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "local_paths_printed": False,
        "product_names_printed": False,
        "manufacturer_names_printed": False,
    }
    _reject_unsafe_payload(summary)
    return summary


def _resolve_dsn(*, dsn: str | None, env_file: Path | None) -> str | None:
    """Resolve an asyncpg-compatible DSN without exposing secret values.

    Args:
        dsn: Explicit DSN or environment-derived DSN.
        env_file: Optional env file to read if ``dsn`` is empty.

    Returns:
        asyncpg-compatible DSN, or ``None`` when unavailable.
    """
    candidate = (dsn or "").strip()
    if not candidate and env_file is not None:
        values = _read_env_file(env_file.expanduser().resolve())
        candidate = (
            values.get("DATABASE_URL_PLAIN")
            or values.get("DATABASE_URL")
            or values.get("SUPABASE_DB_URL")
            or ""
        ).strip()
    if not candidate:
        return None
    return _coerce_asyncpg_dsn(candidate)


def _coerce_asyncpg_dsn(dsn: str) -> str:
    """Convert SQLAlchemy PostgreSQL driver URLs into asyncpg URLs.

    Args:
        dsn: Database URL.

    Returns:
        URL accepted by asyncpg.
    """
    if dsn.startswith("postgresql+asyncpg://"):
        return "postgresql://" + dsn[len("postgresql+asyncpg://") :]
    if dsn.startswith("postgres+asyncpg://"):
        return "postgres://" + dsn[len("postgres+asyncpg://") :]
    return dsn


def _read_env_file(path: Path) -> dict[str, str]:
    """Read key/value pairs from a dotenv-like file.

    Args:
        path: Env file path.

    Returns:
        Parsed environment values.
    """
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        if stripped.startswith("export "):
            stripped = stripped[len("export ") :].strip()
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = _strip_env_value(value.strip())
        if key:
            values[key] = value
    return values


def _strip_env_value(value: str) -> str:
    """Strip matching dotenv quotes from a value.

    Args:
        value: Raw dotenv value.

    Returns:
        Unquoted value.
    """
    if len(value) >= MIN_QUOTED_VALUE_LENGTH and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _write_summary(path: Path, summary: dict[str, object]) -> None:
    """Write a redacted summary JSON file.

    Args:
        path: Destination path.
        summary: Summary object.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sha256_text(value: str) -> str:
    """Return SHA-256 digest for a non-secret value.

    Args:
        value: Source text.

    Returns:
        Hex digest.
    """
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _reject_unsafe_payload(value: Any) -> None:
    """Reject unsafe keys or local path literals from operator summaries.

    Args:
        value: JSON-serializable payload.

    Raises:
        ValueError: If raw payload keys or local paths are found.
    """
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True)
    for marker in LOCAL_PATH_MARKERS:
        if marker in serialized:
            raise ValueError("Auto brand product verification summary contains a local path.")
    _reject_raw_keys(value)


def _reject_raw_keys(value: Any) -> None:
    """Recursively reject raw OCR/provider/security keys.

    Args:
        value: JSON-like value.

    Raises:
        ValueError: If a forbidden key is present.
    """
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).casefold() in RAW_FORBIDDEN_KEYS:
                raise ValueError(f"Auto brand product verification summary contains raw key: {key}")
            _reject_raw_keys(child)
    elif isinstance(value, list):
        for child in value:
            _reject_raw_keys(child)


if __name__ == "__main__":
    raise SystemExit(main())
