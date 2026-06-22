"""Evaluate PaddleOCR text extraction against the CLOVA pseudo-ground-truth.

Standalone harness that runs in the Python 3.12 PaddleOCR venv (``.venv-paddle``)
— it does NOT import the backend package (which requires py3.13). For each
benchmark-ready review image in the ground-truth bundle, it runs the local
PaddleOCR pipeline and scores the extracted text against the CLOVA-built GT.

Two metric families are reported:

* ``field_match_ratio`` (HEADLINE, operator-selected 95% target metric): for each
  structured GT field unit (product name, each ingredient display-name, each
  amount+unit, intake-method text), check whether it is present in the PaddleOCR
  text via a fuzzy partial match (rapidfuzz ``partial_ratio``). Precision-immune:
  PaddleOCR reading *extra* label text never lowers it, which is the correct
  framing for a structured-only pseudo-GT.
* LCS ``normalized_text_precision``/``recall``/``f1`` (mirrors the backend
  collector ``_normalized_text_extraction_metrics``) — kept for the formal
  eval-summary/gate chain. ``precision`` is structurally bounded below 1 against a
  structured-only reference; ``recall`` is the meaningful LCS signal.

Profiles select the detector/recognizer/resolution. PP-OCRv5 has no Korean server
recognizer, so the ``server`` profile is server-detector + Korean mobile-recognizer
at higher resolution (better text-region detection). Run only when no other heavy
model (e.g. the Ollama CLOVA-GT job) is loaded — the server detector on large
images is memory-hungry on CPU.

Outputs (1) a redacted JSON results file (numeric scores only) and, optionally,
(2) a flat observation JSONL compatible with
``merge_paddleocr_text_observations_into_benchmark.py`` so the formal py3.13
eval/gate chain can run. No raw OCR text is written to disk. Dry-run by default;
pass ``--apply`` to score.

References:
    https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from decimal import Decimal
from pathlib import Path
from typing import Any

from rapidfuzz import fuzz
from rapidfuzz.distance import LCSseq

MAX_METRIC_CHARS = 12000
TARGET_PROVIDER = "paddleocr_local"
FIELD_MATCH_THRESHOLD = 85.0  # rapidfuzz partial_ratio (0-100) for field presence.
INGREDIENT_ALIAS_CONFUSION_MIN_CHARS = 5
POST_PASS_NONE = "none"
POST_PASS_INGREDIENT_ALIAS_AMOUNT_UNIT = "ingredient_alias_amount_unit"
POST_PASS_CHOICES = (POST_PASS_NONE, POST_PASS_INGREDIENT_ALIAS_AMOUNT_UNIT)

INGREDIENT_ALIAS_GROUPS: tuple[tuple[str, ...], ...] = (
    ("vitamin c", "ascorbic acid", "비타민 c", "비타민씨", "아스코르브산"),
    ("vitamin d", "vitamin d3", "cholecalciferol", "비타민 d", "비타민 d3", "콜레칼시페롤"),
    ("vitamin b1", "thiamine", "티아민", "비타민 b1"),
    ("vitamin b2", "riboflavin", "리보플라빈", "비타민 b2"),
    (
        "vitamin b6",
        "pyridoxine",
        "pyridoxine hcl",
        "pyridoxine hydrochloride",
        "피리독신",
        "피리독신 염산염",
        "비타민 b6",
    ),
    ("vitamin b12", "cyanocobalamin", "methylcobalamin", "코발라민", "비타민 b12"),
    (
        "niacin",
        "niacinamide",
        "nicotinamide",
        "nicotinic acid",
        "나이아신",
        "나이아신아마이드",
        "니코틴아마이드",
        "니코틴산",
    ),
    (
        "pantothenic acid",
        "calcium pantothenate",
        "vitamin b5",
        "판토텐산",
        "판토텐산칼슘",
        "비타민 b5",
    ),
    ("folate", "folic acid", "엽산"),
    ("biotin", "비오틴"),
    ("choline", "choline bitartrate", "콜린", "콜린 비타르트레이트"),
    ("inositol", "이노시톨"),
    (
        "vitamin k",
        "vitamin k1",
        "vitamin k2",
        "menaquinone",
        "phytonadione",
        "비타민 k",
        "비타민 k1",
        "비타민 k2",
    ),
    ("vitamin e", "tocopherol", "tocopheryl", "d-alpha tocopherol", "비타민 e", "토코페롤"),
    ("calcium", "calcium carbonate", "calcium citrate", "칼슘", "탄산칼슘", "구연산칼슘"),
    (
        "magnesium",
        "magnesium oxide",
        "magnesium citrate",
        "마그네슘",
        "산화마그네슘",
        "구연산마그네슘",
    ),
    ("zinc", "아연"),
    ("iron", "ferrous", "철", "철분"),
    ("iodine", "iodide", "요오드"),
    ("selenium", "셀레늄"),
    ("chromium", "크롬"),
    ("copper", "구리"),
    ("manganese", "망간"),
    ("molybdenum", "몰리브덴"),
    ("boron", "borate", "붕소"),
    ("phosphorus", "phosphate", "인", "인산염"),
    ("potassium", "칼륨"),
    ("sodium", "나트륨"),
    ("chloride", "염화물"),
    ("silica", "silicon", "규소", "실리카"),
    ("omega-3", "omega 3", "epa", "dha", "오메가 3", "오메가3"),
    ("coq10", "coenzyme q10", "코큐텐", "코엔자임 q10"),
    ("lutein", "루테인"),
    ("zeaxanthin", "지아잔틴"),
    ("beta carotene", "beta-carotene", "베타카로틴"),
    ("lycopene", "라이코펜"),
    ("astaxanthin", "아스타잔틴"),
    ("probiotics", "lactobacillus", "bifidobacterium", "유산균", "프로바이오틱스"),
    ("collagen", "콜라겐"),
    ("hyaluronic acid", "sodium hyaluronate", "히알루론산", "히알루론산나트륨"),
    ("glucosamine", "글루코사민"),
    ("msm", "methylsulfonylmethane", "식이유황"),
    ("milk thistle", "silymarin", "밀크씨슬", "실리마린"),
    ("ginseng", "홍삼", "인삼"),
    ("turmeric", "curcumin", "강황", "커큐민"),
    ("cranberry", "크랜베리"),
    ("quercetin", "퀘르세틴"),
    ("bromelain", "브로멜라인"),
    ("melatonin", "멜라토닌"),
    ("gaba", "gamma aminobutyric acid", "감마아미노부티르산", "가바"),
    ("l-theanine", "theanine", "테아닌"),
    ("taurine", "타우린"),
    ("maca", "마카"),
    ("arginine", "l-arginine", "아르기닌"),
    ("citrulline", "l-citrulline", "시트룰린"),
    ("lysine", "l-lysine", "라이신"),
    ("creatine", "크레아틴"),
    ("saw palmetto", "쏘팔메토", "쏘팔메토열매"),
    ("boswellia", "boswellic acid", "보스웰리아"),
    ("sunflower seed", "sunflower seeds", "해바라기씨"),
    (
        "magnesium glycinate",
        "magnesium lysinate glycinate",
        "마그네슘 글리시네이트",
        "글리시네이트 마그네슘",
    ),
    ("zinc picolinate", "아연 피콜리네이트"),
    ("gelatin", "gelatin capsule", "capsule gelatin", "젤라틴", "젤라틴 캡슐"),
    (
        "cellulose",
        "vegetable cellulose",
        "microcrystalline cellulose",
        "hypromellose",
        "hpmc",
        "셀룰로오스",
        "식물성 셀룰로오스",
        "히프로멜로오스",
    ),
    ("rice flour", "rice powder", "쌀가루", "쌀 분말"),
    ("stearic acid", "magnesium stearate", "스테아린산", "스테아린산마그네슘"),
    ("silicon dioxide", "silica", "이산화규소", "실리카"),
    ("maltodextrin", "말토덱스트린"),
    ("glycerin", "glycerol", "글리세린"),
    ("soybean oil", "soy oil", "대두유", "콩기름"),
)

UNIT_ALIASES: dict[str, tuple[str, ...]] = {
    "mg": ("mg", "㎎", "밀리그램", "milligram", "milligrams"),
    "g": ("g", "그램", "gram", "grams"),
    "mcg": ("mcg", "ug", "μg", "µg", "㎍", "마이크로그램", "microgram", "micrograms"),
    "iu": ("iu", "i.u.", "아이유", "international unit", "international units"),
    "cfu": ("cfu", "씨에프유"),
    "%": ("%", "퍼센트"),
}

AMOUNT_UNIT_PATTERN = re.compile(
    r"(?P<amount>\d+(?:[.,]\d+)?)\s*"
    r"(?P<unit>mg|㎎|밀리그램|milligrams?|g|그램|grams?|"
    r"mcg|ug|μg|µg|㎍|마이크로그램|micrograms?|"
    r"iu|i\.u\.|아이유|international units?|cfu|씨에프유|%)",
    re.IGNORECASE,
)
OCR_CONFUSED_AMOUNT_UNIT_PATTERN = re.compile(
    r"(?P<amount>[0-9OoIl.,]+)\s*"
    r"(?P<unit>mg|㎎|밀리그램|milligrams?|g|그램|grams?|"
    r"mcg|ug|μg|µg|㎍|마이크로그램|micrograms?|"
    r"iu|i\.u\.|아이유|international units?|cfu|씨에프유|%)",
    re.IGNORECASE,
)
PLACEHOLDER_TEXT_VALUES = {"", "null", "none", "n/a", "na", "-", "미상", "확인불가", "확인 불가"}

PROFILES: dict[str, dict[str, Any]] = {
    "mobile": {
        "det": "PP-OCRv5_mobile_det",
        "rec": "korean_PP-OCRv5_mobile_rec",
        "max_side": 2048,
    },
    "server": {
        # No Korean server recognizer exists in PP-OCRv5; use server detector +
        # Korean mobile recognizer at higher resolution for better detection.
        "det": "PP-OCRv5_server_det",
        "rec": "korean_PP-OCRv5_mobile_rec",
        "max_side": 3072,
    },
    "server_detection": {
        # Runtime-aligned alias for LOCAL_OCR_MODEL_PROFILE=server_detection.
        "det": "PP-OCRv5_server_det",
        "rec": "korean_PP-OCRv5_mobile_rec",
        "max_side": 3072,
    },
}


def _normalize_for_metric(text: str) -> str:
    """Return NFKC + lowercase + alphanumeric-only text (mirrors the backend metric)."""
    normalized = unicodedata.normalize("NFKC", text).lower()
    return "".join(char for char in normalized if char.isalnum())


def _is_placeholder_text(value: str) -> bool:
    """Return whether a reviewed value is an explicit non-answer placeholder."""
    normalized = " ".join(value.split()).strip().casefold()
    return normalized in PLACEHOLDER_TEXT_VALUES


def _metric_float(value: Decimal) -> float:
    """Return a 4-decimal float from a Decimal metric (mirrors the backend metric)."""
    return float(value.quantize(Decimal("0.0001")))


def _text_extraction_metrics(reference: str, hypothesis: str) -> dict[str, Any] | None:
    """Return LCS-based precision/recall/F1 for one image, or None when skipped.

    Args:
        reference: Structured-section ground-truth text.
        hypothesis: PaddleOCR predicted text.

    Returns:
        Numeric metric mapping, or None when the reference is empty or either
        string exceeds the metric character cap.
    """
    reference_chars = _normalize_for_metric(reference)
    hypothesis_chars = _normalize_for_metric(hypothesis)
    if not reference_chars:
        return None
    if len(reference_chars) > MAX_METRIC_CHARS or len(hypothesis_chars) > MAX_METRIC_CHARS:
        return None
    matched = LCSseq.similarity(reference_chars, hypothesis_chars)
    precision = (
        Decimal(matched) / Decimal(len(hypothesis_chars)) if hypothesis_chars else Decimal(0)
    )
    recall = Decimal(matched) / Decimal(len(reference_chars))
    denom = precision + recall
    f1 = (Decimal(2) * precision * recall / denom) if denom else Decimal(0)
    return {
        "matched_char_count": matched,
        "reference_char_count": len(reference_chars),
        "hypothesis_char_count": len(hypothesis_chars),
        "normalized_text_precision": _metric_float(precision),
        "normalized_text_recall": _metric_float(recall),
        "normalized_text_f1": _metric_float(f1),
    }


def _append_text(parts: list[str], value: Any) -> None:
    """Append one scalar expected value to the reference text parts."""
    if isinstance(value, str) and value.strip() and not _is_placeholder_text(value):
        parts.append(value.strip())
    elif isinstance(value, int | float) and not isinstance(value, bool):
        parts.append(str(value))


def _structured_reference(expected: dict[str, Any]) -> str:
    """Return the structured-section reference text (mirrors the backend builder)."""
    parts: list[str] = []
    _append_text(parts, expected.get("product_name"))
    _append_text(parts, expected.get("manufacturer"))
    for ingredient in expected.get("ingredients", []) or []:
        if not isinstance(ingredient, dict):
            continue
        for key in ("display_name", "original_name"):
            _append_text(parts, ingredient.get(key))
        _append_text(parts, ingredient.get("amount"))
        _append_text(parts, ingredient.get("unit"))
    intake = expected.get("intake_method")
    if isinstance(intake, dict):
        _append_text(parts, intake.get("text"))
    else:
        _append_text(parts, intake)
    for key in ("precautions", "allergen_warnings", "functional_claims", "label_sections"):
        value = expected.get(key)
        if not isinstance(value, list):
            continue
        for item in value:
            if isinstance(item, dict):
                _append_text(parts, item.get("text"))
                _append_text(parts, item.get("section_type"))
            else:
                _append_text(parts, item)
    return " ".join(parts)


def _field_units(expected: dict[str, Any]) -> list[str]:
    """Return the GT field units scored by ``field_match_ratio``.

    Args:
        expected: GT ``expected`` object.

    Returns:
        Non-empty field-unit strings (product name, manufacturer, each ingredient
        display-name, each amount+unit pair, intake-method text).
    """
    units: list[str] = []
    for key in ("product_name", "manufacturer"):
        value = expected.get(key)
        if isinstance(value, str) and value.strip():
            units.append(value.strip())
    for ingredient in expected.get("ingredients", []) or []:
        if not isinstance(ingredient, dict):
            continue
        name = ingredient.get("display_name")
        if isinstance(name, str) and name.strip() and not _is_placeholder_text(name):
            units.append(name.strip())
        amount_unit = " ".join(
            str(ingredient[k])
            for k in ("amount", "unit")
            if ingredient.get(k) not in (None, "")
            and not (isinstance(ingredient.get(k), str) and _is_placeholder_text(ingredient.get(k)))
        )
        if amount_unit.strip():
            units.append(amount_unit.strip())
    intake = expected.get("intake_method")
    intake_text = intake.get("text") if isinstance(intake, dict) else intake
    if (
        isinstance(intake_text, str)
        and intake_text.strip()
        and not _is_placeholder_text(intake_text)
    ):
        units.append(intake_text.strip())
    return units


def _alias_candidates(value: str) -> list[str]:
    """Return deterministic bilingual candidates for one expected text value."""
    value_norm = _normalize_for_metric(value)
    candidates = [value]
    for aliases in INGREDIENT_ALIAS_GROUPS:
        alias_norms = [_normalize_for_metric(alias) for alias in aliases]
        if any(alias_norm and alias_norm == value_norm for alias_norm in alias_norms):
            candidates.extend(aliases)
    return list(dict.fromkeys(candidates))


def _amount_unit_candidates(value: str) -> list[str]:
    """Return equivalent amount/unit spellings for one expected field unit."""
    match = AMOUNT_UNIT_PATTERN.search(unicodedata.normalize("NFKC", value))
    if not match:
        return [value]
    amount = _canonical_amount(match.group("amount"))
    canonical_unit = _canonical_unit(match.group("unit"))
    if canonical_unit is None:
        return [value]
    candidates = [value]
    for unit_alias in UNIT_ALIASES[canonical_unit]:
        candidates.append(f"{amount} {unit_alias}")
        candidates.append(f"{amount}{unit_alias}")
    return list(dict.fromkeys(candidates))


def _field_unit_candidates(unit: str) -> list[str]:
    """Return alias and amount-unit candidates without increasing the denominator."""
    candidates: list[str] = []
    for alias_candidate in _alias_candidates(unit):
        candidates.extend(_amount_unit_candidates(alias_candidate))
    return list(dict.fromkeys(candidates))


def _field_match_ratio(units: list[str], hypothesis_norm: str) -> tuple[int, int]:
    """Return ``(matched, total)`` GT field units present in the PaddleOCR text.

    A unit matches when its normalized form scores ``>= FIELD_MATCH_THRESHOLD`` via
    rapidfuzz ``partial_ratio`` against the normalized hypothesis (precision-immune).

    Args:
        units: GT field-unit strings.
        hypothesis_norm: Normalized PaddleOCR text.

    Returns:
        ``(matched_unit_count, total_unit_count)``.
    """
    total = 0
    matched = 0
    for unit in units:
        candidates = [
            _normalize_for_metric(candidate)
            for candidate in _field_unit_candidates(unit)
            if _normalize_for_metric(candidate)
        ]
        if not candidates:
            continue
        total += 1
        if hypothesis_norm and any(
            fuzz.partial_ratio(candidate_norm, hypothesis_norm) >= FIELD_MATCH_THRESHOLD
            for candidate_norm in candidates
        ):
            matched += 1
    return matched, total


def _ingredient_recall(expected: dict[str, Any], hypothesis_norm: str) -> tuple[int, int]:
    """Return ``(found, total)`` GT ingredient display-names present (substring)."""
    candidate_groups: list[list[str]] = []
    for item in expected.get("ingredients", []) or []:
        if not isinstance(item, dict):
            continue
        raw_names = [
            value
            for value in (item.get("display_name"), item.get("original_name"))
            if isinstance(value, str) and value.strip() and not _is_placeholder_text(value)
        ]
        if not raw_names:
            continue
        candidates: list[str] = []
        for raw_name in raw_names:
            candidates.extend(
                _normalize_for_metric(candidate) for candidate in _alias_candidates(raw_name)
            )
        candidate_groups.append(
            list(dict.fromkeys(candidate for candidate in candidates if candidate))
        )
    found = sum(
        1
        for candidates in candidate_groups
        if _ingredient_candidates_visible(candidates, hypothesis_norm)
    )
    return found, len(candidate_groups)


def _ingredient_candidates_visible(candidates: list[str], hypothesis_norm: str) -> bool:
    """Return whether any normalized ingredient candidate is visibly present.

    Args:
        candidates: Metric-normalized aliases for one GT ingredient.
        hypothesis_norm: Metric-normalized OCR hypothesis text.

    Returns:
        True for exact substring visibility, or for long aliases after bounded
        OCR glyph-confusion cleanup. This keeps short aliases exact to avoid
        broad false positives.
    """
    if not hypothesis_norm:
        return False
    hypothesis_confusion_norm = _normalize_alias_ocr_confusions(hypothesis_norm)
    for candidate in candidates:
        if candidate in hypothesis_norm:
            return True
        if (
            len(candidate) >= INGREDIENT_ALIAS_CONFUSION_MIN_CHARS
            and _normalize_alias_ocr_confusions(candidate) in hypothesis_confusion_norm
        ):
            return True
    return False


def _canonical_unit(unit: str) -> str | None:
    """Return the canonical unit key for a recognized unit token.

    Args:
        unit: Unit token found beside an amount.

    Returns:
        Canonical unit key, or ``None`` when the token is not in the deterministic
        unit table.
    """
    unit_norm = unicodedata.normalize("NFKC", unit).strip().lower()
    aliases = {
        "mg": "mg",
        "밀리그램": "mg",
        "milligram": "mg",
        "milligrams": "mg",
        "g": "g",
        "그램": "g",
        "gram": "g",
        "grams": "g",
        "mcg": "mcg",
        "ug": "mcg",
        "μg": "mcg",
        "µg": "mcg",
        "마이크로그램": "mcg",
        "microgram": "mcg",
        "micrograms": "mcg",
        "iu": "iu",
        "i.u.": "iu",
        "아이유": "iu",
        "international unit": "iu",
        "international units": "iu",
        "cfu": "cfu",
        "씨에프유": "cfu",
        "%": "%",
        "퍼센트": "%",
    }
    return aliases.get(unit_norm)


def _canonical_amount(amount: str) -> str:
    """Normalize OCR amount text without changing its numeric value."""
    translation = str.maketrans({"O": "0", "o": "0", "I": "1", "l": "1"})
    normalized = amount.translate(translation).replace(",", "").strip()
    return normalized[:-2] if normalized.endswith(".0") else normalized


def _normalize_alias_ocr_confusions(value: str) -> str:
    """Normalize bounded OCR glyph confusions for ingredient alias visibility checks.

    Args:
        value: Already metric-normalized alias or OCR text.

    Returns:
        A normalized string where common recognition confusions collapse to the
        same token. This is intentionally exact-match oriented, not fuzzy scoring.
    """
    normalized = value.translate(str.maketrans({"0": "o", "1": "i", "l": "i"}))
    return normalized.replace("rn", "m")


def _alias_group_visible_in_hypothesis(
    normalized_aliases: list[tuple[str, str]], text_norm: str
) -> bool:
    """Return whether an alias group is visibly present after bounded OCR cleanup.

    Args:
        normalized_aliases: ``(display_alias, normalized_alias)`` pairs from one
            canonical alias group.
        text_norm: Normalized OCR hypothesis text.

    Returns:
        True when an alias is exactly visible, or when a long alias is visible
        after deterministic glyph-confusion normalization.
    """
    text_confusion_norm = _normalize_alias_ocr_confusions(text_norm)
    for _, alias_norm in normalized_aliases:
        if not alias_norm:
            continue
        if alias_norm in text_norm:
            return True
        if len(alias_norm) >= INGREDIENT_ALIAS_CONFUSION_MIN_CHARS and (
            _normalize_alias_ocr_confusions(alias_norm) in text_confusion_norm
        ):
            return True
    return False


def _postprocess_hypothesis_text(text: str, *, mode: str) -> tuple[str, bool]:
    """Return OCR hypothesis text augmented with deterministic visible-text aliases.

    This post-pass never invents ingredients from the expected label. It only adds
    canonical Korean/English aliases or unit variants when one alias/amount-unit
    form is already visible in the OCR hypothesis. Long ingredient aliases also
    allow deterministic glyph-confusion normalization to absorb common OCR errors
    without loosening short-token matching. The goal is to make the structured
    metric robust to bilingual supplement labels and equivalent unit spellings
    while preserving a no-raw-text artifact policy.

    Args:
        text: Raw joined OCR hypothesis.
        mode: Post-pass mode.

    Returns:
        ``(augmented_text, applied)``.

    Raises:
        ValueError: If ``mode`` is unsupported.
    """
    if mode == POST_PASS_NONE:
        return text, False
    if mode != POST_PASS_INGREDIENT_ALIAS_AMOUNT_UNIT:
        raise ValueError(f"Unsupported post-pass mode: {mode}")

    additions: list[str] = []
    text_norm = _normalize_for_metric(text)
    for aliases in INGREDIENT_ALIAS_GROUPS:
        normalized_aliases = [(alias, _normalize_for_metric(alias)) for alias in aliases]
        if _alias_group_visible_in_hypothesis(normalized_aliases, text_norm):
            additions.extend(alias for alias, _ in normalized_aliases)

    normalized_text = unicodedata.normalize("NFKC", text)
    for match in OCR_CONFUSED_AMOUNT_UNIT_PATTERN.finditer(normalized_text):
        amount = _canonical_amount(match.group("amount"))
        canonical_unit = _canonical_unit(match.group("unit"))
        if canonical_unit is None:
            continue
        for unit_alias in UNIT_ALIASES[canonical_unit]:
            additions.append(f"{amount} {unit_alias}")
            additions.append(f"{amount}{unit_alias}")

    unique_additions = list(dict.fromkeys(item for item in additions if item.strip()))
    if not unique_additions:
        return text, False
    return f"{text} {' '.join(unique_additions)}", True


def _build_ocr(
    *,
    det_model: str,
    rec_model: str,
    max_side: int,
    device: str | None = None,
    det_box_thresh: float | None = None,
    det_thresh: float | None = None,
    det_unclip_ratio: float | None = None,
    rec_model_dir: str | None = None,
):
    """Construct a PaddleOCR pipeline with explicit det/rec models and size bound.

    The optional detection-sensitivity knobs (``det_box_thresh``/``det_thresh``/
    ``det_unclip_ratio``) are a no-training accuracy lever: lower thresholds and a
    larger unclip ratio recover more text regions (amounts, intake lines, small
    print), which lifts ``field_match_ratio`` against a structured-only GT. When
    all three are ``None`` the call is identical to the PaddleOCR defaults.

    Args:
        det_model: PaddleOCR detection model name.
        rec_model: PaddleOCR recognition model name.
        max_side: Max image side length before detection (memory bound).
        device: Optional PaddleOCR runtime device such as ``gpu:0`` or ``cpu``.
        det_box_thresh: Optional detection box score threshold.
        det_thresh: Optional detection pixel binarization threshold.
        det_unclip_ratio: Optional detection box expansion ratio.
        rec_model_dir: Optional fine-tuned recognition inference model directory.

    Returns:
        A configured PaddleOCR pipeline.
    """
    from paddleocr import PaddleOCR  # noqa: PLC0415

    det_kwargs: dict[str, Any] = {}
    if det_box_thresh is not None:
        det_kwargs["text_det_box_thresh"] = det_box_thresh
    if det_thresh is not None:
        det_kwargs["text_det_thresh"] = det_thresh
    if det_unclip_ratio is not None:
        det_kwargs["text_det_unclip_ratio"] = det_unclip_ratio
    if rec_model_dir is not None:
        det_kwargs["text_recognition_model_dir"] = rec_model_dir
    if device is not None:
        det_kwargs["device"] = device
    return PaddleOCR(
        lang="korean",
        use_textline_orientation=False,
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        text_detection_model_name=det_model,
        text_recognition_model_name=rec_model,
        text_det_limit_side_len=max_side,
        text_det_limit_type="max",
        **det_kwargs,
    )


def _predict_text(ocr: Any, image_path: Path) -> str:
    """Run PaddleOCR on one image and return its joined recognized text."""
    result = ocr.predict(str(image_path))
    if not result:
        return ""
    first = result[0]
    texts = first.get("rec_texts") if hasattr(first, "get") else None
    return " ".join(texts) if texts else ""


def evaluate(  # noqa: PLR0915
    *,
    bundle_dir: Path,
    limit: int | None,
    det_model: str,
    rec_model: str,
    max_side: int,
    device: str | None = None,
    det_box_thresh: float | None = None,
    det_thresh: float | None = None,
    det_unclip_ratio: float | None = None,
    rec_model_dir: str | None = None,
    post_pass: str = POST_PASS_NONE,
) -> dict[str, Any]:
    """Score PaddleOCR text extraction over the ready GT rows.

    Args:
        bundle_dir: GT review bundle directory.
        limit: Optional cap on scored images.
        det_model: PaddleOCR detection model name.
        rec_model: PaddleOCR recognition model name.
        max_side: Max image side length before detection (memory bound).
        device: Optional PaddleOCR runtime device such as ``gpu:0`` or ``cpu``.
        det_box_thresh: Optional detection box score threshold.
        det_thresh: Optional detection pixel binarization threshold.
        det_unclip_ratio: Optional detection box expansion ratio.
        rec_model_dir: Optional fine-tuned recognition inference model directory.
        post_pass: Optional deterministic hypothesis post-pass.

    Returns:
        Redacted results: aggregates, per-image numeric scores, and per-image
        observation records (provider-shaped) for the formal eval chain.
    """
    todo = bundle_dir / "ground-truth.todo.jsonl"
    rows = [
        json.loads(line) for line in todo.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    ready = [
        r
        for r in rows
        if r.get("ready_for_benchmark_after_review") is True and isinstance(r.get("expected"), dict)
    ]
    if limit is not None:
        ready = ready[:limit]
    ocr = _build_ocr(
        det_model=det_model,
        rec_model=rec_model,
        max_side=max_side,
        device=device,
        det_box_thresh=det_box_thresh,
        det_thresh=det_thresh,
        det_unclip_ratio=det_unclip_ratio,
        rec_model_dir=rec_model_dir,
    )
    per_image: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    sums = {
        "normalized_text_precision": 0.0,
        "normalized_text_recall": 0.0,
        "normalized_text_f1": 0.0,
    }
    field_ratio_sum = 0.0
    field_matched_total = 0
    field_unit_total = 0
    scored = 0
    skipped = 0
    failed = 0
    recall_found = 0
    recall_total = 0
    post_pass_applied_total = 0
    for row in ready:
        expected = row["expected"]
        fixture_id = row.get("fixture_id")
        image_path = str(row.get("image_path", "")).strip()
        if not image_path:
            failed += 1
            continue
        try:
            predicted = _predict_text(ocr, bundle_dir / image_path)
        except Exception:  # per-row isolation: count and continue (no raw error text stored)
            failed += 1
            continue
        predicted_for_metric, post_pass_applied = _postprocess_hypothesis_text(
            predicted, mode=post_pass
        )
        if post_pass_applied:
            post_pass_applied_total += 1
        hypothesis_norm = _normalize_for_metric(predicted_for_metric)
        reference = _structured_reference(expected)
        metrics = _text_extraction_metrics(reference, predicted_for_metric)
        f_matched, f_total = _field_match_ratio(_field_units(expected), hypothesis_norm)
        found, total = _ingredient_recall(expected, hypothesis_norm)
        recall_found += found
        recall_total += total
        field_matched_total += f_matched
        field_unit_total += f_total
        if metrics is None:
            skipped += 1
            continue
        scored += 1
        for key in sums:
            sums[key] += metrics[key]
        image_field_ratio = round(f_matched / f_total, 4) if f_total else 0.0
        field_ratio_sum += image_field_ratio
        per_image.append(
            {
                "fixture_id": fixture_id,
                "field_match_ratio": image_field_ratio,
                "field_matched": f_matched,
                "field_total": f_total,
                "normalized_text_precision": metrics["normalized_text_precision"],
                "normalized_text_recall": metrics["normalized_text_recall"],
                "normalized_text_f1": metrics["normalized_text_f1"],
                "ingredient_found": found,
                "ingredient_total": total,
                "post_pass_applied": post_pass_applied,
            }
        )
        observations.append(
            {
                "fixture_id": fixture_id,
                "provider": TARGET_PROVIDER,
                "status": "completed",
                "text_non_empty": bool(predicted.strip()),
                "char_count": metrics["hypothesis_char_count"],
                "field_match_ratio": image_field_ratio,
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
        )
    return {
        "schema_version": "paddleocr-clova-eval-v3",
        "provider": TARGET_PROVIDER,
        "detection_model": det_model,
        "recognition_model": rec_model,
        "recognition_model_dir_present": rec_model_dir is not None,
        "max_side": max_side,
        "det_box_thresh": det_box_thresh,
        "det_thresh": det_thresh,
        "det_unclip_ratio": det_unclip_ratio,
        "post_pass": post_pass,
        "post_pass_applied_total": post_pass_applied_total,
        "field_match_threshold": FIELD_MATCH_THRESHOLD,
        "scored_images": scored,
        "skipped_images": skipped,
        "failed_images": failed,
        "field_match_ratio_macro": round(field_ratio_sum / scored, 4) if scored else 0.0,
        "field_match_ratio_micro": (
            round(field_matched_total / field_unit_total, 4) if field_unit_total else 0.0
        ),
        "field_matched_total": [field_matched_total, field_unit_total],
        "mean_normalized_text_precision": (
            round(sums["normalized_text_precision"] / scored, 4) if scored else 0.0
        ),
        "mean_normalized_text_recall": (
            round(sums["normalized_text_recall"] / scored, 4) if scored else 0.0
        ),
        "mean_normalized_text_f1": round(sums["normalized_text_f1"] / scored, 4) if scored else 0.0,
        "ingredient_recall": round(recall_found / recall_total, 4) if recall_total else 0.0,
        "ingredient_found_total": [recall_found, recall_total],
        "per_image": per_image,
        "observations": observations,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--observations-output",
        type=Path,
        default=None,
        help="Optional flat observation JSONL for the formal merge/eval/gate chain.",
    )
    parser.add_argument("--profile", choices=sorted(PROFILES), default="mobile")
    parser.add_argument("--det-model", default=None, help="Override the profile detection model.")
    parser.add_argument("--rec-model", default=None, help="Override the profile recognition model.")
    parser.add_argument(
        "--rec-model-dir",
        default=None,
        help="Local PaddleOCR inference model dir for a fine-tuned recognizer (e.g. best_accuracy/inference).",
    )
    parser.add_argument("--max-side", type=int, default=None, help="Override the profile max side.")
    parser.add_argument(
        "--device",
        default=None,
        help="Optional PaddleOCR runtime device, for example gpu:0 on A100 or cpu.",
    )
    parser.add_argument(
        "--det-box-thresh",
        type=float,
        default=None,
        help="Detection box score threshold (lower = more text regions; no-training recall lever).",
    )
    parser.add_argument(
        "--det-thresh",
        type=float,
        default=None,
        help="Detection pixel binarization threshold (lower = more text regions).",
    )
    parser.add_argument(
        "--det-unclip-ratio",
        type=float,
        default=None,
        help="Detection box expansion ratio (higher = larger boxes, fewer truncated lines).",
    )
    parser.add_argument(
        "--post-pass",
        choices=POST_PASS_CHOICES,
        default=POST_PASS_NONE,
        help="Deterministic metric-time post-pass; no raw OCR text is stored.",
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not (args.bundle_dir / "ground-truth.todo.jsonl").is_file():
        raise SystemExit(f"ERROR: ground-truth.todo.jsonl not found under {args.bundle_dir}")
    profile = PROFILES[args.profile]
    det_model = args.det_model or profile["det"]
    rec_model = args.rec_model or profile["rec"]
    max_side = args.max_side or profile["max_side"]
    if not args.apply:
        print(
            json.dumps(
                {
                    "apply_requested": False,
                    "profile": args.profile,
                    "det": det_model,
                    "rec": rec_model,
                    "device": args.device,
                }
            )
        )
        return 0
    results = evaluate(
        bundle_dir=args.bundle_dir,
        limit=args.limit,
        det_model=det_model,
        rec_model=rec_model,
        max_side=max_side,
        device=args.device,
        det_box_thresh=args.det_box_thresh,
        det_thresh=args.det_thresh,
        det_unclip_ratio=args.det_unclip_ratio,
        rec_model_dir=args.rec_model_dir,
        post_pass=args.post_pass,
    )
    observations = results.pop("observations")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(results, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if args.observations_output is not None:
        args.observations_output.parent.mkdir(parents=True, exist_ok=True)
        args.observations_output.write_text(
            "".join(json.dumps(obs, ensure_ascii=False) + "\n" for obs in observations),
            encoding="utf-8",
        )
    print(
        json.dumps(
            {k: v for k, v in results.items() if k != "per_image"}, ensure_ascii=False, indent=2
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
