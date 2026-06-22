"""Verify reviewed supplement taxonomy manifests against the database.

This read-only verifier checks that category seed rows and approved
brand/product review rows were actually imported into ``supplement_categories``,
``supplement_products``, and ``supplement_product_categories``. It reuses the
same manifest validation as the importer, but never writes to the database and
never prints local paths, product names, manufacturer names, raw OCR text, or
provider payloads.

References:
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
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

BACKEND_ROOT = Path(__file__).resolve().parents[1]
NUTRITION_BACKEND_ROOT = BACKEND_ROOT / "Nutrition-backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(NUTRITION_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(NUTRITION_BACKEND_ROOT))

from src.db.session import get_sessionmaker  # noqa: E402
from src.models.db.supplement import (  # noqa: E402
    SupplementCategory,
    SupplementProduct,
    SupplementProductCategory,
)

from scripts import import_supplement_taxonomy_approved_manifest as importer  # noqa: E402

SCHEMA_VERSION = "supplement-taxonomy-db-import-verification-v1"
SOURCE_DOC_URLS = (
    "https://docs.sqlalchemy.org/en/21/orm/queryguide/select.html",
    "https://docs.sqlalchemy.org/en/21/orm/extensions/asyncio.html",
    "https://supabase.com/docs/guides/database/postgres/row-level-security",
)


class SupplementTaxonomyVerificationError(ValueError):
    """Raised when taxonomy DB verification cannot be trusted."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed CLI namespace.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--taxonomy-staging", type=Path, required=True)
    parser.add_argument("--product-import-manifest", type=Path, default=None)
    parser.add_argument(
        "--env-file",
        type=Path,
        default=None,
        help="Optional dotenv file. Values are loaded without echoing secrets.",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=None,
        help="Optional summary JSON path. Defaults to stdout only.",
    )
    parser.add_argument(
        "--require-approved-products",
        action="store_true",
        help="Fail if the product import manifest has no approved product rows.",
    )
    parser.add_argument(
        "--fail-on-missing",
        action="store_true",
        help="Exit non-zero when any expected DB row is missing.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Run CLI entrypoint.

    Args:
        argv: Optional argument list for tests.
    """
    raise SystemExit(asyncio.run(run_cli(argv)))


async def run_cli(argv: list[str] | None = None) -> int:
    """Verify DB import state and print a redacted summary.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Process exit code.
    """
    args = parse_args(argv)
    if args.env_file is not None:
        importer._load_env_file(args.env_file.expanduser().resolve())
    try:
        summary = await verify_supplement_taxonomy_db_import(
            taxonomy_staging=args.taxonomy_staging.expanduser().resolve(),
            product_import_manifest=(
                args.product_import_manifest.expanduser().resolve()
                if args.product_import_manifest is not None
                else None
            ),
            require_approved_products=bool(args.require_approved_products),
        )
    except (OSError, ValueError, json.JSONDecodeError, Exception) as exc:
        summary = _failure_summary(
            taxonomy_staging=args.taxonomy_staging,
            product_import_manifest=args.product_import_manifest,
            error=exc,
        )
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


async def verify_supplement_taxonomy_db_import(
    *,
    taxonomy_staging: Path,
    product_import_manifest: Path | None = None,
    require_approved_products: bool = False,
    repository: Any | None = None,
) -> dict[str, object]:
    """Verify taxonomy manifests against persisted DB rows.

    Args:
        taxonomy_staging: JSONL generated by taxonomy DB staging.
        product_import_manifest: Optional approved product import JSONL.
        require_approved_products: Whether an empty approved product manifest is invalid.
        repository: Optional repository double for tests.

    Returns:
        Redacted verification summary.

    Raises:
        ValueError: If manifests are malformed or product rows are required but absent.
    """
    category_rows = importer._category_rows_by_key(importer._read_jsonl_objects(taxonomy_staging))
    product_rows = (
        importer._read_product_import_rows(product_import_manifest)
        if product_import_manifest is not None
        else []
    )
    importer._validate_product_categories(
        product_rows=product_rows,
        category_rows=category_rows,
    )
    if require_approved_products and not product_rows:
        return _blocked_product_verification_summary(
            taxonomy_staging=taxonomy_staging,
            product_import_manifest=product_import_manifest,
            category_rows=category_rows,
            product_rows=product_rows,
            require_approved_products=require_approved_products,
        )

    repo = repository
    if repo is None:
        sessionmaker = get_sessionmaker()
        async with sessionmaker() as session:
            repo = _SqlAlchemyTaxonomyVerificationRepository(session=session)
            return await _verify_with_repository(
                taxonomy_staging=taxonomy_staging,
                product_import_manifest=product_import_manifest,
                category_rows=category_rows,
                product_rows=product_rows,
                repository=repo,
                require_approved_products=require_approved_products,
            )

    return await _verify_with_repository(
        taxonomy_staging=taxonomy_staging,
        product_import_manifest=product_import_manifest,
        category_rows=category_rows,
        product_rows=product_rows,
        repository=repo,
        require_approved_products=require_approved_products,
    )


async def _verify_with_repository(
    *,
    taxonomy_staging: Path,
    product_import_manifest: Path | None,
    category_rows: dict[str, dict[str, Any]],
    product_rows: list[dict[str, Any]],
    repository: Any,
    require_approved_products: bool,
) -> dict[str, object]:
    """Verify manifest rows through a read-only repository.

    Args:
        taxonomy_staging: Taxonomy staging path.
        product_import_manifest: Optional product import manifest path.
        category_rows: Validated category rows keyed by category key.
        product_rows: Validated approved product rows.
        repository: Read-only taxonomy repository.
        require_approved_products: Whether product rows were required.

    Returns:
        Redacted verification summary.
    """
    category_keys = sorted(category_rows)
    product_source_keys = sorted(
        (
            importer._required_string(row, "source_provider"),
            importer._required_string(row, "source_product_id"),
        )
        for row in product_rows
    )
    product_category_keys = sorted(
        (
            importer._required_string(row, "source_provider"),
            importer._required_string(row, "source_product_id"),
            importer._required_string(row, "category_key"),
        )
        for row in product_rows
    )

    present_category_keys = await repository.present_category_keys(category_keys)
    active_category_keys = await repository.active_category_keys()
    present_product_source_keys = await repository.present_product_source_keys(product_source_keys)
    present_product_category_keys = await repository.present_product_category_keys(
        product_category_keys
    )

    missing_category_keys = sorted(set(category_keys) - set(present_category_keys))
    extra_active_category_keys = sorted(set(active_category_keys) - set(category_keys))
    missing_product_source_keys = sorted(
        set(product_source_keys) - set(present_product_source_keys)
    )
    missing_product_category_keys = sorted(
        set(product_category_keys) - set(present_product_category_keys)
    )
    db_import_verified = (
        not missing_category_keys
        and not extra_active_category_keys
        and not missing_product_source_keys
        and not missing_product_category_keys
        and not _product_verification_blockers(
            product_import_manifest=product_import_manifest,
            product_rows=product_rows,
            require_approved_products=require_approved_products,
        )
    )
    category_import_verified = not missing_category_keys and not extra_active_category_keys
    product_import_verified = (
        not missing_product_source_keys and not missing_product_category_keys and bool(product_rows)
    )
    blocked_reason_codes = _verification_blocker_codes(
        product_import_manifest=product_import_manifest,
        product_rows=product_rows,
        require_approved_products=require_approved_products,
        missing_category_keys=missing_category_keys,
        extra_active_category_keys=extra_active_category_keys,
        missing_product_source_keys=missing_product_source_keys,
        missing_product_category_keys=missing_product_category_keys,
    )

    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": _verification_status(
            db_import_verified=db_import_verified,
            blocked_reason_codes=blocked_reason_codes,
        ),
        "taxonomy_staging_name": taxonomy_staging.name,
        "taxonomy_staging_sha256": _sha256_file(taxonomy_staging),
        "product_import_manifest_name": (
            product_import_manifest.name if product_import_manifest is not None else None
        ),
        "product_import_manifest_sha256": (
            _sha256_file(product_import_manifest) if product_import_manifest is not None else None
        ),
        "require_approved_products": require_approved_products,
        "product_import_manifest_present": product_import_manifest is not None,
        "approved_product_rows_required": require_approved_products,
        "approved_product_rows_available": bool(product_rows),
        "verification_scope": (
            "category_and_reviewed_products"
            if require_approved_products or product_import_manifest is not None
            else "category_seed_only"
        ),
        "expected_category_count": len(category_keys),
        "active_db_category_count": len(active_category_keys),
        "matched_category_count": len(present_category_keys),
        "missing_category_count": len(missing_category_keys),
        "missing_category_key_hashes": [_hash_text(key) for key in missing_category_keys],
        "extra_active_category_count": len(extra_active_category_keys),
        "extra_active_category_key_hashes": [_hash_text(key) for key in extra_active_category_keys],
        "expected_product_count": len(product_source_keys),
        "matched_product_count": len(present_product_source_keys),
        "missing_product_count": len(missing_product_source_keys),
        "missing_product_source_key_hashes": [
            _hash_text("::".join(source_key)) for source_key in missing_product_source_keys
        ],
        "expected_product_category_count": len(product_category_keys),
        "matched_product_category_count": len(present_product_category_keys),
        "missing_product_category_count": len(missing_product_category_keys),
        "missing_product_category_key_hashes": [
            _hash_text("::".join(source_category_key))
            for source_category_key in missing_product_category_keys
        ],
        "category_import_verified": category_import_verified,
        "product_import_verified": product_import_verified,
        "blocked_reason_codes": blocked_reason_codes,
        "db_import_verified": db_import_verified,
        "db_write_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "local_paths_printed": False,
        "product_names_printed": False,
        "manufacturer_names_printed": False,
        "source_doc_urls": list(SOURCE_DOC_URLS),
    }
    importer._reject_unsafe_payload(summary)
    return summary


def _blocked_product_verification_summary(
    *,
    taxonomy_staging: Path,
    product_import_manifest: Path | None,
    category_rows: dict[str, dict[str, Any]],
    product_rows: list[dict[str, Any]],
    require_approved_products: bool,
) -> dict[str, object]:
    """Return a redacted blocked summary without opening a DB connection.

    Args:
        taxonomy_staging: Taxonomy staging path.
        product_import_manifest: Optional product import manifest path.
        category_rows: Validated category rows keyed by category key.
        product_rows: Approved product rows parsed from the manifest.
        require_approved_products: Whether reviewed product rows were required.

    Returns:
        Redacted summary that makes product-verification blockers explicit.
    """
    blocked_reason_codes = _verification_blocker_codes(
        product_import_manifest=product_import_manifest,
        product_rows=product_rows,
        require_approved_products=require_approved_products,
        missing_category_keys=[],
        extra_active_category_keys=[],
        missing_product_source_keys=[],
        missing_product_category_keys=[],
    )
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": _verification_status(
            db_import_verified=False,
            blocked_reason_codes=blocked_reason_codes,
        ),
        "taxonomy_staging_name": taxonomy_staging.name,
        "taxonomy_staging_sha256": _sha256_file(taxonomy_staging),
        "product_import_manifest_name": (
            product_import_manifest.name if product_import_manifest is not None else None
        ),
        "product_import_manifest_sha256": (
            _sha256_file(product_import_manifest) if product_import_manifest is not None else None
        ),
        "require_approved_products": require_approved_products,
        "product_import_manifest_present": product_import_manifest is not None,
        "approved_product_rows_required": require_approved_products,
        "approved_product_rows_available": bool(product_rows),
        "verification_scope": "category_and_reviewed_products",
        "expected_category_count": len(category_rows),
        "active_db_category_count": None,
        "matched_category_count": None,
        "missing_category_count": None,
        "missing_category_key_hashes": [],
        "extra_active_category_count": None,
        "extra_active_category_key_hashes": [],
        "expected_product_count": len(product_rows),
        "matched_product_count": None,
        "missing_product_count": None,
        "missing_product_source_key_hashes": [],
        "expected_product_category_count": len(product_rows),
        "matched_product_category_count": None,
        "missing_product_category_count": None,
        "missing_product_category_key_hashes": [],
        "category_import_verified": False,
        "product_import_verified": False,
        "blocked_reason_codes": blocked_reason_codes,
        "db_import_verified": False,
        "db_write_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "local_paths_printed": False,
        "product_names_printed": False,
        "manufacturer_names_printed": False,
        "source_doc_urls": list(SOURCE_DOC_URLS),
    }
    importer._reject_unsafe_payload(summary)
    return summary


class _SqlAlchemyTaxonomyVerificationRepository:
    """SQLAlchemy repository for read-only taxonomy import verification.

    Args:
        session: Async SQLAlchemy session.
    """

    def __init__(self, *, session: AsyncSession) -> None:
        """Initialize the repository.

        Args:
            session: Async SQLAlchemy session.
        """
        self._session = session

    async def present_category_keys(self, category_keys: Iterable[str]) -> set[str]:
        """Return active category keys found in the DB.

        Args:
            category_keys: Expected category keys.

        Returns:
            Present category keys.
        """
        keys = list(category_keys)
        if not keys:
            return set()
        result = await self._session.execute(
            select(SupplementCategory.category_key).where(
                SupplementCategory.category_key.in_(keys),
                SupplementCategory.is_active.is_(True),
            )
        )
        return {str(row[0]) for row in result.all()}

    async def active_category_keys(self) -> set[str]:
        """Return all active category keys found in the DB.

        Returns:
            Active category keys.
        """
        result = await self._session.execute(
            select(SupplementCategory.category_key).where(
                SupplementCategory.is_active.is_(True),
            )
        )
        return {str(row[0]) for row in result.all()}

    async def present_product_source_keys(
        self,
        source_keys: Iterable[tuple[str, str]],
    ) -> set[tuple[str, str]]:
        """Return active product source keys found in the DB.

        Args:
            source_keys: Expected ``source_provider`` and ``source_product_id`` pairs.

        Returns:
            Present source key pairs.
        """
        keys = list(source_keys)
        if not keys:
            return set()
        result = await self._session.execute(
            select(SupplementProduct.source_provider, SupplementProduct.source_product_id).where(
                tuple_(SupplementProduct.source_provider, SupplementProduct.source_product_id).in_(
                    keys
                ),
                SupplementProduct.is_active.is_(True),
            )
        )
        return {(str(row[0]), str(row[1])) for row in result.all()}

    async def present_product_category_keys(
        self,
        source_category_keys: Iterable[tuple[str, str, str]],
    ) -> set[tuple[str, str, str]]:
        """Return product-category import keys found in the DB.

        Args:
            source_category_keys: Expected product source keys plus category key.

        Returns:
            Present product-category key triples.
        """
        keys = list(source_category_keys)
        if not keys:
            return set()
        source_pairs = {(provider, product_id) for provider, product_id, _category in keys}
        category_keys = {category for _provider, _product_id, category in keys}
        result = await self._session.execute(
            select(
                SupplementProduct.source_provider,
                SupplementProduct.source_product_id,
                SupplementCategory.category_key,
            )
            .join(
                SupplementProductCategory,
                SupplementProductCategory.product_id == SupplementProduct.id,
            )
            .join(
                SupplementCategory,
                SupplementCategory.id == SupplementProductCategory.category_id,
            )
            .where(
                tuple_(SupplementProduct.source_provider, SupplementProduct.source_product_id).in_(
                    list(source_pairs)
                ),
                SupplementCategory.category_key.in_(list(category_keys)),
                SupplementProduct.is_active.is_(True),
                SupplementCategory.is_active.is_(True),
            )
        )
        present = {(str(row[0]), str(row[1]), str(row[2])) for row in result.all()}
        return present.intersection(set(keys))


def _product_verification_blockers(
    *,
    product_import_manifest: Path | None,
    product_rows: list[dict[str, Any]],
    require_approved_products: bool,
) -> list[str]:
    """Return blocker codes that prevent reviewed-product verification.

    Args:
        product_import_manifest: Optional product import manifest path.
        product_rows: Approved product rows parsed from the manifest.
        require_approved_products: Whether reviewed product rows are required.

    Returns:
        Stable blocker codes for missing product verification inputs.
    """
    blockers: list[str] = []
    if require_approved_products and product_import_manifest is None:
        blockers.append("missing_required:approved_product_import")
    if require_approved_products and product_import_manifest is not None and not product_rows:
        blockers.append("approved_product_import:no_importable_rows")
    return blockers


def _verification_blocker_codes(
    *,
    product_import_manifest: Path | None,
    product_rows: list[dict[str, Any]],
    require_approved_products: bool,
    missing_category_keys: list[str],
    extra_active_category_keys: list[str],
    missing_product_source_keys: list[tuple[str, str]],
    missing_product_category_keys: list[tuple[str, str, str]],
) -> list[str]:
    """Return redacted blocker codes for a DB import verification summary.

    Args:
        product_import_manifest: Optional product import manifest path.
        product_rows: Approved product rows parsed from the manifest.
        require_approved_products: Whether reviewed product rows are required.
        missing_category_keys: Category keys missing from DB.
        extra_active_category_keys: Active DB category keys outside the staging set.
        missing_product_source_keys: Product source keys missing from DB.
        missing_product_category_keys: Product-category keys missing from DB.

    Returns:
        Stable blocker codes that omit product/category names and paths.
    """
    blockers = _product_verification_blockers(
        product_import_manifest=product_import_manifest,
        product_rows=product_rows,
        require_approved_products=require_approved_products,
    )
    if missing_category_keys:
        blockers.append("missing_db_rows:supplement_categories")
    if extra_active_category_keys:
        blockers.append("extra_db_rows:supplement_categories")
    if missing_product_source_keys:
        blockers.append("missing_db_rows:supplement_products")
    if missing_product_category_keys:
        blockers.append("missing_db_rows:supplement_product_categories")
    return blockers


def _verification_status(*, db_import_verified: bool, blocked_reason_codes: list[str]) -> str:
    """Return a stable verification status.

    Args:
        db_import_verified: Whether all required rows are verified.
        blocked_reason_codes: Redacted blocker codes.

    Returns:
        Status token for readiness consumers.
    """
    if db_import_verified:
        return "verified"
    if "missing_required:approved_product_import" in blocked_reason_codes:
        return "blocked_missing_product_import_manifest"
    if "approved_product_import:no_importable_rows" in blocked_reason_codes:
        return "blocked_no_importable_product_rows"
    return "not_verified_missing_db_rows"


def _sha256_file(path: Path) -> str:
    """Return the SHA-256 digest for a file.

    Args:
        path: File path.

    Returns:
        Hex digest.
    """
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _hash_text(value: str) -> str:
    """Return a stable SHA-256 digest for non-secret identifiers.

    Args:
        value: Identifier value.

    Returns:
        Hex digest.
    """
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


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


def _failure_summary(
    *,
    taxonomy_staging: Path,
    product_import_manifest: Path | None,
    error: BaseException,
) -> dict[str, object]:
    """Build a redacted failure summary.

    Args:
        taxonomy_staging: Requested taxonomy staging path.
        product_import_manifest: Optional requested product import manifest path.
        error: Raised exception.

    Returns:
        Redacted summary.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "error",
        "error_type": type(error).__name__,
        "taxonomy_staging_name": taxonomy_staging.name,
        "taxonomy_staging_path_hash": _hash_text(str(taxonomy_staging.expanduser())),
        "product_import_manifest_name": (
            product_import_manifest.name if product_import_manifest is not None else None
        ),
        "product_import_manifest_path_hash": (
            _hash_text(str(product_import_manifest.expanduser()))
            if product_import_manifest is not None
            else None
        ),
        "db_import_verified": False,
        "db_write_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "local_paths_printed": False,
        "product_names_printed": False,
        "manufacturer_names_printed": False,
    }


if __name__ == "__main__":
    main()
