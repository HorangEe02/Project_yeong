"""KDRIs 룩업 — ``data/kdris/kdris_2020.csv`` 에서 ctx 매칭 row를 조회한다.

KDRIs 2020 연령 브래킷은 명확히 정의되므로 임의 fallback 없이 ``ctx.age`` 가
``[age_min, age_max]`` 범위에 포함되는 단일 row를 선택한다. 데이터 결손 시
``KDRIsCoverageError`` 로 명시적 실패 — 조용히 인접 row를 끌어다 쓰지 않는다.

Reference:
    /Users/yeong/.claude/plans/lemon-track-b/phase-03-nutrition-data.md Step 7
    /Users/yeong/.claude/plans/ocr-yolo-sprightly-neumann.md §3.3 M1
"""

from __future__ import annotations

import csv
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Final

from src.models.schemas.nutrition import UserKDRIsContext

logger = logging.getLogger(__name__)

KDRIS_CSV_PATH: Final[Path] = (
    Path(__file__).resolve().parent.parent.parent.parent / "data" / "kdris" / "kdris_2020.csv"
)


class KDRIsCoverageError(LookupError):
    """``ctx`` 에 매칭되는 KDRIs row가 데이터셋에 존재하지 않을 때 발생."""


def _parse_float(value: str) -> float | None:
    return float(value) if value else None


def _parse_bool(value: str) -> bool:
    return value.strip().lower() == "true"


@lru_cache(maxsize=1)
def _load_rows() -> list[dict[str, Any]]:
    """KDRIs CSV 를 1회 로드하여 정규화된 dict 리스트로 반환."""
    if not KDRIS_CSV_PATH.is_file():
        raise FileNotFoundError(f"KDRIs CSV not found: {KDRIS_CSV_PATH}")
    rows: list[dict[str, Any]] = []
    with KDRIS_CSV_PATH.open("r", encoding="utf-8", newline="") as f:
        for raw in csv.DictReader(f):
            rows.append(
                {
                    "code": raw["code"],
                    "name_ko": raw["name_ko"],
                    "name_en": raw["name_en"],
                    "unit": raw["unit"],
                    "sex": raw["sex"],
                    "age_min": int(raw["age_min"]),
                    "age_max": int(raw["age_max"]),
                    "rda": _parse_float(raw["rda"]),
                    "ai": _parse_float(raw["ai"]),
                    "ear": _parse_float(raw["ear"]),
                    "ul": _parse_float(raw["ul"]),
                    "is_pregnant": _parse_bool(raw["is_pregnant"]),
                    "is_lactating": _parse_bool(raw["is_lactating"]),
                }
            )
    return rows


def _select_row_for_code(
    candidates: list[dict[str, Any]],
    ctx: UserKDRIsContext,
) -> dict[str, Any] | None:
    """한 영양소 코드의 후보 row들 중 ctx에 가장 부합하는 단일 row 선택.

    선택 우선순위 (모두 동시에 만족):
        1. ``ctx.is_pregnant`` → ``is_pregnant=true`` row 우선.
        2. ``ctx.is_lactating`` → ``is_lactating=true`` row 우선.
        3. ``sex`` 일치 + age 범위 포함 + 일반 row (pregnant/lactating 모두 false).

    Returns:
        매칭 row 또는 ``None``.
    """
    if ctx.is_pregnant:
        for r in candidates:
            if r["is_pregnant"]:
                return r
    if ctx.is_lactating:
        for r in candidates:
            if r["is_lactating"]:
                return r
    for r in candidates:
        if (
            r["sex"] == ctx.sex
            and r["age_min"] <= ctx.age <= r["age_max"]
            and not r["is_pregnant"]
            and not r["is_lactating"]
        ):
            return r
    return None


def lookup_kdris(ctx: UserKDRIsContext) -> dict[str, dict[str, float | None]]:
    """``ctx`` 에 맞는 영양소별 ``{rda, ai, ear, ul}`` 매핑을 반환.

    Args:
        ctx: 사용자 인구학 컨텍스트.

    Returns:
        ``{nutrient_code: {"rda": float|None, "ai": ..., "ear": ..., "ul": ...}}``.

    Raises:
        KDRIsCoverageError: 데이터셋에 ctx 에 매칭되는 row가 단 하나도 없는 경우.

    Examples:
        >>> ctx = UserKDRIsContext(age=30, sex="male")
        >>> table = lookup_kdris(ctx)  # doctest: +SKIP
        >>> "vitamin_c_mg" in table
        True
    """
    rows = _load_rows()
    by_code: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_code.setdefault(row["code"], []).append(row)

    result: dict[str, dict[str, float | None]] = {}
    for code, candidates in by_code.items():
        chosen = _select_row_for_code(candidates, ctx)
        if chosen is None:
            logger.info(
                "KDRIs row missing for code=%s ctx=%s — skipped",
                code,
                ctx.model_dump(),
            )
            continue
        result[code] = {key: chosen[key] for key in ("rda", "ai", "ear", "ul")}

    if not result:
        raise KDRIsCoverageError(
            f"No KDRIs rows match context: age={ctx.age}, sex={ctx.sex}, "
            f"is_pregnant={ctx.is_pregnant}, is_lactating={ctx.is_lactating}"
        )
    return result
