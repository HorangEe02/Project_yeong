"""Import auto-normalized supplement brand products into reference tables.

This is the AUTO (non-human-reviewed) path requested for completeness. Each
crawling-image product sub-folder becomes one ``supplement_products`` row with
``manufacturer`` = auto-normalized brand and ``category`` = canonical (proper-
case) category key. The same transaction also upserts one
``supplement_product_categories`` mapping per product so API category filters
can use the curated relation instead of a legacy free-text category column.

Rows are tagged ``source_provider='crawling_image_auto'`` and
``source_manifest_version='crawling-image-auto-brand-v1'`` so they are
identifiable and reversible, and clearly distinct from human-reviewed imports.

Dry-run by default; pass ``--apply`` to upsert. Connection via ``--dsn`` (a
libpq/asyncpg URL), ``--env-file``, or the ``DATABASE_URL_PLAIN`` env var.

References:
    https://www.postgresql.org/docs/current/sql-insert.html
    https://magicstack.github.io/asyncpg/current/usage.html
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import os
import re
import unicodedata
import uuid
from collections import Counter
from decimal import Decimal
from pathlib import Path
from typing import Any

import asyncpg

SCRIPTS_DIR = Path(__file__).resolve().parent
DEFAULT_ROOT = SCRIPTS_DIR.parents[1] / "data" / "nutrition_reference" / "crawling-image"
SOURCE_PROVIDER = "crawling_image_auto"
SOURCE_MANIFEST_VERSION = "crawling-image-auto-brand-v1"
PRODUCT_CATEGORY_SOURCE = "crawling_image_auto"
_WS_RE = re.compile(r"\s+")

# Reuse the normalization logic so brands match the review draft exactly.
_spec = importlib.util.spec_from_file_location(
    "_nz", SCRIPTS_DIR / "normalize_supplement_brand_draft.py"
)
_nz = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_nz)


def _norm_title(name: str) -> str:
    """Return the normalized product title without a trailing source id.

    Args:
        name: Raw product folder name.

    Returns:
        NFC-normalized product title with trailing source id removed.
    """
    return _nz.TRAILING_ID_RE.sub("", unicodedata.normalize("NFC", name)).strip()


def build_rows(root: Path) -> list[dict]:
    """Build deduped supplement product rows from the crawling-image tree.

    Args:
        root: Crawling-image root where first-level folders represent categories.

    Returns:
        Sanitized product rows keyed by source provider and source product id.
    """
    by_key: dict[tuple[str, str], dict] = {}
    for cat_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        cat_name = unicodedata.normalize("NFC", cat_dir.name)
        category_key = _nz.category_key_from_folder(cat_name)
        for prod_dir in sorted(p for p in cat_dir.iterdir() if p.is_dir()):
            prod_name = unicodedata.normalize("NFC", prod_dir.name)
            m = _nz.TRAILING_ID_RE.search(prod_name)
            product_id = m.group(1) if m else prod_name[:128]
            brand, _method, needs_review = _nz.normalize_brand(prod_name)
            title = _norm_title(prod_name)[:240]
            row = {
                "id": uuid.uuid4(),
                "source_provider": SOURCE_PROVIDER,
                "source_product_id": product_id[:128],
                "product_name": title or category_key,
                "normalized_product_name": _WS_RE.sub(" ", title).strip().lower()[:240]
                or category_key.lower(),
                "manufacturer": (brand or None) and brand[:180],
                "category": category_key[:120],
                "source_manifest_version": SOURCE_MANIFEST_VERSION,
                "is_active": True,
                "_needs_review": needs_review,
            }
            by_key[(SOURCE_PROVIDER, product_id)] = row  # dedupe by unique key
    return list(by_key.values())


UPSERT_PRODUCT_SQL = """
INSERT INTO supplement_products
  (id, source_provider, source_product_id, product_name, normalized_product_name,
   manufacturer, category, source_manifest_version, is_active)
VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
ON CONFLICT (source_provider, source_product_id) DO UPDATE SET
  product_name=EXCLUDED.product_name,
  normalized_product_name=EXCLUDED.normalized_product_name,
  manufacturer=EXCLUDED.manufacturer,
  category=EXCLUDED.category,
  source_manifest_version=EXCLUDED.source_manifest_version,
  is_active=EXCLUDED.is_active,
  updated_at=now()
RETURNING id
"""

CATEGORY_ID_SQL = """
SELECT id
FROM supplement_categories
WHERE category_key=$1
  AND is_active=true
"""

UPSERT_PRODUCT_CATEGORY_SQL = """
INSERT INTO supplement_product_categories
  (id, product_id, category_id, source, confidence, is_primary, source_payload, sort_order)
VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb,$8)
ON CONFLICT (product_id, category_id) DO UPDATE SET
  source=EXCLUDED.source,
  confidence=EXCLUDED.confidence,
  is_primary=EXCLUDED.is_primary,
  source_payload=EXCLUDED.source_payload,
  sort_order=EXCLUDED.sort_order,
  updated_at=now()
"""


async def apply_rows(dsn: str, rows: list[dict]) -> dict:
    """Upsert products and category mappings with one fail-closed transaction.

    Args:
        dsn: asyncpg-compatible database URL.
        rows: Product rows returned by :func:`build_rows`.

    Returns:
        Count-only DB write summary.

    Raises:
        ValueError: If a product category key is not present as an active DB category.
    """
    conn = await asyncpg.connect(dsn=dsn)
    try:
        product_before = await conn.fetchval(
            "select count(*) from supplement_products where source_provider=$1", SOURCE_PROVIDER
        )
        mapping_before = await conn.fetchval(
            "select count(*) from supplement_product_categories where source=$1",
            PRODUCT_CATEGORY_SOURCE,
        )
        mapping_upsert_count = 0
        async with conn.transaction():
            for row in rows:
                product_id = await conn.fetchval(
                    UPSERT_PRODUCT_SQL,
                    row["id"],
                    row["source_provider"],
                    row["source_product_id"],
                    row["product_name"],
                    row["normalized_product_name"],
                    row["manufacturer"],
                    row["category"],
                    row["source_manifest_version"],
                    row["is_active"],
                )
                category_id = await conn.fetchval(CATEGORY_ID_SQL, row["category"])
                if category_id is None:
                    raise ValueError("Active supplement category missing for auto product mapping.")
                await conn.execute(
                    UPSERT_PRODUCT_CATEGORY_SQL,
                    uuid.uuid4(),
                    product_id,
                    category_id,
                    PRODUCT_CATEGORY_SOURCE,
                    Decimal("1.0"),
                    True,
                    _product_category_source_payload(),
                    0,
                )
                mapping_upsert_count += 1
        product_after = await conn.fetchval(
            "select count(*) from supplement_products where source_provider=$1", SOURCE_PROVIDER
        )
        mapping_after = await conn.fetchval(
            "select count(*) from supplement_product_categories where source=$1",
            PRODUCT_CATEGORY_SOURCE,
        )
        distinct_brands = await conn.fetchval(
            "select count(distinct manufacturer) from supplement_products "
            "where source_provider=$1 and manufacturer is not null",
            SOURCE_PROVIDER,
        )
        return {
            "rows_before": product_before,
            "rows_after": product_after,
            "distinct_brands_in_db": distinct_brands,
            "product_category_rows_before": mapping_before,
            "product_category_rows_after": mapping_after,
            "product_category_mapping_upsert_count": mapping_upsert_count,
            "category_lookup_attempt_count": len(rows),
            "missing_category_mapping_count": 0,
        }
    finally:
        await conn.close()


def _product_category_source_payload() -> str:
    """Return sanitized product-category mapping metadata as JSON text.

    Returns:
        JSON document without product, category, brand, path, or OCR literals.
    """
    payload: dict[str, Any] = {
        "source_provider": SOURCE_PROVIDER,
        "source_manifest_version": SOURCE_MANIFEST_VERSION,
        "mapping_method": "folder_category",
        "source_payload_policy": "counts_and_source_metadata_only",
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _database_url() -> str | None:
    """Return a driver-compatible DB URL without printing it.

    Returns:
        Database URL from the environment, or ``None`` when unavailable.
    """
    value = (
        os.environ.get("DATABASE_URL_PLAIN")
        or os.environ.get("DATABASE_URL")
        or os.environ.get("SUPABASE_DB_URL")
    )
    if not value:
        return None
    return value.replace("postgresql+asyncpg://", "postgresql://", 1)


def _load_env_file(path: Path) -> None:
    """Load simple KEY=VALUE lines from an env file without echoing values.

    Args:
        path: Env file path.
    """
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional argument vector for tests.

    Returns:
        Parsed CLI namespace.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--dsn", default=None)
    parser.add_argument("--env-file", type=Path, default=None)
    parser.add_argument("--summary", type=Path, default=None)
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the auto import CLI.

    Args:
        argv: Optional argument vector for tests.

    Returns:
        Process exit code.
    """
    args = parse_args(argv)
    if args.env_file is not None:
        _load_env_file(args.env_file.expanduser().resolve())
    rows = build_rows(args.root.expanduser().resolve())
    cat_counts = Counter(r["category"] for r in rows)
    brand_counts = Counter(r["manufacturer"] for r in rows if r["manufacturer"])
    summary = {
        "schema_version": "supplement-brand-products-auto-import-v1",
        "source_provider": SOURCE_PROVIDER,
        "product_row_count": len(rows),
        "with_manufacturer": sum(1 for r in rows if r["manufacturer"]),
        "manufacturer_null_needs_review": sum(1 for r in rows if not r["manufacturer"]),
        "distinct_categories": len(cat_counts),
        "distinct_brands": len(brand_counts),
        "product_category_mapping_planned_count": len(rows),
        "product_category_mapping_write_enabled": bool(args.apply),
        "product_category_mapping_source": PRODUCT_CATEGORY_SOURCE,
        "apply_requested": bool(args.apply),
        "db_write_performed": False,
    }
    if args.apply:
        dsn = args.dsn or _database_url()
        if not dsn:
            raise SystemExit("ERROR: --dsn or DATABASE_URL_PLAIN required for --apply")
        result = asyncio.run(apply_rows(dsn, rows))
        summary.update(result)
        summary["db_write_performed"] = True
    if args.summary:
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
