"""Build an ROI-first ORACLE eval bundle from the GT review bundle (holdout).

To empirically test whether ROI scoping breaks the char-level precision scope-cap
(see 2026-06-08-text-f1-improvement-design.md), this crops each held-out image to
its ground-truth section regions using CLOVA teacher boxes as an ORACLE detector,
then writes a mirrored bundle that the EXISTING paddleocr_clova_eval can score
directly (no new scorer). Comparing full-image vs this cropped bundle isolates the
precision recovered by perfect ROI scoping = the achievable ceiling before training
a real section detector.

CLOVA is external (operator-approved teacher exception). Cropped images derive from
teacher boxes -> written ONLY under a gitignored datasets/ tree. Dry-run (no
--apply) lists the held-out fixtures without any CLOVA call. Runs in the py3.13
backend venv (PYTHONPATH=Nutrition-backend).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
from pathlib import Path
from typing import Any

import build_crawling_realphoto_rec_dataset as crawl
import build_crawling_yolo_section_dataset as yolo
from PIL import Image
from src.config import get_settings
from src.ocr.providers.clova import ClovaOCRAdapter, _validate_clova_settings

CROP_PAD = 10
# GT `expected` dict uses different section keys than the detector CLASS_NAMES.
GT_TO_SECTION = {
    "ingredients": "ingredient_amounts",
    "intake_method": "intake_method",
    "precautions": "precautions",
    "allergen_warnings": "allergen_warning",
    "functional_claims": "functional_claims",
    "product_name": "product_identity",
}


def _holdout_fixtures(splits: Path, eval_split: str) -> dict[str, dict[str, Any]]:
    """Return ``fixture_id -> split row`` for the requested eval split."""
    out: dict[str, dict[str, Any]] = {}
    for line in splits.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("split") == eval_split and r.get("fixture_id"):
            out[r["fixture_id"]] = r
    return out


def _image_for(bundle_dir: Path, fixture_id: str) -> Path | None:
    """Find the bundle image file for a fixture id."""
    matches = sorted((bundle_dir / "images").glob(f"{fixture_id}.*"))
    return matches[0] if matches else None


async def build(
    *,
    bundle_dir: Path,
    splits: Path,
    eval_split: str,
    out_bundle: Path,
    apply: bool,
    limit: int | None,
) -> None:
    """Crop held-out images to GT-section ROI (CLOVA oracle) into a mirrored bundle."""
    holdout = _holdout_fixtures(splits, eval_split)
    todo_rows = [
        json.loads(line)
        for line in (bundle_dir / "ground-truth.todo.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    rows = [
        r
        for r in todo_rows
        if r.get("fixture_id") in holdout
        and r.get("ready_for_benchmark_after_review") is True
        and isinstance(r.get("expected"), dict)
    ]
    print(
        json.dumps(
            {
                "phase": "resolve",
                "eval_split": eval_split,
                "holdout_fixtures": len(holdout),
                "ready_rows": len(rows),
            },
            ensure_ascii=False,
        )
    )
    if not apply:
        print("DRY RUN: no CLOVA calls. Re-run with --apply.")
        return

    settings = get_settings()
    _validate_clova_settings(settings)
    adapter = ClovaOCRAdapter(settings)
    (out_bundle / "images").mkdir(parents=True, exist_ok=True)
    stats = {"cropped": 0, "fallback_full": 0, "failed": 0, "crop_area_ratio_sum": 0.0}
    kept_rows: list[dict[str, Any]] = []
    for i, row in enumerate(rows):
        if limit is not None and i >= limit:
            break
        fid = row["fixture_id"]
        src = _image_for(bundle_dir, fid)
        if src is None:
            stats["failed"] += 1
            continue
        gt_sections = {
            GT_TO_SECTION[k] for k, v in row["expected"].items() if k in GT_TO_SECTION and v
        } or {"ingredient_amounts"}
        try:
            with Image.open(src) as raw:
                rgb = raw.convert("RGB")
                w, h = rgb.size
                boxes = await crawl._clova_boxes(adapter, settings, rgb)
                keep = [b for t, b in boxes if yolo._classify_section(t) in gt_sections]
                dst = out_bundle / "images" / src.name
                if keep:
                    x0 = max(0, min(b[0] for b in keep) - CROP_PAD)
                    y0 = max(0, min(b[1] for b in keep) - CROP_PAD)
                    x1 = min(w, max(b[2] for b in keep) + CROP_PAD)
                    y1 = min(h, max(b[3] for b in keep) + CROP_PAD)
                    rgb.crop((x0, y0, x1, y1)).save(dst, quality=92)
                    stats["cropped"] += 1
                    stats["crop_area_ratio_sum"] += ((x1 - x0) * (y1 - y0)) / (w * h)
                else:
                    rgb.save(dst, quality=92)  # fallback: no GT-section boxes found
                    stats["fallback_full"] += 1
            kept_rows.append(row)
        except Exception:
            stats["failed"] += 1
    with (out_bundle / "ground-truth.todo.jsonl").open("w", encoding="utf-8") as fh:
        for r in kept_rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    n = stats["cropped"] + stats["fallback_full"]
    summary = {
        "schema_version": "roi-first-oracle-bundle-summary-v1",
        "eval_split": eval_split,
        "fixtures": n,
        "cropped": stats["cropped"],
        "fallback_full_image": stats["fallback_full"],
        "failed": stats["failed"],
        "mean_crop_area_ratio": (
            round(stats["crop_area_ratio_sum"] / stats["cropped"], 4) if stats["cropped"] else None
        ),
    }
    (out_bundle / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def main() -> None:
    """CLI entry point."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bundle-dir", required=True, type=Path)
    ap.add_argument("--splits", required=True, type=Path)
    ap.add_argument("--eval-split", default="holdout")
    ap.add_argument("--output-bundle", required=True, type=Path)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    if a.apply and a.output_bundle.exists():
        shutil.rmtree(a.output_bundle)
    asyncio.run(
        build(
            bundle_dir=a.bundle_dir,
            splits=a.splits,
            eval_split=a.eval_split,
            out_bundle=a.output_bundle,
            apply=a.apply,
            limit=a.limit,
        )
    )


if __name__ == "__main__":
    main()
