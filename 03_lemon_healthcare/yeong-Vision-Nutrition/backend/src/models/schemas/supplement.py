"""Supplement API 입출력 Pydantic 스키마.

Reference:
    /Users/yeong/.claude/plans/lemon-track-b/phase-05-api-integration.md Step 3
    docs/dev-guides/09-supplement-registration-api.md §1
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.models.schemas.nutrition import DiagnosisResult


class IngredientResponse(BaseModel):
    """응답에 포함되는 단일 성분."""

    model_config = ConfigDict(frozen=True)

    code: str
    name_ko: str
    amount: float = Field(..., ge=0)
    unit: str


class SupplementRegisterResponse(BaseModel):
    """``POST /api/v1/supplements/register`` 응답.

    Attributes:
        supplement_id: DB row UUID.
        ingredients: MFDS 매칭에 성공한 성분 리스트.
        unmatched_ingredient_names: LLM 이 파싱했지만 표준 코드로 매핑되지 않은
            성분의 한국어 이름 — 사용자에게 "인식되지 않은 성분" 으로 표시 가능.
        diagnosis: KDRIs 기반 진단 결과.
        disclaimers: docs/10 §2.3 표준 면책 문구.
        emergency_resources: docs/10 §11.1 공공 상담 자원.
        consult_professional_message_ko: 약사·의료진 상담 안내.
    """

    model_config = ConfigDict(frozen=True)

    supplement_id: UUID
    product_name: str | None
    manufacturer: str | None
    ingredients: list[IngredientResponse]
    unmatched_ingredient_names: list[str]
    diagnosis: DiagnosisResult
    ocr_engine: str
    llm_engine: str
    elapsed_ms: float = Field(..., ge=0)
    disclaimers: list[str]
    emergency_resources: list[dict[str, str]]
    consult_professional_message_ko: str
