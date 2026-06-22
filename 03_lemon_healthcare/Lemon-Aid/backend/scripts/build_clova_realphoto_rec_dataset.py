"""Build a real-photo PaddleOCR recognition dataset via CLOVA teacher boxes.

Operator-approved teacher weak-supervision (relaxes the "no raw OCR text in
outputs" rule for *training labels only*): for each real supplement-label review
image, this calls CLOVA OCR, reads each detected field's bounding box + text
(``fields[].boundingPoly.vertices`` / ``inferText``), crops that real-photo line
region, and writes ``<crop>\\t<text>`` PaddleOCR recognition labels. The crops are
real label pixels (not synthetic), so a fine-tune on them closes the sim-to-real
gap that the synthetic-only dataset cannot.

Eval honesty: fixtures in the ``holdout`` (and ``test``) benchmark splits are
EXCLUDED so the held-out ``field_match_ratio`` evaluation stays leakage-free; the
recognizer trains only on ``train``-split images.

Output layout (consumed by ``build_paddleocr_finetune_run_plan.py`` and PaddleX):

    <output-dir>/rec/images/*.png
    <output-dir>/rec/rec_gt_train.txt   # "rec/images/xxx.png\\t<text>"
    <output-dir>/rec/rec_gt_val.txt
    <output-dir>/{train,val}.txt        # PaddleX copies
    <output-dir>/dict.txt

Runs in the py3.13 backend venv (``PYTHONPATH=Nutrition-backend``). External CLOVA
calls + label-text storage occur only with ``--apply``.

References:
    https://api.ncloud-docs.com/docs/en/ai-application-service-ocr
    https://www.paddleocr.ai/v3.3.2/en/version2.x/ppocr/model_train/recognition.html
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
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

MIME_BY_SUFFIX = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}
CROP_PAD = 4
MIN_CROP_SIDE = 6
MIN_VERTICES = 2


async def _clova_fields(
    adapter: ClovaOCRAdapter, settings: Settings, image_path: Path
) -> list[tuple[str, tuple[int, int, int, int]]]:
    """Return ``(text, (x0,y0,x1,y1))`` per CLOVA field for one image.

    Args:
        adapter: CLOVA OCR adapter.
        settings: Runtime settings.
        image_path: Review image path.

    Returns:
        Non-empty field text paired with its axis-aligned bounding box.
    """
    data = image_path.read_bytes()
    with Image.open(image_path) as image:
        width, height = image.size
    mime = MIME_BY_SUFFIX.get(image_path.suffix.lower(), "image/jpeg")
    ocr_input = OCRImageInput(image_bytes=data, mime_type=mime, width=width, height=height)
    response = await adapter._post(
        payload=_build_clova_payload(ocr_input), headers=_build_clova_headers(settings)
    )
    images = response.get("images") if isinstance(response, dict) else None
    if not images:
        return []
    fields = images[0].get("fields") or []
    out: list[tuple[str, tuple[int, int, int, int]]] = []
    for field in fields:
        text = " ".join(str(field.get("inferText") or "").split())
        vertices = (field.get("boundingPoly") or {}).get("vertices") or []
        xs = [v.get("x") for v in vertices if isinstance(v.get("x"), int | float)]
        ys = [v.get("y") for v in vertices if isinstance(v.get("y"), int | float)]
        if not text or len(xs) < MIN_VERTICES or len(ys) < MIN_VERTICES:
            continue
        out.append((text, (int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys)))))
    return out


def _crop(image: Image.Image, box: tuple[int, int, int, int]) -> Image.Image | None:
    """Return a padded crop of ``box`` from ``image`` or None when degenerate."""
    width, height = image.size
    x0 = max(0, box[0] - CROP_PAD)
    y0 = max(0, box[1] - CROP_PAD)
    x1 = min(width, box[2] + CROP_PAD)
    y1 = min(height, box[3] + CROP_PAD)
    if x1 - x0 < MIN_CROP_SIDE or y1 - y0 < MIN_CROP_SIDE:
        return None
    return image.crop((x0, y0, x1, y1))


def _split_ids(splits_path: Path) -> dict[str, str]:
    """Return ``fixture_id -> split`` from a benchmark split assignment JSONL."""
    mapping: dict[str, str] = {}
    for line in splits_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            mapping[str(row.get("fixture_id"))] = str(row.get("split"))
    return mapping


async def build(
    *,
    bundle_dir: Path,
    splits_path: Path,
    output_dir: Path,
    val_ratio: float,
    limit: int | None,
    allow_splits: tuple[str, ...],
    seed: int,
) -> dict[str, Any]:
    """Build the real-photo recognition dataset from CLOVA teacher boxes.

    Args:
        bundle_dir: GT review bundle directory.
        splits_path: Benchmark split assignment JSONL (for leakage-safe selection).
        output_dir: Dataset root directory.
        val_ratio: Fraction of training images held for validation.
        limit: Optional cap on processed images.
        allow_splits: Splits whose fixtures MAY be used for training. The guard is
            fail-closed: a ready row whose fixture_id is absent from the splits file
            (or whose split is not in ``allow_splits``) is skipped, so a stale or
            mismatched splits file can never leak holdout/test images into training.
        seed: RNG seed for the train/val shuffle (reproducible, order-independent).

    Returns:
        Count-only summary.
    """
    rows = [
        json.loads(line)
        for line in (bundle_dir / "ground-truth.todo.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    split_by_id = _split_ids(splits_path)
    ready = [
        row
        for row in rows
        if row.get("ready_for_benchmark_after_review") is True
        and split_by_id.get(str(row.get("fixture_id"))) in allow_splits
    ]
    excluded_not_allowed = sum(
        1 for r in rows if r.get("ready_for_benchmark_after_review") is True
    ) - len(ready)
    random.Random(seed).shuffle(ready)
    if limit is not None:
        ready = ready[:limit]
    settings = get_settings()
    _validate_clova_settings(settings)
    adapter = ClovaOCRAdapter(settings)

    val_cut = int(len(ready) * val_ratio)
    if len(ready) > 1 and val_cut == 0:
        val_cut = 1  # guarantee a non-empty val set when there is enough data
    val_ids = {str(row.get("fixture_id")) for row in ready[:val_cut]}

    rec_dir = output_dir / "rec"
    (rec_dir / "images").mkdir(parents=True, exist_ok=True)
    train_rows: list[tuple[str, str]] = []
    val_rows: list[tuple[str, str]] = []
    chars: set[str] = set()
    stats = {"images": 0, "failed": 0, "crops": 0}
    for row in ready:
        fixture_id = str(row.get("fixture_id"))
        image_path = bundle_dir / str(row.get("image_path", ""))
        try:
            fields = await _clova_fields(adapter, settings, image_path)
            with Image.open(image_path) as image:
                rgb = image.convert("RGB")
                for index, (text, box) in enumerate(fields):
                    crop = _crop(rgb, box)
                    if crop is None:
                        continue
                    rel = f"rec/images/{fixture_id}_{index:03d}.png"
                    crop.save(output_dir / rel)
                    (val_rows if fixture_id in val_ids else train_rows).append((rel, text))
                    chars.update(text)
                    stats["crops"] += 1
            stats["images"] += 1
        except Exception:  # per-image isolation; count and continue
            stats["failed"] += 1

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
    return {
        "schema_version": "clova-realphoto-paddleocr-rec-dataset-v1",
        "dataset_dir_name": output_dir.name,
        "source": "clova_teacher_boxes",
        "allowed_splits": list(allow_splits),
        "excluded_not_allowed_row_count": excluded_not_allowed,
        "image_count": stats["images"],
        "failed_image_count": stats["failed"],
        "crop_count": stats["crops"],
        "train_rows": len(train_rows),
        "val_rows": len(val_rows),
        "dict_size": len(chars),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-dir", type=Path, required=True)
    parser.add_argument(
        "--splits", type=Path, required=True, help="Benchmark split assignment JSONL."
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--val-ratio", type=float, default=0.1)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--seed", type=int, default=42, help="Seed for the train/val shuffle.")
    parser.add_argument(
        "--include-test",
        action="store_true",
        help="Also train on the test split (default: train only).",
    )
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not (args.bundle_dir / "ground-truth.todo.jsonl").is_file():
        raise SystemExit(f"ERROR: ground-truth.todo.jsonl not found under {args.bundle_dir}")
    # Fail-closed allow-list: only the train split (and optionally test) may be used.
    allow_splits = ("train", "test") if args.include_test else ("train",)
    # Guard: these labels embed CLOVA teacher text — keep them under a gitignored
    # outputs/.../datasets/ tree (operator-approved scope), never a tracked path.
    resolved_output = args.output_dir.expanduser().resolve()
    if "datasets" not in resolved_output.parts:
        raise SystemExit(
            "ERROR: --output-dir must live under a 'datasets/' directory so the teacher-text "
            "training labels stay in gitignored outputs/.../datasets/ (redaction policy)."
        )
    if not args.apply:
        print(json.dumps({"apply_requested": False, "allowed_splits": list(allow_splits)}))
        return 0
    summary = asyncio.run(
        build(
            bundle_dir=args.bundle_dir,
            splits_path=args.splits,
            output_dir=args.output_dir,
            val_ratio=args.val_ratio,
            limit=args.limit,
            allow_splits=allow_splits,
            seed=args.seed,
        )
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
