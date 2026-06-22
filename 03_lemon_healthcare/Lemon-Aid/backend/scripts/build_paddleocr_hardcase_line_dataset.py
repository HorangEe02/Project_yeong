"""Build a diagnostic PaddleOCR rec dataset from structured OCR hard cases.

The structured holdout gate can identify fixtures where every ingredient was
missed. Those fixtures do not contain reviewed line-level boxes, so this tool
renders synthetic text-line crops from the reviewed structured fields and writes
PaddleOCR recognition labels. The resulting dataset is useful for a diagnostic
stage4 recognizer pass, but if the source hard cases come from holdout/test it
must not be used to claim a production promotion on that same gate.

The output follows PaddleOCR SimpleDataSet recognition format:

    <output-dir>/rec/images/<split>/*.png
    <output-dir>/rec/rec_gt_train.txt
    <output-dir>/rec/rec_gt_val.txt
    <output-dir>/dict.txt

References:
    https://www.paddleocr.ai/latest/en/version2.x/ppocr/model_train/recognition.html
"""

from __future__ import annotations

import argparse
import json
import random
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

SCHEMA_VERSION = "paddleocr-hardcase-line-rec-dataset-v1"
FONT_CANDIDATES = (
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
    "C:/Windows/Fonts/malgun.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
)
DEFAULT_FONT_SIZE_RANGE = (28, 40)
DEFAULT_LINE_HEIGHT = 52
DEFAULT_CANVAS_PAD_X_RANGE = (8, 18)
DEFAULT_CANVAS_PAD_Y_RANGE = (5, 12)
DEFAULT_ROTATE_DEGREES = 1.8
DEFAULT_ROTATE_PROBABILITY = 0.35
TAB_OR_NEWLINE = re.compile(r"[\t\r\n]")
PLACEHOLDER_TEXT_VALUES = {"", "null", "none", "n/a", "na", "-", "미상", "확인불가", "확인 불가"}


class HardcaseDatasetError(RuntimeError):
    """Raised when a hard-case dataset cannot be built safely."""


def _load_json(path: Path) -> dict[str, Any]:
    """Load a JSON object.

    Args:
        path: JSON file path.

    Returns:
        Parsed JSON object.

    Raises:
        HardcaseDatasetError: If the file is missing or not a JSON object.
    """
    if not path.is_file():
        raise HardcaseDatasetError("JSON input file is missing.")
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise HardcaseDatasetError("JSON input must be an object.")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read JSONL rows.

    Args:
        path: JSONL file path.

    Returns:
        Parsed JSON object rows.

    Raises:
        HardcaseDatasetError: If any row is not an object.
    """
    if not path.is_file():
        raise HardcaseDatasetError("ground-truth JSONL file is missing.")
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise HardcaseDatasetError("ground-truth JSONL rows must be objects.")
        rows.append(row)
    return rows


def _hardcase_fixture_ids(manifest: dict[str, Any]) -> list[str]:
    """Return ingredient-all-missed fixture ids from a hardcase manifest.

    Args:
        manifest: Output from ``extract_supplement_structured_hardcases``.

    Returns:
        Fixture ids in manifest order.

    Raises:
        HardcaseDatasetError: If the expected id list is absent.
    """
    fixture_ids = (manifest.get("fixture_ids") or {}).get("ingredient_all_missed")
    if not isinstance(fixture_ids, list):
        raise HardcaseDatasetError("hardcase manifest lacks ingredient_all_missed ids.")
    ids = [str(item).strip() for item in fixture_ids if str(item).strip()]
    if not ids:
        raise HardcaseDatasetError("hardcase manifest does not contain target fixtures.")
    return ids


def _is_holdout_or_test(manifest: dict[str, Any]) -> bool:
    """Return whether the hardcase manifest came from a protected eval split."""
    return str(manifest.get("eval_split") or "").strip().lower() in {"holdout", "test"}


def _eval_split(manifest: dict[str, Any]) -> str:
    """Return normalized source split from a hardcase manifest."""
    return str(manifest.get("eval_split") or "").strip().lower()


def _safe_text(value: object) -> str | None:
    """Return a single-line label text value or None.

    Args:
        value: Candidate label value.

    Returns:
        Normalized text without tabs/newlines, or None.
    """
    if value is None:
        return None
    text = " ".join(str(value).split()).strip()
    if not text or text.casefold() in PLACEHOLDER_TEXT_VALUES or TAB_OR_NEWLINE.search(text):
        return None
    return text


def _ingredient_lines(ingredient: dict[str, Any]) -> list[str]:
    """Return label candidates for one structured ingredient.

    Args:
        ingredient: Structured ingredient row.

    Returns:
        Deduplicated line labels for training.
    """
    names = [
        _safe_text(ingredient.get("display_name")),
        _safe_text(ingredient.get("original_name")),
    ]
    names = [name for name in names if name]
    amount = _safe_text(ingredient.get("amount"))
    unit = _safe_text(ingredient.get("unit"))
    amount_unit = " ".join(part for part in (amount, unit) if part).strip()
    lines: list[str] = []
    for name in names:
        lines.append(name)
        if amount_unit:
            lines.append(f"{name} {amount_unit}")
    if amount_unit:
        lines.append(amount_unit)
    return _dedupe(lines)


def _field_lines(expected: dict[str, Any]) -> list[str]:
    """Return supplement label field lines beyond ingredients.

    Args:
        expected: Structured expected object.

    Returns:
        Deduplicated non-empty label lines.
    """
    candidates: list[str] = []
    for key in ("product_name", "manufacturer", "intake_method"):
        text = _safe_text(expected.get(key))
        if text:
            candidates.append(text)
    for key in ("precautions", "allergen_warnings", "functional_claims"):
        value = expected.get(key)
        if isinstance(value, list):
            candidates.extend(text for item in value if (text := _safe_text(item)))
        elif text := _safe_text(value):
            candidates.append(text)
    return _dedupe(candidates)


def _dedupe(values: Iterable[str]) -> list[str]:
    """Return values deduplicated in input order."""
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        output.append(value)
    return output


def _labels_for_rows(rows: list[dict[str, Any]], target_ids: set[str]) -> tuple[list[str], int]:
    """Return labels for target fixtures.

    Args:
        rows: Ground-truth JSONL rows.
        target_ids: Fixture ids selected for stage4.

    Returns:
        Tuple of deduplicated labels and matched fixture count.
    """
    labels: list[str] = []
    matched = 0
    for row in rows:
        fixture_id = str(row.get("fixture_id") or "").strip()
        if fixture_id not in target_ids:
            continue
        matched += 1
        expected = row.get("expected")
        if not isinstance(expected, dict):
            continue
        for ingredient in expected.get("ingredients") or []:
            if isinstance(ingredient, dict):
                labels.extend(_ingredient_lines(ingredient))
        labels.extend(_field_lines(expected))
    return _dedupe(labels), matched


def _font(size: int) -> ImageFont.ImageFont:
    """Return a font capable of rendering common Korean supplement labels.

    Args:
        size: Desired font size.

    Returns:
        A Pillow font object.
    """
    for candidate in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _render_line(text: str, rng: random.Random) -> Image.Image:
    """Render one text label into a line crop image.

    Args:
        text: Label text.
        rng: Seeded RNG.

    Returns:
        Rendered RGB image.
    """
    font_size = rng.randint(DEFAULT_FONT_SIZE_RANGE[0], DEFAULT_FONT_SIZE_RANGE[1])
    font = _font(font_size)
    pad_x = rng.randint(DEFAULT_CANVAS_PAD_X_RANGE[0], DEFAULT_CANVAS_PAD_X_RANGE[1])
    pad_y = rng.randint(DEFAULT_CANVAS_PAD_Y_RANGE[0], DEFAULT_CANVAS_PAD_Y_RANGE[1])
    dummy = Image.new("RGB", (16, 16), "white")
    bbox = ImageDraw.Draw(dummy).textbbox((0, 0), text, font=font)
    width = max(32, bbox[2] - bbox[0] + pad_x * 2)
    height = max(DEFAULT_LINE_HEIGHT, bbox[3] - bbox[1] + pad_y * 2)
    shade = rng.randint(244, 255)
    image = Image.new("RGB", (width, height), (shade, shade, shade))
    draw = ImageDraw.Draw(image)
    ink = rng.randint(0, 35)
    draw.text((pad_x - bbox[0], pad_y - bbox[1]), text, font=font, fill=(ink, ink, ink))
    if rng.random() < DEFAULT_ROTATE_PROBABILITY:
        angle = rng.uniform(-DEFAULT_ROTATE_DEGREES, DEFAULT_ROTATE_DEGREES)
        image = image.rotate(angle, expand=True, fillcolor=(shade, shade, shade))
    return image


def _write_split(
    *,
    output_dir: Path,
    split: str,
    labels: list[str],
    repeat_per_label: int,
    rng: random.Random,
) -> int:
    """Render and write one split.

    Args:
        output_dir: Dataset root.
        split: Split name.
        labels: Source text labels.
        repeat_per_label: Number of synthetic crops per label.
        rng: Seeded RNG.

    Returns:
        Number of written rows.
    """
    image_dir = output_dir / "rec" / "images" / split
    image_dir.mkdir(parents=True, exist_ok=True)
    rows: list[str] = []
    index = 0
    for label in labels:
        for _ in range(repeat_per_label):
            relative_path = f"rec/images/{split}/hardcase_{split}_{index:05d}.png"
            _render_line(label, rng).save(output_dir / relative_path)
            rows.append(f"{relative_path}\t{label}")
            index += 1
    (output_dir / "rec" / f"rec_gt_{split}.txt").write_text(
        "\n".join(rows) + ("\n" if rows else ""),
        encoding="utf-8",
    )
    return len(rows)


def _write_dict(output_dir: Path, labels: list[str]) -> int:
    """Write a UTF-8 PaddleOCR character dictionary.

    Args:
        output_dir: Dataset root.
        labels: Label texts.

    Returns:
        Dictionary row count.
    """
    chars = sorted({char for label in labels for char in label if char != " "})
    (output_dir / "dict.txt").write_text(
        "\n".join(chars) + ("\n" if chars else ""), encoding="utf-8"
    )
    return len(chars)


def build_hardcase_line_dataset(
    *,
    hardcase_manifest_path: Path,
    ground_truth_jsonl_path: Path,
    output_dir: Path,
    repeat_per_label: int,
    val_ratio: float,
    seed: int,
    acknowledge_holdout_leakage: bool,
    require_train_source: bool = False,
) -> dict[str, Any]:
    """Build a diagnostic hard-case line crop dataset.

    Args:
        hardcase_manifest_path: Redacted hardcase fixture manifest.
        ground_truth_jsonl_path: Operator-reviewed structured ground-truth JSONL.
        output_dir: Dataset root to create.
        repeat_per_label: Synthetic crops to render per label per selected split.
        val_ratio: Fraction of labels assigned to validation.
        seed: RNG seed.
        acknowledge_holdout_leakage: Required when source manifest is holdout/test.
        require_train_source: Require ``eval_split=train`` for promotion-eligible
            hard-case recognizer datasets.

    Returns:
        Count-only summary.

    Raises:
        HardcaseDatasetError: If inputs are unsafe or no labels can be built.
    """
    manifest = _load_json(hardcase_manifest_path)
    source_eval_split = _eval_split(manifest)
    protected_eval_split = _is_holdout_or_test(manifest)
    if require_train_source and source_eval_split != "train":
        raise HardcaseDatasetError(
            "hardcase source must have eval_split=train when --require-train-source is used."
        )
    if protected_eval_split and not acknowledge_holdout_leakage:
        raise HardcaseDatasetError(
            "hardcase source is holdout/test; pass --acknowledge-holdout-leakage "
            "to build a diagnostic-only dataset."
        )
    if output_dir.exists():
        raise HardcaseDatasetError("output directory already exists.")

    target_ids = set(_hardcase_fixture_ids(manifest))
    labels, matched_fixture_count = _labels_for_rows(
        _read_jsonl(ground_truth_jsonl_path), target_ids
    )
    if not labels:
        raise HardcaseDatasetError("no hardcase labels were found in ground truth.")

    rng = random.Random(seed)
    shuffled = labels[:]
    rng.shuffle(shuffled)
    val_count = int(len(shuffled) * val_ratio)
    if len(shuffled) > 1 and val_count == 0:
        val_count = 1
    val_labels = shuffled[:val_count]
    train_labels = shuffled[val_count:] or shuffled

    output_dir.mkdir(parents=True)
    train_rows = _write_split(
        output_dir=output_dir,
        split="train",
        labels=train_labels,
        repeat_per_label=repeat_per_label,
        rng=rng,
    )
    val_rows = _write_split(
        output_dir=output_dir,
        split="val",
        labels=val_labels,
        repeat_per_label=max(1, repeat_per_label // 4),
        rng=rng,
    )
    dict_rows = _write_dict(output_dir, labels)
    summary = {
        "schema_version": SCHEMA_VERSION,
        "source_eval_split": manifest.get("eval_split"),
        "source_fixture_count": len(target_ids),
        "matched_fixture_count": matched_fixture_count,
        "unique_label_count": len(labels),
        "repeat_per_label": repeat_per_label,
        "split_counts": {"train": train_rows, "val": val_rows},
        "dict_rows": dict_rows,
        "synthetic_line_crops": True,
        "holdout_leakage_acknowledged": bool(acknowledge_holdout_leakage),
        "train_source_required": bool(require_train_source),
        "production_gate_eligible": not protected_eval_split
        and (not require_train_source or source_eval_split == "train"),
        "raw_ocr_text_stored": False,
        "provider_payload_stored": False,
        "label_text_printed": False,
        "private_source_paths_printed": False,
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hardcase-manifest", required=True, type=Path)
    parser.add_argument("--ground-truth-jsonl", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--repeat-per-label", default=64, type=int)
    parser.add_argument("--val-ratio", default=0.1, type=float)
    parser.add_argument("--seed", default=20260616, type=int)
    parser.add_argument("--acknowledge-holdout-leakage", action="store_true")
    parser.add_argument(
        "--require-train-source",
        action="store_true",
        help="Fail unless the hardcase manifest declares eval_split=train.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    args = parse_args(argv)
    try:
        summary = build_hardcase_line_dataset(
            hardcase_manifest_path=args.hardcase_manifest,
            ground_truth_jsonl_path=args.ground_truth_jsonl,
            output_dir=args.output_dir,
            repeat_per_label=args.repeat_per_label,
            val_ratio=args.val_ratio,
            seed=args.seed,
            acknowledge_holdout_leakage=args.acknowledge_holdout_leakage,
            require_train_source=args.require_train_source,
        )
    except HardcaseDatasetError as exc:
        print(json.dumps({"status": "failed", "reason": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
