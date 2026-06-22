"""Autofill supplement brand review CSVs from catalog-safe source metadata.

This helper creates operator-review CSV suggestions without modifying the
original batch CSVs. It approves only rows that are already high-confidence in
the brand normalization draft, have a unique source product id, and can recover
a bounded product title from the crawling catalog. All other rows are marked
``needs_review`` with aggregate-safe reason codes.

The script writes product/manufacturer text only to the private review CSV
output requested by the operator flow. Public summaries remain count-only and
do not include source paths, raw OCR, provider payloads, or product literals.

References:
    https://docs.python.org/3/library/argparse.html
    https://docs.python.org/3/library/csv.html
    https://docs.python.org/3/library/json.html
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
NUTRITION_BACKEND_ROOT = BACKEND_ROOT / "Nutrition-backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(NUTRITION_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(NUTRITION_BACKEND_ROOT))

from scripts import apply_supplement_brand_review_decisions as applier  # noqa: E402
from scripts import import_supplement_brand_products_auto as auto_importer  # noqa: E402

SCHEMA_VERSION = "supplement-brand-review-csv-autofill-v1"
REQUIRED_COLUMNS = frozenset(
    {
        "fixture_id",
        "source_product_id",
        "decision",
        "reviewed_manufacturer",
        "reviewed_product_name",
        "reason_codes",
    }
)
APPROVE_REASON = "reviewed_label_or_catalog"
SOURCE_DOC_URLS = (
    "https://docs.python.org/3/library/argparse.html",
    "https://docs.python.org/3/library/csv.html",
    "https://docs.python.org/3/library/json.html",
)


class BrandReviewCsvAutofillError(ValueError):
    """Raised when brand review CSV autofill cannot be trusted."""


@dataclass(frozen=True)
class BrandDraftRow:
    """Brand normalization draft row.

    Args:
        proposed_brand: Normalized manufacturer candidate.
        needs_human_review: Whether the normalization draft marked this row as
            low-confidence.
    """

    proposed_brand: str
    needs_human_review: bool


@dataclass(frozen=True)
class ProductCatalogRow:
    """Catalog-derived product row.

    Args:
        manufacturer: Catalog-derived manufacturer.
        product_name: Catalog-derived product title.
    """

    manufacturer: str
    product_name: str


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional argument vector for tests.

    Returns:
        Parsed CLI namespace.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--crawling-root", type=Path, required=True)
    parser.add_argument("--brand-draft", type=Path, required=True)
    parser.add_argument("--batch-review-csv", type=Path, action="append", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Autofill review CSV files and write a count-only summary.

    Args:
        argv: Optional argument vector for tests.

    Returns:
        Process exit code.
    """
    args = parse_args(argv)
    summary = autofill_brand_review_csvs(
        crawling_root=args.crawling_root.expanduser().resolve(),
        brand_draft=args.brand_draft.expanduser().resolve(),
        batch_review_csvs=[path.expanduser().resolve() for path in args.batch_review_csv],
        output_dir=args.output_dir.expanduser().resolve(),
    )
    args.summary.expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
    args.summary.expanduser().resolve().write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(_cli_summary(summary), ensure_ascii=False, sort_keys=True))
    return 0


def autofill_brand_review_csvs(
    *,
    crawling_root: Path,
    brand_draft: Path,
    batch_review_csvs: Iterable[Path],
    output_dir: Path,
) -> dict[str, Any]:
    """Write autofilled review CSV suggestions.

    Args:
        crawling_root: Crawling-image root used to recover catalog product rows.
        brand_draft: Brand normalization draft JSONL.
        batch_review_csvs: Batch review CSV files to autofill.
        output_dir: Directory for generated CSV suggestions.

    Returns:
        Count-only autofill summary.
    """
    draft_rows, duplicated_source_ids = _load_brand_draft(brand_draft)
    product_rows = _product_rows_by_source_id(crawling_root)
    output_dir.mkdir(parents=True, exist_ok=True)

    file_summaries: list[dict[str, Any]] = []
    aggregate_decisions: Counter[str] = Counter()
    aggregate_reasons: Counter[str] = Counter()
    total_rows = 0

    for input_csv in batch_review_csvs:
        output_csv = output_dir / _safe_filename(input_csv.name)
        file_summary = _autofill_one_csv(
            input_csv=input_csv,
            output_csv=output_csv,
            draft_rows=draft_rows,
            duplicated_source_ids=duplicated_source_ids,
            product_rows=product_rows,
        )
        file_summaries.append(file_summary)
        total_rows += int(file_summary["row_count"])
        aggregate_decisions.update(file_summary["decision_counts"])
        aggregate_reasons.update(file_summary["reason_counts"])

    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "input_csv_count": len(file_summaries),
        "output_csv_count": len(file_summaries),
        "row_count": total_rows,
        "decision_counts": dict(sorted(aggregate_decisions.items())),
        "reason_counts": dict(sorted(aggregate_reasons.items())),
        "file_summaries": file_summaries,
        "csv_write_performed": True,
        "original_csv_modified": False,
        "db_write_performed": False,
        "source_image_read_performed": False,
        "ocr_provider_call_performed": False,
        "llm_call_performed": False,
        "training_execution_performed_by_script": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "local_path_literals_stored": False,
        "source_doc_urls": list(SOURCE_DOC_URLS),
    }
    _reject_public_summary_unsafe(summary)
    return summary


def _autofill_one_csv(
    *,
    input_csv: Path,
    output_csv: Path,
    draft_rows: Mapping[str, BrandDraftRow],
    duplicated_source_ids: set[str],
    product_rows: Mapping[str, ProductCatalogRow],
) -> dict[str, Any]:
    """Autofill one review CSV.

    Args:
        input_csv: Source review CSV.
        output_csv: Generated review CSV path.
        draft_rows: Brand draft rows keyed by source product id.
        duplicated_source_ids: Source product ids that are ambiguous.
        product_rows: Catalog rows keyed by source product id.

    Returns:
        Count-only file summary.
    """
    rows, fieldnames = _read_csv(input_csv)
    output_rows: list[dict[str, str]] = []
    decisions: Counter[str] = Counter()
    reasons: Counter[str] = Counter()

    for row in rows:
        updated = dict(row)
        decision, manufacturer, product_name, reason_codes = _decision_for_row(
            row=row,
            draft_rows=draft_rows,
            duplicated_source_ids=duplicated_source_ids,
            product_rows=product_rows,
        )
        updated["decision"] = decision
        updated["reviewed_manufacturer"] = manufacturer
        updated["reviewed_product_name"] = product_name
        updated["reason_codes"] = ",".join(reason_codes)
        output_rows.append(updated)
        decisions[decision] += 1
        reasons.update(reason_codes)

    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    return {
        "input_name": _safe_filename(input_csv.name),
        "output_name": _safe_filename(output_csv.name),
        "row_count": len(output_rows),
        "decision_counts": dict(sorted(decisions.items())),
        "reason_counts": dict(sorted(reasons.items())),
    }


def _decision_for_row(
    *,
    row: Mapping[str, str],
    draft_rows: Mapping[str, BrandDraftRow],
    duplicated_source_ids: set[str],
    product_rows: Mapping[str, ProductCatalogRow],
) -> tuple[str, str, str, list[str]]:
    """Return CSV decision fields for one row.

    Args:
        row: Original CSV row.
        draft_rows: Brand draft rows keyed by source product id.
        duplicated_source_ids: Source product ids that are ambiguous.
        product_rows: Catalog rows keyed by source product id.

    Returns:
        Decision, manufacturer, product name, and reason codes.
    """
    source_product_id = _safe_source_product_id(row.get("source_product_id"))
    reason_code = ""
    if not source_product_id:
        reason_code = "needs_catalog_lookup"
    elif source_product_id in duplicated_source_ids:
        reason_code = "duplicate_product"
    else:
        draft = draft_rows.get(source_product_id)
        product = product_rows.get(source_product_id)
        if draft is None or product is None:
            reason_code = "needs_catalog_lookup"
        elif draft.needs_human_review:
            reason_code = "unclear_brand"
        elif not product.manufacturer or not product.product_name:
            reason_code = "needs_catalog_lookup"
        else:
            manufacturer = _safe_review_text(product.manufacturer, max_length=180)
            product_name = _safe_review_text(product.product_name, max_length=240)
            if manufacturer is None or product_name is None:
                reason_code = "unsafe_text"
            else:
                _validate_decision(
                    decision="approve",
                    manufacturer=manufacturer,
                    product_name=product_name,
                    reason_codes=[APPROVE_REASON],
                )
                return "approve", manufacturer, product_name, [APPROVE_REASON]

    return "needs_review", "", "", [reason_code]


def _load_brand_draft(path: Path) -> tuple[dict[str, BrandDraftRow], set[str]]:
    """Load brand draft rows keyed by source product id.

    Args:
        path: Brand normalization draft JSONL.

    Returns:
        Brand draft mapping and duplicated source product ids.
    """
    raw_rows = _read_jsonl(path)
    source_counts: Counter[str] = Counter()
    for row in raw_rows:
        source_product_id = _safe_source_product_id(row.get("source_product_id"))
        if source_product_id:
            source_counts[source_product_id] += 1
    duplicated = {source_id for source_id, count in source_counts.items() if count > 1}

    rows: dict[str, BrandDraftRow] = {}
    for row in raw_rows:
        source_product_id = _safe_source_product_id(row.get("source_product_id"))
        if not source_product_id or source_product_id in duplicated:
            continue
        rows[source_product_id] = BrandDraftRow(
            proposed_brand=_safe_review_text(str(row.get("proposed_brand") or ""), max_length=180)
            or "",
            needs_human_review=bool(row.get("needs_human_review")),
        )
    return rows, duplicated


def _product_rows_by_source_id(root: Path) -> dict[str, ProductCatalogRow]:
    """Build catalog product rows keyed by source product id.

    Args:
        root: Crawling-image root.

    Returns:
        Product rows keyed by source product id.
    """
    rows: dict[str, ProductCatalogRow] = {}
    for row in auto_importer.build_rows(root):
        source_product_id = _safe_source_product_id(row.get("source_product_id"))
        if not source_product_id:
            continue
        manufacturer = _safe_review_text(str(row.get("manufacturer") or ""), max_length=180)
        product_name = _safe_review_text(str(row.get("product_name") or ""), max_length=240)
        rows[source_product_id] = ProductCatalogRow(
            manufacturer=manufacturer or "",
            product_name=product_name or "",
        )
    return rows


def _read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    """Read a review CSV and validate required columns.

    Args:
        path: CSV path.

    Returns:
        Rows and field names.
    """
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise BrandReviewCsvAutofillError("Review CSV is missing a header.")
        fieldnames = [str(field) for field in reader.fieldnames]
        missing = sorted(REQUIRED_COLUMNS - set(fieldnames))
        if missing:
            raise BrandReviewCsvAutofillError("Review CSV is missing a required column.")
        rows = [{key: value or "" for key, value in row.items()} for row in reader]
    if not rows:
        raise BrandReviewCsvAutofillError("Review CSV is empty.")
    return rows, fieldnames


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read JSONL object rows.

    Args:
        path: JSONL path.

    Returns:
        JSON object rows.
    """
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise BrandReviewCsvAutofillError("JSONL rows must be objects.")
        rows.append(row)
    return rows


def _validate_decision(
    *,
    decision: str,
    manufacturer: str,
    product_name: str,
    reason_codes: list[str],
) -> None:
    """Validate generated decision fields against the downstream schema.

    Args:
        decision: Decision token.
        manufacturer: Reviewed manufacturer.
        product_name: Reviewed product name.
        reason_codes: Review reason codes.
    """
    payload = {
        "decision": decision,
        "reviewer_id": "operator_autofill_catalog",
        "reviewed_at": "autofill_catalog",
        "reviewed_manufacturer": manufacturer,
        "reviewed_product_name": product_name,
        "reason_codes": reason_codes,
        "attest_brand_product_review_completed": True,
        "attest_not_using_product_folder_literal_as_manufacturer": True,
        "attest_product_name_reviewed_from_label_or_safe_catalog": True,
        "attest_no_raw_ocr_or_provider_payload_copied": True,
        "attest_db_import_allowed": True,
    }
    applier._validate_decision(payload)


def _safe_review_text(value: str, *, max_length: int) -> str | None:
    """Return downstream-safe review text.

    Args:
        value: Candidate text.
        max_length: Maximum length.

    Returns:
        Safe text or ``None``.
    """
    try:
        return applier._safe_display_text(value, max_length=max_length)
    except ValueError:
        return None


def _safe_source_product_id(value: Any) -> str | None:
    """Return safe source product id when available.

    Args:
        value: Candidate source product id.

    Returns:
        Safe source product id or ``None``.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return applier._required_safe_token(value.strip(), field_name="source_product_id")
    except ValueError:
        return None


def _safe_filename(value: str) -> str:
    """Return a safe output filename.

    Args:
        value: Candidate filename.

    Returns:
        Safe filename.
    """
    if "/" in value or "\\" in value or not value.strip():
        raise BrandReviewCsvAutofillError("Unsafe filename.")
    return value.strip()


def _reject_public_summary_unsafe(summary: Mapping[str, Any]) -> None:
    """Reject unsafe fields in public count-only summaries.

    Args:
        summary: Summary payload.
    """
    applier._reject_unsafe_payload(summary)
    text = json.dumps(summary, ensure_ascii=False)
    if "reviewed_product_name" in text or "reviewed_manufacturer" in text:
        raise BrandReviewCsvAutofillError("Public summary must remain count-only.")


def _cli_summary(summary: Mapping[str, Any]) -> dict[str, Any]:
    """Return compact CLI summary.

    Args:
        summary: Full summary.

    Returns:
        Compact summary.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "input_csv_count": int(summary.get("input_csv_count") or 0),
        "row_count": int(summary.get("row_count") or 0),
        "decision_counts": dict(summary.get("decision_counts") or {}),
        "reason_counts": dict(summary.get("reason_counts") or {}),
        "db_write_performed": False,
    }


if __name__ == "__main__":
    raise SystemExit(main())
