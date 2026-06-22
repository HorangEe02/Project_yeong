"""사용자 프로필 공통 스키마."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

Sex = Literal["male", "female"]
PregnancyStatus = Literal["none", "pregnant", "lactating"]
DiseaseCode = Annotated[str, Field(min_length=1, max_length=64)]
SmokingStatus = Literal["never", "former_lt_1y", "former_ge_1y", "current_light", "current_heavy"]
MedicationCode = Annotated[str, Field(min_length=1, max_length=64)]


class UserProfile(BaseModel):
    """계산 알고리즘에 필요한 최소 사용자 프로필.

    Attributes:
        age: 만 나이.
        sex: 생물학적 성별 기반 계산 입력.
        height_cm: 키(cm).
        weight_kg: 체중(kg).
        pregnancy_status: KDRIs 룩업용 임신/수유 상태.
        chronic_diseases: 활동점수 v4 계산에 사용할 만성질환 코드 목록.
        waist_cm: BMI 보완 지표인 허리-신장비 산출용 허리둘레.
        body_fat_pct: 체지방률(%). BMR 보완 공식과 BMI 보조 flag에 사용한다.
        resting_heart_rate_bpm: 안정시 심박수. 입력 시 Karvonen HRR 목표 심박에 사용한다.
        smoking_status: 흡연 관련 영양/활동 안전 분기.
        audit_kr_score: 음주 위험 스크리닝 점수. None이면 미입력.
        medications: 약물-영양제 상호작용 안전 분기용 약물 코드 목록.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "age": 50,
                    "sex": "female",
                    "height_cm": 160,
                    "weight_kg": 68,
                    "pregnancy_status": "none",
                    "chronic_diseases": ["diabetes", "hypertension"],
                    "smoking_status": "never",
                }
            ]
        }
    )

    age: int = Field(ge=1, le=120)
    sex: Sex
    height_cm: float = Field(gt=0, ge=50, le=250)
    weight_kg: float = Field(gt=0, ge=10, le=300)
    pregnancy_status: PregnancyStatus = "none"
    chronic_diseases: list[DiseaseCode] = Field(default_factory=list, max_length=10)
    waist_cm: float | None = Field(default=None, gt=0, le=250)
    body_fat_pct: float | None = Field(default=None, ge=0, le=70)
    resting_heart_rate_bpm: int | None = Field(default=None, ge=20, le=240)
    smoking_status: SmokingStatus = "never"
    audit_kr_score: int | None = Field(default=None, ge=0, le=40)
    medications: list[MedicationCode] = Field(default_factory=list, max_length=20)
