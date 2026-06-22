"""Dry-run and optionally apply supplement category seed cleanup.

The cleanup target is the small set of active ``supplement_categories`` rows
that are not present in the reviewed crawling-image category seed manifest. The
default mode is dry-run only: it validates the current DB dump and the prior
cleanup preflight, then prints a redacted plan without opening a database
session. Applying the plan requires both ``--apply`` and an explicit
confirmation token.

Operator-facing summaries never print category keys, source folder labels,
product names, raw OCR text, provider payloads, image paths, or local paths.

References:
    https://www.postgresql.org/docs/current/ddl-constraints.html
    https://docs.sqlalchemy.org/en/21/orm/queryguide/select.html
    https://docs.sqlalchemy.org/en/21/orm/extensions/asyncio.html
    https://supabase.com/docs/guides/database/postgres/row-level-security
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

BACKEND_ROOT = Path(__file__).resolve().parents[1]
NUTRITION_BACKEND_ROOT = BACKEND_ROOT / "Nutrition-backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(NUTRITION_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(NUTRITION_BACKEND_ROOT))

from src.db.session import get_sessionmaker  # noqa: E402
from src.models.db.supplement import SupplementCategory  # noqa: E402

from scripts import import_supplement_taxonomy_approved_manifest as importer  # noqa: E402
from scripts import preflight_supplement_category_seed_cleanup as preflight  # noqa: E402

SCHEMA_VERSION = "supplement-category-seed-cleanup-apply-v1"
CONFIRMATION_TOKEN = "deactivate-extra-active-supplement-categories"
SOURCE_DOC_URLS = (
    "https://www.postgresql.org/docs/current/ddl-constraints.html",
    "https://docs.sqlalchemy.org/en/21/orm/queryguide/select.html",
    "https://docs.sqlalchemy.org/en/21/orm/extensions/asyncio.html",
    "https://supabase.com/docs/guides/database/postgres/row-level-security",
)
LOCAL_PATH_MARKERS = preflight.LOCAL_PATH_MARKERS
RAW_FORBIDDEN_KEYS = preflight.RAW_FORBIDDEN_KEYS.union(
    {
        "category_key",
        "category_keys",
        "display_name",
        "source_folder_name",
    }
)


class CategorySeedCleanupError(ValueError):
    """Raised when cleanup inputs or apply conditions cannot be trusted."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed CLI namespace.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--taxonomy-staging", type=Path, required=True)
    parser.add_argument(
        "--active-category-dump",
        type=Path,
        required=True,
        help="One active category_key per line from a read-only DB query.",
    )
    parser.add_argument("--cleanup-preflight", type=Path, required=True)
    parser.add_argument(
        "--env-file",
        type=Path,
        default=None,
        help="Optional dotenv file. Values are loaded without echoing secrets.",
    )
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Open a DB session and deactivate extra active categories.",
    )
    parser.add_argument(
        "--confirm-manual-cleanup",
        default="",
        help=f"Required with --apply. Exact value: {CONFIRMATION_TOKEN}",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Run CLI entrypoint.

    Args:
        argv: Optional argument list for tests.
    """
    raise SystemExit(asyncio.run(run_cli(argv)))


async def run_cli(argv: list[str] | None = None) -> int:
    """Run cleanup dry-run/apply and print a redacted summary.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Process exit code.
    """
    args = parse_args(argv)
    if args.env_file is not None:
        importer._load_env_file(args.env_file.expanduser().resolve())
    try:
        summary = await apply_category_seed_cleanup(
            taxonomy_staging=args.taxonomy_staging.expanduser().resolve(),
            active_category_dump=args.active_category_dump.expanduser().resolve(),
            cleanup_preflight=args.cleanup_preflight.expanduser().resolve(),
            apply_changes=bool(args.apply),
            confirm_manual_cleanup=args.confirm_manual_cleanup == CONFIRMATION_TOKEN,
        )
    except (OSError, json.JSONDecodeError, CategorySeedCleanupError, ValueError) as exc:
        summary = _failure_summary(
            taxonomy_staging=args.taxonomy_staging,
            active_category_dump=args.active_category_dump,
            cleanup_preflight=args.cleanup_preflight,
            apply_requested=bool(args.apply),
            error=exc,
        )
        _write_summary(args.summary.expanduser().resolve(), summary)
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
        return 1

    _write_summary(args.summary.expanduser().resolve(), summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


async def apply_category_seed_cleanup(
    *,
    taxonomy_staging: Path,
    active_category_dump: Path,
    cleanup_preflight: Path,
    apply_changes: bool = False,
    confirm_manual_cleanup: bool = False,
    repository: Any | None = None,
) -> dict[str, Any]:
    """Validate and optionally deactivate extra active category seed rows.

    Args:
        taxonomy_staging: JSONL generated by taxonomy DB staging.
        active_category_dump: Read-only DB dump with one active category key per line.
        cleanup_preflight: Redacted preflight summary for the same drift.
        apply_changes: Whether to write to the database.
        confirm_manual_cleanup: Explicit operator confirmation for apply mode.
        repository: Optional repository double for tests.

    Returns:
        Redacted cleanup dry-run/apply summary.

    Raises:
        CategorySeedCleanupError: If inputs are stale, unsafe, or not cleanup-only.
    """
    category_rows = importer._category_rows_by_key(importer._read_jsonl_objects(taxonomy_staging))
    expected_keys = set(category_rows)
    active_keys = preflight._read_active_category_dump(active_category_dump)
    missing_keys = sorted(expected_keys - active_keys)
    extra_keys = sorted(active_keys - expected_keys)
    matched_keys = sorted(expected_keys.intersection(active_keys))
    preflight_summary = _load_json_object(cleanup_preflight)
    _validate_cleanup_preflight(
        preflight_summary=preflight_summary,
        expected_count=len(expected_keys),
        active_count=len(active_keys),
        matched_count=len(matched_keys),
        missing_count=len(missing_keys),
        extra_count=len(extra_keys),
    )

    summary = _plan_summary(
        taxonomy_staging=taxonomy_staging,
        active_category_dump=active_category_dump,
        cleanup_preflight=cleanup_preflight,
        expected_count=len(expected_keys),
        active_count=len(active_keys),
        matched_count=len(matched_keys),
        missing_count=len(missing_keys),
        extra_keys=extra_keys,
        apply_requested=apply_changes,
        confirm_manual_cleanup=confirm_manual_cleanup,
    )
    if not apply_changes:
        _reject_unsafe_payload(summary)
        return summary

    if not confirm_manual_cleanup:
        raise CategorySeedCleanupError("Manual cleanup confirmation token is required.")
    if missing_keys:
        raise CategorySeedCleanupError("Missing expected categories block cleanup apply.")
    if not extra_keys:
        summary["status"] = "no_cleanup_required"
        summary["preflight_only"] = False
        _reject_unsafe_payload(summary)
        return summary

    if repository is not None:
        write_summary = await _apply_with_repository(
            repository=repository,
            extra_category_keys=extra_keys,
        )
    else:
        sessionmaker = get_sessionmaker()
        async with sessionmaker() as session:
            sql_repository = _SqlAlchemyCategorySeedCleanupRepository(session=session)
            write_summary = await _apply_with_repository(
                repository=sql_repository,
                extra_category_keys=extra_keys,
            )

    if write_summary["deactivated_category_count"] != len(extra_keys):
        raise CategorySeedCleanupError("Cleanup apply count did not match the approved plan.")
    summary.update(write_summary)
    summary["status"] = "manual_category_seed_cleanup_applied"
    summary["preflight_only"] = False
    summary["db_write_performed"] = True
    summary["db_update_performed"] = True
    _reject_unsafe_payload(summary)
    return summary


async def _apply_with_repository(
    *,
    repository: Any,
    extra_category_keys: list[str],
) -> dict[str, int]:
    """Deactivate extra active categories inside one repository transaction.

    Args:
        repository: DB repository or test double.
        extra_category_keys: Category keys to deactivate.

    Returns:
        Deactivation count summary.

    Raises:
        Exception: Propagates repository failures after rollback.
    """
    try:
        deactivated_count = await repository.deactivate_active_categories(extra_category_keys)
        await repository.commit()
    except Exception:
        await repository.rollback()
        raise
    return {"deactivated_category_count": deactivated_count}


class _SqlAlchemyCategorySeedCleanupRepository:
    """SQLAlchemy repository for supplement category cleanup.

    Args:
        session: Async SQLAlchemy session.
    """

    def __init__(self, *, session: AsyncSession) -> None:
        """Initialize the repository.

        Args:
            session: Async SQLAlchemy session.
        """
        self._session = session

    async def deactivate_active_categories(self, category_keys: list[str]) -> int:
        """Soft-disable active categories selected by the approved cleanup plan.

        Args:
            category_keys: Category keys that are not present in the approved seed.

        Returns:
            Number of active rows changed to inactive.
        """
        rows = (
            await self._session.scalars(
                select(SupplementCategory).where(
                    SupplementCategory.category_key.in_(category_keys),
                    SupplementCategory.is_active.is_(True),
                )
            )
        ).all()
        for row in rows:
            row.is_active = False
        await self._session.flush()
        return len(rows)

    async def commit(self) -> None:
        """Commit the active cleanup transaction."""
        await self._session.commit()

    async def rollback(self) -> None:
        """Rollback the active cleanup transaction."""
        await self._session.rollback()


def _validate_cleanup_preflight(
    *,
    preflight_summary: dict[str, Any],
    expected_count: int,
    active_count: int,
    matched_count: int,
    missing_count: int,
    extra_count: int,
) -> None:
    """Validate that preflight evidence matches the current cleanup plan.

    Args:
        preflight_summary: Prior cleanup preflight summary.
        expected_count: Current expected category count.
        active_count: Current active DB category count from dump.
        matched_count: Current matched category count.
        missing_count: Current missing category count.
        extra_count: Current extra category count.

    Raises:
        CategorySeedCleanupError: If the preflight is stale or unsafe.
    """
    _reject_unsafe_payload(preflight_summary)
    if preflight_summary.get("schema_version") != preflight.SCHEMA_VERSION:
        raise CategorySeedCleanupError("Unsupported cleanup preflight schema.")
    if preflight_summary.get("db_write_performed") is True:
        raise CategorySeedCleanupError("Cleanup preflight unexpectedly performed DB writes.")
    if preflight_summary.get("db_update_performed") is True:
        raise CategorySeedCleanupError("Cleanup preflight unexpectedly performed DB updates.")
    if preflight_summary.get("db_delete_performed") is True:
        raise CategorySeedCleanupError("Cleanup preflight unexpectedly performed DB deletes.")

    expected_status = "no_cleanup_required" if extra_count == 0 else "manual_cleanup_required"
    if missing_count > 0:
        expected_status = "blocked_missing_expected_categories"
    if preflight_summary.get("status") != expected_status:
        raise CategorySeedCleanupError("Cleanup preflight status is stale.")

    count_pairs = {
        "expected_category_count": expected_count,
        "active_db_category_count": active_count,
        "matched_category_count": matched_count,
        "missing_category_count": missing_count,
        "extra_active_category_count": extra_count,
    }
    for key, expected in count_pairs.items():
        if preflight_summary.get(key) != expected:
            raise CategorySeedCleanupError("Cleanup preflight count is stale.")

    if extra_count > 0:
        if preflight_summary.get("cleanup_required") is not True:
            raise CategorySeedCleanupError("Cleanup preflight did not mark cleanup required.")
        if preflight_summary.get("cleanup_requires_manual_approval") is not True:
            raise CategorySeedCleanupError("Cleanup preflight did not require manual approval.")


def _plan_summary(
    *,
    taxonomy_staging: Path,
    active_category_dump: Path,
    cleanup_preflight: Path,
    expected_count: int,
    active_count: int,
    matched_count: int,
    missing_count: int,
    extra_keys: list[str],
    apply_requested: bool,
    confirm_manual_cleanup: bool,
) -> dict[str, Any]:
    """Build a redacted cleanup plan summary.

    Args:
        taxonomy_staging: JSONL generated by taxonomy DB staging.
        active_category_dump: Read-only DB dump with one active category key per line.
        cleanup_preflight: Prior cleanup preflight summary path.
        expected_count: Expected category count.
        active_count: Active DB category count.
        matched_count: Matched category count.
        missing_count: Missing expected category count.
        extra_keys: Extra active category keys kept local to this process.
        apply_requested: Whether DB apply was requested.
        confirm_manual_cleanup: Whether explicit cleanup confirmation was provided.

    Returns:
        Redacted cleanup plan summary.
    """
    extra_count = len(extra_keys)
    status = "no_cleanup_required"
    if missing_count:
        status = "blocked_missing_expected_categories"
    elif extra_count:
        status = "ready_for_manual_category_seed_cleanup"
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": status,
        "taxonomy_staging_name": taxonomy_staging.name,
        "taxonomy_staging_sha256": _sha256_file(taxonomy_staging),
        "active_category_dump_name": active_category_dump.name,
        "active_category_dump_sha256": _sha256_file(active_category_dump),
        "cleanup_preflight_name": cleanup_preflight.name,
        "cleanup_preflight_sha256": _sha256_file(cleanup_preflight),
        "expected_category_count": expected_count,
        "active_db_category_count": active_count,
        "matched_category_count": matched_count,
        "missing_category_count": missing_count,
        "extra_active_category_count": extra_count,
        "extra_active_category_key_hashes": [_hash_text(key) for key in extra_keys],
        "planned_category_deactivation_count": extra_count,
        "apply_requested": apply_requested,
        "manual_cleanup_confirmation_provided": confirm_manual_cleanup,
        "preflight_only": not apply_requested,
        "db_write_performed": False,
        "db_update_performed": False,
        "db_delete_performed": False,
        "deactivated_category_count": 0,
        "database_connection_opened": apply_requested,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "local_paths_printed": False,
        "category_literals_printed": False,
        "product_names_printed": False,
        "manufacturer_names_printed": False,
        "next_steps": _next_steps(
            missing_count=missing_count,
            extra_count=extra_count,
            apply_requested=apply_requested,
            confirm_manual_cleanup=confirm_manual_cleanup,
        ),
        "source_doc_urls": list(SOURCE_DOC_URLS),
    }


def _next_steps(
    *,
    missing_count: int,
    extra_count: int,
    apply_requested: bool,
    confirm_manual_cleanup: bool,
) -> list[str]:
    """Return stable redacted next-step codes."""
    if missing_count:
        return ["rerun_category_seed_import_before_cleanup"]
    if not extra_count:
        return ["rerun_category_seed_db_verifier"]
    if not apply_requested:
        return ["request_operator_approval_for_manual_category_seed_cleanup"]
    if not confirm_manual_cleanup:
        return ["rerun_with_manual_cleanup_confirmation_token"]
    return ["rerun_category_seed_db_verifier"]


def _load_json_object(path: Path) -> dict[str, Any]:
    """Load a JSON object from disk.

    Args:
        path: JSON file path.

    Returns:
        Parsed JSON object.

    Raises:
        ValueError: If the file does not contain a JSON object.
    """
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object.")
    return value


def _failure_summary(
    *,
    taxonomy_staging: Path,
    active_category_dump: Path,
    cleanup_preflight: Path,
    apply_requested: bool,
    error: Exception,
) -> dict[str, Any]:
    """Build a redacted failure summary."""
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "error",
        "taxonomy_staging_name": taxonomy_staging.name,
        "taxonomy_staging_path_hash": _hash_text(str(taxonomy_staging.expanduser())),
        "active_category_dump_name": active_category_dump.name,
        "active_category_dump_path_hash": _hash_text(str(active_category_dump.expanduser())),
        "cleanup_preflight_name": cleanup_preflight.name,
        "cleanup_preflight_path_hash": _hash_text(str(cleanup_preflight.expanduser())),
        "apply_requested": apply_requested,
        "error_type": type(error).__name__,
        "public_error_code": _safe_error_code(error),
        "db_write_performed": False,
        "db_update_performed": False,
        "db_delete_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "local_paths_printed": False,
        "category_literals_printed": False,
        "source_doc_urls": list(SOURCE_DOC_URLS),
    }


def _safe_error_code(error: Exception) -> str:
    """Return a bounded non-sensitive error code."""
    if isinstance(error, OSError):
        return "local_file_operation_error"
    if isinstance(error, json.JSONDecodeError):
        return "json_decode_error"
    return "validation_error"


def _write_summary(path: Path, summary: dict[str, Any]) -> None:
    """Write a summary JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _hash_text(value: str) -> str:
    """Return a stable short SHA-256 hash for a text value."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _sha256_file(path: Path) -> str:
    """Return SHA-256 for a file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _reject_unsafe_payload(payload: Any) -> None:
    """Reject summaries that expose local paths or raw/private payload fields."""
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    if any(marker in serialized for marker in LOCAL_PATH_MARKERS):
        raise ValueError("summary contains an unsafe local path marker.")
    lowered = serialized.lower()
    for key in RAW_FORBIDDEN_KEYS:
        if f'"{key}"' in lowered:
            raise ValueError("summary contains a forbidden raw/private key.")


if __name__ == "__main__":
    main()
