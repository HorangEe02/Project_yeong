"""Build the OCR benchmark v2 (500) failure-targeted candidate pool.

Strategy (per operator design):
- Keep the existing 203 fixtures FROZEN as the v1 regression holdout.
- Add ~297 NEW fixtures drawn from crawling products NOT in the frozen set, so v2
  totals ~500. The eligible-new pool (~274 products) is close to the target, so the
  lever is NOT product selection but (a) picking the ground-truth-bearing detail
  image per product and (b) oversampling hard cases (ingredient/intake on separate
  pages, very long detail pages, low-signal layouts).
- A LOCAL PaddleOCR proxy (no CLOVA, no external calls, no cost) scans each eligible
  product's detail images to locate ingredient_amounts / intake_method panels and to
  flag hardness. Only derived SIGNALS (booleans + char counts) are stored, never raw
  OCR text or absolute/product-name paths (redaction-safe).
- Product-level, leakage-safe split for the new fixtures (deterministic product hash
  group), disjoint from the frozen 203 products.

Outputs (all under a gitignored reconciled/ tree):
- candidate manifest (redacted: hashes/flags/counts + empty bbox/structured-GT slots),
- an operator-only resolution map (image_sha256 -> relative path) for materialization,
- a markdown v2-structure plan.

Runs in the py3.12 .venv-paddle (PaddleOCR). Reuses paddleocr_clova_eval._build_ocr /
_predict_text so the proxy matches the evaluation pipeline.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paddleocr_clova_eval as pe

DETAIL_DIR_NAME = "상세페이지"
IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".webp")
LONG_PAGE_MIN_PX = 3000
SPLIT_TRAIN_MAX_BUCKET = 70
SPLIT_VAL_MAX_BUCKET = 85

AMOUNT_RE = re.compile(
    r"\d+(?:[.,]\d+)?\s*(?:mg|g|mcg|㎍|㎎|iu|억|cfu|kcal|%|밀리그램|마이크로그램)", re.IGNORECASE
)
INGREDIENT_KW = ("성분", "원료", "함량", "영양성분", "영양정보", "원재료")
INTAKE_KW = ("섭취", "복용", "섭취방법", "복용방법", "1일", "일일", "하루", "1회", "회분")
FACTS_KW = ("영양성분", "영양정보", "기준치", "1일영양성분")
PRECAUTION_KW = ("주의", "주의사항", "경고", "보관", "냉장")
ALLERGEN_KW = ("알레르기", "알러지", "함유", "대두", "우유", "땅콩")


def _product_hash(product_dir: Path, crawl_root: Path) -> str:
    """Return the benchmark-compatible product hash (sha256 of the relative path)."""
    rel = product_dir.resolve().relative_to(crawl_root.resolve())
    return hashlib.sha256(rel.as_posix().encode("utf-8")).hexdigest()


def _detail_dir(product_dir: Path) -> Path | None:
    """Return the detail-page subfolder, tolerating Unicode normalization variants."""
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


def _iter_products(crawl_root: Path) -> list[Path]:
    """Return product directories that contain a detail-page subfolder."""
    products: list[Path] = []
    for category_dir in sorted(p for p in crawl_root.iterdir() if p.is_dir()):
        for product_dir in sorted(p for p in category_dir.iterdir() if p.is_dir()):
            if _detail_dir(product_dir) is not None:
                products.append(product_dir)
    return products


def _scan_signals(text: str) -> dict[str, Any]:
    """Derive section-presence signals from recognized text (no raw text retained)."""
    has_amount = bool(AMOUNT_RE.search(text))
    return {
        "ingredient": has_amount or any(k in text for k in INGREDIENT_KW),
        "intake": any(k in text for k in INTAKE_KW),
        "facts": any(k in text for k in FACTS_KW),
        "precautions": any(k in text for k in PRECAUTION_KW),
        "allergen": any(k in text for k in ALLERGEN_KW),
        "char_count": len(text.replace(" ", "")),
    }


def _image_meta(path: Path) -> tuple[int, float, str]:
    """Return (height, aspect, sha256-hex) for an image without retaining pixels."""
    with Image.open(path) as im:
        w, h = im.size
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return h, round(h / max(w, 1), 2), digest


def _ocr_proxy(
    *,
    crawl_root: Path,
    eligible_hashes: set[str],
    max_images: int,
    cache_path: Path,
    limit: int | None,
) -> dict[str, Any]:
    """Run the local OCR proxy over eligible products, caching per-product signals.

    Args:
        crawl_root: Crawl image root.
        eligible_hashes: Product hashes eligible for the new pool.
        max_images: Per-product detail-image cap for the proxy scan.
        cache_path: Resumable cache file (per product hash).
        limit: Optional cap on products processed this run (testing).

    Returns:
        Mapping ``product_hash -> {category, images:[{index, height, aspect, sha, signals}]}``.
    """
    cache: dict[str, Any] = {}
    if cache_path.exists():
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
    ocr = pe._build_ocr(
        det_model="PP-OCRv5_mobile_det",
        rec_model="korean_PP-OCRv5_mobile_rec",
        max_side=2048,
        det_box_thresh=0.15,
        det_thresh=0.1,
        det_unclip_ratio=2.0,
    )
    processed = 0
    for product_dir in _iter_products(crawl_root):
        h = _product_hash(product_dir, crawl_root)
        if h not in eligible_hashes or h in cache:
            continue
        if limit is not None and processed >= limit:
            break
        images = []
        for idx, ip in enumerate(_detail_images(product_dir)[:max_images]):
            try:
                height, aspect, sha = _image_meta(ip)
                text = pe._predict_text(ocr, ip)
                images.append(
                    {
                        "index": idx,
                        "height": height,
                        "aspect": aspect,
                        "sha256": sha,
                        "signals": _scan_signals(text),
                    }
                )
            except Exception:  # per-image isolation
                continue
        cache[h] = {"category": product_dir.parent.name, "images": images}
        processed += 1
        if processed % 10 == 0:
            cache_path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
            print(f"  proxy progress: {processed} products", flush=True)
    cache_path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    print(f"OCR proxy done: {len(cache)} products cached", flush=True)
    return cache


def _relevance(sig: dict[str, Any]) -> int:
    """Score how likely an image carries the GT-relevant sections."""
    return (
        2 * int(sig["ingredient"])
        + 2 * int(sig["intake"])
        + int(sig["facts"])
        + int(sig["precautions"])
        + int(sig["allergen"])
    )


def _select(cache: dict[str, Any], target_new: int) -> list[dict[str, Any]]:
    """Select ~target_new image-level candidates, failure-targeted.

    One primary pick per product (most GT-relevant image); for products whose
    ingredient and intake signals fall on DIFFERENT images, add a secondary pick
    (the separated-page hard case) until the target is met.

    Args:
        cache: OCR-proxy output.
        target_new: Desired number of new candidate fixtures.

    Returns:
        List of selected candidate dicts (pre-split, pre-redaction-record).
    """
    primaries: list[dict[str, Any]] = []
    secondaries: list[dict[str, Any]] = []
    for h, rec in cache.items():
        imgs = rec.get("images") or []
        if not imgs:
            continue
        ranked = sorted(
            imgs,
            key=lambda im: (_relevance(im["signals"]), im["signals"]["char_count"], im["height"]),
            reverse=True,
        )
        best = ranked[0]
        any_ing = any(im["signals"]["ingredient"] for im in imgs)
        any_int = any(im["signals"]["intake"] for im in imgs)
        ing_img = next((im for im in imgs if im["signals"]["ingredient"]), None)
        int_img = next((im for im in imgs if im["signals"]["intake"]), None)
        fragmented = bool(ing_img and int_img and ing_img["index"] != int_img["index"])
        low_signal = not (any_ing or any_int)
        primaries.append(
            {
                "product_hash": h,
                "category": rec["category"],
                "image": best,
                "fragmented": fragmented,
                "low_signal": low_signal,
                "role": "primary",
            }
        )
        if fragmented:
            other = int_img if best["index"] == ing_img["index"] else ing_img
            secondaries.append(
                {
                    "product_hash": h,
                    "category": rec["category"],
                    "image": other,
                    "fragmented": True,
                    "low_signal": False,
                    "role": "secondary",
                }
            )
    # hardest secondaries first (separated-page cases, then long pages)
    secondaries.sort(
        key=lambda c: (c["image"]["height"], c["image"]["signals"]["char_count"]), reverse=True
    )
    need = max(0, target_new - len(primaries))
    return primaries + secondaries[:need]


def _split_bucket(product_hash: str) -> str:
    """Deterministic product-level split for the new pool (70/15/15)."""
    bucket = int(product_hash[:8], 16) % 100
    if bucket < SPLIT_TRAIN_MAX_BUCKET:
        return "train"
    return "val" if bucket < SPLIT_VAL_MAX_BUCKET else "test"


def _record(cand: dict[str, Any]) -> dict[str, Any]:
    """Build a redacted candidate manifest record (no raw text / no literal paths)."""
    img = cand["image"]
    sig = img["signals"]
    cid = hashlib.sha256(f"{cand['product_hash']}#{img['index']}".encode()).hexdigest()[:20]
    required = ["ingredient_amounts", "intake_method"]
    if sig["facts"]:
        required.append("supplement_facts")
    suggested = list(required)
    return {
        "schema_version": "supplement-ocr-benchmark-v2-candidate-v1",
        "candidate_id": cid,
        "product_dir_hash": cand["product_hash"],
        "category": cand["category"],
        "image_index": img["index"],
        "image_sha256": img["sha256"],
        "source_ref": f"crawling-image:{cand['product_hash'][:32]}#{img['index']}",
        "image_height": img["height"],
        "image_aspect": img["aspect"],
        "signals": sig,
        "hardness": {
            "long_page": img["height"] >= LONG_PAGE_MIN_PX,
            "low_signal": cand["low_signal"],
            "fragmented_product": cand["fragmented"],
            "selection_role": cand["role"],
        },
        "suggested_required_sections": suggested,
        "v2_split": _split_bucket(cand["product_hash"]),
        "pool_role": "detector_roi_annotation",
        "annotation": {
            "bbox": dict.fromkeys(
                ("ingredient_amounts", "intake_method", "supplement_facts", "product_identity")
            ),
            "structured_gt": {
                "ingredient_amounts": [],
                "intake_method": [],
                "precautions": [],
                "allergen_warnings": [],
            },
            "status": "pending",
        },
    }


def build(
    *,
    crawl_root: Path,
    splits: Path,
    inventory: Path,
    cache_path: Path,
    manifest: Path,
    resolution_map: Path,
    plan: Path,
    target_new: int,
    max_images: int,
    limit: int | None,
) -> None:
    """Run the proxy, select candidates, split, and emit manifest + map + plan."""
    inv = json.loads(inventory.read_text(encoding="utf-8"))
    eligible_hashes = {x["hash"] for x in inv["eligible"]}
    frozen_rows = [
        json.loads(line) for line in splits.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    frozen_by_split: dict[str, int] = {}
    for r in frozen_rows:
        frozen_by_split[r["split"]] = frozen_by_split.get(r["split"], 0) + 1

    cache = _ocr_proxy(
        crawl_root=crawl_root,
        eligible_hashes=eligible_hashes,
        max_images=max_images,
        cache_path=cache_path,
        limit=limit,
    )
    selected = _select(cache, target_new)
    records = [_record(c) for c in selected]

    manifest.parent.mkdir(parents=True, exist_ok=True)
    with manifest.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    # operator-only resolution map (sha256 -> product hash + index); gitignored tree
    res = {
        rec["image_sha256"]: {
            "product_dir_hash": rec["product_dir_hash"],
            "image_index": rec["image_index"],
        }
        for rec in records
    }
    resolution_map.write_text(json.dumps(res, ensure_ascii=False, indent=0), encoding="utf-8")

    by_split = Counter(r["v2_split"] for r in records)
    hard = Counter(
        k for r in records for k, v in r["hardness"].items() if v is True and k != "selection_role"
    )
    cats = Counter(r["category"] for r in records)
    stats = {
        "frozen_v1_fixtures": len(frozen_rows),
        "frozen_v1_by_split": frozen_by_split,
        "new_candidates": len(records),
        "v2_total": len(frozen_rows) + len(records),
        "new_by_split": dict(by_split),
        "hardness_counts": dict(hard),
        "distinct_new_products": len({r["product_dir_hash"] for r in records}),
        "category_coverage": len(cats),
    }
    plan.write_text(_plan_md(stats, cats), encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False, indent=2))


def _plan_md(stats: dict[str, Any], cats: Any) -> str:
    """Render the v2-structure markdown plan."""
    top = "\n".join(f"| {c} | {n} |" for c, n in cats.most_common(15))
    return f"""# OCR benchmark v2 (500) — candidate pool 구조

생성: build_supplement_benchmark_v2_candidate_pool.py (로컬 OCR 프록시, CLOVA 미사용).

## 구조
- **frozen v1**: {stats['frozen_v1_fixtures']} fixtures (회귀 비교용 holdout, split 보존) — {stats['frozen_v1_by_split']}
- **new candidates**: {stats['new_candidates']} (detector/ROI annotation pool), distinct products {stats['distinct_new_products']}, 카테고리 {stats['category_coverage']}종
- **v2 total**: {stats['v2_total']}

## new pool product-level split (누수 없음, 203과 제품 분리)
{stats['new_by_split']}

## failure-targeted 강도 (new pool)
{stats['hardness_counts']}
(long_page=상세페이지 길이≥3000px, fragmented_product=성분/섭취가 다른 페이지에 분리, low_signal=현행 OCR이 성분·섭취 미검출=하드)

## new pool 카테고리 분포 (top 15)
| category | n |
|---|---|
{top}

## 최소 라벨 스키마 (각 candidate.annotation)
- bbox: ingredient_amounts, intake_method (필수), supplement_facts/product_identity (가능 시)
- structured_gt: ingredient_amounts[], intake_method[], precautions[], allergen_warnings[]
- (full-text LCS GT는 별도 벤치마크에서만)

## 다음 단계 (기존 운영 파이프라인 연결)
1. 이 candidate 매니페스트 → PII screening 배치 생성 → 운영자 검토(cleared).
2. cleared 이미지 → CLOVA teacher로 per-field bbox+text 자동 채움 → 운영자 검증(섹션 bbox + structured GT 확정).
3. benchmark manifest 병합(frozen 203 + new) → product-level split 확정 → 게이트.
4. 섹션 검출기 학습용 = new pool의 bbox; recognizer/holdout 회귀 = frozen 203.

> 매니페스트는 redaction 준수(해시/플래그/카운트만, 원문·literal 경로 없음). resolution map은 운영자용(gitignored).
"""


def main() -> None:
    """CLI entry point."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--crawl-root", required=True, type=Path)
    ap.add_argument("--splits", required=True, type=Path)
    ap.add_argument("--inventory", required=True, type=Path)
    ap.add_argument("--cache", required=True, type=Path)
    ap.add_argument("--manifest", required=True, type=Path)
    ap.add_argument("--resolution-map", required=True, type=Path)
    ap.add_argument("--plan", required=True, type=Path)
    ap.add_argument("--target-new", type=int, default=297)
    ap.add_argument("--max-images-per-product", type=int, default=8)
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    build(
        crawl_root=a.crawl_root,
        splits=a.splits,
        inventory=a.inventory,
        cache_path=a.cache,
        manifest=a.manifest,
        resolution_map=a.resolution_map,
        plan=a.plan,
        target_new=a.target_new,
        max_images=a.max_images_per_product,
        limit=a.limit,
    )


if __name__ == "__main__":
    main()
