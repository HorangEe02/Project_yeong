# 29. Hall-lite 체중 예측 구현 플랜

> 작성일: 2026-05-13
> 범위: `backend/src/prediction`, `/api/v1/predictions/weight`, 체중 예측 테스트
> 결론: 기존 7-step 모델을 기본값으로 고정한 뒤 `body_composition` -> `hall` -> `selector` 순서로 Hall-lite를 독립 추가한다.
> 구현 상태: 2026-05-13 기준 backend 구현 완료. 기본 feature flag는 `false`이고 `/api/v1/predictions/weight` 기본 응답은 기존 7-step과 동일하다.

---

## 1. 브레인스토밍 결론

### 후보 A: 기존 `/api/v1/predictions/weight`를 Hall-lite로 즉시 교체

- 장점: 사용자에게 새 모델을 바로 제공할 수 있다.
- 문제: 기존 7-step golden value, OpenAPI 응답 의미, 모바일 화면 기대값이 한 번에 바뀐다.
- 판정: **보류**. 현재 요구사항의 "기존 호환성 유지"와 충돌한다.

### 후보 B: 요청/응답 스키마에 `model`, `model_used`, `daily_states`를 바로 추가

- 장점: Hall-lite 결과의 내부 상태를 명확히 노출할 수 있다.
- 문제: OpenAPI contract와 모바일 DTO 변경이 커진다. 현재 P1 안정화 기준선과 충돌할 수 있다.
- 판정: **후속 contract PR로 분리**. 이번 구현 단위에서는 필수 필드를 추가하지 않는다.

### 후보 C: 내부 모델 모듈과 selector를 추가하되 기본은 7-step 유지

- 장점: 코드 경로를 확장하면서도 기존 API 결과가 그대로 유지된다.
- 장점: `feature_hall_lite_weight_prediction=false` 기본값으로 안전하게 병렬 개발할 수 있다.
- 장점: supplement image/OCR/LLM flow와 파일 경계가 분리된다.
- 판정: **권장 방향**.

---

## 2. 현재 구현 기준선

현재 endpoint는 `backend/src/api/v1/predictions.py`의 `POST /api/v1/predictions/weight`이며, `backend/src/prediction/weight.py`의 `predict_weight_periods()`를 직접 호출한다.

고정해야 하는 기존 동작:

- 요청 스키마: `WeightPredictionRequest`
  - `age`, `sex`, `height_cm`, `weight_kg`, `daily_steps`, `daily_intake_kcal`, `periods_days`
- 응답 스키마: `WeightPredictionResponse`
  - `predictions`, `evidence_level`, `note`
- 7-step 상수:
  - `KCAL_PER_KG_FAT = 7700.0`
  - `LOSS_CORRECTION = 0.85`
  - `GAIN_CORRECTION = 0.95`
  - `LONG_TERM_WARNING_DAYS = 90`
- 회귀 테스트 기준:
  - 50세 여성, 160cm, 68kg, 6500보, 1500kcal, 30일
  - BMR `1269.0`
  - TDEE 약 `1745.0`
  - daily balance 약 `-245`
  - cumulative balance 약 `-7350`
  - theoretical change 약 `-0.955`
  - corrected change 약 `-0.81`
  - predicted weight 약 `67.19`
  - 90일 예측 warning 유지

이 값은 Hall-lite 구현 전후에 반드시 동일해야 한다. selector를 route에 연결하더라도 기본 설정에서는 기존 `predict_weight_periods()` 결과와 byte-level에 가까운 구조 동일성을 유지한다.

---

## 3. 근거와 한계

확인한 공식/학술 근거:

- Hall et al. Lancet 2011 / CDC Stacks: <https://stacks.cdc.gov/view/cdc/33652>
- NIDDK Body Weight Planner research page: <https://www.niddk.nih.gov/research-funding/at-niddk/labs-branches/laboratory-biological-modeling/integrative-physiology-section/research/body-weight-planner>
- Hall Lancet web appendix PDF: <https://www.niddk.nih.gov/-/media/Files/BWP/Hall_Lancet_Web_Appendix.pdf>
- Mifflin-St Jeor REE equation: <https://doi.org/10.1093/ajcn/51.2.241>
- Deurenberg adult body-fat percentage equation: <https://pubmed.ncbi.nlm.nih.gov/2043597/>
- FastAPI dependency injection and OpenAPI integration: <https://fastapi.tiangolo.com/tutorial/dependencies/>

설계상 한계:

- 이 구현은 full Hall model 재현이 아니다.
- glycogen, extracellular fluid, sodium, macronutrient flux는 1차 구현에서 제외한다.
- Hall appendix는 초기 체지방 추정에 Jackson 계열 회귀식을 사용하지만, 현재 프로젝트 입력과 기존 문서 흐름은 Deurenberg adult BMI 식을 사용한다. 따라서 `body_composition.py`의 Deurenberg 사용은 **프로젝트용 근사**로 문서화하고, 측정 체지방률 필드가 들어오면 측정값을 우선한다.
- NIDDK 페이지는 2026-05-13 확인 시점에 "niddk.nih.gov 정보가 업데이트되지 않는다"는 상단 안내가 있다. 다만 research page는 Last Reviewed February 2025로 표시되고, Hall appendix PDF 링크를 공식적으로 제공한다.
- 수치 정확도 개선률은 베타 데이터 또는 논문 케이스 재현 검증 전까지 주장하지 않는다.

---

## 4. 목표 아키텍처

추가 파일:

```text
backend/src/prediction/
├── body_composition.py
├── hall.py
├── selector.py
└── weight.py              # 기존 7-step fallback 유지
```

테스트 파일:

```text
backend/tests/unit/prediction/
├── test_body_composition.py
├── test_hall.py
└── test_selector.py

backend/tests/integration/api/
├── test_phase1_api.py
├── test_openapi_examples.py
└── test_p1_api_contract.py
```

설정:

```python
feature_hall_lite_weight_prediction: bool = False
weight_prediction_engine: Literal["static_7step", "hall_lite", "auto"] = "static_7step"
```

선택 규칙:

- `feature_hall_lite_weight_prediction=false`: 항상 기존 `static_7step`
- `feature_hall_lite_weight_prediction=true`, `weight_prediction_engine="static_7step"`: 기존 `static_7step`
- `feature_hall_lite_weight_prediction=true`, `weight_prediction_engine="hall_lite"`: Hall-lite 사용
- `feature_hall_lite_weight_prediction=true`, `weight_prediction_engine="auto"`: 장기 기간만 Hall-lite 후보. 단, API contract 승인 전에는 route 기본값으로 사용하지 않는다.

---

## 5. `body_composition.py` 설계

역할:

- 현재 API 입력만으로 초기 FM/FFM을 추정한다.
- 측정 체지방률이 주입될 경우 추정값보다 우선한다.
- Hall-lite 외 다른 체성분 기반 예측에서도 재사용 가능하게 순수 함수로 둔다.

주요 타입:

```python
class BodyComposition(BaseModel):
    weight_kg: float
    fat_mass_kg: float
    fat_free_mass_kg: float
    body_fat_pct: float
    source: Literal["measured", "deurenberg"]
```

주요 함수:

```python
def estimate_body_fat_percentage(
    bmi: float,
    age: int,
    sex: Sex,
) -> float: ...

def estimate_initial_composition(
    weight_kg: float,
    height_cm: float,
    age: int,
    sex: Sex,
    measured_body_fat_pct: float | None = None,
) -> BodyComposition: ...
```

검증 규칙:

- `fat_mass_kg + fat_free_mass_kg == weight_kg`를 tolerance 내에서 만족해야 한다.
- Deurenberg adult formula는 성인 근사로만 사용한다.
- `age < 18`은 현재 API가 허용하더라도 Hall-lite selector에서 `static_7step` fallback을 우선한다.
- `body_fat_pct` clamp는 명시적으로 테스트한다. clamp 범위는 구현 시 문서와 테스트에 같이 고정한다.

---

## 6. `hall.py` 설계

역할:

- Hall-lite 일별 시뮬레이션의 순수 계산을 담당한다.
- API 스키마를 직접 알지 않는다.
- 내부 단위는 kJ/day, kJ/kg로 통일한다.

상수:

```python
KJ_PER_KCAL = 4.184
GAMMA_F_KJ_PER_KG_DAY = 13.0
GAMMA_L_KJ_PER_KG_DAY = 92.0
RHO_F_KJ_PER_KG = 39_500.0
RHO_L_KJ_PER_KG = 7_600.0
BETA_TEF = 0.10
BETA_AT = 0.14
TAU_AT_DAYS = 14.0
FORBES_C_MASS_KG = 10.4
FORBES_C_ENERGY_PARTITION_KG = FORBES_C_MASS_KG * RHO_L_KJ_PER_KG / RHO_F_KJ_PER_KG
```

단위 기준:

- API 입력 `daily_intake_kcal`은 진입점에서 즉시 kJ로 변환한다.
- Hall 내부의 `RMR`, `TEF`, `PAEE`, `AT`, `TDEE`, `energy_balance`는 모두 kJ/day다.
- 응답 또는 디버그 출력으로 나갈 때만 kcal로 역변환한다.
- 상수명에는 `_KJ_`, `_KCAL_` suffix를 넣어 단위 혼동을 줄인다.

BMR/TDEE baseline 보존:

현재 API는 사용자의 "변경 전 유지 섭취량"을 받지 않는다. 따라서 Hall-lite 초기 조건은 다음 가정을 둔다.

```text
initial_bmr_kcal = calculate_bmr(...)
initial_tdee_kcal = calculate_tdee(initial_bmr_kcal, daily_steps)
baseline_intake_kcal = initial_tdee_kcal
target_intake_kcal = request.daily_intake_kcal
```

그 다음 kJ로 변환한다.

```text
baseline_intake_kJ = initial_tdee_kcal * 4.184
target_intake_kJ = daily_intake_kcal * 4.184
initial_bmr_kJ = initial_bmr_kcal * 4.184
initial_tdee_kJ = initial_tdee_kcal * 4.184
baseline_tef_kJ = BETA_TEF * baseline_intake_kJ
baseline_paee_kJ = max(0, initial_tdee_kJ - initial_bmr_kJ - baseline_tef_kJ)
rmr_intercept_kJ = initial_bmr_kJ - (
    GAMMA_F_KJ_PER_KG_DAY * FM0 + GAMMA_L_KJ_PER_KG_DAY * FFM0
)
delta_ei_kJ = target_intake_kJ - baseline_intake_kJ
```

이렇게 하면 `target_intake_kcal == initial_tdee_kcal`인 유지 조건에서 day 0의 BMR/TDEE baseline이 보존된다.

일별 업데이트:

```text
RMR_D = rmr_intercept_kJ + gamma_F * FM_D + gamma_L * FFM_D
TEF_D = BETA_TEF * target_intake_kJ
PAEE_D = baseline_paee_kJ * (Weight_D / Weight_0)
target_AT_kJ = BETA_AT * delta_ei_kJ
AT_D+1 = AT_D + (target_AT_kJ - AT_D) / TAU_AT_DAYS
TDEE_D = RMR_D + TEF_D + PAEE_D + AT_D
energy_balance_D = target_intake_kJ - TDEE_D
```

FM/FFM partition:

```text
p_lean_energy = FORBES_C_ENERGY_PARTITION_KG / (
    FORBES_C_ENERGY_PARTITION_KG + FM_D
)
delta_ffm_kg = energy_balance_D * p_lean_energy / RHO_L_KJ_PER_KG
delta_fm_kg = energy_balance_D * (1 - p_lean_energy) / RHO_F_KJ_PER_KG
```

주의:

- Hall appendix의 energy partition 식은 `p = C/(C+F)`이고 `C = 10.4 kg * rho_L / rho_F`다. 에너지 수지를 `RHO_L`, `RHO_F`로 나누는 구현에서는 이 energy partition 상수를 사용한다.
- 기존 문서 일부의 `C = 10.4 kg` 표현은 Forbes mass-relationship 설명으로만 남기고, Hall-lite energy split 코드에는 직접 사용하지 않는다.
- Hall-lite golden value를 논문 재현값으로 부르지 않는다. 테스트명은 `sanity`, `unit`, `baseline` 중심으로 작성한다.

---

## 7. `selector.py` 설계

역할:

- route가 직접 Hall-lite를 알지 않게 한다.
- 기본 설정에서 기존 7-step fallback을 100% 유지한다.
- Hall-lite 실패나 입력 범위 미지원 시 안전하게 7-step으로 fallback한다.

주요 함수:

```python
def predict_weight_periods_selected(
    weight_kg: float,
    height_cm: float,
    age: int,
    sex: Sex,
    daily_steps: int,
    daily_intake_kcal: float,
    periods_days: list[int],
    feature_hall_lite_weight_prediction: bool = False,
    weight_prediction_engine: WeightPredictionEngine = WeightPredictionEngine.STATIC_7STEP,
) -> WeightPredictionResponse: ...
```

fallback 조건:

- feature flag가 false
- engine이 `static_7step`
- 만 18세 미만
- Hall-lite 내부 검증 실패
- FM/FFM guard가 발동해서 신체구성 결과가 비현실적임
- API response contract가 Hall-lite 결과를 표현하기에 불충분한 경우

API route 변경:

- `predict_weight()`에서 `Depends(get_settings)`로 설정을 주입한다.
- FastAPI 공식 문서 기준, dependency는 path operation에 주입되고 OpenAPI에도 통합된다.
- 기본 설정이 `static_7step`이므로 `/api/v1/predictions/weight`의 기존 요청/응답은 유지된다.

---

## 8. 테스트 플랜

### HL-0: 기존 기준선 고정

- `test_weight_prediction_50f_30days` 유지
- `test_weight_prediction_periods_includes_long_term_warning` 유지
- 신규 selector 테스트:
  - 기본 설정에서 `predict_weight_periods_selected(...) == predict_weight_periods(...)`
  - feature flag false이면 engine 값이 `hall_lite`여도 static fallback
- 신규 API 테스트:
  - 기본 환경에서 `/api/v1/predictions/weight` 응답 예시가 기존과 동일
  - OpenAPI request/response 필수 필드 변화 없음

### HL-1: body composition 단위 테스트

- Deurenberg formula 회귀 테스트
- measured body fat priority 테스트
- FM/FFM 합산 tolerance 테스트
- invalid/clamp boundary 테스트
- age < 18 selector fallback 테스트

### HL-2: kJ/kcal 및 Hall primitive 테스트

- `kcal_to_kj()` / `kj_to_kcal()` roundtrip
- `GAMMA_F_KJ_PER_KG_DAY`, `GAMMA_L_KJ_PER_KG_DAY` 단위명과 값 테스트
- `RHO_F_KJ_PER_KG`, `RHO_L_KJ_PER_KG` 값 테스트
- `target_intake_kcal == initial_tdee_kcal`이면 30일 후 체중 변화가 0에 가깝다는 유지 조건 테스트
- 감량 intake에서는 동일 입력의 90일 결과가 7-step보다 보수적인 방향인지 sanity test
- FM/FFM이 음수가 되지 않는 guard 테스트

### HL-3: selector/API contract 테스트

- 기본값 `feature_hall_lite_weight_prediction=false`
- 기본 route 결과가 기존 7-step과 동일
- Hall-lite enabled 경로는 unit/integration에서만 검증하고, 사용자 노출 문구는 "참고 시뮬레이션"으로 제한
- `docs/Nutrition-docs/23-p1-stabilization-plan.md`의 전체 backend test와 OpenAPI contract 확인에 포함

검증 명령:

```bash
cd yeong-Lemon-Aid/backend
pytest tests/unit/algorithms/test_metabolism_weight.py
pytest tests/unit/prediction/test_body_composition.py tests/unit/prediction/test_hall.py tests/unit/prediction/test_selector.py
pytest tests/integration/api/test_phase1_api.py tests/integration/api/test_openapi_examples.py tests/integration/api/test_p1_api_contract.py
```

---

## 9. 상세 구현 순서

> 구현 결과: Step 1~5는 코드와 테스트로 반영했다. Step 6 중 current status map 보정은 완료했으며, daily states를 사용자 응답으로 노출하는 contract 확장은 후속 PR 범위로 남긴다.

### Step 1. 기존 fallback 테스트 보강

목표:

- 구현 전에 현재 7-step 결과를 기준선으로 고정한다.
- selector 추가 후 기본 route가 동일하다는 테스트를 먼저 만든다.

작업:

- `tests/unit/prediction/test_selector.py` 생성
- 기본 selector가 `predict_weight_periods()`와 동일한 `WeightPredictionResponse`를 반환하는지 검증
- API contract 테스트에 `/api/v1/predictions/weight` 필수 필드 변화 없음 검증 추가

### Step 2. `body_composition.py`

목표:

- Hall-lite 초기 FM/FFM 추정을 API와 분리한다.

작업:

- `BodyComposition` 모델 추가
- `estimate_body_fat_percentage()` 추가
- `estimate_initial_composition()` 추가
- Google-style docstring 작성
- Deurenberg는 "project approximation"으로 명시

### Step 3. `hall.py`

목표:

- 단위 변환과 baseline 보존이 분명한 Hall-lite primitive를 만든다.

작업:

- 단위 변환 함수 추가
- `HallLiteState`, `HallLiteResult` 모델 추가
- `initialize_hall_state()` 추가
- `step_one_day()` 추가
- `predict_with_hall()` 추가
- 논문 재현이 아닌 project sanity 테스트로만 수치 고정

### Step 4. `selector.py`

목표:

- route와 모델 선택 로직을 분리한다.
- 기본값은 반드시 static 7-step이다.

작업:

- `WeightPredictionEngine` enum 추가
- `predict_weight_periods_selected()` 추가
- feature flag false fallback 테스트 작성
- Hall-lite 실패 fallback 테스트 작성

### Step 5. route/config 연결

목표:

- `/api/v1/predictions/weight` 호환성을 유지하면서 selector를 주입한다.

작업:

- `Settings`에 `feature_hall_lite_weight_prediction=false` 추가
- `Settings`에 `weight_prediction_engine="static_7step"` 추가
- `predict_weight()`에서 `settings: Settings = Depends(get_settings)` 주입
- route는 selector만 호출
- 기본 환경 API 결과가 기존과 동일함을 통합 테스트로 확인

### Step 6. 문서와 contract 보정

목표:

- 구현된 코드와 문서의 용어가 충돌하지 않게 한다.

작업:

- `docs/Nutrition-docs/dev-guides/14-hall-dynamic-model.md` selector 기준 업데이트
- `docs/Nutrition-docs/22-current-implementation-status-map.md`에 구현 후 상태 반영
- OpenAPI examples에 감량 보장, 질환 개선 표현이 없는지 확인

---

## 10. supplement image flow와의 독립성

독립 파일:

- `backend/src/prediction/body_composition.py`
- `backend/src/prediction/hall.py`
- `backend/src/prediction/selector.py`
- `backend/tests/unit/prediction/*`

공유 가능성이 있는 파일:

- `backend/src/config.py`
- `backend/src/api/v1/predictions.py`
- `backend/tests/integration/api/test_openapi_examples.py`

충돌 회피 원칙:

- supplement OCR/LLM/vision/learning 모듈은 import하지 않는다.
- 이미지/학습 feature flag와 Hall-lite feature flag는 분리한다.
- DB migration이 필요 없다.
- 개인정보 consent flow와 연결하지 않는다.

따라서 Hall-lite는 supplement image flow와 병렬 개발 가능한 후보이며, 충돌 지점은 `config.py`와 API contract 테스트 정도로 제한된다.

---

## 11. 완료 기준

- [x] 기존 7-step 테스트가 그대로 통과한다.
- [x] 기본 설정에서 `/api/v1/predictions/weight` 결과가 기존과 동일하다.
- [x] Hall-lite 코드는 feature flag false 기본값 뒤에 숨어 있다.
- [x] kJ/kcal 변환과 상수 단위 테스트가 있다.
- [x] BMR/TDEE baseline 보존 테스트가 있다.
- [x] selector fallback 테스트가 있다.
- [x] OpenAPI contract 테스트가 있다.
- [x] 사용자 노출 문구는 "참고 시뮬레이션" 수준으로 제한된다.
- [x] 구현 후에도 supplement image/OCR/LLM 테스트와 import 경계가 섞이지 않는다.

---

## 12. 커밋 단위 제안

```text
test(weight): freeze static 7-step prediction fallback

Why:
Hall-lite must be added without changing the existing /api/v1/predictions/weight
contract or the current static 7-step outputs.
```

```text
feat(weight): add body composition estimator for hall-lite

Why:
Hall-lite needs an explicit FM/FFM initialization layer before dynamic simulation can
be implemented, and keeping it separate makes the model testable without API changes.
```

```text
feat(weight): add hall-lite dynamic simulation primitives

Why:
Longer-range weight prediction needs kJ-based dynamic energy balance calculations
while preserving the existing BMR/TDEE baseline.
```

```text
feat(weight): route predictions through safe model selector

Why:
The selector allows Hall-lite to be developed behind a disabled feature flag while
keeping the legacy 7-step API behavior as the default fallback.
```
