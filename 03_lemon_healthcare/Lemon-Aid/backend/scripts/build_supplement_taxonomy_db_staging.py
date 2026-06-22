"""Build safe DB-staging rows from crawling-image supplement folders.

This script converts the local ``data/nutrition_reference/crawling-image``
layout into reviewable taxonomy rows. Category rows can seed
``supplement_categories`` directly, while product-folder brand candidates remain
review-gated before they can become ``SupplementProduct.manufacturer`` values.
It never writes to the database and never emits local absolute paths, product
directory literals, raw OCR text, or provider payloads.

References:
    https://www.postgresql.org/docs/current/ddl-constraints.html
    https://supabase.com/docs/guides/database/postgres/row-level-security
    https://docs.sqlalchemy.org/en/20/orm/queryguide/select.html
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts import audit_supplement_crawling_image_taxonomy as audit  # noqa: E402

SCHEMA_VERSION = "supplement-taxonomy-db-staging-v1"
DEFAULT_ROOT = Path("data") / "nutrition_reference" / "crawling-image"
ROW_TYPE_CATEGORY = "category_seed"
ROW_TYPE_BRAND_CANDIDATE = "product_brand_candidate"
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
        "image_bytes",
        "ocr_text",
        "provider_payload",
        "raw_image",
        "raw_model_response",
        "raw_ocr_text",
        "raw_provider_payload",
        "request_headers",
        "service_key",
    }
)
SOURCE_DOC_URLS = (
    "https://www.postgresql.org/docs/current/ddl-constraints.html",
    "https://supabase.com/docs/guides/database/postgres/row-level-security",
    "https://docs.sqlalchemy.org/en/20/orm/queryguide/select.html",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments for the staging exporter.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed CLI namespace.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--summary",
        type=Path,
        default=None,
        help="Optional summary JSON path. Defaults to <output>.summary.json.",
    )
    parser.add_argument("--source-run-id", default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Build taxonomy staging rows and write JSONL plus a redacted summary.

    Args:
        argv: Optional argument list for tests.
    """
    args = parse_args(argv)
    output_path = args.output.expanduser().resolve()
    summary_path = (
        args.summary.expanduser().resolve()
        if args.summary is not None
        else output_path.with_suffix(output_path.suffix + ".summary.json")
    )
    try:
        rows = build_taxonomy_staging_rows(
            root=args.root,
            source_run_id=args.source_run_id,
        )
        summary = build_summary(rows=rows, root=args.root)
        _reject_unsafe_payload({"rows": rows, "summary": summary})

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
            encoding="utf-8",
        )
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    except (OSError, ValueError) as exc:
        failure = _failure_summary(error=exc, root=args.root, output_path=output_path)
        try:
            summary_path.parent.mkdir(parents=True, exist_ok=True)
            summary_path.write_text(
                json.dumps(failure, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        except OSError:
            pass
        print(json.dumps(failure, ensure_ascii=False, indent=2, sort_keys=True))
        raise SystemExit(1) from None


def build_taxonomy_staging_rows(
    *,
    root: Path,
    source_run_id: str | None = None,
) -> list[dict[str, Any]]:
    """Return category seed rows and review-gated brand candidate rows.

    Args:
        root: Local crawling-image root to inspect.
        source_run_id: Optional operator run id for traceability.

    Returns:
        JSON-safe staging rows. Category rows are DB-seedable, while product
        brand candidates are explicitly blocked from DB write until reviewed.

    Raises:
        ValueError: If the source root is missing or unsafe rows are produced.
    """
    resolved_root = root.expanduser().resolve()
    if not resolved_root.is_dir():
        raise ValueError("crawling image root is not a directory.")

    rows: list[dict[str, Any]] = []
    for sort_order, category_dir in enumerate(audit._iter_child_dirs(resolved_root)):
        category_row = _category_row(
            category_dir=category_dir,
            sort_order=sort_order,
            source_run_id=source_run_id,
        )
        rows.append(category_row)
        for product_dir in audit._iter_child_dirs(category_dir):
            rows.append(
                _brand_candidate_row(
                    root=resolved_root,
                    category_row=category_row,
                    product_dir=product_dir,
                    source_run_id=source_run_id,
                )
            )

    _reject_unsafe_payload(rows)
    return rows


def build_summary(*, rows: list[dict[str, Any]], root: Path) -> dict[str, Any]:
    """Return a redacted summary for taxonomy staging output.

    Args:
        rows: Staging rows.
        root: Source root used for the run.

    Returns:
        JSON-safe summary.
    """
    category_rows = [row for row in rows if row["row_type"] == ROW_TYPE_CATEGORY]
    brand_rows = [row for row in rows if row["row_type"] == ROW_TYPE_BRAND_CANDIDATE]
    category_counts = Counter(str(row["category_key"]) for row in brand_rows)
    brand_counts = Counter(str(row["brand_candidate"]["display_name"]) for row in brand_rows)
    issue_counts: Counter[str] = Counter()
    source_kind_counts: Counter[str] = Counter()
    for row in brand_rows:
        audit._merge_counter(issue_counts, row.get("issue_counts", {}))
        audit._merge_counter(source_kind_counts, row.get("source_kind_counts", {}))

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "source_root_name": root.name,
        "source_root_hash": audit._sha256_text(str(root.expanduser())),
        "row_count": len(rows),
        "category_seed_row_count": len(category_rows),
        "brand_candidate_row_count": len(brand_rows),
        "review_required_row_count": sum(1 for row in rows if row["requires_human_review"]),
        "approved_for_db_write_row_count": sum(1 for row in rows if row["approved_for_db_write"]),
        "category_key_counts": dict(sorted(category_counts.items())),
        "top_brand_candidate_counts": audit._top_counter(brand_counts, limit=50),
        "issue_counts": dict(sorted(issue_counts.items())),
        "source_kind_counts": dict(sorted(source_kind_counts.items())),
        "db_write_contract": {
            "category_rows_seedable": True,
            "brand_candidate_rows_seedable_without_review": False,
            "requires_approved_brand_review_manifest": True,
        },
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "source_doc_urls": list(SOURCE_DOC_URLS),
    }


def _category_row(
    *,
    category_dir: Path,
    sort_order: int,
    source_run_id: str | None,
) -> dict[str, Any]:
    """Build one category seed row.

    Args:
        category_dir: Top-level category directory.
        sort_order: Deterministic category order.
        source_run_id: Optional operator run id.

    Returns:
        JSON-safe category row.
    """
    display_name = audit._strip_category_brackets(category_dir.name)
    row: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "row_type": ROW_TYPE_CATEGORY,
        "db_target_table": "supplement_categories",
        "category_key": audit._safe_key(display_name),
        "display_name": display_name,
        "source_folder_name": audit._normalize_text(category_dir.name),
        "source_folder_hash": audit._sha256_text(category_dir.name),
        "source": "crawling_image_top_level_folder",
        "sort_order": sort_order,
        "label_status": "folder_taxonomy_seed",
        "requires_human_review": False,
        "approved_for_db_write": True,
        "source_payload_policy": "sanitized_counts_only",
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "product_dir_literal_stored": False,
    }
    if source_run_id:
        row["source_run_id"] = source_run_id
    return row


def _brand_candidate_row(
    *,
    root: Path,
    category_row: dict[str, Any],
    product_dir: Path,
    source_run_id: str | None,
) -> dict[str, Any]:
    """Build one review-gated product brand candidate row.

    Args:
        root: Crawling-image root.
        category_row: Parent category seed row.
        product_dir: Product directory.
        source_run_id: Optional operator run id.

    Returns:
        JSON-safe product brand candidate row.
    """
    product_audit = audit._audit_product(root=root, product_dir=product_dir)
    row: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "row_type": ROW_TYPE_BRAND_CANDIDATE,
        "db_target_table": "supplement_products",
        "db_target_field": "manufacturer",
        "db_target_relation": "supplement_product_categories",
        "category_key": category_row["category_key"],
        "category_display_name": category_row["display_name"],
        "source_folder_hash": category_row["source_folder_hash"],
        "product_dir_hash": product_audit["product_dir_hash"],
        "source_product_id": product_audit["source_product_id"],
        "brand_candidate": product_audit["brand_candidate"],
        "source": "crawling_image_product_folder_prefix",
        "label_status": "pending_brand_human_review",
        "requires_human_review": True,
        "approved_for_db_write": False,
        "store_as_manufacturer_without_review": False,
        "image_count": product_audit["image_count"],
        "source_kind_counts": product_audit["source_kind_counts"],
        "issue_counts": product_audit["issue_counts"],
        "source_payload_policy": "hashes_counts_and_review_status_only",
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "product_dir_literal_stored": False,
    }
    if source_run_id:
        row["source_run_id"] = source_run_id
    return row


def _reject_unsafe_payload(value: Any) -> None:
    """Reject raw fields, local paths, or path-like literals in output payloads.

    Args:
        value: Candidate payload.

    Raises:
        ValueError: If unsafe keys or local path markers are present.
    """
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True)
    for marker in LOCAL_PATH_MARKERS:
        if marker in serialized:
            raise ValueError("taxonomy staging payload contains a local path literal.")
    _reject_raw_keys(value)


def _reject_raw_keys(value: Any) -> None:
    """Recursively reject raw provider or OCR keys.

    Args:
        value: Candidate payload.

    Raises:
        ValueError: If a forbidden raw key is present.
    """
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).casefold() in RAW_FORBIDDEN_KEYS:
                raise ValueError(f"taxonomy staging payload contains raw key: {key}")
            _reject_raw_keys(child)
    elif isinstance(value, list):
        for child in value:
            _reject_raw_keys(child)


def _failure_summary(*, error: Exception, root: Path, output_path: Path) -> dict[str, Any]:
    """Return a redacted CLI failure summary.

    Args:
        error: Failure exception.
        root: Requested source root.
        output_path: Requested output path.

    Returns:
        JSON-safe failure payload without local path disclosure.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "error",
        "source_root_name": root.name,
        "source_root_hash": audit._sha256_text(str(root.expanduser())),
        "output_name": output_path.name,
        "output_path_hash": audit._sha256_text(str(output_path.expanduser())),
        "error_code": type(error).__name__,
        "error_message": "Taxonomy staging failed.",
        "row_count": 0,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
    }


if __name__ == "__main__":
    main()
