"""Build a local-only bundle for supplement brand/product human review.

The bundle wraps rows from ``export_supplement_brand_review_template.py`` into
an operator-friendly HTML index, CSV review sheet, and editable decision JSONL.
It does not approve rows automatically. Only an operator-edited decision JSONL
can be passed to ``apply_supplement_brand_review_decisions.py`` to build the
approved product import manifest.

This script does not write to the database and does not emit local absolute
paths, product directory literals, raw OCR text, provider payloads, URLs, or
image bytes.

References:
    https://www.postgresql.org/docs/current/ddl-constraints.html
    https://supabase.com/docs/guides/database/postgres/row-level-security
    https://docs.sqlalchemy.org/en/21/orm/queryguide/select.html
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import io
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts import export_supplement_brand_review_template as template_export  # noqa: E402

SCHEMA_VERSION = "supplement-brand-review-bundle-v1"
EXPECTED_TEMPLATE_ROW_SCHEMA_VERSION = template_export.ROW_SCHEMA_VERSION
HTML_INDEX_NAME = "review-index.html"
CSV_NAME = "review.csv"
DECISION_TEMPLATE_NAME = "decisions.todo.jsonl"
README_NAME = "README.md"
SUMMARY_NAME = "summary.json"
SOURCE_DOC_URLS = template_export.SOURCE_DOC_URLS
CSV_FIELDS = (
    "fixture_id",
    "category_key",
    "category_display_name",
    "brand_candidate_display_name",
    "brand_candidate_key",
    "source_product_id",
    "image_count",
    "detail_page_count",
    "review_count",
    "decision",
    "reviewed_manufacturer",
    "reviewed_product_name",
    "reason_codes",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed arguments.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-run-id", default=None)
    parser.add_argument("--limit", type=int, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Write a local-only brand review bundle and print a redacted summary.

    Args:
        argv: Optional argument list for tests.
    """
    args = parse_args(argv)
    output_dir = args.output_dir.expanduser().resolve()
    try:
        summary = build_review_bundle(
            template_path=args.template,
            output_dir=output_dir,
            source_run_id=args.source_run_id,
            limit=args.limit,
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        failure = _failure_summary(
            template_path=args.template,
            output_dir=output_dir,
            error=exc,
        )
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / SUMMARY_NAME).write_text(
                json.dumps(failure, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        except OSError:
            pass
        print(json.dumps(failure, ensure_ascii=False, indent=2, sort_keys=True))
        raise SystemExit(1) from None


def build_review_bundle(
    *,
    template_path: Path,
    output_dir: Path,
    source_run_id: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Build local brand/product review bundle files.

    Args:
        template_path: Brand review template JSONL.
        output_dir: Directory where bundle files are written.
        source_run_id: Optional operator run id.
        limit: Optional maximum number of rows.

    Returns:
        Redacted bundle summary.

    Raises:
        ValueError: If rows are malformed, unsafe, duplicated, or options are
            invalid.
    """
    if limit is not None and limit < 0:
        raise ValueError("limit must be nonnegative.")
    template_path = template_path.expanduser().resolve()
    rows = _read_template_rows(template_path)
    review_rows, skip_reasons = _review_rows(rows, limit=limit)
    decision_rows = [_decision_template_row(row) for row in review_rows]
    csv_text = _csv_text(review_rows)
    html_text = _html_index(review_rows)
    readme_text = _readme_text()
    summary = _summary(
        template_path=template_path,
        source_run_id=source_run_id,
        template_row_count=len(rows),
        review_rows=review_rows,
        decision_rows=decision_rows,
        skip_reasons=skip_reasons,
        limit=limit,
    )
    payload = {
        "html": html_text,
        "csv": csv_text,
        "readme": readme_text,
        "decision_rows": decision_rows,
        "summary": summary,
    }
    template_export._reject_unsafe_payload(payload)

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / HTML_INDEX_NAME).write_text(html_text, encoding="utf-8")
    (output_dir / CSV_NAME).write_text(csv_text, encoding="utf-8")
    (output_dir / DECISION_TEMPLATE_NAME).write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in decision_rows
        ),
        encoding="utf-8",
    )
    (output_dir / README_NAME).write_text(readme_text, encoding="utf-8")
    (output_dir / SUMMARY_NAME).write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def _read_template_rows(path: Path) -> list[dict[str, Any]]:
    """Read and validate brand review template rows.

    Args:
        path: Template JSONL path.

    Returns:
        Validated rows.

    Raises:
        ValueError: If rows are unsafe, duplicated, or not review rows.
    """
    rows = template_export._read_jsonl_objects(path)
    seen: set[str] = set()
    for row in rows:
        template_export._reject_unsafe_payload(row)
        if row.get("schema_version") != EXPECTED_TEMPLATE_ROW_SCHEMA_VERSION:
            raise ValueError("Supplement brand bundle requires review template rows.")
        fixture_id = template_export._required_safe_token(
            row.get("fixture_id"), field_name="fixture_id"
        )
        if fixture_id in seen:
            raise ValueError(f"Duplicate supplement brand template fixture_id: {fixture_id}")
        seen.add(fixture_id)
        if row.get("operator_decision_required") is not True:
            raise ValueError("Supplement brand template rows must require operator decisions.")
        if row.get("approved_for_db_write") is not False:
            raise ValueError("Supplement brand bundle cannot include pre-approved rows.")
    return rows


def _review_rows(
    rows: list[dict[str, Any]],
    *,
    limit: int | None,
) -> tuple[list[dict[str, Any]], Counter[str]]:
    """Return rows included in the review bundle.

    Args:
        rows: Validated template rows.
        limit: Optional maximum row count.

    Returns:
        Review rows and skip reason counts.
    """
    review_rows: list[dict[str, Any]] = []
    skip_reasons: Counter[str] = Counter()
    for row in rows:
        if limit is not None and len(review_rows) >= limit:
            skip_reasons["limit_reached"] += 1
            continue
        review_rows.append(row)
    return review_rows, skip_reasons


def _decision_template_row(row: dict[str, Any]) -> dict[str, Any]:
    """Return an editable brand decision row.

    Args:
        row: Brand review template row.

    Returns:
        Decision JSONL row accepted by the apply script after operator edits.
    """
    decision_stub = row.get("decision_stub")
    if not isinstance(decision_stub, dict):
        raise ValueError("Supplement brand template rows require decision_stub.")
    template_export._reject_unsafe_payload(decision_stub)
    return {
        "schema_version": decision_stub.get("schema_version"),
        "fixture_id": template_export._required_safe_token(
            row.get("fixture_id"), field_name="fixture_id"
        ),
        "brand_review_decision": dict(decision_stub.get("brand_review_decision") or {}),
    }


def _csv_text(rows: list[dict[str, Any]]) -> str:
    """Return CSV review sheet text.

    Args:
        rows: Review rows.

    Returns:
        CSV text.
    """
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_FIELDS)
    writer.writeheader()
    for row in rows:
        writer.writerow(_csv_row(row))
    text = buffer.getvalue()
    template_export._reject_unsafe_payload(text)
    return text


def _csv_row(row: dict[str, Any]) -> dict[str, Any]:
    """Return one CSV row.

    Args:
        row: Brand review template row.

    Returns:
        Flat CSV row.
    """
    brand = _brand_candidate(row)
    source_counts = _source_kind_counts(row)
    return {
        "fixture_id": template_export._required_safe_token(
            row.get("fixture_id"), field_name="fixture_id"
        ),
        "category_key": template_export._required_safe_token(
            row.get("category_key"), field_name="category_key"
        ),
        "category_display_name": template_export._safe_display_text(
            row.get("category_display_name")
        ),
        "brand_candidate_display_name": template_export._safe_display_text(
            brand.get("display_name")
        ),
        "brand_candidate_key": template_export._required_safe_token(
            brand.get("brand_key"),
            field_name="brand_candidate.brand_key",
        ),
        "source_product_id": template_export._safe_optional_token(row.get("source_product_id"))
        or "",
        "image_count": template_export._safe_nonnegative_int(row.get("image_count")),
        "detail_page_count": source_counts.get("detail_page", 0),
        "review_count": source_counts.get("review", 0),
        "decision": "",
        "reviewed_manufacturer": "",
        "reviewed_product_name": "",
        "reason_codes": "",
    }


def _html_index(rows: list[dict[str, Any]]) -> str:
    """Return static HTML review index.

    Args:
        rows: Review rows.

    Returns:
        HTML string.
    """
    table_rows = "\n".join(_html_table_row(row, index=index + 1) for index, row in enumerate(rows))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Supplement Brand Review</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 24px; color: #17202a; background: #f6f7f9; }}
    main {{ max-width: 1180px; margin: 0 auto; }}
    table {{ width: 100%; border-collapse: collapse; background: white; border: 1px solid #dde2e8; }}
    th, td {{ padding: 8px 10px; border-bottom: 1px solid #edf0f3; text-align: left; font-size: 13px; }}
    th {{ background: #f0f3f6; }}
    code {{ word-break: break-all; }}
  </style>
</head>
<body>
  <main>
    <h1>Supplement Brand/Product Review</h1>
    <p>Use <code>{html.escape(CSV_NAME)}</code> for spreadsheet review and edit <code>{html.escape(DECISION_TEMPLATE_NAME)}</code> for the apply script. Do not use folder names as confirmed manufacturer without human review.</p>
    <table>
      <thead>
        <tr><th>#</th><th>fixture</th><th>category</th><th>brand candidate</th><th>images</th><th>source product id</th></tr>
      </thead>
      <tbody>
{table_rows}
      </tbody>
    </table>
  </main>
</body>
</html>
"""


def _html_table_row(row: dict[str, Any], *, index: int) -> str:
    """Return one HTML table row.

    Args:
        row: Review row.
        index: One-based row index.

    Returns:
        HTML table row.
    """
    csv_row = _csv_row(row)
    return f"""        <tr>
          <td>{index}</td>
          <td><code>{html.escape(str(csv_row["fixture_id"]))}</code></td>
          <td>{html.escape(str(csv_row["category_key"]))}</td>
          <td>{html.escape(str(csv_row["brand_candidate_display_name"]))}</td>
          <td>{html.escape(str(csv_row["image_count"]))}</td>
          <td><code>{html.escape(str(csv_row["source_product_id"]))}</code></td>
        </tr>"""


def _readme_text() -> str:
    """Return bundle instructions.

    Returns:
        Markdown instructions.
    """
    return """# Supplement Brand/Product Review Bundle

Open `review-index.html` for a compact overview or `review.csv` in a
spreadsheet. Edit `decisions.todo.jsonl` after review.

Only approve rows when the manufacturer and product name were reviewed from a
safe label or catalog context. Do not use product folder names as confirmed
manufacturer without review. Do not copy raw OCR text, provider payloads, local
paths, URLs, free-text notes, or product directory literals into decisions.

After review, run `apply_supplement_brand_review_decisions.py` with the original
taxonomy staging JSONL and the edited decision JSONL to build an approved
product import manifest. The apply step still does not write to the database.
"""


def _summary(
    *,
    template_path: Path,
    source_run_id: str | None,
    template_row_count: int,
    review_rows: list[dict[str, Any]],
    decision_rows: list[dict[str, Any]],
    skip_reasons: Counter[str],
    limit: int | None,
) -> dict[str, Any]:
    """Return a redacted bundle summary.

    Args:
        template_path: Source template path.
        source_run_id: Optional operator run id.
        template_row_count: Input row count.
        review_rows: Rows included in the bundle.
        decision_rows: Decision template rows.
        skip_reasons: Skip reason counts.
        limit: Optional row limit.

    Returns:
        Summary dictionary.
    """
    category_counts = Counter(str(row["category_key"]) for row in review_rows)
    brand_counts = Counter(_brand_candidate(row)["brand_key"] for row in review_rows)
    return {
        "schema_version": SCHEMA_VERSION,
        "source_run_id": source_run_id,
        "generated_at": datetime.now(UTC).isoformat(),
        "template_name": template_path.name,
        "template_hash": _sha256_text(str(template_path.expanduser())),
        "template_row_count": template_row_count,
        "reviewable_row_count": len(review_rows),
        "decision_template_row_count": len(decision_rows),
        "category_counts": dict(sorted(category_counts.items())),
        "brand_candidate_count": len(brand_counts),
        "skip_reason_counts": dict(sorted(skip_reasons.items())),
        "limit": limit,
        "html_index_name": HTML_INDEX_NAME,
        "csv_name": CSV_NAME,
        "decision_template_name": DECISION_TEMPLATE_NAME,
        "readme_name": README_NAME,
        "operator_decision_required_count": len(review_rows),
        "approved_for_db_write_rows": 0,
        "db_write_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "source_doc_urls": list(SOURCE_DOC_URLS),
    }


def _brand_candidate(row: dict[str, Any]) -> dict[str, Any]:
    """Return validated brand candidate object.

    Args:
        row: Brand review row.

    Returns:
        Brand candidate mapping.

    Raises:
        ValueError: If the object is missing.
    """
    brand = row.get("brand_candidate")
    if not isinstance(brand, dict):
        raise ValueError("Supplement brand template rows require brand_candidate object.")
    return brand


def _source_kind_counts(row: dict[str, Any]) -> dict[str, int]:
    """Return source kind counts.

    Args:
        row: Brand review row.

    Returns:
        Safe count mapping.
    """
    return template_export._safe_counter(row.get("source_kind_counts"))


def _sha256_text(value: str) -> str:
    """Return a SHA-256 digest for text.

    Args:
        value: Text to hash.

    Returns:
        Hex digest.
    """
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _failure_summary(
    *,
    template_path: Path,
    output_dir: Path,
    error: Exception,
) -> dict[str, Any]:
    """Return a redacted failure summary.

    Args:
        template_path: Source template path.
        output_dir: Planned output directory.
        error: Raised exception.

    Returns:
        JSON-safe failure summary.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "error",
        "template_name": template_path.name,
        "template_hash": _sha256_text(str(template_path.expanduser())),
        "output_dir_hash": _sha256_text(str(output_dir.expanduser())),
        "error_code": type(error).__name__,
        "error_message": "Supplement brand review bundle build failed.",
        "reviewable_row_count": 0,
        "approved_for_db_write_rows": 0,
        "db_write_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
    }


if __name__ == "__main__":
    main()
