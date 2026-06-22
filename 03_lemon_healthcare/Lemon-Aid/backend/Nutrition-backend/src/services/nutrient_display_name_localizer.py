"""Deterministic English->Korean localization of supplement ingredient display names.

For the Korean-market launch, English-language OCR'd supplement labels surface
English ingredient names (e.g. "Iodine", "Riboflavin"). This module rewrites each
ingredient candidate's ``display_name`` to its standard Korean name while preserving
the English source in ``original_name``, so the app can render ``한글(영문)`` (e.g.
"요오드(Iodine)") via the existing display formatters.

Design constraints:
- Deterministic: a curated English->Korean map (no LLM, no latency, fully testable).
  This is intentionally separate from the best-effort LLM section-text localizer
  (``supplement_label_localizer``) because nutrient names are a closed, standard
  vocabulary that an LLM translates unreliably.
- Non-destructive: ``original_name`` (the English source) is preserved (and back-filled
  from ``display_name`` when missing) so vision-amount matching / dedup (which fall back
  to ``original_name``) and the ``한글(영문)`` render keep the English component.
- Korean-dominant names are left untouched (Korean labels are already localized).
- Only names present in the map are translated; unknown names keep their English text.

The base vocabulary is sourced from ``data/nutrition_reference/kdris/kdris_2025.csv``
(``nutrient_name_en`` -> ``nutrient_name_ko``); supplement-specific ingredients and
common synonyms not covered by KDRIs are curated below.
"""

from __future__ import annotations

import re
from typing import Any

_HANGUL_START = "가"
_HANGUL_END = "힣"

# Minimum ASCII letters before a name is considered English-worth-translating
# (skips bare units / already-Korean text with a stray Latin token).
_MIN_LATIN_LETTERS = 2

# English (normalized, lowercase) -> standard Korean nutrient/ingredient name.
# Keys MUST be in the form produced by ``_normalize_en`` (lowercase, parentheticals
# dropped, punctuation collapsed).
_EN_TO_KO: dict[str, str] = {
    # --- KDRIs 2025 nutrients (data/nutrition_reference/kdris/kdris_2025.csv) ---
    "alpha-linolenic acid": "알파-리놀렌산",
    "biotin": "비오틴",
    "calcium": "칼슘",
    "carbohydrate": "탄수화물",
    "chloride": "염소",
    "cholesterol": "콜레스테롤",
    "choline": "콜린",
    "chromium": "크롬",
    "copper": "구리",
    "dietary fiber": "식이섬유",
    "energy": "에너지",
    "fat": "지질",
    "fluoride": "불소",
    "folate": "엽산",
    "histidine": "히스티딘",
    "iodine": "요오드",
    "iron": "철",
    "isoleucine": "이소류신",
    "leucine": "류신",
    "linoleic acid": "리놀레산",
    "lysine": "라이신",
    "magnesium": "마그네슘",
    "manganese": "망간",
    "molybdenum": "몰리브덴",
    "niacin": "니아신",
    "pantothenic acid": "판토텐산",
    "phosphorus": "인",
    "potassium": "칼륨",
    "protein": "단백질",
    "riboflavin": "리보플라빈",
    "selenium": "셀레늄",
    "sodium": "나트륨",
    "thiamin": "티아민",
    "threonine": "트레오닌",
    "tryptophan": "트립토판",
    "valine": "발린",
    "vitamin a": "비타민 A",
    "vitamin b12": "비타민 B12",
    "vitamin b6": "비타민 B6",
    "vitamin c": "비타민 C",
    "vitamin d": "비타민 D",
    "vitamin e": "비타민 E",
    "vitamin k": "비타민 K",
    "water": "수분",
    "zinc": "아연",
    # --- common synonyms / alternate spellings of the above ---
    "thiamine": "티아민",
    "vitamin b1": "티아민",
    "vitamin b2": "리보플라빈",
    "vitamin b3": "니아신",
    "niacinamide": "니아신",
    "nicotinamide": "니아신",
    "vitamin b5": "판토텐산",
    "pantothenate": "판토텐산",
    "vitamin b7": "비오틴",
    "vitamin b9": "엽산",
    "folic acid": "엽산",
    "folacin": "엽산",
    "ascorbic acid": "비타민 C",
    "pyridoxine": "비타민 B6",
    "cobalamin": "비타민 B12",
    "cyanocobalamin": "비타민 B12",
    "methylcobalamin": "비타민 B12",
    "cholecalciferol": "비타민 D",
    "vitamin d3": "비타민 D",
    "vitamin d2": "비타민 D",
    "ergocalciferol": "비타민 D",
    "tocopherol": "비타민 E",
    "alpha-tocopherol": "비타민 E",
    "d-alpha-tocopherol": "비타민 E",
    "phylloquinone": "비타민 K",
    "vitamin k1": "비타민 K",
    "vitamin k2": "비타민 K2",
    "menaquinone": "비타민 K2",
    # --- common supplement ingredients not in KDRIs ---
    "lutein": "루테인",
    "zeaxanthin": "지아잔틴",
    "lutein + zeaxanthin": "루테인+지아잔틴",
    "beta-carotene": "베타카로틴",
    "beta carotene": "베타카로틴",
    "omega-3": "오메가-3",
    "omega 3": "오메가-3",
    "omega-3 fatty acids": "오메가-3",
    "fish oil": "어유",
    "coenzyme q10": "코엔자임Q10",
    "coenzyme q-10": "코엔자임Q10",
    "coq10": "코엔자임Q10",
    "ubiquinone": "코엔자임Q10",
    "collagen": "콜라겐",
    "milk thistle": "밀크씨슬",
    "silymarin": "실리마린",
    "ginkgo": "은행잎추출물",
    "ginkgo biloba": "은행잎추출물",
    "glucosamine": "글루코사민",
    "chondroitin": "콘드로이친",
    "msm": "MSM",
    "methylsulfonylmethane": "MSM",
    "probiotics": "프로바이오틱스",
    "lactobacillus": "유산균",
    "saw palmetto": "쏘팔메토",
    "creatine": "크레아틴",
    "taurine": "타우린",
    "theanine": "테아닌",
    "l-theanine": "테아닌",
    "arginine": "아르기닌",
    "l-arginine": "아르기닌",
    "carnitine": "카르니틴",
    "l-carnitine": "카르니틴",
    "glutamine": "글루타민",
    "l-glutamine": "글루타민",
    "inositol": "이노시톨",
    "lecithin": "레시틴",
    "spirulina": "스피루리나",
}


def _normalize_en(name: str) -> str:
    """Normalize an English ingredient name into a map lookup key.

    Lowercases, drops parenthetical qualifiers (e.g. ``(DFE)``), keeps alphanumerics
    plus ``+``/``-`` (for compounds like ``omega-3``), and collapses whitespace.

    Args:
        name: Raw ingredient name.

    Returns:
        Normalized lookup key (possibly empty).
    """
    text = name.strip().lower()
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"[^a-z0-9+\- ]", " ", text)
    text = re.sub(r"\s*\+\s*", " + ", text)
    return re.sub(r"\s+", " ", text).strip()


def is_english_dominant(text: str) -> bool:
    """Return whether the name is Latin-dominant (a foreign-language name worth localizing)."""
    latin = sum(1 for char in text if char.isascii() and char.isalpha())
    hangul = sum(1 for char in text if _HANGUL_START <= char <= _HANGUL_END)
    return latin >= _MIN_LATIN_LETTERS and latin > hangul


def korean_display_name(english_name: str) -> str | None:
    """Return the standard Korean name for an English ingredient name, or None.

    Args:
        english_name: English ingredient/nutrient name (any case/spacing).

    Returns:
        The Korean name when known, else None.
    """
    key = _normalize_en(english_name)
    if not key:
        return None
    return _EN_TO_KO.get(key)


def localize_ingredient_display_names(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Rewrite English ingredient ``display_name`` values to Korean (in place).

    For each ingredient candidate whose ``display_name`` is English-dominant and maps
    to a known Korean name, set ``display_name`` to the Korean name and ensure the
    English source survives in ``original_name`` (back-filled from the prior
    ``display_name`` when ``original_name`` is missing). Unknown / already-Korean names
    are left unchanged.

    Args:
        snapshot: Parsed supplement snapshot (mutated and returned).

    Returns:
        The same snapshot, with English ingredient names localized to Korean.
    """
    candidates = snapshot.get("ingredient_candidates")
    if not isinstance(candidates, list):
        return snapshot
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        display_name = candidate.get("display_name")
        if not isinstance(display_name, str) or not display_name.strip():
            continue
        if not is_english_dominant(display_name):
            continue
        korean = korean_display_name(display_name)
        if not korean or korean == display_name:
            continue
        original_name = candidate.get("original_name")
        if not isinstance(original_name, str) or not original_name.strip():
            candidate["original_name"] = display_name
        candidate["display_name"] = korean
    return snapshot
