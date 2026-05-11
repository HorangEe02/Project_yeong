# dev-guides/08 — LLM 영양제 파싱 (Ollama 로컬 LLM)

> **Phase**: 2 | **선행 작업**: [`07-ocr-pipeline.md`](./07-ocr-pipeline.md) | **예상 소요**: 4~5시간

---

## 🎯 작업 목표

OCR로 추출된 영양제 라벨 텍스트를 **Ollama 로컬 LLM의 Structured Outputs(JSON Schema)** 로 구조화된 영양소 정보(JSON)로 변환한다. 환자 개인정보와 민감 건강정보 보호를 위해 Claude/OpenAI 같은 외부 LLM은 기본 경로에서 제외하고, 비식별 테스트 또는 승인된 환경에서만 선택 Adapter로 둔다.

---

## 📋 산출물

```
backend/
├── src/
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── base.py                # LLMAdapter ABC + DTO
│   │   ├── ollama.py              # Ollama Local API (주력)
│   │   ├── external.py            # 선택: 비식별 테스트용 외부 LLM Adapter
│   │   ├── prompts.py             # 시스템 프롬프트 (의료법 가이드 포함)
│   │   ├── schemas.py             # Pydantic JSON Schema
│   │   └── exceptions.py          # LLMError 등
│   └── nutrition/
│       └── mfds_matcher.py        # 식약처 DB 매칭
└── tests/
    ├── unit/llm/
    │   ├── test_ollama.py         # 모킹
    │   ├── test_external_llm_disabled.py
    │   └── test_mfds_matcher.py
    ├── integration/llm/
    │   └── test_real_ollama.py    # 로컬 Ollama (skip if server unavailable)
    └── e2e/
        └── test_supplement_parse_e2e.py
```

---

## 📐 설계 명세

> 🔍 **출처**: [docs/13-algorithm-literature-evidence.md](../13-algorithm-literature-evidence.md), Ollama 공식 Structured Outputs / Chat API 문서.

### 근거 보강

| 항목 | 근거 수준 | 적용 방식 |
|------|----------|----------|
| Ollama Structured Outputs | A | Ollama 공식 문서의 `format` JSON Schema 방식을 사용하고 Pydantic으로 응답을 재검증한다. |
| 영양제 라벨 파싱 | C | OCR/LLM 결과는 추출 보조값이다. 식약처 DB 매칭과 사용자 확인 전에는 섭취량 확정값으로 쓰지 않는다. |
| 외부 LLM | 정책 제한 | 환자 개인정보와 민감 건강정보 보호를 위해 기본 경로에서는 비활성화한다. |

### 파싱 파이프라인

```
OCR 텍스트 → LLMAdapter.parse_supplement(text) → ParsedSupplement
                                                        │
                                                        ▼
                                          MfdsMatcher.match() → 사용자 확인 → NutrientIntake[]
```

### Structured Outputs JSON Schema

```json
{
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
    """LLM 응답 파싱 실패 (JSON 형식 오류, 스키마 불일치 등)."""


class LLMRefusalError(LLMError):
    """LLM이 안전상 응답을 거부한 경우."""
```

### 2. `src/llm/schemas.py`

```python
"""LLM 구조화 출력 입출력 스키마."""

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
    engine: str = ""
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
반드시 JSON Schema에 맞는 JSON만 반환하세요.
설명 문장, 마크다운 코드블록, 진단·처방 표현은 포함하지 마세요.
"""
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
        >>> llm: LLMAdapter = OllamaAdapter(model="qwen3.5:9b")
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

### 5. `src/llm/ollama.py`

```python
"""Ollama Local API 기반 LLM Adapter."""

from __future__ import annotations

import logging
from typing import Final

from ollama import AsyncClient, ResponseError
from pydantic import ValidationError

from src.llm.base import LLMAdapter
from src.llm.exceptions import LLMApiError, LLMParseError
from src.llm.prompts import SUPPLEMENT_PARSING_SYSTEM
from src.llm.schemas import ParsedSupplement


logger = logging.getLogger(__name__)


DEFAULT_HOST: Final[str] = "http://127.0.0.1:11434"
DEFAULT_MODEL: Final[str] = "qwen3.5:9b"
DEFAULT_TIMEOUT_SEC: Final[float] = 60.0


class OllamaAdapter(LLMAdapter):
    """Ollama 로컬 LLM Adapter.

    환자 개인정보와 민감 건강정보가 외부 LLM 서버로 전송되지 않도록
    FastAPI 백엔드에서 로컬 Ollama API만 호출한다.

    Reference:
        docs/12-local-llm-ollama-migration.md
    """

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        host: str = DEFAULT_HOST,
        timeout_sec: float = DEFAULT_TIMEOUT_SEC,
        client: AsyncClient | None = None,
    ) -> None:
        """Adapter 초기화.

        Args:
            model: 사용할 Ollama 모델 태그.
            host: Ollama API host. 기본값은 로컬 루프백 주소.
            timeout_sec: 요청 제한 시간.
            client: 의존성 주입용 클라이언트. 테스트에서 mock으로 대체한다.
        """
        self._model = model
        self._host = host
        self._timeout_sec = timeout_sec
        self._client = client or AsyncClient(host=host, timeout=timeout_sec)

    @property
    def engine_name(self) -> str:
        return f"ollama:{self._model}"

    async def parse_supplement(self, ocr_text: str) -> ParsedSupplement:
        """OCR 텍스트를 구조화된 영양제 정보로 파싱한다.

        Args:
            ocr_text: OCR로 추출된 영양제 라벨 텍스트.

        Returns:
            ParsedSupplement: Pydantic 검증을 통과한 파싱 결과.

        Raises:
            LLMApiError: Ollama 서버 연결 또는 모델 호출 실패.
            LLMParseError: JSON Schema 검증 실패.
        """
        try:
            response = await self._client.chat(
                model=self._model,
                messages=[
                    {"role": "system", "content": SUPPLEMENT_PARSING_SYSTEM},
                    {"role": "user", "content": f"OCR 텍스트:\n\n{ocr_text}"},
                ],
                format=ParsedSupplement.model_json_schema(),
                stream=False,
                options={"temperature": 0},
            )
        except ResponseError as e:
            raise LLMApiError(self.engine_name, e.error) from e
        except Exception as e:
            raise LLMApiError(self.engine_name, str(e)) from e

        try:
            parsed = ParsedSupplement.model_validate_json(
                response.message.content,
            )
            parsed = parsed.model_copy(
                update={"raw_text": ocr_text, "engine": self.engine_name},
            )
        except ValidationError as e:
            raise LLMParseError(f"Schema validation failed: {e}") from e
        except ValueError as e:
            raise LLMParseError(f"Invalid JSON response: {e}") from e

        logger.info(
            "Ollama parsed supplement with %d ingredients using %s",
            len(parsed.ingredients),
            self._model,
        )
        return parsed
```

### 6. `src/llm/external.py` (선택, 기본 비활성화)

```python
"""비식별 테스트 또는 승인 환경 전용 외부 LLM Adapter 진입점."""

from __future__ import annotations

from src.llm.exceptions import LLMApiError


class ExternalLLMDisabledError(LLMApiError):
    """외부 LLM 호출이 정책상 비활성화된 경우."""


def ensure_external_llm_allowed(allow_external_llm: bool) -> None:
    """외부 LLM 사용 가능 여부를 검증한다.

    Args:
        allow_external_llm: `.env`의 `ALLOW_EXTERNAL_LLM` 값.

    Raises:
        ExternalLLMDisabledError: 외부 LLM이 허용되지 않은 경우.
    """
    if not allow_external_llm:
        raise ExternalLLMDisabledError(
            "external-llm",
            "External LLM calls are disabled for identifiable patient data.",
        )
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

#### `test_ollama.py`

```python
"""OllamaAdapter 단위 테스트 (실제 Ollama 서버 X)."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.llm.ollama import OllamaAdapter
from src.llm.exceptions import LLMApiError, LLMParseError


def make_mock_json_response(content: str):
    """Ollama JSON 응답 모킹."""
    response = MagicMock()
    response.message.content = content
    return response


class TestOllamaAdapter:
    @pytest.mark.asyncio
    async def test_parse_supplement_success(self) -> None:
        client = AsyncMock()
        client.chat.return_value = make_mock_json_response(
            """
            {
              "ingredients": [
                {"name_ko": "비타민 C", "amount": 1000, "unit": "mg"},
                {"name_ko": "비타민 D", "amount": 25, "unit": "ug"}
              ]
            }
            """
        )

        adapter = OllamaAdapter(model="qwen3.5:9b", client=client)
        result = await adapter.parse_supplement("OCR 텍스트")

        assert len(result.ingredients) == 2
        assert result.ingredients[0].name_ko == "비타민 C"
        assert result.engine.startswith("ollama:")

    @pytest.mark.asyncio
    async def test_invalid_json_raises(self) -> None:
        client = AsyncMock()
        client.chat.return_value = make_mock_json_response("not-json")

        adapter = OllamaAdapter(model="qwen3.5:9b", client=client)
        with pytest.raises(LLMParseError):
            await adapter.parse_supplement("text")

    @pytest.mark.asyncio
    async def test_api_error_raises(self) -> None:
        client = AsyncMock()
        client.chat.side_effect = Exception("Ollama unavailable")

        adapter = OllamaAdapter(model="qwen3.5:9b", client=client)
        with pytest.raises(LLMApiError):
            await adapter.parse_supplement("text")

    @pytest.mark.asyncio
    async def test_invalid_schema_raises(self) -> None:
        client = AsyncMock()
        # amount가 음수 → ValidationError
        client.chat.return_value = make_mock_json_response(
            """
            {
              "ingredients": [
                {"name_ko": "비타민 C", "amount": -100, "unit": "mg"}
              ]
            }
            """
        )

        adapter = OllamaAdapter(model="qwen3.5:9b", client=client)
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

#### `test_real_ollama.py`

```python
"""실제 로컬 Ollama 호출 테스트.

조건: Ollama 서버 실행 + OLLAMA_MODEL 환경변수 또는 기본 모델 필요.
"""

import os

import pytest

from src.llm.ollama import OllamaAdapter


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_OLLAMA_TESTS") != "1",
    reason="Set RUN_OLLAMA_TESTS=1 after starting local Ollama",
)


@pytest.mark.integration
class TestOllamaReal:
    @pytest.mark.asyncio
    async def test_parse_typical_label(self):
        adapter = OllamaAdapter(
            model=os.getenv("OLLAMA_MODEL", "qwen3.5:9b")
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
        """Ollama 구조화 결과가 의료법 금지 표현을 포함하지 않는지."""
        adapter = OllamaAdapter(model=os.getenv("OLLAMA_MODEL", "qwen3.5:9b"))
        result = await adapter.parse_supplement("비타민 C 100mg")

        # 구조화 응답이라 의료 표현이 들어갈 가능성은 낮지만 검증
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
        llm = OllamaAdapter(model=os.getenv("OLLAMA_MODEL", "qwen3.5:9b"))
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
        adapter = OllamaAdapter(model=os.getenv("OLLAMA_MODEL", "qwen3.5:9b"))

        start = time.perf_counter()
        await adapter.parse_supplement(SAMPLE_LABEL_TEXT)
        elapsed = time.perf_counter() - start

        assert elapsed < 3.0
```

---

## ✅ Definition of Done

- [ ] `src/llm/exceptions.py` — LLMError 계층
- [ ] `src/llm/schemas.py` — ParsedSupplement 등 Pydantic 모델
- [ ] `src/llm/prompts.py` — 시스템 프롬프트
- [ ] `src/llm/base.py` — LLMAdapter ABC
- [ ] `src/llm/ollama.py` — Ollama Local API 구현
- [ ] `src/llm/external.py` — 외부 LLM 기본 비활성화 가드
- [ ] `src/nutrition/mfds_matcher.py` — 식약처 매칭
- [ ] `data/mfds/functional_ingredients.csv` — 매핑 시드 (최소 30종)
- [ ] 모든 함수 Google-style docstring
- [ ] 모든 함수 타입 힌트
- [ ] 단위 테스트 (Ollama/External guard/Matcher 각 10+)
- [ ] 로컬 Ollama 통합 테스트 (`RUN_OLLAMA_TESTS=1`)
- [ ] E2E 테스트 (OCR + LLM + 매칭)
- [ ] 성능 테스트 (< 3초)
- [ ] **시스템 프롬프트에 의료법 가이드 포함 검증**
- [ ] `mypy src/llm src/nutrition --strict` 통과

---

## 💡 구현 팁

### Structured Outputs 적용 방식

| 방식 | 장점 | 단점 |
|------|------|------|
| **JSON Schema format (권장)** | Pydantic 스키마를 그대로 재사용, 응답 검증 쉬움 | 모델별 응답 품질 재측정 필요 |
| `format="json"` | 빠르게 JSON만 강제 | 필드 누락·타입 오류를 별도 검증해야 함 |

### 모델 선택

- **qwen3.5:9b** 또는 **qwen3.5:latest** — 기본 후보
- **gemma4:e4b** 또는 **gemma4:latest** — 대안 후보
- **qwen3.5:27b**, **gemma4:26b** — MacBook Pro M4 Pro 24GB에서 성능 비교 후 제한 적용
- **qwen3.6:27b** 이상 — 향후 더 큰 스펙 장비 또는 사내 서버 후보
- **deepseek-v4-pro:cloud** — 클라우드 모델이므로 식별 가능 환자 데이터 처리 금지

### 시스템 프롬프트 안정성

시스템 프롬프트는 **자주 변경하지 않는다**. 모델별 정확도 비교가 어려워지고, 금지 표현 검증 결과가 흔들릴 수 있다.

```python
# Ollama 구조화 출력 호출
response = await client.chat(
    model=os.getenv("OLLAMA_MODEL", "qwen3.5:9b"),
    messages=[
        {"role": "system", "content": SUPPLEMENT_PARSING_SYSTEM},
        {"role": "user", "content": f"OCR 텍스트:\n\n{ocr_text}"},
    ],
    format=ParsedSupplement.model_json_schema(),
    stream=False,
    options={"temperature": 0},
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

- ❌ Ollama SDK 직접 호출 (Adapter 우회)
- ❌ Claude/OpenAI/Ollama Cloud에 식별 가능 환자 데이터 전송
- ❌ FastAPI 라우터 통합 (다음 가이드 09)
- ❌ DB 저장 (다음 가이드 09)
- ❌ 시스템 프롬프트에 사용자 데이터 직접 삽입 (Prompt Injection 위험)

---

## 🔗 관련 문서

- [`/CLAUDE.md`](../../CLAUDE.md)
- [`/backend/CLAUDE.md`](../../backend/CLAUDE.md)
- [`/data/CLAUDE.md`](../../data/CLAUDE.md)
- [`/docs/09-data-catalog.md §5.3, §5.4`](../09-data-catalog.md)
- [`/docs/12-local-llm-ollama-migration.md`](../12-local-llm-ollama-migration.md)
- [`/docs/13-algorithm-literature-evidence.md`](../13-algorithm-literature-evidence.md)
- [`/docs/10-compliance-checklist.md §10`](../10-compliance-checklist.md)
- 이전: [`07-ocr-pipeline.md`](./07-ocr-pipeline.md)
- 다음: [`09-supplement-registration-api.md`](./09-supplement-registration-api.md)

## 📚 사용 근거

- Ollama official documentation. Structured Outputs. https://docs.ollama.com/capabilities/structured-outputs
- Ollama official documentation. Chat API. https://docs.ollama.com/api/chat
