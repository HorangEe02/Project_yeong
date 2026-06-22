"""Discover intake_method (섭취방법) panels missed by the v2 ingredient-first selection.

The v2 candidate pool selected ingredient-bearing images, so intake_method coverage
was ~0 (the proxy's loose "1일" matched nutrition-facts daily-value rows, not real
intake panels). This re-scans each product's NON-selected detail images with a STRICT
intake classifier and emits an intake candidate manifest (same schema as the candidate
pool) so the existing CLOVA teacher pass can label them.

Cost control: only images the proxy already flagged as intake (loose) are re-OCR'd
locally (free); CLOVA runs later only on the strict hits. No external calls here.

Runs in the py3.12 .venv-paddle (PaddleOCR). Output manifest -> gitignored reconciled/.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import build_supplement_benchmark_v2_candidate_pool as v2
import paddleocr_clova_eval as pe

# Strict intake markers (exclude bare "1일"/기준치 which pollute via facts tables).
STRICT_INTAKE = (
    "섭취방법",
    "복용방법",
    "섭취 방법",
    "복용 방법",
    "드십시오",
    "드세요",
    "드시기",
    "섭취하",
    "복용하",
    "취침",
    "식후",
    "식전",
    "공복",
    "물과 함께",
    "씹어",
)
STRICT_INTAKE_RE = re.compile(
    r"(1일\s*\d+\s*회|1회\s*\d+\s*(?:정|캡슐|포|스푼|ml|㎖)|하루\s*\d+\s*(?:회|정|캡슐|포))"
)


def _strict_intake_score(text: str) -> int:
    """Return a strict intake-panel score (keyword hits + dosing patterns)."""
    return sum(k in text for k in STRICT_INTAKE) + len(STRICT_INTAKE_RE.findall(text))


def build(
    *, crawl_root: Path, cache_path: Path, selected_manifest: Path, output: Path, max_rescan: int
) -> None:
    """Re-scan non-selected intake-flagged images and emit an intake candidate manifest."""
    cache = json.loads(cache_path.read_text(encoding="utf-8"))
    selected = [
        json.loads(line)
        for line in selected_manifest.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    selected_idx: dict[str, set[int]] = {}
    split_by_product: dict[str, str] = {}
    for r in selected:
        selected_idx.setdefault(r["product_dir_hash"], set()).add(r["image_index"])
        split_by_product[r["product_dir_hash"]] = r["v2_split"]

    # resolve product hash -> product dir (walk once)
    dir_by_hash = {v2._product_hash(p, crawl_root): p for p in v2._iter_products(crawl_root)}
    ocr = pe._build_ocr(
        det_model="PP-OCRv5_mobile_det",
        rec_model="korean_PP-OCRv5_mobile_rec",
        max_side=2048,
        det_box_thresh=0.15,
        det_thresh=0.1,
        det_unclip_ratio=2.0,
    )

    records: list[dict[str, Any]] = []
    scanned = 0
    for phash, rec in cache.items():
        product_dir = dir_by_hash.get(phash)
        if product_dir is None:
            continue
        images = v2._detail_images(product_dir)
        sel = selected_idx.get(phash, set())
        # narrow: non-selected images the proxy flagged intake (loose)
        cand = [
            im
            for im in rec.get("images", [])
            if im["signals"].get("intake") and im["index"] not in sel
        ]
        cand = cand[:max_rescan]
        best: tuple[int, dict[str, Any]] | None = None
        for im in cand:
            idx = im["index"]
            if idx >= len(images):
                continue
            scanned += 1
            try:
                text = pe._predict_text(ocr, images[idx])
            except Exception:
                continue
            score = _strict_intake_score(text)
            if score > 0 and (best is None or score > best[0]):
                best = (score, im)
        if best is None:
            continue
        im = best[1]
        cid = hashlib.sha256(f"{phash}#{im['index']}#intake".encode()).hexdigest()[:20]
        records.append(
            {
                "schema_version": "supplement-ocr-benchmark-v2-candidate-v1",
                "candidate_id": cid,
                "product_dir_hash": phash,
                "category": rec.get("category"),
                "image_index": im["index"],
                "image_sha256": im["sha256"],
                "source_ref": f"crawling-image:{phash[:32]}#{im['index']}",
                "image_height": im["height"],
                "image_aspect": im["aspect"],
                "signals": im["signals"],
                "hardness": {
                    "long_page": im["height"] >= v2.LONG_PAGE_MIN_PX,
                    "low_signal": False,
                    "fragmented_product": True,
                    "selection_role": "intake",
                },
                "suggested_required_sections": ["intake_method"],
                "v2_split": split_by_product.get(phash, v2._split_bucket(phash)),
                "pool_role": "detector_roi_annotation",
                "annotation": {
                    "bbox": dict.fromkeys(("intake_method", "ingredient_amounts")),
                    "structured_gt": {"intake_method": []},
                    "status": "pending",
                },
                "intake_strict_score": best[0],
            }
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(
        json.dumps(
            {
                "images_rescanned": scanned,
                "intake_panels_found": len(records),
                "products_with_intake": len({r["product_dir_hash"] for r in records}),
            },
            ensure_ascii=False,
        )
    )


def main() -> None:
    """CLI entry point."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--crawl-root", required=True, type=Path)
    ap.add_argument("--cache", required=True, type=Path)
    ap.add_argument("--selected-manifest", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--max-rescan-per-product", type=int, default=6)
    a = ap.parse_args()
    build(
        crawl_root=a.crawl_root,
        cache_path=a.cache,
        selected_manifest=a.selected_manifest,
        output=a.output,
        max_rescan=a.max_rescan_per_product,
    )


if __name__ == "__main__":
    main()
