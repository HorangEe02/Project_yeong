"""Import reviewed supplement taxonomy manifests into reference DB tables.

The importer loads category seed rows from
``build_supplement_taxonomy_db_staging.py`` and optional approved product rows
from ``apply_supplement_brand_review_decisions.py``. By default it performs a
dry-run preflight only. A database session is opened only when ``--apply`` is
explicitly provided.

Operator-facing summaries are count-only and never print local absolute paths,
product folder literals, raw OCR text, provider payloads, or image bytes.

References:
    https://www.postgresql.org/docs/current/ddl-constraints.html
    https://supabase.com/docs/guides/database/postgres/row-level-security
    https://docs.sqlalchemy.org/en/21/orm/queryguide/select.html
    https://docs.sqlalchemy.org/en/21/orm/extensions/asyncio.html
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import String, select
from sqlalchemy.ext.asyncio import AsyncSession

BACKEND_ROOT = Path(__file__).resolve().parents[1]
NUTRITION_BACKEND_ROOT = BACKEND_ROOT / "Nutrition-backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(NUTRITION_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(NUTRITION_BACKEND_ROOT))

from src.config import get_settings  # noqa: E402
from src.db.session import get_sessionmaker  # noqa: E402
from src.models.db.supplement import (  # noqa: E402
    SupplementCategory,
    SupplementProduct,
    SupplementProductCategory,
)

from scripts import apply_supplement_brand_review_decisions as brand_apply  # noqa: E402
from scripts import build_supplement_taxonomy_db_staging as staging  # noqa: E402

SCHEMA_VERSION = "supplement-taxonomy-approved-db-import-v1"
DB_SOURCE_MANIFEST_VERSION = "taxonomy-approved-import-v1"
SOURCE_DOC_URLS = (
    "https://www.postgresql.org/docs/current/ddl-constraints.html",
    "https://supabase.com/docs/guides/database/postgres/row-level-security",
    "https://docs.sqlalchemy.org/en/21/orm/queryguide/select.html",
    "https://docs.sqlalchemy.org/en/21/orm/extensions/asyncio.html",
)
LOCAL_PATH_MARKERS = staging.LOCAL_PATH_MARKERS
RAW_FORBIDDEN_KEYS = staging.RAW_FORBIDDEN_KEYS.union(
    {
        "raw_model_response",
        "request_headers",
    }
)
LITERAL_FORBIDDEN_KEYS = frozenset(
    {
        "absolute_path",
        "image_bytes",
        "image_path",
        "local_path",
        "object_uri",
        "product_dir",
        "product_folder",
        "url",
    }
)
WRITE_ACTION_INSERTED = "inserted"
WRITE_ACTION_UPDATED = "updated"
MAPPING_CONFIDENCE_SCALE = 4
MIN_QUOTED_ENV_VALUE_LENGTH = 2


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
        "--apply",
        action="store_true",
        help="Open a DB session and apply reviewed taxonomy rows.",
    )
    parser.add_argument(
        "--require-approved-products",
        action="store_true",
        help="Fail if the product import manifest has no approved rows.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Run CLI preflight and optional DB import.

    Args:
        argv: Optional argument list for tests.
    """
    raise SystemExit(asyncio.run(run_cli(argv)))


async def run_cli(argv: list[str] | None = None) -> int:
    """Execute the CLI and print a redacted JSON summary.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Process exit code.
    """
    args = parse_args(argv)
    if args.env_file is not None:
        _load_env_file(args.env_file.expanduser().resolve())
    try:
        summary = await import_approved_taxonomy_manifest(
            taxonomy_staging=args.taxonomy_staging.expanduser().resolve(),
            product_import_manifest=(
                args.product_import_manifest.expanduser().resolve()
                if args.product_import_manifest is not None
                else None
            ),
            apply_changes=bool(args.apply),
            require_approved_products=bool(args.require_approved_products),
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        summary = _failure_summary(
            taxonomy_staging=args.taxonomy_staging,
            product_import_manifest=args.product_import_manifest,
            apply_requested=bool(args.apply),
            error=exc,
        )
        if args.summary is not None:
            _write_summary(args.summary.expanduser().resolve(), summary)
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
        return 1

    if args.summary is not None:
        _write_summary(args.summary.expanduser().resolve(), summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _load_env_file(path: Path) -> None:
    """Load simple dotenv assignments without printing secret values.

    Existing process environment values take precedence so operators can
    override a file value deliberately from the shell.

    Args:
        path: Dotenv file path.
    """
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        if stripped.startswith("export "):
            stripped = stripped[len("export ") :].strip()
        key, value = stripped.split("=", 1)
        key = key.strip()
        if key:
            os.environ.setdefault(key, _strip_env_value(value.strip()))
    get_settings.cache_clear()


def _strip_env_value(value: str) -> str:
    """Strip matching dotenv quotes from a value.

    Args:
        value: Raw dotenv value.

    Returns:
        Unquoted value when wrapped in matching quotes.
    """
    if (
        len(value) >= MIN_QUOTED_ENV_VALUE_LENGTH
        and value[0] == value[-1]
        and value[0] in {"'", '"'}
    ):
        return value[1:-1]
    return value


async def import_approved_taxonomy_manifest(
    *,
    taxonomy_staging: Path,
    product_import_manifest: Path | None = None,
    apply_changes: bool = False,
    require_approved_products: bool = False,
    repository: Any | None = None,
) -> dict[str, object]:
    """Validate reviewed taxonomy artifacts and optionally write DB rows.

    Args:
        taxonomy_staging: JSONL generated by taxonomy DB staging.
        product_import_manifest: Optional approved product import JSONL.
        apply_changes: Whether to write to the database.
        require_approved_products: Whether an empty approved product manifest is invalid.
        repository: Optional repository double for tests.

    Returns:
        Redacted import summary.

    Raises:
        ValueError: If the manifest rows are unsafe, stale, duplicated, or malformed.
    """
    category_rows = _category_rows_by_key(_read_jsonl_objects(taxonomy_staging))
    product_rows = (
        _read_product_import_rows(product_import_manifest)
        if product_import_manifest is not None
        else []
    )
    if require_approved_products and not product_rows:
        raise ValueError("Approved product import manifest contains no importable rows.")
    _validate_product_categories(product_rows=product_rows, category_rows=category_rows)

    summary = _preflight_summary(
        taxonomy_staging=taxonomy_staging,
        product_import_manifest=product_import_manifest,
        category_rows=category_rows,
        product_rows=product_rows,
        apply_requested=apply_changes,
        require_approved_products=require_approved_products,
    )
    if not apply_changes:
        return summary

    if repository is not None:
        write_summary = await _apply_with_repository(
            repository=repository,
            category_rows=category_rows,
            product_rows=product_rows,
        )
    else:
        sessionmaker = get_sessionmaker()
        async with sessionmaker() as session:
            sql_repository = _SqlAlchemyTaxonomyImportRepository(session=session)
            write_summary = await _apply_with_repository(
                repository=sql_repository,
                category_rows=category_rows,
                product_rows=product_rows,
            )

    summary.update(write_summary)
    summary["preflight_only"] = False
    summary["db_write_performed"] = True
    _reject_unsafe_payload(summary)
    return summary


async def _apply_with_repository(
    *,
    repository: Any,
    category_rows: dict[str, dict[str, Any]],
    product_rows: list[dict[str, Any]],
) -> dict[str, int]:
    """Apply taxonomy rows through a DB repository boundary.

    Args:
        repository: Object implementing category/product/category-map upserts.
        category_rows: Category seed rows keyed by category key.
        product_rows: Approved product import rows.

    Returns:
        Count summary for inserted and updated records.
    """
    category_actions: Counter[str] = Counter()
    product_actions: Counter[str] = Counter()
    mapping_actions: Counter[str] = Counter()
    category_ids: dict[str, UUID] = {}
    try:
        for category_key, row in sorted(category_rows.items()):
            action, category_id = await repository.upsert_category(row)
            category_actions[action] += 1
            category_ids[category_key] = category_id

        for row in product_rows:
            product_action, product_id = await repository.upsert_product(row)
            product_actions[product_action] += 1
            category_key = _required_string(row, "category_key")
            mapping_action = await repository.upsert_product_category(
                product_id=product_id,
                category_id=category_ids[category_key],
                row=row,
            )
            mapping_actions[mapping_action] += 1

        await repository.commit()
    except Exception:
        await repository.rollback()
        raise

    return {
        "inserted_category_count": category_actions[WRITE_ACTION_INSERTED],
        "updated_category_count": category_actions[WRITE_ACTION_UPDATED],
        "inserted_product_count": product_actions[WRITE_ACTION_INSERTED],
        "updated_product_count": product_actions[WRITE_ACTION_UPDATED],
        "inserted_product_category_count": mapping_actions[WRITE_ACTION_INSERTED],
        "updated_product_category_count": mapping_actions[WRITE_ACTION_UPDATED],
    }


class _SqlAlchemyTaxonomyImportRepository:
    """SQLAlchemy repository for reviewed supplement taxonomy imports.

    Args:
        session: Async SQLAlchemy session.
    """

    def __init__(self, *, session: AsyncSession) -> None:
        """Initialize the repository.

        Args:
            session: Async SQLAlchemy session.
        """
        self._session = session

    async def upsert_category(self, row: dict[str, Any]) -> tuple[str, UUID]:
        """Insert or update one supplement category.

        Args:
            row: Validated category seed row.

        Returns:
            Write action and category id.
        """
        category_key = _required_string(row, "category_key")
        category = await self._session.scalar(
            select(SupplementCategory).where(SupplementCategory.category_key == category_key)
        )
        action = WRITE_ACTION_UPDATED
        if category is None:
            category = SupplementCategory(id=uuid4(), category_key=category_key)
            self._session.add(category)
            action = WRITE_ACTION_INSERTED

        category.display_name = _bounded_string_for_column(
            SupplementCategory,
            "display_name",
            row.get("display_name"),
            required=True,
        )
        category.source_folder_name = _bounded_string_for_column(
            SupplementCategory,
            "source_folder_name",
            row.get("source_folder_name"),
        )
        category.source_path = None
        category.source_payload = _category_source_payload(row)
        category.source_manifest_version = DB_SOURCE_MANIFEST_VERSION
        category.sort_order = _non_negative_int(row.get("sort_order"), field_name="sort_order")
        category.is_active = True
        await self._session.flush()
        return action, category.id

    async def upsert_product(self, row: dict[str, Any]) -> tuple[str, UUID]:
        """Insert or update one reviewed supplement product.

        Args:
            row: Approved product import row.

        Returns:
            Write action and product id.
        """
        source_provider = _required_string(row, "source_provider")
        source_product_id = _required_string(row, "source_product_id")
        product = await self._session.scalar(
            select(SupplementProduct).where(
                SupplementProduct.source_provider == source_provider,
                SupplementProduct.source_product_id == source_product_id,
            )
        )
        action = WRITE_ACTION_UPDATED
        if product is None:
            product = SupplementProduct(
                id=uuid4(),
                source_provider=source_provider,
                source_product_id=source_product_id,
            )
            self._session.add(product)
            action = WRITE_ACTION_INSERTED

        product.product_name = _bounded_string_for_column(
            SupplementProduct,
            "product_name",
            row.get("product_name"),
            required=True,
        )
        product.normalized_product_name = _bounded_string_for_column(
            SupplementProduct,
            "normalized_product_name",
            row.get("normalized_product_name"),
            required=True,
        )
        product.manufacturer = _bounded_string_for_column(
            SupplementProduct,
            "manufacturer",
            row.get("manufacturer"),
        )
        product.category = _bounded_string_for_column(
            SupplementProduct,
            "category",
            row.get("category_key"),
        )
        product.source_payload = _required_dict(row, "source_payload")
        product.source_manifest_version = DB_SOURCE_MANIFEST_VERSION
        product.is_active = True
        await self._session.flush()
        return action, product.id

    async def upsert_product_category(
        self,
        *,
        product_id: UUID,
        category_id: UUID,
        row: dict[str, Any],
    ) -> str:
        """Insert or update a product-category mapping.

        Args:
            product_id: Product id.
            category_id: Category id.
            row: Approved product import row containing mapping metadata.

        Returns:
            Write action.
        """
        mapping = await self._session.scalar(
            select(SupplementProductCategory).where(
                SupplementProductCategory.product_id == product_id,
                SupplementProductCategory.category_id == category_id,
            )
        )
        action = WRITE_ACTION_UPDATED
        if mapping is None:
            mapping = SupplementProductCategory(
                id=uuid4(),
                product_id=product_id,
                category_id=category_id,
            )
            self._session.add(mapping)
            action = WRITE_ACTION_INSERTED

        category_mapping = _required_dict(row, "category_mapping")
        mapping.source = _bounded_string_for_column(
            SupplementProductCategory,
            "source",
            category_mapping.get("source"),
            required=True,
        )
        mapping.confidence = _confidence_or_none(category_mapping.get("confidence"))
        mapping.is_primary = category_mapping.get("is_primary") is True
        mapping.source_payload = _product_category_source_payload(row)
        mapping.sort_order = 0
        await self._session.flush()
        return action

    async def commit(self) -> None:
        """Commit the active import transaction."""
        await self._session.commit()

    async def rollback(self) -> None:
        """Rollback the active import transaction."""
        await self._session.rollback()


def _category_rows_by_key(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Return validated category seed rows keyed by category key.

    Args:
        rows: Taxonomy staging JSONL rows.

    Returns:
        Category rows keyed by category key.

    Raises:
        ValueError: If category seed rows are malformed or duplicated.
    """
    categories: dict[str, dict[str, Any]] = {}
    for row in rows:
        _reject_unsafe_payload(row)
        if row.get("schema_version") != staging.SCHEMA_VERSION:
            raise ValueError("Taxonomy staging row uses an unsupported schema.")
        if row.get("row_type") != staging.ROW_TYPE_CATEGORY:
            continue
        if row.get("approved_for_db_write") is not True:
            raise ValueError("Category seed rows must be approved for DB write.")
        if row.get("requires_human_review") is not False:
            raise ValueError("Category seed rows must not require human review.")
        category_key = _required_string(row, "category_key")
        if category_key in categories:
            raise ValueError(f"Duplicate supplement category key: {category_key}")
        _bounded_string_for_column(
            SupplementCategory,
            "category_key",
            category_key,
            required=True,
        )
        _bounded_string_for_column(
            SupplementCategory,
            "display_name",
            row.get("display_name"),
            required=True,
        )
        _bounded_string_for_column(
            SupplementCategory,
            "source_folder_name",
            row.get("source_folder_name"),
        )
        _non_negative_int(row.get("sort_order"), field_name="sort_order")
        categories[category_key] = row

    if not categories:
        raise ValueError("Taxonomy staging requires at least one category seed row.")
    return categories


def _read_product_import_rows(path: Path) -> list[dict[str, Any]]:
    """Read and validate approved product import rows.

    Args:
        path: Product import manifest path.

    Returns:
        Approved product import rows.

    Raises:
        ValueError: If rows are duplicated, unsafe, or not approved for DB write.
    """
    rows = _read_jsonl_objects(path)
    product_rows: list[dict[str, Any]] = []
    seen_source_keys: set[tuple[str, str]] = set()
    for row in rows:
        _reject_unsafe_payload(row)
        _validate_product_import_row(row)
        source_key = (
            _required_string(row, "source_provider"),
            _required_string(row, "source_product_id"),
        )
        if source_key in seen_source_keys:
            raise ValueError("Duplicate source_provider/source_product_id in import manifest.")
        seen_source_keys.add(source_key)
        product_rows.append(row)
    return product_rows


def _validate_product_import_row(row: dict[str, Any]) -> None:
    """Validate one approved supplement product import row.

    Args:
        row: Product import row.

    Raises:
        ValueError: If the row cannot be safely imported.
    """
    if row.get("schema_version") != brand_apply.OUTPUT_ROW_SCHEMA_VERSION:
        raise ValueError("Product import row uses an unsupported schema.")
    if row.get("row_type") != "supplement_product_import":
        raise ValueError("Product import row type is invalid.")
    if row.get("approved_for_db_write") is not True:
        raise ValueError("Product import row is not approved for DB write.")
    if row.get("requires_human_review") is not False:
        raise ValueError("Product import row still requires human review.")
    if row.get("db_write_performed") is not False:
        raise ValueError("Product import row must not already be marked as DB-written.")
    for key in (
        "source_provider",
        "source_product_id",
        "product_name",
        "normalized_product_name",
        "manufacturer",
        "category_key",
    ):
        model = SupplementProduct
        column = "category" if key == "category_key" else key
        _bounded_string_for_column(model, column, row.get(key), required=True)
    _required_dict(row, "source_payload")
    category_mapping = _required_dict(row, "category_mapping")
    _bounded_string_for_column(
        SupplementProductCategory,
        "source",
        category_mapping.get("source"),
        required=True,
    )
    _confidence_or_none(category_mapping.get("confidence"))


def _validate_product_categories(
    *,
    product_rows: list[dict[str, Any]],
    category_rows: dict[str, dict[str, Any]],
) -> None:
    """Ensure product category filters are present in the category seed rows.

    Args:
        product_rows: Approved product rows.
        category_rows: Category seed rows keyed by category key.

    Raises:
        ValueError: If a product references an unavailable category key.
    """
    for row in product_rows:
        category_key = _required_string(row, "category_key")
        if category_key not in category_rows:
            raise ValueError("Product import row references an unknown category_key.")


def _preflight_summary(
    *,
    taxonomy_staging: Path,
    product_import_manifest: Path | None,
    category_rows: dict[str, dict[str, Any]],
    product_rows: list[dict[str, Any]],
    apply_requested: bool,
    require_approved_products: bool,
) -> dict[str, object]:
    """Build a redacted preflight summary.

    Args:
        taxonomy_staging: Taxonomy staging path.
        product_import_manifest: Optional product import manifest path.
        category_rows: Validated category rows.
        product_rows: Validated product rows.
        apply_requested: Whether DB write was requested.
        require_approved_products: Whether product rows were required.

    Returns:
        Redacted summary.
    """
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "taxonomy_staging_name": taxonomy_staging.name,
        "taxonomy_staging_sha256": _sha256_file(taxonomy_staging),
        "product_import_manifest_name": (
            product_import_manifest.name if product_import_manifest is not None else None
        ),
        "product_import_manifest_sha256": (
            _sha256_file(product_import_manifest) if product_import_manifest is not None else None
        ),
        "category_seed_row_count": len(category_rows),
        "approved_product_import_row_count": len(product_rows),
        "planned_category_upsert_count": len(category_rows),
        "planned_product_upsert_count": len(product_rows),
        "planned_product_category_upsert_count": len(product_rows),
        "apply_requested": apply_requested,
        "require_approved_products": require_approved_products,
        "ready_for_db_write": True,
        "preflight_only": True,
        "db_write_performed": False,
        "inserted_category_count": 0,
        "updated_category_count": 0,
        "inserted_product_count": 0,
        "updated_product_count": 0,
        "inserted_product_category_count": 0,
        "updated_product_category_count": 0,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "source_doc_urls": list(SOURCE_DOC_URLS),
    }
    _reject_unsafe_payload(summary)
    return summary


def _category_source_payload(row: dict[str, Any]) -> dict[str, object]:
    """Return sanitized category import metadata.

    Args:
        row: Category seed row.

    Returns:
        Sanitized JSON payload for ``SupplementCategory.source_payload``.
    """
    payload = {
        "source": _required_string(row, "source"),
        "source_folder_hash": _required_string(row, "source_folder_hash"),
        "label_status": _required_string(row, "label_status"),
        "source_schema_version": staging.SCHEMA_VERSION,
        "source_payload_policy": "folder_category_hash_metadata_only",
    }
    _reject_unsafe_payload(payload)
    return payload


def _product_category_source_payload(row: dict[str, Any]) -> dict[str, object]:
    """Return sanitized product-category mapping metadata.

    Args:
        row: Product import row.

    Returns:
        Sanitized JSON payload for ``SupplementProductCategory.source_payload``.
    """
    source_payload = _required_dict(row, "source_payload")
    payload = {
        "source_schema_version": row["schema_version"],
        "source_payload_policy": "mapping_hash_metadata_only",
        "product_dir_hash": source_payload.get("product_dir_hash"),
        "source_folder_hash": source_payload.get("source_folder_hash"),
        "review_decision": source_payload.get("review_decision"),
    }
    _reject_unsafe_payload(payload)
    return payload


def _read_jsonl_objects(path: Path) -> list[dict[str, Any]]:
    """Read JSONL object rows from disk.

    Args:
        path: JSONL path.

    Returns:
        JSON object rows.

    Raises:
        ValueError: If any row is not an object or contains unsafe data.
    """
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError("JSONL rows must be objects.")
        _reject_unsafe_payload(row)
        rows.append(row)
    return rows


def _required_dict(row: dict[str, Any], key: str) -> dict[str, Any]:
    """Return a required object field after unsafe-payload validation.

    Args:
        row: Source row.
        key: Object field key.

    Returns:
        JSON object field.

    Raises:
        ValueError: If the value is absent, not an object, or unsafe.
    """
    value = row.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"Row requires object field: {key}")
    _reject_unsafe_payload(value)
    return value


def _required_string(row: dict[str, Any], key: str) -> str:
    """Return a required non-empty string field.

    Args:
        row: Source row.
        key: String field key.

    Returns:
        Trimmed string.

    Raises:
        ValueError: If the value is missing, empty, or unsafe.
    """
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Row requires string field: {key}")
    stripped = value.strip()
    _reject_unsafe_payload(stripped)
    return stripped


def _bounded_string_for_column(
    model: type[Any],
    column_name: str,
    value: object,
    *,
    required: bool = False,
) -> str | None:
    """Return a string bounded by a SQLAlchemy ``String`` column length.

    Args:
        model: ORM model containing the target column.
        column_name: Column name.
        value: Candidate string.
        required: Whether a blank value should fail.

    Returns:
        Bounded string or ``None``.

    Raises:
        ValueError: If the value is invalid or exceeds ORM column length.
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            raise ValueError(f"Required column value is missing: {column_name}")
        return None
    if not isinstance(value, str):
        raise ValueError(f"Column value must be a string: {column_name}")
    stripped = value.strip()
    _reject_unsafe_payload(stripped)
    max_length = _string_column_length(model, column_name)
    if max_length is not None and len(stripped) > max_length:
        raise ValueError(f"Column value exceeds {model.__name__}.{column_name} length.")
    return stripped


def _string_column_length(model: type[Any], column_name: str) -> int | None:
    """Return a SQLAlchemy ``String`` column length from ORM metadata.

    Args:
        model: ORM model class.
        column_name: Column name.

    Returns:
        Configured string length or ``None``.
    """
    column = model.__table__.columns[column_name]
    column_type = column.type
    if isinstance(column_type, String):
        return column_type.length
    return None


def _non_negative_int(value: object, *, field_name: str) -> int:
    """Return a non-negative integer value.

    Args:
        value: Candidate value.
        field_name: Field name for validation errors.

    Returns:
        Non-negative integer.

    Raises:
        ValueError: If the value is not a non-negative integer.
    """
    if not isinstance(value, int) or value < 0:
        raise ValueError(f"Row requires non-negative integer field: {field_name}")
    return value


def _confidence_or_none(value: object) -> Decimal | None:
    """Return a mapping confidence compatible with ``Numeric(5, 4)``.

    Args:
        value: Candidate confidence.

    Returns:
        Decimal confidence or ``None``.

    Raises:
        ValueError: If the value is not numeric or outside ``0..1``.
    """
    if value is None:
        return None
    if not isinstance(value, int | float | str):
        raise ValueError("Mapping confidence must be numeric.")
    try:
        confidence = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("Mapping confidence must be numeric.") from exc
    if confidence < 0 or confidence > 1:
        raise ValueError("Mapping confidence must be between 0 and 1.")
    if confidence.as_tuple().exponent < -MAPPING_CONFIDENCE_SCALE:
        raise ValueError("Mapping confidence exceeds Numeric(5, 4) scale.")
    return confidence


def _write_summary(path: Path, summary: dict[str, object]) -> None:
    """Write a JSON summary after unsafe-payload validation.

    Args:
        path: Destination summary path.
        summary: Summary object.
    """
    _reject_unsafe_payload(summary)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _failure_summary(
    *,
    taxonomy_staging: Path,
    product_import_manifest: Path | None,
    apply_requested: bool,
    error: BaseException,
) -> dict[str, object]:
    """Return a redacted CLI failure summary.

    Args:
        taxonomy_staging: Requested taxonomy staging path.
        product_import_manifest: Requested product import manifest path.
        apply_requested: Whether DB write was requested.
        error: Failure exception.

    Returns:
        Redacted failure summary.
    """
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "error",
        "taxonomy_staging_name": taxonomy_staging.name,
        "product_import_manifest_name": (
            product_import_manifest.name if product_import_manifest is not None else None
        ),
        "error_code": _safe_error_code(error),
        "error_message": _safe_public_error_message(error),
        "apply_requested": apply_requested,
        "ready_for_db_write": False,
        "preflight_only": not apply_requested,
        "db_write_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
    }
    _reject_unsafe_payload(summary)
    return summary


def _safe_error_code(exc: BaseException) -> str:
    """Return a bounded non-sensitive error code.

    Args:
        exc: Failure exception.

    Returns:
        Error code safe for operator output.
    """
    if isinstance(exc, OSError):
        return "local_file_operation_error"
    if isinstance(exc, json.JSONDecodeError):
        return "json_decode_error"
    return "validation_error"


def _safe_public_error_message(exc: BaseException) -> str:
    """Return a bounded public error message without filesystem details.

    Args:
        exc: Failure exception.

    Returns:
        Sanitized message.
    """
    if isinstance(exc, OSError):
        message = "Local file operation failed."
    elif isinstance(exc, json.JSONDecodeError):
        message = "JSON decode failed."
    else:
        message = str(exc).strip()
    if (
        not message
        or any(marker in message for marker in LOCAL_PATH_MARKERS)
        or "/" in message
        or "\\" in message
    ):
        return "Validation failed."
    return message[:200]


def _reject_unsafe_payload(value: object) -> None:
    """Reject raw keys, local paths, URLs, and sensitive literal keys.

    Args:
        value: Candidate JSON-safe value.

    Raises:
        ValueError: If unsafe data is present.
    """
    if isinstance(value, dict):
        lowered_keys = {str(key).lower() for key in value}
        raw_keys = RAW_FORBIDDEN_KEYS.intersection(lowered_keys)
        literal_keys = LITERAL_FORBIDDEN_KEYS.intersection(lowered_keys)
        if raw_keys:
            raise ValueError(f"Payload contains forbidden raw field(s): {sorted(raw_keys)}")
        if literal_keys:
            raise ValueError(f"Payload contains forbidden literal field(s): {sorted(literal_keys)}")
        for child in value.values():
            _reject_unsafe_payload(child)
    elif isinstance(value, list | tuple):
        for child in value:
            _reject_unsafe_payload(child)
    elif isinstance(value, str):
        if any(marker in value for marker in LOCAL_PATH_MARKERS):
            raise ValueError("Payload contains local path literal.")
        if ("file://" in value or "://" in value) and value not in SOURCE_DOC_URLS:
            raise ValueError("Payload contains URL literal.")


def _sha256_file(path: Path) -> str:
    """Return a SHA-256 digest for a local artifact file.

    Args:
        path: Artifact path.

    Returns:
        Hex digest.
    """
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    main()
