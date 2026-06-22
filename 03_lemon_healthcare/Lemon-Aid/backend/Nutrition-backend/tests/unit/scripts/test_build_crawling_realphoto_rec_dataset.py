"""Tests for the crawling-detail PaddleOCR rec dataset builder."""

from __future__ import annotations

import importlib
import sys
import unicodedata
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

builder = importlib.import_module("scripts.build_crawling_realphoto_rec_dataset")


def _product(root: Path, name: str, *, detail_image_count: int) -> Path:
    """Create one product fixture with a decomposed Korean detail-page folder.

    Args:
        root: Crawl root.
        name: Product directory name.
        detail_image_count: Number of detail-page image files.

    Returns:
        Product directory path.
    """
    product_dir = root / "category" / name
    detail_dir = product_dir / unicodedata.normalize("NFD", "상세페이지")
    detail_dir.mkdir(parents=True)
    for index in range(detail_image_count):
        (detail_dir / f"detail-{index}.jpg").write_bytes(b"image")
    return product_dir


def test_iter_products_accepts_decomposed_detail_page_directory(tmp_path: Path) -> None:
    """Verify Korean detail-page folders are matched after Unicode normalization."""
    product_dir = _product(tmp_path, "product-1", detail_image_count=1)

    products = builder._iter_products(tmp_path)

    assert products == [product_dir]
    assert builder._detail_images(product_dir) == [
        product_dir / unicodedata.normalize("NFD", "상세페이지") / "detail-0.jpg"
    ]


def test_dry_run_source_counts_apply_per_product_image_cap(tmp_path: Path) -> None:
    """Verify dry-run source counts mirror the v2 max-images-per-product gate."""
    products = [
        _product(tmp_path, "product-1", detail_image_count=4),
        _product(tmp_path, "product-2", detail_image_count=2),
        _product(tmp_path, "product-3", detail_image_count=0),
    ]

    summary = builder._dry_run_source_counts(products, max_images_per_product=3)

    assert summary == {
        "products_with_detail_images": 2,
        "detail_images_at_cap": 5,
    }
