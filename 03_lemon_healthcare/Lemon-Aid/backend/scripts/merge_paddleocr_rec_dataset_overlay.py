"""Merge a PaddleOCR recognition overlay dataset into a base dataset.

This is intended for stage4 diagnostic fine-tuning where a small hard-case
overlay is appended to an existing large recognition dataset. The script emits
only count summaries and never prints labels or private image paths.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

COUNT_FILES = {
    "train": Path("rec/rec_gt_train.txt"),
    "val": Path("rec/rec_gt_val.txt"),
}


class DatasetOverlayMergeError(RuntimeError):
    """Raised when the overlay dataset cannot be merged safely."""


def _line_count(path: Path) -> int:
    """Return number of UTF-8 text lines in a file."""
    if not path.is_file():
        return 0
    return sum(1 for _line in path.open(encoding="utf-8"))


def _read_lines(path: Path) -> list[str]:
    """Read non-empty label rows without logging their content."""
    if not path.is_file():
        return []
    return [line for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def _read_dict(path: Path) -> set[str]:
    """Read dictionary characters from a UTF-8 dictionary file."""
    if not path.is_file():
        return set()
    return {line for line in path.read_text(encoding="utf-8-sig").splitlines() if line}


def _copy_overlay_images(*, overlay_dir: Path, output_dir: Path) -> int:
    """Copy overlay recognition images into an already-copied base dataset.

    Args:
        overlay_dir: Overlay dataset root.
        output_dir: Output dataset root.

    Returns:
        Copied image count.

    Raises:
        DatasetOverlayMergeError: If an overlay image would overwrite a base image.
    """
    source_root = overlay_dir / "rec" / "images"
    if not source_root.is_dir():
        return 0
    copied = 0
    for source in source_root.rglob("*"):
        if not source.is_file():
            continue
        relative = source.relative_to(overlay_dir)
        destination = output_dir / relative
        if destination.exists():
            raise DatasetOverlayMergeError("overlay image would overwrite an existing image.")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied += 1
    return copied


def merge_rec_dataset_overlay(
    *,
    base_dir: Path,
    overlay_dir: Path,
    output_dir: Path,
) -> dict[str, Any]:
    """Merge one PaddleOCR rec overlay into a copied base dataset.

    Args:
        base_dir: Existing base PaddleOCR rec dataset.
        overlay_dir: Small overlay dataset to append.
        output_dir: New dataset root. Must not already exist.

    Returns:
        Count-only merge summary.

    Raises:
        DatasetOverlayMergeError: If required inputs are missing or output exists.
    """
    if not (base_dir / "rec").is_dir():
        raise DatasetOverlayMergeError("base dataset rec directory is missing.")
    if not (overlay_dir / "rec").is_dir():
        raise DatasetOverlayMergeError("overlay dataset rec directory is missing.")
    if output_dir.exists():
        raise DatasetOverlayMergeError("output directory already exists.")

    shutil.copytree(base_dir, output_dir)
    overlay_image_count = _copy_overlay_images(overlay_dir=overlay_dir, output_dir=output_dir)

    split_counts: dict[str, dict[str, int]] = {}
    for split, relative_path in COUNT_FILES.items():
        base_rows = _read_lines(base_dir / relative_path)
        overlay_rows = _read_lines(overlay_dir / relative_path)
        (output_dir / relative_path).write_text(
            "\n".join(base_rows + overlay_rows) + "\n",
            encoding="utf-8",
        )
        split_counts[split] = {
            "base": len(base_rows),
            "overlay": len(overlay_rows),
            "output": len(base_rows) + len(overlay_rows),
        }

    merged_dict = _read_dict(base_dir / "dict.txt") | _read_dict(overlay_dir / "dict.txt")
    (output_dir / "dict.txt").write_text(
        "\n".join(sorted(merged_dict)) + ("\n" if merged_dict else ""),
        encoding="utf-8",
    )
    summary = {
        "schema_version": "paddleocr-rec-overlay-merge-v1",
        "split_counts": split_counts,
        "dict_rows": len(merged_dict),
        "overlay_image_count": overlay_image_count,
        "label_text_printed": False,
        "private_source_paths_printed": False,
        "raw_ocr_text_stored": False,
        "provider_payload_stored": False,
    }
    (output_dir / "overlay-merge-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-dir", required=True, type=Path)
    parser.add_argument("--overlay-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    args = parse_args(argv)
    try:
        summary = merge_rec_dataset_overlay(
            base_dir=args.base_dir,
            overlay_dir=args.overlay_dir,
            output_dir=args.output_dir,
        )
    except DatasetOverlayMergeError as exc:
        print(json.dumps({"status": "failed", "reason": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
