"""식단 인식 DTO 검증 테스트.

dev-guide 16 §1. base.py 명세에 정의된 Pydantic 제약을 검증한다.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from src.meal.base import (
    BoundingBox,
    MealDetection,
    RecognizedMeal,
    RecognizedMealItem,
)

BOX_X_MIN = 10
BOX_Y_MIN = 20
BOX_X_MAX = 100
BOX_Y_MAX = 200
YOLO_CONFIDENCE = 0.91
ALTERNATIVE_CONFIDENCE = 0.71
EXPECTED_ITEM_COUNT = 2


class TestBoundingBox:
    """BoundingBox DTO 검증."""

    def test_valid_box(self) -> None:
        """정상 좌표는 통과한다."""
        box = BoundingBox(
            x_min=BOX_X_MIN,
            y_min=BOX_Y_MIN,
            x_max=BOX_X_MAX,
            y_max=BOX_Y_MAX,
        )
        assert box.x_min == BOX_X_MIN
        assert box.x_max == BOX_X_MAX
        assert box.area == (BOX_X_MAX - BOX_X_MIN) * (BOX_Y_MAX - BOX_Y_MIN)

    def test_x_order_violation_raises(self) -> None:
        """x_min >= x_max → ValidationError."""
        with pytest.raises(ValidationError):
            BoundingBox(x_min=100, y_min=20, x_max=100, y_max=200)

    def test_y_order_violation_raises(self) -> None:
        """y_min >= y_max → ValidationError."""
        with pytest.raises(ValidationError):
            BoundingBox(x_min=10, y_min=200, x_max=100, y_max=200)

    def test_negative_x_min_raises(self) -> None:
        """좌표는 음수 불가."""
        with pytest.raises(ValidationError):
            BoundingBox(x_min=-1, y_min=0, x_max=100, y_max=100)

    def test_zero_x_max_raises(self) -> None:
        """우하단 좌표는 gt=0."""
        with pytest.raises(ValidationError):
            BoundingBox(x_min=0, y_min=0, x_max=0, y_max=100)

    def test_frozen_immutable(self) -> None:
        """frozen=True → 속성 변경 불가."""
        box = BoundingBox(x_min=10, y_min=20, x_max=100, y_max=200)
        with pytest.raises(ValidationError):
            box.x_min = 5  # type: ignore[misc]


class TestMealDetection:
    """MealDetection DTO 검증."""

    def test_valid_yolo_detection(self) -> None:
        """YOLO detection 정상 케이스."""
        d = MealDetection(
            class_name_ko="공기밥",
            confidence=YOLO_CONFIDENCE,
            bbox=BoundingBox(x_min=0, y_min=0, x_max=100, y_max=100),
            source="yolo_v8",
        )
        assert d.source == "yolo_v8"
        assert d.confidence == YOLO_CONFIDENCE

    def test_gcv_hint_without_bbox(self) -> None:
        """GCV label hint는 bbox 없을 수 있음."""
        d = MealDetection(
            class_name_ko="rice",
            confidence=0.7,
            bbox=None,
            source="google_vision",
        )
        assert d.bbox is None

    def test_empty_class_name_raises(self) -> None:
        """class_name_ko는 min_length=1."""
        with pytest.raises(ValidationError):
            MealDetection(class_name_ko="", confidence=0.5, source="yolo_v8")

    def test_confidence_out_of_range_raises(self) -> None:
        """confidence는 0~1."""
        with pytest.raises(ValidationError):
            MealDetection(class_name_ko="공기밥", confidence=1.5, source="yolo_v8")
        with pytest.raises(ValidationError):
            MealDetection(class_name_ko="공기밥", confidence=-0.1, source="yolo_v8")

    def test_invalid_source_raises(self) -> None:
        """source는 Literal로 제한."""
        with pytest.raises(ValidationError):
            MealDetection(
                class_name_ko="공기밥",
                confidence=0.5,
                source="claude_vision",  # type: ignore[arg-type]
            )


class TestRecognizedMealItem:
    """RecognizedMealItem DTO 검증."""

    def test_minimal_valid(self) -> None:
        """필수 필드만 채운 정상 케이스."""
        item = RecognizedMealItem(
            name_ko="공기밥",
            estimated_grams=210.0,
            confidence=0.91,
            portion_confidence=0.6,
        )
        assert item.food_code is None
        assert item.needs_user_review is False
        assert item.sources == []
        assert item.alternatives == []
        assert item.estimated_amount == ""

    def test_zero_grams_raises(self) -> None:
        """estimated_grams는 gt=0."""
        with pytest.raises(ValidationError):
            RecognizedMealItem(
                name_ko="공기밥",
                estimated_grams=0,
                confidence=0.9,
                portion_confidence=0.5,
            )

    def test_negative_grams_raises(self) -> None:
        """음수 grams 불가."""
        with pytest.raises(ValidationError):
            RecognizedMealItem(
                name_ko="공기밥",
                estimated_grams=-1.0,
                confidence=0.9,
                portion_confidence=0.5,
            )

    def test_empty_name_raises(self) -> None:
        """name_ko는 min_length=1."""
        with pytest.raises(ValidationError):
            RecognizedMealItem(
                name_ko="",
                estimated_grams=100,
                confidence=0.5,
                portion_confidence=0.5,
            )

    def test_alternatives_collected(self) -> None:
        """alternatives에 MealDetection 리스트 보관."""
        alt = MealDetection(
            class_name_ko="공기밥",
            confidence=ALTERNATIVE_CONFIDENCE,
            bbox=BoundingBox(x_min=0, y_min=0, x_max=10, y_max=10),
            source="yolo_v8",
        )
        item = RecognizedMealItem(
            name_ko="공기밥",
            estimated_grams=210,
            confidence=0.91,
            portion_confidence=0.6,
            alternatives=[alt],
        )
        assert len(item.alternatives) == 1
        assert item.alternatives[0].confidence == ALTERNATIVE_CONFIDENCE

    def test_review_flag_default_false(self) -> None:
        """needs_user_review 기본값은 False."""
        item = RecognizedMealItem(
            name_ko="공기밥",
            estimated_grams=210,
            confidence=0.9,
            portion_confidence=0.6,
        )
        assert item.needs_user_review is False


class TestRecognizedMeal:
    """RecognizedMeal DTO 검증."""

    def _build_item(self) -> RecognizedMealItem:
        """테스트용 RecognizedMealItem 빌더."""
        return RecognizedMealItem(
            name_ko="공기밥",
            estimated_grams=210,
            confidence=0.91,
            portion_confidence=0.6,
        )

    def test_minimal_valid(self) -> None:
        """필수 필드만 채운 정상 케이스."""
        meal = RecognizedMeal(
            meal_type="lunch",
            engine="mock_yolo_v8:fixture_v1",
        )
        assert meal.items == []
        assert meal.raw_input == ""

    def test_invalid_meal_type_raises(self) -> None:
        """meal_type은 Literal로 제한."""
        with pytest.raises(ValidationError):
            RecognizedMeal(
                meal_type="brunch",  # type: ignore[arg-type]
                engine="mock_yolo_v8:fixture_v1",
            )

    def test_empty_engine_raises(self) -> None:
        """engine은 min_length=1."""
        with pytest.raises(ValidationError):
            RecognizedMeal(meal_type="lunch", engine="")

    def test_with_items(self) -> None:
        """items 리스트를 담아도 valid."""
        item = self._build_item()
        meal = RecognizedMeal(
            meal_type="dinner",
            items=[item, item],
            engine="mock_yolo_v8:fixture_v1",
            raw_input="<image:abc123>",
        )
        assert len(meal.items) == EXPECTED_ITEM_COUNT
        assert meal.raw_input == "<image:abc123>"
