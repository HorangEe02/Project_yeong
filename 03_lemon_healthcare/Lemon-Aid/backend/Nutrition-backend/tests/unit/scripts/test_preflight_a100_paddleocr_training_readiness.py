"""Tests for the A100 PaddleOCR training readiness preflight."""

from __future__ import annotations

import importlib
import json
import sys
import unicodedata
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

preflight = importlib.import_module("scripts.preflight_a100_paddleocr_training_readiness")


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> Path:
    """Write JSONL rows.

    Args:
        path: Destination path.
        rows: JSON rows.

    Returns:
        Written path.
    """
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    return path


def _product(root: Path, name: str, *, detail_image_count: int) -> Path:
    """Create one product fixture with a decomposed Korean detail-page folder.

    Args:
        root: Crawl root.
        name: Product directory name.
        detail_image_count: Number of detail-page image files.

    Returns:
        Product directory.
    """
    product_dir = root / "category" / name
    detail_dir = product_dir / unicodedata.normalize("NFD", "상세페이지")
    detail_dir.mkdir(parents=True)
    for index in range(detail_image_count):
        (detail_dir / f"detail-{index}.jpg").write_bytes(b"image")
    return product_dir


def _write_dataset(dataset_dir: Path, *, train: int, val: int, dict_rows: int) -> None:
    """Write a minimal count-only PaddleOCR rec dataset.

    Args:
        dataset_dir: Dataset root.
        train: Train row count.
        val: Validation row count.
        dict_rows: Dictionary row count.
    """
    rec_dir = dataset_dir / "rec"
    rec_dir.mkdir(parents=True)
    (rec_dir / "rec_gt_train.txt").write_text("x\tplaceholder\n" * train, encoding="utf-8")
    (rec_dir / "rec_gt_val.txt").write_text("x\tplaceholder\n" * val, encoding="utf-8")
    (dataset_dir / "dict.txt").write_text("x\n" * dict_rows, encoding="utf-8")


def test_readiness_blocks_when_v2_dataset_is_missing(tmp_path: Path) -> None:
    """Verify source readiness alone is not enough to transfer or train."""
    crawl_root = tmp_path / "crawl"
    _product(crawl_root, "product-1", detail_image_count=2)
    splits = _write_jsonl(tmp_path / "splits.jsonl", [])

    summary = preflight.build_a100_paddleocr_training_readiness(
        crawl_root=crawl_root,
        splits_path=splits,
        dataset_dir=tmp_path / "dataset",
        max_images_per_product=3,
        expected_products_with_detail_images=1,
        expected_detail_images_at_cap=2,
        expected_train_rows=2,
        expected_val_rows=1,
        expected_dict_rows=3,
    )
    serialized = json.dumps(summary, ensure_ascii=False, sort_keys=True)

    assert summary["status"] == "blocked_by_dataset_count_gate"
    assert summary["source_count_gate"]["passed"] is True
    assert summary["dataset_count_gate"]["passed"] is False
    assert summary["ready_for_a100_transfer"] is False
    assert "placeholder" not in serialized
    assert str(tmp_path) not in serialized


def test_readiness_passes_when_source_and_dataset_counts_match(tmp_path: Path) -> None:
    """Verify matching source and dataset gates allow A100 transfer readiness."""
    crawl_root = tmp_path / "crawl"
    _product(crawl_root, "product-1", detail_image_count=4)
    _product(crawl_root, "product-2", detail_image_count=1)
    splits = _write_jsonl(tmp_path / "splits.jsonl", [])
    dataset_dir = tmp_path / "dataset"
    _write_dataset(dataset_dir, train=2, val=1, dict_rows=3)

    summary = preflight.build_a100_paddleocr_training_readiness(
        crawl_root=crawl_root,
        splits_path=splits,
        dataset_dir=dataset_dir,
        max_images_per_product=3,
        expected_products_with_detail_images=2,
        expected_detail_images_at_cap=4,
        expected_train_rows=2,
        expected_val_rows=1,
        expected_dict_rows=3,
    )
    serialized = json.dumps(summary, ensure_ascii=False, sort_keys=True)

    assert summary["status"] == "ready_for_a100_transfer"
    assert summary["ready_for_a100_transfer"] is True
    assert summary["source_count_gate"]["actual"] == {
        "products_with_detail_images": 2,
        "detail_images_at_cap": 4,
    }
    assert summary["dataset_count_gate"]["passed"] is True
    assert "placeholder" not in serialized
    assert str(tmp_path) not in serialized
    assert summary["label_text_printed"] is False
    assert summary["crop_paths_printed"] is False


def test_readiness_blocks_source_count_mismatch_before_dataset_gate_status(tmp_path: Path) -> None:
    """Verify a source-count mismatch blocks even when dataset counts are valid."""
    crawl_root = tmp_path / "crawl"
    _product(crawl_root, "product-1", detail_image_count=1)
    splits = _write_jsonl(tmp_path / "splits.jsonl", [])
    dataset_dir = tmp_path / "dataset"
    _write_dataset(dataset_dir, train=2, val=1, dict_rows=3)

    summary = preflight.build_a100_paddleocr_training_readiness(
        crawl_root=crawl_root,
        splits_path=splits,
        dataset_dir=dataset_dir,
        max_images_per_product=3,
        expected_products_with_detail_images=2,
        expected_detail_images_at_cap=4,
        expected_train_rows=2,
        expected_val_rows=1,
        expected_dict_rows=3,
    )

    assert summary["status"] == "blocked_by_source_count_gate"
    assert summary["source_count_gate"]["passed"] is False
    assert summary["dataset_count_gate"]["passed"] is True
