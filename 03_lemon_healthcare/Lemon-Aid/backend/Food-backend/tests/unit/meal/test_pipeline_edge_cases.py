"""Pipeline + RdaMatcher 통합 edge case 테스트.

dev-guide 16 §"테스트 전략 / Unit" + A3 edge case 정책을 검증한다.

다루는 케이스:
    - 모든 YOLO detection이 conf < 0.40 → 자동 확정 X, 항목 보존.
    - 1글자 음식명 / 특수문자 포함 이름 → pipeline 안전 처리.
    - RDA 매칭 실패 음식도 RecognizedMeal에 보존 (버리지 않음).
    - RDA 매칭 성공·실패 혼합 → 각 item이 독립 결과.
    - 빈 fixture (detections=[]) → 빈 items.
    - 영문 음식명 (alias bridge 없음) → 매칭 실패 stub 반환.

A2.1~A2.5의 실 구현체 + A3.1 RdaMatcher를 사용한 cross-module 통합 검증.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from src.meal.base import RecognizedMeal
from src.meal.fusion import MealFusionEngine
from src.meal.google_vision import MockGoogleVisionMealHintAdapter
from src.meal.pipeline import MealPipeline
from src.meal.portion_estimator import PortionEstimator
from src.meal.yolo_v8 import MockYoloV8MealDetector
from src.nutrition.rda_matcher import FoodNutritionProfile, RdaMatcher

REPO_ROOT = Path(__file__).resolve().parents[5]

IMAGE_AREA_TEST = 10_000.0
LOW_CONF_VALUE = 0.32
LOW_CONF_BAND_UPPER = 0.4
EXPECTED_TWO_ITEMS = 2

ALIASES_FOR_EDGE: dict[str, str] = {
    "공기밥": "F001",
    "비빔밥": "F003",
}

# 최소 영양 데이터 — edge case 검증에 충분.
EDGE_FOOD_ROWS = [
    {
        "food_code": "F001",
        "name_ko": "공기밥",
        "name_en": "",
        "category": "밥류",
        "unit_size_g": 210.0,
        "kcal_per_unit": 310.0,
        "protein_g": 5.6,
        "fat_g": 0.6,
        "carb_g": 68.5,
        "fiber_g": 1.2,
        "sodium_mg": 3.0,
        "calcium_mg": 8.0,
        "iron_mg": 0.2,
        "vitamin_a_ug": 0.0,
        "vitamin_c_mg": 0.0,
    },
    {
        "food_code": "F003",
        "name_ko": "비빔밥",
        "name_en": "",
        "category": "밥류",
        "unit_size_g": 500.0,
        "kcal_per_unit": 560.0,
        "protein_g": 18.0,
        "fat_g": 15.0,
        "carb_g": 82.0,
        "fiber_g": 7.0,
        "sodium_mg": 820.0,
        "calcium_mg": 90.0,
        "iron_mg": 3.6,
        "vitamin_a_ug": 180.0,
        "vitamin_c_mg": 12.0,
    },
]


def _build_matcher() -> RdaMatcher:
    return RdaMatcher.from_rows(aliases=ALIASES_FOR_EDGE, food_rows=EDGE_FOOD_ROWS)


def _build_pipeline(fixture_path: Path) -> MealPipeline:
    return MealPipeline(
        yolo_detector=MockYoloV8MealDetector(fixture_path),
        gcv_adapter=MockGoogleVisionMealHintAdapter(fixture_path),
        fusion_engine=MealFusionEngine(aliases=ALIASES_FOR_EDGE),
        portion_estimator=PortionEstimator(),
        image_area=IMAGE_AREA_TEST,
    )


def _write_fixture(tmp_path: Path, data: dict[str, object]) -> Path:
    """tmp_path에 mock_predictions.json 형태의 fixture를 쓴다."""
    fx = tmp_path / "fx.json"
    fx.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return fx


class TestAllLowConfidence:
    """모든 detection이 conf < 0.40 — 자동 확정 X, 보존."""

    async def test_all_items_review_and_preserved(self, tmp_path: Path) -> None:
        fx = _write_fixture(
            tmp_path,
            {
                "all-low.jpg": {
                    "detections": [
                        {
                            "class_id": 0,
                            "class_name_ko": "공기밥",
                            "confidence": 0.32,
                            "bbox_xyxy": [0, 0, 50, 50],
                        },
                        {
                            "class_id": 3,
                            "class_name_ko": "비빔밥",
                            "confidence": 0.25,
                            "bbox_xyxy": [60, 0, 110, 50],
                        },
                    ],
                    "gcv_hints": {"labels": [], "ocr_text": ""},
                }
            },
        )
        pipeline = _build_pipeline(fx)
        meal: RecognizedMeal = await pipeline.recognize_from_fixture_key("all-low.jpg")
        # 모두 보존됨 (버려지지 않음).
        assert len(meal.items) == EXPECTED_TWO_ITEMS
        # 모두 review=True.
        for item in meal.items:
            assert item.needs_user_review is True
            assert item.confidence < LOW_CONF_BAND_UPPER

    async def test_low_conf_still_matched_in_rda(self, tmp_path: Path) -> None:
        """저신뢰도 item도 RDA matcher로 100g profile 매칭 가능."""
        fx = _write_fixture(
            tmp_path,
            {
                "low.jpg": {
                    "detections": [
                        {
                            "class_id": 0,
                            "class_name_ko": "공기밥",
                            "confidence": LOW_CONF_VALUE,
                            "bbox_xyxy": [0, 0, 50, 50],
                        }
                    ],
                    "gcv_hints": {"labels": [], "ocr_text": ""},
                }
            },
        )
        pipeline = _build_pipeline(fx)
        matcher = _build_matcher()
        meal = await pipeline.recognize_from_fixture_key("low.jpg")
        assert len(meal.items) == 1
        profile = matcher.match_recognized_item(meal.items[0])
        assert profile.food_code == "F001"
        assert profile.needs_user_review is False  # RDA matching 자체는 성공


class TestUnusualFoodNames:
    """1글자 / 특수문자 / 영문 음식명 안전 처리."""

    async def test_single_char_name(self, tmp_path: Path) -> None:
        """1글자 음식명 (예: '죽') — DTO 제약 통과 + pipeline 동작."""
        fx = _write_fixture(
            tmp_path,
            {
                "single-char.jpg": {
                    "detections": [
                        {
                            "class_id": 0,
                            "class_name_ko": "죽",
                            "confidence": 0.8,
                            "bbox_xyxy": [0, 0, 50, 50],
                        }
                    ],
                    "gcv_hints": {"labels": [], "ocr_text": ""},
                }
            },
        )
        pipeline = _build_pipeline(fx)
        meal = await pipeline.recognize_from_fixture_key("single-char.jpg")
        assert len(meal.items) == 1
        assert meal.items[0].name_ko == "죽"

    async def test_special_char_name(self, tmp_path: Path) -> None:
        """특수문자 포함 음식명 (예: '스파게티(미트소스)')."""
        fx = _write_fixture(
            tmp_path,
            {
                "special.jpg": {
                    "detections": [
                        {
                            "class_id": 0,
                            "class_name_ko": "스파게티(미트소스)",
                            "confidence": 0.85,
                            "bbox_xyxy": [0, 0, 50, 50],
                        }
                    ],
                    "gcv_hints": {"labels": [], "ocr_text": ""},
                }
            },
        )
        pipeline = _build_pipeline(fx)
        meal = await pipeline.recognize_from_fixture_key("special.jpg")
        assert len(meal.items) == 1
        assert meal.items[0].name_ko == "스파게티(미트소스)"

    async def test_english_name_not_in_aliases(self, tmp_path: Path) -> None:
        """영문 'bibimbap'은 aliases bridge 없으면 매칭 실패 stub."""
        fx = _write_fixture(
            tmp_path,
            {
                "en.jpg": {
                    "detections": [
                        {
                            "class_id": 0,
                            "class_name_ko": "bibimbap",
                            "confidence": 0.85,
                            "bbox_xyxy": [0, 0, 50, 50],
                        }
                    ],
                    "gcv_hints": {"labels": [], "ocr_text": ""},
                }
            },
        )
        pipeline = _build_pipeline(fx)
        matcher = _build_matcher()
        meal = await pipeline.recognize_from_fixture_key("en.jpg")
        assert meal.items[0].name_ko == "bibimbap"
        # RDA matching 실패 → stub
        profile = matcher.match_recognized_item(meal.items[0])
        assert profile.food_code is None
        assert profile.needs_user_review is True


class TestRdaMatchingFailurePreservation:
    """RDA 매칭 실패 음식도 RecognizedMeal에 보존 (항목 버리지 않음)."""

    async def test_unknown_food_item_kept_in_recognized_meal(self, tmp_path: Path) -> None:
        """alias에 없는 음식도 pipeline은 RecognizedMealItem으로 반환."""
        fx = _write_fixture(
            tmp_path,
            {
                "unknown.jpg": {
                    "detections": [
                        {
                            "class_id": 0,
                            "class_name_ko": "외계행성요리",
                            "confidence": 0.88,
                            "bbox_xyxy": [0, 0, 50, 50],
                        }
                    ],
                    "gcv_hints": {"labels": [], "ocr_text": ""},
                }
            },
        )
        pipeline = _build_pipeline(fx)
        meal = await pipeline.recognize_from_fixture_key("unknown.jpg")
        assert len(meal.items) == 1
        # RDA 별도 호출 → stub profile
        matcher = _build_matcher()
        profile = matcher.match_recognized_item(meal.items[0])
        assert profile.needs_user_review is True
        assert profile.food_code is None

    async def test_mixed_match_success_and_failure(self, tmp_path: Path) -> None:
        """일부 매칭 성공 + 일부 실패 → 각 item이 독립적으로 처리."""
        fx = _write_fixture(
            tmp_path,
            {
                "mixed.jpg": {
                    "detections": [
                        {
                            "class_id": 0,
                            "class_name_ko": "공기밥",  # 매칭 성공
                            "confidence": 0.91,
                            "bbox_xyxy": [0, 0, 50, 50],
                        },
                        {
                            "class_id": 1,
                            "class_name_ko": "외계음식",  # 매칭 실패
                            "confidence": 0.85,
                            "bbox_xyxy": [60, 0, 110, 50],
                        },
                    ],
                    "gcv_hints": {"labels": [], "ocr_text": ""},
                }
            },
        )
        pipeline = _build_pipeline(fx)
        matcher = _build_matcher()
        meal = await pipeline.recognize_from_fixture_key("mixed.jpg")
        assert len(meal.items) == EXPECTED_TWO_ITEMS

        profiles: dict[str, FoodNutritionProfile] = {}
        for item in meal.items:
            profiles[item.name_ko] = matcher.match_recognized_item(item)

        # 공기밥: 정상 매칭
        assert profiles["공기밥"].food_code == "F001"
        assert profiles["공기밥"].needs_user_review is False
        assert profiles["공기밥"].nutrients_per_100g  # non-empty

        # 외계음식: 매칭 실패 stub
        assert profiles["외계음식"].food_code is None
        assert profiles["외계음식"].needs_user_review is True
        assert profiles["외계음식"].nutrients_per_100g == {}


class TestEmptyFixture:
    """detection이 비어도 안전 처리."""

    async def test_empty_detections_returns_empty_items(self, tmp_path: Path) -> None:
        fx = _write_fixture(
            tmp_path,
            {
                "empty.jpg": {
                    "detections": [],
                    "gcv_hints": {"labels": [], "ocr_text": ""},
                }
            },
        )
        pipeline = _build_pipeline(fx)
        meal = await pipeline.recognize_from_fixture_key("empty.jpg")
        assert meal.items == []
        # raw_input / engine 정상.
        assert meal.raw_input == "empty.jpg"
        assert meal.engine

    @pytest.mark.parametrize(
        ("name_ko",),
        [
            ("죽",),  # 1글자
            ("ABC",),  # 영문
            ("음식123",),  # 숫자 포함
            ("음식·요리",),  # 가운데 점
        ],
    )
    async def test_various_name_formats_parametrized(self, name_ko: str, tmp_path: Path) -> None:
        """다양한 음식명 포맷도 pipeline에서 안전 처리."""
        fx = _write_fixture(
            tmp_path,
            {
                "var.jpg": {
                    "detections": [
                        {
                            "class_id": 0,
                            "class_name_ko": name_ko,
                            "confidence": 0.85,
                            "bbox_xyxy": [0, 0, 50, 50],
                        }
                    ],
                    "gcv_hints": {"labels": [], "ocr_text": ""},
                }
            },
        )
        pipeline = _build_pipeline(fx)
        meal = await pipeline.recognize_from_fixture_key("var.jpg")
        assert len(meal.items) == 1
        assert meal.items[0].name_ko == name_ko
