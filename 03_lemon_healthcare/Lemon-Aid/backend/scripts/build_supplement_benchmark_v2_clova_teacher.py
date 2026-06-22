"""Stage 2 — CLOVA teacher pass over the benchmark v2 candidate pool (~297 images).

For each candidate (resolved from the v2 candidate manifest) this runs CLOVA OCR to
produce per-field ``(text, box)`` teacher labels, then bootstraps:
- a STRUCTURED GT draft (section -> field texts) via the section classifier, and
- a SECTION BBOX draft (8-class, vertical-gap clustered regions, YOLO-normalized)

for downstream human review (Stage 3, Label Studio) and the ROI detector trainset.

Privacy / cost:
- CLOVA is external; this is the operator-approved teacher exception used for the
  crawling corpus. Teacher TEXT + boxes are written ONLY under a gitignored
  ``datasets/`` tree. The committable summary carries counts only (no text/paths).
- Dry-run (no ``--apply``) resolves candidate images + verifies sha256 integrity and
  prints counts WITHOUT any CLOVA call (no cost). ``--apply`` performs CLOVA calls.

Runs in the py3.13 backend venv (PYTHONPATH=Nutrition-backend).
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import build_crawling_realphoto_rec_dataset as crawl
import build_crawling_yolo_section_dataset as yolo
from PIL import Image
from src.config import get_settings
from src.ocr.providers.clova import ClovaOCRAdapter, _validate_clova_settings

VERTICAL_GAP_FACTOR = 1.5


def _resolve(crawl_root: Path, manifest: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Resolve candidate records to image paths via product-hash + index, verify sha.

    Args:
        crawl_root: Crawl image root.
        manifest: v2 candidate-pool JSONL.

    Returns:
        ``(resolved, stats)`` where resolved items add a verified ``path``.
    """
    records = [
        json.loads(line)
        for line in manifest.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    by_hash: dict[str, list[dict[str, Any]]] = {}
    for r in records:
        by_hash.setdefault(r["product_dir_hash"], []).append(r)
    resolved: list[dict[str, Any]] = []
    sha_mismatch = 0
    for product_dir in crawl._iter_products(crawl_root):
        h = crawl._product_hash(product_dir, crawl_root)
        if h not in by_hash:
            continue
        images = crawl._detail_images(product_dir)
        for rec in by_hash[h]:
            idx = rec["image_index"]
            if idx >= len(images):
                continue
            path = images[idx]
            if hashlib.sha256(path.read_bytes()).hexdigest() != rec["image_sha256"]:
                sha_mismatch += 1
                continue
            resolved.append({**rec, "path": path})
    stats = {
        "manifest_records": len(records),
        "resolved": len(resolved),
        "sha_mismatch": sha_mismatch,
    }
    return resolved, stats


def _cluster_section_bboxes(
    boxes: list[tuple[str, tuple[int, int, int, int]]], width: int, height: int
) -> list[str]:
    """Cluster classified field boxes into per-section region bboxes (YOLO lines).

    Same-section boxes are grouped by vertical gaps so a section that appears once
    yields one region (avoids the degenerate whole-page union).

    Args:
        boxes: ``(text, (x0,y0,x1,y1))`` CLOVA fields.
        width: Image width.
        height: Image height.

    Returns:
        YOLO label lines ``"<class> cx cy w h"`` (normalized).
    """
    per_section: dict[str, list[tuple[int, int, int, int]]] = {}
    for text, box in boxes:
        section = yolo._classify_section(text)
        if section is not None:
            per_section.setdefault(section, []).append(box)
    lines: list[str] = []
    for section, sboxes in per_section.items():
        ordered = sorted(sboxes, key=lambda b: b[1])
        heights = [b[3] - b[1] for b in ordered] or [1]
        gap = (sum(heights) / len(heights)) * VERTICAL_GAP_FACTOR
        cluster: list[tuple[int, int, int, int]] = []
        clusters: list[list[tuple[int, int, int, int]]] = []
        prev_bottom: int | None = None
        for b in ordered:
            if prev_bottom is not None and b[1] - prev_bottom > gap:
                clusters.append(cluster)
                cluster = []
            cluster.append(b)
            prev_bottom = b[3]
        if cluster:
            clusters.append(cluster)
        for cl in clusters:
            x0 = min(b[0] for b in cl)
            y0 = min(b[1] for b in cl)
            x1 = max(b[2] for b in cl)
            y1 = max(b[3] for b in cl)
            line = yolo._yolo_line(section, (x0, y0, x1, y1), width, height)
            if line:
                lines.append(line)
    return lines


def _structured_draft(boxes: list[tuple[str, tuple[int, int, int, int]]]) -> dict[str, list[str]]:
    """Group classified field texts into a structured-GT draft (section -> texts)."""
    draft: dict[str, list[str]] = {}
    for text, _ in boxes:
        section = yolo._classify_section(text)
        if section is not None:
            draft.setdefault(section, []).append(text)
    return draft


async def _process(
    adapter: ClovaOCRAdapter, settings: Any, rec: dict[str, Any], out_dir: Path
) -> dict[str, Any]:
    """CLOVA-label one candidate and write teacher + drafts (gitignored)."""
    with Image.open(rec["path"]) as raw:
        rgb = raw.convert("RGB")
        width, height = rgb.size
        boxes = await crawl._clova_boxes(adapter, settings, rgb)
    section_lines = _cluster_section_bboxes(boxes, width, height)
    draft = _structured_draft(boxes)
    payload = {
        "candidate_id": rec["candidate_id"],
        "product_dir_hash": rec["product_dir_hash"],
        "image_index": rec["image_index"],
        "width": width,
        "height": height,
        "field_count": len(boxes),
        "fields": [{"text": t, "box": list(b)} for t, b in boxes],
        "section_bboxes_yolo": section_lines,
        "structured_gt_draft": draft,
        "v2_split": rec["v2_split"],
    }
    (out_dir / "teacher").mkdir(parents=True, exist_ok=True)
    (out_dir / "teacher" / f"{rec['candidate_id']}.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )
    return {
        "sections": list(draft.keys()),
        "section_box_count": len(section_lines),
        "field_count": len(boxes),
    }


async def build(
    *, crawl_root: Path, manifest: Path, out_dir: Path, limit: int | None, apply: bool
) -> None:
    """Resolve candidates and (with --apply) run the CLOVA teacher pass."""
    resolved, stats = _resolve(crawl_root, manifest)
    print(json.dumps({"phase": "resolve", **stats}, ensure_ascii=False))
    if not apply:
        print("DRY RUN: no CLOVA calls. Re-run with --apply to perform the paid teacher pass.")
        return
    settings = get_settings()
    _validate_clova_settings(settings)
    adapter = ClovaOCRAdapter(settings)
    section_cov: Counter[str] = Counter()
    done = {"labeled": 0, "failed": 0, "section_box_total": 0}
    for i, rec in enumerate(resolved):
        if limit is not None and i >= limit:
            break
        try:
            res = await _process(adapter, settings, rec, out_dir)
            done["labeled"] += 1
            done["section_box_total"] += res["section_box_count"]
            for s in res["sections"]:
                section_cov[s] += 1
        except Exception:  # per-image isolation
            done["failed"] += 1
        if (i + 1) % 25 == 0:
            print(
                f"  CLOVA progress: {i + 1}/{len(resolved)} labeled={done['labeled']} failed={done['failed']}",
                flush=True,
            )
    summary = {
        "schema_version": "supplement-benchmark-v2-clova-teacher-summary-v1",
        **stats,
        **done,
        "section_coverage": dict(section_cov),
        "candidates_with_ingredient": section_cov.get("ingredient_amounts", 0),
        "candidates_with_intake": section_cov.get("intake_method", 0),
    }
    (out_dir).mkdir(parents=True, exist_ok=True)
    (out_dir / "clova-teacher-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def main() -> None:
    """CLI entry point."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--crawl-root", required=True, type=Path)
    ap.add_argument("--manifest", required=True, type=Path)
    ap.add_argument("--output-dir", required=True, type=Path)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--apply", action="store_true", help="Perform the paid CLOVA teacher pass.")
    a = ap.parse_args()
    asyncio.run(
        build(
            crawl_root=a.crawl_root,
            manifest=a.manifest,
            out_dir=a.output_dir,
            limit=a.limit,
            apply=a.apply,
        )
    )


if __name__ == "__main__":
    main()
