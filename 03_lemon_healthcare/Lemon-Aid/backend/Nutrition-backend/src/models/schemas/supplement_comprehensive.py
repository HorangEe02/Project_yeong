"""5-card 종합 분석 (B-persona 차별화) Pydantic schema.

`POST /api/v1/supplements/analyze/comprehensive` endpoint 의 입출력. OCR analyze
endpoint 가 반환하는 ingredient candidate 들을 KDRIs + 만성질환 매트릭스와
교차하여 모바일 5-card UI 의 5종 카드를 모두 채울 수 있도록 한다:

- 카드 1: 부족 영양소 (`deficient_nutrients`)
- 카드 2: 과다 섭취 (`excessive_nutrients`)
- 카드 3: 주의 성분 (`cautionary_components`)
- 카드 4: 식단/영양제 점수 (`diet_score`)
- 카드 5: 목적별 / 만성질환 (`purpose_targets`)

Reference:
    outputs/todo-list/2026-05-21/b-persona-accuracy-report.md §3
    data/nutrition_reference/chronic_disease_supplement_matrix.json
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from src.models.schemas.chronic_disease_matrix import ChronicCondition

PersonaTag = Literal["A", "B"]
"""사용자 페르소나. A=박직장(예방), B=김건강(만성질환자, 차별화 핵심)."""

ScoreLabel = Literal["excellent", "good", "moderate", "warning", "critical"]
"""식단 점수의 5단계 자연어 라벨."""

Severity = Literal["low", "medium", "high"]
"""주의 성분의 심각도 등급."""

WellnessGoal = Literal[
    "eye_health",
    "liver_health",
    "fatigue_recovery",
    "immune_support",
    "sleep_support",
    "gut_health",
]
"""일반 웰니스 목적별 추천 매트릭스 키."""


class ComprehensiveIngredient(BaseModel):
    """클라이언트가 보낸 ingredient 정보 (analyze endpoint 응답에서 추출).

    Attributes:
        display_name: 사용자에게 표시되는 이름 (한글/영문 그대로).
        nutrient_code: 내부 영양소 코드 (예: `vitamin_d_ug`). 매트릭스 룩업용.
        amount: 1회 섭취량.
        unit: 단위 (예: `mg`, `ug`, `IU`).
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    display_name: str = Field(min_length=1, max_length=120)
    nutrient_code: str | None = Field(default=None, max_length=80)
    amount: float | None = Field(default=None, ge=0)
    unit: str | None = Field(default=None, max_length=40)


class UserProfileInput(BaseModel):
    """KDRIs 룩업과 만성질환 매핑에 필요한 최소 사용자 프로필.

    Attributes:
        age: 만 나이 (1~120).
        sex: 성별.
        chronic_conditions: 사용자가 보유한 만성질환 인디케이션.
        is_pregnant: 임신 여부 (KDRIs 분기에 사용, 선택).
        smoking_status: 흡연자 베타카로틴/비타민A 경고 분기.
        audit_kr_score: 음주 위험 스크리닝 점수. None이면 미입력.
        medications: 약물-영양제 상호작용 경고용 약물 코드.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    age: int = Field(ge=1, le=120)
    sex: Literal["male", "female"]
    chronic_conditions: list[ChronicCondition] = Field(default_factory=list, max_length=8)
    is_pregnant: bool = Field(default=False)
    smoking_status: Literal[
        "never",
        "former_lt_1y",
        "former_ge_1y",
        "current_light",
        "current_heavy",
    ] = "never"
    audit_kr_score: int | None = Field(default=None, ge=0, le=40)
    medications: list[str] = Field(default_factory=list, max_length=20)


class ComprehensiveAnalysisRequest(BaseModel):
    """`POST /api/v1/supplements/analyze/comprehensive` 요청 본문.

    Attributes:
        analysis_id: 선행 OCR analyze 의 식별자 (감사 로그 용도).
        ingredients: 분석 대상 영양제 ingredient 리스트.
        user_profile: KDRIs 룩업용 사용자 프로필.
        persona: A/B 페르소나 분기 (점수 가중치 조정용).
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    analysis_id: str | None = Field(default=None, max_length=80)
    ingredients: list[ComprehensiveIngredient] = Field(min_length=0, max_length=80)
    user_profile: UserProfileInput
    persona: PersonaTag = "B"


class DeficientNutrient(BaseModel):
    """부족 영양소 (KDRIs 권장량 미달).

    Attributes:
        nutrient_code: 내부 영양소 코드.
        display_name: 사용자 표시명.
        current_intake: 현재 섭취량.
        recommended_intake: KDRIs 일일 권장량.
        unit: 비교 단위.
        deficit_ratio: 부족 비율 0.0~1.0 (1.0 = 100% 부족).
    """

    model_config = ConfigDict(extra="forbid")

    nutrient_code: str
    display_name: str
    current_intake: float
    recommended_intake: float
    unit: str
    deficit_ratio: float = Field(ge=0.0, le=1.0)


class ExcessiveNutrient(BaseModel):
    """과다 섭취 영양소 (KDRIs UL 초과).

    Attributes:
        nutrient_code: 내부 영양소 코드.
        display_name: 사용자 표시명.
        current_intake: 현재 섭취량.
        upper_limit: KDRIs 상한 섭취량 (UL).
        unit: 비교 단위.
        excess_ratio: 초과 비율 (1.5 = UL 의 1.5 배).
    """

    model_config = ConfigDict(extra="forbid")

    nutrient_code: str
    display_name: str
    current_intake: float
    upper_limit: float
    unit: str
    excess_ratio: float = Field(ge=1.0)


class CautionaryComponent(BaseModel):
    """주의 성분 (약물 상호작용, 만성질환 회피군 등).

    Attributes:
        component: 성분/카테고리 이름.
        reason: `drug_interaction:warfarin` 등 표준 토큰.
        severity: 심각도.
        message: 사용자 친화 한국어 안내.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    component: str
    reason: str
    severity: Severity
    message: str


class PurposeTarget(BaseModel):
    """만성질환 인디케이션별 적합도 (B-persona 차별화 핵심).

    Attributes:
        condition: 만성질환 인디케이션.
        relevance_score: 0.0~1.0 본 supplement 의 적합도.
        evidence_level: EBM 등급.
        message: 사용자 친화 한국어 안내.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    condition: ChronicCondition
    relevance_score: float = Field(ge=0.0, le=1.0)
    evidence_level: Literal["strong", "moderate", "weak", "insufficient"]
    message: str


class WellnessGoalTarget(BaseModel):
    """일반 웰니스 목적별 적합도.

    Attributes:
        goal: 목적별 추천 매트릭스 키.
        relevance_score: 0.0~1.0 본 supplement 의 목적 적합도.
        evidence_level: 기능성/근거 강도.
        message: 사용자 친화 한국어 안내.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    goal: WellnessGoal
    relevance_score: float = Field(ge=0.0, le=1.0)
    evidence_level: Literal["strong", "moderate", "weak", "insufficient"]
    message: str


class SupplementComprehensiveAnalysis(BaseModel):
    """`POST /api/v1/supplements/analyze/comprehensive` 응답.

    Attributes:
        analysis_id: 요청에서 전달된 식별자 echo.
        persona: 적용된 페르소나.
        deficient_nutrients: 카드 1.
        excessive_nutrients: 카드 2.
        cautionary_components: 카드 3.
        diet_score: 0~100 종합 점수 (카드 4).
        diet_score_label: 점수 라벨.
        diet_score_message: 사용자 친화 한국어 한 줄 코멘트.
        purpose_targets: 만성질환 인디케이션별 적합도 (카드 5).
        wellness_goal_targets: 일반 웰니스 목적별 적합도 (눈·간·피로·면역·수면·장).
        chronic_disease_indications: matrix 기반 자동 매핑 결과.
        algorithm_version: 산출 로직 버전 (회귀 추적용).
        warnings: 산출 과정에서 발생한 경고.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    analysis_id: str | None = None
    persona: PersonaTag
    deficient_nutrients: list[DeficientNutrient] = Field(default_factory=list)
    excessive_nutrients: list[ExcessiveNutrient] = Field(default_factory=list)
    cautionary_components: list[CautionaryComponent] = Field(default_factory=list)
    diet_score: int = Field(ge=0, le=100)
    diet_score_label: ScoreLabel
    diet_score_message: str
    purpose_targets: list[PurposeTarget] = Field(default_factory=list)
    wellness_goal_targets: list[WellnessGoalTarget] = Field(default_factory=list)
    chronic_disease_indications: list[ChronicCondition] = Field(default_factory=list)
    algorithm_version: str = "comprehensive-v1"
    warnings: list[str] = Field(default_factory=list)
