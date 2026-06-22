"""핵심 산출식 알고리즘 요청/응답 스키마."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.models.schemas.user import Sex, UserProfile


class EvidenceLevel(StrEnum):
    """알고리즘 근거 수준.

    Attributes:
        A: 논문 또는 공식 기준에서 직접 확인되는 수식/기준값.
        B: 방향성 근거는 있으나 프로젝트 계수까지 직접 검증되지는 않은 값.
        C: 제품 UX 또는 팀 가정에 가까운 휴리스틱.
    """

    A = "A"
    B = "B"
    C = "C"


class BMICategory(StrEnum):
    """BMI 기준 분류."""

    UNDERWEIGHT = "underweight"
    NORMAL = "normal"
    OVERWEIGHT = "overweight"
    OBESE_1 = "obese_1"
    OBESE_2 = "obese_2"
    OBESE_3 = "obese_3"


BMIRegion = Literal["asia_kr", "who_standard"]
HRMaxFormula = Literal["guide_220_age", "tanaka_2001", "gellish_2007", "nes_2013"]
ActivityPeerScore = Annotated[float, Field(ge=0, le=100)]
PredictionPeriodDays = Annotated[int, Field(ge=1, le=365)]


class BMIResult(BaseModel):
    """BMI 계산 결과.

    Attributes:
        bmi: BMI 값(kg/m^2).
        category: 선택 기준의 BMI 분류.
        region: BMI 기준 체계.
        criteria_source: 기준 출처.
        evidence_level: 기준값 근거 수준.
        note: 사용자 노출 시 확정 표현을 피하기 위한 설명.
        notes: 보완 지표와 사용자 맥락 안내.
        waist_to_height_ratio: 허리-신장비. 허리둘레가 없으면 None.
        central_obesity: WHtR 0.5 이상 여부. 허리둘레가 없으면 None.
        waist_circumference_obesity: KSSO 성별 허리둘레 기준 복부비만 여부.
        body_fat_flag: 체지방률 참고 flag.
        sarcopenic_obesity_suspected: 고령·정상 BMI·높은 체지방률 조합 flag.
    """

    bmi: float
    category: BMICategory
    region: BMIRegion = "asia_kr"
    criteria_source: str = "KSSO 2022"
    evidence_level: EvidenceLevel = EvidenceLevel.A
    note: str = "BMI 분류(스크리닝)이며 체성분이나 질환 상태를 확정하지 않습니다."
    notes: list[str] = Field(default_factory=list)
    waist_to_height_ratio: float | None = None
    central_obesity: bool | None = None
    waist_circumference_obesity: bool | None = None
    body_fat_flag: Literal["high", "normal"] | None = None
    sarcopenic_obesity_suspected: bool | None = None


class TargetHeartRateRange(BaseModel):
    """목표 심박 구간.

    Attributes:
        low_bpm: 목표 심박 하한.
        high_bpm: 목표 심박 상한.
        formula: HRmax 계산식.
        method: 목표 심박 산출 방식.
        resting_heart_rate_bpm: Karvonen HRR 계산에 사용한 안정시 심박수.
    """

    low_bpm: int
    high_bpm: int
    formula: HRMaxFormula
    method: Literal["percent_hrmax", "karvonen_hrr"] = "percent_hrmax"
    resting_heart_rate_bpm: int | None = None


class ActivityScoreRequest(BaseModel):
    """활동점수 API 요청.

    Attributes:
        profile: 사용자 프로필.
        daily_steps: 일일 걸음수.
        target_hr_minutes: 목표 심박 구간 유지 시간. 웨어러블 없음이면 None.
        group_v2_scores: 동일 성별/연령대 비교군 v2 점수.
        hrmax_formula: HRmax 계산 방식.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "profile": {
                        "age": 50,
                        "sex": "female",
                        "height_cm": 160,
                        "weight_kg": 68,
                        "chronic_diseases": ["diabetes", "hypertension"],
                    },
                    "daily_steps": 7000,
                    "target_hr_minutes": 20,
                    "group_v2_scores": [60.0, 62.0, 64.0],
                    "hrmax_formula": "tanaka_2001",
                }
            ]
        }
    )

    profile: UserProfile
    daily_steps: int = Field(ge=0)
    target_hr_minutes: float | None = Field(default=None, ge=0)
    group_v2_scores: list[ActivityPeerScore] = Field(default_factory=list, max_length=500)
    hrmax_formula: HRMaxFormula = "tanaka_2001"


class ActivityScoreResponse(BaseModel):
    """활동점수 API 응답.

    Attributes:
        bmi: BMI 계산 결과.
        recommended_steps: 사용자별 권장 걸음수.
        target_hr_range: 목표 심박 구간.
        hr_factor: 심박 가중 계수.
        percentile_bonus: 비교군 백분위 보너스.
        disease_multiplier: 만성질환 프로젝트 가중치.
        v1_score: 기본 걸음수 점수.
        v2_score: 심박 가중 점수.
        v3_score: 백분위 보너스 반영 점수.
        v4_score: 만성질환 가중 반영 점수.
        score_label: UX 라벨. 질환 개선 효과가 아닌 활동 동기 보정임을 명확히 한다.
        safety_messages: 흡연·음주 등 생활습관 맥락에서 점수 해석을 보수적으로 돕는 안내.
        note: 의료 확정 표현을 피하기 위한 안내.
    """

    bmi: BMIResult
    recommended_steps: int
    target_hr_range: TargetHeartRateRange
    hr_factor: float
    percentile_bonus: int
    disease_multiplier: float
    v1_score: float
    v2_score: float
    v3_score: float
    v4_score: float
    score_label: str = "활동 동기 점수"
    safety_messages: list[str] = Field(default_factory=list)
    note: str = "활동 동기 점수는 건강 행동 참고 지표이며 질환 개선 효과를 의미하지 않습니다."


class WeightPredictionStep(BaseModel):
    """7-step 체중 예측 결과.

    Attributes:
        days: 예측 기간(일).
        estimated_bmr: 예상 BMR.
        estimated_tdee: 예상 TDEE.
        daily_balance_kcal: 일일 에너지 수지.
        cumulative_balance_kcal: 누적 에너지 수지.
        theoretical_change_kg: 7,700 kcal/kg 기준 이론 변화량.
        corrected_change_kg: 프로젝트 보정계수 적용 변화량.
        predicted_weight_kg: 예측 체중.
        expected_weight_range_kg: 기대 체중 범위. 단정적 예측 표현을 피하기 위한 범위값.
        model_name: 사용한 예측 모델 이름.
        confidence: 기간과 사용자 상태를 반영한 신뢰도.
        prediction_status: 계산 여부.
        disabled_reason: 자동 계산이 보류된 사유.
        warning: 장기 예측 한계 안내.
    """

    days: int
    estimated_bmr: float
    estimated_tdee: float
    daily_balance_kcal: float
    cumulative_balance_kcal: float
    theoretical_change_kg: float
    corrected_change_kg: float
    predicted_weight_kg: float
    expected_weight_range_kg: tuple[float, float] | None = None
    model_name: str = "static_energy_balance"
    confidence: Literal["high", "medium", "low"] = "medium"
    prediction_status: Literal["computed", "disabled"] = "computed"
    disabled_reason: str | None = None
    warning: str | None = None


class WeightPredictionCheckIn(BaseModel):
    """예측 후 주간 실측 체중 확인값.

    Attributes:
        week_index: 예측 시작 후 몇 번째 주 실측인지 나타내는 1-based index.
        measured_weight_kg: 해당 주의 실측 체중(kg).
        expected_weight_range_kg: 같은 주차에 기대한 체중 범위.
        measured_date: 사용자 로컬 기준 실측 날짜.
    """

    week_index: int = Field(ge=1, le=156)
    measured_weight_kg: float = Field(ge=10, le=300)
    expected_weight_range_kg: tuple[float, float]
    measured_date: date | None = None

    @model_validator(mode="after")
    def validate_expected_weight_range(self) -> WeightPredictionCheckIn:
        """기대 체중 범위의 하한/상한 순서를 검증한다.

        Returns:
            검증된 주간 실측 체중 확인값.

        Raises:
            ValueError: 기대 체중 범위 하한이 상한보다 큰 경우.
        """
        lower, upper = self.expected_weight_range_kg
        if lower > upper:
            raise ValueError("expected_weight_range_kg lower bound must be <= upper bound")
        return self


class WeightPredictionMismatchWarning(BaseModel):
    """예측-실측 체중 mismatch 판정 결과.

    Attributes:
        triggered: 최근 주간 실측이 2주 연속 기대 범위를 벗어났는지 여부.
        consecutive_out_of_range_weeks: 최근 연속 범위 이탈 주 수.
        out_of_range_count: 전체 입력 check-in 중 범위 이탈 건수.
        message: 사용자 안내 메시지. trigger가 없으면 None.
        recommended_actions: trigger 시 사용자에게 노출할 권장 후속 행동.
    """

    triggered: bool = False
    consecutive_out_of_range_weeks: int = 0
    out_of_range_count: int = 0
    message: str | None = None
    recommended_actions: list[str] = Field(default_factory=list)


class WeightPredictionRequest(BaseModel):
    """체중 예측 API 요청.

    Attributes:
        age: 만 나이.
        sex: 생물학적 성별 기반 계산 입력.
        height_cm: 키(cm).
        weight_kg: 현재 체중(kg).
        daily_steps: 일일 걸음수.
        daily_intake_kcal: 일일 섭취 열량.
        alcohol_kcal: 일일 섭취 열량에 별도로 더할 알코올 열량.
        alcohol_volume_ml: 주류 용량(ml). ABV와 함께 입력하면 알코올 kcal을 자동 산출한다.
        alcohol_abv_percent: 주류 도수(%). volume이 있으면 필요하다.
        body_fat_pct: 체지방률(%). 입력 시 BMR 보조 공식에 사용할 수 있다.
        walking_cadence_steps_per_min: 웨어러블에서 관측한 보행 cadence(steps/min).
        walking_cadence_minutes: cadence가 관측된 보행 시간(분).
        exercise_average_heart_rate_bpm: 운동 구간 평균 심박수(bpm).
        heart_rate_exercise_minutes: 평균 심박수가 관측된 운동 시간(분).
        chronic_diseases: 자동 체중 예측 안전 분기용 만성질환 코드.
        periods_days: 예측 기간 목록.
        prediction_checkins: 주간 실측 체중과 해당 주차 기대 범위 목록.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "age": 50,
                    "sex": "female",
                    "height_cm": 160,
                    "weight_kg": 68,
                    "daily_steps": 6500,
                    "daily_intake_kcal": 1500,
                    "alcohol_kcal": 0,
                    "alcohol_volume_ml": 0,
                    "alcohol_abv_percent": None,
                    "walking_cadence_steps_per_min": None,
                    "walking_cadence_minutes": 0,
                    "exercise_average_heart_rate_bpm": None,
                    "heart_rate_exercise_minutes": 0,
                    "chronic_diseases": [],
                    "periods_days": [7, 30, 90],
                    "prediction_checkins": [],
                }
            ]
        }
    )

    age: int = Field(ge=1, le=120)
    sex: Sex
    height_cm: float = Field(ge=50, le=250)
    weight_kg: float = Field(ge=10, le=300)
    daily_steps: int = Field(ge=0)
    daily_intake_kcal: float = Field(ge=0)
    alcohol_kcal: float = Field(default=0, ge=0, le=5000)
    alcohol_volume_ml: float = Field(default=0, ge=0, le=5000)
    alcohol_abv_percent: float | None = Field(default=None, ge=0, le=100)
    body_fat_pct: float | None = Field(default=None, ge=0, le=70)
    walking_cadence_steps_per_min: float | None = Field(default=None, ge=0, le=250)
    walking_cadence_minutes: float = Field(default=0, ge=0, le=1440)
    exercise_average_heart_rate_bpm: float | None = Field(default=None, ge=30, le=240)
    heart_rate_exercise_minutes: float = Field(default=0, ge=0, le=1440)
    chronic_diseases: list[str] = Field(default_factory=list, max_length=10)
    periods_days: list[PredictionPeriodDays] = Field(
        default_factory=lambda: [7, 30, 90],
        min_length=1,
        max_length=12,
    )
    prediction_checkins: list[WeightPredictionCheckIn] = Field(default_factory=list, max_length=12)

    @model_validator(mode="after")
    def validate_weight_prediction_request(self) -> WeightPredictionRequest:
        """주류 용량과 주간 실측 체중 입력의 교차 조건을 검증한다.

        Returns:
            검증된 요청 모델.

        Raises:
            ValueError: alcohol_volume_ml > 0 이지만 alcohol_abv_percent 가 없는 경우,
                보행 cadence 또는 운동 심박 입력 쌍이 불완전한 경우, 또는 중복 주차 check-in
                이 있는 경우.
        """
        if self.alcohol_volume_ml > 0 and self.alcohol_abv_percent is None:
            raise ValueError("alcohol_abv_percent is required when alcohol_volume_ml is provided")
        if self.walking_cadence_minutes > 0 and self.walking_cadence_steps_per_min is None:
            raise ValueError(
                "walking_cadence_steps_per_min is required when walking_cadence_minutes is provided"
            )
        if self.walking_cadence_steps_per_min is not None and self.walking_cadence_minutes <= 0:
            raise ValueError(
                "walking_cadence_minutes must be positive when walking_cadence_steps_per_min is provided"
            )
        if self.heart_rate_exercise_minutes > 0 and self.exercise_average_heart_rate_bpm is None:
            raise ValueError(
                "exercise_average_heart_rate_bpm is required when heart_rate_exercise_minutes is provided"
            )
        if (
            self.exercise_average_heart_rate_bpm is not None
            and self.heart_rate_exercise_minutes <= 0
        ):
            raise ValueError(
                "heart_rate_exercise_minutes must be positive when exercise_average_heart_rate_bpm is provided"
            )
        week_indices = [checkin.week_index for checkin in self.prediction_checkins]
        if len(week_indices) != len(set(week_indices)):
            raise ValueError("prediction_checkins must not contain duplicate week_index values")
        return self


class WeightPredictionResponse(BaseModel):
    """체중 예측 API 응답.

    Attributes:
        predictions: 기간별 예측 결과.
        prediction_status: 전체 예측 상태.
        safety_warnings: 자동 계산 보류 또는 신뢰도 저하 사유.
        mismatch_warning: 주간 실측 체중이 기대 범위를 2주 연속 벗어났는지에 대한 판정.
        evidence_level: 7,700 kcal/kg 정적 근사와 프로젝트 보정계수의 근거 수준.
        note: 장기 예측 한계 안내.
    """

    predictions: list[WeightPredictionStep]
    prediction_status: Literal["computed", "disabled"] = "computed"
    safety_warnings: list[str] = Field(default_factory=list)
    mismatch_warning: WeightPredictionMismatchWarning | None = None
    evidence_level: EvidenceLevel = EvidenceLevel.B
    note: str = (
        "기대 체중 범위는 일반적 시나리오 기반 참고값이며 장기 대사 적응을 완전히 반영하지 않습니다."
    )
