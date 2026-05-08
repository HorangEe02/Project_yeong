# dev-guides/08 — LLM 영양제 파싱 (Claude + GPT 백업)

> **Phase**: 2 | **선행 작업**: [`07-ocr-pipeline.md`](./07-ocr-pipeline.md) | **예상 소요**: 4~5시간

---

## 🎯 작업 목표

OCR로 추출된 영양제 라벨 텍스트를 **Claude API의 Tool Use** 로 구조화된 영양소 정보(JSON)로 변환한다. 식약처 건기식 DB와 매칭하여 표준 영양소 코드로 정규화. OpenAI GPT를 백업으로 동일 인터페이스 제공.

---

## 📋 산출물

```
backend/
├── src/
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── base.py                # LLMAdapter ABC + DTO
│   │   ├── claude.py              # Claude (Tool Use, 주력)
│   │   ├── openai.py              # GPT (백업)
│   │   ├── prompts.py             # 시스템 프롬프트 (의료법 가이드 포함)
│   │   ├── schemas.py             # Tool Use 입력 스키마
│   │   └── exceptions.py          # LLMError 등
│   └── nutrition/
│       └── mfds_matcher.py        # 식약처 DB 매칭
└── tests/
    ├── unit/llm/
    │   ├── test_claude.py         # 모킹
    │   ├── test_openai.py         # 모킹
    │   └── test_mfds_matcher.py
    ├── integration/llm/
    │   └── test_real_claude.py    # 실제 API (skip if no key)
    └── e2e/
        └── test_supplement_parse_e2e.py
```

---

## 📐 설계 명세

### 파싱 파이프라인

```
OCR 텍스트 → LLMAdapter.parse_supplement(text) → ParsedSupplement
                                                        │
                                                        ▼
                                          MfdsMatcher.match() → NutrientIntake[]
```

### Tool Use 스키마

```json
{
  "name": "extract_supplement_facts",
  "description": "영양제 라벨에서 성분 정보를 구조화하여 추출",
  "input_schema": {
    "type": "object",
    "properties": {
      "product_name": { "type": "string" },
      "manufacturer": { "type": "string" },
      "serving_size": {
        "type": "object",
        "properties": {
          "amount": { "type": "number" },
          "unit": { "type": "string", "enum": ["tablet", "capsule", "ml", "g"] }
        }
      },
      "ingredients": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "name_ko": { "type": "string" },
            "name_en": { "type": "string" },
            "amount": { "type": "number" },
            "unit": { "type": "string" }
          },
          "required": ["name_ko", "amount", "unit"]
        }
      }
    },
    "required": ["ingredients"]
  }
}
```

---

## 🔧 구현 명세

### 1. `src/llm/exceptions.py`

```python
"""LLM 관련 예외."""

from __future__ import annotations


class LLMError(Exception):
    """LLM 처리 실패 기본 예외."""


class LLMApiError(LLMError):
    """외부 API 호출 실패."""

    def __init__(self, engine: str, message: str) -> None:
        super().__init__(f"{engine}: {message}")
        self.engine = engine


class LLMParseError(LLMError):
    """LLM 응답 파싱 실패 (Tool Use 누락 등)."""


class LLMRefusalError(LLMError):
    """LLM이 안전상 응답을 거부한 경우."""
```

### 2. `src/llm/schemas.py`

```python
"""LLM Tool Use 입출력 스키마."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ParsedIngredient(BaseModel):
    """LLM이 파싱한 단일 성분.

    Attributes:
        name_ko: 한국어 성분명 (라벨 그대로).
        name_en: 영어 성분명 (있으면).
        amount: 양 (라벨에 표시된 수치).
        unit: 단위 (mg, μg, IU, g 등 라벨 그대로).
    """

    model_config = ConfigDict(frozen=True)

    name_ko: str = Field(..., min_length=1)
    name_en: str | None = None
    amount: float = Field(..., ge=0)
    unit: str = Field(..., min_length=1)


class ParsedServingSize(BaseModel):
    """1회 제공량."""

    model_config = ConfigDict(frozen=True)

    amount: float = Field(..., ge=0)
    unit: str = Field(..., pattern=r"^(tablet|capsule|ml|g)$")


class ParsedSupplement(BaseModel):
    """LLM이 라벨에서 추출한 전체 영양제 정보.

    Attributes:
        product_name: 제품명.
        manufacturer: 제조사 (있으면).
        serving_size: 1회 제공량.
        ingredients: 성분 리스트.
        raw_text: 원본 OCR 텍스트.
        engine: 사용된 LLM 엔진.
    """

    model_config = ConfigDict(frozen=True)

    product_name: str | None = None
    manufacturer: str | None = None
    serving_size: ParsedServingSize | None = None
    ingredients: list[ParsedIngredient]
    raw_text: str = ""
    engine: str
```

### 3. `src/llm/prompts.py`

```python
"""LLM 시스템 프롬프트.

⚠️ 의료법·약사법·건기식법 표현 가이드를 시스템 프롬프트에 강제 포함.

Reference:
    docs/10-compliance-checklist.md §10
"""

from __future__ import annotations

from typing import Final


SUPPLEMENT_PARSING_SYSTEM: Final[str] = """\
당신은 한국 영양제 라벨에서 성분 정보를 정확히 추출하는 어시스턴트입니다.

## 작업
주어진 OCR 텍스트(한국어 + 영어 혼용)에서 영양제의 성분, 양, 단위를 추출하여
구조화된 JSON으로 반환하세요.

## 추출 규칙
1. 라벨에 있는 성분만 추출 (추측 금지)
2. 양과 단위는 라벨에 표시된 그대로 (mg, μg, IU, g 등)
3. 1회 제공량 (예: "1정", "2캡슐") 별도 추출
4. 한국어명을 우선 추출, 영문명도 있으면 함께
5. 영양제와 관련 없는 텍스트(브랜드 슬로건 등)는 무시
6. OCR 노이즈로 추정되는 텍스트는 제외 (확신이 없으면 누락)

## 절대 금지
- 의료적 진단·처방 표현 사용 ("진단", "처방", "치료" 등)
- 효능에 대한 단정적 표현 ("확실히", "보장합니다" 등)
- 라벨에 없는 정보를 추측·생성
- 의약품으로 표현 (영양제는 식품)

## 응답 형식
반드시 `extract_supplement_facts` 도구를 호출하세요.
도구 호출 외의 텍스트는 포함하지 마세요.
"""


SUPPLEMENT_TOOL_SCHEMA: Final[dict] = {
    "name": "extract_supplement_facts",
    "description": "영양제 라벨에서 성분 정보를 구조화하여 추출",
    "input_schema": {
        "type": "object",
        "properties": {
            "product_name": {
                "type": "string",
                "description": "제품명 (라벨에 표시된 그대로)",
            },
            "manufacturer": {
                "type": "string",
                "description": "제조사 (있으면)",
            },
            "serving_size": {
                "type": "object",
                "properties": {
                    "amount": {"type": "number"},
                    "unit": {
                        "type": "string",
                        "enum": ["tablet", "capsule", "ml", "g"],
                    },
                },
                "required": ["amount", "unit"],
            },
            "ingredients": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name_ko": {"type": "string"},
                        "name_en": {"type": "string"},
                        "amount": {"type": "number"},
                        "unit": {"type": "string"},
                    },
                    "required": ["name_ko", "amount", "unit"],
                },
            },
        },
        "required": ["ingredients"],
    },
}
```

### 4. `src/llm/base.py`

```python
"""LLM Adapter 추상 인터페이스."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.llm.schemas import ParsedSupplement


class LLMAdapter(ABC):
    """LLM 엔진의 추상 인터페이스.

    Examples:
        >>> llm: LLMAdapter = ClaudeAdapter(api_key="...")
        >>> parsed = await llm.parse_supplement("OCR 텍스트")
    """

    @abstractmethod
    async def parse_supplement(self, ocr_text: str) -> ParsedSupplement:
        """OCR 텍스트를 구조화된 영양제 정보로 파싱.

        Args:
            ocr_text: OCR로 추출된 텍스트.

        Returns:
            ParsedSupplement.

        Raises:
            LLMApiError: API 호출 실패.
            LLMParseError: 응답 파싱 실패.
            LLMRefusalError: LLM이 응답 거부.
        """
        ...

    @property
    @abstractmethod
    def engine_name(self) -> str:
        """엔진 식별자."""
        ...
```

### 5. `src/llm/claude.py`

```python
"""Anthropic Claude API 기반 LLM Adapter (주력)."""

from __future__ import annotations

import logging
from typing import Any, Final

from anthropic import AsyncAnthropic
from anthropic.types import Message
from pydantic import ValidationError

from src.llm.base import LLMAdapter
from src.llm.exceptions import LLMApiError, LLMParseError, LLMRefusalError
from src.llm.prompts import SUPPLEMENT_PARSING_SYSTEM, SUPPLEMENT_TOOL_SCHEMA
from src.llm.schemas import ParsedSupplement


logger = logging.getLogger(__name__)


DEFAULT_MODEL: Final[str] = "claude-sonnet-4-6"
MAX_TOKENS: Final[int] = 2048
TIMEOUT_SEC: Final[float] = 30.0


class ClaudeAdapter(LLMAdapter):
    """Claude API 기반 LLM Adapter.

    Tool Use 모드를 사용하여 구조화된 출력을 강제한다.

    Reference:
        docs/09-data-catalog.md §5.3
    """

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        client: AsyncAnthropic | None = None,
    ) -> None:
        """Adapter 초기화.

        Args:
            api_key: Anthropic API 키.
            model: 사용할 모델 (기본: claude-sonnet-4-6).
            client: 의존성 주입용 (테스트 모킹).
        """
        self._client = client or AsyncAnthropic(api_key=api_key)
        self._model = model

    @property
    def engine_name(self) -> str:
        return f"claude:{self._model}"

    async def parse_supplement(self, ocr_text: str) -> ParsedSupplement:
        """Tool Use로 구조화된 영양제 정보 추출."""
        try:
            response: Message = await self._client.messages.create(
                model=self._model,
                max_tokens=MAX_TOKENS,
                system=SUPPLEMENT_PARSING_SYSTEM,
                tools=[SUPPLEMENT_TOOL_SCHEMA],
                tool_choice={"type": "tool", "name": "extract_supplement_facts"},
                messages=[{"role": "user", "content": f"OCR 텍스트:\n\n{ocr_text}"}],
                timeout=TIMEOUT_SEC,
            )
        except Exception as e:
            raise LLMApiError(self.engine_name, str(e)) from e

        if response.stop_reason == "refusal":
            raise LLMRefusalError(f"Claude refused: {response.content}")

        # Tool Use 블록 추출
        tool_use_block = next(
            (b for b in response.content if b.type == "tool_use"),
            None,
        )
        if tool_use_block is None:
            raise LLMParseError(
                f"No tool_use in response. Stop reason: {response.stop_reason}"
            )

        tool_input: dict[str, Any] = tool_use_block.input  # type: ignore[assignment]
        try:
            parsed = ParsedSupplement(
                product_name=tool_input.get("product_name"),
                manufacturer=tool_input.get("manufacturer"),
                serving_size=tool_input.get("serving_size"),  # type: ignore[arg-type]
                ingredients=tool_input.get("ingredients", []),  # type: ignore[arg-type]
                raw_text=ocr_text,
                engine=self.engine_name,
            )
        except ValidationError as e:
            raise LLMParseError(f"Schema validation failed: {e}") from e

        logger.info(
            "Claude parsed supplement: %d ingredients",
            len(parsed.ingredients),
        )
        return parsed
```

### 6. `src/llm/openai.py` (백업)

```python
"""OpenAI GPT 기반 LLM Adapter (백업)."""

from __future__ import annotations

import json
import logging
from typing import Final

import httpx
from openai import AsyncOpenAI
from pydantic import ValidationError

from src.llm.base import LLMAdapter
from src.llm.exceptions import LLMApiError, LLMParseError
from src.llm.prompts import SUPPLEMENT_PARSING_SYSTEM, SUPPLEMENT_TOOL_SCHEMA
from src.llm.schemas import ParsedSupplement


logger = logging.getLogger(__name__)


DEFAULT_MODEL: Final[str] = "gpt-4o-mini"
TIMEOUT_SEC: Final[float] = 30.0


class OpenAIAdapter(LLMAdapter):
    """OpenAI GPT 기반 LLM Adapter (백업).

    Function Calling 모드 사용. Claude의 Tool Use와 호환되도록
    동일 스키마를 변환하여 사용.

    Reference:
        docs/09-data-catalog.md §5.4
    """

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        client: AsyncOpenAI | None = None,
    ) -> None:
        self._client = client or AsyncOpenAI(api_key=api_key)
        self._model = model

    @property
    def engine_name(self) -> str:
        return f"openai:{self._model}"

    async def parse_supplement(self, ocr_text: str) -> ParsedSupplement:
        """OpenAI Function Calling으로 추출."""
        # Anthropic Tool Use → OpenAI Function 형식 변환
        function_def = {
            "type": "function",
            "function": {
                "name": SUPPLEMENT_TOOL_SCHEMA["name"],
                "description": SUPPLEMENT_TOOL_SCHEMA["description"],
                "parameters": SUPPLEMENT_TOOL_SCHEMA["input_schema"],
            },
        }

        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": SUPPLEMENT_PARSING_SYSTEM},
                    {"role": "user", "content": f"OCR 텍스트:\n\n{ocr_text}"},
                ],
                tools=[function_def],
                tool_choice={
                    "type": "function",
                    "function": {"name": SUPPLEMENT_TOOL_SCHEMA["name"]},
                },
                timeout=TIMEOUT_SEC,
            )
        except Exception as e:
            raise LLMApiError(self.engine_name, str(e)) from e

        message = response.choices[0].message
        if not message.tool_calls:
            raise LLMParseError("No tool_calls in OpenAI response")

        tool_call = message.tool_calls[0]
        try:
            tool_input = json.loads(tool_call.function.arguments)
        except json.JSONDecodeError as e:
            raise LLMParseError(f"Invalid JSON in arguments: {e}") from e

        try:
            parsed = ParsedSupplement(
                product_name=tool_input.get("product_name"),
                manufacturer=tool_input.get("manufacturer"),
                serving_size=tool_input.get("serving_size"),
                ingredients=tool_input.get("ingredients", []),
                raw_text=ocr_text,
                engine=self.engine_name,
            )
        except ValidationError as e:
            raise LLMParseError(f"Schema validation failed: {e}") from e

        return parsed
```

### 7. `src/nutrition/mfds_matcher.py`

```python
"""LLM 파싱 결과를 식약처 표준 영양소 코드로 매칭."""

from __future__ import annotations

import csv
import logging
from functools import lru_cache
from pathlib import Path
from typing import Final

from src.llm.schemas import ParsedIngredient
from src.models.schemas.nutrition import NutrientIntake


logger = logging.getLogger(__name__)


MFDS_INGREDIENTS_PATH: Final[Path] = Path("data/mfds/functional_ingredients.csv")
"""식약처 건강기능식품 인정 원료 CSV."""


@lru_cache(maxsize=1)
def _load_mfds_ingredients() -> dict[str, str]:
    """식약처 원료 → 표준 영양소 코드 매핑.

    CSV 형식:
        ingredient_name_ko,ingredient_name_en,nutrient_code
        비타민 C,Vitamin C,vitamin_c_mg
        비타민 D,Vitamin D,vitamin_d_ug
        ...

    Returns:
        {정규화된 한국어/영어명 → nutrient_code}.
    """
    if not MFDS_INGREDIENTS_PATH.exists():
        logger.warning("MFDS ingredients CSV not found: %s", MFDS_INGREDIENTS_PATH)
        return {}

    mapping: dict[str, str] = {}
    with MFDS_INGREDIENTS_PATH.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ko = _normalize_name(row["ingredient_name_ko"])
            en = _normalize_name(row.get("ingredient_name_en", ""))
            code = row["nutrient_code"]
            if ko:
                mapping[ko] = code
            if en:
                mapping[en] = code
    return mapping


def _normalize_name(name: str) -> str:
    """성분명 정규화 (공백·특수문자 제거, 소문자)."""
    return "".join(c for c in name.lower() if c.isalnum())


def match_to_nutrient_code(ingredient: ParsedIngredient) -> str | None:
    """파싱된 성분을 표준 영양소 코드로 매칭.

    Args:
        ingredient: LLM이 파싱한 단일 성분.

    Returns:
        매칭된 영양소 코드 (e.g., "vitamin_c_mg"), 또는 None.

    Examples:
        >>> ing = ParsedIngredient(name_ko="비타민 C", amount=100, unit="mg")
        >>> match_to_nutrient_code(ing)
        'vitamin_c_mg'
    """
    mapping = _load_mfds_ingredients()

    # 한국어 우선
    ko_normalized = _normalize_name(ingredient.name_ko)
    if ko_normalized in mapping:
        return mapping[ko_normalized]

    # 영어 폴백
    if ingredient.name_en:
        en_normalized = _normalize_name(ingredient.name_en)
        if en_normalized in mapping:
            return mapping[en_normalized]

    logger.warning(
        "No nutrient code match for: ko='%s', en='%s'",
        ingredient.name_ko, ingredient.name_en,
    )
    return None


def to_nutrient_intakes(
    ingredients: list[ParsedIngredient],
) -> list[NutrientIntake]:
    """파싱된 성분 리스트를 NutrientIntake 리스트로 변환.

    매칭 실패 항목은 결과에서 제외 (warning 로그).

    Args:
        ingredients: LLM 파싱 결과.

    Returns:
        NutrientIntake 리스트 (매칭된 항목만).
    """
    intakes: list[NutrientIntake] = []
    for ing in ingredients:
        code = match_to_nutrient_code(ing)
        if code is None:
            continue
        intakes.append(NutrientIntake(
            code=code,
            amount=ing.amount,
            unit=ing.unit.lower().replace("μ", "u"),
            source="supplement",
        ))
    return intakes
```

---

## 🧪 테스트 (4-Tier)

### Tier 1: 단위 테스트

#### `test_claude.py`

```python
"""ClaudeAdapter 단위 테스트 (실제 API X)."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.llm.claude import ClaudeAdapter
from src.llm.exceptions import LLMApiError, LLMParseError, LLMRefusalError


def make_mock_tool_use_response(ingredients: list[dict]):
    """Tool Use 응답 모킹."""
    response = MagicMock()
    response.stop_reason = "tool_use"
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.input = {"ingredients": ingredients}
    response.content = [tool_block]
    return response


class TestClaudeAdapter:
    @pytest.mark.asyncio
    async def test_parse_supplement_success(self) -> None:
        client = AsyncMock()
        client.messages.create.return_value = make_mock_tool_use_response([
            {"name_ko": "비타민 C", "amount": 1000, "unit": "mg"},
            {"name_ko": "비타민 D", "amount": 25, "unit": "ug"},
        ])

        adapter = ClaudeAdapter(api_key="test", client=client)
        result = await adapter.parse_supplement("OCR 텍스트")

        assert len(result.ingredients) == 2
        assert result.ingredients[0].name_ko == "비타민 C"
        assert result.engine.startswith("claude:")

    @pytest.mark.asyncio
    async def test_no_tool_use_raises(self) -> None:
        client = AsyncMock()
        response = MagicMock()
        response.stop_reason = "end_turn"
        response.content = []  # tool_use 블록 없음
        client.messages.create.return_value = response

        adapter = ClaudeAdapter(api_key="test", client=client)
        with pytest.raises(LLMParseError):
            await adapter.parse_supplement("text")

    @pytest.mark.asyncio
    async def test_api_error_raises(self) -> None:
        client = AsyncMock()
        client.messages.create.side_effect = Exception("Quota exceeded")

        adapter = ClaudeAdapter(api_key="test", client=client)
        with pytest.raises(LLMApiError):
            await adapter.parse_supplement("text")

    @pytest.mark.asyncio
    async def test_refusal_raises(self) -> None:
        client = AsyncMock()
        response = MagicMock()
        response.stop_reason = "refusal"
        response.content = []
        client.messages.create.return_value = response

        adapter = ClaudeAdapter(api_key="test", client=client)
        with pytest.raises(LLMRefusalError):
            await adapter.parse_supplement("text")

    @pytest.mark.asyncio
    async def test_invalid_schema_raises(self) -> None:
        client = AsyncMock()
        # amount가 음수 → ValidationError
        client.messages.create.return_value = make_mock_tool_use_response([
            {"name_ko": "비타민 C", "amount": -100, "unit": "mg"},
        ])

        adapter = ClaudeAdapter(api_key="test", client=client)
        with pytest.raises(LLMParseError):
            await adapter.parse_supplement("text")
```

#### `test_mfds_matcher.py`

| 테스트 | 검증 |
|-------|------|
| `test_match_korean_name` | "비타민 C" → "vitamin_c_mg" |
| `test_match_english_fallback` | name_ko 매칭 실패 → en 폴백 |
| `test_match_with_whitespace` | "비타민  C" → 정상 매칭 |
| `test_no_match_returns_none` | "Unobtainium" → None |
| `test_to_nutrient_intakes_skips_unmatched` | 매칭 실패는 결과에서 제외 |
| `test_unit_normalized_to_lowercase` | "MG" → "mg" |
| `test_micro_symbol_normalized` | "μg" → "ug" |

### Tier 2: 통합 테스트

#### `test_real_claude.py`

```python
"""실제 Claude API 호출 테스트.

조건: ANTHROPIC_API_KEY 환경변수 필요.
"""

import os

import pytest


@pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"),
    reason="No Anthropic API key"
)
@pytest.mark.integration
class TestClaudeReal:
    @pytest.mark.asyncio
    async def test_parse_typical_label(self):
        adapter = ClaudeAdapter(
            api_key=os.environ["ANTHROPIC_API_KEY"]
        )
        ocr_text = """\
        종합비타민
        1정 중
        비타민 C 1000mg
        비타민 D3 25μg (1000 IU)
        칼슘 600mg
        제조: ABC제약
        """
        result = await adapter.parse_supplement(ocr_text)

        assert len(result.ingredients) >= 3
        # 비타민 C가 포함되어야 함
        assert any("비타민 C" in i.name_ko for i in result.ingredients)

    @pytest.mark.asyncio
    async def test_no_medical_terms_in_response(self):
        """Claude가 의료법 가이드를 준수하는지."""
        adapter = ClaudeAdapter(api_key=os.environ["ANTHROPIC_API_KEY"])
        result = await adapter.parse_supplement("비타민 C 100mg")

        # Tool Use 응답이라 의료 표현이 들어갈 가능성은 낮지만 검증
        for ing in result.ingredients:
            assert "진단" not in ing.name_ko
            assert "처방" not in ing.name_ko
```

### Tier 3: E2E 테스트 (OCR + LLM 통합)

```python
"""OCR → LLM → 매칭 E2E."""

@pytest.mark.e2e
class TestSupplementParseE2E:
    @pytest.mark.asyncio
    async def test_full_pipeline(self):
        """실제 영양제 사진 → ingredients 추출 → NutrientIntake."""
        # 1. OCR
        with open("tests/fixtures/sample_supplement.jpg", "rb") as f:
            image = f.read()
        ocr_pipeline = OCRPipeline(
            primary=GoogleVisionOCR(),
            fallback=None,
        )
        ocr_result = await ocr_pipeline.extract(image)
        assert ocr_result.text  # 텍스트가 추출됨

        # 2. LLM 파싱
        llm = ClaudeAdapter(api_key=os.environ["ANTHROPIC_API_KEY"])
        parsed = await llm.parse_supplement(ocr_result.text)
        assert len(parsed.ingredients) > 0

        # 3. NutrientIntake 변환
        intakes = to_nutrient_intakes(parsed.ingredients)
        # 최소 1개 이상은 매칭되어야 함
        assert len(intakes) > 0
```

### Tier 4: 성능 테스트

```python
"""LLM 응답 시간 검증."""

@pytest.mark.performance
class TestLLMPerformance:
    @pytest.mark.asyncio
    async def test_typical_label_under_3s(self):
        """일반 영양제 라벨 파싱 < 3초."""
        adapter = ClaudeAdapter(api_key=os.environ["ANTHROPIC_API_KEY"])

        start = time.perf_counter()
        await adapter.parse_supplement(SAMPLE_LABEL_TEXT)
        elapsed = time.perf_counter() - start

        assert elapsed < 3.0
```

---

## ✅ Definition of Done

- [ ] `src/llm/exceptions.py` — LLMError 계층
- [ ] `src/llm/schemas.py` — ParsedSupplement 등 Pydantic 모델
- [ ] `src/llm/prompts.py` — 시스템 프롬프트 + Tool Use 스키마
- [ ] `src/llm/base.py` — LLMAdapter ABC
- [ ] `src/llm/claude.py` — Claude (Tool Use) 구현
- [ ] `src/llm/openai.py` — GPT (Function Calling) 백업
- [ ] `src/nutrition/mfds_matcher.py` — 식약처 매칭
- [ ] `data/mfds/functional_ingredients.csv` — 매핑 시드 (최소 30종)
- [ ] 모든 함수 Google-style docstring
- [ ] 모든 함수 타입 힌트
- [ ] 단위 테스트 (Claude/OpenAI/Matcher 각 10+)
- [ ] (선택) 실 API 통합 테스트
- [ ] E2E 테스트 (OCR + LLM + 매칭)
- [ ] 성능 테스트 (< 3초)
- [ ] **시스템 프롬프트에 의료법 가이드 포함 검증**
- [ ] `mypy src/llm src/nutrition --strict` 통과

---

## 💡 구현 팁

### Tool Use vs JSON Mode 차이

| 방식 | 장점 | 단점 |
|------|------|------|
| **Tool Use (권장)** | 스키마 강제, 응답 신뢰도 ↑ | 약간 느림 |
| JSON Mode | 빠름 | 스키마 검증 약함, 추가 텍스트 섞일 수 있음 |

### 모델 선택

- **claude-sonnet-4-6** (기본) — 균형, 대부분 충분
- **claude-haiku-4-5** — 단순 라벨, 비용 절감
- **claude-opus-4-7** — 복잡한 한국어 라벨, 최고 정확도

### 시스템 프롬프트 안정성

CLAUDE.md 처럼 시스템 프롬프트는 **자주 변경하지 마세요**. 캐싱 효과로 비용·속도 모두 이득.

```python
# Claude API의 Prompt Caching 활용
response = await client.messages.create(
    system=[
        {
            "type": "text",
            "text": SUPPLEMENT_PARSING_SYSTEM,
            "cache_control": {"type": "ephemeral"},  # ← 캐싱
        }
    ],
    ...
)
```

### 식약처 매핑 데이터 시드

`data/mfds/functional_ingredients.csv` 초기 시드 (최소):

```csv
ingredient_name_ko,ingredient_name_en,nutrient_code
비타민 A,Vitamin A,vitamin_a_ug_rae
비타민 C,Vitamin C,vitamin_c_mg
비타민 D,Vitamin D,vitamin_d_ug
비타민 D3,Vitamin D3,vitamin_d_ug
비타민 E,Vitamin E,vitamin_e_mg_ate
비타민 B1,Thiamine,vitamin_b1_mg
비타민 B2,Riboflavin,vitamin_b2_mg
...
```

---

## 🚫 이 작업에서 하지 말 것

- ❌ Claude/OpenAI SDK 직접 호출 (Adapter 우회)
- ❌ FastAPI 라우터 통합 (다음 가이드 09)
- ❌ DB 저장 (다음 가이드 09)
- ❌ 시스템 프롬프트에 사용자 데이터 직접 삽입 (Prompt Injection 위험)

---

## 🔗 관련 문서

- [`/CLAUDE.md`](../../CLAUDE.md)
- [`/backend/CLAUDE.md`](../../backend/CLAUDE.md)
- [`/data/CLAUDE.md`](../../data/CLAUDE.md)
- [`/docs/09-data-catalog.md §5.3, §5.4`](../09-data-catalog.md)
- [`/docs/10-compliance-checklist.md §10`](../10-compliance-checklist.md)
- 이전: [`07-ocr-pipeline.md`](./07-ocr-pipeline.md)
- 다음: [`09-supplement-registration-api.md`](./09-supplement-registration-api.md)
