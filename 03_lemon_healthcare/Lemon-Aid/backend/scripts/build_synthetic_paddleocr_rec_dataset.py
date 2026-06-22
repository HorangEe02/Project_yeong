"""Synthesize a PaddleOCR recognition fine-tune dataset for supplement labels.

Real recognizer fine-tuning needs cropped text-line images paired with their
transcriptions. The CLOVA pseudo-GT only holds *structured* fields (no line
crops, no line transcriptions), so this tool renders SYNTHETIC Korean text-line
images from the target label vocabulary (ingredient display-names + amount/unit
patterns + intake phrases) using a local font. The transcriptions are authored
text we generate — not raw OCR of any real image — so nothing private is written.

Output layout matches what ``build_paddleocr_finetune_run_plan.py`` validates:

    <output-dir>/rec/images/<split>/*.png
    <output-dir>/rec/rec_gt_train.txt   # "rec/images/train/xxx.png\\t<text>"
    <output-dir>/rec/rec_gt_val.txt

This is a CPU-only, seed-stable seed dataset that proves the fine-tune recipe end
to end up to the GPU ``--execute`` boundary. Synthetic-only training has a
sim-to-real gap; scale up and/or mix real photo line-crops for production.

Runs in the PaddleOCR venv (``.venv-paddle``); does not import the backend.

References:
    https://www.paddleocr.ai/v3.3.2/en/version2.x/ppocr/model_train/recognition.html
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

DEFAULT_FONT = "/System/Library/Fonts/AppleSDGothicNeo.ttc"
LINE_HEIGHT = 48
NAME_AMOUNT_PROB = 0.5  # P(line = "<name> <amount><unit>")
NAME_ONLY_PROB = 0.75  # cumulative P(line is a bare ingredient name)
ROTATE_PROB = 0.3  # P(apply a small rotation augmentation)
UNITS = ("mg", "g", "mcg", "µg", "IU", "mL", "억 CFU", "%")
INTAKE_TEMPLATES = (
    "1일 1회 1정 섭취",
    "1일 1회 1캡슐 섭취",
    "1일 2회 1정",
    "1일 1회 2정",
    "식후 30분 이내 섭취",
    "충분한 물과 함께 섭취",
    "1일 1회 1포 섭취",
)
# Generic Korean supplement ingredient vocabulary (independent baseline lexicon).
GENERIC_INGREDIENTS = (
    "비타민C",
    "비타민D",
    "비타민B6",
    "비타민B12",
    "비타민E",
    "아연",
    "마그네슘",
    "칼슘",
    "철분",
    "오메가3",
    "루테인",
    "프로바이오틱스",
    "콜라겐",
    "밀크씨슬",
    "코엔자임Q10",
    "글루코사민",
    "엽산",
    "EPA",
    "DHA",
    "셀레늄",
)


def _font(size: int) -> ImageFont.FreeTypeFont:
    """Return the rendering font at a given size (falls back to PIL default)."""
    try:
        return ImageFont.truetype(DEFAULT_FONT, size)
    except OSError:
        return ImageFont.load_default()


def _ingredient_vocab(gt_path: Path | None, exclude_ids: set[str] | None = None) -> list[str]:
    """Return ingredient display-names from the GT plus a generic baseline lexicon.

    Args:
        gt_path: Optional ground-truth JSONL to harvest target vocabulary from.
        exclude_ids: Fixture ids whose vocabulary must NOT be harvested (e.g.
            holdout/test fixtures) to avoid vocabulary-level eval leakage.

    Returns:
        Deduplicated ingredient name strings.
    """
    names: set[str] = set(GENERIC_INGREDIENTS)
    skip = exclude_ids or set()
    if gt_path is not None and gt_path.is_file():
        for line in gt_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if str(row.get("fixture_id")) in skip:
                continue
            expected = row.get("expected")
            if not isinstance(expected, dict):
                continue
            for item in expected.get("ingredients", []) or []:
                if isinstance(item, dict) and isinstance(item.get("display_name"), str):
                    name = item["display_name"].strip()
                    if name:
                        names.add(name)
    return sorted(names)


def _synth_lines(vocab: list[str], count: int, rng: random.Random) -> list[str]:
    """Return synthetic text lines drawn from the supplement label grammar.

    Args:
        vocab: Ingredient name vocabulary.
        count: Number of lines to synthesize.
        rng: Seeded RNG.

    Returns:
        Authored Korean text-line strings.
    """
    lines: list[str] = []
    for _ in range(count):
        kind = rng.random()
        if kind < NAME_AMOUNT_PROB:
            name = rng.choice(vocab)
            amount = rng.choice((50, 100, 200, 250, 400, 500, 1000, 1200, 2000))
            unit = rng.choice(UNITS)
            lines.append(f"{name} {amount}{unit}")
        elif kind < NAME_ONLY_PROB:
            lines.append(rng.choice(vocab))
        else:
            lines.append(rng.choice(INTAKE_TEMPLATES))
    return lines


def _render(text: str, rng: random.Random) -> Image.Image:
    """Render one text line to a small RGB image with light augmentation.

    Args:
        text: Line text.
        rng: Seeded RNG.

    Returns:
        A rendered line image.
    """
    size = rng.choice((28, 32, 36, 40))
    font = _font(size)
    pad_x, pad_y = rng.randint(6, 16), rng.randint(4, 10)
    dummy = Image.new("RGB", (8, 8), "white")
    bbox = ImageDraw.Draw(dummy).textbbox((0, 0), text, font=font)
    width = (bbox[2] - bbox[0]) + 2 * pad_x
    height = max(LINE_HEIGHT, (bbox[3] - bbox[1]) + 2 * pad_y)
    shade = rng.randint(245, 255)
    image = Image.new("RGB", (width, height), (shade, shade, shade))
    draw = ImageDraw.Draw(image)
    ink = rng.randint(0, 40)
    draw.text((pad_x - bbox[0], pad_y - bbox[1]), text, font=font, fill=(ink, ink, ink))
    if rng.random() < ROTATE_PROB:
        image = image.rotate(rng.uniform(-2.0, 2.0), expand=True, fillcolor=(shade, shade, shade))
    return image


def _excluded_fixture_ids(splits_path: Path | None) -> set[str]:
    """Return fixture ids in holdout/test splits (excluded from vocab harvest).

    Args:
        splits_path: Optional benchmark split assignment JSONL.

    Returns:
        Fixture ids whose vocabulary must not leak into synthetic training.
    """
    excluded: set[str] = set()
    if splits_path is not None and splits_path.is_file():
        for line in splits_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if str(row.get("split")) in ("holdout", "test"):
                excluded.add(str(row.get("fixture_id")))
    return excluded


def build(
    *,
    gt_path: Path | None,
    splits_path: Path | None,
    output_dir: Path,
    train_count: int,
    val_count: int,
    seed: int,
) -> dict[str, Any]:
    """Render a synthetic recognition dataset and write PaddleOCR label files.

    Args:
        gt_path: Optional GT JSONL for target vocabulary.
        output_dir: Dataset root directory.
        train_count: Number of train lines.
        val_count: Number of val lines.
        seed: RNG seed for reproducibility.

    Returns:
        Count-only summary (no rendered text echoed).
    """
    rng = random.Random(seed)
    exclude_ids = _excluded_fixture_ids(splits_path)
    vocab = _ingredient_vocab(gt_path, exclude_ids)
    rec_dir = output_dir / "rec"
    counts: dict[str, int] = {}
    for split, count in (("train", train_count), ("val", val_count)):
        img_dir = rec_dir / "images" / split
        img_dir.mkdir(parents=True, exist_ok=True)
        label_rows: list[str] = []
        for index, text in enumerate(_synth_lines(vocab, count, rng)):
            rel = f"rec/images/{split}/{split}_{index:05d}.png"
            _render(text, rng).save(output_dir / rel)
            label_rows.append(f"{rel}\t{text}")
        (rec_dir / f"rec_gt_{split}.txt").write_text("\n".join(label_rows) + "\n", encoding="utf-8")
        counts[split] = len(label_rows)
    return {
        "schema_version": "synthetic-paddleocr-rec-dataset-v1",
        "dataset_dir_name": output_dir.name,
        "vocab_size": len(vocab),
        "vocab_excluded_fixture_count": len(exclude_ids),
        "split_counts": counts,
        "label_files": ["rec/rec_gt_train.txt", "rec/rec_gt_val.txt"],
        "raw_ocr_text_stored": False,
        "synthetic_only": True,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gt", type=Path, default=None, help="Optional GT JSONL for target vocab.")
    parser.add_argument(
        "--splits",
        type=Path,
        default=None,
        help="Benchmark split assignment JSONL; holdout/test vocab is excluded to avoid leakage.",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--train-count", type=int, default=500)
    parser.add_argument("--val-count", type=int, default=80)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.apply:
        print(json.dumps({"apply_requested": False}))
        return 0
    summary = build(
        gt_path=args.gt,
        splits_path=args.splits,
        output_dir=args.output_dir,
        train_count=args.train_count,
        val_count=args.val_count,
        seed=args.seed,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
