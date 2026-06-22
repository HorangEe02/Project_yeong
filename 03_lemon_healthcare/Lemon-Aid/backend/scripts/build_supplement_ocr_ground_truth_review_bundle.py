"""Build a local-only bundle for supplement OCR ground-truth review.

The bundle wraps rows from ``export_supplement_ocr_ground_truth_template.py`` so
an operator can inspect PII-cleared review images and edit a copied JSONL
template with human-reviewed product, ingredient, intake, and precaution facts.

This script does not infer text, does not call OCR providers, does not write to
the database, does not train PaddleOCR, and does not emit local absolute paths,
raw OCR text, provider payloads, product directory literals, or image bytes.

References:
    https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html
    https://cloud.google.com/vision/docs/ocr
    https://api.ncloud-docs.com/docs/en/ai-application-service-ocr
"""

from __future__ import annotations

import argparse
import html
import json
import shutil
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts import build_supplement_ocr_benchmark_manifest as benchmark  # noqa: E402
from scripts import export_supplement_ocr_ground_truth_template as template_export  # noqa: E402

SCHEMA_VERSION = "supplement-ocr-ground-truth-review-bundle-v1"
EXPECTED_TEMPLATE_ROW_SCHEMA_VERSION = template_export.ROW_SCHEMA_VERSION
HTML_INDEX_NAME = "ground-truth-index.html"
GROUND_TRUTH_TEMPLATE_NAME = "ground-truth.todo.jsonl"
README_NAME = "README.md"
SUMMARY_NAME = "summary.json"
SOURCE_DOC_URLS = template_export.SOURCE_DOC_URLS


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
    """Write a local-only ground-truth bundle and print a redacted summary.

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
    """Build a local OCR ground-truth review bundle.

    Args:
        template_path: Manual OCR ground-truth template JSONL.
        output_dir: Directory where bundle files are written.
        source_run_id: Optional operator run id.
        limit: Optional maximum number of reviewable rows.

    Returns:
        Redacted bundle summary.

    Raises:
        ValueError: If rows are malformed, unsafe, duplicated, or not
            materialized with safe relative image paths.
    """
    if limit is not None and limit < 0:
        raise ValueError("limit must be nonnegative.")
    template_path = template_path.expanduser().resolve()
    rows = _read_template_rows(template_path)
    review_rows, skip_reasons = _reviewable_rows(
        rows, source_base=template_path.parent, limit=limit
    )
    ground_truth_rows = [_ground_truth_template_row(row) for row in review_rows]
    html_text = _html_index(review_rows)
    readme_text = _readme_text()
    summary = _summary(
        template_path=template_path,
        source_run_id=source_run_id,
        template_row_count=len(rows),
        review_rows=review_rows,
        ground_truth_rows=ground_truth_rows,
        skip_reasons=skip_reasons,
        limit=limit,
    )
    payload = {
        "html": html_text,
        "readme": readme_text,
        "ground_truth_rows": ground_truth_rows,
        "summary": summary,
    }
    benchmark._reject_unsafe_payload(payload)

    output_dir.mkdir(parents=True, exist_ok=True)
    image_copied_count = _copy_review_images(
        review_rows,
        source_base=template_path.parent,
        output_dir=output_dir,
    )
    summary["image_copied_count"] = image_copied_count
    benchmark._reject_unsafe_payload(summary)
    (output_dir / HTML_INDEX_NAME).write_text(html_text, encoding="utf-8")
    (output_dir / GROUND_TRUTH_TEMPLATE_NAME).write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in ground_truth_rows
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
    """Read and validate manual ground-truth template rows.

    Args:
        path: Template JSONL path.

    Returns:
        Validated template rows.

    Raises:
        ValueError: If rows are unsafe, duplicated, or not pending GT rows.
    """
    rows = benchmark._read_jsonl(path)
    seen: set[str] = set()
    for row in rows:
        benchmark._reject_unsafe_payload(row)
        if row.get("schema_version") != EXPECTED_TEMPLATE_ROW_SCHEMA_VERSION:
            raise ValueError("Supplement OCR GT bundle requires ground-truth template rows.")
        fixture_id = benchmark._safe_required_token(row.get("fixture_id"), field_name="fixture_id")
        if fixture_id in seen:
            raise ValueError(f"Duplicate supplement OCR GT template fixture_id: {fixture_id}")
        seen.add(fixture_id)
        if row.get("source_kind") != "review":
            raise ValueError("Supplement OCR GT bundle only accepts review-image rows.")
        if row.get("contains_personal_data") is not False:
            raise ValueError("Supplement OCR GT rows must be PII-cleared before review.")
        if row.get("external_transfer_allowed") is not True:
            raise ValueError("Supplement OCR GT rows must be teacher-transfer eligible.")
        if row.get("teacher_ocr_allowed") is not True:
            raise ValueError("Supplement OCR GT rows must be teacher-OCR eligible.")
        if row.get("ready_for_benchmark_after_review") is not False:
            raise ValueError("Supplement OCR GT bundle only accepts pre-benchmark rows.")
        if row.get("paddleocr_training_performed") is not False:
            raise ValueError("Supplement OCR GT bundle cannot include trained rows.")
    return rows


def _reviewable_rows(
    rows: list[dict[str, Any]],
    *,
    source_base: Path,
    limit: int | None,
) -> tuple[list[dict[str, Any]], Counter[str]]:
    """Return rows that have materialized images ready for local GT review.

    Args:
        rows: Ground-truth template rows.
        source_base: Directory containing relative template image paths.
        limit: Optional maximum row count.

    Returns:
        Reviewable rows and skip reason counts.
    """
    review_rows: list[dict[str, Any]] = []
    skip_reasons: Counter[str] = Counter()
    for row in rows:
        if limit is not None and len(review_rows) >= limit:
            skip_reasons["limit_reached"] += 1
            continue
        image_path = row.get("image_path")
        if not isinstance(image_path, str) or not image_path:
            skip_reasons["missing_materialized_image_path"] += 1
            continue
        _safe_relative_image_path(image_path)
        if not (source_base / image_path).is_file():
            skip_reasons["materialized_image_file_not_found"] += 1
            continue
        review_rows.append(row)
    return review_rows, skip_reasons


def _copy_review_images(
    rows: list[dict[str, Any]],
    *,
    source_base: Path,
    output_dir: Path,
) -> int:
    """Copy materialized review images into the ground-truth bundle.

    Args:
        rows: Reviewable rows.
        source_base: Directory containing source relative image paths.
        output_dir: Bundle output directory.

    Returns:
        Number of copied or already-present image files.
    """
    copied_count = 0
    for row in rows:
        image_path = _safe_relative_image_path(str(row.get("image_path")))
        source = (source_base / image_path).resolve()
        destination = (output_dir / image_path).resolve()
        if source == destination:
            copied_count += 1
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied_count += 1
    return copied_count


def _ground_truth_template_row(row: dict[str, Any]) -> dict[str, Any]:
    """Return a copied editable ground-truth row.

    Args:
        row: Reviewable ground-truth template row.

    Returns:
        Editable row accepted by the benchmark manifest script after review.
    """
    copied = dict(row)
    copied["review_bundle_hint"] = {
        "set_ground_truth_status_after_review": "human_reviewed",
        "set_expected_verification_status_after_review": "human_reviewed",
        "set_ready_for_benchmark_after_review": True,
    }
    benchmark._reject_unsafe_payload(copied)
    return copied


def _html_index(rows: list[dict[str, Any]]) -> str:
    """Return static local-only HTML for ground-truth review.

    Args:
        rows: Reviewable rows.

    Returns:
        HTML string with relative image references only.
    """
    cards = "\n".join(_html_card(row, index=index + 1) for index, row in enumerate(rows))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Supplement OCR Ground Truth Review</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 24px; background: #f6f7f9; color: #17202a; }}
    header {{ max-width: 980px; margin: 0 auto 24px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; max-width: 1280px; margin: 0 auto; }}
    article {{ background: white; border: 1px solid #dde2e8; border-radius: 8px; padding: 14px; }}
    img {{ width: 100%; max-height: 560px; object-fit: contain; background: #111; border-radius: 6px; }}
    code {{ word-break: break-all; }}
    .meta {{ color: #52606d; font-size: 13px; line-height: 1.5; }}
    .checklist {{ margin: 10px 0 0; padding-left: 20px; color: #24313f; }}
  </style>
</head>
<body>
  <header>
    <h1>Supplement OCR Ground Truth Review</h1>
    <p>Inspect local PII-cleared review images and edit <code>{html.escape(GROUND_TRUTH_TEMPLATE_NAME)}</code>. Copy only visible product, ingredient, intake, precaution, and section facts. Do not add medical interpretation.</p>
  </header>
  <main class="grid">
{cards}
  </main>
</body>
</html>
"""


def _html_card(row: dict[str, Any], *, index: int) -> str:
    """Return one HTML review card.

    Args:
        row: Reviewable row.
        index: One-based display index.

    Returns:
        HTML card.
    """
    image_path = _safe_relative_image_path(str(row.get("image_path")))
    fixture_id = benchmark._safe_required_token(row.get("fixture_id"), field_name="fixture_id")
    category_key = benchmark._safe_required_token(
        row.get("category_key"), field_name="category_key"
    )
    source_ref = benchmark._safe_required_token(row.get("source_ref"), field_name="source_ref")
    size_bytes = benchmark._safe_nonnegative_int(row.get("image_size_bytes"))
    allowed_sections = [
        benchmark._safe_required_token(section, field_name="allowed_label_section")
        for section in row.get("allowed_label_sections", [])
        if isinstance(section, str)
    ]
    return f"""    <article>
      <h2>{index}. <code>{html.escape(fixture_id)}</code></h2>
      <img src="{html.escape(image_path)}" alt="ground-truth review image for {html.escape(fixture_id)}">
      <p class="meta">category: <code>{html.escape(category_key)}</code><br>source: <code>{html.escape(source_ref)}</code><br>size: {size_bytes} bytes</p>
      <p class="meta">sections: {html.escape(", ".join(allowed_sections))}</p>
      <ul class="checklist">
        <li>Fill only visible label facts in the JSONL expected object.</li>
        <li>Use visible precaution sentences without summarizing medical meaning.</li>
        <li>After double-checking, set ground_truth_status and expected.verification_status to human_reviewed.</li>
      </ul>
    </article>"""


def _readme_text() -> str:
    """Return bundle instructions.

    Returns:
        Markdown instructions.
    """
    return """# Supplement OCR Ground Truth Review Bundle

Open `ground-truth-index.html` locally and inspect each PII-cleared review
image. Edit `ground-truth.todo.jsonl` after review.

For each row, fill only facts visible in the image:

- product name and manufacturer when visible
- ingredient display name, amount, unit, and optional nutrient code
- intake method text or simple structured timing
- visible precaution and functional-claim sentences
- visible label section types

Do not add medical interpretation, raw OCR provider output, local paths, URLs,
or free-form notes. After double-checking the row, set:

- `ground_truth_status` to `human_reviewed`
- `expected.verification_status` to `human_reviewed`
- `ready_for_benchmark_after_review` to `true`

Then pass the edited JSONL to `build_supplement_ocr_benchmark_manifest.py`.
"""


def _summary(
    *,
    template_path: Path,
    source_run_id: str | None,
    template_row_count: int,
    review_rows: list[dict[str, Any]],
    ground_truth_rows: list[dict[str, Any]],
    skip_reasons: Counter[str],
    limit: int | None,
) -> dict[str, Any]:
    """Return a redacted bundle summary.

    Args:
        template_path: Source template path.
        source_run_id: Optional operator run id.
        template_row_count: Input row count.
        review_rows: Rows included in the bundle.
        ground_truth_rows: Editable JSONL rows.
        skip_reasons: Skip reason counts.
        limit: Optional row limit.

    Returns:
        Summary dictionary.
    """
    category_counts = Counter(str(row["category_key"]) for row in review_rows)
    return {
        "schema_version": SCHEMA_VERSION,
        "source_run_id": source_run_id,
        "generated_at": datetime.now(UTC).isoformat(),
        "template_name": template_path.name,
        "template_hash": benchmark._sha256_text(str(template_path.expanduser())),
        "template_row_count": template_row_count,
        "reviewable_row_count": len(review_rows),
        "ground_truth_template_row_count": len(ground_truth_rows),
        "category_counts": dict(sorted(category_counts.items())),
        "skip_reason_counts": dict(sorted(skip_reasons.items())),
        "limit": limit,
        "html_index_name": HTML_INDEX_NAME,
        "ground_truth_template_name": GROUND_TRUTH_TEMPLATE_NAME,
        "readme_name": README_NAME,
        "image_path_style": "relative_private_hashed_fixture_copy",
        "manual_review_required_count": len(review_rows),
        "ready_for_benchmark_rows": 0,
        "db_write_performed": False,
        "ocr_provider_call_performed": False,
        "paddleocr_training_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "source_doc_urls": list(SOURCE_DOC_URLS),
    }


def _safe_relative_image_path(value: str) -> str:
    """Validate and return a relative image path.

    Args:
        value: Candidate image path.

    Returns:
        The validated path.

    Raises:
        ValueError: If the path is absolute, traversing, or outside images/.
    """
    if value.startswith("/") or value.startswith("\\") or "://" in value:
        raise ValueError("Supplement OCR GT review bundle requires relative image paths.")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError("Supplement OCR GT review bundle image paths must be safe relative paths.")
    if path.parts[0] != "images":
        raise ValueError("Supplement OCR GT review bundle image paths must stay under images/.")
    return value


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
        "template_hash": benchmark._sha256_text(str(template_path.expanduser())),
        "output_dir_hash": benchmark._sha256_text(str(output_dir.expanduser())),
        "error_code": type(error).__name__,
        "error_message": "Supplement OCR ground-truth review bundle build failed.",
        "reviewable_row_count": 0,
        "db_write_performed": False,
        "ocr_provider_call_performed": False,
        "paddleocr_training_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
    }


if __name__ == "__main__":
    main()
