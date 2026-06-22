# dev-guides/01 — BMI 분류 + v1 활동점수

> **Phase**: 1 | **선행 작업**: [`00-setup-environment.md`](./00-setup-environment.md) | **예상 소요**: 2~3시간

---

## 🎯 작업 목표

한국·아시아 BMI 분류와 v1 활동점수 (권장 걸음수 + 기본점수) 알고리즘을 구현하고, 회사 가이드 PPTX의 계산 예시를 단위 테스트로 검증한다.

---

## 📋 산출물

```
backend/
├── src/
│   ├── models/schemas/
│   │   ├── algorithm.py       # BMICategory enum
│   │   └── user.py            # UserProfile
│   └── algorithms/
│       ├── bmi.py             # BMI 분류
│       └── activity.py        # v1 (이 작업), v2~v4 (다음)
└── tests/
    └── unit/algorithms/
        ├── __init__.py
        ├── test_bmi.py
        └── test_activity_v1.py
```

---

## 📐 알고리즘 명세

> 🔍 **출처**: [docs/Nutrition-docs/07-core-algorithm.md §3.1, §3.2](../07-core-algorithm.md), [docs/Nutrition-docs/13-algorithm-literature-evidence.md](../13-algorithm-literature-evidence.md)

### 근거 보강

| 항목 | 근거 수준 | 적용 방식 |
|------|----------|----------|
| BMI 분류 | A | WHO Expert Consultation의 아시아 BMI action point를 근거로 한국·아시아 기준을 유지한다. |
| 8,000보 기준 | B | Paluch et al. 2022의 step count 메타분석과 Lee et al. 2019의 older women cohort 결과를 참고해 기본 목표로 유지한다. |
| 성별·나이·BMI 계수 | C | 논문에서 직접 제시된 값이 아니므로 프로젝트 휴리스틱으로 표시하고 설정값으로 분리한다. |

> 사용자 화면에서는 BMI와 활동점수를 건강 상태의 참고 지표로만 설명한다. 질병 진단, 치료 효과, 감량 보장 표현은 사용하지 않는다.

### BMI 분류 (한국·아시아 기준)

```
BMI = 체중(kg) / 키(m)²

분류:
  < 18.5     → underweight
  18.5~22.9  → normal
  23.0~24.9  → overweight
  25.0~29.9  → obese_1
  ≥ 30.0     → obese_2
```

### v1 권장 걸음수

```
권장걸음수 = 8,000 × 성별계수 × 나이계수 × BMI계수

성별계수: 여성 0.95 / 남성 1.0
나이계수: 40세 미만 1.0 / 40~59세 0.9 / 60세 이상 0.8
BMI계수:  저체중 0.9 / 정상 1.0 / 과체중 1.05 / 비만1 1.1 / 비만2 1.15
```

### v1 기본점수

```
기본점수 = min(실제걸음수 ÷ 권장걸음수, 1.2) × 83.33
```

> 📌 달성률 120%에서 정확히 100점이 되도록 설계됨 (1.2 × 83.33 = 100).

---

## 🔧 구현 명세

### 1. `src/models/schemas/algorithm.py`

```python
"""알고리즘 관련 공통 스키마."""

from __future__ import annotations

from enum import StrEnum


class BMICategory(StrEnum):
    """BMI 분류 (한국·아시아 기준).

    Reference:
        docs/Nutrition-docs/07-core-algorithm.md §3.1
    """

    UNDERWEIGHT = "underweight"
    NORMAL = "normal"
    OVERWEIGHT = "overweight"
    OBESE_1 = "obese_1"
    OBESE_2 = "obese_2"
```

### 2. `src/models/schemas/user.py`

```python
"""사용자 프로필 스키마."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class UserProfile(BaseModel):
    """건강 분석을 위한 사용자 프로필 입력.

    Attributes:
        age: 만 나이 (1~120).
        sex: 성별 ("male" | "female").
        height_cm: 키 (cm, 50~250).
        weight_kg: 체중 (kg, 10~300).
        diseases: 만성질환 코드 리스트 (없으면 빈 리스트).
        is_smoker: 흡연자 여부.
    """

    model_config = ConfigDict(
        frozen=True,
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    age: int = Field(..., ge=1, le=120, description="만 나이")
    sex: Literal["male", "female"] = Field(..., description="성별")
    height_cm: float = Field(..., ge=50, le=250, description="키 (cm)")
    weight_kg: float = Field(..., ge=10, le=300, description="체중 (kg)")
    diseases: list[str] = Field(default_factory=list, description="만성질환 코드")
    is_smoker: bool = Field(default=False, description="흡연자 여부")
```

### 3. `src/algorithms/bmi.py`

다음 두 함수를 구현:

```python
def calculate_bmi(weight_kg: float, height_cm: float) -> float: ...
def classify_bmi(bmi: float) -> BMICategory: ...
```

#### 요구사항

- `calculate_bmi`: 입력 검증 (체중 10~300, 키 50~250), 결과는 소수점 1자리 round
- `classify_bmi`: 한국·아시아 기준 (Rule 8 in `/CLAUDE.md`)
- 모든 함수에 Google-style docstring + Examples 섹션
- 입력 범위 벗어나면 `ValueError` raise

### 4. `src/algorithms/activity.py`

다음 함수들을 구현 (v1 부분만 — v2~v4는 다음 작업):

```python
# 모듈 상수
SEX_FACTORS: dict[str, float] = ...
BMI_FACTORS: dict[BMICategory, float] = ...
V1_BASE_MAX: float = 83.33
V1_ACHIEVEMENT_CAP: float = 1.2


def get_age_factor(age: int) -> float: ...
def calculate_recommended_steps(
    sex: str, age: int, bmi_category: BMICategory
) -> int: ...
def calculate_v1_score(actual_steps: int, recommended_steps: int) -> float: ...
```

#### 요구사항

- `get_age_factor`: 40세 미만 1.0 / 40~59 0.9 / 60+ 0.8, age 검증
- `calculate_recommended_steps`: 4개 계수 곱셈, `round()` 정수 반환
- `calculate_v1_score`: `min(achievement, 1.2)` 캡, 100 상한 자연 보장
- 모든 함수에 Google-style docstring + Examples
- 모듈 상수에 한 줄 docstring (`"""..."""` 다음 줄)

---

## 🧪 단위 테스트 (필수 작성)

### `tests/conftest.py` 갱신

```python
"""공통 pytest 픽스처."""

import pytest

from src.models.schemas.user import UserProfile


@pytest.fixture
def user_50f_obese1() -> UserProfile:
    """[가이드 예시 1] 50대 여성, 비만 1단계, 당뇨+고혈압."""
    return UserProfile(
        age=50,
        sex="female",
        height_cm=160,
        weight_kg=68.0,
        diseases=["diabetes", "hypertension"],
    )


@pytest.fixture
def user_45m_overweight() -> UserProfile:
    """[가이드 예시 2] 45세 남성, 175cm 82kg."""
    return UserProfile(
        age=45,
        sex="male",
        height_cm=175,
        weight_kg=82.0,
        diseases=[],
    )
```

### `tests/unit/algorithms/test_bmi.py`

다음 테스트 케이스를 모두 포함:

| 테스트 | 입력 | 기대 결과 |
|-------|------|---------|
| `test_bmi_underweight` | 50kg, 170cm | BMI 17.3, UNDERWEIGHT |
| `test_bmi_normal` | 60kg, 170cm | BMI 20.8, NORMAL |
| `test_bmi_overweight` | 70kg, 170cm | BMI 24.2, OVERWEIGHT |
| `test_bmi_obese_1` | 80kg, 170cm | BMI 27.7, OBESE_1 |
| `test_bmi_obese_2` | 90kg, 170cm | BMI 31.1, OBESE_2 |
| `test_boundary_normal_lower` | 53.4kg, 170cm | BMI 18.5, NORMAL (경계) |
| `test_boundary_overweight_lower` | 66.4kg, 170cm | BMI 23.0, OVERWEIGHT (경계) |
| `test_boundary_obese1_lower` | 72.3kg, 170cm | BMI 25.0, OBESE_1 (경계) |
| `test_boundary_obese2_lower` | 86.7kg, 170cm | BMI 30.0, OBESE_2 (경계) |
| **`test_50f_obese1_guide_example`** | **fixture user_50f_obese1** | **BMI 26.5, OBESE_1** |
| `test_invalid_weight_raises` | -10kg | ValueError |
| `test_invalid_height_raises` | 0cm | ValueError |

`@pytest.mark.parametrize` 적극 활용 권장.

### `tests/unit/algorithms/test_activity_v1.py`

| 테스트 | 입력 | 기대 결과 |
|-------|------|---------|
| **`test_recommended_steps_50f_obese1_guide`** | sex=female, age=50, BMI_cat=OBESE_1 | **7,524 (가이드 예시)** |
| `test_recommended_steps_male_normal_30` | sex=male, age=30, BMI_cat=NORMAL | 8,000 |
| `test_recommended_steps_female_normal_30` | sex=female, age=30, BMI_cat=NORMAL | 7,600 (×0.95) |
| `test_recommended_steps_male_50_normal` | sex=male, age=50, BMI_cat=NORMAL | 7,200 (×0.9) |
| `test_recommended_steps_male_65_normal` | sex=male, age=65, BMI_cat=NORMAL | 6,400 (×0.8) |
| `test_age_factor_under_40` | age=39 | 1.0 |
| `test_age_factor_40_59` | age=40, 50, 59 | 0.9 |
| `test_age_factor_60_plus` | age=60, 75 | 0.8 |
| `test_v1_at_recommended` | 7524 / 7524 | ≈83.33 |
| `test_v1_at_120_pct_cap` | 9028 / 7524 | ≈100.0 (캡 상한) |
| `test_v1_above_cap_remains_100` | 15048 / 7524 | ≈100.0 (200%여도 캡) |
| **`test_v1_50f_obese1_7000_guide_example`** | 7000 / 7524 | **≈77.5 (가이드 예시)** |
| `test_v1_zero_steps` | 0 / 7524 | 0.0 |

#### 부동소수점 비교 표준

```python
assert v1_score == pytest.approx(77.5, abs=0.1)
```

가이드 예시는 PPTX의 손계산이라 ±0.1 오차 허용.

---

## 📊 가이드 예시 검증 매트릭스

이 작업이 완료되면 다음 회사 가이드 예시가 모두 자동 검증됩니다:

```
입력: 50대 여성, 키 160cm, 체중 68kg, 당뇨+고혈압, 7,000보/일

✅ BMI = 68 / 1.6² = 26.56 ≈ 26.5 → OBESE_1
✅ 권장걸음수 = 8000 × 0.95 × 0.9 × 1.1 = 7,524
✅ v1 점수 = min(7000/7524, 1.2) × 83.33 = 0.930 × 83.33 ≈ 77.5
```

---

## ✅ Definition of Done

- [ ] `src/models/schemas/algorithm.py` — BMICategory enum
- [ ] `src/models/schemas/user.py` — UserProfile (Pydantic v2, frozen)
- [ ] `src/algorithms/bmi.py` — calculate_bmi, classify_bmi
- [ ] `src/algorithms/activity.py` — get_age_factor, calculate_recommended_steps, calculate_v1_score
- [ ] 모든 함수에 Google-style docstring (Args/Returns/Raises/Examples)
- [ ] 모든 함수에 타입 힌트 100%
- [ ] `tests/conftest.py` — 가이드 예시 픽스처 2개
- [ ] `tests/unit/algorithms/test_bmi.py` — 12+ 테스트, 가이드 예시 포함
- [ ] `tests/unit/algorithms/test_activity_v1.py` — 13+ 테스트, 가이드 예시 포함
- [ ] `mypy src/algorithms src/models --strict` 통과
- [ ] `pytest tests/unit/algorithms -v` 모든 테스트 통과
- [ ] 코드 커버리지 ≥ 90% (해당 모듈)
- [ ] `black src tests --check` 통과
- [ ] `ruff check src tests` 통과 (warning 0)

---

## 🚫 이 작업에서 하지 말 것

- ❌ v2, v3, v4 구현 (다음 작업)
- ❌ DB 모델 정의
- ❌ FastAPI 라우터 작성
- ❌ HealthKit 연동

---

## 💡 구현 팁

### round() vs int()

```python
# ✅ round() 권장 (가이드 예시와 일치)
return round(8000 * 0.95 * 0.9 * 1.1)  # 7524 (Python의 banker's rounding)

# ❌ int() 사용 시 7523이 될 수 있음
return int(8000 * 0.95 * 0.9 * 1.1)
```

### Enum + dict 매핑

```python
BMI_FACTORS: dict[BMICategory, float] = {
    BMICategory.UNDERWEIGHT: 0.9,
    BMICategory.NORMAL: 1.0,
    BMICategory.OVERWEIGHT: 1.05,
    BMICategory.OBESE_1: 1.1,
    BMICategory.OBESE_2: 1.15,
}
"""BMI 카테고리별 권장걸음수 보정 계수."""
```

### Boolean 단축 평가 vs 명시적 비교

```python
# ✅ 명시적
if not 1 <= age <= 120:
    raise ValueError(...)

# ❌ 모호함
if age < 1 or age > 120:
    raise ValueError(...)
```

---

## 🔗 관련 문서

- [`/CLAUDE.md`](../../CLAUDE.md)
- [`/backend/CLAUDE.md`](../../backend/CLAUDE.md)
- [`/docs/Nutrition-docs/07-core-algorithm.md §3.1, §3.2`](../07-core-algorithm.md)
- 이전 작업: [`00-setup-environment.md`](./00-setup-environment.md)
- 다음 작업: [`02-v2-v3-v4-algorithms.md`](./02-v2-v3-v4-algorithms.md)
