"""RdaMatcher + FoodNutritionProfile 단위 테스트.

dev-guide 16 §"6. rda_matcher.py"와 A3.1 정책을 검증한다.

검증 범위:
    - FoodNutritionProfile DTO 제약.
    - match() 성공/실패/시드 정합성 깨짐.
    - 100g 정규화 공식 (nutrient_per_unit / unit_size_g * 100).
    - highlights/cautions 임계점 분기.
    - CSV에 없는 영양소(sugar_g)는 결과에 포함되지 않음.
    - from_paths / from_rows 로딩 + 스키마 검증.

Reference:
    docs/dev-guides/16-meal-recognition.md
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from src.meal.base import BoundingBox, MealDetection, RecognizedMealItem
from src.meal.exceptions import MealParseError
from src.nutrition.rda_matcher import (
    AmountNutritionEstimate,
    FoodNutritionProfile,
    RdaMatcher,
)

REPO_ROOT = Path(__file__).resolve().parents[5]
REAL_ALIASES = REPO_ROOT / "data" / "rda" / "food_aliases.json"
REAL_FOODS_CSV = REPO_ROOT / "data" / "rda" / "korean_foods.csv"

BASE_AMOUNT_G = 100.0
"""dev-guide 16 §"100g 정규화 공식" 분모."""

EXPECTED_KCAL_PER_100G = 112.0
"""비빔밥 560kcal / 500g * 100 = 112 kcal/100g."""

EXPECTED_SODIUM_PER_100G_BIBIMBAP = 164.0
"""비빔밥 820mg / 500g * 100 = 164 mg/100g."""

GONGGI_BAP_UNIT_SIZE_G = 210.0
"""공기밥 단위 크기 (테스트 fixture, dev-guide 16의 CSV 값)."""


def _row(
    food_code: str,
    name_ko: str,
    *,
    unit_size_g: float = 100.0,
    kcal_per_unit: float = 0.0,
    protein_g: float = 0.0,
    fat_g: float = 0.0,
    carb_g: float = 0.0,
    fiber_g: float = 0.0,
    sodium_mg: float = 0.0,
    calcium_mg: float = 0.0,
    iron_mg: float = 0.0,
    vitamin_a_ug: float = 0.0,
    vitamin_c_mg: float = 0.0,
    category: str = "",
    name_en: str = "",
) -> dict[str, Any]:
    """테스트용 food row 팩토리 — 영양소 0 기본값으로 부분 지정 가능."""
    return {
        "food_code": food_code,
        "name_ko": name_ko,
        "name_en": name_en,
        "category": category,
        "unit_size_g": unit_size_g,
        "kcal_per_unit": kcal_per_unit,
        "protein_g": protein_g,
        "fat_g": fat_g,
        "carb_g": carb_g,
        "fiber_g": fiber_g,
        "sodium_mg": sodium_mg,
        "calcium_mg": calcium_mg,
        "iron_mg": iron_mg,
        "vitamin_a_ug": vitamin_a_ug,
        "vitamin_c_mg": vitamin_c_mg,
    }


class TestFoodNutritionProfile:
    """DTO 제약 검증."""

    def test_minimal_valid_profile(self) -> None:
        """필수 필드만 채운 정상 케이스."""
        profile = FoodNutritionProfile(
            food_code="F001",
            name_ko_canonical="공기밥",
            default_serving_g=210.0,
        )
        assert profile.food_code == "F001"
        assert profile.base_amount_g == BASE_AMOUNT_G
        assert profile.nutrients_per_100g == {}
        assert profile.highlights == []
        assert profile.cautions == []
        assert profile.needs_user_review is False

    def test_food_code_can_be_none(self) -> None:
        """매칭 실패 시 food_code=None 허용."""
        profile = FoodNutritionProfile(
            food_code=None,
            name_ko_canonical="알 수 없는 음식",
            default_serving_g=100.0,
            needs_user_review=True,
        )
        assert profile.food_code is None

    def test_empty_name_raises(self) -> None:
        """name_ko_canonical은 min_length=1."""
        with pytest.raises(ValidationError):
            FoodNutritionProfile(
                food_code="F001",
                name_ko_canonical="",
                default_serving_g=100.0,
            )

    def test_default_serving_zero_raises(self) -> None:
        """default_serving_g gt=0 제약."""
        with pytest.raises(ValidationError):
            FoodNutritionProfile(
                food_code="F001",
                name_ko_canonical="공기밥",
                default_serving_g=0,
            )

    def test_frozen_immutable(self) -> None:
        """frozen=True → 속성 변경 불가."""
        profile = FoodNutritionProfile(
            food_code="F001",
            name_ko_canonical="공기밥",
            default_serving_g=210.0,
        )
        with pytest.raises(ValidationError):
            profile.food_code = "F002"  # type: ignore[misc]


class TestMatchSuccess:
    """alias로 매칭 성공 케이스."""

    def test_known_alias_returns_profile(self) -> None:
        """등록된 alias → 정상 프로필."""
        matcher = RdaMatcher.from_rows(
            aliases={"공기밥": "F001"},
            food_rows=[
                _row(
                    "F001",
                    "공기밥",
                    unit_size_g=210.0,
                    kcal_per_unit=310.0,
                    protein_g=5.6,
                    carb_g=68.5,
                ),
            ],
        )
        profile = matcher.match("공기밥")
        assert profile.food_code == "F001"
        assert profile.name_ko_canonical == "공기밥"
        assert profile.needs_user_review is False

    def test_alias_to_canonical_name(self) -> None:
        """alias 키와 CSV의 name_ko가 달라도 CSV의 name_ko가 canonical."""
        matcher = RdaMatcher.from_rows(
            aliases={"쌀밥": "F001", "흰밥": "F001"},
            food_rows=[_row("F001", "공기밥", unit_size_g=210.0)],
        )
        profile = matcher.match("쌀밥")
        # name_ko_canonical은 CSV의 공기밥
        assert profile.name_ko_canonical == "공기밥"
        assert profile.food_code == "F001"

    def test_default_serving_from_unit_size_g(self) -> None:
        """default_serving_g는 CSV의 unit_size_g."""
        matcher = RdaMatcher.from_rows(
            aliases={"공기밥": "F001"},
            food_rows=[_row("F001", "공기밥", unit_size_g=GONGGI_BAP_UNIT_SIZE_G)],
        )
        profile = matcher.match("공기밥")
        assert profile.default_serving_g == GONGGI_BAP_UNIT_SIZE_G


class TestMatchFailure:
    """매칭 실패 → stub 프로필."""

    def test_unknown_name_returns_stub_with_review(self) -> None:
        """alias에 없는 이름 → food_code=None, needs_user_review=True."""
        matcher = RdaMatcher.from_rows(aliases={}, food_rows=[])
        profile = matcher.match("외계 음식")
        assert profile.food_code is None
        assert profile.name_ko_canonical == "외계 음식"
        assert profile.needs_user_review is True
        assert profile.nutrients_per_100g == {}
        assert profile.highlights == []
        assert profile.cautions == []

    def test_alias_to_missing_food_code_returns_stub(self) -> None:
        """alias가 가리키는 food_code가 CSV에 없음 → stub, food_code 유지."""
        matcher = RdaMatcher.from_rows(
            aliases={"공기밥": "F999"},
            food_rows=[_row("F001", "공기밥")],  # F999 없음
        )
        profile = matcher.match("공기밥")
        assert profile.food_code == "F999"
        assert profile.needs_user_review is True
        assert profile.nutrients_per_100g == {}


class TestNormalizationTo100g:
    """nutrient_per_100g = nutrient_per_unit / unit_size_g * 100."""

    def test_kcal_normalization(self) -> None:
        """비빔밥 560kcal / 500g * 100 = 112 kcal/100g."""
        matcher = RdaMatcher.from_rows(
            aliases={"비빔밥": "F003"},
            food_rows=[
                _row(
                    "F003",
                    "비빔밥",
                    unit_size_g=500.0,
                    kcal_per_unit=560.0,
                    protein_g=18.0,
                    sodium_mg=820.0,
                ),
            ],
        )
        profile = matcher.match("비빔밥")
        assert profile.nutrients_per_100g["kcal"] == pytest.approx(EXPECTED_KCAL_PER_100G)

    def test_sodium_normalization(self) -> None:
        """비빔밥 820mg / 500g * 100 = 164 mg/100g."""
        matcher = RdaMatcher.from_rows(
            aliases={"비빔밥": "F003"},
            food_rows=[
                _row(
                    "F003",
                    "비빔밥",
                    unit_size_g=500.0,
                    sodium_mg=820.0,
                ),
            ],
        )
        profile = matcher.match("비빔밥")
        assert profile.nutrients_per_100g["sodium_mg"] == pytest.approx(
            EXPECTED_SODIUM_PER_100G_BIBIMBAP
        )

    def test_unit_size_equals_100g_passes_values_through(self) -> None:
        """unit_size_g=100이면 모든 영양소가 그대로."""
        matcher = RdaMatcher.from_rows(
            aliases={"sample": "F100"},
            food_rows=[
                _row(
                    "F100",
                    "sample",
                    unit_size_g=100.0,
                    kcal_per_unit=250.0,
                    protein_g=12.0,
                    sodium_mg=500.0,
                ),
            ],
        )
        profile = matcher.match("sample")
        assert profile.nutrients_per_100g["kcal"] == pytest.approx(250.0)
        assert profile.nutrients_per_100g["protein_g"] == pytest.approx(12.0)
        assert profile.nutrients_per_100g["sodium_mg"] == pytest.approx(500.0)

    def test_all_csv_nutrients_present(self) -> None:
        """CSV 영양소 10종(kcal, protein_g, fat_g, carb_g, fiber_g, sodium_mg, calcium_mg, iron_mg, vitamin_a_ug, vitamin_c_mg) 모두 포함."""
        matcher = RdaMatcher.from_rows(
            aliases={"sample": "F100"},
            food_rows=[_row("F100", "sample", unit_size_g=100.0)],
        )
        profile = matcher.match("sample")
        expected_keys = {
            "kcal",
            "protein_g",
            "fat_g",
            "carb_g",
            "fiber_g",
            "sodium_mg",
            "calcium_mg",
            "iron_mg",
            "vitamin_a_ug",
            "vitamin_c_mg",
        }
        assert set(profile.nutrients_per_100g.keys()) == expected_keys

    def test_sugar_g_never_in_profile(self) -> None:
        """CSV에 없는 sugar_g는 nutrients_per_100g에 포함되지 않는다."""
        matcher = RdaMatcher.from_rows(
            aliases={"sample": "F100"},
            food_rows=[_row("F100", "sample", unit_size_g=100.0)],
        )
        profile = matcher.match("sample")
        assert "sugar_g" not in profile.nutrients_per_100g


class TestHighlightsCautions:
    """100g 임계점에 따른 정보 문구 생성."""

    def test_high_protein_highlight(self) -> None:
        """100g 기준 단백질 10g+ → 단백질 풍부 highlight."""
        matcher = RdaMatcher.from_rows(
            aliases={"닭가슴살": "F051"},
            food_rows=[
                _row("F051", "닭가슴살", unit_size_g=100.0, protein_g=25.0),
            ],
        )
        profile = matcher.match("닭가슴살")
        assert "단백질이 풍부해요" in profile.highlights

    def test_high_sodium_caution(self) -> None:
        """100g 기준 나트륨 600mg+ → 나트륨 caution."""
        matcher = RdaMatcher.from_rows(
            aliases={"가공식품": "F900"},
            food_rows=[
                _row("F900", "가공식품", unit_size_g=100.0, sodium_mg=800.0),
            ],
        )
        profile = matcher.match("가공식품")
        assert "나트륨 함량이 다소 높아요" in profile.cautions

    def test_balanced_food_no_highlights_or_cautions(self) -> None:
        """기준치 미달 음식 → highlights/cautions 모두 빈 리스트."""
        matcher = RdaMatcher.from_rows(
            aliases={"공기밥": "F001"},
            food_rows=[
                _row(
                    "F001",
                    "공기밥",
                    unit_size_g=210.0,
                    kcal_per_unit=310.0,
                    protein_g=5.6,
                    sodium_mg=3.0,
                ),
            ],
        )
        profile = matcher.match("공기밥")
        assert profile.highlights == []
        assert profile.cautions == []

    def test_multiple_highlights(self) -> None:
        """여러 영양소가 임계 넘으면 모두 추가."""
        matcher = RdaMatcher.from_rows(
            aliases={"슈퍼푸드": "F999"},
            food_rows=[
                _row(
                    "F999",
                    "슈퍼푸드",
                    unit_size_g=100.0,
                    protein_g=20.0,
                    fiber_g=5.0,
                    calcium_mg=200.0,
                    iron_mg=3.0,
                    vitamin_c_mg=30.0,
                ),
            ],
        )
        profile = matcher.match("슈퍼푸드")
        assert "단백질이 풍부해요" in profile.highlights
        assert "식이섬유가 풍부해요" in profile.highlights
        assert "칼슘이 풍부해요" in profile.highlights
        assert "철분이 풍부해요" in profile.highlights
        assert "비타민 C가 풍부해요" in profile.highlights

    def test_stub_profile_has_empty_highlights_cautions(self) -> None:
        """매칭 실패 stub은 정보 문구 없음."""
        matcher = RdaMatcher.from_rows(aliases={}, food_rows=[])
        profile = matcher.match("???")
        assert profile.highlights == []
        assert profile.cautions == []


class TestMatchRecognizedItem:
    """RecognizedMealItem 편의 매칭."""

    def test_uses_name_ko(self) -> None:
        """RecognizedMealItem.name_ko를 사용해 매칭."""
        matcher = RdaMatcher.from_rows(
            aliases={"공기밥": "F001"},
            food_rows=[_row("F001", "공기밥", unit_size_g=210.0)],
        )
        item = RecognizedMealItem(
            name_ko="공기밥",
            estimated_grams=100.0,
            confidence=0.9,
            portion_confidence=0.6,
        )
        profile = matcher.match_recognized_item(item)
        assert profile.food_code == "F001"


class TestFromRows:
    """from_rows 클래스 메서드."""

    def test_invalid_row_raises_meal_parse_error(self) -> None:
        """unit_size_g<=0 등 스키마 위반 → MealParseError."""
        with pytest.raises(MealParseError):
            RdaMatcher.from_rows(
                aliases={},
                food_rows=[
                    {
                        "food_code": "F001",
                        "name_ko": "잘못된 행",
                        "name_en": "",
                        "category": "",
                        "unit_size_g": 0,  # gt=0 위반
                        "kcal_per_unit": 100,
                        "protein_g": 0,
                        "fat_g": 0,
                        "carb_g": 0,
                        "fiber_g": 0,
                        "sodium_mg": 0,
                        "calcium_mg": 0,
                        "iron_mg": 0,
                        "vitamin_a_ug": 0,
                        "vitamin_c_mg": 0,
                    },
                ],
            )

    def test_extra_columns_ignored(self) -> None:
        """CSV에 없는 추가 컬럼은 silently ignore."""
        matcher = RdaMatcher.from_rows(
            aliases={"sample": "F100"},
            food_rows=[
                {**_row("F100", "sample"), "unknown_extra_column": "ignored"},
            ],
        )
        profile = matcher.match("sample")
        assert profile.food_code == "F100"


class TestFromPaths:
    """파일 로드 경로."""

    def test_loads_real_files(self) -> None:
        """실 data/rda 파일들로 로드 성공."""
        matcher = RdaMatcher.from_paths(
            aliases_path=REAL_ALIASES,
            foods_csv_path=REAL_FOODS_CSV,
        )
        profile = matcher.match("공기밥")
        assert profile.food_code is not None
        assert profile.needs_user_review is False

    def test_missing_aliases_raises_meal_parse_error(self, tmp_path: Path) -> None:
        """aliases 파일 누락 → MealParseError."""
        csv_path = tmp_path / "foods.csv"
        csv_path.write_text("food_code\nF001\n", encoding="utf-8")
        with pytest.raises(MealParseError):
            RdaMatcher.from_paths(
                aliases_path=tmp_path / "missing.json",
                foods_csv_path=csv_path,
            )

    def test_missing_csv_raises_meal_parse_error(self, tmp_path: Path) -> None:
        """CSV 파일 누락 → MealParseError."""
        aliases_path = tmp_path / "aliases.json"
        aliases_path.write_text("{}", encoding="utf-8")
        with pytest.raises(MealParseError):
            RdaMatcher.from_paths(
                aliases_path=aliases_path,
                foods_csv_path=tmp_path / "missing.csv",
            )

    def test_malformed_aliases_json_raises(self, tmp_path: Path) -> None:
        """malformed JSON → MealParseError."""
        bad = tmp_path / "aliases.json"
        bad.write_text("not json {{{", encoding="utf-8")
        csv_path = tmp_path / "foods.csv"
        csv_path.write_text("food_code\nF001\n", encoding="utf-8")
        with pytest.raises(MealParseError):
            RdaMatcher.from_paths(
                aliases_path=bad,
                foods_csv_path=csv_path,
            )

    def test_aliases_value_must_be_string(self, tmp_path: Path) -> None:
        """alias value가 string이 아니면 MealParseError."""
        bad = tmp_path / "aliases.json"
        bad.write_text(
            json.dumps({"공기밥": 123}),  # int 값 — 위반
            encoding="utf-8",
        )
        csv_path = tmp_path / "foods.csv"
        csv_path.write_text("food_code\nF001\n", encoding="utf-8")
        with pytest.raises(MealParseError):
            RdaMatcher.from_paths(
                aliases_path=bad,
                foods_csv_path=csv_path,
            )


class TestMockDataUsage:
    """MealDetection / BoundingBox 등 의존 타입 import 확인용 smoke test."""

    def test_imports_intact(self) -> None:
        """import 후 인스턴스화 가능."""
        bbox = BoundingBox(x_min=0, y_min=0, x_max=10, y_max=10)
        det = MealDetection(
            class_name_ko="공기밥",
            confidence=0.9,
            bbox=bbox,
            source="yolo_v8",
        )
        assert det.class_name_ko == "공기밥"


# ── A3.3: AmountNutritionEstimate + estimate_for_amount ──────────────────


SAMPLE_PROTEIN_PER_100G = 20.0
SAMPLE_KCAL_PER_100G = 200.0
SAMPLE_SODIUM_PER_100G = 400.0
SAMPLE_UNIT_SIZE_G = 200.0


def _sample_profile() -> FoodNutritionProfile:
    """테스트용 단순 100g 프로필."""
    return FoodNutritionProfile(
        food_code="F999",
        name_ko_canonical="샘플",
        default_serving_g=SAMPLE_UNIT_SIZE_G,
        nutrients_per_100g={
            "kcal": SAMPLE_KCAL_PER_100G,
            "protein_g": SAMPLE_PROTEIN_PER_100G,
            "sodium_mg": SAMPLE_SODIUM_PER_100G,
        },
    )


class TestAmountNutritionEstimateDTO:
    """AmountNutritionEstimate DTO 제약."""

    def test_minimal_valid(self) -> None:
        est = AmountNutritionEstimate(
            food_code="F001",
            name_ko_canonical="공기밥",
            amount_g=210.0,
        )
        assert est.amount_g == GONGGI_BAP_UNIT_SIZE_G
        assert est.serving_count is None
        assert est.nutrients_for_amount == {}

    def test_amount_g_zero_raises(self) -> None:
        with pytest.raises(ValidationError):
            AmountNutritionEstimate(
                food_code="F001",
                name_ko_canonical="공기밥",
                amount_g=0,
            )

    def test_amount_g_negative_raises(self) -> None:
        with pytest.raises(ValidationError):
            AmountNutritionEstimate(
                food_code="F001",
                name_ko_canonical="공기밥",
                amount_g=-1.0,
            )

    def test_serving_count_zero_raises(self) -> None:
        """serving_count는 명시되면 양수여야 함."""
        with pytest.raises(ValidationError):
            AmountNutritionEstimate(
                food_code="F001",
                name_ko_canonical="공기밥",
                amount_g=100.0,
                serving_count=0,
            )

    def test_serving_count_negative_raises(self) -> None:
        with pytest.raises(ValidationError):
            AmountNutritionEstimate(
                food_code="F001",
                name_ko_canonical="공기밥",
                amount_g=100.0,
                serving_count=-1.0,
            )

    def test_serving_count_none_allowed(self) -> None:
        """serving_count=None은 정상."""
        est = AmountNutritionEstimate(
            food_code="F001",
            name_ko_canonical="공기밥",
            amount_g=100.0,
            serving_count=None,
        )
        assert est.serving_count is None

    def test_frozen(self) -> None:
        est = AmountNutritionEstimate(
            food_code=None,
            name_ko_canonical="x",
            amount_g=100.0,
        )
        with pytest.raises(ValidationError):
            est.amount_g = 200.0  # type: ignore[misc]


class TestEstimateForAmountByGrams:
    """g 입력 경로."""

    def test_basic_scaling(self) -> None:
        """nutrient_for_amount = nutrient_per_100g * amount_g / 100."""
        matcher = RdaMatcher.from_rows(aliases={}, food_rows=[])
        est = matcher.estimate_for_amount(_sample_profile(), amount_g=50.0)
        # 50g → 1/2 of per-100g
        expected_kcal = SAMPLE_KCAL_PER_100G * 50.0 / 100.0
        expected_protein = SAMPLE_PROTEIN_PER_100G * 50.0 / 100.0
        assert est.nutrients_for_amount["kcal"] == pytest.approx(expected_kcal)
        assert est.nutrients_for_amount["protein_g"] == pytest.approx(expected_protein)

    def test_amount_g_recorded(self) -> None:
        matcher = RdaMatcher.from_rows(aliases={}, food_rows=[])
        est = matcher.estimate_for_amount(_sample_profile(), amount_g=150.0)
        assert est.amount_g == pytest.approx(150.0)

    def test_serving_count_none_when_using_grams(self) -> None:
        """g 입력 시 serving_count는 None으로 기록."""
        matcher = RdaMatcher.from_rows(aliases={}, food_rows=[])
        est = matcher.estimate_for_amount(_sample_profile(), amount_g=50.0)
        assert est.serving_count is None

    def test_food_code_propagated(self) -> None:
        matcher = RdaMatcher.from_rows(aliases={}, food_rows=[])
        est = matcher.estimate_for_amount(_sample_profile(), amount_g=100.0)
        assert est.food_code == "F999"
        assert est.name_ko_canonical == "샘플"


class TestEstimateForAmountByServing:
    """인분 입력 경로."""

    def test_serving_count_converted_to_grams(self) -> None:
        """amount_g = default_serving_g * serving_count."""
        matcher = RdaMatcher.from_rows(aliases={}, food_rows=[])
        # default_serving_g=200, serving_count=2 → 400g
        est = matcher.estimate_for_amount(_sample_profile(), serving_count=2.0)
        assert est.amount_g == pytest.approx(400.0)

    def test_serving_count_recorded(self) -> None:
        matcher = RdaMatcher.from_rows(aliases={}, food_rows=[])
        est = matcher.estimate_for_amount(_sample_profile(), serving_count=1.5)
        assert est.serving_count == pytest.approx(1.5)

    def test_nutrients_scaled_for_converted_grams(self) -> None:
        """인분→g 환산 후 nutrients가 scaled."""
        matcher = RdaMatcher.from_rows(aliases={}, food_rows=[])
        # 2인분 x 200g = 400g → x4 of per-100g
        est = matcher.estimate_for_amount(_sample_profile(), serving_count=2.0)
        expected_kcal = SAMPLE_KCAL_PER_100G * 400.0 / 100.0
        assert est.nutrients_for_amount["kcal"] == pytest.approx(expected_kcal)


class TestEstimateForAmountValidation:
    """입력 조합·양수 제약 검증."""

    def test_neither_raises(self) -> None:
        """g와 인분 모두 None → ValueError."""
        matcher = RdaMatcher.from_rows(aliases={}, food_rows=[])
        with pytest.raises(ValueError, match=r"amount_g.*serving_count"):
            matcher.estimate_for_amount(_sample_profile())

    def test_both_raises(self) -> None:
        """g와 인분 모두 명시 → ValueError."""
        matcher = RdaMatcher.from_rows(aliases={}, food_rows=[])
        with pytest.raises(ValueError, match="not both"):
            matcher.estimate_for_amount(_sample_profile(), amount_g=100.0, serving_count=1.0)

    def test_amount_g_zero_raises(self) -> None:
        matcher = RdaMatcher.from_rows(aliases={}, food_rows=[])
        with pytest.raises(ValueError, match="amount_g"):
            matcher.estimate_for_amount(_sample_profile(), amount_g=0)

    def test_amount_g_negative_raises(self) -> None:
        matcher = RdaMatcher.from_rows(aliases={}, food_rows=[])
        with pytest.raises(ValueError, match="amount_g"):
            matcher.estimate_for_amount(_sample_profile(), amount_g=-1.0)

    def test_serving_count_zero_raises(self) -> None:
        matcher = RdaMatcher.from_rows(aliases={}, food_rows=[])
        with pytest.raises(ValueError, match="serving_count"):
            matcher.estimate_for_amount(_sample_profile(), serving_count=0)

    def test_serving_count_negative_raises(self) -> None:
        matcher = RdaMatcher.from_rows(aliases={}, food_rows=[])
        with pytest.raises(ValueError, match="serving_count"):
            matcher.estimate_for_amount(_sample_profile(), serving_count=-2.0)


class TestEstimateForAmountWithStubProfile:
    """매칭 실패한 stub 프로필에 대한 scaling 처리."""

    def test_stub_profile_returns_empty_nutrients(self) -> None:
        """nutrients_per_100g가 비면 nutrients_for_amount도 빈 dict."""
        matcher = RdaMatcher.from_rows(aliases={}, food_rows=[])
        stub = matcher.match("???")  # stub
        est = matcher.estimate_for_amount(stub, amount_g=100.0)
        assert est.nutrients_for_amount == {}
        assert est.food_code is None
        assert est.amount_g == pytest.approx(100.0)
