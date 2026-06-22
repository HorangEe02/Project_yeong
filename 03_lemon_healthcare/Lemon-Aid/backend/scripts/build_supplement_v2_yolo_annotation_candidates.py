"""Adapt benchmark v2 candidates into YOLO section-bbox annotation candidates.

Bridges the v2 candidate pool (schema ``supplement-ocr-benchmark-v2-candidate-v1``)
and the existing annotation chain: it emits rows in the
``supplement-detail-page-yolo-annotation-candidate-v1`` schema consumed by
``export_supplement_yolo_annotation_template.py`` -> ``build_supplement_yolo_annotation_review_bundle.py``
so an operator can draw 8-section bboxes in Label Studio.

Resolution: each candidate (product_dir_hash + image_index) is resolved to its
crawling-image path; ``image_ref_hash`` is computed as ``sha256(<path relative to
crawl-root>)`` to match the template exporter's materialization map. The image
sha256 is re-verified for integrity.

contains_personal_data is set False under the operator-approved crawling-teacher
exception (same corpus as the 203 benchmark + teacher datasets). No raw OCR text,
payloads, absolute paths, or product-directory literals are emitted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import unicodedata
from pathlib import Path
from typing import Any

DETAIL_DIR_NAME = "상세페이지"
IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".webp")
MIME_BY_SUFFIX = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}
CANDIDATE_SCHEMA_VERSION = "supplement-detail-page-yolo-annotation-candidate-v1"


def _product_hash(product_dir: Path, crawl_root: Path) -> str:
    """Return sha256 of the product dir path relative to the crawl root."""
    return hashlib.sha256(
        product_dir.resolve().relative_to(crawl_root.resolve()).as_posix().encode()
    ).hexdigest()


def _detail_dir(product_dir: Path) -> Path | None:
    """Return the detail-page subfolder (NFC-tolerant)."""
    expected = unicodedata.normalize("NFC", DETAIL_DIR_NAME)
    for child in product_dir.iterdir():
        if child.is_dir() and unicodedata.normalize("NFC", child.name) == expected:
            return child
    return None


def _detail_images(product_dir: Path) -> list[Path]:
    """Return sorted detail-page image paths."""
    detail = _detail_dir(product_dir)
    if detail is None:
        return []
    return sorted(p for p in detail.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES)


def _iter_products(crawl_root: Path) -> list[Path]:
    """Return product directories containing a detail-page subfolder."""
    out: list[Path] = []
    for category_dir in sorted(p for p in crawl_root.iterdir() if p.is_dir()):
        for product_dir in sorted(p for p in category_dir.iterdir() if p.is_dir()):
            if _detail_dir(product_dir) is not None:
                out.append(product_dir)
    return out


def _category_key(raw: str | None) -> str:
    """Normalize a folder category like '[BCAA_EAA]' to 'bcaa_eaa'.

    Applies NFC so macOS-decomposed (NFD) Korean folder names match the safe-token
    Hangul range (가-힣) expected downstream.
    """
    norm = unicodedata.normalize("NFC", raw or "")
    return norm.strip().strip("[]").lower() or "unknown"


def build(*, crawl_root: Path, manifests: list[Path], output: Path) -> None:
    """Resolve v2 candidates to annotation candidates and write the manifest."""
    wanted: dict[str, list[dict[str, Any]]] = {}
    total = 0
    for m in manifests:
        for line in m.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            wanted.setdefault(r["product_dir_hash"], []).append(r)
            total += 1

    rows: list[dict[str, Any]] = []
    sha_mismatch = 0
    seen: set[str] = set()
    for product_dir in _iter_products(crawl_root):
        h = _product_hash(product_dir, crawl_root)
        if h not in wanted:
            continue
        images = _detail_images(product_dir)
        for rec in wanted[h]:
            idx = rec["image_index"]
            if idx >= len(images):
                continue
            path = images[idx]
            if hashlib.sha256(path.read_bytes()).hexdigest() != rec["image_sha256"]:
                sha_mismatch += 1
                continue
            rel = path.resolve().relative_to(crawl_root.resolve()).as_posix()
            ref_hash = hashlib.sha256(rel.encode("utf-8")).hexdigest()
            if ref_hash in seen:
                continue
            seen.add(ref_hash)
            rows.append(
                {
                    "schema_version": CANDIDATE_SCHEMA_VERSION,
                    "candidate_purpose": "supplement_section_bbox_annotation",
                    "source_kind": "detail_page",
                    "annotation_task_type": "supplement_roi_box",
                    "contains_personal_data": False,
                    "local_processing_allowed": True,
                    "custom_section_model_required": True,
                    "coco_pretrained_allowed_for_final_labels": False,
                    "fixture_id": rec["candidate_id"],
                    "source_ref": f"crawling-image:{h[:32]}-i{idx}",
                    "image_ref_hash": ref_hash,
                    "image_sha256": rec["image_sha256"],
                    "image_mime_type": MIME_BY_SUFFIX.get(path.suffix.lower(), "image/jpeg"),
                    "category_key": _category_key(rec.get("category")),
                    "v2_split": rec.get("v2_split"),
                }
            )
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(
        json.dumps(
            {
                "input_candidates": total,
                "resolved_annotation_candidates": len(rows),
                "sha_mismatch": sha_mismatch,
            },
            ensure_ascii=False,
        )
    )


def main() -> None:
    """CLI entry point."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--crawl-root", required=True, type=Path)
    ap.add_argument(
        "--candidate-manifest",
        required=True,
        type=Path,
        action="append",
        help="v2 candidate manifest (repeatable).",
    )
    ap.add_argument("--output", required=True, type=Path)
    a = ap.parse_args()
    build(crawl_root=a.crawl_root, manifests=a.candidate_manifest, output=a.output)


if __name__ == "__main__":
    main()
