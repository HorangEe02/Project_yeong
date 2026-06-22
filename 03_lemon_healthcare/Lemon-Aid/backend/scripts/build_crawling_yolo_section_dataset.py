"""Weak-supervision YOLO26 section-detection dataset from crawling detail pages.

Gap #1 of the pipeline-evaluation: the YOLO section detector has no trained weights
and no bbox annotations (205 unfilled). Manual section-region annotation is the
blocker. This tool removes it with CLOVA-box weak supervision: for each crawling
``상세페이지`` image it runs CLOVA OCR (operator-approved teacher), classifies each
detected text field into a supplement section by Korean keyword/pattern heuristics,
unions the boxes of each section into one region bbox, and writes Ultralytics YOLO
detection labels (``class_id cx cy w h`` normalized). The result is a
contract-valid dataset (``validate_supplement_section_yolo_dataset``) ready for
YOLO26 training on a GPU (see RUN_ON_GPU). Labels are weak (heuristic) — intended
to bootstrap/pretrain; human review still improves quality.

Safety: detail pages only (``리뷰`` skipped); fail-closed leakage exclusion of
holdout/test products (same ``product_dir_hash`` scheme as the benchmark); cost
caps; per-image isolation; seeded product-grouped train/val split; output confined
to a gitignored ``datasets/`` tree (teacher-derived labels).

Runs in the py3.13 backend venv (``PYTHONPATH=Nutrition-backend``). External CLOVA
calls occur only with ``--apply``.

References:
    https://docs.ultralytics.com/modes/train/
    https://api.ncloud-docs.com/docs/en/ai-application-service-ocr
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

from PIL import Image
from src.config import get_settings
from src.ocr.providers.clova import ClovaOCRAdapter, _validate_clova_settings

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts import build_crawling_realphoto_rec_dataset as crawl  # noqa: E402

# Canonical class ordering (must match learning.retraining.SUPPLEMENT_SECTION_CLASS_NAMES).
CLASS_NAMES = (
    "product_identity",
    "supplement_facts",
    "ingredient_amounts",
    "precautions",
    "allergen_warning",
    "intake_method",
    "other_ingredients",
    "functional_claims",
)
CLASS_ID = {name: index for index, name in enumerate(CLASS_NAMES)}
_AMOUNT_RE = re.compile(
    r"\d\s*(mg|g|mcg|㎍|µg|iu|억|cfu|kcal|kj|%|밀리그램|마이크로그램)", re.IGNORECASE
)


def _norm(text: str) -> str:
    """Return NFKC text for keyword matching."""
    return unicodedata.normalize("NFKC", text)


def _classify_section(text: str) -> str | None:
    """Classify one CLOVA field's text into a supplement section, or None.

    Order matters: more specific sections are checked first so an allergen or
    precaution line is not mis-bucketed as intake/ingredient.

    Args:
        text: Field text.

    Returns:
        A section class name, or None when no rule matches.
    """
    t = _norm(text)

    def has(*keywords: str) -> bool:
        return any(k in t for k in keywords)

    if has("알레르기", "알러지") or ("함유" in t and "알레르" in t):
        section: str | None = "allergen_warning"
    elif has("주의", "경고", "금지", "이상반응", "섭취를 중단", "의사와 상담", "전문가와 상담"):
        section = "precautions"
    elif has("섭취", "복용", "1일", "식후", "식전", "물과 함께") and has(
        "회", "정", "캡슐", "포", "스푼", "ml", "정도", "알"
    ):
        section = "intake_method"
    elif _AMOUNT_RE.search(t):
        section = "ingredient_amounts"
    elif has("영양정보", "영양성분", "1일 영양성분", "총 내용량", "열량", "기준치"):
        section = "supplement_facts"
    elif has("기능성", "도움을 줄 수", "도움을 줌"):
        section = "functional_claims"
    else:
        section = None
    return section


def _yolo_line(section: str, box: tuple[int, int, int, int], width: int, height: int) -> str | None:
    """Return a normalized Ultralytics label line ``class cx cy w h`` or None."""
    x0, y0, x1, y1 = box
    if width <= 0 or height <= 0 or x1 <= x0 or y1 <= y0:
        return None
    cx = ((x0 + x1) / 2) / width
    cy = ((y0 + y1) / 2) / height
    w = (x1 - x0) / width
    h = (y1 - y0) / height
    clamp = lambda v: max(0.0, min(1.0, v))  # noqa: E731
    return f"{CLASS_ID[section]} {clamp(cx):.6f} {clamp(cy):.6f} {clamp(w):.6f} {clamp(h):.6f}"


def _write_dataset_yaml(output_dir: Path) -> None:
    """Write an Ultralytics dataset.yaml with the canonical section class names."""
    names = "\n".join(f"  {i}: {name}" for i, name in enumerate(CLASS_NAMES))
    # Absolute root so the validator + Ultralytics resolve images/labels locally;
    # the file lives under a gitignored datasets/ tree (adjust 'path' on the GPU box).
    (output_dir / "dataset.yaml").write_text(
        f"path: {output_dir.resolve()}\ntrain: images/train\nval: images/val\nnames:\n{names}\n",
        encoding="utf-8",
    )


async def _process_image(
    *,
    adapter: ClovaOCRAdapter,
    settings: Any,
    image_path: Path,
    output_dir: Path,
    split: str,
    stem: str,
) -> tuple[str, list[str]]:
    """Label one detail image via CLOVA weak supervision and write YOLO files.

    Args:
        adapter: CLOVA OCR adapter.
        settings: Runtime settings.
        image_path: Detail-page image path.
        output_dir: Dataset root.
        split: 'train' or 'val'.
        stem: Output file stem.

    Returns:
        ``(status, sections)`` where status is 'labeled'/'no_section'/'failed'.
    """
    try:
        with Image.open(image_path) as raw:
            rgb = raw.convert("RGB")
            width, height = rgb.size
            boxes = await crawl._clova_boxes(adapter, settings, rgb)
            lines: list[str] = []
            sections: list[str] = []
            for text, box in boxes:
                section = _classify_section(text)
                if section is None:
                    continue
                line = _yolo_line(section, box, width, height)
                if line:
                    lines.append(line)
                    sections.append(section)
            if not lines:
                return ("no_section", [])
            rgb.save(output_dir / "images" / split / f"{stem}.jpg", format="JPEG", quality=90)
            (output_dir / "labels" / split / f"{stem}.txt").write_text(
                "\n".join(lines) + "\n", encoding="utf-8"
            )
            return ("labeled", sections)
    except Exception:  # per-image isolation: count and continue
        return ("failed", [])


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
    """Build the weak-supervision YOLO section-detection dataset.

    Args:
        crawl_root: crawling-image root directory.
        splits_path: Benchmark split assignment JSONL (leakage-safe exclusion).
        output_dir: Dataset root directory (must be under a ``datasets/`` tree).
        max_images_per_product: Cap on detail images per product (cost bound).
        max_products: Optional cap on eligible products.
        limit: Optional global cap on processed detail images.
        val_ratio: Fraction of eligible products held for validation.
        seed: RNG seed for the product-grouped split.

    Returns:
        Count-only summary.
    """
    excluded = crawl._excluded_product_hashes(splits_path)
    products = [
        p
        for p in crawl._iter_products(crawl_root)
        if crawl._product_hash(p, crawl_root) not in excluded
    ]
    rng = random.Random(seed)
    rng.shuffle(products)
    if max_products is not None:
        products = products[:max_products]
    val_cut = int(len(products) * val_ratio)
    if len(products) > 1 and val_cut == 0:
        val_cut = 1
    val_hashes = {crawl._product_hash(p, crawl_root) for p in products[:val_cut]}

    settings = get_settings()
    _validate_clova_settings(settings)
    adapter = ClovaOCRAdapter(settings)
    for split in ("train", "val"):
        (output_dir / "images" / split).mkdir(parents=True, exist_ok=True)
        (output_dir / "labels" / split).mkdir(parents=True, exist_ok=True)

    section_counts: dict[str, int] = dict.fromkeys(CLASS_NAMES, 0)
    stats = {
        "products": 0,
        "images_labeled": 0,
        "images_no_section": 0,
        "failed_images": 0,
        "boxes": 0,
    }
    processed = 0
    for product_dir in products:
        product_hash = crawl._product_hash(product_dir, crawl_root)
        split = "val" if product_hash in val_hashes else "train"
        used = False
        for image_path in crawl._detail_images(product_dir)[:max_images_per_product]:
            if limit is not None and processed >= limit:
                break
            processed += 1
            stem = f"{product_hash[:16]}_{stats['images_labeled']:05d}"
            status, sections = await _process_image(
                adapter=adapter,
                settings=settings,
                image_path=image_path,
                output_dir=output_dir,
                split=split,
                stem=stem,
            )
            if status == "labeled":
                stats["images_labeled"] += 1
                stats["boxes"] += len(sections)
                for section in sections:
                    section_counts[section] += 1
                used = True
            elif status == "no_section":
                stats["images_no_section"] += 1
            else:
                stats["failed_images"] += 1
        if used:
            stats["products"] += 1
        if limit is not None and processed >= limit:
            break

    _write_dataset_yaml(output_dir)
    return {
        "schema_version": "crawling-yolo-section-detect-dataset-v1",
        "dataset_dir_name": output_dir.name,
        "source": "crawling_image_detail_pages_clova_weak_supervision",
        "class_names": list(CLASS_NAMES),
        "eligible_product_count": len(products),
        "excluded_holdout_test_product_count": len(excluded),
        "products_used": stats["products"],
        "images_labeled": stats["images_labeled"],
        "images_no_section": stats["images_no_section"],
        "failed_image_count": stats["failed_images"],
        "box_count": stats["boxes"],
        "per_section_image_counts": section_counts,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--crawl-root", type=Path, required=True)
    parser.add_argument("--splits", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-images-per-product", type=int, default=3)
    parser.add_argument("--max-products", type=int, default=None)
    parser.add_argument("--limit", type=int, default=None)
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
    resolved = args.output_dir.expanduser().resolve()
    if "datasets" not in resolved.parts:
        raise SystemExit(
            "ERROR: --output-dir must live under a 'datasets/' directory (teacher-derived labels)."
        )
    if not args.apply:
        excluded = crawl._excluded_product_hashes(args.splits)
        eligible = [
            p
            for p in crawl._iter_products(args.crawl_root)
            if crawl._product_hash(p, args.crawl_root) not in excluded
        ]
        print(json.dumps({"apply_requested": False, "eligible_product_count": len(eligible)}))
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
