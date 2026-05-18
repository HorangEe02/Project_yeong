"""LLM 구조화 출력 Pydantic v2 스키마.

Ollama의 ``format=`` 인자로 ``ParsedSupplement.model_json_schema()`` 를 전달한다.

Reference:
    /Users/yeong/.claude/plans/lemon-track-b/phase-02-ollama-llm-safety.md Step 2
    docs/dev-guides/08-llm-supplement-parsing.md §2
    backend/CLAUDE.md Pattern 2
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ParsedIngredient(BaseModel):
    """LLM이 파싱한 단일 성분.

    Attributes:
        name_ko: 한국어 성분명 (라벨 그대로).
        name_en: 영어 성분명 (있으면).
        amount: 라벨에 표시된 수치 (≥ 0).
        unit: 단위 (mg, μg, IU, g 등 라벨 그대로).
    """

    model_config = ConfigDict(frozen=True)

    name_ko: str = Field(..., min_length=1)
    name_en: str | None = None
    amount: float = Field(..., ge=0)
    unit: str = Field(..., min_length=1)


class ParsedServingSize(BaseModel):
    """1회 제공량.

    Attributes:
        amount: 제공량 수치 (≥ 0).
        unit: 제공 형태 — ``tablet``, ``capsule``, ``ml``, ``g`` 중 하나.
    """

    model_config = ConfigDict(frozen=True)

    amount: float = Field(..., ge=0)
    unit: str = Field(..., pattern=r"^(tablet|capsule|ml|g)$")


class ParsedSupplement(BaseModel):
    """LLM이 라벨에서 추출한 전체 영양제 정보.

    Attributes:
        product_name: 제품명 (없으면 ``None``).
        manufacturer: 제조사 (없으면 ``None``).
        serving_size: 1회 제공량 (없으면 ``None``).
        ingredients: 성분 리스트. 0개 가능.
        warnings: 라벨에 명시된 경고 텍스트 (임산부 주의 등). 0개 가능.
        raw_text: 호출처가 ``model_copy`` 로 채우는 원본 OCR 텍스트.
        engine: 호출처가 채우는 LLM 엔진 식별자.
    """

    model_config = ConfigDict(frozen=True)

    product_name: str | None = None
    manufacturer: str | None = None
    serving_size: ParsedServingSize | None = None
    ingredients: list[ParsedIngredient] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    raw_text: str = ""
    engine: str = ""
