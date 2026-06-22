# 04. 7-step 체중 예측 알고리즘 평가 및 수정안

> **문서 목적**: Lemon-Aid 헬스케어 프로젝트의 `07-core-algorithm.md`에 정의된 7단계 체중 예측 알고리즘을, 영양생리학·대사학 분야의 1차 문헌(Wishnofsky 1958, Hall et al. 2011 Lancet, Fothergill et al. 2016 Obesity, NIH NIDDK)을 근거로 평가하고, 단기·중기·장기 예측에서의 한계를 식별한 뒤 수정안을 제시한다.
>
> **작성일**: 2026-05-26
> **대상 파일**: `core-algorithm/07-core-algorithm.md` (현 7-step 구현)

---

## 1. 현재 구현 요약

| Step | 수식 / 처리 | 비고 |
|---|---|---|
| 1 | **BMR** = Mifflin-St Jeor 식 | 성별·체중·키·나이 입력 |
| 2 | **TDEE** = BMR × 활동계수 (1.2 ~ 1.9) | 활동수준 자기보고 |
| 3 | **일일 수지** = 섭취 kcal − TDEE | + = 잉여, − = 적자 |
| 4 | **N일 누적** = Σ(일일 수지) | 단순 합산 |
| 5 | **이론 변화량** = 누적 ÷ **7,700 kcal/kg** | Wishnofsky 1958 규칙 |
| 6 | **현실 보정** | 감량 × 0.85, 증량 × 0.95 (회사 가이드 휴리스틱) |
| 7 | **예측 체중** = 시작 체중 + 보정 변화량 | 사용자에게 표시 |

핵심 가정 두 가지:
1. **7,700 kcal/kg**은 시간·체성분·대사 적응과 무관하게 일정한 상수.
2. **0.85 / 0.95** 보정은 모든 사용자(연령·질환·체성분 무관)에게 동일하게 적용.

---

## 2. 논문·공식 자료 근거

### 2.1 Wishnofsky 1958 규칙

- **원논문**: Wishnofsky M. "Caloric equivalents of gained or lost weight." *Am J Clin Nutr*. 1958;6(5):542–546.
  - PubMed: [PMID 13594881](https://pubmed.ncbi.nlm.nih.gov/13594881/)
- **계산 근거**: 1 lb 지방조직 ≈ 3,500 kcal → 1 kg ≈ **7,716 kcal** (실무에선 7,700으로 반올림).
- **원래의 가정**: 감량되는 체중 중 약 **87%가 지방조직**, **13%가 제지방조직(lean)**이라는 1950년대 비만환자 대상 대사 연구에 근거.
- ⚠️ **정적(static) 모델의 한계**:
  - 체중이 감소하면 BMR과 활동대사량(TEE)도 함께 감소함에도 불구하고 TDEE를 *고정 상수*로 가정.
  - 감량 기간이 길어질수록 실측 감량량과 예측치의 괴리가 누적 → **과대 예측**.

> Thomas DM et al. *"Why is the 3500 kcal per pound weight loss rule wrong?"* Int J Obes. 2013;37:1611–1613. [PMC3859816](https://pmc.ncbi.nlm.nih.gov/articles/PMC3859816/) — "이 규칙은 에너지 균형을 *정적 양*으로 가정하지만, 실제로는 동적으로 변화한다."

### 2.2 Hall et al. 2011 The Lancet — 동적(dynamic) 모델

- **원논문**: Hall KD, Sacks G, Chandramohan D, Chow CC, Wang YC, Gortmaker SL, Swinburn BA. "Quantification of the effect of energy imbalance on bodyweight." *Lancet*. 2011 Aug 27;378(9793):826–837.
  - **DOI**: [10.1016/S0140-6736(11)60812-X](https://doi.org/10.1016/S0140-6736(11)60812-X)
  - PMC 전문: [PMC3880593](https://pmc.ncbi.nlm.nih.gov/articles/PMC3880593/)
- **핵심 경험식 (Rule of Thumb)**:
  > 성인의 경우 일일 섭취 에너지를 **100 kJ/day (≈24 kcal/day)** 줄이면 *최종적으로* 약 **1 kg**의 체중 감소가 달성된다. **절반(50%)은 약 1년**, **95%는 약 3년**에 도달한다.
- **정적 7,700 규칙 대비 결과**:
  - 동일한 일일 적자 (예: 2 MJ/day ≈ 478 kcal/day)에 대해, 정적 규칙은 **1년차에 ~22 kg** 감량을 예측하지만, 동적 모델은 그 **절반 수준**(약 11 kg)을 예측한다. **정적 규칙의 과대평가율 ≈ 100%**.
- **plateau 해석**: 6~8개월 시점에 흔히 관찰되는 정체기는 "대사 셧다운"이 아니라 **순응도 저하 + 점진적 대사 적응**의 누적 효과로 설명된다.

### 2.3 NIH Body Weight Planner (BWP)

- **공식 사이트**: <https://www.niddk.nih.gov/health-information/weight-management/body-weight-planner>
- **연구 배경**: <https://www.niddk.nih.gov/research-funding/at-niddk/labs-branches/laboratory-biological-modeling/integrative-physiology-section/research/body-weight-planner>
- **운영 주체**: NIDDK Laboratory of Biological Modeling, Integrative Physiology Section (Kevin Hall 박사).
- **모델**: Hall 2011 Lancet 동적 모델을 웹 기반으로 구현. 체중 변화에 따른 RMR·TEE의 동적 변화를 반영.
- **입력**: 성별, 나이, 키, 현재 체중, 활동 수준, 목표 체중, 목표 기간 → 출력: 목표 달성에 필요한 일일 섭취 칼로리와 활동량.
- **제한**: 성인(≥18세) 대상. 임신·수유부 제외. 어린이는 별도 모델(NIDDK 어린이용 BWP).
- **공개 API**는 제공되지 않으며, 모델 방정식 자체는 논문 부록(Web Appendix)에 공개되어 직접 구현 가능.

### 2.4 적응성 열생성 (Adaptive Thermogenesis)

- **개념**: 체중 감량 시 BMR이 *단순 체중 비례 감소를 넘어서* 추가로 떨어지는 현상. 갑상선호르몬·렙틴·교감신경 활성도의 하향 조절이 매개.
- **대표 임상 증거**: Fothergill E, Guo J, Howard L, Kerns JC, Knuth ND, Brychta R, Chen KY, Skarulis MC, Walter M, Walter PJ, Hall KD. *"Persistent metabolic adaptation 6 years after 'The Biggest Loser' competition."* Obesity. 2016;24(8):1612–1619.
  - DOI: [10.1002/oby.21538](https://doi.org/10.1002/oby.21538)
  - PubMed: [PMID 27136388](https://pubmed.ncbi.nlm.nih.gov/27136388/)
- **수치 요약** (14명, 평균 58 kg 감량 후):
  - 대회 직후 RMR **610 ± 483 kcal/day** 감소.
  - **6년 후** 평균 **41 kg 재증가**했음에도 RMR은 베이스라인 대비 **704 ± 427 kcal/day** 여전히 낮음.
  - 6년 시점 측정된 *대사적응(metabolic adaptation)* = **−499 ± 207 kcal/day** (체성분으로 설명되지 않는 잔여 감소).
- **시사점**: 감량 후 *체중을 유지하는 것 자체가* 동일 체중의 비감량자보다 ~500 kcal/day 적게 먹어야 가능하다는 의미. 7,700 kcal/kg을 사용한 *유지기 예측*은 비현실적.

### 2.5 단기 vs 장기 체중 변화 — 1주차의 "물 빠짐" 효과

- 다이어트 초기 (24시간~수일):
  - 근·간 글리코겐 (성인 평균 ~500 g) + 결합 수분 (1 g 글리코겐 ≈ 3 g 물) 손실로 **최대 5 kg 수준의 비-지방 감량** 가능.
  - 첫 며칠간 감량 체중의 **약 70%가 수분·글리코겐**, 25%가 지방, 5%가 단백질로 추정 (저탄수·케토 식이에서 특히 현저).
- 연구적으로 측정된 *kcal/kg 환산값*:
  - **4주차 측정값 ≈ 4,858 ± 388 kcal/kg** (Heymsfield et al., *Energy content of weight loss*, [PMC3810417](https://pmc.ncbi.nlm.nih.gov/articles/PMC3810417/)) — Wishnofsky 7,700 kcal/kg의 **약 63%**.
  - 즉 **단기에는 7,700이 오히려 과대 산정** (체수분이 빠지면서 같은 칼로리 적자로 더 많은 체중이 빠짐). → 단기 예측에서는 7,700을 그대로 쓰면 "예측보다 더 빠르게 빠진다"는 사용자 경험 발생.
- 장기 (3개월~):
  - 글리코겐·체수분이 새 정상상태로 안정 + 적응성 열생성 → **7,700 kcal/kg이 과소 산정** (정적 규칙은 체중 비례 BMR 감소를 무시하므로 *누적 적자를 과대평가*하여 결과적으로 *감량량을 과대예측*).

### 2.6 0.85 / 0.95 보정 계수의 근거 검토

- 회사 가이드의 **휴리스틱**. 공개 학술 출처는 확인되지 않음.
- 정성적 해석:
  - **0.85 (감량)**: 적응성 열생성 + 순응도 저하를 반영한 일종의 "마찰계수". 1~3개월 구간에서 동적 모델과 *우연히 유사한* 결과를 낼 수는 있으나, 그 이상 기간에서는 여전히 과대평가.
  - **0.95 (증량)**: 증량 시도에서는 일반적으로 추가 섭취 칼로리가 *낮은 효율*로 체중 증가에 기여하나(식이성 열생성 약 8~10% + 신체활동 증가), 0.95라는 값의 *임상적 출처는 불분명*.
- **결론**: 0.85/0.95는 "단순 7,700 모델보다는 보수적인 예측을 내는" 안전장치 역할은 하지만, *근거 수준은 낮음*.

---

## 3. 평가

### 3.1 강점

1. **단순성** — 4개 입력(키·체중·나이·성별)+활동수준+섭취 칼로리만으로 결과 산출. UX 설명이 매우 직관적.
2. **단기(1~4주) 예측 활용성** — 글리코겐·수분 효과를 0.85 보정으로 *부분적으로* 흡수하면서, 실용적 정확도 확보 가능.
3. **재현성** — 결정론적이므로 단위 테스트로 회귀 검증 용이.
4. **개인 데이터 의존성 낮음** — 추가 측정장비(체성분계 등) 불필요.

### 3.2 약점

1. **장기(3개월+) 과대평가** — Hall 2011 기준 최대 ~2배 과대.
2. **적응성 열생성 미반영** — Fothergill 2016이 보여준 −500 kcal/day 수준의 잔여 적응을 모델 내에서 표현할 변수가 없음.
3. **0.85/0.95의 근거 부재** — 임상적 검증 또는 자체 데이터 학습 결과로 대체 필요.
4. **체성분 변화 미반영** — 감량 시 지방 vs 제지방 비율(Forbes equation 등), 증량 시 근·지방 비율을 다루지 않음.
5. **개인 차이 미반영** — 동일 BMI·동일 적자라도 유전·약물·질환에 따라 반응이 매우 다름.
6. **만성질환자 분기 없음** — 갑상선·당뇨·스테로이드 복용·신부전 등에서는 가정 자체가 무너짐 (§4.4 참조).

---

## 4. 수정 권고

### 4.1 예측 기간별 모델 분기

| 예측 기간 | 권장 모델 | 핵심 보정 | 근거 |
|---|---|---|---|
| **1주 (≤7일)** | 7,700 × **0.55** (감량) / × 0.95 (증량) | 글리코겐·체수분 손실 반영 | Heymsfield 4주 측정 4,858 kcal/kg, Justin Owings/Pressbooks 70% 수분설 |
| **2주 ~ 1개월** | 7,700 × **0.85** (감량) / × 0.95 (증량) | 회사 가이드 휴리스틱 유지 | 임상 휴리스틱 + 단기 동적 모델과 근사 |
| **1 ~ 3개월** | **Hall 단순화 식** 사용 | RMR을 매주 재계산 | Hall 2011 Lancet, Eq. (1~3) |
| **3개월 이상** | **Hall 완전 동적 모델 (NIH BWP 방식)** | 적응성 열생성(−20 ~ −30 kcal/day per kg lost) 추가 | Fothergill 2016, NIH BWP |

### 4.2 Hall 모델 도입 옵션 (Phase 2~3 로드맵)

**옵션 A — 자체 구현 (권장)**
- Hall 2011 Lancet의 Web Appendix에 공개된 ODE 방정식을 직접 구현.
- 입력: 성별, 나이, 키, 현재 체중, 체지방률 추정, PAL(활동수준), 일일 섭취 칼로리.
- 출력: 일별 체중·체지방·제지방 시계열.

**옵션 B — NIH BWP 웹 인터페이스 안내**
- 공개 API가 없으므로 백엔드 통합은 불가능.
- 대신 *고난도 예측이 필요한 사용자*에게 NIH BWP 링크를 안내하는 UI 분기.

**옵션 C — 간이 Rule-of-Thumb (Phase 1 MVP)**
- 장기(3개월+) 안내에서: "**일일 24 kcal/day 적자가 약 1년 후 0.5 kg, 3년 후 1 kg에 도달**" (Hall 2011)이라는 *기대 변화율 캡션*만 표시. 수치 예측은 1개월까지만.

**적응성 열생성 보정식 (간이)**
```
adaptive_kcal_per_day = -20 ~ -30 × Δweight_kg   (감량 시)
adjusted_TDEE         = base_TDEE + adaptive_kcal_per_day
```
※ Δweight는 음수(감량) → 결과적으로 TDEE 추가 감소. Fothergill 2016의 잔여 적응 −499 kcal / 평균 ~25 kg 유지 감량 ≈ −20 kcal/day per kg lost 수준에서 시작.

### 4.3 UX 표시 권고

1. **"예측 체중"이 아니라 "기대 체중 범위(±)"로 표기.**
   - 예: `1개월 후 -2.3 kg (-1.7 ~ -2.9 kg)`
2. **신뢰도 등급을 시각화.**
   - 1주: 신뢰도 高 (단, 체수분 변동성 별도 안내)
   - 1개월: 신뢰도 中
   - 3개월+: 신뢰도 低, 동적 모델 사용 명시
3. **사용자 실측 체중을 베이지안 갱신에 사용 (Phase 3+).**
   - 매주 입력되는 실측 체중으로 개인별 *유효 kcal/kg* 사후분포 갱신.
4. **"예측 미스매치" 경고 시스템.**
   - 실측이 예측 범위를 2주 연속 벗어나면 *알고리즘 한계 가능성*을 사용자에게 알리고, 만성질환 체크리스트를 다시 묻거나 전문가 상담 안내.

### 4.4 만성질환자 분기 — 핵심 권고

**왜 만성질환자에게 일반 7-step을 그대로 적용하면 안 되는가**:

| 질환 / 약물 | 일반 공식이 실패하는 이유 | 권장 분기 처리 |
|---|---|---|
| **갑상선기능저하증 (hypothyroidism)** | BMR이 ~10~30% 낮아짐, 체액·점액성 부종 동반 → Mifflin-St Jeor가 *실제 TDEE를 과대평가*. 치료(LT4) 시작·용량 조정 시점에 따라 같은 사람도 BMR이 크게 변동. ([ATA Thyroid & Weight](https://www.thyroid.org/thyroid-and-weight/)) | 진단 명시 시 *예측 비활성화* 또는 BMR 보정계수 ×0.75~0.90 옵션을 의료진 입력으로만 활성화 |
| **갑상선기능항진증 (hyperthyroidism)** | BMR 20~40% 상승, 의도치 않은 감량 → 7-step은 *추가 감량*을 권하는 위험한 결과를 낼 수 있음 | 예측 비활성화 + 체중 *모니터링*만 수행 |
| **2형 당뇨 + 인슐린/SGLT2/GLP-1** | 인슐린은 지방합성·수분저류 촉진(체중 +). SGLT2 억제제는 삼투성 이뇨로 단기 체중 −. GLP-1 (semaglutide 등)은 식욕·위배출 직접 억제 → 섭취 입력 자체가 부정확. | 약물 클래스별 안내 카드 표시, 단기(2주) 예측만 제공, 장기 예측은 비활성화 |
| **부신피질호르몬(글루코코르티코이드, 예: prednisone)** | 알도스테론 유사 작용 → 나트륨·수분 저류로 첫 주 2~5 lb (~1~2 kg) 체중 증가는 *수분*; 동시에 식욕 자극으로 *지방 증가*. 7-step의 "잉여 kcal → 체중"이 *체액 변화와 분리되지 않음*. ([UCSF Health](https://www.ucsfhealth.org/education/ild-nutrition-manual-prednisone-and-weight-gain)) | 복용 사실 입력 시 예측 비활성화 + "체중 변화 = 수분 + 지방" 분리 설명 |
| **만성신부전 / 투석** | 체액 균형이 일반인과 완전히 다름. 일일 체중 ±2 kg 변동이 정상. *섭취 칼로리 ↔ 체중*의 인과 자체가 약함. | 절대 예측 금지, "투석 전후 체중 변화 ≠ 지방 변화" 명시 |
| **PCOS (다낭성 난소 증후군)** | 인슐린 저항성 + *체중 감량 시 더 큰 대사 적응* 보고. 동일 적자에 대해 감량 폭이 일반인보다 작음. ([Frontiers in Nutrition 2025](https://www.frontiersin.org/journals/nutrition/articles/10.3389/fnut.2025.1578459/full)) | 0.85 → 0.75 수준의 더 보수적 보정 옵션 + 인슐린 저항성 식단 가이드 연결 |
| **심부전 / 간경변** | 부종·복수 → 체중이 수분에 지배됨 | 예측 비활성화 |

**핵심 원칙**:

> "예측 체중"은 사용자가 *우리에게 거는 약속*으로 인식된다. 만성질환자에게 일반 공식을 적용해 어긋나면, 그것은 단순 부정확이 아니라 **약속 미달 경험**으로 누적되어 *사용자 신뢰를 회복 불가능하게 손상*시킨다.

따라서 만성질환 체크리스트는:
1. **온보딩 단계에서 강제 입력** (스킵 가능, 단 미입력 시 예측 신뢰도 자동 강등).
2. 해당 질환이 체크되면 **7-step 예측 비활성화** + "전문의 상담" 안내 카드로 대체.
3. 의료진 모드(별도 권한)에서는 *질환별 보정 옵션*을 의사가 선택하여 활성화 가능.

### 4.5 수정된 의사 코드

```python
from dataclasses import dataclass
from enum import Enum

class Horizon(Enum):
    SHORT = "1week"      # ≤ 7일
    MID   = "1month"     # 8일 ~ 30일
    LONG  = "3month"     # 31일 ~ 90일
    EXTRA = "long"       # > 90일

@dataclass
class ChronicCondition:
    hypothyroidism: bool = False
    hyperthyroidism: bool = False
    diabetes_on_insulin: bool = False
    diabetes_on_glp1: bool = False
    on_corticosteroid: bool = False
    ckd_dialysis: bool = False
    heart_failure_edema: bool = False
    pcos: bool = False

def predict_weight(
    *,
    start_weight_kg: float,
    height_cm: float,
    age: int,
    sex: str,
    activity_factor: float,
    daily_intake_kcal: float,
    horizon_days: int,
    conditions: ChronicCondition,
) -> dict:
    # 1) 만성질환 분기 — 가장 먼저
    block = (
        conditions.ckd_dialysis
        or conditions.heart_failure_edema
        or conditions.hyperthyroidism
    )
    if block:
        return {
            "mode": "DISABLED",
            "reason": "체액 균형 또는 대사율이 일반 공식 적용 범위를 벗어남",
            "recommendation": "전문의 상담 권장",
        }

    # 2) BMR (Mifflin-St Jeor) + 질환별 BMR 보정
    bmr = mifflin_st_jeor(start_weight_kg, height_cm, age, sex)
    if conditions.hypothyroidism:
        bmr *= 0.85           # 보수적 가정
    if conditions.on_corticosteroid:
        # 체중 변화 ≠ 지방 변화 → 예측은 가능하나 신뢰도 낮음
        confidence_penalty = True
    tdee = bmr * activity_factor

    # 3) 누적 적자
    daily_balance = daily_intake_kcal - tdee
    cumulative_kcal = daily_balance * horizon_days

    # 4) 기간별 kcal/kg 계수 선택
    horizon = classify(horizon_days)
    if horizon == Horizon.SHORT:
        kcal_per_kg = 7700 * 0.55 if daily_balance < 0 else 7700 * 0.95
        model_note = "단기: 글리코겐·수분 손실 반영"
    elif horizon == Horizon.MID:
        kcal_per_kg = 7700 * 0.85 if daily_balance < 0 else 7700 * 0.95
        model_note = "중기: 회사 가이드 휴리스틱"
    else:
        # 5) 장기 — Hall 동적 모델로 위임
        return hall_dynamic_simulate(
            start_weight_kg, height_cm, age, sex,
            activity_factor, daily_intake_kcal, horizon_days,
            conditions=conditions,
        )

    # PCOS 추가 보정
    if conditions.pcos and daily_balance < 0:
        kcal_per_kg *= (7700 * 0.75) / (7700 * 0.85)  # 보수적 강화

    delta_kg = cumulative_kcal / kcal_per_kg
    predicted = start_weight_kg + delta_kg

    # 6) 신뢰구간 — 단순 ±10% (Phase 1)
    band = abs(delta_kg) * 0.10
    return {
        "mode": "STATIC_HEURISTIC",
        "predicted_kg": predicted,
        "range_kg": (predicted - band, predicted + band),
        "model_note": model_note,
        "confidence": "low" if conditions.on_corticosteroid else "mid",
    }


def hall_dynamic_simulate(...):
    """
    Hall 2011 Lancet 동적 모델 ODE를 일별로 적분.
    적응성 열생성: adaptive = -20 kcal/day per kg lost (Fothergill 2016 기반 초기값).
    """
    ...
```

---

## 5. 근거 수준 재평가

근거 수준 등급: **A**(다수 RCT/메타분석), **B**(단일 대규모 임상), **C**(전문가 합의/휴리스틱), **D**(추정).

| 항목 | 이전 등급 | 수정 후 등급 | 비고 |
|---|---|---|---|
| Mifflin-St Jeor BMR | B | B | 일반인 대상으로 검증됨, 변경 없음 |
| 7,700 kcal/kg (정적) | B/C | **C** (단기에만 한정) | 장기는 부정확함이 다수 문헌으로 확인됨 |
| 0.85 / 0.95 보정 | C | **C → D 강등 후 데이터로 대체 예정** | 학술 출처 부재, Phase 3에서 실측 데이터 학습으로 대체 |
| Hall 동적 모델 도입 | — | **A** (3개월+ 예측) | Lancet 게재 + NIH 공식 도구 채택 |
| 적응성 열생성 보정 (−20 kcal/day per kg) | — | **B** | Fothergill 2016 유일 대규모 장기추적 |
| 만성질환자 분기 | — | **A** (안전성 측면) | 임상 가이드라인 일치 |

---

## 6. 참고 문헌

### 핵심 문헌
- **[Wishnofsky 1958]** Wishnofsky M. *Caloric equivalents of gained or lost weight.* Am J Clin Nutr. 1958;6(5):542–546. [PubMed 13594881](https://pubmed.ncbi.nlm.nih.gov/13594881/)
- **[Hall 2011 Lancet]** Hall KD, Sacks G, Chandramohan D, Chow CC, Wang YC, Gortmaker SL, Swinburn BA. *Quantification of the effect of energy imbalance on bodyweight.* Lancet. 2011;378(9793):826–837. DOI: [10.1016/S0140-6736(11)60812-X](https://doi.org/10.1016/S0140-6736(11)60812-X) · [PMC3880593](https://pmc.ncbi.nlm.nih.gov/articles/PMC3880593/)
- **[Thomas 2013]** Thomas DM et al. *Why is the 3500 kcal per pound weight loss rule wrong?* Int J Obes. 2013;37:1611–1613. [PMC3859816](https://pmc.ncbi.nlm.nih.gov/articles/PMC3859816/)
- **[Fothergill 2016]** Fothergill E et al. *Persistent metabolic adaptation 6 years after "The Biggest Loser" competition.* Obesity. 2016;24(8):1612–1619. DOI: [10.1002/oby.21538](https://doi.org/10.1002/oby.21538) · [PubMed 27136388](https://pubmed.ncbi.nlm.nih.gov/27136388/)
- **[Hall — 3500 rule critique]** Hall KD, Chow CC. *Why is the 3500 kcal per pound weight loss rule wrong?* Int J Obes. 2013. [Nature](https://www.nature.com/articles/ijo2013112)
- **[Heymsfield Energy Content]** *Energy content of weight loss: kinetic features during voluntary caloric restriction.* [PMC3810417](https://pmc.ncbi.nlm.nih.gov/articles/PMC3810417/) — 4주차 측정 4,858 kcal/kg.

### 공식 도구 / 기관 자료
- **NIH NIDDK Body Weight Planner**: <https://www.niddk.nih.gov/health-information/weight-management/body-weight-planner>
- **NIDDK Research Behind the BWP**: <https://www.niddk.nih.gov/research-funding/at-niddk/labs-branches/laboratory-biological-modeling/integrative-physiology-section/research/body-weight-planner>

### 만성질환 관련
- **갑상선·체중**: American Thyroid Association. *Thyroid and Weight.* <https://www.thyroid.org/thyroid-and-weight/> · [브로셔 PDF](https://www.thyroid.org/wp-content/uploads/patients/brochures/Thyroid_and_Weight.pdf)
- **PCOS 영양·체중**: *Optimizing carbohydrate quality: a path to better health for women with PCOS.* Front Nutr. 2025. <https://www.frontiersin.org/journals/nutrition/articles/10.3389/fnut.2025.1578459/full>
- **부신피질호르몬·체중**: UCSF Health, *ILD Nutrition Manual: Prednisone and Weight Gain.* <https://www.ucsfhealth.org/education/ild-nutrition-manual-prednisone-and-weight-gain>

### 보조 자료
- *Time to Correctly Predict the Amount of Weight Loss with Dieting.* J Acad Nutr Diet. 2014. [PMC4035446](https://pmc.ncbi.nlm.nih.gov/articles/PMC4035446/)
- *Can a weight loss of one pound a week be achieved with a 3,500-kcal deficit?* [PMC4024447](https://pmc.ncbi.nlm.nih.gov/articles/PMC4024447/)

---

## 부록: 다음 단계 (Action Items)

1. **Phase 1 (즉시)**: 만성질환 온보딩 체크리스트 추가 + 해당 사용자에 대한 예측 비활성화 분기 구현.
2. **Phase 1 (즉시)**: 1주 예측에서 7,700 → 7,700×0.55 옵션 A/B 테스트 설계.
3. **Phase 2 (1~2분기)**: Hall 2011 동적 모델 자체 구현 (Web Appendix ODE 이식). 3개월+ 예측을 동적 모델로 전환.
4. **Phase 3 (3~4분기)**: 사용자 실측 체중 → 베이지안 갱신 파이프라인. 0.85/0.95를 *개인별 학습 계수*로 대체.
5. **상시**: 예측-실측 미스매치 ≥ 2주 연속 시 알고리즘 한계 안내 카드.
