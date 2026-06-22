"""이미지 인식 결과 → 100g 영양 프로필 통합 테스트.

dev-guide 16 §"입력 방식 / 방식 A" 전체 플로우를 실 mock 데이터와 실
data/rda 시드로 검증한다.

검증 플로우:
    1. MealPipeline.recognize_from_fixture_key(...) → RecognizedMeal
    2. RdaMatcher.match_recognized_item(item) → FoodNutritionProfile (100g 기준)
    3. (옵션) RdaMatcher.estimate_for_amount(profile, ...) → AmountNutritionEstimate

본 단계에서는 dev-guide 06의 NutrientIntake 변환은 다루지 않으며, 100g 프로필
+ 사용자 입력량 기반 재계산까지만 검증한다.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from src.meal.fusion import MealFusionEngine
from src.meal.google_vision import MockGoogleVisionMealHintAdapter
from src.meal.pipeline import MealPipeline
from src.meal.portion_estimator import PortionEstimator
from src.meal.yolo_v8 import MockYoloV8MealDetector
from src.nutrition.rda_matcher import (
    AmountNutritionEstimate,
    FoodNutritionProfile,
    RdaMatcher,
)

REPO_ROOT = Path(__file__).resolve().parents[5]
MOCK_FIXTURES = REPO_ROOT / "data" / "meal_vision" / "mock_predictions.json"
REAL_ALIASES = REPO_ROOT / "data" / "rda" / "food_aliases.json"
REAL_FOODS_CSV = REPO_ROOT / "data" / "rda" / "korean_foods.csv"

KIMCHI_STEW_RICE_KEY = "sample_kimchi_stew_rice.jpg"
BIBIMBAP_SOLO_KEY = "sample_bibimbap_solo.jpg"

IMAGE_AREA_TEST = 1024 * 1024  # 1MP 가정
USER_AMOUNT_G = 250.0
USER_SERVING_COUNT = 1.5

EXPECTED_TWO_ITEMS = 2
EXPECTED_ONE_ITEM = 1


def _build_pipeline() -> MealPipeline:
    """real mock fixture + real food_aliases.json을 사용한 pipeline."""
    aliases: dict[str, str] = json.loads(REAL_ALIASES.read_text(encoding="utf-8"))
    return MealPipeline(
        yolo_detector=MockYoloV8MealDetector(MOCK_FIXTURES),
        gcv_adapter=MockGoogleVisionMealHintAdapter(MOCK_FIXTURES),
        fusion_engine=MealFusionEngine(aliases=aliases),
        portion_estimator=PortionEstimator(),
        image_area=IMAGE_AREA_TEST,
    )


def _build_matcher() -> RdaMatcher:
    """real data/rda 시드로 RdaMatcher 생성."""
    return RdaMatcher.from_paths(
        aliases_path=REAL_ALIASES,
        foods_csv_path=REAL_FOODS_CSV,
    )


class TestImageToProfileEndToEnd:
    """이미지(fixture_key) → RecognizedMeal → 100g profile 전체 플로우."""

    async def test_kimchi_stew_rice_to_two_profiles(self) -> None:
        """김치찌개+공기밥 fixture → 두 음식 모두 매칭 + 100g 영양 정상."""
        pipeline = _build_pipeline()
        matcher = _build_matcher()
        meal = await pipeline.recognize_from_fixture_key(KIMCHI_STEW_RICE_KEY)
        assert len(meal.items) == EXPECTED_TWO_ITEMS

        profiles = [matcher.match_recognized_item(it) for it in meal.items]
        for profile in profiles:
            assert isinstance(profile, FoodNutritionProfile)
            assert profile.food_code is not None
            assert profile.needs_user_review is False
            assert profile.nutrients_per_100g  # non-empty
            assert profile.default_serving_g > 0

    async def test_bibimbap_solo_profile_kcal_per_100g(self) -> None:
        """비빔밥 fixture → real CSV 비빔밥 100g 영양 검증.

        비빔밥 unit=500g, kcal=560 → 100g 기준 112 kcal.
        """
        pipeline = _build_pipeline()
        matcher = _build_matcher()
        meal = await pipeline.recognize_from_fixture_key(BIBIMBAP_SOLO_KEY)
        assert len(meal.items) == EXPECTED_ONE_ITEM
        item = meal.items[0]
        assert item.name_ko == "비빔밥"

        profile = matcher.match_recognized_item(item)
        assert profile.food_code == "F003"
        expected_kcal_per_100g = 560.0 / 500.0 * 100.0
        assert profile.nutrients_per_100g["kcal"] == pytest.approx(expected_kcal_per_100g)

    async def test_food_code_present_for_known_foods(self) -> None:
        """real fixture의 음식은 real food_aliases.json에 모두 등록되어 있어 매칭 성공."""
        pipeline = _build_pipeline()
        matcher = _build_matcher()
        meal = await pipeline.recognize_from_fixture_key(KIMCHI_STEW_RICE_KEY)
        for item in meal.items:
            profile = matcher.match_recognized_item(item)
            assert profile.food_code is not None


class TestAmountEstimateFromImageProfile:
    """이미지 인식 결과의 profile에 사용자 양 입력 적용."""

    async def test_user_amount_g_scales_nutrients(self) -> None:
        """사용자가 250g 입력 → 100g 기준 값의 2.5배로 scaled."""
        pipeline = _build_pipeline()
        matcher = _build_matcher()
        meal = await pipeline.recognize_from_fixture_key(BIBIMBAP_SOLO_KEY)
        profile = matcher.match_recognized_item(meal.items[0])
        estimate = matcher.estimate_for_amount(profile, amount_g=USER_AMOUNT_G)
        assert isinstance(estimate, AmountNutritionEstimate)
        assert estimate.amount_g == pytest.approx(USER_AMOUNT_G)
        # 250g = 100g x 2.5 → kcal도 2.5배
        expected_kcal = profile.nutrients_per_100g["kcal"] * (USER_AMOUNT_G / 100.0)
        assert estimate.nutrients_for_amount["kcal"] == pytest.approx(expected_kcal)

    async def test_user_serving_count_converted_to_grams(self) -> None:
        """사용자가 1.5인분 입력 → amount_g = default_serving_g x 1.5."""
        pipeline = _build_pipeline()
        matcher = _build_matcher()
        meal = await pipeline.recognize_from_fixture_key(BIBIMBAP_SOLO_KEY)
        profile = matcher.match_recognized_item(meal.items[0])
        estimate = matcher.estimate_for_amount(profile, serving_count=USER_SERVING_COUNT)
        expected_g = profile.default_serving_g * USER_SERVING_COUNT
        assert estimate.amount_g == pytest.approx(expected_g)
        assert estimate.serving_count == pytest.approx(USER_SERVING_COUNT)


class TestImagePortionDoesNotDriveNutrition:
    """이미지 기반 estimated_grams는 기본 영양 계산에 사용되지 않는다 (A3 정책).

    PortionEstimator의 결과는 UI 참고/미래 확장용. 기본 영양은 100g 프로필,
    그리고 사용자가 직접 입력한 g/인분 기준 재계산만 사용한다.
    """

    async def test_image_estimated_grams_independent_of_profile(self) -> None:
        """RecognizedMealItem.estimated_grams는 FoodNutritionProfile 생성에 영향 없음."""
        pipeline = _build_pipeline()
        matcher = _build_matcher()
        meal = await pipeline.recognize_from_fixture_key(BIBIMBAP_SOLO_KEY)
        item = meal.items[0]
        # 이미지 추정 g는 100/0.7/1.0/1.2 중 하나.
        assert item.estimated_grams > 0  # 값 존재
        # 100g 프로필은 estimated_grams와 무관 — CSV unit_size_g 기반.
        profile = matcher.match_recognized_item(item)
        # 비빔밥 unit_size_g = 500.0 (CSV 값).
        assert profile.default_serving_g == pytest.approx(500.0)
        # 이미지 추정값은 default_serving_g와 일반적으로 다르다.
        # (이 동일성/차이 자체가 핵심은 아니지만, 두 값이 독립 계산됨을 시각화)
