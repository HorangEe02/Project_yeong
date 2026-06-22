"""Preflight local readiness for the A100 PaddleOCR recognition training run.

This script performs only count-based checks. It does not call external OCR
providers, does not create teacher labels, and does not print label text, crop
paths, absolute paths, or provider payloads.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
NUTRITION_BACKEND_ROOT = BACKEND_ROOT / "Nutrition-backend"
for candidate in (BACKEND_ROOT, NUTRITION_BACKEND_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from scripts import build_crawling_realphoto_rec_dataset as dataset_builder  # noqa: E402
from scripts import validate_paddleocr_rec_dataset_counts as count_gate  # noqa: E402

DEFAULT_EXPECTED_PRODUCTS_WITH_DETAIL_IMAGES = 342
DEFAULT_EXPECTED_DETAIL_IMAGES_AT_CAP = 885


def _dataset_count_summary(
    *,
    dataset_dir: Path,
    expected_train_rows: int,
    expected_val_rows: int,
    expected_dict_rows: int,
) -> dict[str, Any]:
    """Return the dataset count-gate summary without raising.

    Args:
        dataset_dir: Candidate PaddleOCR recognition dataset root.
        expected_train_rows: Expected train label row count.
        expected_val_rows: Expected validation label row count.
        expected_dict_rows: Expected character dictionary row count.

    Returns:
        Count-gate summary with ``passed`` set to false on failure.
    """
    try:
        return count_gate.validate_paddleocr_rec_dataset_counts(
            dataset_dir=dataset_dir,
            expected_train_rows=expected_train_rows,
            expected_val_rows=expected_val_rows,
            expected_dict_rows=expected_dict_rows,
        )
    except count_gate.DatasetCountValidationError as exc:
        return json.loads(str(exc))


def build_a100_paddleocr_training_readiness(
    *,
    crawl_root: Path,
    splits_path: Path,
    dataset_dir: Path,
    max_images_per_product: int = 3,
    expected_products_with_detail_images: int = DEFAULT_EXPECTED_PRODUCTS_WITH_DETAIL_IMAGES,
    expected_detail_images_at_cap: int = DEFAULT_EXPECTED_DETAIL_IMAGES_AT_CAP,
    expected_train_rows: int = count_gate.DEFAULT_EXPECTED_TRAIN_ROWS,
    expected_val_rows: int = count_gate.DEFAULT_EXPECTED_VAL_ROWS,
    expected_dict_rows: int = count_gate.DEFAULT_EXPECTED_DICT_ROWS,
) -> dict[str, Any]:
    """Build a count-only readiness summary for the A100 training run.

    Args:
        crawl_root: Local crawling-image corpus root.
        splits_path: Benchmark split assignment JSONL.
        dataset_dir: Candidate v2 PaddleOCR recognition dataset root.
        max_images_per_product: Detail-page image cap used by the v2 dataset builder.
        expected_products_with_detail_images: Expected product count after leakage exclusion.
        expected_detail_images_at_cap: Expected source detail-image count after cap.
        expected_train_rows: Expected train label row count.
        expected_val_rows: Expected validation label row count.
        expected_dict_rows: Expected character dictionary row count.

    Returns:
        Redacted count-only readiness summary.

    Raises:
        FileNotFoundError: If the crawl root or split assignment file is missing.
    """
    if not crawl_root.is_dir():
        raise FileNotFoundError("crawl-root is missing")
    if not splits_path.is_file():
        raise FileNotFoundError("splits file is missing")

    excluded = dataset_builder._excluded_product_hashes(splits_path)
    eligible = [
        product
        for product in dataset_builder._iter_products(crawl_root)
        if dataset_builder._product_hash(product, crawl_root) not in excluded
    ]
    source_counts = dataset_builder._dry_run_source_counts(eligible, max_images_per_product)
    expected_source_counts = {
        "products_with_detail_images": expected_products_with_detail_images,
        "detail_images_at_cap": expected_detail_images_at_cap,
    }
    source_gate_passed = all(
        source_counts[key] == expected_value
        for key, expected_value in expected_source_counts.items()
    )
    dataset_gate_summary = _dataset_count_summary(
        dataset_dir=dataset_dir,
        expected_train_rows=expected_train_rows,
        expected_val_rows=expected_val_rows,
        expected_dict_rows=expected_dict_rows,
    )

    if not source_gate_passed:
        status = "blocked_by_source_count_gate"
    elif not dataset_gate_summary["passed"]:
        status = "blocked_by_dataset_count_gate"
    else:
        status = "ready_for_a100_transfer"

    return {
        "schema_version": "a100-paddleocr-training-readiness-v1",
        "status": status,
        "ready_for_a100_transfer": status == "ready_for_a100_transfer",
        "source_count_gate": {
            "passed": source_gate_passed,
            "expected": expected_source_counts,
            "actual": source_counts,
            "eligible_product_count": len(eligible),
            "excluded_holdout_test_product_count": len(excluded),
            "max_images_per_product": max_images_per_product,
        },
        "dataset_count_gate": dataset_gate_summary,
        "next_required_action": (
            "transfer_dataset_to_a100_and_run_preflight"
            if status == "ready_for_a100_transfer"
            else "build_or_fix_v2_dataset_before_training"
        ),
        "crawl_root_printed": False,
        "splits_path_printed": False,
        "dataset_path_printed": False,
        "label_text_printed": False,
        "crop_paths_printed": False,
        "raw_provider_payload_printed": False,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional argument vector.

    Returns:
        Parsed arguments.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--crawl-root", required=True, type=Path)
    parser.add_argument("--splits", required=True, type=Path)
    parser.add_argument("--dataset-dir", required=True, type=Path)
    parser.add_argument("--max-images-per-product", default=3, type=int)
    parser.add_argument(
        "--expected-products-with-detail-images",
        default=DEFAULT_EXPECTED_PRODUCTS_WITH_DETAIL_IMAGES,
        type=int,
    )
    parser.add_argument(
        "--expected-detail-images-at-cap",
        default=DEFAULT_EXPECTED_DETAIL_IMAGES_AT_CAP,
        type=int,
    )
    parser.add_argument(
        "--expected-train-rows",
        default=count_gate.DEFAULT_EXPECTED_TRAIN_ROWS,
        type=int,
    )
    parser.add_argument(
        "--expected-val-rows",
        default=count_gate.DEFAULT_EXPECTED_VAL_ROWS,
        type=int,
    )
    parser.add_argument(
        "--expected-dict-rows",
        default=count_gate.DEFAULT_EXPECTED_DICT_ROWS,
        type=int,
    )
    parser.add_argument("--summary-output", default=None, type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the local readiness preflight.

    Args:
        argv: Optional argument vector.

    Returns:
        Process exit code.
    """
    args = parse_args(argv)
    summary = build_a100_paddleocr_training_readiness(
        crawl_root=args.crawl_root,
        splits_path=args.splits,
        dataset_dir=args.dataset_dir,
        max_images_per_product=args.max_images_per_product,
        expected_products_with_detail_images=args.expected_products_with_detail_images,
        expected_detail_images_at_cap=args.expected_detail_images_at_cap,
        expected_train_rows=args.expected_train_rows,
        expected_val_rows=args.expected_val_rows,
        expected_dict_rows=args.expected_dict_rows,
    )
    if args.summary_output is not None:
        args.summary_output.parent.mkdir(parents=True, exist_ok=True)
        args.summary_output.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if summary["ready_for_a100_transfer"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
