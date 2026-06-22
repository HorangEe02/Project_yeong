#!/usr/bin/env python3
"""Select a representative naver supplement-image sample for simulator testing.

The naver scrape holds ~138k images across 42 supplement categories, each with
per-brand product folders split into ``상세페이지`` (label/detail pages — the OCR
target) and ``리뷰`` (user review photos). This copies a small, mixed sample into
a flat staging directory with ASCII-safe filenames so it can be pushed into an
iOS Simulator (``xcrun simctl addmedia``) or Android emulator (``adb push``)
gallery without Korean/space path issues. Originals are read-only; this only
reads + copies.

Each output filename encodes ``<idx>_<category>_<kind>.<ext>`` and a manifest CSV
maps every sample back to its source path for traceability.
"""

from __future__ import annotations

import argparse
import csv
import os
import shutil
import struct
from pathlib import Path

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
DETAIL_DIR = "상세페이지"
REVIEW_DIR = "리뷰"
# Backend decode pixel cap (supplement_image_max_pixels default = 12_000_000).
MAX_PIXELS = 12_000_000


def _category_slug(name: str) -> str:
    """Romanize-free ASCII slug from a bracketed Korean category name.

    Args:
        name: Directory name such as ``[오메가3]``.

    Returns:
        ASCII slug; non-ASCII chars are dropped so names stay filesystem-safe.
    """
    inner = name.strip().strip("[]")
    out: list[str] = []
    for ch in inner:
        if ch.isascii() and ch.isalnum():
            out.append(ch)
        elif ch in (" ", "_", "-"):
            out.append("_")
    slug = "".join(out).strip("_")
    return slug or f"cat{abs(hash(name)) % 100000}"


def _jpeg_dimensions(path: Path) -> tuple[int, int] | None:
    """Read JPEG width/height from SOF markers without a full decode.

    Args:
        path: Image file path.

    Returns:
        (width, height) or None if it cannot be parsed.
    """
    try:
        with path.open("rb") as handle:
            if handle.read(2) != b"\xff\xd8":
                return None
            while True:
                marker = handle.read(2)
                if len(marker) < 2 or marker[0] != 0xFF:
                    return None
                kind = marker[1]
                if 0xC0 <= kind <= 0xCF and kind not in (0xC4, 0xC8, 0xCC):
                    handle.read(3)
                    height, width = struct.unpack(">HH", handle.read(4))
                    return width, height
                size = struct.unpack(">H", handle.read(2))[0]
                handle.seek(size - 2, os.SEEK_CUR)
    except (OSError, struct.error):
        return None


def _within_pixel_cap(path: Path) -> bool:
    """Return whether a JPEG is within the backend decode pixel cap.

    Non-JPEG or unreadable dimensions pass (the backend enforces the real cap);
    this only proactively drops the very tall detail pages that would 422.

    Args:
        path: Image file path.

    Returns:
        True when within cap or dimensions are unknown.
    """
    if path.suffix.lower() not in (".jpg", ".jpeg"):
        return True
    dims = _jpeg_dimensions(path)
    if dims is None:
        return True
    return dims[0] * dims[1] <= MAX_PIXELS


def _pick(files: list[Path], count: int) -> list[Path]:
    """Pick up to ``count`` cap-passing images spread across a folder.

    Args:
        files: Candidate image paths.
        count: Maximum to select.

    Returns:
        Selected paths.
    """
    eligible = [f for f in files if _within_pixel_cap(f)]
    if not eligible:
        return []
    if len(eligible) <= count:
        return eligible
    step = len(eligible) // count
    return [eligible[i * step] for i in range(count)]


def _images_in(folder: Path) -> list[Path]:
    """List sorted image files under a folder tree (skipping .DS_Store).

    Args:
        folder: Folder to walk.

    Returns:
        Sorted image paths.
    """
    found: list[Path] = []
    for root, _dirs, files in os.walk(folder):
        for name in files:
            if name == ".DS_Store":
                continue
            if Path(name).suffix.lower() in IMAGE_EXTS:
                found.append(Path(root) / name)
    return sorted(found)


def main() -> int:
    """Select and stage the sample set."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        default=(
            "/Volumes/Corsair EX400U Media/00_work_out/00_data_set/pr/"
            "downloads_tampermonkey/lemon-aid/_inbox/tampermonkey/naver"
        ),
    )
    parser.add_argument("--out", default="/tmp/lemon-naver-samples")
    parser.add_argument("--detail-per-category", type=int, default=2)
    parser.add_argument("--review-per-category", type=int, default=2)
    parser.add_argument("--brands-per-category", type=int, default=2)
    args = parser.parse_args()

    source = Path(args.source)
    out = Path(args.out)
    if not source.is_dir():
        print(f"SOURCE_NOT_FOUND: {source}")
        return 1
    out.mkdir(parents=True, exist_ok=True)

    manifest_rows: list[dict[str, str]] = []
    idx = 0
    categories = sorted(d for d in os.listdir(source) if (source / d).is_dir())
    for category in categories:
        cat_dir = source / category
        slug = _category_slug(category)
        brands = sorted(d for d in os.listdir(cat_dir) if (cat_dir / d).is_dir())
        used_detail = used_review = 0
        for brand in brands[: args.brands_per_category]:
            brand_dir = cat_dir / brand
            detail_dir = brand_dir / DETAIL_DIR
            review_dir = brand_dir / REVIEW_DIR
            if detail_dir.is_dir() and used_detail < args.detail_per_category:
                for src in _pick(_images_in(detail_dir), 1):
                    idx += 1
                    dst = out / f"{idx:03d}_{slug}_detail{src.suffix.lower()}"
                    shutil.copy2(src, dst)
                    manifest_rows.append(
                        {"idx": str(idx), "category": category, "kind": "detail",
                         "dest": dst.name, "source": str(src)}
                    )
                    used_detail += 1
            if review_dir.is_dir() and used_review < args.review_per_category:
                for src in _pick(_images_in(review_dir), 1):
                    idx += 1
                    dst = out / f"{idx:03d}_{slug}_review{src.suffix.lower()}"
                    shutil.copy2(src, dst)
                    manifest_rows.append(
                        {"idx": str(idx), "category": category, "kind": "review",
                         "dest": dst.name, "source": str(src)}
                    )
                    used_review += 1

    manifest = out / "_manifest.csv"
    with manifest.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["idx", "category", "kind", "dest", "source"]
        )
        writer.writeheader()
        writer.writerows(manifest_rows)

    detail_n = sum(1 for r in manifest_rows if r["kind"] == "detail")
    review_n = sum(1 for r in manifest_rows if r["kind"] == "review")
    print(f"SELECTED total={len(manifest_rows)} detail={detail_n} review={review_n}")
    print(f"OUT={out}")
    print(f"MANIFEST={manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
