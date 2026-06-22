"""Import taxo59 food nutrition rows into the existing food catalog.

The teammate-provided ``food_nutrition_taxo59.csv`` is a standalone nutrition
table proposal. This importer maps that CSV into the current Lemon-Aid schema:
``food_cuisines`` -> ``food_courses`` -> ``food_catalog_items`` with nutrition
values stored in ``FoodCatalogItem.nutrition_reference``. It does not run the
teammate SQL because that SQL drops and recreates ``food_nutrition`` and would
conflict with the already migrated catalog tables.

References:
    https://www.postgresql.org/docs/current/ddl-constraints.html
    https://docs.sqlalchemy.org/en/21/orm/queryguide/select.html
    https://docs.sqlalchemy.org/en/21/orm/extensions/asyncio.html
    https://supabase.com/docs/guides/database/postgres/row-level-security
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

BACKEND_ROOT = Path(__file__).resolve().parents[1]
NUTRITION_BACKEND_ROOT = BACKEND_ROOT / "Nutrition-backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(NUTRITION_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(NUTRITION_BACKEND_ROOT))

from src.db.session import get_sessionmaker  # noqa: E402
from src.models.db.meal import FoodCatalogItem, FoodCourse, FoodCuisine  # noqa: E402

SCHEMA_VERSION = "food-taxo59-catalog-import-v1"
DB_SOURCE = "aihub_taxo59_csv"
SOURCE_DOC_URLS = (
    "https://www.postgresql.org/docs/current/ddl-constraints.html",
    "https://docs.sqlalchemy.org/en/21/orm/queryguide/select.html",
    "https://docs.sqlalchemy.org/en/21/orm/extensions/asyncio.html",
    "https://supabase.com/docs/guides/database/postgres/row-level-security",
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
REQUIRED_COLUMNS = (
    "class_en",
    "class_ko",
    "n_source_codes",
    "serving_g",
    "kcal_100g",
    "carb_g",
    "sugar_g",
    "fat_g",
    "protein_g",
    "sodium_mg",
    "chol_mg",
    "sat_fat_g",
    "trans_fat_g",
)

# Deterministic mapping from taxo59 detector class to the existing requested
# Lemon-Aid food taxonomy. The mapping is intentionally explicit so a model
# class rename cannot silently fall into a wrong cuisine/course bucket.
TAXO59_CLASS_TAXONOMY: dict[str, tuple[str, str]] = {
    "barbecue-ribs": ("korean", "main"),
    "black-bean-noodles": ("chinese", "main"),
    "braised-chicken": ("korean", "main"),
    "braised-pork-hock": ("korean", "main"),
    "bread": ("western", "side"),
    "bulgogi": ("korean", "main"),
    "cake": ("western", "dessert"),
    "cold-noodles": ("korean", "main"),
    "cold-ramen": ("japanese", "main"),
    "curry": ("other", "ethnic"),
    "dim-sum": ("chinese", "side"),
    "doenjang-jjigae": ("korean", "soup_stew"),
    "dumplings": ("chinese", "side"),
    "fish-cake": ("korean", "side"),
    "fried-chicken": ("other", "fast_food"),
    "fried-food-platter": ("korean", "side"),
    "fried-rice": ("chinese", "main"),
    "grilled-beef": ("korean", "main"),
    "grilled-fish": ("korean", "main"),
    "grilled-pork-belly": ("korean", "main"),
    "hamburger": ("other", "fast_food"),
    "hot-pot": ("korean", "soup_stew"),
    "japanese-ramen": ("japanese", "main"),
    "jjamppong": ("chinese", "main"),
    "jjigae-red": ("korean", "soup_stew"),
    "kalguksu": ("korean", "main"),
    "korean-blood-sausage": ("korean", "side"),
    "korean-clear-soup": ("korean", "soup_stew"),
    "korean-ramyeon-red": ("korean", "main"),
    "korean-red-soup": ("korean", "soup_stew"),
    "mixed-rice-bowl": ("korean", "main"),
    "nagasaki-champon": ("japanese", "main"),
    "noodle-plain": ("korean", "main"),
    "pasta": ("western", "main"),
    "pizza": ("western", "main"),
    "pork-cutlet-dry": ("japanese", "main"),
    "pork-cutlet-sauced": ("japanese", "main"),
    "raw-fish": ("japanese", "main"),
    "rice-bowl": ("korean", "main"),
    "rice-noodle-soup": ("other", "ethnic"),
    "rice-porridge": ("korean", "main"),
    "rice-soup": ("korean", "soup_stew"),
    "salad": ("western", "salad"),
    "sandwich": ("western", "main"),
    "savory-pancake": ("korean", "side"),
    "seafood-clear-tang": ("korean", "soup_stew"),
    "seafood-jjim": ("korean", "main"),
    "seafood-spicy-tang": ("korean", "soup_stew"),
    "seaweed-rice-roll": ("korean", "main"),
    "shrimp-dish": ("korean", "main"),
    "spicy-mixed-noodles": ("korean", "main"),
    "squid-dish": ("korean", "main"),
    "sushi": ("japanese", "main"),
    "takoyaki": ("japanese", "side"),
    "tteokbokki-cream-rose": ("korean", "main"),
    "tteokbokki-jajang": ("korean", "main"),
    "tteokbokki-red": ("korean", "main"),
    "udon": ("japanese", "main"),
    "western-cream-soup": ("western", "soup"),
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed CLI namespace.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument("--apply", action="store_true")
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
    try:
        summary = await import_food_taxo59_catalog(
            csv_path=args.csv.expanduser().resolve(),
            manifest_path=(
                args.manifest.expanduser().resolve() if args.manifest is not None else None
            ),
            apply_changes=bool(args.apply),
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        summary = _failure_summary(csv_path=args.csv, apply_requested=bool(args.apply), error=exc)
        _write_summary(args.summary.expanduser().resolve(), summary)
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
        return 1

    _write_summary(args.summary.expanduser().resolve(), summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


async def import_food_taxo59_catalog(
    *,
    csv_path: Path,
    manifest_path: Path | None = None,
    apply_changes: bool = False,
    repository: Any | None = None,
) -> dict[str, object]:
    """Validate taxo59 CSV rows and optionally upsert food catalog items.

    Args:
        csv_path: Teammate-provided taxo59 CSV path.
        manifest_path: Optional JSONL manifest output path.
        apply_changes: Whether to open a DB session and upsert catalog items.
        repository: Optional repository double for tests.

    Returns:
        Redacted import summary.

    Raises:
        ValueError: If CSV rows are unsafe, duplicated, or unmapped.
    """
    rows = build_food_catalog_rows(csv_path=csv_path)
    _reject_unsafe_payload(rows)
    if manifest_path is not None:
        _write_manifest(manifest_path, rows)

    summary = _preflight_summary(csv_path=csv_path, rows=rows, apply_requested=apply_changes)
    if not apply_changes:
        return summary

    if repository is not None:
        write_summary = await _apply_with_repository(repository=repository, rows=rows)
    else:
        sessionmaker = get_sessionmaker()
        async with sessionmaker() as session:
            write_summary = await _apply_with_repository(
                repository=_SqlAlchemyFoodTaxo59Repository(session=session),
                rows=rows,
            )
    summary.update(write_summary)
    summary["preflight_only"] = False
    summary["db_write_performed"] = True
    _reject_unsafe_payload(summary)
    return summary


def build_food_catalog_rows(*, csv_path: Path) -> list[dict[str, Any]]:
    """Return DB-ready food catalog rows from a taxo59 CSV file.

    Args:
        csv_path: CSV file path.

    Returns:
        Validated food catalog rows.

    Raises:
        ValueError: If required columns, taxonomy mappings, or class ids are invalid.
    """
    raw_rows = _read_taxo59_csv(csv_path)
    seen_classes: set[str] = set()
    rows: list[dict[str, Any]] = []
    for sort_order, raw in enumerate(raw_rows):
        class_en = _required_text(raw, "class_en")
        if class_en in seen_classes:
            raise ValueError("taxo59 CSV contains duplicate class_en values.")
        seen_classes.add(class_en)
        if class_en not in TAXO59_CLASS_TAXONOMY:
            raise ValueError(f"taxo59 class has no cuisine/course mapping: {class_en}")
        cuisine_code, course_code = TAXO59_CLASS_TAXONOMY[class_en]
        rows.append(
            {
                "schema_version": SCHEMA_VERSION,
                "row_type": "food_catalog_item",
                "db_target_table": "food_catalog_items",
                "class_en": class_en,
                "cuisine_code": cuisine_code,
                "course_code": course_code,
                "canonical_name_ko": _required_text(raw, "class_ko"),
                "canonical_name_en": _title_from_class(class_en),
                "aliases": [class_en],
                "nutrition_reference": _nutrition_reference(raw),
                "source": DB_SOURCE,
                "source_payload": {
                    "model_class": class_en,
                    "n_source_codes": _int_or_none(raw.get("n_source_codes")),
                    "source_dataset": "aihub_food_image_taxo59",
                    "source_unit": "per_100g_average",
                },
                "sort_order": sort_order,
                "is_active": True,
                "raw_provider_payload_stored": False,
                "raw_ocr_text_stored": False,
            }
        )
    missing_mappings = sorted(set(TAXO59_CLASS_TAXONOMY) - seen_classes)
    if missing_mappings:
        raise ValueError("taxonomy mapping contains classes not present in CSV.")
    return rows


async def _apply_with_repository(*, repository: Any, rows: list[dict[str, Any]]) -> dict[str, int]:
    """Apply rows through a repository boundary.

    Args:
        repository: Food taxo59 repository.
        rows: Validated catalog rows.

    Returns:
        Insert/update count summary.
    """
    actions: Counter[str] = Counter()
    try:
        for row in rows:
            actions[await repository.upsert_catalog_item(row)] += 1
        await repository.commit()
    except Exception:
        await repository.rollback()
        raise
    return {
        "inserted_food_catalog_item_count": actions["inserted"],
        "updated_food_catalog_item_count": actions["updated"],
    }


class _SqlAlchemyFoodTaxo59Repository:
    """SQLAlchemy repository for taxo59 food catalog imports.

    Args:
        session: Async SQLAlchemy session.
    """

    def __init__(self, *, session: AsyncSession) -> None:
        """Initialize the repository.

        Args:
            session: Async SQLAlchemy session.
        """
        self._session = session

    async def upsert_catalog_item(self, row: dict[str, Any]) -> str:
        """Insert or update one food catalog item.

        Args:
            row: Validated food catalog row.

        Returns:
            ``inserted`` or ``updated``.

        Raises:
            ValueError: If the required cuisine/course seed is missing.
        """
        cuisine = await self._session.scalar(
            select(FoodCuisine).where(
                FoodCuisine.cuisine_code == row["cuisine_code"],
                FoodCuisine.is_active.is_(True),
            )
        )
        if cuisine is None:
            raise ValueError("Required active food cuisine seed is missing.")
        course = await self._session.scalar(
            select(FoodCourse).where(
                FoodCourse.cuisine_id == cuisine.id,
                FoodCourse.course_code == row["course_code"],
                FoodCourse.is_active.is_(True),
            )
        )
        if course is None:
            raise ValueError("Required active food course seed is missing.")

        item = await self._session.scalar(
            select(FoodCatalogItem).where(
                FoodCatalogItem.cuisine_id == cuisine.id,
                FoodCatalogItem.course_id == course.id,
                FoodCatalogItem.canonical_name_ko == row["canonical_name_ko"],
            )
        )
        action = "updated"
        if item is None:
            item = FoodCatalogItem(
                id=uuid4(),
                cuisine_id=cuisine.id,
                course_id=course.id,
                canonical_name_ko=row["canonical_name_ko"],
            )
            self._session.add(item)
            action = "inserted"

        item.canonical_name_en = row["canonical_name_en"]
        item.aliases = row["aliases"]
        item.nutrition_reference = row["nutrition_reference"]
        item.source = row["source"]
        item.source_payload = row["source_payload"]
        item.is_active = True
        await self._session.flush()
        return action

    async def commit(self) -> None:
        """Commit the active import transaction."""
        await self._session.commit()

    async def rollback(self) -> None:
        """Rollback the active import transaction."""
        await self._session.rollback()


def _read_taxo59_csv(csv_path: Path) -> list[dict[str, str]]:
    """Read and validate a taxo59 CSV file.

    Args:
        csv_path: CSV file path.

    Returns:
        CSV rows.

    Raises:
        ValueError: If the CSV header is missing required columns.
    """
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = tuple(reader.fieldnames or ())
        missing = [column for column in REQUIRED_COLUMNS if column not in fieldnames]
        if missing:
            raise ValueError("taxo59 CSV is missing required columns.")
        return [dict(row) for row in reader]


def _nutrition_reference(row: dict[str, str]) -> dict[str, Any]:
    """Build bounded nutrition reference JSON for one class row."""
    serving_g = _decimal_or_none(row.get("serving_g"))
    nutrients_100g = {
        "kcal": _decimal_or_none(row.get("kcal_100g")),
        "carb_g": _decimal_or_none(row.get("carb_g")),
        "sugar_g": _decimal_or_none(row.get("sugar_g")),
        "fat_g": _decimal_or_none(row.get("fat_g")),
        "protein_g": _decimal_or_none(row.get("protein_g")),
        "sodium_mg": _decimal_or_none(row.get("sodium_mg")),
        "cholesterol_mg": _decimal_or_none(row.get("chol_mg")),
        "saturated_fat_g": _decimal_or_none(row.get("sat_fat_g")),
        "trans_fat_g": _decimal_or_none(row.get("trans_fat_g")),
    }
    per_serving = {
        key: _scale_per_serving(value, serving_g)
        for key, value in nutrients_100g.items()
        if value is not None and serving_g is not None
    }
    return {
        "schema_version": "food-nutrition-taxo59-v1",
        "basis": "per_100g_class_average",
        "serving_g": _json_decimal(serving_g),
        "per_100g": {key: _json_decimal(value) for key, value in nutrients_100g.items()},
        "per_serving_estimate": {key: _json_decimal(value) for key, value in per_serving.items()},
        "precision_note": "demo_class_average_not_medical_or_prescriptive",
    }


def _preflight_summary(
    *,
    csv_path: Path,
    rows: list[dict[str, Any]],
    apply_requested: bool,
) -> dict[str, object]:
    """Build a redacted import preflight summary."""
    cuisine_counts = Counter(str(row["cuisine_code"]) for row in rows)
    course_counts = Counter(f"{row['cuisine_code']}:{row['course_code']}" for row in rows)
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "csv_name": csv_path.name,
        "csv_sha256": _sha256_file(csv_path),
        "csv_row_count": len(rows),
        "mapped_food_catalog_item_count": len(rows),
        "cuisine_counts": dict(sorted(cuisine_counts.items())),
        "course_counts": dict(sorted(course_counts.items())),
        "apply_requested": apply_requested,
        "preflight_only": not apply_requested,
        "ready_for_db_write": True,
        "db_write_performed": False,
        "source_table_sql_executed": False,
        "standalone_food_nutrition_table_created": False,
        "target_tables": ["food_catalog_items"],
        "requires_existing_tables": ["food_cuisines", "food_courses", "food_catalog_items"],
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "local_paths_printed": False,
        "database_url_printed": False,
        "source_doc_urls": list(SOURCE_DOC_URLS),
    }
    _reject_unsafe_payload(summary)
    return summary


def _failure_summary(*, csv_path: Path, apply_requested: bool, error: Exception) -> dict[str, Any]:
    """Build a redacted failure summary."""
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "error",
        "csv_name": csv_path.name,
        "csv_path_hash": _sha256_text(str(csv_path.expanduser())),
        "apply_requested": apply_requested,
        "db_write_performed": False,
        "error_type": type(error).__name__,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "local_paths_printed": False,
        "database_url_printed": False,
    }


def _required_text(row: dict[str, str], column: str) -> str:
    """Return a required stripped CSV string."""
    value = (row.get(column) or "").strip()
    if not value:
        raise ValueError(f"taxo59 CSV column is required: {column}")
    return value


def _title_from_class(class_en: str) -> str:
    """Return a user-safe English label from a model class id."""
    return " ".join(part.capitalize() for part in class_en.split("-"))


def _decimal_or_none(value: str | None) -> Decimal | None:
    """Parse optional decimal values from CSV text."""
    if value is None or value.strip() == "":
        return None
    try:
        return Decimal(value.strip())
    except InvalidOperation as exc:
        raise ValueError("taxo59 CSV contains an invalid numeric value.") from exc


def _int_or_none(value: str | None) -> int | None:
    """Parse an optional integer value."""
    decimal_value = _decimal_or_none(value)
    return int(decimal_value) if decimal_value is not None else None


def _scale_per_serving(value: Decimal | None, serving_g: Decimal | None) -> Decimal | None:
    """Scale a 100g nutrient value to the class serving estimate."""
    if value is None or serving_g is None:
        return None
    return (value * serving_g / Decimal("100")).quantize(Decimal("0.01"))


def _json_decimal(value: Decimal | None) -> float | None:
    """Convert optional Decimal values into JSON floats."""
    return float(value) if value is not None else None


def _write_summary(path: Path, summary: dict[str, Any]) -> None:
    """Write a redacted summary JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_manifest(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write a JSONL manifest for reviewed food catalog import rows."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _sha256_file(path: Path) -> str:
    """Return a file SHA-256 digest."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_text(value: str) -> str:
    """Return a SHA-256 digest for text."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _reject_unsafe_payload(value: Any) -> None:
    """Reject raw keys or local absolute paths from operator-facing output."""
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True)
    for marker in LOCAL_PATH_MARKERS:
        if marker in serialized:
            raise ValueError("food taxo59 payload contains a local path literal.")
    _reject_raw_keys(value)


def _reject_raw_keys(value: Any) -> None:
    """Recursively reject raw OCR/provider/security keys."""
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).casefold() in RAW_FORBIDDEN_KEYS:
                raise ValueError(f"food taxo59 payload contains raw key: {key}")
            _reject_raw_keys(child)
    elif isinstance(value, list):
        for child in value:
            _reject_raw_keys(child)


if __name__ == "__main__":
    main()
