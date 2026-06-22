"""식단 인식 도메인의 공통 DTO.

dev-guide 16 §1. base.py 명세를 따른다. 모든 DTO는 Pydantic v2 기반 불변
객체(`frozen=True`)로, YOLO/GCV/Fusion/Portion/RDA 단계에서 공유된다.

Reference:
    docs/dev-guides/16-meal-recognition.md §"구현 명세 / 1. base.py"
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

MealType = Literal["breakfast", "lunch", "dinner", "snack"]
"""식사 종류 enum 별칭."""


DetectionSource = Literal["yolo_v8", "google_vision"]
"""음식 후보의 출처 식별자."""


class BoundingBox(BaseModel):
    """이미지 좌표 기반 bounding box.

    Attributes:
        x_min: 좌상단 x 좌표 (픽셀).
        y_min: 좌상단 y 좌표 (픽셀).
        x_max: 우하단 x 좌표 (픽셀, `x_min`보다 큼).
        y_max: 우하단 y 좌표 (픽셀, `y_min`보다 큼).
    """

    model_config = ConfigDict(frozen=True)

    x_min: float = Field(..., ge=0)
    y_min: float = Field(..., ge=0)
    x_max: float = Field(..., gt=0)
    y_max: float = Field(..., gt=0)

    @model_validator(mode="after")
    def _check_order(self) -> BoundingBox:
        """좌표 순서를 검증한다.

        Returns:
            검증된 인스턴스.

        Raises:
            ValueError: `x_min >= x_max` 또는 `y_min >= y_max`.
        """
        if self.x_min >= self.x_max:
            raise ValueError(f"x_min({self.x_min}) must be < x_max({self.x_max})")
        if self.y_min >= self.y_max:
            raise ValueError(f"y_min({self.y_min}) must be < y_max({self.y_max})")
        return self

    @property
    def area(self) -> float:
        """bbox 면적 (픽셀 제곱)."""
        return (self.x_max - self.x_min) * (self.y_max - self.y_min)


class MealDetection(BaseModel):
    """YOLO 또는 GCV의 단일 음식 후보.

    Fusion 이전 단계의 원시 출력을 표현한다. confidence 정책은 Fusion에서
    적용되며, 본 DTO 자체는 신뢰도 정책을 강제하지 않는다.

    Attributes:
        class_name_ko: 한국어 음식명 (`classes.yaml`의 names 항목과 일치 권장).
        confidence: 모델 신뢰도 (0.0~1.0).
        bbox: 음식 영역 bbox (GCV label hint는 bbox 없을 수 있음 → None).
        source: 출처 (`yolo_v8` 또는 `google_vision`).
    """

    model_config = ConfigDict(frozen=True)

    class_name_ko: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)
    bbox: BoundingBox | None = None
    source: DetectionSource


class RecognizedMealItem(BaseModel):
    """Fusion·Portion·RDA 매칭을 거친 최종 음식 항목.

    Attributes:
        name_ko: 정규화된 한국어 음식명.
        food_code: 농진청 식품성분표 코드 (매칭 실패 시 None).
        estimated_grams: 추정 중량 (g, 양수).
        estimated_amount: 양 표현 (예: "1공기").
        confidence: 음식 분류 신뢰도 (0.0~1.0).
        portion_confidence: 양 추정 신뢰도 (0.0~1.0).
        needs_user_review: 사용자 확인이 필요한 항목 여부.
        sources: 결과 도출에 사용된 출처 리스트.
        alternatives: 대안 후보 (동일 음식의 다른 bbox 또는 충돌 후보).
    """

    model_config = ConfigDict(frozen=True)

    name_ko: str = Field(..., min_length=1)
    food_code: str | None = None
    estimated_grams: float = Field(..., gt=0)
    estimated_amount: str = Field(default="")
    confidence: float = Field(..., ge=0.0, le=1.0)
    portion_confidence: float = Field(..., ge=0.0, le=1.0)
    needs_user_review: bool = False
    sources: list[DetectionSource] = Field(default_factory=list)
    alternatives: list[MealDetection] = Field(default_factory=list)


class RecognizedMeal(BaseModel):
    """식사 단위의 최종 인식 결과.

    Pipeline의 최종 출력. dev-guide 06 완료 후 follow-up PR에서 본 DTO를
    `NutrientIntake[]`로 변환하는 계층이 추가된다.

    Attributes:
        meal_type: 식사 종류 (breakfast/lunch/dinner/snack).
        items: 인식된 음식 항목 리스트.
        engine: 사용된 엔진 식별자 (예: "mock_yolo_v8:fixture_v1").
        raw_input: 원본 입력 표현 (이미지 해시 또는 텍스트 앞부분).
    """

    model_config = ConfigDict(frozen=True)

    meal_type: MealType
    items: list[RecognizedMealItem] = Field(default_factory=list)
    engine: str = Field(..., min_length=1)
    raw_input: str = Field(default="")
