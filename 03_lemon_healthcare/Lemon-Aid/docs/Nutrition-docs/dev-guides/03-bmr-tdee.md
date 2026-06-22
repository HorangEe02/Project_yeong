# dev-guides/03 — BMR + TDEE

> **Phase**: 1 | **선행 작업**: [`02-v2-v3-v4-algorithms.md`](./02-v2-v3-v4-algorithms.md) | **예상 소요**: 1.5~2시간

---

## 🎯 작업 목표

기초대사량(BMR, Mifflin-St Jeor)과 총 에너지 소비량(TDEE, 활동계수)을 계산하는 알고리즘을 구현하고 가이드 예시를 검증한다.

---

## 📋 산출물

```
backend/
├── src/algorithms/
│   └── metabolism.py            # BMR + TDEE
└── tests/unit/algorithms/
    └── test_metabolism.py
```

---

## 📐 알고리즘 명세

> 🔍 **출처**: [docs/Nutrition-docs/07-core-algorithm.md §3.6, §3.7](../07-core-algorithm.md), [docs/Nutrition-docs/13-algorithm-literature-evidence.md](../13-algorithm-literature-evidence.md)

### 근거 보강

| 항목 | 근거 수준 | 적용 방식 |
|------|----------|----------|
| BMR / REE 공식 | A | Mifflin et al. 1990의 resting energy expenditure 예측식을 코드화한다. |
| 걸음수 기반 활동계수 | C | Mifflin 공식의 일부가 아니라 프로젝트 활동량 추정 테이블이다. 설정값으로 분리하고 실제 체중 변화 로그로 보정한다. |

> UI와 API 응답 필드명은 `estimated_bmr`, `estimated_tdee`처럼 예측값임을 드러내는 이름을 우선 사용한다.

### BMR — Mifflin-St Jeor 공식

```
남성: BMR = 10×W + 6.25×H − 5×A + 5
여성: BMR = 10×W + 6.25×H − 5×A − 161

W: 체중 (kg)
H: 키 (cm)
A: 나이 (세)
```

### TDEE — 활동계수

```
TDEE = BMR × 활동계수

활동계수 (걸음수 기반):
  < 5,000보       → 1.200 (좌식)
  5,000~7,499     → 1.375 (가벼운 활동)
  7,500~9,999     → 1.550 (보통 활동)
  10,000~12,499   → 1.725 (활발)
  ≥ 12,500        → 1.900 (매우 활발)
```

---

## 🔧 구현 명세

### `src/algorithms/metabolism.py`

#### 모듈 상수

```python
"""기초대사량 및 총에너지소비량 계산 모듈.

회사 가이드의 Mifflin-St Jeor 공식과 활동계수 테이블을 구현한다.

Reference:
    docs/Nutrition-docs/07-core-algorithm.md §3.6, §3.7
"""

from __future__ import annotations

from typing import Final


# Mifflin-St Jeor 공식 상수
BMR_WEIGHT_COEF: Final[float] = 10.0
BMR_HEIGHT_COEF: Final[float] = 6.25
BMR_AGE_COEF: Final[float] = 5.0
BMR_MALE_CONSTANT: Final[float] = 5.0
BMR_FEMALE_CONSTANT: Final[float] = -161.0

# 활동계수 (걸음수 → 활동수준)
ACTIVITY_FACTORS: Final[list[tuple[int, float]]] = [
    (5000, 1.200),    # < 5,000 보 → 1.200
    (7500, 1.375),    # < 7,500 보 → 1.375
    (10000, 1.550),   # < 10,000 보 → 1.550
    (12500, 1.725),   # < 12,500 보 → 1.725
]
"""(걸음수 상한, 활동계수) 정렬된 튜플 리스트."""

ACTIVITY_FACTOR_MAX: Final[float] = 1.900
"""12,500보 이상의 매우 활발한 활동계수."""
```

#### 구현해야 할 함수

```python
def calculate_bmr(
    weight_kg: float,
    height_cm: float,
    age: int,
    sex: str,
) -> float:
    """Mifflin-St Jeor 공식으로 기초대사량(BMR)을 계산한다.

    Args:
        weight_kg: 체중 (kg, 10~300).
        height_cm: 키 (cm, 50~250).
        age: 만 나이 (1~120).
        sex: 성별 ("male" | "female").

    Returns:
        기초대사량 (kcal/일, 소수점 1자리).

    Raises:
        ValueError: 입력값이 허용 범위를 벗어나거나 sex가 잘못된 경우.

    Examples:
        >>> calculate_bmr(68.0, 160, 50, "female")
        1269.0
        >>> calculate_bmr(82.0, 175, 45, "male")
        1694.0

    Reference:
        docs/Nutrition-docs/07-core-algorithm.md §3.6
    """
    ...


def get_activity_factor(daily_steps: int) -> float:
    """일일 걸음수에 따른 활동계수를 반환한다.

    Args:
        daily_steps: 일일 걸음수 (0 이상).

    Returns:
        활동계수 (1.200 ~ 1.900).

    Raises:
        ValueError: daily_steps < 0인 경우.

    Examples:
        >>> get_activity_factor(3000)
        1.2
        >>> get_activity_factor(6500)
        1.375
        >>> get_activity_factor(8000)
        1.55
        >>> get_activity_factor(15000)
        1.9
    """
    ...


def calculate_tdee(bmr: float, daily_steps: int) -> float:
    """총 에너지 소비량(TDEE)을 계산한다.

    Args:
        bmr: 기초대사량 (kcal/일).
        daily_steps: 일일 걸음수.

    Returns:
        총 에너지 소비량 (kcal/일, 소수점 1자리).

    Raises:
        ValueError: bmr < 0 또는 daily_steps < 0인 경우.

    Examples:
        >>> calculate_tdee(1269.0, 6500)
        1745.0

    Reference:
        docs/Nutrition-docs/07-core-algorithm.md §3.7
    """
    ...
```

#### 요구사항

- 모든 함수에 Google-style docstring (Args/Returns/Raises/Examples)
- 모든 함수에 타입 힌트
- `calculate_bmr`은 입력 검증 (체중·키·나이·성별 모두)
- `get_activity_factor`는 정렬된 ACTIVITY_FACTORS 순회로 매칭
- 결과는 `round(value, 1)`

---

## 🧪 단위 테스트

### `tests/unit/algorithms/test_metabolism.py`

#### TestBMR

| 테스트 | 입력 | 기대값 |
|-------|------|-------|
| **`test_bmr_50f_guide_example`** | **68kg, 160cm, 50세, female** | **1,269.0 (가이드)** |
| **`test_bmr_45m_guide_example`** | **82kg, 175cm, 45세, male** | **1,694.0 (가이드)** |
| `test_bmr_male_female_diff` | 70kg, 170cm, 30세 | male - female = 166 (5−(−161)) |
| `test_bmr_higher_weight_higher_bmr` | 80kg vs 70kg (동일 키·나이·성별) | 80kg가 100 더 높음 |
| `test_bmr_higher_age_lower_bmr` | 50세 vs 30세 (동일) | 50세가 100 더 낮음 |
| `test_bmr_invalid_sex_raises` | sex="other" | ValueError |
| `test_bmr_invalid_age_raises` | age=0 | ValueError |
| `test_bmr_invalid_weight_raises` | weight=5 | ValueError |

#### TestActivityFactor

| 테스트 | 입력 | 기대값 |
|-------|------|-------|
| `test_sedentary` | 3000 | 1.200 |
| **`test_light_activity_guide_50f`** | **6500** | **1.375 (가이드)** |
| **`test_moderate_activity_guide_45m`** | **8000** | **1.550 (가이드)** |
| `test_active` | 11000 | 1.725 |
| `test_very_active` | 15000 | 1.900 |
| **경계값** |||
| `test_boundary_4999` | 4999 | 1.200 |
| `test_boundary_5000` | 5000 | 1.375 |
| `test_boundary_7499` | 7499 | 1.375 |
| `test_boundary_7500` | 7500 | 1.550 |
| `test_boundary_9999` | 9999 | 1.550 |
| `test_boundary_10000` | 10000 | 1.725 |
| `test_boundary_12499` | 12499 | 1.725 |
| `test_boundary_12500` | 12500 | 1.900 |
| `test_zero_steps` | 0 | 1.200 |
| `test_negative_raises` | -100 | ValueError |

#### TestTDEE

| 테스트 | 입력 | 기대값 |
|-------|------|-------|
| **`test_tdee_50f_guide_example`** | **bmr=1269, steps=6500** | **≈1,745 (가이드)** |
| **`test_tdee_45m_guide_example`** | **bmr=1694, steps=8000** | **≈2,625 (가이드)** |
| `test_tdee_zero_steps` | bmr=1500, steps=0 | 1500 × 1.2 = 1800 |
| `test_tdee_negative_bmr_raises` | bmr=-100 | ValueError |

#### 가이드 예시 통합 테스트

```python
def test_bmr_tdee_50f_full_chain(user_50f_obese1):
    """[가이드 예시 1 통합] 50대 여성 BMR → TDEE."""
    bmr = calculate_bmr(
        weight_kg=user_50f_obese1.weight_kg,
        height_cm=user_50f_obese1.height_cm,
        age=user_50f_obese1.age,
        sex=user_50f_obese1.sex,
    )
    assert bmr == 1269.0  # 가이드

    tdee = calculate_tdee(bmr, daily_steps=6500)
    assert tdee == pytest.approx(1745.0, abs=0.5)  # 가이드


def test_bmr_tdee_45m_full_chain(user_45m_overweight):
    """[가이드 예시 2 통합] 45세 남성 BMR → TDEE."""
    bmr = calculate_bmr(
        weight_kg=user_45m_overweight.weight_kg,
        height_cm=user_45m_overweight.height_cm,
        age=user_45m_overweight.age,
        sex=user_45m_overweight.sex,
    )
    assert bmr == 1694.0  # 가이드

    tdee = calculate_tdee(bmr, daily_steps=8000)
    assert tdee == pytest.approx(2625.0, abs=1)  # 가이드
```

---

## 📊 가이드 예시 검증 (이 작업 완료 시)

```
입력 1: 50세 여성, 160cm, 68kg, 6,500보
  BMR = 10×68 + 6.25×160 − 5×50 − 161 = 1,269  ✅
  TDEE = 1,269 × 1.375 (가벼운 활동) = 1,744.875 ≈ 1,745  ✅

입력 2: 45세 남성, 175cm, 82kg, 8,000보
  BMR = 10×82 + 6.25×175 − 5×45 + 5 = 1,694  ✅
  TDEE = 1,694 × 1.550 (보통 활동) = 2,625.7 ≈ 2,625  ✅
```

---

## ✅ Definition of Done

- [ ] `src/algorithms/metabolism.py` — BMR + 활동계수 + TDEE 함수
- [ ] 모듈 상수 (`BMR_*`, `ACTIVITY_FACTORS`) 정의 + docstring
- [ ] 모든 함수 Google-style docstring + Examples
- [ ] 모든 함수 타입 힌트
- [ ] `tests/unit/algorithms/test_metabolism.py` — 25+ 테스트
- [ ] 가이드 예시 1 (50대 여성 BMR=1269, TDEE=1745) 통합 테스트
- [ ] 가이드 예시 2 (45세 남성 BMR=1694, TDEE=2625) 통합 테스트
- [ ] 경계값 테스트 모두 (4999, 5000, 7499, 7500, 9999, 10000, 12499, 12500)
- [ ] `mypy src/algorithms/metabolism.py --strict` 통과
- [ ] `pytest tests/unit/algorithms/test_metabolism.py -v` 통과
- [ ] 코드 커버리지 ≥ 95% (해당 모듈)

---

## 💡 구현 팁

### activity_factor 매칭 로직

```python
def get_activity_factor(daily_steps: int) -> float:
    """..."""
    if daily_steps < 0:
        raise ValueError(f"daily_steps must be non-negative, got {daily_steps}")

    for upper_bound, factor in ACTIVITY_FACTORS:
        if daily_steps < upper_bound:
            return factor
    return ACTIVITY_FACTOR_MAX
```

→ 정렬된 리스트 순회로 첫 매칭에서 반환. `if/elif/elif/...` 보다 유지보수 좋음.

### BMR 정확도 검증

가이드 예시는 **정수 결과**:
- 50대 여성 → 정확히 1269.0
- 45세 남성 → 정확히 1694.0

따라서 테스트는 `pytest.approx` 없이 정확 비교 가능:
```python
assert calculate_bmr(68.0, 160, 50, "female") == 1269.0
```

### sex 검증 — Literal vs Enum

```python
# 옵션 A: Literal (간단)
def calculate_bmr(..., sex: Literal["male", "female"]) -> float:
    ...

# 옵션 B: enum (확장 가능)
class Sex(StrEnum):
    MALE = "male"
    FEMALE = "female"
```

> 권장: **Literal** (간단하고 Pydantic v2와 자연스럽게 호환). 단, 미래 확장(예: "other") 가능성 있으면 enum.

### Final 타입 힌트

```python
from typing import Final

BMR_WEIGHT_COEF: Final[float] = 10.0
```

→ mypy가 재할당을 에러로 감지. 상수 명확화에 도움.

---

## 🚫 이 작업에서 하지 말 것

- ❌ Katch-McArdle 공식 (Phase 3 고도화)
- ❌ Cunningham 공식 (Phase 3)
- ❌ 한국인 보정 계수 (Phase 3)
- ❌ DB에 BMR/TDEE 저장 (Phase 1 후반)

---

## 🔗 관련 문서

- [`/CLAUDE.md`](../../CLAUDE.md)
- [`/backend/CLAUDE.md`](../../backend/CLAUDE.md)
- [`/docs/Nutrition-docs/07-core-algorithm.md §3.6, §3.7`](../07-core-algorithm.md)
- 이전 작업: [`02-v2-v3-v4-algorithms.md`](./02-v2-v3-v4-algorithms.md)
- 다음 작업: [`04-weight-prediction-7step.md`](./04-weight-prediction-7step.md)
