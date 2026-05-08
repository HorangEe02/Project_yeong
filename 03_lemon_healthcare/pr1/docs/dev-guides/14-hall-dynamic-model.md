# dev-guides/14 — Hall 동적 모델 (체중 예측 v2)

> **Phase**: 3 | **선행 작업**: [`04-weight-prediction-7step.md`](./04-weight-prediction-7step.md) | **예상 소요**: 5~6시간

---

## 🎯 작업 목표

기존 7-step 단순 예측을 NIH의 Hall 동적 모델로 고도화한다. 체중 변화에 따른 BMR 자기조정, 적응적 열역학, 신체구성(FFM/FM) 분리 추적으로 장기(3개월+) 예측 정확도 향상.

---

## 📋 산출물

```
backend/
├── src/prediction/
│   ├── hall.py                  # Hall 동적 모델 (메인)
│   ├── body_composition.py     # FFM/FM 추정
│   └── selector.py              # 7-step / Hall 자동 선택
├── tests/
│   ├── unit/prediction/
│   │   ├── test_hall.py
│   │   ├── test_body_composition.py
│   │   └── test_selector.py
│   ├── integration/prediction/
│   │   └── test_hall_vs_7step.py    # 두 모델 결과 비교
│   └── e2e/
│       └── test_hall_long_term.py   # 6개월 시뮬레이션
```

---

## 📐 알고리즘 명세

> 🔍 **출처**: [docs/07-core-algorithm.md §6.1](../07-core-algorithm.md), Hall et al. (2011) "Quantification of the effect of energy imbalance on bodyweight."

### Hall 모델의 핵심 아이디어

7-step 단순 모델의 한계:
- BMR을 시작 시점에서 1회 계산 (실제로는 체중 변화에 따라 변화)
- 모든 변화를 지방으로 가정 (실제로는 FFM도 함께 변화)
- 30일 이상 장기 예측 시 오차 누적

Hall 모델 개선:
- **일별 시뮬레이션**: 매일 체중·BMR·TDEE 재계산
- **신체구성 분리**: FFM(제지방) + FM(지방) 별도 추적
- **적응적 열역학**: 감량 시 BMR 적응 반영 (대사 적응)

### 핵심 수식

```
일일 시뮬레이션 (D=0~N):
  1. FFM_D, FM_D 로부터 RMR 계산:
     RMR = γ_F × FM + γ_L × FFM
     γ_F = 13 (지방의 RMR 기여)
     γ_L = 92 (제지방의 RMR 기여)

  2. PAEE (활동 에너지) = (TDEE - RMR - TEF)
     TEF = 0.10 × intake (식이성 발열)

  3. 에너지 수지:
     ΔE = intake - TDEE_D

  4. FFM·FM 변화 (Forbes 방정식):
     p = C / (C + FM_D)         # 제지방 변화 비율
     C = 10.4 (Forbes 상수)
     ΔFM = ΔE / 9500 × (1 - p)
     ΔFFM = ΔE / 7600 × p

  5. 다음날 갱신:
     FM_{D+1} = FM_D + ΔFM
     FFM_{D+1} = FFM_D + ΔFFM
     Weight_{D+1} = FFM_{D+1} + FM_{D+1}
```

### 신체구성 초기화

체지방률을 모르는 경우 BMI·성별·나이로 추정 (Deurenberg 공식):

```
체지방률 (%) = 1.20 × BMI + 0.23 × age − 10.8 × sex_factor − 5.4
  (sex_factor: 남성 1, 여성 0)

FM = weight × (BFP / 100)
FFM = weight − FM
```

---

## 🔧 구현 명세

### 1. `src/prediction/body_composition.py`

```python
"""신체구성 추정 (FFM/FM)."""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict, Field


# Deurenberg 공식 계수
DEURENBERG_BMI_COEF: Final[float] = 1.20
DEURENBERG_AGE_COEF: Final[float] = 0.23
DEURENBERG_SEX_COEF: Final[float] = 10.8
DEURENBERG_CONST: Final[float] = 5.4


class BodyComposition(BaseModel):
    """신체구성 (Fat Mass + Fat Free Mass).

    Attributes:
        weight_kg: 총 체중.
        fat_mass_kg: 지방량.
        fat_free_mass_kg: 제지방량 (근육·뼈·장기·수분 등).
        body_fat_pct: 체지방률 (%).
    """

    model_config = ConfigDict(frozen=True)

    weight_kg: float = Field(..., gt=0)
    fat_mass_kg: float = Field(..., ge=0)
    fat_free_mass_kg: float = Field(..., ge=0)
    body_fat_pct: float = Field(..., ge=0, le=70)


def estimate_body_fat_percentage(
    bmi: float,
    age: int,
    sex: str,
) -> float:
    """Deurenberg 공식으로 체지방률 추정.

    Args:
        bmi: 체질량지수 (kg/m²).
        age: 만 나이.
        sex: "male" | "female".

    Returns:
        체지방률 (%, 5~50 범위로 클램핑).

    Examples:
        >>> estimate_body_fat_percentage(bmi=26.5, age=50, sex="female")
        37.16
        >>> estimate_body_fat_percentage(bmi=26.7, age=45, sex="male")
        25.18

    Reference:
        Deurenberg P, et al. (1991). Br J Nutr 65: 105-114.
    """
    sex_factor = 1.0 if sex == "male" else 0.0
    bfp = (
        DEURENBERG_BMI_COEF * bmi
        + DEURENBERG_AGE_COEF * age
        - DEURENBERG_SEX_COEF * sex_factor
        - DEURENBERG_CONST
    )
    # 안전 클램핑
    return round(max(5.0, min(50.0, bfp)), 2)


def estimate_initial_composition(
    weight_kg: float,
    height_cm: float,
    age: int,
    sex: str,
    measured_bfp: float | None = None,
) -> BodyComposition:
    """초기 신체구성 추정.

    Args:
        weight_kg: 체중.
        height_cm: 키.
        age: 만 나이.
        sex: 성별.
        measured_bfp: 측정된 체지방률 (있으면 우선).

    Returns:
        BodyComposition.

    Examples:
        >>> bc = estimate_initial_composition(
        ...     weight_kg=68, height_cm=160, age=50, sex="female"
        ... )
        >>> bc.body_fat_pct
        37.16
        >>> round(bc.fat_mass_kg, 1)
        25.3
    """
    bmi = weight_kg / ((height_cm / 100) ** 2)
    bfp = (
        measured_bfp
        if measured_bfp is not None
        else estimate_body_fat_percentage(bmi, age, sex)
    )
    fat_mass = weight_kg * (bfp / 100)
    ffm = weight_kg - fat_mass
    return BodyComposition(
        weight_kg=weight_kg,
        fat_mass_kg=round(fat_mass, 2),
        fat_free_mass_kg=round(ffm, 2),
        body_fat_pct=bfp,
    )
```

### 2. `src/prediction/hall.py`

```python
"""Hall 동적 체중 예측 모델."""

from __future__ import annotations

import logging
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from src.algorithms.metabolism import calculate_tdee
from src.prediction.body_composition import (
    BodyComposition,
    estimate_initial_composition,
)


logger = logging.getLogger(__name__)


# Hall 모델 상수
GAMMA_F: Final[float] = 13.0   # 지방 RMR 기여 (kcal/kg/day)
GAMMA_L: Final[float] = 92.0   # FFM RMR 기여 (kcal/kg/day)
KCAL_PER_KG_FAT: Final[float] = 9500.0  # 체지방 1kg 에너지 (Hall 보정값)
KCAL_PER_KG_FFM: Final[float] = 7600.0  # FFM 1kg 에너지
FORBES_C: Final[float] = 10.4  # Forbes 상수
TEF_RATIO: Final[float] = 0.10  # 식이성 발열 (intake의 10%)


class DailyState(BaseModel):
    """일별 시뮬레이션 상태.

    Attributes:
        day: 시작일로부터 N일째.
        composition: 현재 신체구성.
        rmr_kcal: 휴식 대사량.
        tdee_kcal: 총 에너지 소비.
        intake_kcal: 섭취량.
        energy_balance_kcal: 일일 수지.
    """

    model_config = ConfigDict(frozen=True)

    day: int
    composition: BodyComposition
    rmr_kcal: float
    tdee_kcal: float
    intake_kcal: float
    energy_balance_kcal: float


class HallPredictionResult(BaseModel):
    """Hall 모델 예측 결과.

    Attributes:
        starting_weight: 시작 체중.
        initial_composition: 초기 신체구성.
        daily_states: 일별 상태 (선택, 메모리 절약을 위해 N+1 일치 저장).
        predicted_weight: 최종 예측 체중.
        predicted_fm: 최종 지방량.
        predicted_ffm: 최종 제지방량.
        weight_change: 변화량.
        period_days: 예측 기간.
    """

    model_config = ConfigDict(frozen=True)

    starting_weight: float
    initial_composition: BodyComposition
    daily_states: list[DailyState] = Field(default_factory=list)
    predicted_weight: float
    predicted_fm: float
    predicted_ffm: float
    weight_change: float
    period_days: int


def calculate_rmr_hall(composition: BodyComposition) -> float:
    """신체구성 기반 RMR 계산 (Hall 공식).

    Args:
        composition: 현재 신체구성.

    Returns:
        RMR (kcal/일).

    Examples:
        >>> bc = BodyComposition(
        ...     weight_kg=68, fat_mass_kg=25, fat_free_mass_kg=43,
        ...     body_fat_pct=37,
        ... )
        >>> round(calculate_rmr_hall(bc))
        4281
    """
    rmr = GAMMA_F * composition.fat_mass_kg + GAMMA_L * composition.fat_free_mass_kg
    return round(rmr, 1)


def step_one_day(
    composition: BodyComposition,
    intake_kcal: float,
    daily_steps: int,
    age: int,
    sex: str,
    height_cm: float,
) -> tuple[BodyComposition, DailyState]:
    """하루 시뮬레이션 진행.

    Args:
        composition: 시작 신체구성.
        intake_kcal: 일일 섭취 칼로리.
        daily_steps: 일일 걸음수.
        age: 나이.
        sex: 성별.
        height_cm: 키 (TDEE 계산용).

    Returns:
        (다음날 신체구성, 일별 상태).
    """
    # 1. RMR 계산 (Hall)
    rmr = calculate_rmr_hall(composition)

    # 2. TDEE는 기존 metabolism 모듈 활용 (활동계수 곱)
    # Mifflin-St Jeor BMR 대신 Hall RMR 사용
    from src.algorithms.metabolism import get_activity_factor
    activity_factor = get_activity_factor(daily_steps)
    paee = rmr * (activity_factor - 1.0)  # PAEE = (factor-1) × RMR

    # 3. TEF (식이성 발열)
    tef = TEF_RATIO * intake_kcal

    # 4. TDEE
    tdee = rmr + paee + tef

    # 5. 에너지 수지
    energy_balance = intake_kcal - tdee

    # 6. Forbes 방정식 (FFM 변화 비율)
    p = FORBES_C / (FORBES_C + composition.fat_mass_kg)

    # 7. 신체구성 변화
    delta_fm = (energy_balance * (1 - p)) / KCAL_PER_KG_FAT
    delta_ffm = (energy_balance * p) / KCAL_PER_KG_FFM

    new_fm = max(0.0, composition.fat_mass_kg + delta_fm)
    new_ffm = max(0.0, composition.fat_free_mass_kg + delta_ffm)
    new_weight = new_fm + new_ffm
    new_bfp = (new_fm / new_weight) * 100 if new_weight > 0 else 0

    new_composition = BodyComposition(
        weight_kg=round(new_weight, 3),
        fat_mass_kg=round(new_fm, 3),
        fat_free_mass_kg=round(new_ffm, 3),
        body_fat_pct=round(new_bfp, 2),
    )

    state = DailyState(
        day=0,  # 호출자가 갱신
        composition=composition,
        rmr_kcal=rmr,
        tdee_kcal=round(tdee, 1),
        intake_kcal=intake_kcal,
        energy_balance_kcal=round(energy_balance, 1),
    )

    return new_composition, state


def predict_with_hall(
    weight_kg: float,
    height_cm: float,
    age: int,
    sex: str,
    daily_steps: int,
    daily_intake_kcal: float,
    n_days: int,
    measured_bfp: float | None = None,
    save_daily_states: bool = False,
) -> HallPredictionResult:
    """Hall 동적 모델로 N일 후 체중 예측.

    Args:
        weight_kg: 시작 체중.
        height_cm: 키.
        age: 나이.
        sex: 성별.
        daily_steps: 일일 걸음수 (시나리오 동안 일정 가정).
        daily_intake_kcal: 일일 섭취 칼로리.
        n_days: 예측 기간 (1~365).
        measured_bfp: 측정된 체지방률.
        save_daily_states: 일별 상태 저장 여부 (시각화용).

    Returns:
        HallPredictionResult.

    Raises:
        ValueError: 입력값이 비정상인 경우.

    Examples:
        >>> result = predict_with_hall(
        ...     weight_kg=68, height_cm=160, age=50, sex="female",
        ...     daily_steps=6500, daily_intake_kcal=1500, n_days=30,
        ... )
        >>> result.predicted_weight  # 7-step과 다른 값
        67.43
    """
    if not 1 <= n_days <= 365:
        raise ValueError(f"n_days must be 1-365, got {n_days}")
    if daily_intake_kcal < 0:
        raise ValueError(f"daily_intake_kcal must be non-negative")

    # 초기 신체구성
    composition = estimate_initial_composition(
        weight_kg=weight_kg,
        height_cm=height_cm,
        age=age,
        sex=sex,
        measured_bfp=measured_bfp,
    )
    initial = composition

    # 일별 시뮬레이션
    daily_states: list[DailyState] = []
    for d in range(n_days):
        composition, state = step_one_day(
            composition=composition,
            intake_kcal=daily_intake_kcal,
            daily_steps=daily_steps,
            age=age,
            sex=sex,
            height_cm=height_cm,
        )
        if save_daily_states:
            daily_states.append(state.model_copy(update={"day": d}))

    return HallPredictionResult(
        starting_weight=weight_kg,
        initial_composition=initial,
        daily_states=daily_states,
        predicted_weight=composition.weight_kg,
        predicted_fm=composition.fat_mass_kg,
        predicted_ffm=composition.fat_free_mass_kg,
        weight_change=round(composition.weight_kg - weight_kg, 2),
        period_days=n_days,
    )
```

### 3. `src/prediction/selector.py`

```python
"""7-step / Hall 모델 자동 선택."""

from __future__ import annotations

import logging
from typing import Final

from src.prediction.hall import HallPredictionResult, predict_with_hall
from src.prediction.weight import WeightPrediction, predict_weight_n_days


logger = logging.getLogger(__name__)


SHORT_TERM_THRESHOLD_DAYS: Final[int] = 14
"""이 기간 이하면 7-step (단순 모델) 사용."""


def predict_weight_adaptive(
    weight_kg: float,
    height_cm: float,
    age: int,
    sex: str,
    daily_steps: int,
    daily_intake_kcal: float,
    n_days: int,
    use_hall: bool | None = None,
    measured_bfp: float | None = None,
) -> dict:
    """기간에 따라 적절한 모델 선택.

    Args:
        n_days: 예측 기간.
        use_hall: 명시적 선택. None이면 자동 (14일↑→Hall, 이하→7-step).
        measured_bfp: 측정 체지방률 (Hall에서 사용).

    Returns:
        {model: "hall" | "7step", result: ..., predicted_weight: float}

    예측 정확도:
        - 7-step: 단기 (≤ 14일) 적합, 빠름, 단순
        - Hall: 장기 (> 14일) 적합, 일별 적응, 신체구성 분리
    """
    if use_hall is None:
        use_hall = n_days > SHORT_TERM_THRESHOLD_DAYS

    if use_hall:
        result = predict_with_hall(
            weight_kg=weight_kg, height_cm=height_cm,
            age=age, sex=sex,
            daily_steps=daily_steps,
            daily_intake_kcal=daily_intake_kcal,
            n_days=n_days,
            measured_bfp=measured_bfp,
        )
        logger.info("Used Hall model for n_days=%d", n_days)
        return {
            "model": "hall",
            "predicted_weight": result.predicted_weight,
            "result": result,
        }
    else:
        result = predict_weight_n_days(
            weight_kg=weight_kg, height_cm=height_cm,
            age=age, sex=sex,
            daily_steps=daily_steps,
            daily_intake_kcal=daily_intake_kcal,
            n_days=n_days,
        )
        logger.info("Used 7-step model for n_days=%d", n_days)
        return {
            "model": "7step",
            "predicted_weight": result.predicted_weight,
            "result": result,
        }
```

---

## 🧪 테스트 (4-Tier)

### Tier 1: 단위 테스트

#### `test_body_composition.py`

| 테스트 | 입력 | 기대값 |
|-------|------|-------|
| `test_deurenberg_50f_obese1` | bmi=26.5, age=50, female | ≈37.16 |
| `test_deurenberg_45m_overweight` | bmi=26.7, age=45, male | ≈25.18 |
| `test_estimate_uses_measured_bfp` | measured=30.0 | 추정 무시, 30.0 사용 |
| `test_clamping_lower` | 매우 마른 사람 | ≥ 5.0 |
| `test_clamping_upper` | 비현실적 비만 | ≤ 50.0 |
| `test_fm_ffm_sum_equals_weight` | 모든 케이스 | FM + FFM = weight |

#### `test_hall.py`

| 테스트 | 검증 |
|-------|------|
| `test_calculate_rmr_hall_basic` | RMR 공식 검증 |
| `test_step_one_day_no_balance` | 섭취 = TDEE → 신체구성 거의 불변 |
| `test_step_one_day_deficit_loses_fm` | 적자 → FM 감소 우세 |
| `test_step_one_day_surplus_gains_fm` | 흑자 → FM 증가 우세 |
| `test_forbes_higher_fm_more_fat_change` | FM 높을수록 변화도 FM에 집중 |
| `test_predict_50f_30days` | 50f 30일 → 67.4kg 근처 |
| `test_predict_long_term_60days` | 60일 → 7-step과 차이 발생 |
| `test_n_days_too_long_raises` | n_days=400 → ValueError |
| `test_n_days_zero_raises` | n_days=0 → ValueError |

### Tier 2: 통합 테스트 (7-step vs Hall 비교)

```python
"""7-step과 Hall 모델 결과 비교."""

import pytest

from src.prediction.weight import predict_weight_n_days
from src.prediction.hall import predict_with_hall


class TestModelComparison:
    """단기·장기 시뮬레이션에서 두 모델 비교."""

    @pytest.mark.parametrize("days", [7, 14, 30, 60, 90])
    def test_models_diverge_with_time(self, days):
        """기간이 길수록 두 모델 차이가 커진다."""
        kwargs = {
            "weight_kg": 68, "height_cm": 160, "age": 50, "sex": "female",
            "daily_steps": 6500, "daily_intake_kcal": 1500, "n_days": days,
        }
        seven = predict_weight_n_days(**kwargs)
        hall = predict_with_hall(**kwargs)

        diff = abs(seven.predicted_weight - hall.predicted_weight)
        assert diff < days * 0.05, f"Excessive divergence at day {days}: {diff}"

    def test_hall_more_conservative_for_loss(self):
        """감량 시 Hall이 7-step보다 보수적."""
        # 대사 적응을 반영하므로 같은 적자에서도 감소량이 작음
        kwargs = {
            "weight_kg": 68, "height_cm": 160, "age": 50, "sex": "female",
            "daily_steps": 6500, "daily_intake_kcal": 1500, "n_days": 90,
        }
        seven = predict_weight_n_days(**kwargs)
        hall = predict_with_hall(**kwargs)

        # Hall이 감량을 덜 예측 (대사 적응 반영)
        seven_loss = kwargs["weight_kg"] - seven.predicted_weight
        hall_loss = kwargs["weight_kg"] - hall.predicted_weight
        assert hall_loss < seven_loss
```

### Tier 3: 장기 시뮬레이션 E2E

```python
"""6개월 장기 시뮬레이션."""

@pytest.mark.e2e
class TestHallLongTerm:
    def test_6month_loss_plateau(self):
        """6개월 시뮬레이션에서 정체기(plateau) 관찰."""
        result = predict_with_hall(
            weight_kg=80, height_cm=170, age=40, sex="male",
            daily_steps=8000, daily_intake_kcal=2000,
            n_days=180, save_daily_states=True,
        )

        # 첫 30일 손실량 vs 마지막 30일 손실량
        first_30 = result.daily_states[29].composition.weight_kg \
                   - result.daily_states[0].composition.weight_kg
        last_30 = result.daily_states[179].composition.weight_kg \
                  - result.daily_states[150].composition.weight_kg

        # 후반기 변화량 < 초반기 (대사 적응)
        assert abs(last_30) < abs(first_30)

    def test_steady_state_no_change(self):
        """유지 칼로리에서는 거의 변화 없음."""
        # 사용자의 추정 TDEE와 같은 섭취 → 변화량 < 0.5kg
        result = predict_with_hall(
            weight_kg=68, height_cm=160, age=50, sex="female",
            daily_steps=6500, daily_intake_kcal=1745,  # 추정 TDEE
            n_days=90,
        )
        assert abs(result.weight_change) < 0.5
```

### Tier 4: 성능 테스트

```python
@pytest.mark.performance
class TestHallPerformance:
    def test_30day_under_100ms(self):
        """30일 시뮬레이션 < 100ms."""
        start = time.perf_counter()
        predict_with_hall(
            weight_kg=68, height_cm=160, age=50, sex="female",
            daily_steps=6500, daily_intake_kcal=1500, n_days=30,
        )
        elapsed = time.perf_counter() - start
        assert elapsed < 0.1

    def test_365day_under_1s(self):
        """1년 시뮬레이션 < 1초."""
        start = time.perf_counter()
        predict_with_hall(
            weight_kg=68, height_cm=160, age=50, sex="female",
            daily_steps=6500, daily_intake_kcal=1500, n_days=365,
        )
        elapsed = time.perf_counter() - start
        assert elapsed < 1.0
```

---

## ✅ Definition of Done

- [ ] `src/prediction/body_composition.py` — Deurenberg 추정 + 모델
- [ ] `src/prediction/hall.py` — calculate_rmr_hall, step_one_day, predict_with_hall
- [ ] `src/prediction/selector.py` — 자동 모델 선택
- [ ] 모든 함수 Google-style docstring + Examples
- [ ] 모든 함수 타입 힌트
- [ ] 단위 테스트 (Body Composition + Hall) 25+
- [ ] 통합 테스트 (7-step vs Hall 비교)
- [ ] E2E 테스트 (6개월 시뮬레이션, 정체기 관찰)
- [ ] 성능 테스트 (30일 < 100ms, 365일 < 1s)
- [ ] **수식 정확성 검증** — Hall 논문의 케이스 재현
- [ ] `mypy src/prediction --strict` 통과
- [ ] 기존 7-step 테스트 회귀 없음

---

## 💡 구현 팁

### Hall 모델 단순화 결정

학생 프로젝트에서는 **단순화된 Hall 모델** 만 구현. 풀 모델의 다음은 생략:
- 단백질·탄수화물·지방 섭취 별도 추적 (3-개체 모델)
- 글리코겐 변화 (단기 변동의 큰 부분이지만 ±2kg 수준)
- 운동 강도 vs PAEE 변환 정확화

→ **목표**: 30~90일 범위에서 7-step보다 5~15% 정확도 향상.

### 일별 시뮬레이션 메모리

365일 모든 상태 저장하면 365 × ~100 bytes = 36KB. 큰 문제 없음. 하지만 **`save_daily_states=False`** 가 기본값이고, 시각화 필요 시만 True.

### NumPy 활용 (선택)

벡터화 시뮬레이션이 필요하면:

```python
import numpy as np

def predict_hall_numpy(...):
    fm = np.zeros(n_days + 1)
    ffm = np.zeros(n_days + 1)
    fm[0], ffm[0] = initial_fm, initial_ffm
    for d in range(n_days):
        rmr = GAMMA_F * fm[d] + GAMMA_L * ffm[d]
        # ... 벡터화
```

→ 365일 시뮬레이션 < 5ms. 하지만 학생 프로젝트엔 일반 Python 충분.

### 사용자에게 보여주는 값

UI에서는:
- ✅ 예측 체중 (소수점 1자리)
- ✅ 시작 대비 변화량
- ⚠️ FFM/FM 분리는 **선택적** 표시 (어려운 개념)
- ⚠️ 정체기 그래프는 시각적 흥미로움

---

## 🚫 이 작업에서 하지 말 것

- ❌ 7-step 모델 제거 (단기 예측에는 여전히 유용)
- ❌ 운동 종류별 PAEE 세분화 (Phase 4+)
- ❌ ML 적응형 보정 (Phase 4+)
- ❌ 사용자 측정 BFP 입력 UI (백엔드만, 모바일은 나중)

---

## 🔗 관련 문서

- [`/docs/07-core-algorithm.md §6.1`](../07-core-algorithm.md)
- [`/backend/CLAUDE.md`](../../backend/CLAUDE.md)
- 이전: [`13-mobile-dashboard.md`](./13-mobile-dashboard.md)
- 다음: [`15-goal-based-analysis.md`](./15-goal-based-analysis.md)
