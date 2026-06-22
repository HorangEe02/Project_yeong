# dev-guides/14 — Hall 동적 모델 (체중 예측 v2)

> **Phase**: 3 | **선행 작업**: [`04-weight-prediction-7step.md`](./04-weight-prediction-7step.md) | **예상 소요**: 5~6시간

> **구현 플랜**: [`../29-hall-lite-weight-prediction-implementation-plan.md`](../29-hall-lite-weight-prediction-implementation-plan.md)를 우선 기준으로 삼는다. 기존 `/api/v1/predictions/weight` 호환성을 위해 기본 route 동작은 7-step fallback으로 유지한다.

---

## 🎯 작업 목표

기존 7-step 단순 예측을 NIH/NIDDK Hall 모델을 참고한 **Hall-lite 동적 시뮬레이터**로 고도화한다. 체중 변화에 따른 RMR/TDEE 재계산, 적응적 열역학, 신체구성(FFM/FM) 분리 추적으로 장기(3개월+) 예측의 구조적 한계를 보완한다.

---

## 📋 산출물

```
backend/
├── src/prediction/
│   ├── hall.py                  # Hall-lite 동적 모델 (메인)
│   ├── body_composition.py     # FFM/FM 추정
│   └── selector.py              # 7-step / Hall-lite 선택 및 기본 fallback
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

> 🔍 **출처**: [docs/Nutrition-docs/07-core-algorithm.md §6.1](../07-core-algorithm.md), [docs/Nutrition-docs/13-algorithm-literature-evidence.md](../13-algorithm-literature-evidence.md), Hall et al. (2011) "Quantification of the effect of energy imbalance on bodyweight.", NIDDK Body Weight Planner 공식 문서와 Hall Lancet web appendix.

### 근거 보강

| 항목 | 근거 수준 | 적용 방식 |
|------|----------|----------|
| Hall 동적 체중 모델 | A/B | 장기 체중 변화에는 정적 7,700 kcal/kg 규칙보다 동적 모델을 우선 검토한다. 단, 본 구현은 full Hall model 재현이 아니라 Hall-lite 단순화 구현이다. |
| Hall web appendix 단위 체계 | A | 내부 계산은 kJ/day와 kJ/kg로 통일하고, API 입출력과 UI 표시는 kcal/day로 변환한다. `γF=13`, `γL=92`는 kcal이 아니라 kJ/kg/day 계수다. |
| Deurenberg 체지방률 추정 | A/B | 체지방률 미입력 시 초기 FM/FFM 추정값으로 사용한다. 개인 측정값이 있으면 측정값을 우선한다. |
| Forbes body composition response | B | 감량·증량 시 FFM/FM 변화 비율을 단순 모델에 반영한다. |

> 현재 구현 계획은 논문 전체 모델의 완전 재현이 아니라 학생 프로젝트용 단순화 버전이다. 실제 사용자 데이터 또는 논문 케이스 재현 검증 전까지는 "정확한 예측"이 아니라 "정적 모델보다 보수적인 장기 참고 시뮬레이션"으로 설명한다.

### 모델 범위와 단위 원칙

- **내부 단위**: Hall 계수와 조직 에너지 밀도는 kJ 기준으로 계산한다.
- **외부 단위**: 기존 API와 모바일 UI는 kcal/day, kg, day를 유지한다.
- **기준 BMR 보정**: `γF × FM + γL × FFM`만 RMR로 쓰면 기존 Mifflin-St Jeor BMR보다 낮아질 수 있다. 따라서 초기 BMR을 기존 `calculate_bmr()`로 계산하고, `rmr_intercept = initial_bmr_kJ - (γF×FM0 + γL×FFM0)`를 보정항으로 저장한다.
- **Hall-lite 한계**: glycogen, extracellular fluid, macronutrient flux 전체 모델은 구현하지 않는다. 장기 예측의 곡선 형태와 보수성을 개선하는 수준으로 제한한다.
- **의료 표현 제한**: 사용자 노출 문구는 "예측", "참고 시뮬레이션", "생활 변화 가정"으로 제한하고, 질환 개선·감량 보장 표현은 금지한다.

### Hall 모델의 핵심 아이디어

7-step 단순 모델의 한계:
- BMR을 시작 시점에서 1회 계산 (실제로는 체중 변화에 따라 변화)
- 모든 변화를 지방으로 가정 (실제로는 FFM도 함께 변화)
- 30일 이상 장기 예측 시 오차 누적

Hall 모델 개선:
- **일별 시뮬레이션**: 매일 체중·RMR·TDEE 재계산
- **신체구성 분리**: FFM(제지방) + FM(지방) 별도 추적
- **적응적 열역학**: 감량 시 에너지 소비 감소를 1차 지연 항으로 반영

### 핵심 수식

```
단위 변환:
  kcal_to_kJ = 4.184
  target_intake_kJ = intake_kcal × 4.184

초기화:
  initial_bmr_kJ = calculate_bmr(weight, height, age, sex) × 4.184
  initial_tdee_kJ = calculate_tdee(initial_bmr_kcal, steps) × 4.184
  baseline_intake_kJ = initial_tdee_kJ
  baseline_tef_kJ = 0.10 × baseline_intake_kJ
  initial_paee_kJ = max(0, initial_tdee_kJ - initial_bmr_kJ - baseline_tef_kJ)
  rmr_intercept_kJ = initial_bmr_kJ - (γ_F × FM_0 + γ_L × FFM_0)
  delta_ei_kJ = target_intake_kJ - baseline_intake_kJ

일일 시뮬레이션 (D=0~N):
  1. FFM_D, FM_D 로부터 dynamic RMR 계산:
     RMR_D = rmr_intercept_kJ + γ_F × FM_D + γ_L × FFM_D
     γ_F = 13 kJ/kg/day
     γ_L = 92 kJ/kg/day

  2. 활동 에너지와 TEF 계산:
     PAEE_D = initial_paee_kJ × (Weight_D / Weight_0)
     TEF_D = 0.10 × target_intake_kJ

  3. 적응적 열역학:
     target_AT = β_AT × delta_ei_kJ
     AT_{D+1} = AT_D + (target_AT - AT_D) / τ_AT
     β_AT = 0.14
     τ_AT = 14 days

  4. 총 에너지 소비와 수지:
     TDEE_D = RMR_D + PAEE_D + TEF_D + AT_D
     ΔE_D = target_intake_kJ - TDEE_D

  5. FFM·FM 변화 (Forbes partition):
     p = C_E / (C_E + FM_D)
     C_E = 10.4 kg × ρ_L / ρ_F
     ρ_F = 39,500 kJ/kg
     ρ_L = 7,600 kJ/kg
     ΔFM = ΔE_D × (1 - p) / ρ_F
     ΔFFM = ΔE_D × p / ρ_L

  6. 다음날 갱신:
     FM_{D+1} = max(min_fm, FM_D + ΔFM)
     FFM_{D+1} = max(min_ffm, FFM_D + ΔFFM)
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
        37.9
        >>> estimate_body_fat_percentage(bmi=26.7, age=45, sex="male")
        26.19

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
        37.98
        >>> round(bc.fat_mass_kg, 1)
        25.8
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
"""Hall-lite 동적 체중 예측 모델.

Full Hall model의 glycogen, ECF, macronutrient flux는 구현하지 않는다.
내부 에너지 계산은 kJ 기준이며 API 표시값만 kcal로 변환한다.
"""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict

from src.algorithms.metabolism import calculate_bmr, calculate_tdee
from src.prediction.body_composition import BodyComposition

KCAL_TO_KJ: Final[float] = 4.184
GAMMA_F_KJ_PER_KG_DAY: Final[float] = 13.0
GAMMA_L_KJ_PER_KG_DAY: Final[float] = 92.0
RHO_F_KJ_PER_KG: Final[float] = 39_500.0
RHO_L_KJ_PER_KG: Final[float] = 7_600.0
FORBES_C_MASS_KG: Final[float] = 10.4
FORBES_C_ENERGY_PARTITION_KG: Final[float] = (
    FORBES_C_MASS_KG * RHO_L_KJ_PER_KG / RHO_F_KJ_PER_KG
)
TEF_RATIO: Final[float] = 0.10
ADAPTIVE_THERMOGENESIS_BETA: Final[float] = 0.14
ADAPTIVE_THERMOGENESIS_TAU_DAYS: Final[float] = 14.0


class HallBaseline(BaseModel):
    """초기 에너지 소비 기준선.

    Args:
        initial_weight_kg: 시작 체중.
        initial_bmr_kj: 기존 Mifflin-St Jeor BMR을 kJ로 변환한 값.
        initial_tdee_kj: 기존 activity-factor TDEE를 kJ로 변환한 값.
        initial_paee_kj: 초기 활동 에너지. 이후 체중 비율로 scale한다.
        rmr_intercept_kj: composition RMR을 기존 BMR에 맞추는 보정항.
    """

    model_config = ConfigDict(frozen=True)

    initial_weight_kg: float
    initial_bmr_kj: float
    initial_tdee_kj: float
    initial_paee_kj: float
    rmr_intercept_kj: float


class DailyState(BaseModel):
    """일별 시뮬레이션 상태.

    Attributes:
        day: 시뮬레이션 일차.
        composition: 해당 일차 종료 시점의 신체구성.
        rmr_kcal: 휴식대사량.
        paee_kcal: 활동 에너지 소비량.
        tef_kcal: 음식 열효과.
        adaptive_thermogenesis_kcal: 적응성 열생성 보정값.
        tdee_kcal: 총 일일 에너지 소비량.
        intake_kcal: 일일 섭취 열량.
        energy_balance_kcal: 섭취량에서 소비량을 뺀 에너지 균형.
    """

    model_config = ConfigDict(frozen=True)

    day: int
    composition: BodyComposition
    rmr_kcal: float
    paee_kcal: float
    tef_kcal: float
    adaptive_thermogenesis_kcal: float
    tdee_kcal: float
    intake_kcal: float
    energy_balance_kcal: float


def kcal_to_kj(value: float) -> float:
    """kcal을 kJ로 변환한다.

    Args:
        value: kcal 단위 에너지 값.

    Returns:
        kJ 단위 에너지 값.
    """
    return value * KCAL_TO_KJ


def kj_to_kcal(value: float) -> float:
    """kJ을 kcal로 변환한다.

    Args:
        value: kJ 단위 에너지 값.

    Returns:
        kcal 단위 에너지 값.
    """
    return value / KCAL_TO_KJ


def calculate_composition_rmr_kj(composition: BodyComposition) -> float:
    """Hall appendix의 FM/FFM 회귀 계수로 RMR 구성요소를 계산한다.

    Args:
        composition: 체중, 지방량, 제지방량을 포함한 신체구성.

    Returns:
        Hall composition term 기반 RMR 구성요소 (kJ/day).
    """
    return (
        GAMMA_F_KJ_PER_KG_DAY * composition.fat_mass_kg
        + GAMMA_L_KJ_PER_KG_DAY * composition.fat_free_mass_kg
    )


def build_baseline(
    *,
    composition: BodyComposition,
    height_cm: float,
    age: int,
    sex: str,
    daily_steps: int,
) -> HallBaseline:
    """기존 7-step BMR/TDEE와 Hall composition term을 같은 기준선으로 맞춘다.

    Args:
        composition: 초기 신체구성.
        height_cm: 키.
        age: 만 나이.
        sex: 성별.
        daily_steps: 일일 걸음 수.
    Returns:
        초기 BMR/TDEE와 composition RMR 보정항을 담은 기준선.
    """
    initial_bmr_kcal = calculate_bmr(
        weight_kg=composition.weight_kg,
        height_cm=height_cm,
        age=age,
        sex=sex,
    )
    initial_tdee_kcal = calculate_tdee(
        estimated_bmr=initial_bmr_kcal,
        daily_steps=daily_steps,
    )
    initial_bmr_kj = kcal_to_kj(initial_bmr_kcal)
    initial_tdee_kj = kcal_to_kj(initial_tdee_kcal)
    baseline_intake_kj = initial_tdee_kj
    baseline_tef_kj = TEF_RATIO * baseline_intake_kj
    initial_paee_kj = max(0.0, initial_tdee_kj - initial_bmr_kj - baseline_tef_kj)
    rmr_intercept_kj = initial_bmr_kj - calculate_composition_rmr_kj(composition)
    return HallBaseline(
        initial_weight_kg=composition.weight_kg,
        initial_bmr_kj=initial_bmr_kj,
        initial_tdee_kj=initial_tdee_kj,
        initial_paee_kj=initial_paee_kj,
        rmr_intercept_kj=rmr_intercept_kj,
    )


def calculate_dynamic_rmr_kj(composition: BodyComposition, baseline: HallBaseline) -> float:
    """초기 BMR 보정항을 포함한 동적 RMR을 계산한다.

    Args:
        composition: 현재 일차의 신체구성.
        baseline: 초기 에너지 소비 기준선.

    Returns:
        보정항이 포함된 동적 RMR (kJ/day).
    """
    return max(0.0, baseline.rmr_intercept_kj + calculate_composition_rmr_kj(composition))


def partition_energy_balance(energy_balance_kj: float, composition: BodyComposition) -> tuple[float, float]:
    """Forbes partition으로 FM/FFM 변화량을 kg 단위로 계산한다.

    Args:
        energy_balance_kj: 하루 에너지 균형 (kJ/day).
        composition: 현재 일차의 신체구성.

    Returns:
        지방량 변화량과 제지방량 변화량의 튜플 (kg/day).
    """
    p = FORBES_C_ENERGY_PARTITION_KG / (
        FORBES_C_ENERGY_PARTITION_KG + composition.fat_mass_kg
    )
    delta_fm = energy_balance_kj * (1.0 - p) / RHO_F_KJ_PER_KG
    delta_ffm = energy_balance_kj * p / RHO_L_KJ_PER_KG
    return delta_fm, delta_ffm
```

`step_one_day()`와 `predict_with_hall()`은 위 primitive를 조합한다. 구현 시 반드시 지킬 규칙:

- `RMR`, `PAEE`, `TEF`, `AT`, `TDEE`, `energy_balance`는 내부에서 kJ로 계산한다.
- 응답에는 kcal로 변환한 값을 저장한다.
- `PAEE_D = initial_paee_kJ × (Weight_D / Weight_0)`로 체중 변화에 따른 활동 비용 변화를 반영한다.
- `AT`는 `target_AT = β_AT × (target_intake_kJ - baseline_intake_kJ)`에 14일 시정수로 점진 접근한다.
- `FM`과 `FFM`은 0으로 떨어지지 않도록 최소값 guard를 둔다.
- 1차 구현의 golden value는 논문 재현값이 아니라 프로젝트 기준 sanity check로 둔다. 정확한 수치 주장은 실제 검증 데이터가 들어온 뒤에만 허용한다.

### 3. `src/prediction/selector.py`

```python
"""7-step / Hall-lite 모델 선택 및 안전 fallback."""

from __future__ import annotations

from enum import StrEnum
from typing import Final

from src.prediction.hall import predict_with_hall
from src.prediction.weight import predict_weight_n_days


LONG_TERM_HALL_CANDIDATE_DAYS: Final[int] = 90
"""auto 모드에서 Hall-lite 후보로 볼 최소 기간."""


class WeightPredictionModel(StrEnum):
    """체중 예측 모델 선택값."""

    AUTO = "auto"
    STATIC_7STEP = "static_7step"
    HALL_LITE = "hall_lite"


def predict_weight_adaptive(
    weight_kg: float,
    height_cm: float,
    age: int,
    sex: str,
    daily_steps: int,
    daily_intake_kcal: float,
    days: int,
    model: WeightPredictionModel = WeightPredictionModel.STATIC_7STEP,
    enable_hall_lite: bool = False,
    measured_bfp: float | None = None,
) -> dict[str, object]:
    """설정에 따라 체중 예측 모델 선택.

    Args:
        weight_kg: 현재 체중.
        height_cm: 키.
        age: 만 나이.
        sex: 성별.
        daily_steps: 일일 걸음 수.
        daily_intake_kcal: 일일 섭취 열량.
        days: 예측 기간.
        model: 명시적 모델 선택. 기본값은 기존 7-step.
        enable_hall_lite: Hall-lite 기능 플래그. False이면 항상 7-step.
        measured_bfp: 측정 체지방률 (Hall에서 사용).

    Returns:
        {model_used: "hall_lite" | "static_7step", result: ..., predicted_weight_kg: float}

    예측 정확도:
        - 7-step: 기본 fallback, 빠름, 기존 API와 동일
        - Hall-lite: 기능 플래그가 켜진 장기 예측 후보, 일별 적응, 신체구성 분리
    """
    use_hall = enable_hall_lite and (
        model == WeightPredictionModel.HALL_LITE
        or (model == WeightPredictionModel.AUTO and days >= LONG_TERM_HALL_CANDIDATE_DAYS)
    )

    if use_hall:
        result = predict_with_hall(
            weight_kg=weight_kg, height_cm=height_cm,
            age=age, sex=sex,
            daily_steps=daily_steps,
            daily_intake_kcal=daily_intake_kcal,
            n_days=days,
            measured_bfp=measured_bfp,
        )
        return {
            "model_used": WeightPredictionModel.HALL_LITE.value,
            "predicted_weight_kg": result.predicted_weight,
            "result": result,
        }

    result = predict_weight_n_days(
        weight_kg=weight_kg, height_cm=height_cm,
        age=age, sex=sex,
        daily_steps=daily_steps,
        daily_intake_kcal=daily_intake_kcal,
        days=days,
    )
    return {
        "model_used": WeightPredictionModel.STATIC_7STEP.value,
        "predicted_weight_kg": result.predicted_weight_kg,
        "result": result,
    }
```

---

## 🧪 테스트 (4-Tier)

### Tier 1: 단위 테스트

#### `test_body_composition.py`

| 테스트 | 입력 | 기대값 |
|-------|------|-------|
| `test_deurenberg_50f_obese1` | bmi=26.5, age=50, female | ≈37.90 |
| `test_deurenberg_45m_overweight` | bmi=26.7, age=45, male | ≈26.19 |
| `test_estimate_uses_measured_bfp` | measured=30.0 | 추정 무시, 30.0 사용 |
| `test_clamping_lower` | 매우 마른 사람 | ≥ 5.0 |
| `test_clamping_upper` | 비현실적 비만 | ≤ 50.0 |
| `test_fm_ffm_sum_equals_weight` | 모든 케이스 | FM + FFM = weight |

#### `test_hall.py`

| 테스트 | 검증 |
|-------|------|
| `test_calculate_composition_rmr_kj_basic` | `γF/γL`가 kJ/kg/day 단위로 적용되는지 검증 |
| `test_build_baseline_preserves_initial_static_tdee` | day 0 TDEE가 기존 7-step TDEE와 일치 |
| `test_step_one_day_no_balance` | 섭취 = 초기 TDEE → 신체구성 거의 불변 |
| `test_step_one_day_deficit_loses_fm` | 적자 → FM 감소 우세 |
| `test_step_one_day_surplus_gains_fm` | 흑자 → FM 증가 우세 |
| `test_forbes_higher_fm_more_fat_change` | FM 높을수록 변화도 FM에 집중 |
| `test_adaptive_thermogenesis_reduces_expenditure_in_deficit` | 적자 시 AT가 음수 방향으로 이동 |
| `test_predict_50f_30days_sanity` | 50f 30일 → 감량 방향, 비현실적 급감 없음 |
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
        base_kwargs = {
            "weight_kg": 68, "height_cm": 160, "age": 50, "sex": "female",
            "daily_steps": 6500, "daily_intake_kcal": 1500,
        }
        seven = predict_weight_n_days(**base_kwargs, days=days)
        hall = predict_with_hall(**base_kwargs, n_days=days)

        diff = abs(seven.predicted_weight_kg - hall.predicted_weight)
        assert diff < days * 0.05, f"Excessive divergence at day {days}: {diff}"

    def test_hall_more_conservative_for_loss(self):
        """감량 시 Hall이 7-step보다 보수적."""
        # 대사 적응을 반영하므로 같은 적자에서도 감소량이 작음
        base_kwargs = {
            "weight_kg": 68, "height_cm": 160, "age": 50, "sex": "female",
            "daily_steps": 6500, "daily_intake_kcal": 1500,
        }
        seven = predict_weight_n_days(**base_kwargs, days=90)
        hall = predict_with_hall(**base_kwargs, n_days=90)

        # Hall이 감량을 덜 예측 (대사 적응 반영)
        seven_loss = base_kwargs["weight_kg"] - seven.predicted_weight_kg
        hall_loss = base_kwargs["weight_kg"] - hall.predicted_weight
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
- [ ] `src/prediction/hall.py` — 단위 변환, baseline 보정, step_one_day, predict_with_hall
- [ ] `src/prediction/selector.py` — 설정 기반 모델 선택 및 기본 7-step fallback
- [ ] `WeightPredictionRequest/Response` — 기존 필수 필드와 기본 응답 유지. `model`, `model_used`, `measured_body_fat_pct`, `include_daily_states`는 별도 contract 승인 후 optional 확장
- [ ] 모든 함수 Google-style docstring + Examples
- [ ] 모든 함수 타입 힌트
- [ ] 단위 테스트 (Body Composition + Hall) 25+
- [ ] kJ/kcal 단위 변환과 `γF/γL` 단위 회귀 테스트
- [ ] 통합 테스트 (7-step vs Hall 비교)
- [ ] E2E 테스트 (6개월 시뮬레이션, 정체기 관찰)
- [ ] 성능 테스트 (30일 < 100ms, 365일 < 1s)
- [ ] **수식 정확성 검증** — Hall appendix 상수 단위와 baseline TDEE 보존 검증
- [ ] **제한 문구 검증** — API note/OpenAPI example에서 감량 보장·질환 개선 표현 금지
- [ ] `mypy src/prediction --strict` 통과
- [ ] 기존 7-step 테스트 회귀 없음

---

## 💡 구현 팁

### Hall 모델 단순화 결정

학생 프로젝트에서는 **단순화된 Hall 모델** 만 구현. 풀 모델의 다음은 생략:
- 단백질·탄수화물·지방 섭취 별도 추적 (3-개체 모델)
- 글리코겐 변화 (단기 변동의 큰 부분이지만 ±2kg 수준)
- extracellular fluid/sodium 변화
- 운동 종류별 PAEE 변환 정확화

→ **목표**: 30~90일 범위에서 7-step보다 더 보수적인 장기 예측 제공. 실제 정확도 개선률은 베타 데이터 검증 전까지 수치로 주장하지 않는다.

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
        rmr_kj = baseline.rmr_intercept_kj + (
            GAMMA_F_KJ_PER_KG_DAY * fm[d]
            + GAMMA_L_KJ_PER_KG_DAY * ffm[d]
        )
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

- [`/docs/Nutrition-docs/07-core-algorithm.md §6.1`](../07-core-algorithm.md)
- [`/docs/Nutrition-docs/13-algorithm-literature-evidence.md`](../13-algorithm-literature-evidence.md)
- [`/backend/CLAUDE.md`](../../backend/CLAUDE.md)
- 이전: [`13-mobile-dashboard.md`](./13-mobile-dashboard.md)
- 다음: [`15-goal-based-analysis.md`](./15-goal-based-analysis.md)

## 📚 사용 근거

- NIDDK Body Weight Planner. 성인용 체중·칼로리 계획 도구와 의료 조언이 아니라는 제한 문구를 확인했다. https://www.niddk.nih.gov/health-information/weight-management/body-weight-planner
- NIDDK Research Behind the Body Weight Planner. Hall 연구팀, Lancet 2011 논문, 모델 방정식 web appendix 연결을 확인했다. https://www.niddk.nih.gov/research-funding/at-niddk/labs-branches/laboratory-biological-modeling/integrative-physiology-section/research/body-weight-planner
- Hall KD, Sacks G, Chandramohan D, et al. Quantification of the effect of energy imbalance on bodyweight. The Lancet. 2011. https://stacks.cdc.gov/view/cdc/33652
- Hall Lancet web appendix. `ρF=39.5 MJ/kg`, `ρL=7.6 MJ/kg`, `γF=13 kJ/kg/day`, `γL=92 kJ/kg/day`, `βTEF=0.1`, `βAT=0.14`, `τAT=14 days` 단위를 확인했다. https://www.niddk.nih.gov/-/media/Files/BWP/Hall_Lancet_Web_Appendix.pdf
- Deurenberg P, Weststrate JA, Seidell JC. Body mass index as a measure of body fatness. British Journal of Nutrition. 1991. https://www.cambridge.org/core/journals/british-journal-of-nutrition/article/body-mass-index-as-a-measure-of-body-fatness-age-and-sexspecific-prediction-formulas/9C03B18E1A0E4CDB0441644EE64D9AA2
- Forbes GB. Body fat content influences the body composition response to nutrition and exercise. Annals of the New York Academy of Sciences. 2000. https://pubmed.ncbi.nlm.nih.gov/10865771/
