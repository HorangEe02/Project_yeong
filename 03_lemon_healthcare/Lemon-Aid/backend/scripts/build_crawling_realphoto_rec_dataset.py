"""Scale up the real-photo PaddleOCR rec dataset from the crawling-image corpus.

The earlier real-photo dataset only used the 203 benchmark GT images. The crawling
corpus holds far more text: each product folder has a ``상세페이지`` (detail-page)
subfolder of ingredient/nutrition/usage images. This tool walks those detail
images, runs CLOVA OCR (operator-approved teacher), and emits ``<crop>\\t<text>``
recognition labels from each detected field — producing a much larger training set
to re-train the Korean recognizer on.

Design / safety:
- Source = ``<root>/<category>/<product>/상세페이지/*`` only. ``리뷰`` (user-review)
  folders are skipped (noise, not labels).
- Leakage-safe (fail-closed): a product whose ``product_dir_hash`` (sha256 of its
  path relative to the crawl root — same scheme as the benchmark) is in the
  ``holdout``/``test`` benchmark splits is EXCLUDED, so the held-out
  ``field_match_ratio`` eval stays honest. Products absent from the benchmark are
  not evaluated and may be used for training.
- Tall detail strips are vertically tiled (with overlap) before CLOVA so text
  stays legible and within provider limits; box coordinates are mapped back and
  de-duplicated across tile overlaps.
- Caps (``--max-images-per-product``, ``--max-products``, ``--limit``) bound the
  external CLOVA call volume / cost. Per-image failure isolation; seeded,
  product-grouped train/val split. Labels (teacher text) are written ONLY under a
  gitignored ``datasets/`` tree (operator-approved scope).

Runs in the py3.13 backend venv (``PYTHONPATH=Nutrition-backend``). External CLOVA
calls + label-text storage occur only with ``--apply``.

References:
    https://api.ncloud-docs.com/docs/en/ai-application-service-ocr
    https://www.paddleocr.ai/v3.3.2/en/version2.x/ppocr/model_train/recognition.html
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import random
import unicodedata
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image
from src.config import Settings, get_settings
from src.ocr.base import OCRImageInput
from src.ocr.providers.clova import (
    ClovaOCRAdapter,
    _build_clova_headers,
    _build_clova_payload,
    _validate_clova_settings,
)

DETAIL_DIR_NAME = "상세페이지"
IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".webp")
EXCLUDED_SPLITS = ("holdout", "test")
CROP_PAD = 4
MIN_CROP_SIDE = 6
MIN_VERTICES = 2
DEFAULT_TILE_HEIGHT = 1600
DEFAULT_TILE_OVERLAP = 120
DEDUP_Y_BUCKET = 24


def _product_hash(product_dir: Path, crawl_root: Path) -> str:
    """Return the benchmark-compatible product hash (sha256 of the relative path)."""
    relative = product_dir.resolve().relative_to(crawl_root.resolve())
    return hashlib.sha256(relative.as_posix().encode("utf-8")).hexdigest()


def _excluded_product_hashes(splits_path: Path) -> set[str]:
    """Return product hashes in holdout/test benchmark splits (excluded from training)."""
    excluded: set[str] = set()
    for line in splits_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if str(row.get("split")) in EXCLUDED_SPLITS:
            digest = row.get("product_dir_hash")
            if isinstance(digest, str) and digest:
                excluded.add(digest)
    return excluded


def _iter_products(crawl_root: Path) -> list[Path]:
    """Return product directories that contain a detail-page subfolder."""
    products: list[Path] = []
    for category_dir in sorted(p for p in crawl_root.iterdir() if p.is_dir()):
        for product_dir in sorted(p for p in category_dir.iterdir() if p.is_dir()):
            if _detail_dir(product_dir) is not None:
                products.append(product_dir)
    return products


def _detail_dir(product_dir: Path) -> Path | None:
    """Return the detail-page directory, tolerating Unicode normalization variants.

    Args:
        product_dir: Product directory that may contain a Korean detail-page folder.

    Returns:
        Matching detail-page directory, or None when absent.
    """
    expected = unicodedata.normalize("NFC", DETAIL_DIR_NAME)
    for child in product_dir.iterdir():
        if child.is_dir() and unicodedata.normalize("NFC", child.name) == expected:
            return child
    return None


def _detail_images(product_dir: Path) -> list[Path]:
    """Return sorted detail-page image paths for one product."""
    detail = _detail_dir(product_dir)
    if detail is None:
        return []
    return sorted(p for p in detail.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES)


def _dry_run_source_counts(products: list[Path], max_images_per_product: int) -> dict[str, int]:
    """Return count-only source stats for a dry run without reading labels.

    Args:
        products: Eligible product directories after leakage exclusion.
        max_images_per_product: Per-product detail-page image cap.

    Returns:
        Count-only source stats used to verify the intended crawl scale.
    """
    products_with_detail_images = 0
    detail_images_at_cap = 0
    for product in products:
        capped_images = _detail_images(product)[:max_images_per_product]
        if not capped_images:
            continue
        products_with_detail_images += 1
        detail_images_at_cap += len(capped_images)
    return {
        "products_with_detail_images": products_with_detail_images,
        "detail_images_at_cap": detail_images_at_cap,
    }


def _tiles(image: Image.Image, tile_height: int, overlap: int) -> list[tuple[Image.Image, int]]:
    """Return ``(tile_image, y_offset)`` vertical tiles for a (possibly tall) image.

    Args:
        image: RGB source image.
        tile_height: Target tile height in pixels.
        overlap: Vertical overlap between consecutive tiles.

    Returns:
        Whole-image single tile when short; otherwise overlapping vertical tiles.
    """
    width, height = image.size
    if height <= int(tile_height * 1.5):
        return [(image, 0)]
    tiles: list[tuple[Image.Image, int]] = []
    step = max(1, tile_height - overlap)
    y = 0
    while y < height:
        bottom = min(height, y + tile_height)
        tiles.append((image.crop((0, y, width, bottom)), y))
        if bottom >= height:
            break
        y += step
    return tiles


def _jpeg_bytes(image: Image.Image) -> bytes:
    """Return JPEG-encoded bytes for an RGB image (normalizes jpg/png/webp)."""
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=90)
    return buffer.getvalue()


async def _clova_boxes(
    adapter: ClovaOCRAdapter, settings: Settings, image: Image.Image
) -> list[tuple[str, tuple[int, int, int, int]]]:
    """Return de-duplicated ``(text, box)`` fields for an image via tiled CLOVA OCR.

    Args:
        adapter: CLOVA OCR adapter.
        settings: Runtime settings.
        image: RGB source image.

    Returns:
        Field text paired with its axis-aligned box in original-image coordinates.
    """
    found: dict[tuple[str, int], tuple[str, tuple[int, int, int, int]]] = {}
    for tile, y_offset in _tiles(image, DEFAULT_TILE_HEIGHT, DEFAULT_TILE_OVERLAP):
        tile_bytes = _jpeg_bytes(tile)
        ocr_input = OCRImageInput(
            image_bytes=tile_bytes, mime_type="image/jpeg", width=tile.width, height=tile.height
        )
        response = await adapter._post(
            payload=_build_clova_payload(ocr_input), headers=_build_clova_headers(settings)
        )
        images = response.get("images") if isinstance(response, dict) else None
        if not images:
            continue
        for field in images[0].get("fields") or []:
            text = " ".join(str(field.get("inferText") or "").split())
            vertices = (field.get("boundingPoly") or {}).get("vertices") or []
            xs = [v.get("x") for v in vertices if isinstance(v.get("x"), int | float)]
            ys = [v.get("y") for v in vertices if isinstance(v.get("y"), int | float)]
            if not text or len(xs) < MIN_VERTICES or len(ys) < MIN_VERTICES:
                continue
            y0 = int(min(ys)) + y_offset
            box = (int(min(xs)), y0, int(max(xs)), int(max(ys)) + y_offset)
            found.setdefault((text, y0 // DEDUP_Y_BUCKET), (text, box))
    return list(found.values())


def _crop(image: Image.Image, box: tuple[int, int, int, int]) -> Image.Image | None:
    """Return a padded crop of ``box`` or None when degenerate."""
    width, height = image.size
    x0 = max(0, box[0] - CROP_PAD)
    y0 = max(0, box[1] - CROP_PAD)
    x1 = min(width, box[2] + CROP_PAD)
    y1 = min(height, box[3] + CROP_PAD)
    if x1 - x0 < MIN_CROP_SIDE or y1 - y0 < MIN_CROP_SIDE:
        return None
    return image.crop((x0, y0, x1, y1))


def _write_label_files(
    *,
    output_dir: Path,
    train_rows: list[tuple[str, str]],
    val_rows: list[tuple[str, str]],
    chars: set[str],
) -> None:
    """Write PaddleOCR rec label files (rec_gt + PaddleX copies) and the char dict."""
    rec_dir = output_dir / "rec"
    (rec_dir / "rec_gt_train.txt").write_text(
        "".join(f"{p}\t{t}\n" for p, t in train_rows), encoding="utf-8"
    )
    (rec_dir / "rec_gt_val.txt").write_text(
        "".join(f"{p}\t{t}\n" for p, t in val_rows), encoding="utf-8"
    )
    (output_dir / "train.txt").write_text(
        "".join(f"{p}\t{t}\n" for p, t in train_rows), encoding="utf-8"
    )
    (output_dir / "val.txt").write_text(
        "".join(f"{p}\t{t}\n" for p, t in val_rows), encoding="utf-8"
    )
    chars.discard(" ")
    (output_dir / "dict.txt").write_text("\n".join(sorted(chars)) + "\n", encoding="utf-8")


async def build(
    *,
    crawl_root: Path,
    splits_path: Path,
    output_dir: Path,
    max_images_per_product: int,
    max_products: int | None,
    limit: int | None,
    val_ratio: float,
    seed: int,
) -> dict[str, Any]:
    """Build the scaled real-photo rec dataset from detail-page images.

    Args:
        crawl_root: crawling-image root directory.
        splits_path: Benchmark split assignment JSONL (for leakage-safe exclusion).
        output_dir: Dataset root directory (must be under a ``datasets/`` tree).
        max_images_per_product: Cap on detail images per product (cost bound).
        max_products: Optional cap on eligible products processed.
        limit: Optional global cap on processed detail images.
        val_ratio: Fraction of eligible products held for validation.
        seed: RNG seed for the product-grouped train/val shuffle.

    Returns:
        Count-only summary.
    """
    excluded = _excluded_product_hashes(splits_path)
    products = _iter_products(crawl_root)
    eligible = [p for p in products if _product_hash(p, crawl_root) not in excluded]
    rng = random.Random(seed)
    rng.shuffle(eligible)
    if max_products is not None:
        eligible = eligible[:max_products]

    val_cut = int(len(eligible) * val_ratio)
    if len(eligible) > 1 and val_cut == 0:
        val_cut = 1
    val_products = {_product_hash(p, crawl_root) for p in eligible[:val_cut]}

    settings = get_settings()
    _validate_clova_settings(settings)
    adapter = ClovaOCRAdapter(settings)

    rec_dir = output_dir / "rec"
    (rec_dir / "images").mkdir(parents=True, exist_ok=True)
    train_rows: list[tuple[str, str]] = []
    val_rows: list[tuple[str, str]] = []
    chars: set[str] = set()
    stats = {"products": 0, "images": 0, "failed_images": 0, "crops": 0}
    processed_images = 0
    for product_dir in eligible:
        product_hash = _product_hash(product_dir, crawl_root)
        is_val = product_hash in val_products
        product_used = False
        for image_path in _detail_images(product_dir)[:max_images_per_product]:
            if limit is not None and processed_images >= limit:
                break
            processed_images += 1
            try:
                with Image.open(image_path) as raw:
                    rgb = raw.convert("RGB")
                    boxes = await _clova_boxes(adapter, settings, rgb)
                    for index, (text, box) in enumerate(boxes):
                        crop = _crop(rgb, box)
                        if crop is None:
                            continue
                        rel = (
                            f"rec/images/{product_hash[:16]}_{stats['images']:05d}_{index:03d}.png"
                        )
                        crop.save(output_dir / rel)
                        (val_rows if is_val else train_rows).append((rel, text))
                        chars.update(text)
                        stats["crops"] += 1
                stats["images"] += 1
                product_used = True
            except Exception:  # per-image isolation: count and continue (no raw error stored)
                stats["failed_images"] += 1
        if product_used:
            stats["products"] += 1
        if limit is not None and processed_images >= limit:
            break

    _write_label_files(output_dir=output_dir, train_rows=train_rows, val_rows=val_rows, chars=chars)
    return {
        "schema_version": "crawling-realphoto-paddleocr-rec-dataset-v1",
        "dataset_dir_name": output_dir.name,
        "source": "crawling_image_detail_pages_clova_teacher_boxes",
        "eligible_product_count": len(eligible),
        "excluded_holdout_test_product_count": len(excluded),
        "products_used": stats["products"],
        "detail_images_processed": stats["images"],
        "failed_image_count": stats["failed_images"],
        "crop_count": stats["crops"],
        "train_rows": len(train_rows),
        "val_rows": len(val_rows),
        "dict_size": len(chars),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--crawl-root", type=Path, required=True, help="crawling-image root.")
    parser.add_argument(
        "--splits", type=Path, required=True, help="Benchmark split assignment JSONL."
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-images-per-product", type=int, default=6)
    parser.add_argument("--max-products", type=int, default=None)
    parser.add_argument("--limit", type=int, default=None, help="Global cap on detail images.")
    parser.add_argument("--val-ratio", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.crawl_root.is_dir():
        raise SystemExit(f"ERROR: crawl-root is not a directory: {args.crawl_root}")
    if not args.splits.is_file():
        raise SystemExit(f"ERROR: splits file not found: {args.splits}")
    resolved_output = args.output_dir.expanduser().resolve()
    if "datasets" not in resolved_output.parts:
        raise SystemExit(
            "ERROR: --output-dir must live under a 'datasets/' directory so the teacher-text "
            "training labels stay in gitignored outputs/.../datasets/ (redaction policy)."
        )
    if not args.apply:
        excluded = _excluded_product_hashes(args.splits)
        eligible = [
            p
            for p in _iter_products(args.crawl_root)
            if _product_hash(p, args.crawl_root) not in excluded
        ]
        source_counts = _dry_run_source_counts(eligible, args.max_images_per_product)
        print(
            json.dumps(
                {
                    "apply_requested": False,
                    "eligible_product_count": len(eligible),
                    "excluded_holdout_test_product_count": len(excluded),
                    "max_images_per_product": args.max_images_per_product,
                    **source_counts,
                },
                ensure_ascii=False,
            )
        )
        return 0
    summary = asyncio.run(
        build(
            crawl_root=args.crawl_root,
            splits_path=args.splits,
            output_dir=args.output_dir,
            max_images_per_product=args.max_images_per_product,
            max_products=args.max_products,
            limit=args.limit,
            val_ratio=args.val_ratio,
            seed=args.seed,
        )
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
