"""LLM 파싱 결과 (``ParsedIngredient``) 를 표준 영양소 코드로 매칭한다.

매칭 실패한 성분은 결과에서 제외되지만 호출처가 별도 리스트로 받아 사용자에게
"인식되지 않은 성분" 으로 표시할 수 있다.

Reference:
    /Users/yeong/.claude/plans/lemon-track-b/phase-03-nutrition-data.md Step 9
    docs/dev-guides/08-llm-supplement-parsing.md §7
"""

from __future__ import annotations

import csv
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Final

from src.llm.schemas import ParsedIngredient
from src.models.schemas.nutrition import NutrientIntake

logger = logging.getLogger(__name__)

MFDS_INGREDIENTS_PATH: Final[Path] = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "data"
    / "mfds"
    / "functional_ingredients.csv"
)

_NORMALIZE_RE: Final[re.Pattern[str]] = re.compile(r"[\s\-()·,/+]+")


def _normalize_name(name: str) -> str:
    """공백·괄호·구분자 제거 + 소문자."""
    if not name:
        return ""
    return _NORMALIZE_RE.sub("", name).lower()


@lru_cache(maxsize=1)
def _load_alias_map() -> dict[str, str]:
    """정규화된 alias → ``nutrient_code`` 매핑."""
    mapping: dict[str, str] = {}
    if not MFDS_INGREDIENTS_PATH.is_file():
        logger.warning("MFDS ingredients CSV not found: %s", MFDS_INGREDIENTS_PATH)
        return mapping
    with MFDS_INGREDIENTS_PATH.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            code = row["nutrient_code"].strip()
            if not code:
                continue
            ko_key = _normalize_name(row["ingredient_name_ko"])
            if ko_key:
                mapping[ko_key] = code
            en_name = row.get("ingredient_name_en", "")
            if en_name:
                en_key = _normalize_name(en_name)
                if en_key:
                    mapping[en_key] = code
            for alias in row.get("source_aliases", "").split("|"):
                normalized = _normalize_name(alias)
                if normalized:
                    mapping[normalized] = code
    return mapping


def match_to_nutrient_code(ingredient: ParsedIngredient) -> str | None:
    """``ParsedIngredient`` 를 표준 ``nutrient_code`` 로 매칭.

    Args:
        ingredient: LLM이 파싱한 단일 성분.

    Returns:
        매칭된 ``nutrient_code`` 또는 ``None`` (호출처가 unmatched 처리).

    Examples:
        >>> from src.llm.schemas import ParsedIngredient
        >>> ing = ParsedIngredient(name_ko="비타민 C", amount=1000, unit="mg")
        >>> match_to_nutrient_code(ing)
        'vitamin_c_mg'
    """
    mapping = _load_alias_map()
    ko_key = _normalize_name(ingredient.name_ko)
    if ko_key in mapping:
        return mapping[ko_key]
    if ingredient.name_en:
        en_key = _normalize_name(ingredient.name_en)
        if en_key in mapping:
            return mapping[en_key]
    logger.warning(
        "No nutrient code match for: ko=%r en=%r",
        ingredient.name_ko,
        ingredient.name_en,
    )
    return None


def to_nutrient_intakes(
    ingredients: list[ParsedIngredient],
) -> tuple[list[NutrientIntake], list[str]]:
    """``ParsedIngredient`` 리스트를 ``NutrientIntake`` 와 매칭 실패 이름으로 분리.

    Args:
        ingredients: LLM 파싱 결과.

    Returns:
        ``(intakes, unmatched_names)``. ``intakes`` 는 단위가 lowercase로 정규화되어
        있고 ``μ`` 는 ``u`` 로 치환된다.
    """
    intakes: list[NutrientIntake] = []
    unmatched: list[str] = []
    for ing in ingredients:
        code = match_to_nutrient_code(ing)
        if code is None:
            unmatched.append(ing.name_ko)
            continue
        unit = ing.unit.replace("μ", "u").lower()
        intakes.append(
            NutrientIntake(
                code=code,
                amount=ing.amount,
                unit=unit,
                source="supplement",
            )
        )
    return intakes, unmatched
