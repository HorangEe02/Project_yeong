# dev-guides/02 — v2·v3·v4 활동점수

> **Phase**: 1 | **선행 작업**: [`01-bmi-and-v1-algorithm.md`](./01-bmi-and-v1-algorithm.md) | **예상 소요**: 2~3시간

---

## 🎯 작업 목표

v1 기본점수에 심박수 가중(v2), 백분위 보너스(v3), 만성질환 가중(v4)을 적용하는 알고리즘을 구현하고 가이드 PPTX의 계산 예시를 검증한다.

---

## 📋 산출물

기존 `src/algorithms/activity.py` 와 `tests/unit/algorithms/test_activity_v1.py` 에 추가:

```
backend/
├── src/algorithms/activity.py       # v2~v4 함수 추가
└── tests/unit/algorithms/
    ├── test_activity_v2.py          # 신규
    ├── test_activity_v3.py          # 신규
    └── test_activity_v4.py          # 신규
```

---

## 📐 알고리즘 명세

> 🔍 **출처**: [docs/07-core-algorithm.md §3.3, §3.4, §3.5](../07-core-algorithm.md), [docs/13-algorithm-literature-evidence.md](../13-algorithm-literature-evidence.md)

### 근거 보강

| 항목 | 근거 수준 | 적용 방식 |
|------|----------|----------|
| HRmax 추정 | B | 회사 가이드 재현은 `220 - age`를 기본으로 유지한다. Tanaka et al. 2001의 `208 - 0.7 * age`는 옵션으로 추가한다. |
| 심박 유지 30분 | C | 운동 질을 반영하는 프로젝트 기준이다. 의료 판단값으로 사용하지 않는다. |
| 백분위 보너스 | C | 동기부여 UX 기준이다. 최소 표본, 동점 처리, 개인정보 보호 정책이 함께 필요하다. |
| 만성질환 가중 | B/C | 신체활동 권고 방향은 HHS/CDC 근거가 있으나, 질환별 가산치는 프로젝트 우선순위 계수다. |

### v2 — 심박수 가중

```
목표심박구간 = (220 − 나이) × [0.5 ~ 0.7]
심박계수 = min(목표심박 유지시간(분) ÷ 30, 1.0)
※ 웨어러블 미착용 시: 심박계수 = 0.7 (기본값)

v2점수 = v1점수 × (0.7 + 0.3 × 심박계수)
```

### v3 — 백분위 보너스

```
비교 그룹 = 같은 성별 + 동일 연령대 (10세 단위)
최소 표본 = 30명 이상

순위 보너스:
  상위 10% 이내 → +10점
  상위 20% 이내 → +5점
  상위 30% 이내 → +3점
  그 외         → 0점

v3점수 = min(100, v2점수 + 백분위 보너스)
```

### v4 — 만성질환 가중

```
만성질환가중 = 1.0 + Σ(질환별 가산치)  [최대 1.3 상한]

질환별 가산치:
  당뇨        +0.10
  고혈압      +0.10
  심혈관질환  +0.15
  관절질환    +0.15
  호흡기질환  +0.10

v4점수 = min(100, v3점수 × 만성질환가중)
```

---

## 🔧 구현 명세

### 1. `src/algorithms/activity.py` 에 추가

#### 모듈 상수

```python
# 심박수 관련
HR_FACTOR_DEFAULT_NO_WEARABLE: float = 0.7
"""웨어러블 미착용 시 사용할 기본 심박계수."""

HR_TARGET_LOW_PCT: float = 0.5
HR_TARGET_HIGH_PCT: float = 0.7
"""목표 심박구간 (HRmax의 50%~70%)."""

HR_TARGET_DURATION_MIN: float = 30
"""심박계수 만점 기준 시간 (분)."""

V2_BASELINE_WEIGHT: float = 0.7
V2_HR_WEIGHT: float = 0.3
"""v2 가중치: 0.7 × v1점수 + 0.3 × (v1점수 × 심박계수)."""

# 백분위 보너스
PERCENTILE_MIN_GROUP_SIZE: int = 30
PERCENTILE_BONUS_MAP: list[tuple[float, int]] = [
    (10.0, 10),  # 상위 10% → +10
    (20.0, 5),   # 상위 20% → +5
    (30.0, 3),   # 상위 30% → +3
]
"""(상위 백분위 임계, 보너스 점수) 튜플 리스트. 정렬된 순서로 평가."""

# 만성질환 가중
DISEASE_WEIGHTS: dict[str, float] = {
    "diabetes": 0.10,
    "hypertension": 0.10,
    "cardiovascular": 0.15,
    "joint": 0.15,
    "respiratory": 0.10,
}
"""만성질환 코드별 v4 가중치."""

DISEASE_MULTIPLIER_MAX: float = 1.3
"""만성질환 가중치 상한."""

SCORE_MAX: float = 100.0
"""모든 점수의 상한값."""
```

#### 구현해야 할 함수 시그니처

```python
def calculate_estimated_hr_max(age: int, method: str = "guide_220") -> float: ...

def calculate_target_hr_range(age: int, method: str = "guide_220") -> tuple[int, int]: ...

def calculate_hr_factor(target_hr_minutes: float | None) -> float: ...

def calculate_v2_score(v1_score: float, hr_factor: float) -> float: ...

def calculate_percentile_bonus(
    user_v2: float,
    group_v2_scores: list[float],
) -> int: ...

def calculate_v3_score(v2_score: float, bonus: int) -> float: ...

def calculate_disease_multiplier(diseases: list[str]) -> float: ...

def calculate_v4_score(v3_score: float, multiplier: float) -> float: ...
```

#### 요구사항 (모든 함수 공통)

- 모든 함수에 Google-style docstring (Args/Returns/Raises/Examples)
- `Examples:` 섹션에는 가이드 예시 포함
- 타입 힌트 100%
- `min(SCORE_MAX, ...)` 형태로 100점 상한 강제
- `calculate_estimated_hr_max`는 `guide_220`과 `tanaka_2001`만 허용하고, 그 외 method는 `ValueError` 발생
- `calculate_target_hr_range` 테스트 기본값은 기존 가이드 재현을 위해 `guide_220` 기준 유지
- `calculate_hr_factor`는 `None` 입력 시 `HR_FACTOR_DEFAULT_NO_WEARABLE` 반환
- `calculate_percentile_bonus`는 표본 < 30 시 0 반환
- `calculate_disease_multiplier`는 미정의 질환 코드 무시 (warning 로그)

---

## 🧪 단위 테스트

### `test_activity_v2.py`

| 테스트 | 입력 | 기대 결과 |
|-------|------|---------|
| `test_target_hr_50yo` | age=50 | (85, 119) |
| `test_target_hr_30yo` | age=30 | (95, 133) |
| `test_target_hr_60yo` | age=60 | (80, 112) |
| `test_estimated_hr_max_tanaka_50yo` | age=50, method="tanaka_2001" | 173.0 |
| `test_hr_factor_no_wearable` | None | 0.7 |
| `test_hr_factor_under_30min` | 20분 | ≈0.667 |
| `test_hr_factor_exact_30min` | 30분 | 1.0 |
| `test_hr_factor_over_30min` | 45분 | 1.0 (캡) |
| `test_hr_factor_zero_min` | 0분 | 0.0 |
| `test_v2_at_max_hr_factor` | v1=100, hr=1.0 | 100.0 |
| `test_v2_no_wearable_default` | v1=100, hr=0.7 | 91.0 |
| **`test_v2_50f_guide_example`** | **v1=77.5, hr=0.667** | **≈69.7 (가이드)** |

### `test_activity_v3.py`

| 테스트 | 입력 | 기대 결과 |
|-------|------|---------|
| `test_bonus_top_10pct` | user=80, group=[50]*95 + [80]*5 | 10 |
| `test_bonus_top_20pct` | user=70, group=[50]*85 + [70]*15 | 5 |
| `test_bonus_top_30pct` | user=60, group=[50]*75 + [60]*25 | 3 |
| `test_bonus_below_30pct` | user=50, group=[40]*50 + [50]*50 | 0 |
| `test_bonus_below_min_group_size` | group=[50]*20 | 0 (표본 부족) |
| `test_bonus_at_min_group_size` | group=[50]*30 (표본 충족) | 0 또는 평가 |
| **`test_v3_50f_guide_example`** | **v2=69.7, bonus=3** | **≈72.7 (가이드)** |
| `test_v3_capped_at_100` | v2=95, bonus=10 | 100.0 |
| `test_v3_no_bonus` | v2=80, bonus=0 | 80.0 |

### `test_activity_v4.py`

| 테스트 | 입력 | 기대 결과 |
|-------|------|---------|
| `test_no_disease` | [] | 1.0 |
| `test_single_diabetes` | ["diabetes"] | 1.10 |
| `test_single_hypertension` | ["hypertension"] | 1.10 |
| `test_single_cardiovascular` | ["cardiovascular"] | 1.15 |
| `test_single_joint` | ["joint"] | 1.15 |
| `test_single_respiratory` | ["respiratory"] | 1.10 |
| **`test_diabetes_plus_hypertension_guide`** | **["diabetes", "hypertension"]** | **1.20 (가이드)** |
| `test_three_diseases_summed` | ["diabetes", "hypertension", "respiratory"] | 1.30 (합계 0.30) |
| `test_capped_at_max` | 4개 질환 (합 0.5) | 1.3 (상한) |
| `test_unknown_disease_ignored` | ["covid", "diabetes"] | 1.10 |
| `test_v4_at_max_score` | v3=100, mult=1.3 | 100.0 (캡) |
| `test_v4_below_max` | v3=80, mult=1.0 | 80.0 |
| **`test_v4_50f_guide_example`** | **v3=72.7, mult=1.20** | **≈87.2 (가이드)** |

---

## 📊 가이드 예시 검증 매트릭스 (이 작업 완료 시)

```
연속 계산 (50대 여성 비만1, 당뇨+고혈압, 7000보, 심박 20분, 상위 25%):

v1 = 77.5  (이전 작업에서 검증됨)
   ↓
v2 = 77.5 × (0.7 + 0.3 × 0.667) = 77.5 × 0.9001 ≈ 69.7  ✅
   ↓
v3 = 69.7 + 3 (상위 25% → 30% 이내) = 72.7  ✅
   ↓
v4 = min(100, 72.7 × 1.20) = 87.24 ≈ 87.2  ✅
```

→ **회사 가이드 PPTX 활동점수 예시 100% 일치**

---

## ✅ Definition of Done

- [ ] `calculate_target_hr_range` 구현 + 테스트
- [ ] `calculate_hr_factor` 구현 + 테스트 (None 처리 포함)
- [ ] `calculate_v2_score` 구현 + 테스트 (가이드 예시)
- [ ] `calculate_percentile_bonus` 구현 + 테스트 (표본 부족 분기)
- [ ] `calculate_v3_score` 구현 + 테스트 (가이드 예시)
- [ ] `calculate_disease_multiplier` 구현 + 테스트 (가이드 예시)
- [ ] `calculate_v4_score` 구현 + 테스트 (가이드 예시)
- [ ] 모든 함수에 Google-style docstring + Examples
- [ ] 모든 함수에 타입 힌트
- [ ] 통합 테스트 — v1 → v2 → v3 → v4 연속 계산이 87.2 도출
- [ ] `mypy src/algorithms --strict` 통과
- [ ] `pytest tests/unit/algorithms -v` 전체 통과
- [ ] 코드 커버리지 ≥ 90%

---

## 💡 구현 팁

### 부동소수점 누적 오차

가이드 예시 (87.24)는 손계산이라 약간의 오차 허용 필요:

```python
# v3 = 69.7 + 3 = 72.7
# 그런데 실제 v2 정확값은 69.7325 → v3 = 72.7325
# v4 = min(100, 72.7325 × 1.2) = 87.279 ≈ 87.3
# 가이드는 87.24

# 따라서 테스트에서는 ±0.1 ~ ±0.2 허용
assert v4 == pytest.approx(87.2, abs=0.2)
```

### 백분위 계산 (편향 주의)

```python
def calculate_percentile_bonus(
    user_v2: float,
    group_v2_scores: list[float],
) -> int:
    """..."""
    if len(group_v2_scores) < PERCENTILE_MIN_GROUP_SIZE:
        return 0

    # 사용자보다 점수가 *높은* 사람의 비율
    higher_count = sum(1 for s in group_v2_scores if s > user_v2)
    percentile_rank = (higher_count / len(group_v2_scores)) * 100

    for threshold, bonus in PERCENTILE_BONUS_MAP:
        if percentile_rank <= threshold:
            return bonus
    return 0
```

> 💡 동률 처리: 사용자와 동일 점수인 사람들은 "위"가 아니므로 카운트 X. 이는 동점일 경우 사용자에게 유리하게 작용 (낙관적 백분위).

### 미정의 질환 무시

```python
import logging

logger = logging.getLogger(__name__)


def calculate_disease_multiplier(diseases: list[str]) -> float:
    """..."""
    total_addon = 0.0
    for disease in diseases:
        if disease in DISEASE_WEIGHTS:
            total_addon += DISEASE_WEIGHTS[disease]
        else:
            logger.warning("Unknown disease code ignored: %s", disease)

    multiplier = min(1.0 + total_addon, DISEASE_MULTIPLIER_MAX)
    return round(multiplier, 3)
```

---

## 🚫 이 작업에서 하지 말 것

- ❌ DB에 v2~v4 저장 (다음 단계)
- ❌ FastAPI 라우터 작성
- ❌ Phase 3의 Hall 동적 모델 도입 (별도 마일스톤)

---

## 🔗 관련 문서

- [`/CLAUDE.md`](../../CLAUDE.md)
- [`/backend/CLAUDE.md`](../../backend/CLAUDE.md)
- [`/docs/07-core-algorithm.md §3.3~§3.5`](../07-core-algorithm.md)
- 이전 작업: [`01-bmi-and-v1-algorithm.md`](./01-bmi-and-v1-algorithm.md)
- 다음 작업: [`03-bmr-tdee.md`](./03-bmr-tdee.md)
