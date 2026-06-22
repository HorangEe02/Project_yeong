"""Drop non-ingredient entries from OCR pattern-fallback candidates.

The OCR pattern fallback (``_extract_ocr_pattern_ingredient_candidates``) mines
name/amount rows from raw OCR text. On dense nutrition-facts tables it also picks up
table headers (영양성분; "기준치에 대한 비율" → split fragments 기준치에 / 대한 / 비율),
label boilerplate (별도, 표기일까지, 품목보고번호), bare units (g, kcal, "g)"), and
ultra-short OCR noise (MI, CA). These are never real ingredients and must not reach the
confirmation UI as supplement components.

This filter is applied ONLY to the low-confidence pattern-fallback candidates — the
LLM-structured ingredients bypass it. It is deliberately CONSERVATIVE: it drops exact
header/boilerplate/unit tokens and 1-2 character Latin OCR fragments, but KEEPS every
real nutrient (탄수화물 / 단백질 / 나트륨 / 콜레스테롤 / 트랜스지방 / 비타민… and English
ones like SUGAR / IRON / ZINC), since dropping a real ingredient is worse than leaving
a rare noise token.
"""

from __future__ import annotations

import re
from typing import Any

# Exact (normalized) non-ingredient names: nutrition-facts headers, the
# "기준치에 대한 비율" phrase and its OCR split fragments, label boilerplate, bare units,
# and energy metrics. Real nutrients are intentionally NOT listed.
_NON_INGREDIENT_NAMES: frozenset[str] = frozenset(
    {
        # nutrition-facts headers + "기준치에 대한 비율" split fragments
        "영양성분",
        "영양정보",
        "영양성분정보",
        "기능정보",
        "기준치",
        "기준치에",
        "대한",
        "비율",
        "기준치에 대한 비율",
        "1일 영양성분 기준치",
        "1일영양성분기준치",
        "일일기준치",
        "내용량",
        "총 내용량",
        "총내용량",
        "1회 제공량",
        "1회제공량",
        "제공량",
        "1회 분량",
        "원재료명",
        "원재료",
        "성분명",
        "함량",
        "단위",
        "구분",
        # label boilerplate
        "별도",
        "별도표기",
        "표기일",
        "표기일까지",
        "품목보고번호",
        "유통기한",
        "소비기한",
        "제조번호",
        "보관방법",
        "섭취방법",
        "주의사항",
        "제조원",
        "판매원",
        # bare units / measure words
        "g",
        "mg",
        "mcg",
        "ug",
        "µg",
        "kg",
        "ml",
        "l",
        "iu",
        "kcal",
        "%",
        "g 당",
        "g당",
        # energy metrics (not an ingredient)
        "열량",
        "칼로리",
        "energy",
        "calories",
        "calorie",
        # english nutrition-facts headers
        "nutrition facts",
        "supplement facts",
        "amount per serving",
        "daily value",
        "% daily value",
        "serving size",
        "servings per container",
        "per serving",
        "per scoop",
    }
)


def _normalize(name: str) -> str:
    """Lowercase, strip trailing punctuation (e.g. ``g)`` -> ``g``), and collapse spaces."""
    text = name.strip().lower()
    text = re.sub(r"[)\].,;:·]+$", "", text)
    return re.sub(r"\s+", " ", text).strip()


def is_non_ingredient_candidate(candidate: dict[str, Any]) -> bool:
    """Return True when a pattern-fallback candidate is a label header / unit / OCR noise.

    Conservative: only nameless candidates, exact header/boilerplate/unit matches, and
    1-2 character pure-Latin OCR fragments (e.g. ``MI``, ``CA``) are rejected. Real
    nutrient names — Korean or English, any length >= 3 — are always kept.
    """
    name = candidate.get("display_name") or candidate.get("original_name")
    if not isinstance(name, str) or not name.strip():
        return True
    if _normalize(name) in _NON_INGREDIENT_NAMES:
        return True
    # Ultra-short pure-Latin OCR fragments (MI, CA) are never real ingredient names;
    # 3+ char Latin words (SUGAR, IRON, ZINC, MSM, EPA) are preserved.
    return bool(re.fullmatch(r"[A-Za-z]{1,2}", name.strip()))


def filter_non_ingredient_ocr_fallback_candidates(
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Drop non-ingredient (header / unit / noise) entries from pattern-fallback candidates."""
    return [
        candidate
        for candidate in candidates
        if isinstance(candidate, dict) and not is_non_ingredient_candidate(candidate)
    ]
