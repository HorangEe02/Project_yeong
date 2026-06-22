# dev-guides/16 — 식단 인식 (이미지 + 텍스트)

> **Phase**: 3 | **선행 작업**: [`08-llm-supplement-parsing.md`](./08-llm-supplement-parsing.md) | **예상 소요**: 4~5시간

---

## 🎯 작업 목표

사용자가 식사 사진 또는 텍스트("점심: 김치찌개, 공기밥, 계란말이")를 입력하면 음식·양·영양소를 인식하여 영양 분석에 통합한다. 환자 개인정보 보호를 위해 Ollama 로컬 Vision/Text 모델 + 농진청 식품성분 DB 매칭 기반으로 구현한다.

---

## 📋 산출물

```
backend/
├── src/
│   ├── meal/
│   │   ├── __init__.py
│   │   ├── base.py                # MealRecognizerAdapter ABC
│   │   ├── ollama_meal.py         # Ollama Vision/Text 인식 (주력)
│   │   ├── text_parser.py         # 텍스트 입력 파싱
│   │   ├── prompts.py             # 시스템 프롬프트
│   │   └── exceptions.py
│   └── nutrition/
│       └── rda_matcher.py         # 농진청 식품성분 DB 매칭
└── tests/
    ├── unit/meal/
    │   ├── test_ollama_meal.py    # 모킹
    │   ├── test_text_parser.py
    │   └── test_rda_matcher.py
    ├── integration/meal/
    │   └── test_meal_pipeline.py
    └── e2e/meal/
        └── test_meal_e2e.py
```

---

## 📐 설계 명세

> 🔍 **출처**: [docs/Nutrition-docs/13-algorithm-literature-evidence.md](../13-algorithm-literature-evidence.md), Ollama 공식 Structured Outputs 문서, AI Hub 음식 이미지 데이터, 이미지 기반 식이평가 systematic review.

### 근거 보강

| 항목 | 근거 수준 | 적용 방식 |
|------|----------|----------|
| 이미지 기반 식단 인식 | B | Food-101, AI Hub 음식 이미지 데이터, systematic review를 근거로 기능 방향을 유지한다. |
| 1장 이미지의 분량 추정 | C | 사진만으로 정확한 중량을 확정하지 않는다. 사용자 확인·수정 UI를 필수로 둔다. |
| Ollama Structured Outputs | A | Ollama 공식 문서의 `format` JSON Schema 방식을 사용하고 Pydantic으로 재검증한다. |
| 환자 개인정보 보호 | 필수 정책 | 기본 경로는 로컬 Ollama만 허용한다. 클라우드 LLM은 비식별 테스트 또는 승인된 환경에서만 사용한다. |

### 두 가지 입력 방식

```
[방식 A: 이미지 입력]
  사진 → Ollama Vision Structured Outputs → 음식 리스트 + 양 추정
  → 사용자 확인/수정 → 농진청 DB 매칭 → NutrientIntake 변환

[방식 B: 텍스트 입력]
  "점심: 김치찌개, 공기밥, 계란말이 1개"
  → Ollama Text Structured Outputs → 구조화된 음식 리스트
  → 사용자 확인/수정
  → 농진청 DB 매칭 → NutrientIntake 변환
```

### 농진청 식품성분 DB

```csv
food_code,name_ko,name_en,category,unit_size_g,kcal_per_unit,protein_g,fat_g,carb_g,...
F001,공기밥,Steamed Rice,곡류,210,310,5.6,0.6,68.5,...
F002,김치찌개,Kimchi Stew,찌개류,300,180,12.4,8.2,15.3,...
F003,계란말이,Egg Roll,난류,80,160,11.0,12.4,1.8,...
```

영양소별로 칼로리·단백질·탄수화물·지방 + 비타민·미네랄까지.

### Structured Outputs JSON Schema

```json
{
  "type": "object",
  "properties": {
    "meal_type": {
      "type": "string",
      "enum": ["breakfast", "lunch", "dinner", "snack"]
    },
    "items": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name_ko": { "type": "string" },
          "estimated_amount": { "type": "string", "description": "예: '1공기', '반접시', '약 100g'" },
          "estimated_grams": { "type": "number" },
          "confidence": { "type": "number", "minimum": 0, "maximum": 1 }
        },
        "required": ["name_ko", "estimated_grams", "confidence"]
      }
    }
  },
  "required": ["items"]
}
```

---

## 🔧 구현 명세

### 1. `src/meal/exceptions.py`

```python
"""식단 인식 예외."""

class MealRecognitionError(Exception):
    """식단 인식 실패."""


class MealApiError(MealRecognitionError):
    """API 호출 실패."""


class MealParseError(MealRecognitionError):
    """LLM 응답 파싱 실패."""
```

### 2. `src/meal/base.py`

```python
"""식단 인식 Adapter 추상."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pydantic import BaseModel, ConfigDict, Field


class RecognizedMealItem(BaseModel):
    """인식된 음식 한 개.

    Attributes:
        name_ko: 한국어 음식명.
        estimated_amount: 양 표현 (예: "1공기").
        estimated_grams: 추정 중량 (g).
        confidence: 모델 자기확신도 (0~1). 사용자 확인 전 참고값.
        user_confirmed: 사용자가 음식명·분량을 확인했는지 여부.
    """

    model_config = ConfigDict(frozen=True)

    name_ko: str = Field(..., min_length=1)
    estimated_amount: str
    estimated_grams: float = Field(..., gt=0)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    user_confirmed: bool = False


class RecognizedMeal(BaseModel):
    """인식된 식사 전체.

    Attributes:
        meal_type: breakfast/lunch/dinner/snack.
        items: 음식 리스트.
        engine: 사용된 엔진.
        raw_input: 원본 입력 (텍스트 또는 이미지 해시).
    """

    model_config = ConfigDict(frozen=True)

    meal_type: str = Field(..., pattern=r"^(breakfast|lunch|dinner|snack)$")
    items: list[RecognizedMealItem]
    engine: str = ""
    raw_input: str = ""


class MealRecognizerAdapter(ABC):
    """식단 인식 추상."""

    @abstractmethod
    async def recognize_from_image(self, image_bytes: bytes) -> RecognizedMeal:
        """이미지에서 식단 인식."""
        ...

    @abstractmethod
    async def recognize_from_text(self, text: str) -> RecognizedMeal:
        """텍스트에서 식단 추출."""
        ...

    @property
    @abstractmethod
    def engine_name(self) -> str:
        ...
```

### 3. `src/meal/prompts.py`

```python
"""식단 인식 시스템 프롬프트."""

from __future__ import annotations

from typing import Final


MEAL_RECOGNITION_SYSTEM: Final[str] = """\
당신은 한국 음식 사진과 식단 텍스트를 분석하여 음식명과 양을 추출하는 어시스턴트입니다.

## 작업
사용자의 식사 사진 또는 텍스트 설명에서 다음을 추출하세요:
1. 식사 종류 (아침/점심/저녁/간식)
2. 각 음식의 한국어 이름
3. 양 (양 표현 + g 단위 추정)

## 추정 규칙
- 한국 표준 1인분 기준으로 g 추정
- 공기밥 1개 = 약 210g, 국 1그릇 = 약 250g, 찌개 1그릇 = 약 300g
- 사진의 그릇 크기·시각적 양으로 보정
- 명확하지 않으면 1인분 기본값 사용

## 절대 금지
- 의료적 권고 ("이 음식은 당뇨에 좋습니다" 등)
- 칼로리·영양소 계산 (백엔드에서 별도 처리)
- 음식명 추측·창작 (사진/텍스트에 명확히 보이는 것만)

## 응답 형식
반드시 JSON Schema에 맞는 JSON만 반환하세요.
설명 문장이나 마크다운 코드블록은 포함하지 마세요.
"""


MEAL_RESPONSE_SCHEMA: Final[dict] = {
    "type": "object",
    "properties": {
        "meal_type": {
            "type": "string",
            "enum": ["breakfast", "lunch", "dinner", "snack"],
        },
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name_ko": {"type": "string"},
                    "estimated_amount": {"type": "string"},
                    "estimated_grams": {"type": "number"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
                "required": ["name_ko", "estimated_grams", "confidence"],
            },
        },
    },
    "required": ["items"],
}
```

### 4. `src/meal/ollama_meal.py`

```python
"""Ollama Vision/Text 식단 인식."""

from __future__ import annotations

import logging
from typing import Final

from ollama import AsyncClient, ResponseError
from pydantic import ValidationError

from src.meal.base import MealRecognizerAdapter, RecognizedMeal, RecognizedMealItem
from src.meal.exceptions import MealApiError, MealParseError
from src.meal.prompts import MEAL_RECOGNITION_SYSTEM


logger = logging.getLogger(__name__)


DEFAULT_MODEL: Final[str] = "gemma4:e4b"
DEFAULT_HOST: Final[str] = "http://127.0.0.1:11434"


class OllamaMealAdapter(MealRecognizerAdapter):
    """Ollama 로컬 Vision/Text 기반 식단 인식.

    - 이미지: Vision 모델 + Structured Outputs
    - 텍스트: 일반 텍스트 입력 + Structured Outputs
    """

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        host: str = DEFAULT_HOST,
        client: AsyncClient | None = None,
    ) -> None:
        self._client = client or AsyncClient(host=host)
        self._model = model

    @property
    def engine_name(self) -> str:
        return f"ollama_meal:{self._model}"

    async def recognize_from_image(self, image_bytes: bytes) -> RecognizedMeal:
        """이미지에서 식단 인식."""
        try:
            response = await self._client.chat(
                model=self._model,
                messages=[
                    {"role": "system", "content": MEAL_RECOGNITION_SYSTEM},
                    {
                        "role": "user",
                        "content": "이 식사 사진을 분석해주세요.",
                        "images": [image_bytes],
                    },
                ],
                format=RecognizedMeal.model_json_schema(),
                stream=False,
                options={"temperature": 0},
            )
        except ResponseError as e:
            raise MealApiError(f"Ollama Vision failed: {e.error}") from e
        except Exception as e:
            raise MealApiError(f"Ollama Vision failed: {e}") from e

        return self._parse_json_response(response.message.content, raw_input="<image>")

    async def recognize_from_text(self, text: str) -> RecognizedMeal:
        """텍스트에서 식단 추출."""
        try:
            response = await self._client.chat(
                model=self._model,
                messages=[
                    {"role": "system", "content": MEAL_RECOGNITION_SYSTEM},
                    {
                        "role": "user",
                        "content": f"다음 식단 설명을 분석해주세요:\n\n{text}",
                    },
                ],
                format=RecognizedMeal.model_json_schema(),
                stream=False,
                options={"temperature": 0},
            )
        except ResponseError as e:
            raise MealApiError(f"Ollama meal text parsing failed: {e.error}") from e
        except Exception as e:
            raise MealApiError(f"Ollama meal text parsing failed: {e}") from e

        return self._parse_json_response(response.message.content, raw_input=text)

    def _parse_json_response(self, response_text: str, raw_input: str) -> RecognizedMeal:
        """Ollama JSON 응답 파싱."""

        try:
            parsed = RecognizedMeal.model_validate_json(response_text)
            return parsed.model_copy(
                update={
                    "engine": self.engine_name,
                    "raw_input": raw_input[:200],
                },
            )
        except (ValueError, ValidationError) as e:
            raise MealParseError(f"Schema validation failed: {e}") from e
```

### 5. `src/meal/text_parser.py`

```python
"""텍스트 입력 사전 파싱 (LLM 호출 전 검증).

LLM 호출 지연을 줄이기 위해 단순 케이스는 정규식으로 처리.
복잡한 케이스만 LLM 호출.
"""

from __future__ import annotations

import re
from typing import Final


SIMPLE_FOOD_PATTERN: Final[re.Pattern] = re.compile(
    r"^([가-힣]+)\s*(\d+)\s*(공기|그릇|개|조각|컵)?$"
)


def is_simple_meal_text(text: str) -> bool:
    """단순 형식 (음식명 + 양) 인지 확인.

    Args:
        text: 입력 텍스트.

    Returns:
        단순 형식이면 True.

    Examples:
        >>> is_simple_meal_text("공기밥 1개")
        True
        >>> is_simple_meal_text("점심에 김치찌개랑 공기밥, 그리고 계란말이를 먹었어")
        False
    """
    return bool(SIMPLE_FOOD_PATTERN.match(text.strip()))


def normalize_meal_text(text: str) -> str:
    """입력 텍스트 정규화.

    - 공백 정규화
    - 특수문자 제거
    """
    text = re.sub(r"\s+", " ", text)
    text = text.strip()
    return text
```

### 6. `src/nutrition/rda_matcher.py`

```python
"""농진청 식품성분 DB 매칭."""

from __future__ import annotations

import csv
import logging
from functools import lru_cache
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ConfigDict

from src.meal.base import RecognizedMealItem
from src.models.schemas.nutrition import NutrientIntake


logger = logging.getLogger(__name__)


KOREAN_FOODS_PATH: Final[Path] = Path("data/rda/korean_foods.csv")


class FoodNutrient(BaseModel):
    """식품 1g당 영양소 함량."""

    model_config = ConfigDict(frozen=True)

    food_code: str
    name_ko: str
    kcal_per_g: float
    nutrients_per_g: dict[str, float]  # {"vitamin_c_mg": 0.05, "calcium_mg": 0.10, ...}


@lru_cache(maxsize=1)
def load_foods_db() -> dict[str, FoodNutrient]:
    """농진청 DB 로드.

    Returns:
        {정규화된 음식명 → FoodNutrient}.
    """
    if not KOREAN_FOODS_PATH.exists():
        logger.warning("Korean foods CSV not found")
        return {}

    db: dict[str, FoodNutrient] = {}
    with KOREAN_FOODS_PATH.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = _normalize(row["name_ko"])
            unit_size = float(row["unit_size_g"])
            kcal_total = float(row["kcal_per_unit"])

            # 1g당 환산
            nutrients_per_g: dict[str, float] = {}
            for col, value in row.items():
                if col in ("food_code", "name_ko", "name_en", "category",
                           "unit_size_g", "kcal_per_unit"):
                    continue
                if value and unit_size > 0:
                    nutrients_per_g[col] = float(value) / unit_size

            db[name] = FoodNutrient(
                food_code=row["food_code"],
                name_ko=row["name_ko"],
                kcal_per_g=kcal_total / unit_size if unit_size > 0 else 0,
                nutrients_per_g=nutrients_per_g,
            )
    return db


def _normalize(name: str) -> str:
    """음식명 정규화."""
    return "".join(c for c in name.lower() if c.isalnum())


def match_food(item: RecognizedMealItem) -> FoodNutrient | None:
    """인식된 음식을 농진청 DB와 매칭.

    Args:
        item: 인식된 음식.

    Returns:
        매칭된 FoodNutrient, 없으면 None.
    """
    db = load_foods_db()
    normalized = _normalize(item.name_ko)
    return db.get(normalized)


def to_nutrient_intakes(meal_items: list[RecognizedMealItem]) -> list[NutrientIntake]:
    """인식된 식사 → NutrientIntake 리스트.

    매칭 실패 항목은 결과에서 제외 (warning 로그).
    """
    intakes: list[NutrientIntake] = []
    for item in meal_items:
        food = match_food(item)
        if food is None:
            logger.warning("Food not in DB: %s", item.name_ko)
            continue

        # 음식의 추정 g × 1g당 영양소 = 섭취 영양소
        for nutrient_code, per_g in food.nutrients_per_g.items():
            amount = per_g * item.estimated_grams
            if amount <= 0:
                continue
            # nutrient_code는 이미 표준 단위 포함 (e.g., "vitamin_c_mg")
            unit = nutrient_code.rsplit("_", 1)[-1]
            intakes.append(NutrientIntake(
                code=nutrient_code,
                amount=round(amount, 3),
                unit=unit,
                source="meal",
            ))
    return intakes
```

---

## 🧪 테스트 (4-Tier)

### Tier 1: 단위 테스트

#### `test_ollama_meal.py`

| 테스트 | 검증 |
|-------|------|
| `test_recognize_image_with_schema` | JSON Schema 응답 파싱 정상 |
| `test_recognize_text_basic` | 텍스트 입력 처리 |
| `test_invalid_json_raises` | JSON 형식 오류 → MealParseError |
| `test_api_error_raises` | API 에러 → MealApiError |
| `test_invalid_grams_raises` | grams=0 → ValidationError |

#### `test_text_parser.py`

| 테스트 | 검증 |
|-------|------|
| `test_simple_meal_recognized` | "공기밥 1개" → True |
| `test_complex_text_not_simple` | 긴 문장 → False |
| `test_normalize_whitespace` | "공기밥  1개" → "공기밥 1개" |

#### `test_rda_matcher.py`

| 테스트 | 검증 |
|-------|------|
| `test_match_steamed_rice` | "공기밥" 매칭 |
| `test_no_match_returns_none` | 알 수 없는 음식 |
| `test_to_nutrient_intakes_scales_by_grams` | 200g vs 100g → 2배 |
| `test_to_nutrient_intakes_skips_unmatched` | 매칭 실패는 제외 |

### Tier 2: 통합 테스트 (모킹)

```python
"""식단 인식 + 농진청 매칭 통합."""

class TestMealPipeline:
    @pytest.mark.asyncio
    async def test_text_to_intakes(self, mock_ollama):
        recognizer = OllamaMealAdapter(client=mock_ollama)
        meal = await recognizer.recognize_from_text("공기밥 1개, 김치찌개 1그릇")

        intakes = to_nutrient_intakes(meal.items)
        # 공기밥의 탄수화물 + 김치찌개의 영양소가 포함되어야
        codes = [i.code for i in intakes]
        assert any("carbs" in c or "carb" in c for c in codes) or len(intakes) > 0
```

### Tier 3: 실 API 테스트 (선택)

```python
pytestmark = pytest.mark.skipif(
    os.getenv("RUN_OLLAMA_TESTS") != "1",
    reason="Set RUN_OLLAMA_TESTS=1 after starting local Ollama",
)
@pytest.mark.integration
class TestOllamaMealReal:
    @pytest.mark.asyncio
    async def test_real_meal_image(self):
        with open("tests/fixtures/sample_meal.jpg", "rb") as f:
            image = f.read()

        recognizer = OllamaMealAdapter(model=os.getenv("OLLAMA_MODEL", "gemma4:e4b"))
        meal = await recognizer.recognize_from_image(image)

        assert len(meal.items) > 0
        for item in meal.items:
            assert item.estimated_grams > 0
            assert item.name_ko
```

### Tier 4: E2E 테스트

```python
"""사진 → 인식 → 매칭 → 영양 분석 통합."""

@pytest.mark.e2e
class TestMealE2E:
    @pytest.mark.asyncio
    async def test_meal_image_to_diagnosis(self):
        """식사 사진 → NutrientIntake → 부족 영양소 진단."""
        with open("tests/fixtures/sample_meal.jpg", "rb") as f:
            image = f.read()

        # 1. 인식
        recognizer = OllamaMealAdapter(model=os.getenv("OLLAMA_MODEL", "gemma4:e4b"))
        meal = await recognizer.recognize_from_image(image)

        # 2. 영양소 변환
        intakes = to_nutrient_intakes(meal.items)
        assert len(intakes) > 0

        # 3. 진단 (06번 모듈)
        from src.nutrition.diagnosis import diagnose
        from src.models.schemas.nutrition import UserKDRIsContext
        user = UserKDRIsContext(age=30, sex="male")
        result = diagnose(intakes, user)

        # 4. 결과 검증
        assert len(result.diagnoses) > 0
```

---

## ✅ Definition of Done

- [ ] `data/rda/korean_foods.csv` — 최소 50종 (밥·국·찌개·반찬·과일)
- [ ] `src/meal/exceptions.py`, `base.py`, `prompts.py`
- [ ] `src/meal/ollama_meal.py` — 이미지·텍스트 인식
- [ ] `src/meal/text_parser.py` — 단순 케이스 사전 처리
- [ ] `src/nutrition/rda_matcher.py` — 농진청 매칭
- [ ] 모든 함수 Google-style docstring
- [ ] 모든 함수 타입 힌트
- [ ] 단위 테스트 (각 모듈) 25+
- [ ] 통합 테스트 (인식 + 매칭)
- [ ] (선택) 실 API 테스트
- [ ] E2E 테스트 (사진 → 진단)
- [ ] **시스템 프롬프트의 의료 표현 가이드 검증**
- [ ] `mypy src/meal src/nutrition --strict` 통과

---

## 💡 구현 팁

### 양 추정의 한계

학생 프로젝트에서 양 추정 정확도는 실제 데이터로 검증하기 전까지 수치로 주장하지 않는다. UI에서:
- 인식 결과를 사용자가 **수정 가능**
- "확실하지 않음" 표시 (`confidence`와 사용자 확인 상태)
- 자주 먹는 음식은 학습 (Phase 4+)

### 지연 시간 최적화

```
이미지 1장: Ollama Vision 모델별 로컬 응답 시간 측정
텍스트만:    Ollama Text 모델별 로컬 응답 시간 측정

→ 텍스트 입력 우선 권장. 이미지는 백업.
```

### 농진청 DB 시드

최소 50종으로 시작 (학생 팀이 점진적 확장):
- 밥류: 공기밥, 잡곡밥, 비빔밥
- 국·찌개: 김치찌개, 된장국, 미역국
- 반찬: 김치, 시금치나물, 멸치볶음
- 단백질: 계란말이, 닭가슴살, 두부
- 면류: 라면, 짜장면, 칼국수
- 과일: 사과, 바나나, 귤
- ... (점진적 추가)

---

## 🚫 이 작업에서 하지 말 것

- ❌ "이 음식은 당뇨에 안 좋다" 같은 의료 권고
- ❌ 칼로리·영양소 직접 계산 (DB 매칭만)
- ❌ FastAPI 라우터 통합 (별도 작업)
- ❌ 모바일 식단 입력 화면 (가이드 20)

---

## 🔗 관련 문서

- [`/docs/Nutrition-docs/09-data-catalog.md`](../09-data-catalog.md) — 농진청 데이터
- [`/docs/Nutrition-docs/13-algorithm-literature-evidence.md`](../13-algorithm-literature-evidence.md)
- 이전: [`15-goal-based-analysis.md`](./15-goal-based-analysis.md)
- 다음: [`17-feedback-and-notifications.md`](./17-feedback-and-notifications.md)

## 📚 사용 근거

- AI Hub. 음식 이미지 및 영양정보 텍스트 데이터. https://aihub.or.kr/aihubdata/data/view.do?dataSetSn=74
- AI Hub. 한국 이미지(음식) 데이터. https://www.aihub.or.kr/aihubdata/data/view.do?aihubDataSe=&currMenu=&dataSetSn=79&topMenu=
- Bossard L, Guillaumin M, Van Gool L. Food-101. ECCV. 2014. https://data.vision.ee.ethz.ch/cvl/datasets_extra/food-101/
- Dalakleidi K, et al. Applying Image-Based Food-Recognition Systems on Dietary Assessment. Advances in Nutrition. 2022. https://pubmed.ncbi.nlm.nih.gov/35803496/
- Lo FPW, et al. Image-Based Food Classification and Volume Estimation for Dietary Assessment. IEEE Journal of Biomedical and Health Informatics. 2020. https://pubmed.ncbi.nlm.nih.gov/32365038/
- Ollama official documentation. Structured Outputs. https://docs.ollama.com/capabilities/structured-outputs
- Ollama official documentation. Chat API. https://docs.ollama.com/api/chat
