"""만성질환-영양제 매트릭스 Pydantic schema.

``data/nutrition_reference/chronic_disease_supplement_matrix.json`` 의 정적
매핑 파일을 검증·로드하기 위한 모델. 페르소나 B형(만성질환자) 시나리오에서
카테고리별로 어떤 만성질환에 어느 정도 증거가 있는지를 코드에서 활용한다.

Reference:
    outputs/todo-list/2026-05-21/chronic-disease-category-brainstorming.md §2
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel

ChronicCondition = Literal[
    "diabetes",
    "hypertension",
    "dyslipidemia",
    "cardiovascular",
    "osteoporosis",
    "chronic_kidney_disease",
    "liver_disease",
    "cognitive_decline",
]
"""B형 페르소나에 자주 동반되는 8 종 만성질환 인디케이션."""

EvidenceLevel = Literal["strong", "moderate", "weak", "insufficient"]
"""EBM 증거 수준 4 단계 (strong > moderate > weak > insufficient)."""

PersonaRecommendation = Literal[
    "prioritize_for_chronic",
    "moderate_for_chronic",
    "caution_for_chronic",
    "avoid_for_chronic",
    "avoid_for_ckd",
    "neutral",
]
"""B형 페르소나에 대한 카테고리 권장 등급."""


class ChronicDiseaseTarget(BaseModel):
    """단일 (condition, evidence) 매핑 항목.

    Attributes:
        condition: 만성질환 인디케이션.
        evidence_level: EBM 증거 수준.
        notes: 권장 용량·연구 출처 등 추가 메모.
    """

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True, extra="forbid")

    condition: ChronicCondition
    evidence_level: EvidenceLevel
    notes: str = ""


class CategoryProfile(BaseModel):
    """단일 카테고리 (예: ``오메가3``) 의 만성질환 프로필.

    Attributes:
        chronic_disease_targets: 만성질환 인디케이션 리스트 (비어 있을 수 있음).
        cautions: 자유 텍스트 주의사항 (의약품 상호작용, 회피군 등).
        persona_recommendation: B형 페르소나에 대한 권장 등급.
        notes: 카테고리 일반 메모.
    """

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True, extra="forbid")

    chronic_disease_targets: list[ChronicDiseaseTarget] = Field(default_factory=list)
    cautions: list[str] = Field(default_factory=list)
    persona_recommendation: PersonaRecommendation = "neutral"
    notes: str = ""


class MatrixReference(BaseModel):
    """매트릭스 JSON 의 외부 출처 항목.

    Attributes:
        source: 인용 자료 이름.
        url: 자료 URL.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    source: str
    url: str


class ChronicDiseaseSupplementMatrix(BaseModel):
    """카테고리-만성질환 매핑의 전체 데이터.

    Attributes:
        schema_version: 매트릭스 schema 버전 (호환성 검증용).
        generated_at: 생성 일자 (`YYYY-MM-DD`).
        persona_focus: 본 매트릭스가 타겟하는 페르소나 설명.
        evidence_legend: ``EvidenceLevel`` 각 값의 자연어 정의.
        condition_legend: ``ChronicCondition`` 각 값의 자연어 정의.
        categories: ``카테고리명 -> CategoryProfile`` 매핑.
        references: 외부 출처 목록.
    """

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True, extra="forbid")

    schema_version: str
    generated_at: str
    persona_focus: str = ""
    evidence_legend: dict[EvidenceLevel, str] = Field(default_factory=dict)
    condition_legend: dict[ChronicCondition, str] = Field(default_factory=dict)
    categories: dict[str, CategoryProfile]
    references: list[MatrixReference] = Field(default_factory=list)


class ChronicDiseaseSupplementMatrixRoot(RootModel[ChronicDiseaseSupplementMatrix]):
    """JSON root level 호환을 위한 RootModel wrapper.

    실제로 dict 와 동일 구조이므로 ``ChronicDiseaseSupplementMatrix`` 를
    직접 ``model_validate(payload)`` 해도 동일하게 동작한다. 필요 시 이 wrapper 사용.
    """
