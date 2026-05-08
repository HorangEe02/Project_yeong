# dev-guides/04 — 7-step 체중 예측

> **Phase**: 1 | **선행 작업**: [`03-bmr-tdee.md`](./03-bmr-tdee.md) | **예상 소요**: 2~3시간

---

## 🎯 작업 목표

회사 가이드의 7단계 체중 예측 알고리즘을 구현하고, 1주/1개월/3개월 일괄 예측 함수를 제공한다. 가이드 PPTX의 두 계산 예시를 단위 테스트로 검증한다.

---

## 📋 산출물

```
backend/
├── src/
│   ├── models/schemas/
│   │   └── prediction.py       # WeightPrediction, WeightPeriodPredictions
│   └── prediction/
│       ├── __init__.py
│       └── weight.py           # 7-step 알고리즘
└── tests/unit/prediction/
    ├── __init__.py
    └── test_weight.py
```

---

## 📐 알고리즘 명세

> 🔍 **출처**: [docs/07-core-algorithm.md §3.8](../07-core-algorithm.md)

### 7단계 흐름

```
Step 1. BMR 계산           (Mifflin-St Jeor — 이전 작업)
Step 2. TDEE = BMR × 활동계수 (이전 작업)
Step 3. 일일 수지 = 섭취칼로리 − TDEE
Step 4. N일 누적 = 일일 수지 × N
Step 5. 이론 변화 = 누적 ÷ 7,700  (지방 1kg ≈ 7,700 kcal)
Step 6. 현실 보정:
        감량 (수지 < 0) → ×0.85
        증량 (수지 > 0) → ×0.95
Step 7. 예측 체중 = 시작 체중 + 보정 변화
```

### 핵심 상수

```
KCAL_PER_KG_FAT = 7,700
LOSS_CORRECTION = 0.85   (감량 보정)
GAIN_CORRECTION = 0.95   (증량 보정)

표준 예측 기간: 7일 (1주), 30일 (1개월), 90일 (3개월)
```

---

## 🔧 구현 명세

### 1. `src/models/schemas/prediction.py`

```python
"""체중 예측 결과 스키마."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class WeightPrediction(BaseModel):
    """N일 후 체중 예측 결과 (단일 기간).

    Attributes:
        period_days: 예측 기간 (일).
        bmr: 기초대사량 (kcal/일).
        tdee: 총 에너지 소비량 (kcal/일).
        daily_balance: 일일 에너지 수지 (kcal/일, 음수면 적자).
        cumulative_balance: N일 누적 수지 (kcal).
        theoretical_change: 이론 체중 변화 (kg, 보정 전).
        corrected_change: 보정된 체중 변화 (kg).
        starting_weight: 시작 체중 (kg).
        predicted_weight: 예측 체중 (kg).

    Reference:
        docs/07-core-algorithm.md §3.8
    """

    model_config = ConfigDict(frozen=True)

    period_days: int = Field(..., ge=1, le=365)
    bmr: float
    tdee: float
    daily_balance: float
    cumulative_balance: float
    theoretical_change: float
    corrected_change: float
    starting_weight: float
    predicted_weight: float


class WeightPeriodPredictions(BaseModel):
    """표준 3 기간(1주/1개월/3개월) 일괄 예측.

    Attributes:
        week_1: 1주(7일) 후 예측.
        month_1: 1개월(30일) 후 예측.
        month_3: 3개월(90일) 후 예측.
    """

    model_config = ConfigDict(frozen=True)

    week_1: WeightPrediction
    month_1: WeightPrediction
    month_3: WeightPrediction
```

### 2. `src/prediction/weight.py`

```python
"""7-step 체중 예측 알고리즘.

회사 가이드의 7단계 산출식을 구현한다. 지방 1kg 당 7,700 kcal 환산을 기준으로
N일 후 체중을 예측하며, 감량/증량 시 현실 보정 계수를 적용한다.

Reference:
    docs/07-core-algorithm.md §3.8
"""

from __future__ import annotations

from typing import Final

from src.algorithms.metabolism import calculate_bmr, calculate_tdee
from src.models.schemas.prediction import (
    WeightPeriodPredictions,
    WeightPrediction,
)


KCAL_PER_KG_FAT: Final[float] = 7700.0
"""체지방 1kg에 해당하는 에너지 (kcal)."""

LOSS_CORRECTION: Final[float] = 0.85
"""감량 시 현실 보정 계수 (체수분 손실·대사 적응 등 반영)."""

GAIN_CORRECTION: Final[float] = 0.95
"""증량 시 현실 보정 계수."""

STANDARD_PERIODS: Final[tuple[int, int, int]] = (7, 30, 90)
"""표준 예측 기간 (일): 1주, 1개월, 3개월."""
```

#### 구현해야 할 함수

```python
def predict_weight_n_days(
    weight_kg: float,
    height_cm: float,
    age: int,
    sex: str,
    daily_steps: int,
    daily_intake_kcal: float,
    n_days: int,
) -> WeightPrediction:
    """N일 후 체중을 7-step 알고리즘으로 예측한다.

    Args:
        weight_kg: 시작 체중 (kg).
        height_cm: 키 (cm).
        age: 만 나이.
        sex: "male" | "female".
        daily_steps: 일일 평균 걸음수.
        daily_intake_kcal: 일일 평균 섭취 칼로리.
        n_days: 예측 기간 (일, 1~365).

    Returns:
        WeightPrediction — 7단계 중간 결과 + 최종 체중.

    Raises:
        ValueError: 입력값이 허용 범위를 벗어난 경우.

    Examples:
        >>> pred = predict_weight_n_days(
        ...     weight_kg=68.0, height_cm=160, age=50, sex="female",
        ...     daily_steps=6500, daily_intake_kcal=1500, n_days=30
        ... )
        >>> pred.predicted_weight
        67.19
    """
    ...


def predict_weight_periods(
    weight_kg: float,
    height_cm: float,
    age: int,
    sex: str,
    daily_steps: int,
    daily_intake_kcal: float,
) -> WeightPeriodPredictions:
    """1주/1개월/3개월 일괄 예측.

    Args:
        (predict_weight_n_days와 동일, n_days 제외)

    Returns:
        WeightPeriodPredictions — 3 기간 예측 묶음.

    Examples:
        >>> preds = predict_weight_periods(
        ...     weight_kg=68.0, height_cm=160, age=50, sex="female",
        ...     daily_steps=6500, daily_intake_kcal=1500
        ... )
        >>> preds.month_1.predicted_weight
        67.19
    """
    ...
```

#### 구현 가이드

```python
def predict_weight_n_days(...) -> WeightPrediction:
    if not 1 <= n_days <= 365:
        raise ValueError(f"n_days must be 1-365, got {n_days}")
    if daily_intake_kcal < 0:
        raise ValueError(f"daily_intake_kcal must be non-negative, got {daily_intake_kcal}")

    # Step 1: BMR
    bmr = calculate_bmr(weight_kg, height_cm, age, sex)

    # Step 2: TDEE
    tdee = calculate_tdee(bmr, daily_steps)

    # Step 3: 일일 수지
    daily_balance = daily_intake_kcal - tdee

    # Step 4: N일 누적
    cumulative = daily_balance * n_days

    # Step 5: 이론 변화 (kg)
    theoretical = cumulative / KCAL_PER_KG_FAT

    # Step 6: 현실 보정
    if daily_balance < 0:
        corrected = theoretical * LOSS_CORRECTION
    elif daily_balance > 0:
        corrected = theoretical * GAIN_CORRECTION
    else:
        corrected = 0.0

    # Step 7: 예측 체중
    predicted = weight_kg + corrected

    return WeightPrediction(
        period_days=n_days,
        bmr=bmr,
        tdee=tdee,
        daily_balance=round(daily_balance, 1),
        cumulative_balance=round(cumulative, 1),
        theoretical_change=round(theoretical, 3),
        corrected_change=round(corrected, 3),
        starting_weight=weight_kg,
        predicted_weight=round(predicted, 2),
    )
```

---

## 🧪 단위 테스트

### `tests/unit/prediction/test_weight.py`

#### 가이드 예시 1 — 50대 여성 (감량)

```python
def test_predict_50f_30days_guide_example():
    """[가이드 예시 1]
    50세 여성, 키 160cm, 시작 68kg, 6,500보, 1,500 kcal, 30일.
    
    예상 단계:
      BMR = 1,269
      TDEE = 1,269 × 1.375 = 1,745
      일일 수지 = 1,500 − 1,745 = −245
      30일 누적 = −7,350
      이론 변화 = −7,350 ÷ 7,700 = −0.955
      보정 변화 = −0.955 × 0.85 = −0.811
      예측 체중 = 68.0 − 0.81 = 67.19
    """
    pred = predict_weight_n_days(
        weight_kg=68.0, height_cm=160, age=50, sex="female",
        daily_steps=6500, daily_intake_kcal=1500, n_days=30,
    )
    assert pred.bmr == 1269.0
    assert pred.tdee == pytest.approx(1745.0, abs=0.5)
    assert pred.daily_balance == pytest.approx(-245.0, abs=0.5)
    assert pred.cumulative_balance == pytest.approx(-7350.0, abs=2)
    assert pred.theoretical_change == pytest.approx(-0.955, abs=0.01)
    assert pred.corrected_change == pytest.approx(-0.811, abs=0.01)
    assert pred.predicted_weight == pytest.approx(67.19, abs=0.05)
```

#### 가이드 예시 2 — 45세 남성 (감량)

```python
def test_predict_45m_60days_guide_example():
    """[가이드 예시 2]
    45세 남성, 175cm, 82kg, 8,000보, 2,231 kcal (TDEE 85%), 60일.
    
    예상:
      BMR = 1,694
      TDEE = 1,694 × 1.55 = 2,625.7 ≈ 2,625
      권장 섭취 = 2,625 × 0.85 ≈ 2,231
      일일 수지 = 2,231 − 2,625 = −394
      60일 누적 = −23,640
      이론 변화 = −23,640 / 7,700 ≈ −3.07
      보정 변화 = −3.07 × 0.85 ≈ −2.61
      예측 체중 = 82.0 − 2.61 = 79.39
    """
    pred = predict_weight_n_days(
        weight_kg=82.0, height_cm=175, age=45, sex="male",
        daily_steps=8000, daily_intake_kcal=2231, n_days=60,
    )
    assert pred.bmr == 1694.0
    assert pred.tdee == pytest.approx(2625.0, abs=1)
    assert pred.daily_balance == pytest.approx(-394.0, abs=1)
    assert pred.predicted_weight == pytest.approx(79.39, abs=0.1)
```

#### 추가 테스트 케이스

| 테스트 | 입력 | 검증 |
|-------|------|------|
| `test_predict_maintenance_no_change` | 섭취 = TDEE | corrected_change ≈ 0 |
| `test_predict_gain_uses_095_correction` | 섭취 > TDEE 명확 | GAIN_CORRECTION 적용 확인 |
| `test_predict_loss_uses_085_correction` | 섭취 < TDEE 명확 | LOSS_CORRECTION 적용 확인 |
| `test_predict_zero_balance_no_correction` | 섭취 정확히 TDEE | corrected_change = 0 |
| `test_predict_invalid_n_days_raises` | n_days = 0 | ValueError |
| `test_predict_invalid_n_days_too_long_raises` | n_days = 366 | ValueError |
| `test_predict_invalid_intake_negative_raises` | daily_intake = -100 | ValueError |
| `test_predict_period_days_in_result` | n_days=15 | result.period_days == 15 |
| `test_periods_returns_3_predictions` | predict_weight_periods | week_1, month_1, month_3 모두 존재 |
| `test_periods_week_1_period_days_7` | week_1.period_days | 7 |
| `test_periods_month_1_period_days_30` | month_1.period_days | 30 |
| `test_periods_month_3_period_days_90` | month_3.period_days | 90 |

#### 회귀 방지 테스트

```python
def test_predict_50f_periods_consistent():
    """[가이드 예시] 50대 여성에 대해 1주/1개월/3개월 일괄 예측."""
    preds = predict_weight_periods(
        weight_kg=68.0, height_cm=160, age=50, sex="female",
        daily_steps=6500, daily_intake_kcal=1500,
    )
    # 시작 체중은 모두 동일
    assert preds.week_1.starting_weight == 68.0
    assert preds.month_1.starting_weight == 68.0
    assert preds.month_3.starting_weight == 68.0

    # 감량 시: 기간이 길수록 더 많이 감소
    assert preds.month_3.predicted_weight < preds.month_1.predicted_weight
    assert preds.month_1.predicted_weight < preds.week_1.predicted_weight

    # 1개월 결과는 가이드 예시와 일치
    assert preds.month_1.predicted_weight == pytest.approx(67.19, abs=0.05)
```

---

## 📊 가이드 예시 검증 (이 작업 완료 시)

```
예시 1: 50세 여성, 160cm, 68kg, 6,500보, 1,500 kcal/일, 30일
  → 예측 67.19 kg ✅

예시 2: 45세 남성, 175cm, 82kg, 8,000보, 2,231 kcal/일, 60일
  → 예측 79.39 kg ✅
```

---

## ✅ Definition of Done

- [ ] `src/models/schemas/prediction.py` — Pydantic 스키마 2개
- [ ] `src/prediction/weight.py` — 7-step 알고리즘
- [ ] `predict_weight_n_days` 단일 기간 예측
- [ ] `predict_weight_periods` 1주/1개월/3개월 일괄
- [ ] 모듈 상수 `KCAL_PER_KG_FAT`, `LOSS_CORRECTION`, `GAIN_CORRECTION` 정의
- [ ] 모든 함수 Google-style docstring + Examples
- [ ] 모든 함수 타입 힌트
- [ ] 가이드 예시 1 검증 (50대 여성, 30일, 67.19kg)
- [ ] 가이드 예시 2 검증 (45세 남성, 60일, 79.39kg)
- [ ] 입력 검증 테스트 (n_days 범위, intake 음수 등)
- [ ] 보정 계수 분기 테스트 (감량 / 유지 / 증량)
- [ ] `mypy src/prediction src/models/schemas/prediction.py --strict` 통과
- [ ] `pytest tests/unit/prediction -v` 통과
- [ ] 코드 커버리지 ≥ 95%

---

## 💡 구현 팁

### Pydantic v2 + 불변

```python
class WeightPrediction(BaseModel):
    model_config = ConfigDict(frozen=True)
    # frozen=True로 결과 객체 불변
    # 외부에서 .predicted_weight = 100 같은 변조 차단
```

### 부동소수점 누적 처리

```python
# corrected_change는 round(x, 3) — 이론 변화의 정밀도 보존
# predicted_weight는 round(x, 2) — UI 표시 정확도

# 가이드 예시는 손계산이라 약간의 오차 허용:
assert pred.predicted_weight == pytest.approx(67.19, abs=0.05)
```

### `STANDARD_PERIODS` 상수 활용

```python
def predict_weight_periods(...) -> WeightPeriodPredictions:
    week_pred, month_pred, month3_pred = (
        predict_weight_n_days(..., n_days=days)
        for days in STANDARD_PERIODS
    )
    return WeightPeriodPredictions(
        week_1=week_pred,
        month_1=month_pred,
        month_3=month3_pred,
    )
```

### 의존성 — 이전 작업과 결합

이 모듈은 `src.algorithms.metabolism` 의 `calculate_bmr`, `calculate_tdee` 를 호출.

```python
# 잘못된 예 — 직접 공식 재구현
bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + (5 if sex == "male" else -161)

# 올바른 예 — 기존 함수 호출 (DRY)
from src.algorithms.metabolism import calculate_bmr
bmr = calculate_bmr(weight_kg, height_cm, age, sex)
```

→ DRY 원칙. 한 곳에서만 공식 정의, 여러 곳에서 사용.

---

## 🚫 이 작업에서 하지 말 것

- ❌ Hall 동적 모델 (Phase 3 고도화)
- ❌ ML 적응형 보정 (Phase 3+)
- ❌ DB 저장 / API 라우터 (Phase 1 후반)
- ❌ 1주는 ×0.5 보정, 3개월은 Hall 같은 기간별 차별화 (Phase 3)

---

## 🔗 관련 문서

- [`/CLAUDE.md`](../../CLAUDE.md)
- [`/backend/CLAUDE.md`](../../backend/CLAUDE.md)
- [`/docs/07-core-algorithm.md §3.8`](../07-core-algorithm.md)
- 이전 작업: [`03-bmr-tdee.md`](./03-bmr-tdee.md)
- 다음 작업: [`05-kdris-lookup.md`](./05-kdris-lookup.md)
