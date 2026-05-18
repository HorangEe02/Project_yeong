"""영양 분석 도메인 Pydantic v2 스키마 + Enum.

Reference:
    /Users/yeong/.claude/plans/lemon-track-b/phase-03-nutrition-data.md Step 6
    docs/07-core-algorithm.md §4.3
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class NutrientStatus(StrEnum):
    """영양소 섭취 상태 분류.

    Reference:
        docs/07-core-algorithm.md §4.3
    """

    DEFICIENT = "deficient"
    """ratio < 0.35 — 매우 낮음."""
    LOW = "low"
    """0.35 ≤ ratio < 0.7 — 부족."""
    ADEQUATE = "adequate"
    """0.7 ≤ ratio ≤ 1.3 — 적정."""
    EXCESSIVE = "excessive"
    """ratio > 1.3 (UL 미만) — 다소 높음."""
    RISKY = "risky"
    """actual > UL — 상한 초과 위험."""


class NutrientIntake(BaseModel):
    """사용자의 단일 영양소 섭취량 — 영양제·식단·합산 어디서든 동일 구조."""

    model_config = ConfigDict(frozen=True)

    code: str = Field(..., pattern=r"^[a-z][a-z0-9_]+$")
    amount: float = Field(..., ge=0)
    unit: str = Field(..., min_length=1)
    source: Literal["supplement", "meal", "combined"] = "supplement"


class UserKDRIsContext(BaseModel):
    """KDRIs 룩업 컨텍스트 (사용자 인구학 정보).

    Attributes:
        age: 만 나이 (1~120).
        sex: 성별.
        is_pregnant: 임신부 여부 (해당 row 우선 매칭).
        is_lactating: 수유부 여부 (해당 row 우선 매칭).
    """

    model_config = ConfigDict(frozen=True)

    age: int = Field(..., ge=1, le=120)
    sex: Literal["male", "female"]
    is_pregnant: bool = False
    is_lactating: bool = False


class NutrientDiagnosis(BaseModel):
    """단일 영양소의 진단 결과."""

    model_config = ConfigDict(frozen=True)

    code: str
    name_ko: str
    rda: float | None = None
    ai: float | None = None
    ear: float | None = None
    ul: float | None = None
    actual: float = Field(..., ge=0)
    unit: str
    ratio: float = Field(..., ge=0)
    status: NutrientStatus
    message_ko: str


class DiagnosisResult(BaseModel):
    """전체 진단 결과 (영양소 리스트 + 요약 카운트)."""

    model_config = ConfigDict(frozen=True)

    diagnoses: list[NutrientDiagnosis]
    deficient_count: int = Field(..., ge=0)
    risky_count: int = Field(..., ge=0)
    adequate_count: int = Field(..., ge=0)
    summary_message_ko: str
