"""Tests for PaddleOCR recognition overlay merge."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

merger = importlib.import_module("scripts.merge_paddleocr_rec_dataset_overlay")


def _dataset(root: Path, *, prefix: str, train_rows: int, val_rows: int) -> Path:
    """Create a tiny PaddleOCR rec dataset fixture."""
    for split, count in (("train", train_rows), ("val", val_rows)):
        image_dir = root / "rec" / "images" / split
        image_dir.mkdir(parents=True, exist_ok=True)
        rows = []
        for index in range(count):
            rel = f"rec/images/{split}/{prefix}_{split}_{index}.png"
            (root / rel).write_bytes(b"png")
            rows.append(f"{rel}\tlabel-{prefix}-{split}-{index}")
        (root / "rec" / f"rec_gt_{split}.txt").write_text(
            "\n".join(rows) + "\n",
            encoding="utf-8",
        )
    (root / "dict.txt").write_text("a\nb\n", encoding="utf-8")
    return root


def test_merge_rec_dataset_overlay_appends_counts(tmp_path: Path) -> None:
    """Verify overlay rows/images are appended without printing labels."""
    base = _dataset(tmp_path / "base", prefix="base", train_rows=2, val_rows=1)
    overlay = _dataset(tmp_path / "overlay", prefix="hardcase", train_rows=3, val_rows=2)

    summary = merger.merge_rec_dataset_overlay(
        base_dir=base,
        overlay_dir=overlay,
        output_dir=tmp_path / "merged",
    )

    assert summary["split_counts"]["train"] == {"base": 2, "overlay": 3, "output": 5}
    assert summary["split_counts"]["val"] == {"base": 1, "overlay": 2, "output": 3}
    assert summary["label_text_printed"] is False
    assert (tmp_path / "merged" / "rec" / "images" / "train" / "hardcase_train_0.png").is_file()
