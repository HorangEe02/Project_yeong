"""식단 텍스트 입력 정규화 parser.

dev-guide 16 §"입력 방식 / 방식 B: 텍스트 입력" 명세를 따른다.
사용자가 입력한 자연어 식단 텍스트(예: "점심: 김치찌개, 공기밥, 계란말이
1개")를 meal_type, 음식명, 양 표현으로 분해한다.

A3.2 정책:
    - LLM 호출 없음 — 규칙 기반 파싱만.
    - meal_type prefix 인식 (아침/점심/저녁/간식/브런치).
    - 분리자(쉼표, 세미콜론, 슬래시, 와/과/그리고) 기준 음식 분리.
    - 양 표현(개/공기/인분/그릇/컵/잔/장/조각/쪽/봉지/병/캔) 추출 — 정량 환산은
      `RdaMatcher.estimate_for_amount` (A3.3) 책임.
    - 음식명을 다른 canonical name으로 변환하지 않는다 (alias 매칭은 RdaMatcher
      책임).
    - 의료/영양 단정 표현은 생성하지 않는다.

Reference:
    docs/dev-guides/16-meal-recognition.md §"입력 방식 / 방식 B"
"""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field

from src.meal.base import MealType

_FULLWIDTH_COLON = "："  # noqa: RUF001 — U+FF1A, 한국어 IME 자동 변환 지원
_FULLWIDTH_COMMA = "，"  # noqa: RUF001 — U+FF0C
_IDEOGRAPHIC_COMMA = "、"  # U+3001 (일본식 열거 쉼표)

_MEAL_TYPE_PREFIX_PATTERN = re.compile(
    rf"^\s*(?P<meal>아침|점심|저녁|간식|브런치)\s*[:{_FULLWIDTH_COLON}]\s*"
)
"""식사 시간대 prefix.

ASCII 콜론과 전각 콜론(U+FF1A)을 모두 허용한다. 한국어 모바일 IME에서는
전각 콜론이 자동 입력되는 경우가 흔하므로 양쪽을 지원한다.
"""

_AMOUNT_PATTERN = re.compile(
    r"\s*(?P<amount>\d+(?:\.\d+)?\s*(?:개|공기|인분|그릇|컵|잔|장|조각|쪽|봉지|병|캔))$"
)
"""문자열 끝에 붙은 양 표현. 정량 환산 없이 원문 그대로 캡처."""

_SEPARATOR_PATTERN = re.compile(
    rf"\s*[,;{_IDEOGRAPHIC_COMMA}{_FULLWIDTH_COMMA}/]\s*" r"|\s+와\s+|\s+과\s+|\s+그리고\s+"
)
"""음식 항목 분리자.

ASCII 쉼표/세미콜론/슬래시, 일본식 열거 쉼표(U+3001), 전각 쉼표(U+FF0C),
한국어 연결어(와/과/그리고)를 모두 허용한다.
"""

_MEAL_TYPE_MAP: dict[str, MealType] = {
    "아침": "breakfast",
    "점심": "lunch",
    "저녁": "dinner",
    "간식": "snack",
    "브런치": "lunch",
}
"""한국어 prefix → MealType 매핑. '브런치'는 점심 카테고리로 묶는다."""


class ParsedMealItem(BaseModel):
    """텍스트에서 추출된 단일 음식 항목.

    Attributes:
        name_ko: 추출된 음식명 (정규화·alias 매칭 X).
        raw_text: 분리·정규화 전 원문 세그먼트.
        amount_text: 양 표현 원문 (예: "1개", "2공기"). 정량 환산은 본 parser
            범위 외 — `RdaMatcher.estimate_for_amount`가 처리.
    """

    model_config = ConfigDict(frozen=True)

    name_ko: str = Field(..., min_length=1)
    raw_text: str = Field(default="")
    amount_text: str = Field(default="")


class ParsedMealText(BaseModel):
    """parse() 결과 wrapper.

    Attributes:
        meal_type: prefix("점심:" 등)에서 추론한 식사 종류. 없으면 None.
        items: 추출된 ParsedMealItem 리스트.
    """

    model_config = ConfigDict(frozen=True)

    meal_type: MealType | None = None
    items: list[ParsedMealItem] = Field(default_factory=list)


class MealTextParser:
    """식단 텍스트 → ParsedMealText 변환기.

    상태 없음 — 생성자는 인자를 받지 않는다. 파일 I/O 없음.

    Examples:
        >>> parser = MealTextParser()
        >>> result = parser.parse("점심: 김치찌개, 공기밥, 계란말이 1개")
        >>> result.meal_type
        'lunch'
        >>> [item.name_ko for item in result.items]
        ['김치찌개', '공기밥', '계란말이']
        >>> result.items[2].amount_text
        '1개'
    """

    def parse(self, text: str) -> ParsedMealText:
        """텍스트에서 meal_type과 음식 항목 리스트를 추출한다.

        Args:
            text: 사용자 입력 식단 자연어 텍스트.

        Returns:
            `ParsedMealText`. 빈 입력이면 `meal_type=None`, `items=[]`.
        """
        stripped = text.strip()
        if not stripped:
            return ParsedMealText(items=[])

        meal_type: MealType | None = None
        prefix_match = _MEAL_TYPE_PREFIX_PATTERN.match(stripped)
        if prefix_match:
            meal_type = _MEAL_TYPE_MAP.get(prefix_match.group("meal"))
            stripped = stripped[prefix_match.end() :]

        if not stripped.strip():
            return ParsedMealText(meal_type=meal_type, items=[])

        segments = _SEPARATOR_PATTERN.split(stripped)
        items: list[ParsedMealItem] = []
        for raw_seg in segments:
            seg = raw_seg.strip()
            if not seg:
                continue
            name, amount = _split_name_and_amount(seg)
            if not name:
                continue
            items.append(ParsedMealItem(name_ko=name, raw_text=seg, amount_text=amount))
        return ParsedMealText(meal_type=meal_type, items=items)


def _split_name_and_amount(text: str) -> tuple[str, str]:
    """문자열 끝의 양 표현을 분리한다.

    Args:
        text: 단일 음식 세그먼트.

    Returns:
        (name, amount_text) 쌍. 양 표현이 없으면 ("text", "").
    """
    match = _AMOUNT_PATTERN.search(text)
    if match:
        name = text[: match.start()].strip()
        amount = match.group("amount").strip()
        # 공백 제거 — "1 개" → "1개"
        amount = re.sub(r"\s+", "", amount)
        return name, amount
    return text.strip(), ""
