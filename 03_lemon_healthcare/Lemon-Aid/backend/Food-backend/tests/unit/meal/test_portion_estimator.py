"""PortionEstimator 단위 테스트.

dev-guide 16 §"5. portion_estimator.py"와 A2.4 정책을 검증한다.

규칙 요약:
    - bbox 또는 image_area 없음 → default_serving_g fallback (conf 0.3).
    - image_area ≤ 0 → ValueError.
    - ratio = bbox.area / image_area:
        - < 0.15 → x0.7, "소량 추정"
        - 0.15 ~ 0.45 → x1.0, "1인분 추정"
        - > 0.45 → x1.2, "많음 추정"
    - bbox 보정 시 portion_confidence=0.6.
    - food_code / confidence / sources / alternatives / needs_user_review 보존.
    - estimate_items: name_ko 매칭, 매칭 없으면 fallback, alternatives 보존.

Reference:
    docs/dev-guides/16-meal-recognition.md
    docs/superpowers/plans/2026-05-11-meal-recognition-gcv-yolov8.md §"A2"
"""

from __future__ import annotations

import inspect

import pytest
from src.meal import portion_estimator as portion_estimator_module
from src.meal.base import (
    BoundingBox,
    DetectionSource,
    MealDetection,
    RecognizedMealItem,
)
from src.meal.portion_estimator import PortionEstimator

DEFAULT_SERVING = 100.0
CUSTOM_SERVING = 150.0
IMAGE_AREA = 10_000.0

EXPECTED_SMALL_GRAMS = 70.0
EXPECTED_MEDIUM_GRAMS = 100.0
EXPECTED_LARGE_GRAMS = 120.0

FALLBACK_CONFIDENCE = 0.3
BBOX_CONFIDENCE = 0.6

AMOUNT_SMALL = "소량 추정"
AMOUNT_MEDIUM = "1인분 추정"
AMOUNT_LARGE = "많음 추정"

ITEM_CONFIDENCE = 0.85
ITEM_FOOD_CODE = "F001"

# Image: 100x100 → area = 10000.
# 모든 bbox는 (0,0)에서 시작, x_max·y_max로 area 직접 결정.
SMALL_RATIO_BBOX = BoundingBox(x_min=0, y_min=0, x_max=10, y_max=10)
"""area=100, ratio=0.01 (<0.15) → '소량'."""

BOUNDARY_LOW_BBOX = BoundingBox(x_min=0, y_min=0, x_max=30, y_max=50)
"""area=1500, ratio=0.15 (==0.15 경계, inclusive → '1인분')."""

MID_BBOX = BoundingBox(x_min=0, y_min=0, x_max=30, y_max=100)
"""area=3000, ratio=0.30 → '1인분'."""

BOUNDARY_HIGH_BBOX = BoundingBox(x_min=0, y_min=0, x_max=45, y_max=100)
"""area=4500, ratio=0.45 (==0.45 경계, inclusive → '1인분')."""

LARGE_RATIO_BBOX = BoundingBox(x_min=0, y_min=0, x_max=50, y_max=100)
"""area=5000, ratio=0.50 (>0.45) → '많음'."""


def _item(
    name: str = "공기밥",
    *,
    food_code: str | None = None,
    confidence: float = ITEM_CONFIDENCE,
    needs_user_review: bool = False,
    sources: list[DetectionSource] | None = None,
    alternatives: list[MealDetection] | None = None,
) -> RecognizedMealItem:
    """테스트용 RecognizedMealItem 팩토리.

    estimated_grams는 Pydantic gt=0 만족용 placeholder. PortionEstimator가
    fallback 또는 bbox 비율에 따라 갱신할 값.
    """
    return RecognizedMealItem(
        name_ko=name,
        food_code=food_code,
        estimated_grams=DEFAULT_SERVING,
        estimated_amount="",
        confidence=confidence,
        portion_confidence=0.0,
        needs_user_review=needs_user_review,
        sources=sources if sources is not None else ["yolo_v8"],
        alternatives=alternatives if alternatives is not None else [],
    )


def _yolo_det(name: str, bbox: BoundingBox | None) -> MealDetection:
    """테스트용 YOLO MealDetection 팩토리."""
    return MealDetection(
        class_name_ko=name,
        confidence=0.85,
        bbox=bbox,
        source="yolo_v8",
    )


class TestFallback:
    """bbox 또는 image_area 없을 때 fallback."""

    def test_bbox_none_uses_default_serving(self) -> None:
        """bbox=None → default_serving_g, '1인분 추정', conf 0.3."""
        estimator = PortionEstimator()
        result = estimator.estimate_item(_item(), bbox=None, image_area=IMAGE_AREA)
        assert result.estimated_grams == DEFAULT_SERVING
        assert result.estimated_amount == AMOUNT_MEDIUM
        assert result.portion_confidence == FALLBACK_CONFIDENCE

    def test_image_area_none_uses_default_serving(self) -> None:
        """image_area=None (bbox 있어도) → fallback."""
        estimator = PortionEstimator()
        result = estimator.estimate_item(_item(), bbox=SMALL_RATIO_BBOX, image_area=None)
        assert result.estimated_grams == DEFAULT_SERVING
        assert result.estimated_amount == AMOUNT_MEDIUM
        assert result.portion_confidence == FALLBACK_CONFIDENCE

    def test_both_missing_uses_default_serving(self) -> None:
        """bbox=None, image_area=None → fallback."""
        estimator = PortionEstimator()
        result = estimator.estimate_item(_item(), bbox=None, image_area=None)
        assert result.estimated_grams == DEFAULT_SERVING
        assert result.portion_confidence == FALLBACK_CONFIDENCE

    def test_custom_default_serving_propagates(self) -> None:
        """default_serving_g 변경 시 fallback에도 반영."""
        estimator = PortionEstimator()
        result = estimator.estimate_item(
            _item(), bbox=None, image_area=None, default_serving_g=CUSTOM_SERVING
        )
        assert result.estimated_grams == CUSTOM_SERVING


class TestInvalidImageArea:
    """image_area precondition."""

    def test_image_area_zero_raises(self) -> None:
        """image_area=0 → ValueError."""
        estimator = PortionEstimator()
        with pytest.raises(ValueError, match="image_area"):
            estimator.estimate_item(_item(), bbox=SMALL_RATIO_BBOX, image_area=0)

    def test_image_area_negative_raises(self) -> None:
        """image_area<0 → ValueError."""
        estimator = PortionEstimator()
        with pytest.raises(ValueError, match="image_area"):
            estimator.estimate_item(_item(), bbox=SMALL_RATIO_BBOX, image_area=-1.0)


class TestInvalidDefaultServing:
    """default_serving_g precondition.

    `model_copy(update=...)`는 Pydantic validator를 재실행하지 않으므로
    `RecognizedMealItem.estimated_grams`의 `gt=0` 계약이 우회될 수 있다.
    default_serving_g=0이면 estimated_grams=0, default_serving_g=-1이면
    multiplier 적용 시 음수가 들어가므로 명시적으로 ValueError로 차단한다.
    """

    def test_default_serving_zero_raises_in_fallback_path(self) -> None:
        """default_serving_g=0 → ValueError (fallback 경로)."""
        estimator = PortionEstimator()
        with pytest.raises(ValueError, match="default_serving_g"):
            estimator.estimate_item(_item(), bbox=None, image_area=None, default_serving_g=0.0)

    def test_default_serving_negative_raises_in_bbox_path(self) -> None:
        """default_serving_g<0 → ValueError (bbox 보정 경로)."""
        estimator = PortionEstimator()
        with pytest.raises(ValueError, match="default_serving_g"):
            estimator.estimate_item(
                _item(),
                bbox=SMALL_RATIO_BBOX,
                image_area=IMAGE_AREA,
                default_serving_g=-1.0,
            )

    def test_estimate_items_propagates_default_serving_validation(self) -> None:
        """estimate_items 경로도 default_serving_g 검증을 전파한다."""
        estimator = PortionEstimator()
        with pytest.raises(ValueError, match="default_serving_g"):
            estimator.estimate_items(
                [_item("공기밥")],
                detections=[],
                default_serving_g=0.0,
            )


class TestRatioBands:
    """bbox.area / image_area 비율 3구간."""

    def test_small_ratio_uses_multiplier_07(self) -> None:
        """ratio<0.15 → x0.7, '소량 추정', conf 0.6."""
        estimator = PortionEstimator()
        result = estimator.estimate_item(_item(), bbox=SMALL_RATIO_BBOX, image_area=IMAGE_AREA)
        assert result.estimated_grams == pytest.approx(EXPECTED_SMALL_GRAMS)
        assert result.estimated_amount == AMOUNT_SMALL
        assert result.portion_confidence == BBOX_CONFIDENCE

    def test_boundary_015_is_medium(self) -> None:
        """ratio==0.15 → '1인분 추정' (lower boundary inclusive)."""
        estimator = PortionEstimator()
        result = estimator.estimate_item(_item(), bbox=BOUNDARY_LOW_BBOX, image_area=IMAGE_AREA)
        assert result.estimated_grams == pytest.approx(EXPECTED_MEDIUM_GRAMS)
        assert result.estimated_amount == AMOUNT_MEDIUM
        assert result.portion_confidence == BBOX_CONFIDENCE

    def test_mid_ratio_is_medium(self) -> None:
        """0.15<ratio<0.45 → '1인분 추정'."""
        estimator = PortionEstimator()
        result = estimator.estimate_item(_item(), bbox=MID_BBOX, image_area=IMAGE_AREA)
        assert result.estimated_grams == pytest.approx(EXPECTED_MEDIUM_GRAMS)
        assert result.estimated_amount == AMOUNT_MEDIUM

    def test_boundary_045_is_medium(self) -> None:
        """ratio==0.45 → '1인분 추정' (upper boundary inclusive)."""
        estimator = PortionEstimator()
        result = estimator.estimate_item(_item(), bbox=BOUNDARY_HIGH_BBOX, image_area=IMAGE_AREA)
        assert result.estimated_grams == pytest.approx(EXPECTED_MEDIUM_GRAMS)
        assert result.estimated_amount == AMOUNT_MEDIUM

    def test_large_ratio_uses_multiplier_12(self) -> None:
        """ratio>0.45 → x1.2, '많음 추정', conf 0.6."""
        estimator = PortionEstimator()
        result = estimator.estimate_item(_item(), bbox=LARGE_RATIO_BBOX, image_area=IMAGE_AREA)
        assert result.estimated_grams == pytest.approx(EXPECTED_LARGE_GRAMS)
        assert result.estimated_amount == AMOUNT_LARGE
        assert result.portion_confidence == BBOX_CONFIDENCE


class TestPreservedFields:
    """estimated_* 3필드 외 모든 필드 보존."""

    def test_food_code_preserved(self) -> None:
        """food_code는 변경되지 않는다 (A3 책임)."""
        estimator = PortionEstimator()
        item = _item(food_code=ITEM_FOOD_CODE)
        result = estimator.estimate_item(item, bbox=None, image_area=None)
        assert result.food_code == ITEM_FOOD_CODE

    def test_food_code_none_preserved(self) -> None:
        """food_code=None도 그대로 None."""
        estimator = PortionEstimator()
        item = _item(food_code=None)
        result = estimator.estimate_item(item, bbox=LARGE_RATIO_BBOX, image_area=IMAGE_AREA)
        assert result.food_code is None

    def test_confidence_preserved(self) -> None:
        """confidence는 변경되지 않는다."""
        estimator = PortionEstimator()
        item = _item(confidence=ITEM_CONFIDENCE)
        result = estimator.estimate_item(item, bbox=LARGE_RATIO_BBOX, image_area=IMAGE_AREA)
        assert result.confidence == ITEM_CONFIDENCE

    def test_sources_preserved(self) -> None:
        """sources는 변경되지 않는다."""
        estimator = PortionEstimator()
        sources: list[DetectionSource] = ["yolo_v8", "google_vision"]
        item = _item(sources=sources)
        result = estimator.estimate_item(item, bbox=LARGE_RATIO_BBOX, image_area=IMAGE_AREA)
        assert result.sources == sources

    def test_needs_user_review_preserved(self) -> None:
        """needs_user_review는 변경되지 않는다."""
        estimator = PortionEstimator()
        item = _item(needs_user_review=True)
        result = estimator.estimate_item(item, bbox=LARGE_RATIO_BBOX, image_area=IMAGE_AREA)
        assert result.needs_user_review is True

    def test_alternatives_preserved(self) -> None:
        """alternatives는 fusion이 결정한 결과 그대로 보존된다."""
        estimator = PortionEstimator()
        alt = MealDetection(
            class_name_ko="공기밥",
            confidence=0.65,
            bbox=None,
            source="yolo_v8",
        )
        item = _item(alternatives=[alt])
        result = estimator.estimate_item(item, bbox=LARGE_RATIO_BBOX, image_area=IMAGE_AREA)
        assert result.alternatives == [alt]


class TestImmutability:
    """frozen DTO + model_copy 검증."""

    def test_estimate_item_returns_new_instance(self) -> None:
        """model_copy로 새 인스턴스 반환."""
        estimator = PortionEstimator()
        item = _item()
        result = estimator.estimate_item(item, bbox=None, image_area=None)
        assert result is not item

    def test_original_item_unchanged_after_estimate(self) -> None:
        """frozen이므로 원본 item의 estimated_* 필드는 변경되지 않는다."""
        estimator = PortionEstimator()
        item = _item()
        original_grams = item.estimated_grams
        original_amount = item.estimated_amount
        original_conf = item.portion_confidence
        estimator.estimate_item(item, bbox=LARGE_RATIO_BBOX, image_area=IMAGE_AREA)
        assert item.estimated_grams == original_grams
        assert item.estimated_amount == original_amount
        assert item.portion_confidence == original_conf


class TestEstimateItems:
    """estimate_items 매칭 + 일괄 처리."""

    def test_empty_items_returns_empty(self) -> None:
        """빈 items 리스트는 빈 리스트 반환."""
        estimator = PortionEstimator()
        assert estimator.estimate_items([], detections=[]) == []

    def test_matches_by_name_ko_eq_class_name_ko(self) -> None:
        """item.name_ko == detection.class_name_ko인 detection의 bbox를 사용."""
        estimator = PortionEstimator()
        item = _item("공기밥")
        det = _yolo_det("공기밥", SMALL_RATIO_BBOX)
        results = estimator.estimate_items([item], detections=[det], image_area=IMAGE_AREA)
        assert len(results) == 1
        # SMALL_RATIO_BBOX → '소량 추정', x0.7
        assert results[0].estimated_amount == AMOUNT_SMALL
        assert results[0].estimated_grams == pytest.approx(EXPECTED_SMALL_GRAMS)

    def test_no_matching_detection_falls_back(self) -> None:
        """매칭 detection 없으면 fallback (default_serving_g, '1인분 추정', conf 0.3)."""
        estimator = PortionEstimator()
        item = _item("공기밥")
        det = _yolo_det("김치찌개", SMALL_RATIO_BBOX)  # 다른 이름
        results = estimator.estimate_items([item], detections=[det], image_area=IMAGE_AREA)
        assert results[0].estimated_grams == DEFAULT_SERVING
        assert results[0].estimated_amount == AMOUNT_MEDIUM
        assert results[0].portion_confidence == FALLBACK_CONFIDENCE

    def test_first_matching_detection_used(self) -> None:
        """동일 이름 detection이 여러 개면 첫 번째 detection 사용."""
        estimator = PortionEstimator()
        item = _item("공기밥")
        det1 = _yolo_det("공기밥", SMALL_RATIO_BBOX)  # ratio 0.01 → 소량
        det2 = _yolo_det("공기밥", LARGE_RATIO_BBOX)  # ratio 0.50 → 많음
        results = estimator.estimate_items([item], detections=[det1, det2], image_area=IMAGE_AREA)
        # 첫 번째 det1의 bbox로 → 소량
        assert results[0].estimated_amount == AMOUNT_SMALL

    def test_alternatives_unchanged_in_batch(self) -> None:
        """estimate_items도 alternatives를 변경하지 않는다."""
        estimator = PortionEstimator()
        alt = MealDetection(
            class_name_ko="공기밥",
            confidence=0.5,
            bbox=None,
            source="yolo_v8",
        )
        item = _item("공기밥", alternatives=[alt])
        det = _yolo_det("공기밥", SMALL_RATIO_BBOX)
        results = estimator.estimate_items([item], detections=[det], image_area=IMAGE_AREA)
        assert results[0].alternatives == [alt]

    def test_image_area_none_all_fallback(self) -> None:
        """image_area=None이면 모든 item이 fallback."""
        estimator = PortionEstimator()
        items = [_item("a"), _item("b")]
        det_a = _yolo_det("a", SMALL_RATIO_BBOX)
        results = estimator.estimate_items(items, detections=[det_a], image_area=None)
        for r in results:
            assert r.estimated_amount == AMOUNT_MEDIUM
            assert r.portion_confidence == FALLBACK_CONFIDENCE

    def test_detection_with_none_bbox_falls_back(self) -> None:
        """매칭 detection의 bbox가 None이면 fallback."""
        estimator = PortionEstimator()
        item = _item("공기밥")
        det = _yolo_det("공기밥", bbox=None)  # GCV label hint 시뮬레이션
        results = estimator.estimate_items([item], detections=[det], image_area=IMAGE_AREA)
        assert results[0].estimated_grams == DEFAULT_SERVING
        assert results[0].portion_confidence == FALLBACK_CONFIDENCE


class TestModuleStructure:
    """파일 I/O 비-수행 및 외부 모듈 미참조를 코드 구조로 보장."""

    def test_constructs_with_no_args(self) -> None:
        """__init__이 인자를 요구하지 않는다 (Path 없음)."""
        PortionEstimator()

    def test_does_not_import_pipeline(self) -> None:
        """pipeline 모듈을 import하지 않는다 (계층 위반 방지)."""
        source = inspect.getsource(portion_estimator_module)
        assert "src.meal.pipeline" not in source

    def test_does_not_import_fusion(self) -> None:
        """fusion 모듈을 import하지 않는다 (책임 분리)."""
        source = inspect.getsource(portion_estimator_module)
        assert "src.meal.fusion" not in source

    def test_does_not_import_rda_matcher(self) -> None:
        """nutrition.rda_matcher를 import하지 않는다 (A3 책임)."""
        source = inspect.getsource(portion_estimator_module)
        assert "src.nutrition.rda_matcher" not in source
        assert "src.nutrition" not in source
