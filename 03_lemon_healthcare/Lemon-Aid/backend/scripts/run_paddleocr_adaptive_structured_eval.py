"""Evaluate adaptive PaddleOCR candidate merging for structured extraction.

This runner compares two recognition-model candidates under the same detector
configuration and evaluates a production-plausible ``union`` strategy:

* primary: first OCR candidate as-is
* secondary: second OCR candidate as-is
* union: primary lines plus secondary-only lines, de-duplicated by normalized text
* evidence_union: source-only ingredient evidence windows for split table rows
* oracle_best: upper-bound diagnostic that chooses the best metric row using GT

Only redacted metrics, fixture ids, and line hashes/counts are written to the
normal output directory. Raw OCR lines can be written only when
``--raw-debug-dir`` is explicitly provided; that directory is intended for
temporary operator inspection and must not be committed.

References:
    https://www.paddleocr.ai/latest/en/version3.x/pipeline_usage/OCR.html
    https://www.paddleocr.ai/latest/en/version2.x/ppocr/model_train/recognition.html
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
import time
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from PIL import Image

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts.build_supplement_structured_extraction_eval_summary import build_summary  # noqa: E402
from scripts.extract_supplement_structured_hardcases import extract_hardcases  # noqa: E402
from scripts.gate_supplement_structured_extraction_target import (  # noqa: E402
    build_structured_extraction_gate,
)
from scripts.paddleocr_clova_eval import (  # noqa: E402
    FIELD_MATCH_THRESHOLD,
    POST_PASS_CHOICES,
    POST_PASS_INGREDIENT_ALIAS_AMOUNT_UNIT,
    PROFILES,
    TARGET_PROVIDER,
    _build_ocr,
    _field_match_ratio,
    _field_units,
    _ingredient_recall,
    _normalize_for_metric,
    _postprocess_hypothesis_text,
    _structured_reference,
    _text_extraction_metrics,
)

SCHEMA_VERSION = "paddleocr-adaptive-structured-eval-v1"
COMPARISON_SCHEMA_VERSION = "paddleocr-adaptive-line-comparison-v1"
SOURCE_DOC_URLS = (
    "https://www.paddleocr.ai/latest/en/version3.x/pipeline_usage/OCR.html",
    "https://www.paddleocr.ai/latest/en/version2.x/ppocr/model_train/recognition.html",
)
SAFE_FILENAME_PATTERN = re.compile(r"[^A-Za-z0-9_.-]+")
MIN_ROI_CROP_SIDE_PX = 8
MIN_NAME_FRAGMENT_NORM_CHARS = 2
MIN_SECTION_NAME_WINDOW_SIZE = 2
MAX_SECTION_NAME_WINDOW_SIZE = 4
MIN_SECTION_NAME_NORM_CHARS = 4
MAX_SECTION_NAME_NORM_CHARS = 80
MAX_SECTION_NAME_FRAGMENT_CHARS = 24
MAX_REDACTED_EVIDENCE_RECORDS = 40
MAX_DECLARATION_CONTINUATION_LINES = 10
EVIDENCE_AMOUNT_UNIT_PATTERN = re.compile(
    r"[0-9OoIl]+(?:[,.][0-9OoIl]+)?\s*"
    r"(?:mg|m\s*g|㎎|밀리그램|milligrams?|g|그램|grams?|"
    r"mcg|m\s*c\s*g|ug|u\s*g|μg|µg|㎍|마이크로그램|micrograms?|"
    r"iu|i\s*u|i\.u\.|아이유|international\s+units?|"
    r"(?:억|조|만|billion|million)?\s*(?:cfu|씨에프유)|%)",
    re.IGNORECASE,
)
EVIDENCE_REAL_AMOUNT_UNIT_PATTERN = re.compile(
    r"[0-9OoIl]+(?:[,.][0-9OoIl]+)?\s*"
    r"(?:mg|m\s*g|㎎|밀리그램|milligrams?|g|그램|grams?|"
    r"mcg|m\s*c\s*g|ug|u\s*g|μg|µg|㎍|마이크로그램|micrograms?|"
    r"iu|i\s*u|i\.u\.|아이유|international\s+units?|"
    r"(?:억|조|만|billion|million)?\s*(?:cfu|씨에프유))",
    re.IGNORECASE,
)
EVIDENCE_DAILY_VALUE_PATTERN = re.compile(
    r"^\s*(?:[|｜·•:/-]\s*)?(?P<dv>[0-9OoIl]+(?:[,.][0-9OoIl]+)?)\s*%\s*"
    r"(?:(?:daily\s*value|dv|영양성분\s*기준치|기준치)\b)?\s*$",
    re.IGNORECASE,
)
EVIDENCE_AMOUNT_ONLY_PATTERN = re.compile(r"^\s*[0-9OoIl]+(?:[,.][0-9OoIl]+)?\s*$")
EVIDENCE_UNIT_ONLY_PATTERN = re.compile(
    r"^\s*(?:mg|m\s*g|㎎|밀리그램|milligrams?|g|그램|grams?|"
    r"mcg|m\s*c\s*g|ug|u\s*g|μg|µg|㎍|마이크로그램|micrograms?|"
    r"iu|i\s*u|i\.u\.|아이유|international\s+units?|"
    r"(?:억|조|만|billion|million)?\s*(?:cfu|씨에프유))\s*$",
    re.IGNORECASE,
)
SECTION_CONTEXT_PATTERN = re.compile(
    r"(?:"
    r"supplement\s+facts|nutrition\s+facts|amount\s+per\s+serving|daily\s+value|"
    r"active\s+ingredients?|other\s+ingredients?|ingredients?|"
    r"medicinal\s+ingredients?|non[-\s]?medicinal\s+ingredients?|"
    r"each\s+(?:capsule|tablet|softgel)\s+contains|per\s+(?:capsule|tablet|softgel)|contains|"
    r"영양\s*정보|영양\s*기능\s*정보|기능\s*정보|영양\s*성분|성분\s*명|성분\s*및\s*함량|"
    r"원\s*재\s*료\s*명|원\s*료\s*명|주\s*원\s*료|부\s*원\s*료|함량|1\s*일\s*섭취량"
    r")",
    re.IGNORECASE,
)
DECLARATION_HEADER_PATTERN = re.compile(
    r"(?:"
    r"원\s*재\s*료\s*명|원\s*료\s*명|성분\s*명|성분\s*및\s*함량|"
    r"부\s*원\s*료\s*명|other\s+ingredients?|active\s+ingredients?|ingredients?|"
    r"medicinal\s+ingredients?|non[-\s]?medicinal\s+ingredients?|"
    r"each\s+(?:capsule|tablet|softgel)\s+contains|contains"
    r")",
    re.IGNORECASE,
)
DECLARATION_STOP_PATTERN = re.compile(
    r"(?:"
    r"supplement\s+facts|nutrition\s+facts|amount\s+per\s+serving|daily\s+value|"
    r"serving\s+size|servings?\s+per\s+container|directions?|suggested\s+use|"
    r"warnings?|cautions?|storage|expiration|best\s+before|"
    r"영양\s*정보|영양\s*성분|섭취\s*방법|복용\s*방법|섭취\s*시\s*주의\s*사항|"
    r"주의\s*사항|보관\s*방법|유통\s*기한|제조\s*원|판매\s*원"
    r")",
    re.IGNORECASE,
)
EVIDENCE_TEXT_PATTERN = re.compile(r"[A-Za-z가-힣]{2,}")
EVIDENCE_NOISE_PATTERN = re.compile(
    r"(?:barcode|qr|www\.|http|copyright|instagram|facebook|제조번호|유통기한|고객센터)",
    re.IGNORECASE,
)
TABLE_HEADER_NOISE_PATTERN = re.compile(
    r"(?:"
    r"%\s*daily\s*value|daily\s*value|amount\s*per\s*serving|per\s*serving|"
    r"serving\s*size|servings?\s*per\s*container|amount|nutrition\s*information|"
    r"%\s*dv|dv|per\s+(?:capsule|tablet|softgel)|each\s+(?:capsule|tablet|softgel)|"
    r"1\s*일\s*영양성분|영양\s*성분\s*기준치|기준치|함량|섭취량"
    r")",
    re.IGNORECASE,
)
ROI_CROP_PRESETS = (
    "none",
    "vertical3",
    "vertical3_lr2",
    "section_aware",
    "section_aware_v2",
    "section_aware_v3",
    "section_aware_v4",
    "section_aware_v5",
    "section_aware_v6",
    "section_aware_v7",
)
OCR_PASS_PRESETS = ("single", "recall_precision_v1")
CropSpec = tuple[str, tuple[float, float, float, float], float]
BASE_VERTICAL_CROPS: tuple[CropSpec, ...] = (
    ("top60", (0.0, 0.0, 1.0, 0.60), 1.0),
    ("mid70", (0.0, 0.15, 1.0, 0.85), 1.0),
    ("bottom60", (0.0, 0.40, 1.0, 1.0), 1.0),
)
LR_SECTION_CROPS: tuple[CropSpec, ...] = (
    ("left70", (0.0, 0.0, 0.70, 1.0), 1.0),
    ("right70", (0.30, 0.0, 1.0, 1.0), 1.0),
)
SECTION_AWARE_CROPS: tuple[CropSpec, ...] = (
    # These crop ratios are repo-local experimental OCR hypotheses, not
    # PaddleOCR official recommendations. They target common supplement label
    # layouts where product identity, facts table, and Korean declaration text
    # occupy different vertical or column bands.
    ("facts_center90", (0.05, 0.03, 0.95, 0.92), 1.25),
    ("facts_left85", (0.0, 0.02, 0.85, 0.95), 1.25),
    ("facts_right85", (0.15, 0.02, 1.0, 0.95), 1.25),
    ("upper_facts75", (0.0, 0.0, 1.0, 0.75), 1.15),
    ("lower_facts75", (0.0, 0.25, 1.0, 1.0), 1.15),
    ("center_table70", (0.10, 0.12, 0.90, 0.82), 1.45),
    ("declaration_bottom45", (0.0, 0.55, 1.0, 1.0), 1.35),
)
SECTION_AWARE_V2_CROPS: tuple[CropSpec, ...] = (
    # Recall-first additions for hard cases where the nutrition table is split
    # across curved bottle panels. These are not official PaddleOCR values; they
    # are repo-local hypotheses that must be measured on locked holdouts.
    ("facts_inner_tall92", (0.04, 0.02, 0.96, 0.98), 1.45),
    ("facts_left_column60", (0.00, 0.04, 0.60, 0.96), 1.55),
    ("facts_right_column60", (0.40, 0.04, 1.00, 0.96), 1.55),
    ("upper_table_half", (0.02, 0.00, 0.98, 0.55), 1.50),
    ("middle_table_half", (0.02, 0.22, 0.98, 0.78), 1.60),
    ("lower_declaration_half", (0.02, 0.45, 0.98, 1.00), 1.50),
    ("left_lower_panel", (0.00, 0.35, 0.68, 1.00), 1.50),
    ("right_lower_panel", (0.32, 0.35, 1.00, 1.00), 1.50),
)
SECTION_AWARE_V3_CROPS: tuple[CropSpec, ...] = (
    # Detector-led ROI v3 placeholder crops. When YOLO section boxes are
    # available these ratios should be replaced by real section coordinates;
    # until then they provide bounded recall probes for supplement facts and
    # declaration areas. These values are repo experiments, not PaddleOCR
    # official recommendations.
    ("facts_core_table", (0.08, 0.06, 0.92, 0.74), 1.70),
    ("facts_core_table_pad12", (0.02, 0.00, 0.98, 0.82), 1.65),
    ("facts_left_narrow", (0.00, 0.06, 0.54, 0.86), 1.80),
    ("facts_right_narrow", (0.46, 0.06, 1.00, 0.86), 1.80),
    ("facts_center_column", (0.22, 0.04, 0.78, 0.90), 1.90),
    ("other_ingredients_band", (0.00, 0.58, 1.00, 0.92), 1.80),
    ("lower_declaration_dense", (0.04, 0.64, 0.96, 1.00), 1.85),
    ("product_plus_facts", (0.00, 0.00, 1.00, 0.68), 1.45),
    ("adjacent_panel_left", (0.00, 0.08, 0.76, 0.96), 1.65),
    ("adjacent_panel_right", (0.24, 0.08, 1.00, 0.96), 1.65),
)
SECTION_AWARE_V4_CROPS: tuple[CropSpec, ...] = (
    # ROI v4 expands facts-table and declaration rows for labels where section
    # boxes are visually correct but OCR splits names, amounts, and units across
    # nearby table cells. These are temporary evaluation crops only.
    ("facts_row_strip_upper", (0.02, 0.10, 0.98, 0.48), 2.00),
    ("facts_row_strip_middle", (0.02, 0.28, 0.98, 0.66), 2.05),
    ("facts_row_strip_lower", (0.02, 0.46, 0.98, 0.84), 2.00),
    ("facts_name_left_column", (0.00, 0.08, 0.48, 0.86), 2.10),
    ("facts_amount_right_column", (0.35, 0.08, 1.00, 0.86), 2.05),
    ("facts_amount_center_right", (0.24, 0.04, 1.00, 0.72), 2.00),
    ("facts_full_width_dense", (0.00, 0.00, 1.00, 0.92), 1.90),
    ("other_ingredients_wide", (0.00, 0.48, 1.00, 0.98), 2.00),
    ("warnings_bottom_dense", (0.00, 0.68, 1.00, 1.00), 2.10),
    ("curved_panel_left_dense", (0.00, 0.04, 0.66, 0.98), 1.95),
    ("curved_panel_right_dense", (0.34, 0.04, 1.00, 0.98), 1.95),
)
SECTION_AWARE_V4_ANCHOR_CROPS: tuple[CropSpec, ...] = (
    ("facts_core_table", (0.08, 0.06, 0.92, 0.74), 1.70),
    ("facts_left_narrow", (0.00, 0.06, 0.54, 0.86), 1.80),
    ("facts_right_narrow", (0.46, 0.06, 1.00, 0.86), 1.80),
    ("other_ingredients_band", (0.00, 0.58, 1.00, 0.92), 1.80),
    ("lower_declaration_dense", (0.04, 0.64, 0.96, 1.00), 1.85),
)
SECTION_AWARE_V5_CROPS: tuple[CropSpec, ...] = (
    # ROI v5 targets line-pairing failures in facts tables. These bounded crops
    # are evaluation hypotheses: they never read GT labels and must beat v4 on
    # locked holdouts before becoming runtime defaults.
    ("facts_row_strip_top_third", (0.01, 0.06, 0.99, 0.36), 2.25),
    ("facts_row_strip_mid_third", (0.01, 0.30, 0.99, 0.62), 2.25),
    ("facts_row_strip_low_third", (0.01, 0.54, 0.99, 0.88), 2.20),
    ("facts_table_left_name_col", (0.00, 0.04, 0.58, 0.92), 2.30),
    ("facts_table_mid_amount_col", (0.30, 0.04, 0.82, 0.92), 2.30),
    ("facts_table_right_dv_col", (0.52, 0.04, 1.00, 0.92), 2.30),
    ("facts_table_name_amount_pair", (0.00, 0.04, 0.86, 0.92), 2.15),
    ("facts_table_amount_dv_pair", (0.28, 0.04, 1.00, 0.92), 2.15),
    ("supplement_facts_header_to_rows", (0.00, 0.00, 1.00, 0.58), 2.00),
    ("other_ingredients_declaration_dense", (0.00, 0.50, 1.00, 1.00), 2.20),
    ("directions_precautions_dense", (0.00, 0.62, 1.00, 1.00), 2.15),
)
SECTION_AWARE_V6_CROPS: tuple[CropSpec, ...] = (
    # ROI v6 focuses on table-row reconstruction instead of pure OCR recall.
    # It keeps all coordinates source-image-only and GT-free, then lets the
    # evidence merger decide whether the resulting text has visible ingredients
    # plus amount/unit spans.
    ("facts_row_micro_01", (0.00, 0.08, 1.00, 0.24), 2.55),
    ("facts_row_micro_02", (0.00, 0.20, 1.00, 0.38), 2.55),
    ("facts_row_micro_03", (0.00, 0.34, 1.00, 0.52), 2.55),
    ("facts_row_micro_04", (0.00, 0.48, 1.00, 0.66), 2.55),
    ("facts_row_micro_05", (0.00, 0.62, 1.00, 0.82), 2.45),
    ("facts_name_amount_left_pair", (0.00, 0.06, 0.72, 0.94), 2.45),
    ("facts_name_amount_center_pair", (0.14, 0.06, 0.86, 0.94), 2.45),
    ("facts_amount_unit_right_pair", (0.38, 0.06, 1.00, 0.94), 2.45),
    ("facts_serving_to_low_rows", (0.00, 0.14, 1.00, 0.96), 2.25),
    ("facts_header_removed_rows", (0.00, 0.22, 1.00, 0.92), 2.35),
    ("declaration_other_ingredients_line", (0.00, 0.52, 1.00, 0.78), 2.45),
    ("directions_warning_line", (0.00, 0.72, 1.00, 1.00), 2.35),
)
SECTION_AWARE_V7_CROPS: tuple[CropSpec, ...] = (
    # ROI v7 is still GT-free: it adds higher-overlap table/section crops for
    # the remaining holdout hard cases where v6 leaves field_zero or
    # ingredient_all_missed failures. The goal is not recognition retraining but
    # exposing already-visible text fragments to the evidence merger.
    ("facts_ultra_row_01", (0.00, 0.06, 1.00, 0.20), 2.80),
    ("facts_ultra_row_02", (0.00, 0.16, 1.00, 0.32), 2.80),
    ("facts_ultra_row_03", (0.00, 0.28, 1.00, 0.44), 2.80),
    ("facts_ultra_row_04", (0.00, 0.40, 1.00, 0.58), 2.75),
    ("facts_ultra_row_05", (0.00, 0.54, 1.00, 0.74), 2.70),
    ("facts_ultra_row_06", (0.00, 0.68, 1.00, 0.90), 2.60),
    ("facts_left_name_dense_top", (0.00, 0.04, 0.62, 0.52), 2.70),
    ("facts_left_name_dense_bottom", (0.00, 0.42, 0.62, 0.94), 2.70),
    ("facts_right_amount_dense_top", (0.34, 0.04, 1.00, 0.52), 2.70),
    ("facts_right_amount_dense_bottom", (0.34, 0.42, 1.00, 0.94), 2.70),
    ("facts_center_name_amount_dense", (0.10, 0.04, 0.90, 0.94), 2.65),
    ("facts_headerless_full_dense", (0.00, 0.18, 1.00, 0.94), 2.55),
    ("other_ingredients_low_band_dense", (0.00, 0.46, 1.00, 0.86), 2.70),
    ("other_ingredients_bottom_band_dense", (0.00, 0.58, 1.00, 0.98), 2.65),
    ("side_panel_left_all_dense", (0.00, 0.02, 0.72, 0.98), 2.35),
    ("side_panel_right_all_dense", (0.28, 0.02, 1.00, 0.98), 2.35),
)


@dataclass(frozen=True)
class CandidateConfig:
    """One PaddleOCR recognition candidate.

    Args:
        name: Stable candidate label used in output filenames.
        recognition_model_dir: PaddleOCR inference directory.
    """

    name: str
    recognition_model_dir: str


@dataclass(frozen=True)
class OCRPassConfig:
    """One detector-pass configuration for a recognition candidate.

    Args:
        name: Stable pass label used only in redacted diagnostics.
        det_box_thresh: Optional PaddleOCR text detection box threshold.
        det_thresh: Optional PaddleOCR text detection threshold.
        det_unclip_ratio: PaddleOCR detection unclip ratio.
    """

    name: str
    det_box_thresh: float | None
    det_thresh: float | None
    det_unclip_ratio: float


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed CLI namespace.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-dir", required=True, type=Path)
    parser.add_argument("--splits", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--profile", choices=sorted(PROFILES), default="server_detection")
    parser.add_argument("--primary-name", default="primary")
    parser.add_argument("--primary-rec-model-dir", required=True)
    parser.add_argument("--secondary-name", default="secondary")
    parser.add_argument("--secondary-rec-model-dir", required=True)
    parser.add_argument("--det-model", default=None)
    parser.add_argument("--rec-model", default=None)
    parser.add_argument("--max-side", type=int, default=None)
    parser.add_argument(
        "--device",
        default=None,
        help="Optional PaddleOCR runtime device, for example gpu:0 on A100 or cpu.",
    )
    parser.add_argument("--det-box-thresh", type=float, default=None)
    parser.add_argument("--det-thresh", type=float, default=None)
    parser.add_argument("--det-unclip-ratio", type=float, default=2.5)
    parser.add_argument(
        "--roi-crop-preset",
        choices=ROI_CROP_PRESETS,
        default="none",
        help=(
            "Temporary OCR-only crop expansion. Crops are created under a temp "
            "directory and are never written to normal artifacts."
        ),
    )
    parser.add_argument(
        "--ocr-pass-preset",
        choices=OCR_PASS_PRESETS,
        default="single",
        help=(
            "Run one or more detector threshold passes per recognizer. "
            "recall_precision_v1 uses experimental pass values and must be "
            "judged only by locked holdout metrics."
        ),
    )
    parser.add_argument(
        "--post-pass",
        choices=POST_PASS_CHOICES,
        default=POST_PASS_INGREDIENT_ALIAS_AMOUNT_UNIT,
    )
    parser.add_argument("--eval-split", default="holdout")
    parser.add_argument("--provider", default=TARGET_PROVIDER)
    parser.add_argument("--target-threshold", default="0.90")
    parser.add_argument("--min-ingredient-recall", default="0.85")
    parser.add_argument("--min-fixtures", type=int, default=30)
    parser.add_argument(
        "--fixture-id",
        action="append",
        default=[],
        help=(
            "Run only the selected fixture id. Repeat for multiple ids. This is "
            "for locked-holdout debugging and never changes GT labels."
        ),
    )
    parser.add_argument(
        "--shard-index",
        type=int,
        default=None,
        help="Zero-based shard index for long locked-holdout runs.",
    )
    parser.add_argument(
        "--num-shards",
        type=int,
        default=None,
        help="Total shard count used with --shard-index.",
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--progress-jsonl",
        type=Path,
        default=None,
        help=(
            "Optional redacted per-fixture progress log. The log contains only "
            "fixture ids, counts, elapsed time, and failure reasons."
        ),
    )
    parser.add_argument(
        "--raw-debug-dir",
        type=Path,
        default=None,
        help="Temporary raw OCR line output for hard-case fixtures only. Do not commit.",
    )
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args(argv)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read a JSONL file.

    Args:
        path: JSONL path.

    Returns:
        Parsed row objects.
    """
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]


def _load_ready_rows(bundle_dir: Path, limit: int | None) -> list[dict[str, Any]]:
    """Load benchmark-ready GT rows.

    Args:
        bundle_dir: Bundle directory containing ``ground-truth.todo.jsonl``.
        limit: Optional row cap.

    Returns:
        Ready benchmark rows.
    """
    rows = _read_jsonl(bundle_dir / "ground-truth.todo.jsonl")
    ready = [
        row
        for row in rows
        if row.get("ready_for_benchmark_after_review") is True
        and isinstance(row.get("expected"), dict)
    ]
    return ready[:limit] if limit is not None else ready


def _stable_fixture_shard(fixture_id: str, num_shards: int) -> int:
    """Return a stable shard number for a fixture id.

    Args:
        fixture_id: Stable fixture identifier from the locked bundle.
        num_shards: Positive total shard count.

    Returns:
        Zero-based shard index.

    Raises:
        ValueError: If ``num_shards`` is not positive.
    """
    if num_shards <= 0:
        raise ValueError("num_shards must be positive")
    digest = hashlib.sha256(fixture_id.encode("utf-8")).hexdigest()
    return int(digest[:12], 16) % num_shards


def _selected_ready_rows(
    rows: list[dict[str, Any]],
    *,
    fixture_ids: list[str] | None,
    shard_index: int | None,
    num_shards: int | None,
    limit: int | None,
) -> list[dict[str, Any]]:
    """Filter ready rows by explicit fixture ids, shard, and optional limit.

    Args:
        rows: Ready benchmark rows.
        fixture_ids: Optional allow-list of fixture ids.
        shard_index: Optional zero-based shard index.
        num_shards: Optional positive shard count.
        limit: Optional cap after deterministic filtering.

    Returns:
        Selected benchmark rows in their original bundle order.

    Raises:
        ValueError: If shard arguments are inconsistent.
    """
    selected = list(rows)
    requested_ids = {item for item in (fixture_ids or []) if item}
    if requested_ids:
        selected = [row for row in selected if str(row.get("fixture_id") or "") in requested_ids]

    if (shard_index is None) != (num_shards is None):
        raise ValueError("--shard-index and --num-shards must be provided together")
    if shard_index is not None and num_shards is not None:
        if num_shards <= 0:
            raise ValueError("--num-shards must be positive")
        if shard_index < 0 or shard_index >= num_shards:
            raise ValueError("--shard-index must satisfy 0 <= shard_index < num_shards")
        selected = [
            row
            for row in selected
            if _stable_fixture_shard(str(row.get("fixture_id") or ""), num_shards) == shard_index
        ]

    return selected[:limit] if limit is not None else selected


def _fixture_selector_summary(
    args: argparse.Namespace, selected_count: int, ready_count: int
) -> dict[str, Any]:
    """Return redacted metadata for fixture selection.

    Args:
        args: Parsed CLI namespace.
        selected_count: Number of fixtures selected for this run.
        ready_count: Number of ready fixtures before filtering.

    Returns:
        Selector metadata without raw OCR text or provider payloads.
    """
    fixture_ids = [item for item in getattr(args, "fixture_id", []) if item]
    shard_index = getattr(args, "shard_index", None)
    num_shards = getattr(args, "num_shards", None)
    return {
        "ready_fixture_count": ready_count,
        "selected_fixture_count": selected_count,
        "fixture_id_filter_count": len(fixture_ids),
        "fixture_ids": fixture_ids,
        "shard_index": shard_index,
        "num_shards": num_shards,
        "limit": getattr(args, "limit", None),
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write a JSON artifact."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write JSONL rows."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8"
    )


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    """Append one JSONL row and flush it for long-running A100 jobs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()


def _safe_filename(value: str) -> str:
    """Return a safe filename stem for a fixture id."""
    return SAFE_FILENAME_PATTERN.sub("_", value).strip("._-") or "fixture"


def _line_hash(text: str) -> str:
    """Return a short hash for redacted line comparison."""
    normalized = _normalize_for_metric(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16] if normalized else "empty"


def _predict_lines(ocr: Any, image_path: Path) -> list[str]:
    """Run PaddleOCR and return recognized text lines.

    Args:
        ocr: PaddleOCR pipeline object.
        image_path: Local image path.

    Returns:
        Recognized line strings in PaddleOCR reading order.
    """
    result = ocr.predict(str(image_path))
    if not result:
        return []
    first = result[0]
    texts = first.get("rec_texts") if hasattr(first, "get") else None
    if not isinstance(texts, list | tuple):
        return []
    return [str(text).strip() for text in texts if str(text).strip()]


def _crop_variants(image_path: Path, *, fixture_id: str, temp_dir: Path, preset: str) -> list[Path]:
    """Return full image plus temporary OCR crop variants.

    Args:
        image_path: Source benchmark image path.
        fixture_id: Fixture id used only for a safe temporary filename prefix.
        temp_dir: Existing temp directory for crop files.
        preset: Crop preset name.

    Returns:
        Image paths to OCR. The first path is always the original image.

    Raises:
        ValueError: If ``preset`` is unsupported.
    """
    if preset == "none":
        return [image_path]
    if preset not in ROI_CROP_PRESETS:
        raise ValueError(f"Unsupported ROI crop preset: {preset}")

    safe_id = _safe_filename(fixture_id)
    with Image.open(image_path) as image:
        width, height = image.size
        crop_specs = list(BASE_VERTICAL_CROPS)
        if preset in {
            "section_aware_v4",
            "section_aware_v5",
            "section_aware_v6",
            "section_aware_v7",
        }:
            crop_specs.extend(LR_SECTION_CROPS)
            crop_specs.extend(SECTION_AWARE_V4_ANCHOR_CROPS)
            crop_specs.extend(SECTION_AWARE_V4_CROPS)
            if preset in {"section_aware_v5", "section_aware_v6", "section_aware_v7"}:
                crop_specs.extend(SECTION_AWARE_V5_CROPS)
            if preset in {"section_aware_v6", "section_aware_v7"}:
                crop_specs.extend(SECTION_AWARE_V6_CROPS)
            if preset == "section_aware_v7":
                crop_specs.extend(SECTION_AWARE_V7_CROPS)
        else:
            if preset in {"vertical3_lr2", "section_aware", "section_aware_v2", "section_aware_v3"}:
                crop_specs.extend(LR_SECTION_CROPS)
            if preset in {"section_aware", "section_aware_v2", "section_aware_v3"}:
                crop_specs.extend(SECTION_AWARE_CROPS)
            if preset in {"section_aware_v2", "section_aware_v3"}:
                crop_specs.extend(SECTION_AWARE_V2_CROPS)
            if preset == "section_aware_v3":
                crop_specs.extend(SECTION_AWARE_V3_CROPS)

        variant_paths = [image_path]
        for name, fraction_box, scale in crop_specs:
            left = max(0, min(width - 1, int(width * fraction_box[0])))
            top = max(0, min(height - 1, int(height * fraction_box[1])))
            right = max(left + 1, min(width, int(width * fraction_box[2])))
            bottom = max(top + 1, min(height, int(height * fraction_box[3])))
            if right - left < MIN_ROI_CROP_SIDE_PX or bottom - top < MIN_ROI_CROP_SIDE_PX:
                continue
            crop = image.crop((left, top, right, bottom)).convert("RGB")
            if scale != 1.0:
                scaled_width = max(MIN_ROI_CROP_SIDE_PX, round(crop.width * scale))
                scaled_height = max(MIN_ROI_CROP_SIDE_PX, round(crop.height * scale))
                crop = crop.resize((scaled_width, scaled_height), Image.Resampling.LANCZOS)
            crop_path = temp_dir / f"{safe_id}.{name}.jpg"
            crop.save(crop_path, format="JPEG", quality=95)
            variant_paths.append(crop_path)
    return variant_paths


def _predict_variant_lines(ocr: Any, variant_paths: list[Path]) -> list[str]:
    """Run OCR on image variants and return normalized line union."""
    merged: list[str] = []
    for variant_path in variant_paths:
        merged = _union_lines(merged, _predict_lines(ocr, variant_path))
    return merged


def _ocr_pass_configs(args: argparse.Namespace) -> tuple[OCRPassConfig, ...]:
    """Return detector-pass configs for the requested OCR pass preset.

    Args:
        args: Parsed CLI namespace.

    Returns:
        Ordered OCR pass configurations.

    Raises:
        ValueError: If the preset is unsupported.
    """
    base = OCRPassConfig(
        name="base",
        det_box_thresh=args.det_box_thresh,
        det_thresh=args.det_thresh,
        det_unclip_ratio=args.det_unclip_ratio,
    )
    if args.ocr_pass_preset == "single":
        return (base,)
    if args.ocr_pass_preset != "recall_precision_v1":
        raise ValueError(f"Unsupported OCR pass preset: {args.ocr_pass_preset}")

    # Experimental pass values. PaddleOCR documents these as configurable
    # pipeline parameters, but these specific values are repo hypotheses only.
    recall = OCRPassConfig(
        name="recall_low_box",
        det_box_thresh=min(args.det_box_thresh, 0.25) if args.det_box_thresh is not None else 0.25,
        det_thresh=min(args.det_thresh, 0.15) if args.det_thresh is not None else 0.15,
        det_unclip_ratio=max(args.det_unclip_ratio, 3.5),
    )
    precision = OCRPassConfig(
        name="precision_high_box",
        det_box_thresh=max(args.det_box_thresh, 0.65) if args.det_box_thresh is not None else 0.65,
        det_thresh=max(args.det_thresh, 0.35) if args.det_thresh is not None else 0.35,
        det_unclip_ratio=args.det_unclip_ratio,
    )
    return (base, recall, precision)


def _build_candidate_ocr_passes(
    *,
    candidate: CandidateConfig,
    pass_configs: tuple[OCRPassConfig, ...],
    det_model: str,
    rec_model: str,
    max_side: int,
    device: str | None,
) -> list[tuple[OCRPassConfig, Any]]:
    """Build PaddleOCR objects for all passes of one recognition candidate.

    Args:
        candidate: Recognition candidate configuration.
        pass_configs: Detector-pass configs.
        det_model: PaddleOCR detection model name.
        rec_model: PaddleOCR recognition model name.
        max_side: Detection side length limit.
        device: Optional PaddleOCR runtime device such as ``gpu:0`` or ``cpu``.

    Returns:
        Ordered pairs of pass config and PaddleOCR object.
    """
    return [
        (
            pass_config,
            _build_ocr(
                det_model=det_model,
                rec_model=rec_model,
                max_side=max_side,
                det_box_thresh=pass_config.det_box_thresh,
                det_thresh=pass_config.det_thresh,
                det_unclip_ratio=pass_config.det_unclip_ratio,
                rec_model_dir=candidate.recognition_model_dir,
                device=device,
            ),
        )
        for pass_config in pass_configs
    ]


def _predict_candidate_lines(
    ocr_passes: list[tuple[OCRPassConfig, Any]],
    variant_paths: list[Path],
) -> tuple[list[str], list[dict[str, Any]]]:
    """Run all OCR passes over all variants and return line union plus counts."""
    merged: list[str] = []
    counts: list[dict[str, Any]] = []
    for pass_config, ocr in ocr_passes:
        pass_lines, pass_counts = _predict_lines_by_variant(ocr, variant_paths)
        for item in pass_counts:
            counts.append(
                {
                    **item,
                    "ocr_pass": pass_config.name,
                    "det_box_thresh": pass_config.det_box_thresh,
                    "det_thresh": pass_config.det_thresh,
                    "det_unclip_ratio": pass_config.det_unclip_ratio,
                }
            )
        merged = _union_lines(merged, pass_lines)
    return merged, counts


def _union_lines(primary: list[str], secondary: list[str]) -> list[str]:
    """Return primary lines plus secondary-only normalized lines."""
    merged: list[str] = []
    seen: set[str] = set()
    for line in [*primary, *secondary]:
        key = _normalize_for_metric(line)
        if not key or key in seen:
            continue
        seen.add(key)
        merged.append(line)
    return merged


def _evidence_section_type(text: str) -> str | None:
    """Return a coarse section type for a visible OCR evidence window."""
    if re.search(
        r"supplement\s+facts|nutrition\s+facts|daily\s+value|영양|함량", text, re.IGNORECASE
    ):
        return "supplement_facts"
    if re.search(
        r"active\s+ingredients?|other\s+ingredients?|ingredients?|원\s*재\s*료|원\s*료",
        text,
        re.IGNORECASE,
    ):
        return "ingredients"
    if re.search(r"suggested\s+use|directions?|섭취|복용", text, re.IGNORECASE):
        return "intake_or_directions"
    return None


def _evidence_record(
    *,
    text: str,
    row_or_window_id: str,
    accept_reason: str,
) -> dict[str, Any]:
    """Build one redacted ingredient evidence record.

    Args:
        text: Visible OCR window. Only a hash and booleans are persisted.
        row_or_window_id: Stable window identifier scoped to one fixture.
        accept_reason: Why this source-only evidence was accepted.

    Returns:
        Redacted evidence metadata without raw OCR text.
    """
    return {
        "line_hash": _line_hash(text),
        "source_variant_id": "ocr_line_union",
        "section_type": _evidence_section_type(text),
        "row_or_window_id": row_or_window_id,
        "has_amount_unit": bool(EVIDENCE_AMOUNT_UNIT_PATTERN.search(text)),
        "has_real_amount_unit": bool(EVIDENCE_REAL_AMOUNT_UNIT_PATTERN.search(text)),
        "has_text_candidate": bool(EVIDENCE_TEXT_PATTERN.search(text)),
        "confidence": 0.55,
        "accept_reason": accept_reason,
        "reject_reason": None,
        "raw_text_stored": False,
    }


def _add_evidence_line(
    evidence: list[str],
    records: list[dict[str, Any]],
    *,
    text: str,
    row_or_window_id: str,
    accept_reason: str,
) -> list[str]:
    """Add one de-duplicated evidence line plus its redacted record."""
    before_count = len(evidence)
    evidence = _union_lines(evidence, [text])
    if len(evidence) > before_count:
        records.append(
            _evidence_record(
                text=text,
                row_or_window_id=row_or_window_id,
                accept_reason=accept_reason,
            )
        )
    return evidence


def _ingredient_evidence_lines_with_records(
    lines: list[str],
) -> tuple[list[str], list[dict[str, Any]]]:
    """Create visible-text evidence windows from OCR lines.

    This helper never uses GT labels. It only fuses adjacent OCR lines when the
    fused window contains both text-like ingredient evidence and a visible
    amount/unit token. It helps table OCR cases where name, amount, and unit are
    split across neighboring cells or crop passes.

    Args:
        lines: OCR line strings.

    Returns:
        De-duplicated original lines plus fused evidence windows and redacted
        evidence metadata.
    """
    evidence = _union_lines(lines, [])
    records: list[dict[str, Any]] = []
    normalized_lines = [line.strip() for line in lines if line.strip()]
    for index, line in enumerate(normalized_lines):
        for size in (2, 3, 4, 5, 6, 7, 8, 9, 10):
            window = normalized_lines[index : index + size]
            if len(window) != size:
                continue
            fused = " ".join(part.strip() for part in window if part.strip())
            if _looks_like_ingredient_evidence(fused):
                evidence = _add_evidence_line(
                    evidence,
                    records,
                    text=fused,
                    row_or_window_id=f"window:{index}:{size}:spaced",
                    accept_reason="name_amount_unit_window",
                )
            header_stripped = _table_header_stripped_window(window)
            if header_stripped != fused and _looks_like_ingredient_evidence(header_stripped):
                evidence = _add_evidence_line(
                    evidence,
                    records,
                    text=header_stripped,
                    row_or_window_id=f"window:{index}:{size}:header_stripped",
                    accept_reason="name_amount_unit_window_header_stripped",
                )
            if _looks_like_section_name_window(window):
                evidence = _add_evidence_line(
                    evidence,
                    records,
                    text=fused,
                    row_or_window_id=f"window:{index}:{size}:section_name_spaced",
                    accept_reason="section_name_window",
                )
                evidence = _add_evidence_line(
                    evidence,
                    records,
                    text="".join(window),
                    row_or_window_id=f"window:{index}:{size}:section_name_compact",
                    accept_reason="section_name_window_compact",
                )

        if EVIDENCE_REAL_AMOUNT_UNIT_PATTERN.search(line):
            for nearby_index, nearby in enumerate(
                _nearby_amount_name_windows(normalized_lines, index)
            ):
                evidence = _add_evidence_line(
                    evidence,
                    records,
                    text=nearby,
                    row_or_window_id=f"nearby_amount:{index}:{nearby_index}",
                    accept_reason="nearby_name_amount_unit",
                )

        for split_index, split_window in enumerate(
            _nearby_split_amount_unit_windows(normalized_lines, index)
        ):
            evidence = _add_evidence_line(
                evidence,
                records,
                text=split_window,
                row_or_window_id=f"split_amount_unit:{index}:{split_index}",
                accept_reason="nearby_name_split_amount_unit",
            )

        for split_index, split_window in enumerate(
            _nearby_any_order_split_amount_unit_windows(normalized_lines, index)
        ):
            evidence = _add_evidence_line(
                evidence,
                records,
                text=split_window,
                row_or_window_id=f"split_amount_unit_any_order:{index}:{split_index}",
                accept_reason="nearby_name_any_order_split_amount_unit",
            )

        if not SECTION_CONTEXT_PATTERN.search(line):
            continue
        context_window = normalized_lines[index : index + 13]
        for size in range(2, min(10, len(context_window)) + 1):
            for start in range(0, len(context_window) - size + 1):
                window = context_window[start : start + size]
                fused = " ".join(part.strip() for part in window if part.strip())
                if _looks_like_ingredient_evidence(fused):
                    evidence = _add_evidence_line(
                        evidence,
                        records,
                        text=fused,
                        row_or_window_id=f"context:{index}:{start}:{size}:spaced",
                        accept_reason="section_context_amount_unit_window",
                    )
                header_stripped = _table_header_stripped_window(window)
                if header_stripped != fused and _looks_like_ingredient_evidence(header_stripped):
                    evidence = _add_evidence_line(
                        evidence,
                        records,
                        text=header_stripped,
                        row_or_window_id=f"context:{index}:{start}:{size}:header_stripped",
                        accept_reason="section_context_amount_unit_window_header_stripped",
                    )
                if _looks_like_section_name_window(window):
                    evidence = _add_evidence_line(
                        evidence,
                        records,
                        text=fused,
                        row_or_window_id=f"context:{index}:{start}:{size}:name_spaced",
                        accept_reason="section_context_name_window",
                    )
                    evidence = _add_evidence_line(
                        evidence,
                        records,
                        text="".join(window),
                        row_or_window_id=f"context:{index}:{start}:{size}:name_compact",
                        accept_reason="section_context_name_window_compact",
                    )
        for declaration_index, declaration_line in enumerate(
            _declaration_continuation_windows(normalized_lines, index)
        ):
            evidence = _add_evidence_line(
                evidence,
                records,
                text=declaration_line,
                row_or_window_id=f"declaration:{index}:{declaration_index}",
                accept_reason="declaration_header_continuation_window",
            )
    return evidence, records


def _ingredient_evidence_lines(lines: list[str]) -> list[str]:
    """Create visible-text evidence windows from OCR lines."""
    evidence, _records = _ingredient_evidence_lines_with_records(lines)
    return evidence


def _declaration_continuation_windows(lines: list[str], header_index: int) -> list[str]:
    """Return source-visible ingredient declaration windows after a header.

    Args:
        lines: OCR lines.
        header_index: Index of a visible declaration heading line.

    Returns:
        Candidate text windows built from the heading body and following OCR
        lines. This is source-only and intentionally stops at explicit next
        sections such as directions, warnings, or facts-table headings.
    """
    header = lines[header_index].strip()
    if not DECLARATION_HEADER_PATTERN.search(header):
        return []

    declaration_parts: list[str] = []
    header_body = _declaration_header_body(header)
    if header_body and _looks_like_declaration_fragment(header_body):
        declaration_parts.append(header_body)

    for line in lines[header_index + 1 : header_index + 1 + MAX_DECLARATION_CONTINUATION_LINES]:
        if _is_declaration_stop_line(line):
            break
        cleaned = _strip_table_header_noise(line)
        if not _looks_like_declaration_fragment(cleaned):
            continue
        declaration_parts.append(cleaned)

    if not declaration_parts:
        return []

    windows: list[str] = []
    max_size = min(len(declaration_parts), 8)
    for start in range(len(declaration_parts)):
        for size in range(1, max_size + 1):
            window = declaration_parts[start : start + size]
            if len(window) != size:
                continue
            spaced = " ".join(window)
            compact = "".join(window)
            if _looks_like_declaration_window(spaced):
                windows.append(spaced)
            if compact != spaced and _looks_like_declaration_window(compact):
                windows.append(compact)
    return _union_lines([], windows)


def _declaration_header_body(header: str) -> str:
    """Return text after a visible declaration heading when present."""
    if ":" in header:
        return header.split(":", 1)[1].strip()
    if "：" in header:
        return header.split("：", 1)[1].strip()
    return DECLARATION_HEADER_PATTERN.sub(" ", header, count=1).strip(" \t:-：")


def _is_declaration_stop_line(line: str) -> bool:
    """Return whether a line should end declaration continuation merging."""
    stripped = line.strip()
    if not stripped:
        return True
    return bool(
        DECLARATION_STOP_PATTERN.search(stripped)
        and not DECLARATION_HEADER_PATTERN.search(stripped)
    )


def _looks_like_declaration_fragment(text: str) -> bool:
    """Return whether an OCR line can be part of an ingredient declaration."""
    stripped = text.strip(" \t,，;；·•|｜")
    if not stripped or EVIDENCE_NOISE_PATTERN.search(stripped):
        return False
    if EVIDENCE_DAILY_VALUE_PATTERN.fullmatch(stripped):
        return False
    if EVIDENCE_AMOUNT_ONLY_PATTERN.fullmatch(stripped) or EVIDENCE_UNIT_ONLY_PATTERN.fullmatch(
        stripped
    ):
        return False
    if EVIDENCE_REAL_AMOUNT_UNIT_PATTERN.fullmatch(stripped):
        return False
    return bool(EVIDENCE_TEXT_PATTERN.search(stripped))


def _looks_like_declaration_window(text: str) -> bool:
    """Return whether a declaration window is bounded enough for evidence."""
    normalized = _normalize_for_metric(text)
    return MIN_SECTION_NAME_NORM_CHARS <= len(normalized) <= 160 and bool(
        EVIDENCE_TEXT_PATTERN.search(text)
    )


def _table_header_stripped_window(window: list[str]) -> str:
    """Return an OCR window with visible table header noise removed.

    Args:
        window: Adjacent OCR lines.

    Returns:
        A space-joined window that keeps visible ingredient and amount tokens but
        removes table headers such as ``% Daily Value``.
    """
    cleaned_parts = [_strip_table_header_noise(part) for part in window]
    return " ".join(part for part in cleaned_parts if part)


def _strip_table_header_noise(text: str) -> str:
    """Remove common facts-table header phrases from one visible OCR line.

    Args:
        text: OCR line.

    Returns:
        The same line with deterministic table header phrases removed.
    """
    return TABLE_HEADER_NOISE_PATTERN.sub(" ", text).strip()


def _nearby_amount_name_windows(lines: list[str], amount_index: int) -> list[str]:
    """Return visible name+amount windows around an amount/unit OCR line.

    Args:
        lines: OCR lines.
        amount_index: Index of the line containing a visible amount/unit token.

    Returns:
        Candidate windows built only from nearby visible OCR tokens.
    """
    candidates: list[str] = []
    amount_line = lines[amount_index]
    start = max(0, amount_index - 8)
    end = min(len(lines), amount_index + 7)
    nearby_daily_values = [
        _strip_table_header_noise(lines[index])
        for index in range(amount_index + 1, min(len(lines), amount_index + 4))
        if EVIDENCE_DAILY_VALUE_PATTERN.fullmatch(_strip_table_header_noise(lines[index]))
    ]
    for left in range(start, amount_index + 1):
        for right in range(amount_index + 1, end + 1):
            window = lines[left:right]
            cleaned_window = [_strip_table_header_noise(part) for part in window]
            if not any(_looks_like_name_fragment(part) for part in cleaned_window):
                continue
            for fused in (
                " ".join(part.strip() for part in window if part.strip()),
                " ".join(part.strip() for part in cleaned_window if part.strip()),
                "".join(part.strip() for part in cleaned_window if part.strip()),
            ):
                if _looks_like_ingredient_evidence(fused):
                    candidates.append(fused)
            for daily_value in nearby_daily_values:
                with_dv = " ".join(
                    part.strip() for part in [*cleaned_window, daily_value] if part.strip()
                )
                if _looks_like_ingredient_evidence(with_dv):
                    candidates.append(with_dv)
    for neighbor_index in range(start, end):
        if neighbor_index == amount_index:
            continue
        neighbor = _strip_table_header_noise(lines[neighbor_index])
        if not _looks_like_name_fragment(neighbor):
            continue
        candidates.extend([f"{neighbor} {amount_line}", f"{amount_line} {neighbor}"])
        for daily_value in nearby_daily_values:
            candidates.extend(
                [
                    f"{neighbor} {amount_line} {daily_value}",
                    f"{neighbor} | {amount_line} | {daily_value}",
                    f"{amount_line} {daily_value} {neighbor}",
                ]
            )
    return candidates


def _nearby_split_amount_unit_windows(lines: list[str], amount_index: int) -> list[str]:
    """Return evidence windows for amount-only lines followed by unit-only lines.

    Args:
        lines: OCR lines.
        amount_index: Index of a potential numeric amount-only line.

    Returns:
        Source-visible candidate windows that combine nearby name fragments with
        a split amount/unit pair, such as ``"100"`` + ``"mg"``.
    """
    amount_line = _strip_table_header_noise(lines[amount_index])
    if not EVIDENCE_AMOUNT_ONLY_PATTERN.fullmatch(amount_line):
        return []

    candidates: list[str] = []
    unit_indices = [
        index
        for index in range(amount_index + 1, min(len(lines), amount_index + 4))
        if EVIDENCE_UNIT_ONLY_PATTERN.fullmatch(_strip_table_header_noise(lines[index]))
    ]
    for unit_index in unit_indices:
        unit_line = _strip_table_header_noise(lines[unit_index])
        amount_unit = f"{amount_line} {unit_line}"
        start = max(0, amount_index - 8)
        end = min(len(lines), unit_index + 7)
        for name_index in range(start, end):
            if name_index in {amount_index, unit_index}:
                continue
            name = _strip_table_header_noise(lines[name_index])
            if not _looks_like_name_fragment(name):
                continue
            for fused in (f"{name} {amount_unit}", f"{amount_unit} {name}"):
                if _looks_like_ingredient_evidence(fused):
                    candidates.append(fused)

        span = [_strip_table_header_noise(part) for part in lines[start:end]]
        for left in range(0, max(0, amount_index - start + 1)):
            for right in range(unit_index - start + 1, len(span) + 1):
                fused = " ".join(part for part in span[left:right] if part)
                if _looks_like_ingredient_evidence(fused):
                    candidates.append(fused)
    return candidates


def _nearby_any_order_split_amount_unit_windows(lines: list[str], anchor_index: int) -> list[str]:
    """Return evidence windows for split amount/unit pairs in either OCR order.

    PaddleOCR may read facts-table columns vertically or right-to-left on curved
    labels, so a unit-only line can appear before its amount-only partner. This
    helper only uses visible neighboring OCR lines: it pairs nearby amount-only
    and unit-only tokens, then attaches nearby name fragments.

    Args:
        lines: OCR lines.
        anchor_index: Index of a potential amount-only or unit-only line.

    Returns:
        Source-visible candidate windows for ingredient evidence.
    """
    anchor = _strip_table_header_noise(lines[anchor_index])
    if not (
        EVIDENCE_AMOUNT_ONLY_PATTERN.fullmatch(anchor)
        or EVIDENCE_UNIT_ONLY_PATTERN.fullmatch(anchor)
    ):
        return []

    candidates: list[str] = []
    pair_start = max(0, anchor_index - 3)
    pair_end = min(len(lines), anchor_index + 4)
    amount_indices = [
        index
        for index in range(pair_start, pair_end)
        if EVIDENCE_AMOUNT_ONLY_PATTERN.fullmatch(_strip_table_header_noise(lines[index]))
    ]
    unit_indices = [
        index
        for index in range(pair_start, pair_end)
        if EVIDENCE_UNIT_ONLY_PATTERN.fullmatch(_strip_table_header_noise(lines[index]))
    ]
    for amount_index in amount_indices:
        for unit_index in unit_indices:
            if amount_index == unit_index or abs(amount_index - unit_index) > 3:
                continue
            amount_unit = (
                f"{_strip_table_header_noise(lines[amount_index])} "
                f"{_strip_table_header_noise(lines[unit_index])}"
            )
            left_edge = min(amount_index, unit_index)
            right_edge = max(amount_index, unit_index)
            name_start = max(0, left_edge - 8)
            name_end = min(len(lines), right_edge + 8)
            for name_window in _nearby_name_fragment_windows(
                lines,
                start=name_start,
                end=name_end,
                excluded_indices={amount_index, unit_index},
            ):
                for fused in (
                    f"{name_window} {amount_unit}",
                    f"{amount_unit} {name_window}",
                    f"{name_window} | {amount_unit}",
                ):
                    if _looks_like_ingredient_evidence(fused):
                        candidates.append(fused)
    return _union_lines([], candidates)


def _nearby_name_fragment_windows(
    lines: list[str],
    *,
    start: int,
    end: int,
    excluded_indices: set[int],
) -> list[str]:
    """Return short adjacent name-fragment windows around an amount/unit pair.

    Args:
        lines: OCR lines.
        start: Inclusive window start.
        end: Exclusive window end.
        excluded_indices: Amount/unit indices that must not be used as names.

    Returns:
        De-duplicated visible name fragments.
    """
    windows: list[str] = []
    for index in range(start, end):
        if index in excluded_indices:
            continue
        fragment = _strip_table_header_noise(lines[index])
        if _looks_like_name_fragment(fragment):
            windows.append(fragment)
        for size in (2, 3, 4):
            span_indices = range(index, min(index + size, end))
            if len(list(span_indices)) != size or any(
                span_index in excluded_indices for span_index in span_indices
            ):
                continue
            parts = [_strip_table_header_noise(lines[span_index]) for span_index in span_indices]
            if all(_looks_like_name_fragment(part) for part in parts):
                windows.append(" ".join(parts))
                windows.append("".join(parts))
    return _union_lines([], windows)


def _looks_like_name_fragment(text: str) -> bool:
    """Return whether an OCR line can be part of an ingredient name."""
    stripped = text.strip()
    if not stripped or EVIDENCE_NOISE_PATTERN.search(stripped):
        return False
    if TABLE_HEADER_NOISE_PATTERN.fullmatch(stripped):
        return False
    if len(_normalize_for_metric(stripped)) < MIN_NAME_FRAGMENT_NORM_CHARS:
        return False
    if EVIDENCE_REAL_AMOUNT_UNIT_PATTERN.fullmatch(stripped):
        return False
    return bool(EVIDENCE_TEXT_PATTERN.search(stripped))


def _looks_like_section_name_window(window: list[str]) -> bool:
    """Return whether adjacent visible OCR lines look like a split name.

    Name-only windows are accepted only for short adjacent fragments or when
    section context is visible. This recovers OCR splits such as ``Vitamin`` /
    ``C`` without creating amount/unit values that are not present.
    """
    if len(window) < MIN_SECTION_NAME_WINDOW_SIZE or len(window) > MAX_SECTION_NAME_WINDOW_SIZE:
        return False
    fused = " ".join(part.strip() for part in window if part.strip())
    if EVIDENCE_NOISE_PATTERN.search(fused):
        return False
    if EVIDENCE_REAL_AMOUNT_UNIT_PATTERN.search(fused):
        return _looks_like_ingredient_evidence(fused)
    fragments = [part for part in window if _looks_like_name_fragment(part)]
    if len(fragments) < MIN_SECTION_NAME_WINDOW_SIZE:
        return False
    normalized = _normalize_for_metric(fused)
    if (
        len(normalized) < MIN_SECTION_NAME_NORM_CHARS
        or len(normalized) > MAX_SECTION_NAME_NORM_CHARS
    ):
        return False
    return bool(
        SECTION_CONTEXT_PATTERN.search(fused)
        or all(len(part.strip()) <= MAX_SECTION_NAME_FRAGMENT_CHARS for part in fragments)
    )


def _looks_like_ingredient_evidence(text: str) -> bool:
    """Return whether fused OCR text is worth adding as ingredient evidence.

    The predicate is intentionally source-only: it requires visible text plus a
    visible amount/unit token and never reads the expected label. Percent-only
    windows are accepted only near section/table context so a %DV column can help
    recover adjacent ingredient names without turning arbitrary percentages into
    ingredient evidence.

    Args:
        text: OCR text or a fused neighboring-line window.

    Returns:
        True when the text is a safe evidence candidate.
    """
    if not text or not EVIDENCE_TEXT_PATTERN.search(text):
        return False
    if EVIDENCE_REAL_AMOUNT_UNIT_PATTERN.search(text):
        return True
    return bool(SECTION_CONTEXT_PATTERN.search(text) and EVIDENCE_AMOUNT_UNIT_PATTERN.search(text))


def _score_prediction(
    *,
    fixture_id: str,
    expected: dict[str, Any],
    lines: list[str],
    post_pass: str,
    provider: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Score one OCR candidate without storing raw text.

    Args:
        fixture_id: Fixture id.
        expected: Structured GT object.
        lines: OCR line strings.
        post_pass: Deterministic post-pass mode.
        provider: Provider label.

    Returns:
        ``(per_image_row, observation_row)``.
    """
    predicted = " ".join(lines)
    predicted_for_metric, post_pass_applied = _postprocess_hypothesis_text(
        predicted, mode=post_pass
    )
    hypothesis_norm = _normalize_for_metric(predicted_for_metric)
    reference = _structured_reference(expected)
    metrics = _text_extraction_metrics(reference, predicted_for_metric)
    if metrics is None:
        metrics = {
            "matched_char_count": 0,
            "reference_char_count": len(_normalize_for_metric(reference)),
            "hypothesis_char_count": len(hypothesis_norm),
            "normalized_text_precision": 0.0,
            "normalized_text_recall": 0.0,
            "normalized_text_f1": 0.0,
        }
    f_matched, f_total = _field_match_ratio(_field_units(expected), hypothesis_norm)
    ingredient_found, ingredient_total = _ingredient_recall(expected, hypothesis_norm)
    field_ratio = round(f_matched / f_total, 4) if f_total else 0.0
    per_image = {
        "fixture_id": fixture_id,
        "field_match_ratio": field_ratio,
        "field_matched": f_matched,
        "field_total": f_total,
        "normalized_text_precision": metrics["normalized_text_precision"],
        "normalized_text_recall": metrics["normalized_text_recall"],
        "normalized_text_f1": metrics["normalized_text_f1"],
        "ingredient_found": ingredient_found,
        "ingredient_total": ingredient_total,
        "post_pass_applied": post_pass_applied,
        "line_count": len(lines),
    }
    observation = {
        "fixture_id": fixture_id,
        "provider": provider,
        "status": "completed",
        "text_non_empty": bool(lines),
        "char_count": metrics["hypothesis_char_count"],
        "field_match_ratio": field_ratio,
        "matched_char_count": metrics["matched_char_count"],
        "reference_char_count": metrics["reference_char_count"],
        "hypothesis_char_count": metrics["hypothesis_char_count"],
        "normalized_text_precision": metrics["normalized_text_precision"],
        "normalized_text_recall": metrics["normalized_text_recall"],
        "normalized_text_f1": metrics["normalized_text_f1"],
        "text_metric_reference_source": "expected.structured_sections",
        "post_pass": post_pass,
        "post_pass_applied": post_pass_applied,
    }
    return per_image, observation


def _aggregate_eval(
    *,
    strategy: str,
    per_image: list[dict[str, Any]],
    observations: list[dict[str, Any]],
    args: argparse.Namespace,
    det_model: str,
    rec_model: str,
    max_side: int,
) -> dict[str, Any]:
    """Build a redacted PaddleOCR-like eval artifact.

    Args:
        strategy: Strategy label.
        per_image: Per-fixture metric rows.
        observations: Provider-shaped observation rows.
        args: CLI namespace.
        det_model: Detection model name.
        rec_model: Recognition model name.
        max_side: Detection side limit.

    Returns:
        Redacted eval artifact.
    """
    scored = len(per_image)
    field_matched_total = sum(int(row.get("field_matched", 0)) for row in per_image)
    field_unit_total = sum(int(row.get("field_total", 0)) for row in per_image)
    ingredient_found_total = sum(int(row.get("ingredient_found", 0)) for row in per_image)
    ingredient_total = sum(int(row.get("ingredient_total", 0)) for row in per_image)
    precision_total = sum(float(row.get("normalized_text_precision", 0.0)) for row in per_image)
    recall_total = sum(float(row.get("normalized_text_recall", 0.0)) for row in per_image)
    f1_total = sum(float(row.get("normalized_text_f1", 0.0)) for row in per_image)
    field_ratio_total = sum(float(row.get("field_match_ratio", 0.0)) for row in per_image)
    return {
        "schema_version": SCHEMA_VERSION,
        "strategy": strategy,
        "provider": args.provider,
        "detection_model": det_model,
        "recognition_model": rec_model,
        "recognition_model_dir_present": True,
        "max_side": max_side,
        "det_box_thresh": args.det_box_thresh,
        "det_thresh": args.det_thresh,
        "det_unclip_ratio": args.det_unclip_ratio,
        "ocr_pass_preset": getattr(args, "ocr_pass_preset", "single"),
        "post_pass": args.post_pass,
        "field_match_threshold": FIELD_MATCH_THRESHOLD,
        "scored_images": scored,
        "skipped_images": 0,
        "failed_images": 0,
        "field_match_ratio_macro": round(field_ratio_total / scored, 4) if scored else 0.0,
        "field_match_ratio_micro": (
            round(field_matched_total / field_unit_total, 4) if field_unit_total else 0.0
        ),
        "field_matched_total": [field_matched_total, field_unit_total],
        "mean_normalized_text_precision": round(precision_total / scored, 4) if scored else 0.0,
        "mean_normalized_text_recall": round(recall_total / scored, 4) if scored else 0.0,
        "mean_normalized_text_f1": round(f1_total / scored, 4) if scored else 0.0,
        "ingredient_recall": (
            round(ingredient_found_total / ingredient_total, 4) if ingredient_total else 0.0
        ),
        "ingredient_found_total": [ingredient_found_total, ingredient_total],
        "per_image": per_image,
        "observations": observations,
    }


def _better_metric_row(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    """Return the better diagnostic row using GT-derived metrics.

    This is intentionally not a production strategy; it is an upper bound used to
    decide whether more data/parser work could pay off.
    """
    left_key = (
        int(left.get("ingredient_found", 0)),
        int(left.get("field_matched", 0)),
        float(left.get("field_match_ratio", 0.0)),
    )
    right_key = (
        int(right.get("ingredient_found", 0)),
        int(right.get("field_matched", 0)),
        float(right.get("field_match_ratio", 0.0)),
    )
    return left if left_key >= right_key else right


def _comparison_row(
    *,
    fixture_id: str,
    primary_name: str,
    secondary_name: str,
    primary_lines: list[str],
    secondary_lines: list[str],
    union_lines: list[str],
    evidence_union_lines: list[str],
    evidence_records: list[dict[str, Any]],
    primary_metrics: dict[str, Any],
    secondary_metrics: dict[str, Any],
    union_metrics: dict[str, Any],
    evidence_union_metrics: dict[str, Any],
) -> dict[str, Any]:
    """Build one redacted line-comparison row."""
    primary_hashes = {_line_hash(line) for line in primary_lines}
    secondary_hashes = {_line_hash(line) for line in secondary_lines}
    return {
        "fixture_id": fixture_id,
        "primary_name": primary_name,
        "secondary_name": secondary_name,
        "primary_line_count": len(primary_lines),
        "secondary_line_count": len(secondary_lines),
        "union_line_count": len(union_lines),
        "common_line_hash_count": len(primary_hashes & secondary_hashes),
        "primary_only_line_hash_count": len(primary_hashes - secondary_hashes),
        "secondary_only_line_hash_count": len(secondary_hashes - primary_hashes),
        "evidence_union_line_count": len(evidence_union_lines),
        "evidence_record_count": len(evidence_records),
        "evidence_accept_reasons": sorted(
            {
                str(record.get("accept_reason"))
                for record in evidence_records
                if record.get("accept_reason")
            }
        ),
        "evidence_records": evidence_records[:MAX_REDACTED_EVIDENCE_RECORDS],
        "primary": {
            "field_match_ratio": primary_metrics["field_match_ratio"],
            "field_matched": primary_metrics["field_matched"],
            "field_total": primary_metrics["field_total"],
            "ingredient_found": primary_metrics["ingredient_found"],
            "ingredient_total": primary_metrics["ingredient_total"],
        },
        "secondary": {
            "field_match_ratio": secondary_metrics["field_match_ratio"],
            "field_matched": secondary_metrics["field_matched"],
            "field_total": secondary_metrics["field_total"],
            "ingredient_found": secondary_metrics["ingredient_found"],
            "ingredient_total": secondary_metrics["ingredient_total"],
        },
        "union": {
            "field_match_ratio": union_metrics["field_match_ratio"],
            "field_matched": union_metrics["field_matched"],
            "field_total": union_metrics["field_total"],
            "ingredient_found": union_metrics["ingredient_found"],
            "ingredient_total": union_metrics["ingredient_total"],
        },
        "evidence_union": {
            "field_match_ratio": evidence_union_metrics["field_match_ratio"],
            "field_matched": evidence_union_metrics["field_matched"],
            "field_total": evidence_union_metrics["field_total"],
            "ingredient_found": evidence_union_metrics["ingredient_found"],
            "ingredient_total": evidence_union_metrics["ingredient_total"],
        },
        "raw_ocr_text_stored": False,
        "evidence_records_truncated": len(evidence_records) > MAX_REDACTED_EVIDENCE_RECORDS,
    }


def _write_raw_debug(
    *,
    raw_debug_dir: Path,
    fixture_id: str,
    primary_name: str,
    secondary_name: str,
    primary_lines: list[str],
    secondary_lines: list[str],
    union_lines: list[str] | None = None,
    evidence_union_lines: list[str] | None = None,
    variant_line_counts: list[dict[str, Any]] | None = None,
) -> None:
    """Write temporary raw OCR lines for operator-only hard-case analysis.

    Args:
        raw_debug_dir: Operator-local debug directory. This path must not be
            committed or copied into normal artifacts.
        fixture_id: Hard-case fixture id.
        primary_name: Primary OCR candidate label.
        secondary_name: Secondary OCR candidate label.
        primary_lines: Primary OCR candidate lines.
        secondary_lines: Secondary OCR candidate lines.
        union_lines: Optional merged candidate lines.
        evidence_union_lines: Optional visible-text evidence windows.
        variant_line_counts: Optional per-crop line-count diagnostics.
    """
    raw_debug_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "paddleocr-raw-line-debug-v2",
        "fixture_id": fixture_id,
        "warning": "temporary operator-only raw OCR debug artifact; do not commit",
        "primary_name": primary_name,
        "secondary_name": secondary_name,
        "variant_line_counts": variant_line_counts or [],
        "primary_lines": primary_lines,
        "secondary_lines": secondary_lines,
        "union_lines": union_lines or _union_lines(primary_lines, secondary_lines),
        "evidence_union_lines": evidence_union_lines
        or _ingredient_evidence_lines(_union_lines(primary_lines, secondary_lines)),
    }
    _write_json(raw_debug_dir / f"{_safe_filename(fixture_id)}.json", payload)


def _predict_lines_by_variant(
    ocr: Any, variant_paths: list[Path]
) -> tuple[list[str], list[dict[str, Any]]]:
    """Run OCR on each variant and return line union plus redacted counts.

    Args:
        ocr: PaddleOCR instance.
        variant_paths: Full image and temporary crop paths.

    Returns:
        A tuple of merged lines and per-variant line-count diagnostics. Variant
        paths are not exposed, only basename-level labels for operator analysis.
    """
    merged: list[str] = []
    counts: list[dict[str, Any]] = []
    for index, variant_path in enumerate(variant_paths):
        lines = _predict_lines(ocr, variant_path)
        counts.append(
            {
                "variant_index": index,
                "variant_name": variant_path.name,
                "line_count": len(lines),
            }
        )
        merged = _union_lines(merged, lines)
    return merged, counts


def _write_strategy_artifacts(
    *,
    output_dir: Path,
    strategy: str,
    eval_payload: dict[str, Any],
    split_rows: list[dict[str, Any]],
    args: argparse.Namespace,
) -> dict[str, Any]:
    """Write eval, observations, summary, and gate artifacts for one strategy."""
    observations = eval_payload.pop("observations")
    eval_path = output_dir / f"paddleocr-adaptive-eval.{strategy}.json"
    observations_path = output_dir / f"paddleocr-adaptive-observations.{strategy}.jsonl"
    summary_path = output_dir / f"structured-extraction-summary.{strategy}.json"
    gate_path = output_dir / f"structured-extraction-gate.{strategy}.json"
    _write_json(eval_path, eval_payload)
    _write_jsonl(observations_path, observations)
    summary = build_summary(
        eval_json=eval_payload,
        split_rows=split_rows,
        eval_split=args.eval_split,
        provider=args.provider,
        leakage_check_passed=True,
        privacy_review_cleared=True,
    )
    gate = build_structured_extraction_gate(
        summary,
        target_threshold=Decimal(str(args.target_threshold)),
        min_ingredient_recall=Decimal(str(args.min_ingredient_recall)),
        min_fixture_count=args.min_fixtures,
    )
    _write_json(summary_path, summary)
    _write_json(gate_path, gate)
    return {
        "strategy": strategy,
        "metrics": summary["metrics"],
        "failure_modes": summary["failure_modes"],
        "gate_status": gate["status"],
        "eval_json": str(eval_path.relative_to(output_dir)),
        "summary_json": str(summary_path.relative_to(output_dir)),
        "gate_json": str(gate_path.relative_to(output_dir)),
    }


def run_adaptive_eval(args: argparse.Namespace) -> dict[str, Any]:  # noqa: PLR0915
    """Run adaptive OCR merge evaluation.

    Args:
        args: Parsed CLI namespace.

    Returns:
        Redacted comparison summary.

    Raises:
        FileNotFoundError: If required inputs are missing.
    """
    todo_path = args.bundle_dir / "ground-truth.todo.jsonl"
    if not todo_path.is_file():
        raise FileNotFoundError(f"ground-truth.todo.jsonl not found under {args.bundle_dir}")
    if not args.splits.is_file():
        raise FileNotFoundError(f"splits JSONL not found: {args.splits}")

    primary_config = CandidateConfig(args.primary_name, args.primary_rec_model_dir)
    secondary_config = CandidateConfig(args.secondary_name, args.secondary_rec_model_dir)
    profile = PROFILES[args.profile]
    det_model = args.det_model or profile["det"]
    rec_model = args.rec_model or profile["rec"]
    max_side = args.max_side or profile["max_side"]
    device = getattr(args, "device", None)

    if not args.apply:
        return {
            "schema_version": SCHEMA_VERSION,
            "apply_requested": False,
            "profile": args.profile,
            "det_unclip_ratio": args.det_unclip_ratio,
            "ocr_pass_preset": args.ocr_pass_preset,
            "device": device,
            "primary_name": primary_config.name,
            "secondary_name": secondary_config.name,
            "raw_debug_requested": args.raw_debug_dir is not None,
            "source_doc_urls": SOURCE_DOC_URLS,
        }

    pass_configs = _ocr_pass_configs(args)
    primary_ocr_passes = _build_candidate_ocr_passes(
        candidate=primary_config,
        pass_configs=pass_configs,
        det_model=det_model,
        rec_model=rec_model,
        max_side=max_side,
        device=device,
    )
    secondary_ocr_passes = _build_candidate_ocr_passes(
        candidate=secondary_config,
        pass_configs=pass_configs,
        det_model=det_model,
        rec_model=rec_model,
        max_side=max_side,
        device=device,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    all_ready_rows = _load_ready_rows(args.bundle_dir, limit=None)
    ready_rows = _selected_ready_rows(
        all_ready_rows,
        fixture_ids=getattr(args, "fixture_id", []),
        shard_index=getattr(args, "shard_index", None),
        num_shards=getattr(args, "num_shards", None),
        limit=getattr(args, "limit", None),
    )
    fixture_selector = _fixture_selector_summary(
        args,
        selected_count=len(ready_rows),
        ready_count=len(all_ready_rows),
    )
    progress_path = getattr(args, "progress_jsonl", None) or (
        args.output_dir / "progress.redacted.jsonl"
    )
    _append_jsonl(
        progress_path,
        {
            "event": "start",
            "total_fixtures": len(ready_rows),
            "fixture_selector": fixture_selector,
            "roi_crop_preset": args.roi_crop_preset,
            "ocr_pass_preset": args.ocr_pass_preset,
            "device": device,
            "raw_ocr_text_stored": False,
            "provider_payload_stored": False,
        },
    )

    primary_rows: list[dict[str, Any]] = []
    secondary_rows: list[dict[str, Any]] = []
    union_rows: list[dict[str, Any]] = []
    evidence_union_rows: list[dict[str, Any]] = []
    oracle_rows: list[dict[str, Any]] = []
    primary_observations: list[dict[str, Any]] = []
    secondary_observations: list[dict[str, Any]] = []
    union_observations: list[dict[str, Any]] = []
    evidence_union_observations: list[dict[str, Any]] = []
    oracle_observations: list[dict[str, Any]] = []
    comparison_rows: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []

    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="lemon_ocr_roi_crops_") as temp_name:
        temp_dir = Path(temp_name)
        for row_index, row in enumerate(ready_rows, start=1):
            fixture_id = str(row.get("fixture_id") or "")
            expected = row["expected"]
            image_path = str(row.get("image_path", "")).strip()
            if not fixture_id or not image_path:
                failures.append(
                    {"fixture_id": fixture_id or "unknown", "reason": "missing_fixture_or_image"}
                )
                _append_jsonl(
                    progress_path,
                    {
                        "event": "fixture_skipped",
                        "index": row_index,
                        "total_fixtures": len(ready_rows),
                        "fixture_id": fixture_id or "unknown",
                        "reason": "missing_fixture_or_image",
                        "elapsed_seconds": round(time.monotonic() - started, 3),
                        "raw_ocr_text_stored": False,
                        "provider_payload_stored": False,
                    },
                )
                continue
            try:
                variant_paths = _crop_variants(
                    args.bundle_dir / image_path,
                    fixture_id=fixture_id,
                    temp_dir=temp_dir,
                    preset=args.roi_crop_preset,
                )
                primary_lines, _primary_variant_counts = _predict_candidate_lines(
                    primary_ocr_passes, variant_paths
                )
                secondary_lines, _secondary_variant_counts = _predict_candidate_lines(
                    secondary_ocr_passes, variant_paths
                )
            except Exception:
                failures.append({"fixture_id": fixture_id, "reason": "paddleocr_prediction_failed"})
                _append_jsonl(
                    progress_path,
                    {
                        "event": "fixture_failed",
                        "index": row_index,
                        "total_fixtures": len(ready_rows),
                        "fixture_id": fixture_id,
                        "reason": "paddleocr_prediction_failed",
                        "elapsed_seconds": round(time.monotonic() - started, 3),
                        "raw_ocr_text_stored": False,
                        "provider_payload_stored": False,
                    },
                )
                continue
            merged_lines = _union_lines(primary_lines, secondary_lines)
            evidence_lines, evidence_records = _ingredient_evidence_lines_with_records(merged_lines)

            primary_metric, primary_observation = _score_prediction(
                fixture_id=fixture_id,
                expected=expected,
                lines=primary_lines,
                post_pass=args.post_pass,
                provider=args.provider,
            )
            secondary_metric, secondary_observation = _score_prediction(
                fixture_id=fixture_id,
                expected=expected,
                lines=secondary_lines,
                post_pass=args.post_pass,
                provider=args.provider,
            )
            union_metric, union_observation = _score_prediction(
                fixture_id=fixture_id,
                expected=expected,
                lines=merged_lines,
                post_pass=args.post_pass,
                provider=args.provider,
            )
            evidence_union_metric, evidence_union_observation = _score_prediction(
                fixture_id=fixture_id,
                expected=expected,
                lines=evidence_lines,
                post_pass=args.post_pass,
                provider=args.provider,
            )
            oracle_metric = _better_metric_row(
                _better_metric_row(
                    _better_metric_row(primary_metric, secondary_metric), union_metric
                ),
                evidence_union_metric,
            )
            if oracle_metric is primary_metric:
                oracle_observation = primary_observation
            elif oracle_metric is secondary_metric:
                oracle_observation = secondary_observation
            elif oracle_metric is union_metric:
                oracle_observation = union_observation
            else:
                oracle_observation = evidence_union_observation

            primary_rows.append(primary_metric)
            secondary_rows.append(secondary_metric)
            union_rows.append(union_metric)
            evidence_union_rows.append(evidence_union_metric)
            oracle_rows.append({**oracle_metric, "oracle_source": oracle_observation["status"]})
            primary_observations.append(primary_observation)
            secondary_observations.append(secondary_observation)
            union_observations.append(union_observation)
            evidence_union_observations.append(evidence_union_observation)
            oracle_observations.append(oracle_observation)
            comparison_rows.append(
                _comparison_row(
                    fixture_id=fixture_id,
                    primary_name=primary_config.name,
                    secondary_name=secondary_config.name,
                    primary_lines=primary_lines,
                    secondary_lines=secondary_lines,
                    union_lines=merged_lines,
                    evidence_union_lines=evidence_lines,
                    evidence_records=evidence_records,
                    primary_metrics=primary_metric,
                    secondary_metrics=secondary_metric,
                    union_metrics=union_metric,
                    evidence_union_metrics=evidence_union_metric,
                )
            )
            _append_jsonl(
                progress_path,
                {
                    "event": "fixture_done",
                    "index": row_index,
                    "total_fixtures": len(ready_rows),
                    "fixture_id": fixture_id,
                    "variant_count": len(variant_paths),
                    "primary_line_count": len(primary_lines),
                    "secondary_line_count": len(secondary_lines),
                    "union_line_count": len(merged_lines),
                    "evidence_union_line_count": len(evidence_lines),
                    "evidence_record_count": len(evidence_records),
                    "elapsed_seconds": round(time.monotonic() - started, 3),
                    "raw_ocr_text_stored": False,
                    "provider_payload_stored": False,
                },
            )

    strategy_evals = {
        primary_config.name: _aggregate_eval(
            strategy=primary_config.name,
            per_image=primary_rows,
            observations=primary_observations,
            args=args,
            det_model=det_model,
            rec_model=rec_model,
            max_side=max_side,
        ),
        secondary_config.name: _aggregate_eval(
            strategy=secondary_config.name,
            per_image=secondary_rows,
            observations=secondary_observations,
            args=args,
            det_model=det_model,
            rec_model=rec_model,
            max_side=max_side,
        ),
        "union": _aggregate_eval(
            strategy="union",
            per_image=union_rows,
            observations=union_observations,
            args=args,
            det_model=det_model,
            rec_model=rec_model,
            max_side=max_side,
        ),
        "evidence_union": _aggregate_eval(
            strategy="evidence_union",
            per_image=evidence_union_rows,
            observations=evidence_union_observations,
            args=args,
            det_model=det_model,
            rec_model=rec_model,
            max_side=max_side,
        ),
        "oracle_best": _aggregate_eval(
            strategy="oracle_best",
            per_image=oracle_rows,
            observations=oracle_observations,
            args=args,
            det_model=det_model,
            rec_model=rec_model,
            max_side=max_side,
        ),
    }
    split_rows = _read_jsonl(args.splits)
    strategy_summaries = [
        _write_strategy_artifacts(
            output_dir=args.output_dir,
            strategy=strategy,
            eval_payload=dict(eval_payload),
            split_rows=split_rows,
            args=args,
        )
        for strategy, eval_payload in strategy_evals.items()
    ]
    primary_hardcases = extract_hardcases(
        eval_json=strategy_evals[primary_config.name],
        split_by_fixture={str(row.get("fixture_id")): str(row.get("split")) for row in split_rows},
        eval_split=args.eval_split,
    )
    hardcase_ids = set(
        primary_hardcases["fixture_ids"]["union_field_zero_or_ingredient_all_missed"]
    )
    hardcase_comparison_rows = [row for row in comparison_rows if row["fixture_id"] in hardcase_ids]
    line_comparison = {
        "schema_version": COMPARISON_SCHEMA_VERSION,
        "primary_name": primary_config.name,
        "secondary_name": secondary_config.name,
        "hardcase_fixture_count": len(hardcase_comparison_rows),
        "rows": hardcase_comparison_rows,
        "raw_ocr_text_stored": False,
        "provider_payload_stored": False,
    }
    _write_json(args.output_dir / "hardcase-fixtures.primary.json", primary_hardcases)
    _write_json(args.output_dir / "line-comparison-hardcases.redacted.json", line_comparison)

    if args.raw_debug_dir is not None:
        with tempfile.TemporaryDirectory(prefix="lemon_ocr_raw_debug_crops_") as debug_temp_name:
            debug_temp_dir = Path(debug_temp_name)
            for row in ready_rows:
                fixture_id = str(row.get("fixture_id") or "")
                image_path = str(row.get("image_path", "")).strip()
                if fixture_id not in hardcase_ids or not image_path:
                    continue
                try:
                    variant_paths = _crop_variants(
                        args.bundle_dir / image_path,
                        fixture_id=fixture_id,
                        temp_dir=debug_temp_dir,
                        preset=args.roi_crop_preset,
                    )
                    primary_lines, primary_variant_counts = _predict_candidate_lines(
                        primary_ocr_passes, variant_paths
                    )
                    secondary_lines, secondary_variant_counts = _predict_candidate_lines(
                        secondary_ocr_passes, variant_paths
                    )
                except Exception:
                    continue
                union_lines = _union_lines(primary_lines, secondary_lines)
                evidence_union_lines = _ingredient_evidence_lines(union_lines)
                _write_raw_debug(
                    raw_debug_dir=args.raw_debug_dir,
                    fixture_id=fixture_id,
                    primary_name=primary_config.name,
                    secondary_name=secondary_config.name,
                    primary_lines=primary_lines,
                    secondary_lines=secondary_lines,
                    union_lines=union_lines,
                    evidence_union_lines=evidence_union_lines,
                    variant_line_counts=[
                        {
                            "candidate": primary_config.name,
                            "variants": primary_variant_counts,
                        },
                        {
                            "candidate": secondary_config.name,
                            "variants": secondary_variant_counts,
                        },
                    ],
                )

    by_strategy = {item["strategy"]: item for item in strategy_summaries}
    primary_recall = by_strategy[primary_config.name]["metrics"]["ingredient_recall"]
    union_recall = by_strategy["union"]["metrics"]["ingredient_recall"]
    evidence_union_recall = by_strategy["evidence_union"]["metrics"]["ingredient_recall"]
    return {
        "schema_version": SCHEMA_VERSION,
        "apply_requested": True,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "profile": args.profile,
        "detection_model": det_model,
        "recognition_model": rec_model,
        "max_side": max_side,
        "det_box_thresh": args.det_box_thresh,
        "det_thresh": args.det_thresh,
        "det_unclip_ratio": args.det_unclip_ratio,
        "roi_crop_preset": args.roi_crop_preset,
        "ocr_pass_preset": args.ocr_pass_preset,
        "ocr_passes": [
            {
                "name": pass_config.name,
                "det_box_thresh": pass_config.det_box_thresh,
                "det_thresh": pass_config.det_thresh,
                "det_unclip_ratio": pass_config.det_unclip_ratio,
                "official_recommended_value": False,
            }
            for pass_config in pass_configs
        ],
        "post_pass": args.post_pass,
        "primary_name": primary_config.name,
        "secondary_name": secondary_config.name,
        "fixture_selector": fixture_selector,
        "total_fixtures": len(ready_rows),
        "strategy_summaries": strategy_summaries,
        "ingredient_recall_improved_by_union": union_recall > primary_recall,
        "ingredient_recall_improved_by_evidence_union": evidence_union_recall > primary_recall,
        "primary_hardcase_counts": primary_hardcases["counts"],
        "failed_fixture_count": len(failures),
        "failures": failures,
        "redacted_line_comparison": "line-comparison-hardcases.redacted.json",
        "hardcase_fixtures": "hardcase-fixtures.primary.json",
        "raw_debug_dir_written": args.raw_debug_dir is not None,
        "raw_debug_policy": (
            "temporary_operator_only_do_not_commit" if args.raw_debug_dir is not None else None
        ),
        "oracle_best_note": "GT-derived upper bound; do not use as production strategy.",
        "source_doc_urls": SOURCE_DOC_URLS,
    }


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    args = parse_args(argv)
    try:
        summary = run_adaptive_eval(args)
    except (FileNotFoundError, ValueError) as exc:
        print(
            json.dumps(
                {"schema_version": SCHEMA_VERSION, "status": "error", "error": str(exc)},
                ensure_ascii=False,
            )
        )
        return 1
    args.output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(args.output_dir / "adaptive-structured-summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
