"""Audit the local crawling-image supplement taxonomy without moving data.

This operator tool inspects the repo-local
``data/nutrition_reference/crawling-image`` tree and returns a sanitized summary
that can be used to plan DB category/brand seeding, OCR ground-truth work, and
YOLO section-label annotation. It does not decode images, run OCR, call external
providers, or persist raw provider payloads.

References:
    https://docs.ultralytics.com/tasks/detect/
    https://docs.ultralytics.com/modes/predict/
    https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html
    https://cloud.google.com/vision/docs/ocr
    https://api.ncloud-docs.com/docs/en/ai-application-service-ocr
    https://docs.ollama.com/capabilities/vision
    https://docs.ollama.com/capabilities/structured-outputs
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "supplement-crawling-image-taxonomy-audit-v1"
IMAGE_SUFFIXES = frozenset({".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"})
SOURCE_KIND_DETAIL = "detail_page"
SOURCE_KIND_REVIEW = "review"
SOURCE_KIND_UNKNOWN = "unknown"
SOURCE_DOC_URLS = (
    "https://docs.ultralytics.com/tasks/detect/",
    "https://docs.ultralytics.com/modes/predict/",
    "https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html",
    "https://cloud.google.com/vision/docs/ocr",
    "https://api.ncloud-docs.com/docs/en/ai-application-service-ocr",
    "https://docs.ollama.com/capabilities/vision",
    "https://docs.ollama.com/capabilities/structured-outputs",
)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the taxonomy audit."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("data") / "nutrition_reference" / "crawling-image",
    )
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument(
        "--sample-products-per-category",
        type=int,
        default=3,
        help="Number of hashed product examples to include per category.",
    )
    return parser.parse_args()


def main() -> None:
    """Run the crawling-image taxonomy audit and print a sanitized JSON summary."""
    args = parse_args()
    try:
        summary = audit_crawling_image_taxonomy(
            root=args.root,
            sample_products_per_category=args.sample_products_per_category,
        )
        serialized = json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(serialized, encoding="utf-8")
        print(serialized, end="")
    except (OSError, ValueError) as exc:
        failure = _failure_summary(error=exc, root=args.root)
        print(json.dumps(failure, ensure_ascii=False, indent=2, sort_keys=True))
        raise SystemExit(1) from None


def audit_crawling_image_taxonomy(
    *,
    root: Path,
    sample_products_per_category: int = 3,
) -> dict[str, Any]:
    """Return a sanitized taxonomy and image-layout audit for crawling-image.

    Args:
        root: Local crawling-image root to inspect.
        sample_products_per_category: Number of hashed product examples to
            expose per category for debugging structure, not product identity.

    Returns:
        JSON-serializable summary with category, source-kind, and brand-candidate
        counts.

    Raises:
        ValueError: If ``root`` is missing or options are invalid.
    """
    if sample_products_per_category < 0:
        raise ValueError("sample_products_per_category must be nonnegative.")
    resolved_root = root.expanduser().resolve()
    if not resolved_root.is_dir():
        raise ValueError("crawling image root is not a directory.")

    categories: list[dict[str, Any]] = []
    global_brand_counts: Counter[str] = Counter()
    global_source_kind_counts: Counter[str] = Counter()
    issue_counts: Counter[str] = Counter()
    layout_counts: Counter[str] = Counter()
    total_products = 0
    total_images = 0
    total_non_image_files = 0

    for sort_order, category_dir in enumerate(_iter_child_dirs(resolved_root)):
        category_audit = _audit_category(
            root=resolved_root,
            category_dir=category_dir,
            sort_order=sort_order,
            sample_products_per_category=sample_products_per_category,
        )
        categories.append(category_audit)
        total_products += int(category_audit["product_count"])
        total_images += int(category_audit["image_count"])
        total_non_image_files += int(category_audit["non_image_file_count"])
        _merge_counter(layout_counts, category_audit["product_layout_counts"])
        _merge_counter(global_brand_counts, category_audit["brand_candidate_counts"])
        _merge_counter(global_source_kind_counts, category_audit["source_kind_counts"])
        _merge_counter(issue_counts, category_audit["issue_counts"])

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "source_root_name": resolved_root.name,
        "source_root_hash": _sha256_text(str(resolved_root)),
        "category_count": len(categories),
        "product_count": total_products,
        "image_count": total_images,
        "non_image_file_count": total_non_image_files,
        "product_layout_counts": dict(sorted(layout_counts.items())),
        "source_kind_counts": dict(sorted(global_source_kind_counts.items())),
        "brand_candidate_counts": _top_counter(global_brand_counts, limit=50),
        "issue_counts": dict(sorted(issue_counts.items())),
        "categories": categories,
        "observations": _build_observations(categories),
        "db_seed_contract": {
            "category_source": "top_level_folder_name",
            "brand_source": "review_required_product_folder_prefix",
            "product_source_id_source": "trailing_numeric_product_folder_suffix",
            "store_absolute_paths": False,
            "store_product_dir_literals": False,
            "requires_brand_review_before_db_write": True,
        },
        "ground_truth_contract": {
            "review_images": "OCR ground-truth candidates after PII screening",
            "detail_page_images": "YOLO section bbox annotation candidates",
            "required_sections": [
                "product_identity",
                "supplement_facts",
                "ingredient_amounts",
                "intake_method",
                "precautions",
                "allergen_warning",
            ],
            "teacher_ocr_providers": ["clova", "google_vision"],
            "target_ocr_provider": "paddleocr",
        },
        "source_doc_urls": list(SOURCE_DOC_URLS),
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
    }


def _audit_category(
    *,
    root: Path,
    category_dir: Path,
    sort_order: int,
    sample_products_per_category: int,
) -> dict[str, Any]:
    """Return one category audit row.

    Args:
        root: crawling-image root.
        category_dir: Category directory.
        sort_order: Deterministic category order.
        sample_products_per_category: Number of hashed product examples to keep.

    Returns:
        JSON-safe category audit row.
    """
    display_name = _strip_category_brackets(category_dir.name)
    product_rows: list[dict[str, Any]] = []
    brand_counts: Counter[str] = Counter()
    source_kind_counts: Counter[str] = Counter()
    issue_counts: Counter[str] = Counter()
    layout_counts: Counter[str] = Counter()
    image_count = 0
    non_image_file_count = 0

    for product_dir in _iter_child_dirs(category_dir):
        product_row = _audit_product(root=root, product_dir=product_dir)
        product_rows.append(product_row)
        image_count += int(product_row["image_count"])
        non_image_file_count += int(product_row["non_image_file_count"])
        brand = str(product_row["brand_candidate"]["display_name"])
        brand_counts[brand] += 1
        _merge_counter(layout_counts, product_row["layout_counts"])
        _merge_counter(source_kind_counts, product_row["source_kind_counts"])
        _merge_counter(issue_counts, product_row["issue_counts"])

    direct_files = [path for path in category_dir.iterdir() if path.is_file()]
    direct_image_count = sum(1 for path in direct_files if _is_image_file(path))
    direct_non_image_count = len(direct_files) - direct_image_count
    image_count += direct_image_count
    non_image_file_count += direct_non_image_count
    if direct_image_count:
        issue_counts["category_contains_direct_images"] += direct_image_count
    if direct_non_image_count:
        issue_counts["category_contains_non_image_files"] += direct_non_image_count

    sampled_products = [
        _redacted_product_sample(row) for row in product_rows[:sample_products_per_category]
    ]
    return {
        "category_key": _safe_key(display_name),
        "display_name": display_name,
        "source_folder_name": _normalize_text(category_dir.name),
        "source_folder_hash": _sha256_text(category_dir.name),
        "sort_order": sort_order,
        "product_count": len(product_rows),
        "image_count": image_count,
        "non_image_file_count": non_image_file_count,
        "product_layout_counts": dict(sorted(layout_counts.items())),
        "source_kind_counts": dict(sorted(source_kind_counts.items())),
        "brand_candidate_counts": _top_counter(brand_counts, limit=25),
        "issue_counts": dict(sorted(issue_counts.items())),
        "product_samples": sampled_products,
    }


def _audit_product(*, root: Path, product_dir: Path) -> dict[str, Any]:
    """Return a sanitized product-folder audit row.

    Args:
        root: crawling-image root.
        product_dir: Product directory.

    Returns:
        Product row with hashes, source kind counts, and a review-required brand
        candidate.
    """
    relative_product_path = product_dir.relative_to(root)
    product_id = _source_product_id(product_dir.name)
    brand_candidate = _brand_candidate(product_dir.name)
    source_kind_counts: Counter[str] = Counter()
    issue_counts: Counter[str] = Counter()
    image_count = 0
    non_image_file_count = 0
    has_review_dir = False
    has_detail_dir = False

    for path in product_dir.rglob("*"):
        if path.is_dir():
            normalized_name = _normalize_text(path.name)
            has_review_dir = has_review_dir or "리뷰" in normalized_name
            has_detail_dir = has_detail_dir or "상세페이지" in normalized_name
            continue
        if _is_image_file(path):
            source_kind = _source_kind(path.relative_to(root))
            source_kind_counts[source_kind] += 1
            image_count += 1
        else:
            non_image_file_count += 1

    if not has_review_dir:
        issue_counts["missing_review_dir"] += 1
    if not has_detail_dir:
        issue_counts["missing_detail_page_dir"] += 1
    if source_kind_counts.get(SOURCE_KIND_UNKNOWN, 0):
        issue_counts["unknown_source_kind_images"] += source_kind_counts[SOURCE_KIND_UNKNOWN]
    if product_id is None:
        issue_counts["missing_trailing_product_id"] += 1
    if not brand_candidate:
        issue_counts["missing_brand_candidate"] += 1

    layout_counts = _product_layout_counts(
        has_review_dir=has_review_dir,
        has_detail_dir=has_detail_dir,
    )

    return {
        "product_dir_hash": _sha256_text(relative_product_path.as_posix()),
        "source_product_id": product_id,
        "brand_candidate": {
            "brand_key": _safe_key(brand_candidate or "unknown"),
            "display_name": brand_candidate or "unknown",
            "verification_status": "requires_human_review",
        },
        "has_review_dir": has_review_dir,
        "has_detail_page_dir": has_detail_dir,
        "layout_counts": layout_counts,
        "image_count": image_count,
        "non_image_file_count": non_image_file_count,
        "source_kind_counts": dict(sorted(source_kind_counts.items())),
        "issue_counts": dict(sorted(issue_counts.items())),
    }


def _redacted_product_sample(row: dict[str, Any]) -> dict[str, Any]:
    """Return a product sample without product-directory literals.

    Args:
        row: Product audit row.

    Returns:
        Redacted product sample.
    """
    return {
        "product_dir_hash": row["product_dir_hash"],
        "source_product_id": row["source_product_id"],
        "brand_candidate": row["brand_candidate"],
        "has_review_dir": row["has_review_dir"],
        "has_detail_page_dir": row["has_detail_page_dir"],
        "image_count": row["image_count"],
        "source_kind_counts": row["source_kind_counts"],
        "issue_counts": row["issue_counts"],
    }


def _build_observations(categories: list[dict[str, Any]]) -> list[str]:
    """Build deterministic high-level observations for the audit summary.

    Args:
        categories: Category audit rows.

    Returns:
        Stable observation strings.
    """
    observations = [
        "top_level_category_folders_present",
        "dedicated_brand_folder_level_absent",
        "product_folder_combines_brand_product_name_and_source_product_id",
        "brand_candidates_require_human_review_before_db_write",
    ]
    if any(category["issue_counts"] for category in categories):
        observations.append("structure_issues_present")
    return observations


def _product_layout_counts(*, has_review_dir: bool, has_detail_dir: bool) -> dict[str, int]:
    """Summarize source-subfolder coverage for one product candidate.

    Args:
        has_review_dir: Whether the product candidate contains a review folder.
        has_detail_dir: Whether the product candidate contains a detail-page
            folder.

    Returns:
        A small counter-compatible mapping that is safe to aggregate without
        exposing product or folder literals.
    """
    counts: Counter[str] = Counter()
    if has_review_dir:
        counts["with_review_dir"] += 1
    else:
        counts["without_review_dir"] += 1
    if has_detail_dir:
        counts["with_detail_page_dir"] += 1
    else:
        counts["without_detail_page_dir"] += 1
    if has_review_dir and has_detail_dir:
        counts["with_review_and_detail_page_dirs"] += 1
    elif has_review_dir or has_detail_dir:
        counts["with_single_expected_source_dir"] += 1
    else:
        counts["with_no_expected_source_dirs"] += 1
    return dict(sorted(counts.items()))


def _source_kind(relative_path: Path) -> str:
    """Classify a crawling-image file by known section folder names.

    Args:
        relative_path: Path relative to the crawling-image root.

    Returns:
        ``detail_page``, ``review``, or ``unknown``.
    """
    parts = [_normalize_text(part) for part in relative_path.parts]
    if any("상세페이지" in part for part in parts):
        return SOURCE_KIND_DETAIL
    if any("리뷰" in part for part in parts):
        return SOURCE_KIND_REVIEW
    return SOURCE_KIND_UNKNOWN


def _source_product_id(folder_name: str) -> str | None:
    """Extract a trailing numeric source product id from a product folder.

    Args:
        folder_name: Product directory name.

    Returns:
        Numeric product id string when present, otherwise None.
    """
    normalized = _normalize_text(folder_name).strip()
    prefix, separator, suffix = normalized.rpartition("_")
    if separator and prefix and suffix.isdigit():
        return suffix
    return None


def _brand_candidate(folder_name: str) -> str | None:
    """Infer a review-required brand candidate from a product folder name.

    Args:
        folder_name: Product directory name.

    Returns:
        First meaningful token after removing promotional prefixes and trailing
        source product ids. The value is a candidate only and must not be treated
        as confirmed manufacturer data.
    """
    normalized = _normalize_text(folder_name).strip()
    product_name = normalized.rpartition("_")[0] if _source_product_id(normalized) else normalized
    product_name = _strip_leading_wrapped_tokens(product_name)
    product_name = product_name.strip(" -_")
    if not product_name:
        return None
    return product_name.split()[0].strip(" -_,") or None


def _strip_leading_wrapped_tokens(value: str) -> str:
    """Remove leading promotional bracket or parenthesis groups.

    Args:
        value: Raw product-folder text.

    Returns:
        Product text after removing leading ``[...]`` or ``(...)`` groups.
    """
    current = value.strip()
    while current:
        if current[0] == "[" and "]" in current:
            current = current[current.index("]") + 1 :].strip()
            continue
        if current[0] == "(" and ")" in current:
            current = current[current.index(")") + 1 :].strip()
            continue
        break
    return current


def _strip_category_brackets(value: str) -> str:
    """Return a category display name without surrounding square brackets.

    Args:
        value: Source folder name.

    Returns:
        Display name.
    """
    normalized = _normalize_text(value).strip()
    if normalized.startswith("[") and normalized.endswith("]"):
        return normalized[1:-1].strip() or "unknown"
    return normalized or "unknown"


def _safe_key(value: str) -> str:
    """Return a stable lowercase key for a display label.

    Args:
        value: Display text.

    Returns:
        Lowercase underscore-delimited key.
    """
    normalized = _normalize_text(value).casefold()
    key = re.sub(r"[^\w]+", "_", normalized, flags=re.UNICODE).strip("_")
    return key or "unknown"


def _iter_child_dirs(path: Path) -> list[Path]:
    """Return deterministic non-hidden child directories.

    Args:
        path: Parent directory.

    Returns:
        Sorted child directories.
    """
    return sorted(
        [child for child in path.iterdir() if child.is_dir() and not child.name.startswith(".")],
        key=lambda child: _normalize_text(child.name),
    )


def _is_image_file(path: Path) -> bool:
    """Check whether a path has a supported image suffix.

    Args:
        path: File path.

    Returns:
        True when the suffix looks like an image.
    """
    return path.suffix.casefold() in IMAGE_SUFFIXES


def _normalize_text(value: str) -> str:
    """Normalize decomposed macOS path text to NFC.

    Args:
        value: Input text.

    Returns:
        NFC-normalized text.
    """
    return unicodedata.normalize("NFC", value)


def _merge_counter(counter: Counter[str], values: dict[str, object]) -> None:
    """Add numeric values from a dict into a counter.

    Args:
        counter: Destination counter.
        values: Mapping with string keys and integer-like values.
    """
    for key, value in values.items():
        if isinstance(value, int):
            counter[key] += value


def _top_counter(counter: Counter[str], *, limit: int) -> dict[str, int]:
    """Return top counter values as a stable dict.

    Args:
        counter: Counter to serialize.
        limit: Maximum number of rows.

    Returns:
        Count mapping sorted by count desc then key asc.
    """
    return dict(sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:limit])


def _sha256_text(value: str) -> str:
    """Return a SHA-256 hex digest for text.

    Args:
        value: Text to hash.

    Returns:
        SHA-256 hex digest.
    """
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _failure_summary(*, error: Exception, root: Path) -> dict[str, Any]:
    """Return a sanitized failure payload without local path disclosure.

    Args:
        error: Exception raised while auditing.
        root: Requested crawling-image root.

    Returns:
        JSON-safe failure summary that redacts local absolute paths.
    """
    normalized_root = str(root.expanduser())
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": False,
        "error_type": type(error).__name__,
        "error_message": str(error).replace(normalized_root, "<redacted-root>"),
        "source_root_name": root.name,
        "source_root_hash": _sha256_text(normalized_root),
        "source_doc_urls": list(SOURCE_DOC_URLS),
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
    }


if __name__ == "__main__":
    main()
