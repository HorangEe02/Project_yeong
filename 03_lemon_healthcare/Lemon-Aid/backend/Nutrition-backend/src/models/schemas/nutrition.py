"""영양 기준 룩업과 섭취량 분석 스키마."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.models.schemas.user import PregnancyStatus, Sex, UserProfile

NutrientCode = Annotated[str, Field(min_length=1, max_length=64)]
UnitCode = Annotated[str, Field(min_length=1, max_length=16)]
AuditKRItemScore = Annotated[int, Field(ge=0, le=4)]


class NutrientStatus(StrEnum):
    """영양소 섭취 상태 분류."""

    AT_RISK_INADEQUATE = "at_risk_inadequate"
    BELOW_RDA = "below_rda"
    DEFICIENT = "deficient"
    LOW = "low"
    ADEQUATE = "adequate"
    EXCESSIVE_NEAR_UL = "excessive_near_ul"
    EXCESSIVE = "excessive"
    RISKY = "risky"
    REFERRAL_REQUIRED = "referral_required"


class KDRIReference(BaseModel):
    """KDRIs 기준값 레코드.

    Attributes:
        nutrient_code: 내부 영양소 코드.
        nutrient_name: 영양소 표시명.
        nutrient_name_ko: 한국어 영양소명.
        nutrient_name_en: 영어 영양소명.
        nutrient_group: KDRIs 영양소 그룹.
        sex: 적용 성별. "all"이면 공통 기준.
        age_min: 적용 나이 하한.
        age_max: 적용 나이 상한.
        age_min_months: 적용 나이 하한(개월).
        age_max_months: 적용 나이 상한(개월).
        pregnancy_status: 임신/수유 조건.
        condition_detail: 임신 분기, 부가량, 총량 등 조건 세부 구분.
        source_variant: 같은 영양소의 공식 표 variant(예: liquid water, total water).
        reference_type: RDA, AI, EER 등 기준 유형.
        reference_amount: 단일 기준 섭취량.
        reference_amount_min: 범위 기준 하한.
        reference_amount_max: 범위 기준 상한.
        reference_unit: 기준 단위.
        ul_amount: 상한 섭취량.
        ul_unit: 상한 단위.
        ul_amount_secondary: 같은 row에서 병기되는 두 번째 상한 섭취량.
        ul_unit_secondary: 두 번째 상한 섭취량 단위.
        source_note: 출처 또는 검수 상태.
        source_id: KDRIs source manifest source id.
        source_artifact: 검수한 원본 산출물.
        source_page: 원본 페이지.
        source_table: 원본 표.
        source_cell: 원본 표 셀 또는 행/열 위치.
        errata_version: 적용한 공식 정오표 버전.
        review_status: 행 단위 검수 상태.
        reviewer_1: 1차 검수자.
        reviewer_2: 2차 검수자.
        reviewed_at: 최종 검수일.
        dataset_version: 데이터셋 버전.
        source_manifest_version: source manifest schema version.
    """

    nutrient_code: str
    nutrient_name: str
    nutrient_name_ko: str | None = None
    nutrient_name_en: str | None = None
    nutrient_group: str | None = None
    sex: str
    age_min: int
    age_max: int
    age_min_months: int | None = None
    age_max_months: int | None = None
    pregnancy_status: PregnancyStatus
    condition_detail: str | None = None
    source_variant: str | None = None
    reference_type: str
    reference_amount: float | None
    reference_amount_min: float | None = None
    reference_amount_max: float | None = None
    reference_unit: str
    ul_amount: float | None = None
    ul_unit: str | None = None
    ul_amount_secondary: float | None = None
    ul_unit_secondary: str | None = None
    source_note: str
    source_id: str | None = None
    source_artifact: str | None = None
    source_page: str | None = None
    source_table: str | None = None
    source_cell: str | None = None
    errata_version: str | None = None
    review_status: str | None = None
    reviewer_1: str | None = None
    reviewer_2: str | None = None
    reviewed_at: str | None = None
    dataset_version: str | None = None
    source_manifest_version: str | None = None


class KDRILookupResponse(BaseModel):
    """KDRIs 룩업 API 응답.

    Attributes:
        query: 조회 조건.
        references: 매칭된 기준값 목록.
        dataset_status: 샘플/공식 데이터 상태.
        dataset_version: KDRIs 데이터셋 버전.
        source_manifest_version: source manifest schema version.
        routing_status: 사용자 건강 상태에 따른 분석 라우팅 상태.
        safety_messages: 만성질환·임신·약물 등으로 인한 안전 안내.
        note: 사용자 노출용 안전 문구.
    """

    query: KDRIQuery
    references: list[KDRIReference]
    dataset_status: str
    dataset_version: str
    source_manifest_version: str
    note: str = (
        "KDRIs 기준값은 source manifest의 dataset_status와 row review_status를 함께 확인해야 합니다."
    )


class NutrientIntake(BaseModel):
    """영양소 섭취량 입력.

    Attributes:
        nutrient_code: 내부 영양소 코드.
        amount: 섭취량.
        unit: 섭취량 단위.
    """

    nutrient_code: NutrientCode
    amount: float = Field(ge=0)
    unit: UnitCode


class NutrientAnalysisResult(BaseModel):
    """영양소별 섭취 상태 분석 결과.

    Attributes:
        nutrient_code: 내부 영양소 코드.
        nutrient_name: 영양소 표시명.
        reference_amount: 기준 섭취량.
        reference_type: KDRIs 기준 유형.
        source_id: KDRIs source manifest source id.
        errata_version: 적용한 공식 정오표 버전.
        review_status: 기준 행 검수 상태.
        reference_unit: 기준 단위.
        actual_amount: 기준 단위로 환산한 실제 섭취량.
        ratio: 실제 섭취량 / 기준 섭취량.
        ul_amount: 상한 섭취량.
        status: 섭취 상태.
        priority: 부족 가능성 우선순위.
        priority_context: 우선 확인 대상 정렬에 반영된 canonical 만성질환 코드.
        priority_source_ids: 우선 확인 대상 정렬 근거 source id.
        user_message: 사용자 노출용 안전 문구.
    """

    nutrient_code: str
    nutrient_name: str
    reference_amount: float
    reference_type: str
    source_id: str | None = None
    errata_version: str | None = None
    review_status: str | None = None
    reference_unit: str
    actual_amount: float
    ratio: float
    ul_amount: float | None
    status: NutrientStatus
    priority: int
    priority_context: list[str] = Field(default_factory=list)
    priority_source_ids: list[str] = Field(default_factory=list)
    user_message: str


class ConditionNutritionGuide(BaseModel):
    """질환별 영양 가이드 라우팅 메타데이터.

    Attributes:
        condition_codes: 사용자 입력에서 매칭된 canonical condition code 목록.
        guide_key: 클라이언트 표시/분기용 안정 key.
        guide_label: 가이드 표시명.
        source_id: 공식 근거 source id.
        source_title: 공식 근거 title.
        source_url: 공식 공개 URL.
        focus_nutrients: 우선 확인할 영양소 또는 식사 패턴 key.
        referral_required: 일반 KDRIs 자동 분석 보류 여부.
        user_message: 사용자 노출용 안전 안내.
    """

    condition_codes: list[str] = Field(default_factory=list)
    guide_key: Literal[
        "ada_diabetes_nutrition",
        "dash_hypertension",
        "kdoqi_ckd_nutrition",
        "easl_liver_nutrition",
    ]
    guide_label: str
    source_id: str
    source_title: str
    source_url: str
    focus_nutrients: list[str] = Field(default_factory=list)
    referral_required: bool = False
    user_message: str


class NutritionAnalysisRequest(BaseModel):
    """영양소 섭취 상태 분석 API 요청.

    Attributes:
        profile: 사용자 프로필.
        intakes: 영양소 섭취량 목록.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "profile": {
                        "age": 30,
                        "sex": "male",
                        "height_cm": 170,
                        "weight_kg": 70,
                    },
                    "intakes": [
                        {"nutrient_code": "vitamin_c_mg", "amount": 30, "unit": "mg"},
                        {"nutrient_code": "vitamin_a_ug", "amount": 5000, "unit": "ug"},
                    ],
                }
            ]
        }
    )

    profile: UserProfile
    intakes: list[NutrientIntake] = Field(min_length=1, max_length=100)


class NutritionAnalysisResponse(BaseModel):
    """영양소 섭취 상태 분석 API 응답.

    Attributes:
        results: 영양소별 분석 결과.
        dataset_status: 샘플/공식 데이터 상태.
        dataset_version: KDRIs 데이터셋 버전.
        source_manifest_version: source manifest schema version.
        condition_nutrition_guides: 질환별 공식 가이드 라우팅 메타데이터.
        note: 사용자 노출용 안전 문구.
    """

    results: list[NutrientAnalysisResult]
    dataset_status: str
    dataset_version: str
    source_manifest_version: str
    routing_status: Literal["ok", "referral_required"] = "ok"
    safety_messages: list[str] = Field(default_factory=list)
    condition_nutrition_guides: list[ConditionNutritionGuide] = Field(default_factory=list)
    note: str = "결과는 섭취 상태 참고용이며 개인 건강 상태를 확정하지 않습니다."


class AuditKRRequest(BaseModel):
    """AUDIT-KR 10문항 점수 입력.

    Attributes:
        sex: AUDIT-KR 알코올 사용장애 cut-off 선택용 성별.
        item_scores: AUDIT-KR 10개 문항의 0-4점 점수 목록. 문항 텍스트는 UI 콘텐츠에서 관리한다.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "sex": "female",
                    "item_scores": [1, 1, 1, 0, 0, 0, 0, 0, 0, 0],
                }
            ]
        }
    )

    sex: Sex
    item_scores: list[AuditKRItemScore] = Field(min_length=10, max_length=10)


class AuditKRResponse(BaseModel):
    """AUDIT-KR self-check 점수화 결과.

    Attributes:
        score: 10문항 합산 점수.
        risk_level: 위험 음주 또는 알코올 사용장애 cut-off 도달 여부.
        risk_cutoff: 위험 음주 cut-off.
        dependence_cutoff: 성별에 따른 알코올 사용장애 screening cut-off.
        nutrition_priority_nutrients: 위험 음주 범위에서 우선 확인할 영양소 코드.
        supplement_recommendation_paused: 영양제 자동 추천 보류 여부.
        recommendation_messages: 사용자 노출용 안전 안내.
        algorithm_version: AUDIT-KR scoring version.
        note: 확정 진단 표현을 피하기 위한 안내.
    """

    score: int = Field(ge=0, le=40)
    risk_level: Literal["low_risk", "risky_drinking", "dependence_cutoff"]
    risk_cutoff: int
    dependence_cutoff: int
    nutrition_priority_nutrients: list[str] = Field(default_factory=list)
    supplement_recommendation_paused: bool = False
    recommendation_messages: list[str] = Field(default_factory=list)
    algorithm_version: str
    note: str = "AUDIT-KR 결과는 선별 참고용이며 진단이나 치료 판단을 대체하지 않습니다."


class NutritionDiagnosisSummary(BaseModel):
    """Persisted nutrition diagnosis summary for mobile/dashboard views.

    Attributes:
        total_count: Number of analyzed nutrients.
        deficient_count: Count classified as deficient.
        low_count: Count classified as low.
        adequate_count: Count classified as adequate.
        excessive_count: Count classified as excessive.
        risky_count: Count classified as above the upper intake limit.
        deficient_or_low_count: Count requiring intake review for low intake.
        excessive_or_risky_count: Count requiring intake review for high intake.
        dataset_status: KDRIs dataset operational status.
        dataset_version: KDRIs dataset version.
        source_manifest_version: KDRIs source manifest schema version.
        summary_message: Safe user-facing summary.
    """

    total_count: int = Field(ge=0)
    deficient_count: int = Field(ge=0)
    low_count: int = Field(ge=0)
    adequate_count: int = Field(ge=0)
    excessive_count: int = Field(ge=0)
    risky_count: int = Field(ge=0)
    deficient_or_low_count: int = Field(ge=0)
    excessive_or_risky_count: int = Field(ge=0)
    dataset_status: str | None = None
    dataset_version: str | None = None
    source_manifest_version: str | None = None
    summary_message: str


class NutritionDiagnosisLatestResponse(BaseModel):
    """Latest persisted nutrition diagnosis visible to the current user.

    Attributes:
        data_status: Whether a persisted nutrition analysis is available.
        result_id: Persisted analysis result identifier.
        created_at: Time when the persisted analysis was created.
        algorithm_version: Nutrition algorithm version used for the result.
        summary: Count and source summary for the diagnosis.
        diagnoses: Nutrient-level persisted analysis results.
        recommended_foods: Reserved map for reviewed food recommendations.
        disclaimers: Safety notices for user-facing health screens.
    """

    data_status: str = Field(pattern=r"^(ready|not_ready)$")
    result_id: UUID | None
    created_at: datetime | None
    algorithm_version: str | None
    summary: NutritionDiagnosisSummary
    diagnoses: list[NutrientAnalysisResult]
    recommended_foods: dict[str, list[str]] = Field(default_factory=dict)
    disclaimers: list[str]


class KDRIQuery(BaseModel):
    """KDRIs 조회 조건.

    Attributes:
        age: 만 나이.
        sex: 성별.
        pregnancy_status: 임신/수유 상태.
    """

    age: int = Field(ge=1, le=120)
    sex: Sex
    pregnancy_status: PregnancyStatus = "none"
