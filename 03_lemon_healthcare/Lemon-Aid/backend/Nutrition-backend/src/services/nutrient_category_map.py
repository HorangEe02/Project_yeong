"""Map nutrient codes / ingredient text to supplement ``category_key`` values.

Used to derive ``entity_keys`` for WIKI RAG entity-link boosting so supplement
explanations are grounded in the canonical wiki page for the relevant category
(e.g. nutrient ``magnesium_mg`` -> category ``마그네슘`` -> wiki
``mineral-supplements``). Pure/deterministic; no DB or network access.

The 43 ``supplement_categories.category_key`` values are ingredient-themed; only
nutrients/ingredients with a clear dedicated category are mapped (others yield no
entity key, and the retriever still returns semantic matches).
"""

from __future__ import annotations

import re
from collections.abc import Iterable

# Strip a trailing KDRIs unit suffix so ``calcium_mg`` and ``calcium`` both map.
_UNIT_SUFFIX_RE = re.compile(r"_(percent_energy|kcal|mcg|mg|ug|ml|iu|g)$")

# KDRIs nutrient base (unit-stripped) -> supplement category_key.
NUTRIENT_BASE_TO_CATEGORY_KEY: dict[str, str] = {
    "calcium": "칼슘",
    "iron": "철분",
    "zinc": "아연",
    "magnesium": "마그네슘",
    "vitamin_a": "비타민A",
    "vitamin_b6": "비타민B",
    "vitamin_b12": "비타민B",
    "niacin": "비타민B",
    "thiamin": "비타민B",
    "riboflavin": "비타민B",
    "pantothenic_acid": "비타민B",
    "biotin": "비타민B",
    "folate": "비타민B",
    "choline": "비타민B",
    "vitamin_c": "비타민C",
    "vitamin_d": "비타민D",
    "vitamin_e": "비타민E",
    "vitamin_k": "비타민K",
    "epa_dha": "오메가3",
    "epa": "오메가3",
    "dha": "오메가3",
    "alpha_linolenic_acid": "오메가3",
    "omega_3": "오메가3",
    "omega3": "오메가3",
    "protein": "단백질_프로틴",
    "leucine": "BCAA_EAA",
    "isoleucine": "BCAA_EAA",
    "valine": "BCAA_EAA",
    "lysine": "BCAA_EAA",
    "threonine": "BCAA_EAA",
    "tryptophan": "BCAA_EAA",
    "histidine": "BCAA_EAA",
    "methionine_cysteine": "BCAA_EAA",
    "phenylalanine_tyrosine": "BCAA_EAA",
    "fiber": "식이섬유",
    "dietary_fiber": "식이섬유",
}

# Ingredient-text keyword (lowercased substring) -> category_key, for the OCR
# analysis path which carries Korean/label ingredient text but no nutrient code.
INGREDIENT_KEYWORD_TO_CATEGORY_KEY: tuple[tuple[str, str], ...] = (
    ("마그네슘", "마그네슘"),
    ("칼슘", "칼슘"),
    ("철분", "철분"),
    ("아연", "아연"),
    ("오메가", "오메가3"),
    ("epa", "오메가3"),
    ("dha", "오메가3"),
    ("비타민a", "비타민A"),
    ("비타민b", "비타민B"),
    ("비타민c", "비타민C"),
    ("비타민d", "비타민D"),
    ("비타민e", "비타민E"),
    ("비타민k", "비타민K"),
    ("유산균", "유산균_프로바이오틱"),
    ("프로바이오틱", "유산균_프로바이오틱"),
    ("루테인", "루테인_눈"),
    ("콜라겐", "콜라겐"),
    ("코엔자임", "코엔자임Q10"),
    ("coq10", "코엔자임Q10"),
    ("큐텐", "코엔자임Q10"),
    ("msm", "관절_MSM_콘드로이친"),
    ("콘드로이친", "관절_MSM_콘드로이친"),
    ("글루코사민", "글루코사민"),
    ("밀크씨슬", "밀크씨슬_간"),
    ("실리마린", "밀크씨슬_간"),
    ("쏘팔메토", "남성_쏘팔메토"),
    ("은행잎", "뇌_은행잎"),
    ("징코", "뇌_은행잎"),
    ("멜라토닌", "수면_멜라토닌"),
    ("아쉬와간다", "스트레스_아쉬와간다"),
    ("프로폴리스", "프로폴리스_벌"),
    ("크레아틴", "크레아틴"),
    ("아르기닌", "아르기닌_시트룰린"),
    ("시트룰린", "아르기닌_시트룰린"),
    ("커큐민", "강황_커큐민"),
    ("강황", "강황_커큐민"),
    ("타우린", "HMB_타우린"),
    ("hmb", "HMB_타우린"),
    ("bcaa", "BCAA_EAA"),
    ("eaa", "BCAA_EAA"),
    ("단백질", "단백질_프로틴"),
    ("프로틴", "단백질_프로틴"),
    ("식이섬유", "식이섬유"),
    ("스피루리나", "스피루리나_클로렐라"),
    ("클로렐라", "스피루리나_클로렐라"),
    ("낫토", "혈관_낫토_폴리코사놀"),
    ("폴리코사놀", "혈관_낫토_폴리코사놀"),
    ("멀티비타민", "멀티비타민"),
    ("종합비타민", "종합영양제"),
    ("카페인", "카페인_각성"),
    ("아사이", "아사이_베리류"),
)


def allowed_supplement_category_keys() -> tuple[str, ...]:
    """Return the deduplicated set of mappable supplement ``category_key`` values.

    The values of :data:`NUTRIENT_BASE_TO_CATEGORY_KEY` and
    :data:`INGREDIENT_KEYWORD_TO_CATEGORY_KEY` together enumerate every category
    key this codebase can derive from a nutrient code or ingredient text. They are
    used as the closed allow-list for the local Gemma vision label transcription
    pass so the model can only choose an existing curated category, never invent
    one. First-seen order is preserved for stable prompts and tests.

    Returns:
        First-seen-ordered, deduplicated tuple of allowed category keys.
    """
    seen: dict[str, None] = {}
    for key in NUTRIENT_BASE_TO_CATEGORY_KEY.values():
        seen.setdefault(key, None)
    for _, key in INGREDIENT_KEYWORD_TO_CATEGORY_KEY:
        seen.setdefault(key, None)
    return tuple(seen)


def _strip_unit(code: str) -> str:
    """Return a nutrient code with its trailing KDRIs unit suffix removed."""
    return _UNIT_SUFFIX_RE.sub("", code.strip().lower())


def category_keys_for_nutrient_codes(codes: Iterable[str]) -> tuple[str, ...]:
    """Return deduplicated category keys for KDRIs nutrient codes.

    Args:
        codes: Nutrient codes, with or without a unit suffix (``calcium_mg``).

    Returns:
        First-seen-ordered category keys with a clear dedicated category.
    """
    seen: dict[str, None] = {}
    for code in codes:
        if not code:
            continue
        key = NUTRIENT_BASE_TO_CATEGORY_KEY.get(_strip_unit(code))
        if key:
            seen.setdefault(key, None)
    return tuple(seen)


def category_keys_for_ingredient_texts(texts: Iterable[str]) -> tuple[str, ...]:
    """Return deduplicated category keys for free-form ingredient texts.

    Args:
        texts: Ingredient display/original names (Korean or label text).

    Returns:
        First-seen-ordered category keys whose keyword appears in any text.
    """
    seen: dict[str, None] = {}
    for text in texts:
        if not text:
            continue
        lowered = text.lower()
        for keyword, key in INGREDIENT_KEYWORD_TO_CATEGORY_KEY:
            if keyword in lowered:
                seen.setdefault(key, None)
    return tuple(seen)
