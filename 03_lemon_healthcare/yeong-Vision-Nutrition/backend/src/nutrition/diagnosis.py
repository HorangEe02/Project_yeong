"""부족·과다·위험 영양소 진단.

``intakes`` 와 ``UserKDRIsContext`` 를 받아 ``DiagnosisResult`` 를 산출한다.
모든 메시지는 ``safety.forbidden_terms`` 의 의료법 표현 가이드를 통과한다.

Reference:
    /Users/yeong/.claude/plans/lemon-track-b/phase-03-nutrition-data.md Step 10
    docs/07-core-algorithm.md §4.3
    docs/10-compliance-checklist.md §10
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Final

from src.models.schemas.nutrition import (
    DiagnosisResult,
    NutrientDiagnosis,
    NutrientIntake,
    NutrientStatus,
    UserKDRIsContext,
)
from src.nutrition.kdris import lookup_kdris
from src.safety.forbidden_terms import assert_no_forbidden_terms

logger = logging.getLogger(__name__)

NUTRIENT_CODES_PATH: Final[Path] = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "data"
    / "reference"
    / "nutrient_codes.json"
)

DEFICIENT_THRESHOLD: Final[float] = 0.35
LOW_THRESHOLD: Final[float] = 0.7
EXCESSIVE_THRESHOLD: Final[float] = 1.3


@lru_cache(maxsize=1)
def _load_nutrient_names() -> dict[str, dict[str, str]]:
    with NUTRIENT_CODES_PATH.open("r", encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)
    return {k: v for k, v in data.items() if not k.startswith("_")}


def _name_ko(code: str) -> str:
    info = _load_nutrient_names().get(code)
    return info["name_ko"] if info else code


def _select_reference(row: dict[str, float | None]) -> float | None:
    """RDA → AI → EAR 우선순위로 reference 값을 선택."""
    for key in ("rda", "ai", "ear"):
        value = row.get(key)
        if value is not None and value > 0:
            return value
    return None


def _format_diagnosis_message(
    name_ko: str,
    status: NutrientStatus,
    ratio: float,
    ul: float | None,
) -> str:
    """진단 메시지 — 정량 + 비단정 표현 + 전문가 상담 안내."""
    pct = round(ratio * 100, 1)
    if status == NutrientStatus.RISKY and ul is not None:
        msg = (
            f"{name_ko} 섭취가 상한 기준의 {pct}% 수준입니다. "
            "과다 섭취 위험이 있을 수 있으니 전문가와 상담하세요."
        )
    elif status == NutrientStatus.EXCESSIVE:
        msg = (
            f"{name_ko} 섭취가 권장량의 {pct}% 수준으로 다소 높습니다. "
            "전문가와 상담을 권장합니다."
        )
    elif status == NutrientStatus.ADEQUATE:
        msg = f"{name_ko} 섭취가 권장량 수준입니다 ({pct}%)."
    elif status == NutrientStatus.LOW:
        msg = (
            f"{name_ko} 섭취가 권장량의 {pct}% 수준입니다. "
            "식단이나 보충을 늘리는 것을 고려해 보세요."
        )
    else:  # DEFICIENT
        msg = (
            f"{name_ko} 섭취가 권장량의 {pct}% 수준으로 매우 낮습니다. "
            "전문가와 상담하시기 바랍니다."
        )
    assert_no_forbidden_terms(msg, context="diagnose:message")
    return msg


def _build_summary(deficient: int, risky: int, adequate: int) -> str:
    """요약 메시지 — 항상 의료법 표현 가이드 통과."""
    parts: list[str] = []
    if deficient > 0:
        parts.append(f"부족 가능 영양소 {deficient}종")
    if risky > 0:
        parts.append(f"상한 초과 우려 {risky}종")
    if adequate > 0:
        parts.append(f"적정 범위 {adequate}종")
    if not parts:
        msg = "분석할 영양소가 확인되지 않았습니다. 다른 사진을 시도해 주세요."
    else:
        msg = "분석 결과: " + " · ".join(parts) + ". 자세한 권고는 전문가와 상담하세요."
    assert_no_forbidden_terms(msg, context="diagnose:summary")
    return msg


def diagnose(
    intakes: list[NutrientIntake],
    ctx: UserKDRIsContext,
) -> DiagnosisResult:
    """``intakes`` 와 KDRIs 룩업을 비교해 영양소별 status를 산출.

    Args:
        intakes: 사용자가 섭취한 영양소 리스트.
        ctx: 사용자 KDRIs 컨텍스트.

    Returns:
        ``DiagnosisResult`` — 영양소별 진단 + 카운트 + 요약 메시지.

    Raises:
        KDRIsCoverageError: ``ctx`` 에 매칭되는 KDRIs row가 전혀 없는 경우.
    """
    rdi_table = lookup_kdris(ctx)
    diagnoses: list[NutrientDiagnosis] = []

    for intake in intakes:
        row = rdi_table.get(intake.code)
        if row is None:
            logger.info("Skip diagnose — code not in KDRIs: %s", intake.code)
            continue

        reference = _select_reference(row)
        ul = row.get("ul")
        actual = intake.amount

        if ul is not None and ul > 0 and actual > ul:
            ratio = actual / ul
            status = NutrientStatus.RISKY
        elif reference is None:
            logger.info("Skip diagnose — no reference value for %s", intake.code)
            continue
        else:
            ratio = actual / reference
            if ratio > EXCESSIVE_THRESHOLD:
                status = NutrientStatus.EXCESSIVE
            elif ratio >= LOW_THRESHOLD:
                status = NutrientStatus.ADEQUATE
            elif ratio >= DEFICIENT_THRESHOLD:
                status = NutrientStatus.LOW
            else:
                status = NutrientStatus.DEFICIENT

        name_ko = _name_ko(intake.code)
        diagnoses.append(
            NutrientDiagnosis(
                code=intake.code,
                name_ko=name_ko,
                rda=row.get("rda"),
                ai=row.get("ai"),
                ear=row.get("ear"),
                ul=ul,
                actual=actual,
                unit=intake.unit,
                ratio=round(ratio, 2),
                status=status,
                message_ko=_format_diagnosis_message(name_ko, status, ratio, ul),
            )
        )

    deficient = sum(
        1 for d in diagnoses if d.status in (NutrientStatus.DEFICIENT, NutrientStatus.LOW)
    )
    risky = sum(1 for d in diagnoses if d.status == NutrientStatus.RISKY)
    adequate = sum(1 for d in diagnoses if d.status == NutrientStatus.ADEQUATE)

    return DiagnosisResult(
        diagnoses=diagnoses,
        deficient_count=deficient,
        risky_count=risky,
        adequate_count=adequate,
        summary_message_ko=_build_summary(deficient, risky, adequate),
    )
