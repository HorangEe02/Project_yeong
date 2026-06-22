"""MealTextParser 단위 테스트.

dev-guide 16 §"입력 방식 / 방식 B"와 A3.2 정책을 검증한다.

검증 범위:
    - meal_type prefix 인식.
    - 음식 분리자(comma, semicolon, 와/과, 그리고).
    - 양 표현 추출(개/공기/인분 등).
    - 빈 입력 / prefix-only 입력 안전 처리.
    - DTO 제약.

Reference:
    docs/dev-guides/16-meal-recognition.md §"입력 방식 / 방식 B"
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from src.meal.text_parser import MealTextParser, ParsedMealItem, ParsedMealText

EXPECTED_THREE_ITEMS = 3
EXPECTED_TWO_ITEMS = 2


class TestEmptyInput:
    """빈 입력 안전 처리."""

    def test_empty_string_returns_empty_text(self) -> None:
        result = MealTextParser().parse("")
        assert result.meal_type is None
        assert result.items == []

    def test_whitespace_only_returns_empty(self) -> None:
        result = MealTextParser().parse("   \n  \t ")
        assert result.meal_type is None
        assert result.items == []


class TestMealTypePrefix:
    """식사 시간대 prefix 인식."""

    def test_breakfast_prefix(self) -> None:
        result = MealTextParser().parse("아침: 토스트")
        assert result.meal_type == "breakfast"

    def test_lunch_prefix(self) -> None:
        result = MealTextParser().parse("점심: 김치찌개")
        assert result.meal_type == "lunch"

    def test_dinner_prefix(self) -> None:
        result = MealTextParser().parse("저녁: 비빔밥")
        assert result.meal_type == "dinner"

    def test_snack_prefix(self) -> None:
        result = MealTextParser().parse("간식: 사과")
        assert result.meal_type == "snack"

    def test_brunch_maps_to_lunch(self) -> None:
        """'브런치'는 MealType에 없으므로 점심으로 매핑."""
        result = MealTextParser().parse("브런치: 샌드위치")
        assert result.meal_type == "lunch"

    def test_no_prefix_meal_type_none(self) -> None:
        result = MealTextParser().parse("김치찌개, 공기밥")
        assert result.meal_type is None

    def test_only_prefix_returns_no_items(self) -> None:
        """prefix만 있고 음식이 없는 경우."""
        result = MealTextParser().parse("점심:")
        assert result.meal_type == "lunch"
        assert result.items == []

    def test_fullwidth_colon_supported(self) -> None:
        """전각 콜론 (U+FF1A) 지원 — 한국어 IME 자동 입력 케이스."""
        fullwidth_colon = "："  # noqa: RUF001 — 의도적으로 U+FF1A 사용
        result = MealTextParser().parse(f"점심{fullwidth_colon} 김치찌개")
        assert result.meal_type == "lunch"
        assert len(result.items) == 1


class TestItemSeparators:
    """음식 분리자."""

    def test_comma_separator(self) -> None:
        result = MealTextParser().parse("김치찌개, 공기밥, 계란말이")
        names = [item.name_ko for item in result.items]
        assert names == ["김치찌개", "공기밥", "계란말이"]

    def test_semicolon_separator(self) -> None:
        result = MealTextParser().parse("김치찌개; 공기밥")
        names = [item.name_ko for item in result.items]
        assert names == ["김치찌개", "공기밥"]

    def test_slash_separator(self) -> None:
        result = MealTextParser().parse("김치찌개 / 공기밥")
        names = [item.name_ko for item in result.items]
        assert names == ["김치찌개", "공기밥"]

    def test_korean_wa_separator(self) -> None:
        """'와' 분리자."""
        result = MealTextParser().parse("김치찌개 와 공기밥")
        names = [item.name_ko for item in result.items]
        assert names == ["김치찌개", "공기밥"]

    def test_korean_gwa_separator(self) -> None:
        """'과' 분리자."""
        result = MealTextParser().parse("김치찌개 과 공기밥")
        names = [item.name_ko for item in result.items]
        assert names == ["김치찌개", "공기밥"]

    def test_geurigo_separator(self) -> None:
        """'그리고' 분리자."""
        result = MealTextParser().parse("김치찌개 그리고 공기밥")
        names = [item.name_ko for item in result.items]
        assert names == ["김치찌개", "공기밥"]


class TestAmountExtraction:
    """양 표현 추출."""

    def test_trailing_gae(self) -> None:
        result = MealTextParser().parse("계란말이 1개")
        assert len(result.items) == 1
        assert result.items[0].name_ko == "계란말이"
        assert result.items[0].amount_text == "1개"

    def test_trailing_gonggi(self) -> None:
        result = MealTextParser().parse("공기밥 1공기")
        assert result.items[0].amount_text == "1공기"

    def test_trailing_inbun(self) -> None:
        result = MealTextParser().parse("김치찌개 1인분")
        assert result.items[0].amount_text == "1인분"

    def test_decimal_amount(self) -> None:
        result = MealTextParser().parse("김치찌개 1.5인분")
        assert result.items[0].amount_text == "1.5인분"

    def test_no_amount(self) -> None:
        result = MealTextParser().parse("김치찌개")
        assert result.items[0].amount_text == ""

    def test_amount_with_space_normalized(self) -> None:
        """'2 공기' → '2공기'."""
        result = MealTextParser().parse("공기밥 2 공기")
        assert result.items[0].amount_text == "2공기"

    def test_per_item_amount_in_multi(self) -> None:
        """여러 항목에서 양 표현이 각 항목에만 붙는다."""
        result = MealTextParser().parse("공기밥 1공기, 계란말이 2개")
        assert result.items[0].amount_text == "1공기"
        assert result.items[1].amount_text == "2개"


class TestFullSentence:
    """전체 문장 처리 (dev-guide 16 §B 예시)."""

    def test_classic_lunch_example(self) -> None:
        """'점심: 김치찌개, 공기밥, 계란말이 1개'."""
        result = MealTextParser().parse("점심: 김치찌개, 공기밥, 계란말이 1개")
        assert result.meal_type == "lunch"
        assert len(result.items) == EXPECTED_THREE_ITEMS
        names = [item.name_ko for item in result.items]
        assert names == ["김치찌개", "공기밥", "계란말이"]
        assert result.items[0].amount_text == ""
        assert result.items[1].amount_text == ""
        assert result.items[2].amount_text == "1개"

    def test_raw_text_preserved(self) -> None:
        """ParsedMealItem.raw_text는 분리 후 trim된 세그먼트 원문."""
        result = MealTextParser().parse("김치찌개, 공기밥")
        for item in result.items:
            assert item.raw_text  # non-empty


class TestNoCanonicalization:
    """alias 매칭/canonical name 변환은 본 parser 책임이 아님."""

    def test_alias_name_not_converted(self) -> None:
        """'쌀밥'은 '공기밥'으로 변환되지 않는다 (RdaMatcher 책임)."""
        result = MealTextParser().parse("쌀밥")
        assert result.items[0].name_ko == "쌀밥"

    def test_english_name_preserved(self) -> None:
        """영문 음식명도 그대로 보존."""
        result = MealTextParser().parse("bibimbap")
        assert result.items[0].name_ko == "bibimbap"


class TestDTOValidation:
    """DTO 제약."""

    def test_parsed_item_empty_name_raises(self) -> None:
        with pytest.raises(ValidationError):
            ParsedMealItem(name_ko="")

    def test_parsed_item_frozen(self) -> None:
        item = ParsedMealItem(name_ko="공기밥")
        with pytest.raises(ValidationError):
            item.name_ko = "비빔밥"  # type: ignore[misc]

    def test_parsed_meal_text_defaults(self) -> None:
        text = ParsedMealText()
        assert text.meal_type is None
        assert text.items == []

    def test_invalid_meal_type_raises(self) -> None:
        """meal_type은 Literal 제약."""
        with pytest.raises(ValidationError):
            ParsedMealText(meal_type="invalid")  # type: ignore[arg-type]
