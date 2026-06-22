"""Build redacted detail-page thumbnails for brand/product operator review.

The crawling-image source tree is category -> product-like folder -> review /
detail-page images. Brand/product DB import cannot trust the product-like folder
literal, so this script uses the existing review CSV identifiers to find detail
page images and emits only redacted thumbnail filenames for operator inspection.

This script does not write to the database, does not call OCR providers, does
not run LLMs, does not train PaddleOCR, and does not emit local absolute paths,
product directory literals, raw OCR text, provider payloads, or full-size source
images.

References:
    https://docs.python.org/3/library/csv.html
    https://docs.python.org/3/library/pathlib.html
    https://pillow.readthedocs.io/en/stable/reference/Image.html
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import sys
import unicodedata
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from PIL import Image

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts import audit_supplement_crawling_image_taxonomy as taxonomy_audit  # noqa: E402
from scripts import export_supplement_brand_review_template as template_export  # noqa: E402

SCHEMA_VERSION = "supplement-brand-detail-contact-sheet-v1"
HTML_INDEX_NAME = "brand-detail-contact-sheet.html"
README_NAME = "README.md"
SUMMARY_NAME = "brand-detail-contact-sheet.summary.json"
CSV_REQUIRED_FIELDS = frozenset(
    {
        "fixture_id",
        "category_key",
        "category_display_name",
        "brand_candidate_display_name",
        "source_product_id",
        "detail_page_count",
    }
)
IMAGE_SUFFIXES = taxonomy_audit.IMAGE_SUFFIXES
SOURCE_DOC_URLS = (
    "https://docs.python.org/3/library/csv.html",
    "https://docs.python.org/3/library/pathlib.html",
    "https://pillow.readthedocs.io/en/stable/reference/Image.html",
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
        "absolute_path",
        "file_path",
        "image_bytes",
        "image_base64",
        "local_path",
        "ocr_text",
        "product_dir",
        "product_dir_literal",
        "product_folder",
        "provider_payload",
        "raw_ocr",
        "raw_ocr_text",
        "raw_provider_payload",
        "source_path",
    }
)
SAFE_FILENAME_PATTERN = re.compile(r"[^0-9A-Za-z_.-]+")


@dataclass(frozen=True)
class ReviewCsvRow:
    """Safe review CSV row used to locate source detail-page images.

    Attributes:
        row_index: One-based row number from the operator CSV.
        fixture_id: Stable redacted fixture id.
        category_key: Sanitized category key.
        category_display_name: Operator-facing category display name.
        brand_candidate_display_name: Review-only brand candidate from the
            existing CSV. It is not treated as a confirmed manufacturer.
        source_product_id: Source product id extracted by the taxonomy audit.
        detail_page_count: Expected detail-page image count from the CSV.
    """

    row_index: int
    fixture_id: str
    category_key: str
    category_display_name: str
    brand_candidate_display_name: str
    source_product_id: str
    detail_page_count: int


@dataclass(frozen=True)
class CategoryIndex:
    """Redacted lookup index for crawling-image category directories.

    Attributes:
        category_dir: Source category directory. This value is used only in
            memory and is never serialized.
        product_dirs_by_source_id: Product directories grouped by source id.
    """

    category_dir: Path
    product_dirs_by_source_id: dict[str, tuple[Path, ...]]


@dataclass(frozen=True)
class MaterializedThumbnail:
    """One thumbnail emitted for operator review.

    Attributes:
        filename: Redacted thumbnail filename stored inside the output directory.
        source_kind: Safe source kind label.
    """

    filename: str
    source_kind: str = taxonomy_audit.SOURCE_KIND_DETAIL


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed arguments.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("data") / "nutrition_reference" / "crawling-image",
    )
    parser.add_argument("--review-csv", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-run-id", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--max-images-per-row", type=int, default=3)
    parser.add_argument("--thumbnail-max-side", type=int, default=420)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Write contact-sheet artifacts and print a redacted JSON summary.

    Args:
        argv: Optional argument list for tests.
    """
    args = parse_args(argv)
    output_dir = args.output_dir.expanduser().resolve()
    try:
        summary = build_detail_contact_sheet(
            root=args.root,
            review_csv=args.review_csv,
            output_dir=output_dir,
            source_run_id=args.source_run_id,
            limit=args.limit,
            max_images_per_row=args.max_images_per_row,
            thumbnail_max_side=args.thumbnail_max_side,
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        failure = _failure_summary(error=exc)
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


def build_detail_contact_sheet(
    *,
    root: Path,
    review_csv: Path,
    output_dir: Path,
    source_run_id: str | None = None,
    limit: int | None = None,
    max_images_per_row: int = 3,
    thumbnail_max_side: int = 420,
) -> dict[str, Any]:
    """Build a redacted detail-page thumbnail contact sheet.

    Args:
        root: Local crawling-image root.
        review_csv: Existing operator brand/product review CSV.
        output_dir: Directory where HTML, thumbnails, and summary are written.
        source_run_id: Optional run id for traceability.
        limit: Optional maximum number of CSV rows to include.
        max_images_per_row: Maximum thumbnails emitted per review row.
        thumbnail_max_side: Maximum thumbnail side in pixels.

    Returns:
        Redacted JSON summary of materialized thumbnails and unresolved rows.

    Raises:
        ValueError: If options are invalid, source folders are missing, or rows
            contain unsafe values.
    """
    if limit is not None and limit < 0:
        raise ValueError("limit must be nonnegative.")
    if max_images_per_row <= 0:
        raise ValueError("max_images_per_row must be positive.")
    if thumbnail_max_side <= 0:
        raise ValueError("thumbnail_max_side must be positive.")

    resolved_root = root.expanduser().resolve()
    resolved_review_csv = review_csv.expanduser().resolve()
    if not resolved_root.is_dir():
        raise ValueError("crawling image root is not a directory.")
    if not resolved_review_csv.is_file():
        raise ValueError("review CSV is not a file.")

    rows = _read_review_csv(resolved_review_csv, limit=limit)
    category_index = _build_category_index(resolved_root)
    output_dir.mkdir(parents=True, exist_ok=True)

    contact_rows: list[dict[str, Any]] = []
    unresolved_counts: Counter[str] = Counter()
    thumbnail_count = 0
    for row in rows:
        category = category_index.get(row.category_key)
        if category is None:
            unresolved_counts["category_not_found"] += 1
            contact_rows.append(_contact_row(row, matched_product_count=0, thumbnails=()))
            continue

        product_dirs = category.product_dirs_by_source_id.get(row.source_product_id, ())
        if not product_dirs:
            unresolved_counts["product_not_found"] += 1
            contact_rows.append(_contact_row(row, matched_product_count=0, thumbnails=()))
            continue

        detail_images = _detail_page_images(product_dirs)
        if not detail_images:
            unresolved_counts["detail_page_image_not_found"] += 1
            contact_rows.append(
                _contact_row(
                    row,
                    matched_product_count=len(product_dirs),
                    thumbnails=(),
                )
            )
            continue

        thumbnails: list[MaterializedThumbnail] = []
        for image_index, image_path in enumerate(detail_images[:max_images_per_row], start=1):
            filename = _thumbnail_filename(row=row, image_index=image_index)
            _write_thumbnail(
                source_path=image_path,
                output_path=output_dir / filename,
                max_side=thumbnail_max_side,
            )
            thumbnails.append(MaterializedThumbnail(filename=filename))
        thumbnail_count += len(thumbnails)
        contact_rows.append(
            _contact_row(
                row,
                matched_product_count=len(product_dirs),
                thumbnails=tuple(thumbnails),
                source_image_count=len(detail_images),
            )
        )

    summary = _summary(
        source_run_id=source_run_id,
        root=resolved_root,
        review_csv=resolved_review_csv,
        contact_rows=contact_rows,
        thumbnail_count=thumbnail_count,
        unresolved_counts=unresolved_counts,
        max_images_per_row=max_images_per_row,
        thumbnail_max_side=thumbnail_max_side,
        limit=limit,
    )
    html_text = _html_index(contact_rows)
    readme_text = _readme_text()
    _reject_unsafe_payload({"summary": summary, "html": html_text, "readme": readme_text})

    (output_dir / HTML_INDEX_NAME).write_text(html_text, encoding="utf-8")
    (output_dir / README_NAME).write_text(readme_text, encoding="utf-8")
    (output_dir / SUMMARY_NAME).write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def _read_review_csv(path: Path, *, limit: int | None) -> list[ReviewCsvRow]:
    """Read and validate an operator brand/product review CSV.

    Args:
        path: Review CSV path.
        limit: Optional row limit.

    Returns:
        Validated review rows.

    Raises:
        ValueError: If required headers are missing or values are unsafe.
    """
    rows: list[ReviewCsvRow] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = set(reader.fieldnames or ())
        missing = sorted(CSV_REQUIRED_FIELDS - fieldnames)
        if missing:
            raise ValueError(f"review CSV missing required fields: {','.join(missing)}")
        for row_index, raw in enumerate(reader, start=1):
            if limit is not None and len(rows) >= limit:
                break
            rows.append(
                ReviewCsvRow(
                    row_index=row_index,
                    fixture_id=template_export._required_safe_token(
                        raw.get("fixture_id"),
                        field_name="fixture_id",
                    ),
                    category_key=template_export._required_safe_token(
                        raw.get("category_key"),
                        field_name="category_key",
                    ),
                    category_display_name=_required_safe_text(
                        raw.get("category_display_name"),
                        field_name="category_display_name",
                    ),
                    brand_candidate_display_name=_required_safe_text(
                        raw.get("brand_candidate_display_name"),
                        field_name="brand_candidate_display_name",
                    ),
                    source_product_id=template_export._required_safe_token(
                        raw.get("source_product_id"),
                        field_name="source_product_id",
                    ),
                    detail_page_count=_safe_nonnegative_int(
                        raw.get("detail_page_count"),
                        field_name="detail_page_count",
                    ),
                )
            )
    return rows


def _build_category_index(root: Path) -> dict[str, CategoryIndex]:
    """Build a source-product lookup without serializing source paths.

    Args:
        root: Local crawling-image root.

    Returns:
        Mapping from category key to source-product id lookups.
    """
    index: dict[str, CategoryIndex] = {}
    for category_dir in taxonomy_audit._iter_child_dirs(root):
        display_name = taxonomy_audit._strip_category_brackets(category_dir.name)
        category_key = taxonomy_audit._safe_key(display_name)
        products: dict[str, list[Path]] = {}
        for product_dir in taxonomy_audit._iter_child_dirs(category_dir):
            source_product_id = taxonomy_audit._source_product_id(product_dir.name)
            if source_product_id is None:
                continue
            products.setdefault(source_product_id, []).append(product_dir)
        index[category_key] = CategoryIndex(
            category_dir=category_dir,
            product_dirs_by_source_id={
                product_id: tuple(sorted(paths, key=lambda path: _normalize_text(path.name)))
                for product_id, paths in products.items()
            },
        )
    return index


def _detail_page_images(product_dirs: tuple[Path, ...]) -> list[Path]:
    """Return deterministic detail-page image paths for matched products.

    Args:
        product_dirs: Matched source product directories.

    Returns:
        Detail-page image paths. Paths are kept in memory only.
    """
    images: list[Path] = []
    for product_dir in product_dirs:
        for image_path in product_dir.rglob("*"):
            if not image_path.is_file() or image_path.suffix.casefold() not in IMAGE_SUFFIXES:
                continue
            if taxonomy_audit._source_kind(image_path.relative_to(product_dir)) != (
                taxonomy_audit.SOURCE_KIND_DETAIL
            ):
                continue
            images.append(image_path)
    return sorted(images, key=lambda path: _normalize_text(path.name))


def _write_thumbnail(*, source_path: Path, output_path: Path, max_side: int) -> None:
    """Write a bounded JPEG thumbnail from a source image.

    Args:
        source_path: Local source image path, held only in memory.
        output_path: Redacted output thumbnail path.
        max_side: Maximum width or height in pixels.

    Raises:
        OSError: If the image cannot be decoded or written.
    """
    with Image.open(source_path) as source_image:
        source_image.thumbnail((max_side, max_side))
        output_image = source_image if source_image.mode == "RGB" else source_image.convert("RGB")
        try:
            output_image.save(output_path, format="JPEG", quality=84, optimize=True)
        finally:
            if output_image is not source_image:
                output_image.close()


def _contact_row(
    row: ReviewCsvRow,
    *,
    matched_product_count: int,
    thumbnails: tuple[MaterializedThumbnail, ...],
    source_image_count: int = 0,
) -> dict[str, Any]:
    """Return a redacted contact-sheet row.

    Args:
        row: Source review CSV row.
        matched_product_count: Number of source product folders matched in memory.
        thumbnails: Materialized thumbnails.
        source_image_count: Number of in-memory source images found.

    Returns:
        JSON-safe contact row.
    """
    return {
        "row_index": row.row_index,
        "contact_sheet_anchor": _row_anchor(row.row_index),
        "fixture_id": row.fixture_id,
        "category_key": row.category_key,
        "category_display_name": row.category_display_name,
        "brand_candidate_display_name": row.brand_candidate_display_name,
        "source_product_id": row.source_product_id,
        "expected_detail_page_count": row.detail_page_count,
        "matched_product_count": matched_product_count,
        "source_detail_page_image_count": source_image_count,
        "thumbnail_count": len(thumbnails),
        "thumbnail_filenames": [thumbnail.filename for thumbnail in thumbnails],
        "operator_decision_required": True,
        "auto_decision_performed": False,
        "db_write_allowed": False,
    }


def _summary(
    *,
    source_run_id: str | None,
    root: Path,
    review_csv: Path,
    contact_rows: list[dict[str, Any]],
    thumbnail_count: int,
    unresolved_counts: Counter[str],
    max_images_per_row: int,
    thumbnail_max_side: int,
    limit: int | None,
) -> dict[str, Any]:
    """Return a redacted contact-sheet summary.

    Args:
        source_run_id: Optional run id.
        root: Source root, hashed only.
        review_csv: Source CSV, hashed only.
        contact_rows: Redacted contact rows.
        thumbnail_count: Number of thumbnails written.
        unresolved_counts: Unresolved row reason counts.
        max_images_per_row: Thumbnail cap per row.
        thumbnail_max_side: Thumbnail side cap.
        limit: Optional row limit.

    Returns:
        JSON-safe summary.
    """
    reviewable_count = len(contact_rows)
    rows_with_thumbnails = sum(1 for row in contact_rows if int(row["thumbnail_count"]) > 0)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "source_run_id": _safe_optional_run_id(source_run_id),
        "source_root_name": root.name,
        "source_root_hash": _sha256_text(str(root)),
        "review_csv_name": review_csv.name,
        "review_csv_hash": _sha256_text(str(review_csv)),
        "reviewable_row_count": reviewable_count,
        "rows_with_thumbnails": rows_with_thumbnails,
        "rows_without_thumbnails": reviewable_count - rows_with_thumbnails,
        "thumbnail_count": thumbnail_count,
        "max_images_per_row": max_images_per_row,
        "thumbnail_max_side": thumbnail_max_side,
        "limit": limit,
        "unresolved_reason_counts": dict(sorted(unresolved_counts.items())),
        "contact_rows": contact_rows,
        "operator_decision_required": True,
        "brand_product_review_required": True,
        "db_write_performed": False,
        "db_import_allowed": False,
        "auto_decision_performed": False,
        "ocr_provider_call_performed": False,
        "external_provider_call_performed": False,
        "llm_call_performed": False,
        "paddleocr_training_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "local_path_literals_stored": False,
        "product_dir_literals_stored": False,
        "source_image_read_performed": True,
        "full_size_source_images_copied": False,
        "source_doc_urls": list(SOURCE_DOC_URLS),
    }


def _html_index(contact_rows: list[dict[str, Any]]) -> str:
    """Return a local HTML contact sheet.

    Args:
        contact_rows: Redacted contact-sheet rows.

    Returns:
        HTML document with relative thumbnail filenames only.
    """
    cards: list[str] = []
    for row in contact_rows:
        row_anchor = _row_anchor(row["row_index"])
        thumbnails = [
            f'<img src="{html.escape(filename)}" alt="detail thumbnail" loading="lazy">'
            for filename in row["thumbnail_filenames"]
        ]
        if not thumbnails:
            thumbnails = ['<p class="empty">No detail-page thumbnail materialized.</p>']
        cards.append(
            "\n".join(
                [
                    f'<article class="card" id="{html.escape(row_anchor)}">',
                    f"<h2>{html.escape(str(row['row_index']))}. "
                    f"{html.escape(str(row['brand_candidate_display_name']))}</h2>",
                    "<dl>",
                    f"<dt>contact_sheet_anchor</dt><dd>{html.escape(row_anchor)}</dd>",
                    f"<dt>fixture_id</dt><dd>{html.escape(str(row['fixture_id']))}</dd>",
                    f"<dt>category</dt><dd>{html.escape(str(row['category_display_name']))}</dd>",
                    f"<dt>source_product_id</dt><dd>{html.escape(str(row['source_product_id']))}</dd>",
                    f"<dt>expected_detail_page_count</dt><dd>{row['expected_detail_page_count']}</dd>",
                    f"<dt>matched_product_count</dt><dd>{row['matched_product_count']}</dd>",
                    "</dl>",
                    '<div class="thumbs">',
                    *thumbnails,
                    "</div>",
                    "</article>",
                ]
            )
        )
    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="ko">',
            "<head>",
            '<meta charset="utf-8">',
            "<title>Supplement Brand Detail Contact Sheet</title>",
            "<style>",
            "body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;margin:24px;background:#f6f7f8;color:#111827}",
            "main{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:16px}",
            ".card{background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:14px;box-shadow:0 1px 2px rgba(0,0,0,.04)}",
            "h1{font-size:22px;margin:0 0 12px}h2{font-size:16px;margin:0 0 10px}",
            "dl{display:grid;grid-template-columns:150px 1fr;gap:4px 8px;font-size:12px;margin:0 0 12px}",
            "dt{font-weight:700;color:#6b7280}dd{margin:0;word-break:break-word}",
            ".thumbs{display:flex;flex-wrap:wrap;gap:8px}.thumbs img{max-width:150px;max-height:150px;border:1px solid #e5e7eb;border-radius:8px;background:#fff}",
            ".empty{font-size:12px;color:#9ca3af;margin:0}",
            "</style>",
            "</head>",
            "<body>",
            "<h1>Supplement Brand/Product Detail Contact Sheet</h1>",
            "<p>This local bundle is for human review only. It does not approve DB import.</p>",
            "<main>",
            *cards,
            "</main>",
            "</body>",
            "</html>",
        ]
    )


def _readme_text() -> str:
    """Return operator instructions for the generated contact sheet."""
    return "\n".join(
        [
            "# Supplement Brand Detail Contact Sheet",
            "",
            "Use `brand-detail-contact-sheet.html` to inspect redacted thumbnails",
            "while filling the existing brand/product review CSV or decision JSONL.",
            "Triage row hints use anchors such as `brand-detail-contact-sheet.html#row-001`.",
            "",
            "Rules:",
            "- Do not treat source folder names as confirmed manufacturer/product data.",
            "- Use visible label evidence or safe catalog evidence before approving DB import.",
            "- This bundle does not run OCR, LLM, PaddleOCR training, or DB writes.",
            "- Full-size source images and local paths are not included in the summary.",
            "",
        ]
    )


def _thumbnail_filename(*, row: ReviewCsvRow, image_index: int) -> str:
    """Return a deterministic redacted thumbnail filename.

    Args:
        row: Source review row.
        image_index: One-based image index within the row.

    Returns:
        Safe JPEG filename.
    """
    base = SAFE_FILENAME_PATTERN.sub("_", row.fixture_id).strip("._-") or "fixture"
    return f"{base}-detail-{image_index:02d}.jpg"


def _row_anchor(value: Any) -> str:
    """Return a deterministic contact-sheet row anchor.

    Args:
        value: One-based CSV row index.

    Returns:
        Safe HTML fragment identifier.

    Raises:
        ValueError: If the row index is invalid.
    """
    try:
        row_index = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("row index must be an integer.") from exc
    if row_index <= 0:
        raise ValueError("row index must be positive.")
    return f"row-{row_index:03d}"


def _required_safe_text(value: Any, *, field_name: str) -> str:
    """Return bounded display text without local path markers.

    Args:
        value: Raw display value.
        field_name: Name used in validation errors.

    Returns:
        Sanitized display string.

    Raises:
        ValueError: If the value is missing or unsafe.
    """
    text = template_export._safe_display_text(value, max_length=180)
    if text is None:
        raise ValueError(f"review CSV requires field: {field_name}")
    return text


def _safe_nonnegative_int(value: Any, *, field_name: str) -> int:
    """Return a nonnegative integer parsed from CSV text.

    Args:
        value: Raw CSV value.
        field_name: Name used in validation errors.

    Returns:
        Nonnegative integer.

    Raises:
        ValueError: If parsing fails or value is negative.
    """
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"review CSV requires nonnegative integer: {field_name}") from exc
    if parsed < 0:
        raise ValueError(f"review CSV requires nonnegative integer: {field_name}")
    return parsed


def _safe_optional_run_id(value: str | None) -> str | None:
    """Return an optional safe run id.

    Args:
        value: Optional run id.

    Returns:
        Safe run id or ``None``.
    """
    if value is None:
        return None
    return template_export._required_safe_token(value, field_name="source_run_id")


def _reject_unsafe_payload(value: Any) -> None:
    """Reject raw keys, local paths, and source folder literals.

    Args:
        value: JSON-like payload.

    Raises:
        ValueError: If unsafe content is present.
    """
    if isinstance(value, dict):
        for key, child in value.items():
            normalized_key = str(key).casefold()
            if normalized_key in RAW_FORBIDDEN_KEYS:
                raise ValueError(f"Unsafe raw field present: {key}")
            _reject_unsafe_payload(child)
        return
    if isinstance(value, list | tuple):
        for child in value:
            _reject_unsafe_payload(child)
        return
    if isinstance(value, str):
        if any(marker in value for marker in LOCAL_PATH_MARKERS):
            raise ValueError("Payload contains local path marker.")
        if "상세페이지" in value or "리뷰" in value:
            raise ValueError("Payload contains source folder literal.")


def _failure_summary(*, error: Exception) -> dict[str, Any]:
    """Return a redacted failure summary.

    Args:
        error: Exception raised by bundle generation.

    Returns:
        JSON-safe failure summary.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "failed",
        "error_type": type(error).__name__,
        "error_message": str(error)[:200],
        "db_write_performed": False,
        "ocr_provider_call_performed": False,
        "external_provider_call_performed": False,
        "llm_call_performed": False,
        "paddleocr_training_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "local_path_literals_stored": False,
        "product_dir_literals_stored": False,
    }


def _sha256_text(value: str) -> str:
    """Return SHA-256 hex digest for a text value.

    Args:
        value: Text value.

    Returns:
        SHA-256 hex digest.
    """
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _normalize_text(value: str) -> str:
    """Normalize text for deterministic local sorting.

    Args:
        value: Input text.

    Returns:
        Normalized text.
    """
    return unicodedata.normalize("NFC", value)


if __name__ == "__main__":
    main()
