"""RDA 식품성분표 매칭 + 100g 기준 영양 프로필 생성.

dev-guide 16 §"6. rda_matcher.py" 명세를 따른다. 음식명 alias로
`korean_foods.csv` 행을 찾아 100g 기준 영양 프로필을 만든다. 사용자
입력량(g/인분) 기반 재계산은 별도 단계(A3.3 `estimate_for_amount`)에서
추가한다.

A3.1 정책:
    - 기본 표시값은 100g 기준 영양 프로필이다.
    - `nutrient_per_100g = nutrient_per_unit / unit_size_g * 100` 정규화.
    - 매칭 실패 또는 alias가 가리키는 food_code가 CSV에 없으면 항목을 버리지
      않고 `needs_user_review=True` stub 프로필을 반환한다.
    - `sugar_g`처럼 CSV에 없는 영양소는 highlights/cautions에 생성하지 않는다.
    - 의료적 단정 표현(진단/처방/치료/보장)은 사용자 노출 문구에 포함하지 않는다.
    - 본 모듈의 highlights/cautions는 정보 제공 수준의 문구만 사용한다.

Reference:
    docs/dev-guides/16-meal-recognition.md §"구현 명세 / 6. rda_matcher.py"
"""

from __future__ import annotations

import csv
import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    ValidationError,
    model_validator,
)

from src.meal.base import RecognizedMealItem
from src.meal.exceptions import MealParseError

_BASE_AMOUNT_G = 100.0
"""기본 영양 프로필 기준 양 (g). dev-guide 16 §100g 정규화 공식의 분모."""

_PROTEIN_HIGHLIGHT_THRESHOLD_PER_100G = 10.0
_FIBER_HIGHLIGHT_THRESHOLD_PER_100G = 3.0
_CALCIUM_HIGHLIGHT_THRESHOLD_PER_100G = 100.0
_IRON_HIGHLIGHT_THRESHOLD_PER_100G = 2.0
_VITAMIN_C_HIGHLIGHT_THRESHOLD_PER_100G = 20.0
_SODIUM_CAUTION_THRESHOLD_PER_100G = 600.0
"""100g 기준 임계값.

- 단백질 10g+: 정보 제공 수준의 풍부함 표시.
- 식이섬유 3g+, 칼슘 100mg+, 철분 2mg+, 비타민C 20mg+: 동일.
- 나트륨 600mg+: 함량이 다소 높음을 안내 (한국 가공식품 라벨 기준 참고).

본 값들은 의료적 권장 또는 치료 기준이 아니라 사용자에게 영양 함량을 알리는
참고 수치다.
"""


class _FoodRow(BaseModel):
    """korean_foods.csv 단일 행 (내부 표현)."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    food_code: str = Field(..., min_length=1)
    name_ko: str = Field(..., min_length=1)
    name_en: str = ""
    category: str = ""
    unit_size_g: float = Field(..., gt=0)
    kcal_per_unit: float = Field(..., ge=0)
    protein_g: float = Field(..., ge=0)
    fat_g: float = Field(..., ge=0)
    carb_g: float = Field(..., ge=0)
    fiber_g: float = Field(..., ge=0)
    sodium_mg: float = Field(..., ge=0)
    calcium_mg: float = Field(..., ge=0)
    iron_mg: float = Field(..., ge=0)
    vitamin_a_ug: float = Field(..., ge=0)
    vitamin_c_mg: float = Field(..., ge=0)


class FoodNutritionProfile(BaseModel):
    """100g 기준 영양 프로필 (RdaMatcher 출력 DTO).

    Attributes:
        food_code: 농진청 food_code. 매칭 실패 시 None.
        name_ko_canonical: CSV 기준 표준 한국어 이름 (매칭 실패 시 입력 이름 유지).
        category: 음식 분류 (CSV의 category). 빈 문자열은 None으로 정규화.
        base_amount_g: 영양 프로필 기준 양 (g). 기본 100.0.
        default_serving_g: CSV의 unit_size_g — 사용자 인분 입력 시 환산 기준.
        nutrients_per_100g: 영양소 이름 → 100g 기준 값. CSV에 없는 항목은 포함하지 않음.
        highlights: 영양 함량 풍부 정보 문구 (정보 제공 수준).
        cautions: 영양 함량 주의 정보 문구 (정보 제공 수준).
        needs_user_review: 매칭 실패 또는 시드 정합성 깨진 경우 True.
    """

    model_config = ConfigDict(frozen=True)

    food_code: str | None = None
    name_ko_canonical: str = Field(..., min_length=1)
    category: str | None = None
    base_amount_g: float = Field(default=_BASE_AMOUNT_G, gt=0)
    default_serving_g: float = Field(..., gt=0)
    nutrients_per_100g: dict[str, float] = Field(default_factory=dict)
    highlights: list[str] = Field(default_factory=list)
    cautions: list[str] = Field(default_factory=list)
    needs_user_review: bool = False


class AmountNutritionEstimate(BaseModel):
    """사용자 입력량 기반 영양소 재계산 결과 DTO.

    `FoodNutritionProfile`의 100g 기준 영양소를 사용자가 입력한 g 또는
    인분으로 환산한 결과를 담는다. 본 DTO는 100g 프로필을 대체하지 않으며,
    UI에서 사용자가 직접 양을 입력한 경우에만 추가로 노출되는 보조값이다.

    Attributes:
        food_code: 매칭된 농진청 food_code. 매칭 실패 시 None.
        name_ko_canonical: CSV 기준 표준 한국어 이름.
        amount_g: 영양소 계산에 실제 사용된 양 (g).
        serving_count: 사용자가 입력한 인분 수 (g 단위 입력 시 None).
        nutrients_for_amount: 영양소 이름 → `amount_g` 기준 값.
    """

    model_config = ConfigDict(frozen=True)

    food_code: str | None = None
    name_ko_canonical: str = Field(..., min_length=1)
    amount_g: float = Field(..., gt=0)
    serving_count: float | None = Field(default=None)
    nutrients_for_amount: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check_serving_count(self) -> AmountNutritionEstimate:
        """serving_count가 명시되면 양수여야 한다."""
        if self.serving_count is not None and self.serving_count <= 0:
            raise ValueError(f"serving_count must be > 0 when provided, got {self.serving_count}")
        return self


_FOODS_CSV_ADAPTER: TypeAdapter[list[_FoodRow]] = TypeAdapter(list[_FoodRow])
"""CSV rows → _FoodRow 리스트 검증 adapter."""


class RdaMatcher:
    """음식명 → food_code → 100g 영양 프로필 매칭기.

    의존성 주입: `aliases` (alias_name → food_code) + `foods_by_code`
    (food_code → `_FoodRow`). 외부에서 데이터를 미리 검증한 뒤 dict로
    주입하거나 `from_paths` / `from_rows` 편의 메서드로 로드한다.

    Examples:
        >>> matcher = RdaMatcher.from_paths(
        ...     aliases_path=Path("data/rda/food_aliases.json"),
        ...     foods_csv_path=Path("data/rda/korean_foods.csv"),
        ... )
        >>> profile = matcher.match("비빔밥")
        >>> profile.nutrients_per_100g["kcal"]
        112.0
    """

    def __init__(
        self,
        *,
        aliases: Mapping[str, str],
        foods_by_code: Mapping[str, _FoodRow],
    ) -> None:
        """검증된 aliases와 food 행을 주입한다.

        Args:
            aliases: alias_name → food_code 매핑.
            foods_by_code: food_code → _FoodRow 매핑.
        """
        self._aliases: dict[str, str] = dict(aliases)
        self._foods: dict[str, _FoodRow] = dict(foods_by_code)

    @classmethod
    def from_rows(
        cls,
        *,
        aliases: Mapping[str, str],
        food_rows: Iterable[Mapping[str, Any]],
    ) -> RdaMatcher:
        """raw dict rows에서 RdaMatcher를 생성한다.

        `from_paths`와 테스트가 공통으로 사용하는 검증 경로.

        Args:
            aliases: alias_name → food_code 매핑.
            food_rows: 검증할 raw dict 행들.

        Raises:
            MealParseError: 행 스키마가 `_FoodRow` 제약을 위반한 경우.
        """
        try:
            validated = _FOODS_CSV_ADAPTER.validate_python(list(food_rows))
        except ValidationError as e:
            raise MealParseError(f"food rows schema invalid: {e}") from e
        foods_by_code = {row.food_code: row for row in validated}
        return cls(aliases=aliases, foods_by_code=foods_by_code)

    @classmethod
    def from_paths(
        cls,
        *,
        aliases_path: Path,
        foods_csv_path: Path,
    ) -> RdaMatcher:
        """파일에서 aliases JSON과 foods CSV를 로드한다.

        Args:
            aliases_path: `food_aliases.json` 경로.
            foods_csv_path: `korean_foods.csv` 경로.

        Raises:
            MealParseError: 파일이 없거나 JSON/CSV 파싱·스키마가 실패한 경우.
        """
        aliases = _load_aliases(aliases_path)
        rows = _load_csv_rows(foods_csv_path)
        return cls.from_rows(aliases=aliases, food_rows=rows)

    def match(self, name_ko: str) -> FoodNutritionProfile:
        """음식명을 alias로 매핑해 100g 영양 프로필을 반환한다.

        Args:
            name_ko: 매칭 대상 한국어 음식명.

        Returns:
            `FoodNutritionProfile`. 매칭 실패 시 `needs_user_review=True`인
            stub 프로필을 반환한다 (항목을 버리지 않는다).
        """
        food_code = self._aliases.get(name_ko)
        if food_code is None:
            return _stub_profile(name_ko, food_code=None)
        row = self._foods.get(food_code)
        if row is None:
            return _stub_profile(name_ko, food_code=food_code)
        return _build_profile(row)

    def match_recognized_item(self, item: RecognizedMealItem) -> FoodNutritionProfile:
        """`RecognizedMealItem.name_ko`로 직접 매칭한다 (편의 메서드)."""
        return self.match(item.name_ko)

    def estimate_for_amount(
        self,
        profile: FoodNutritionProfile,
        *,
        amount_g: float | None = None,
        serving_count: float | None = None,
    ) -> AmountNutritionEstimate:
        """사용자 입력 g 또는 인분에 대해 영양소를 재계산한다.

        둘 중 하나만 지정해야 한다. 양쪽이 동시에 None이거나 동시에
        지정되면 `ValueError`. g/인분/profile.default_serving_g는 모두
        양수여야 한다. `model_copy(update=...)`로 외부 입력이 DTO 제약을
        우회하는 경로를 막기 위해 모든 양수 조건은 본 메서드에서 명시
        검증한다.

        공식 (dev-guide 16 §"사용자 입력량 계산"):
            - g 입력: `nutrient_for_amount = nutrient_per_100g * amount_g / 100`.
            - 인분 입력: `amount_g = default_serving_g * serving_count` 후 동일.

        Args:
            profile: 기준 100g 영양 프로필.
            amount_g: 사용자가 입력한 g.
            serving_count: 사용자가 입력한 인분 수.

        Returns:
            `AmountNutritionEstimate`.

        Raises:
            ValueError: 입력 조합이 부적절하거나 양수 제약 위반.
        """
        if amount_g is None and serving_count is None:
            raise ValueError("either amount_g or serving_count must be provided")
        if amount_g is not None and serving_count is not None:
            raise ValueError("provide either amount_g or serving_count, not both")

        if amount_g is not None:
            if amount_g <= 0:
                raise ValueError(f"amount_g must be > 0, got {amount_g}")
            actual_g = amount_g
            recorded_serving: float | None = None
        else:
            # serving_count is not None (위 분기 보장).
            assert serving_count is not None
            if serving_count <= 0:
                raise ValueError(f"serving_count must be > 0, got {serving_count}")
            if profile.default_serving_g <= 0:
                raise ValueError("profile.default_serving_g must be > 0 to use serving_count")
            actual_g = profile.default_serving_g * serving_count
            recorded_serving = serving_count

        factor = actual_g / _BASE_AMOUNT_G
        nutrients_for_amount = {
            name: value * factor for name, value in profile.nutrients_per_100g.items()
        }
        return AmountNutritionEstimate(
            food_code=profile.food_code,
            name_ko_canonical=profile.name_ko_canonical,
            amount_g=actual_g,
            serving_count=recorded_serving,
            nutrients_for_amount=nutrients_for_amount,
        )


def _load_aliases(path: Path) -> dict[str, str]:
    """aliases JSON 로드 + 타입 검증."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as e:
        raise MealParseError(f"aliases file not readable: {path}") from e
    try:
        data: Any = json.loads(raw)
    except json.JSONDecodeError as e:
        raise MealParseError(f"aliases JSON invalid: {path}") from e
    if not isinstance(data, dict):
        raise MealParseError(f"aliases root must be object, got {type(data).__name__}")
    result: dict[str, str] = {}
    for k, v in data.items():
        if not isinstance(v, str):
            raise MealParseError(f"alias value for '{k}' must be str, got {type(v).__name__}")
        result[str(k)] = v
    return result


def _load_csv_rows(path: Path) -> list[dict[str, str]]:
    """foods CSV 행을 dict 리스트로 로드한다 (검증 전)."""
    try:
        with path.open(encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            return list(reader)
    except OSError as e:
        raise MealParseError(f"foods CSV not readable: {path}") from e


def _stub_profile(name_ko: str, *, food_code: str | None) -> FoodNutritionProfile:
    """매칭 실패용 stub 프로필.

    `default_serving_g`는 Pydantic gt=0 제약을 충족시키기 위해
    `_BASE_AMOUNT_G` placeholder를 사용한다. 호출자는 `needs_user_review`로
    실제 매칭이 안 된 항목임을 인지해야 한다.
    """
    return FoodNutritionProfile(
        food_code=food_code,
        name_ko_canonical=name_ko,
        category=None,
        base_amount_g=_BASE_AMOUNT_G,
        default_serving_g=_BASE_AMOUNT_G,
        nutrients_per_100g={},
        highlights=[],
        cautions=[],
        needs_user_review=True,
    )


def _build_profile(row: _FoodRow) -> FoodNutritionProfile:
    """`_FoodRow`를 100g 프로필로 변환한다."""
    nutrients = _normalize_to_100g(row)
    highlights, cautions = _build_highlights_cautions(nutrients)
    return FoodNutritionProfile(
        food_code=row.food_code,
        name_ko_canonical=row.name_ko,
        category=row.category or None,
        base_amount_g=_BASE_AMOUNT_G,
        default_serving_g=row.unit_size_g,
        nutrients_per_100g=nutrients,
        highlights=highlights,
        cautions=cautions,
        needs_user_review=False,
    )


def _normalize_to_100g(row: _FoodRow) -> dict[str, float]:
    """`unit_size_g` 기준 값을 100g 기준으로 정규화한다.

    공식: `nutrient_per_100g = nutrient_per_unit / unit_size_g * 100`.
    CSV에 없는 영양소(sugar_g 등)는 본 매핑에 포함하지 않는다.
    """
    factor = _BASE_AMOUNT_G / row.unit_size_g
    return {
        "kcal": row.kcal_per_unit * factor,
        "protein_g": row.protein_g * factor,
        "fat_g": row.fat_g * factor,
        "carb_g": row.carb_g * factor,
        "fiber_g": row.fiber_g * factor,
        "sodium_mg": row.sodium_mg * factor,
        "calcium_mg": row.calcium_mg * factor,
        "iron_mg": row.iron_mg * factor,
        "vitamin_a_ug": row.vitamin_a_ug * factor,
        "vitamin_c_mg": row.vitamin_c_mg * factor,
    }


def _build_highlights_cautions(
    nutrients_per_100g: dict[str, float],
) -> tuple[list[str], list[str]]:
    """100g 기준 함량 임계점에 따라 정보 문구를 생성한다.

    의료적 단정 표현(진단/처방/치료/보장) 또는 효능 주장은 본 함수에서
    생성하지 않는다. 본 문구는 영양 함량 정보 제공 수준이다.
    """
    highlights: list[str] = []
    cautions: list[str] = []
    if nutrients_per_100g.get("protein_g", 0.0) >= _PROTEIN_HIGHLIGHT_THRESHOLD_PER_100G:
        highlights.append("단백질이 풍부해요")
    if nutrients_per_100g.get("fiber_g", 0.0) >= _FIBER_HIGHLIGHT_THRESHOLD_PER_100G:
        highlights.append("식이섬유가 풍부해요")
    if nutrients_per_100g.get("calcium_mg", 0.0) >= _CALCIUM_HIGHLIGHT_THRESHOLD_PER_100G:
        highlights.append("칼슘이 풍부해요")
    if nutrients_per_100g.get("iron_mg", 0.0) >= _IRON_HIGHLIGHT_THRESHOLD_PER_100G:
        highlights.append("철분이 풍부해요")
    if nutrients_per_100g.get("vitamin_c_mg", 0.0) >= _VITAMIN_C_HIGHLIGHT_THRESHOLD_PER_100G:
        highlights.append("비타민 C가 풍부해요")
    if nutrients_per_100g.get("sodium_mg", 0.0) >= _SODIUM_CAUTION_THRESHOLD_PER_100G:
        cautions.append("나트륨 함량이 다소 높아요")
    return highlights, cautions
