# 03. BMR / TDEE 알고리즘 평가 및 수정안

> **목적**: Lemon-Aid가 현재 사용 중인 BMR(Mifflin-St Jeor) + TDEE(걸음수 기반 활동계수) 알고리즘을 1차 문헌과 공식 자료에 비추어 평가하고, 한국인·만성질환자를 고려한 단계적 개선안을 제안한다.
> **작성일**: 2026-05-26
> **근거 수준 표기**: A(다수 RCT/메타분석), B(관찰연구·합의문), C(전문가 의견)

---

## 1. 현재 구현 요약 (07-core-algorithm.md 기준)

### 1.1 BMR — Mifflin-St Jeor (1990)
```
남성:  BMR = 10 × W(kg) + 6.25 × H(cm) − 5 × A(yr) + 5
여성:  BMR = 10 × W(kg) + 6.25 × H(cm) − 5 × A(yr) − 161
```

### 1.2 TDEE — 걸음수 기반 활동계수
| 일일 걸음수 | 활동계수 (PAL 대응) | Tudor-Locke 분류 |
|---|---|---|
| < 5,000 보 | 1.200 | Sedentary |
| 5,000 – 7,499 | 1.375 | Low active |
| 7,500 – 9,999 | 1.550 | Somewhat active |
| 10,000 – 12,499 | 1.725 | Active |
| ≥ 12,500 | 1.900 | Highly active |

`TDEE(kcal/day) = BMR × PAL`

---

## 2. BMR 공식 비교

### 2.1 Mifflin-St Jeor (1990) — 현재 채택 공식
- **원논문**: Mifflin MD, St Jeor ST, Hill LA, Scott BJ, Daugherty SA, Koh YO. *A new predictive equation for resting energy expenditure in healthy individuals*. **Am J Clin Nutr** 1990;51(2):241–7. **DOI: 10.1093/ajcn/51.2.241**.
- **표본**: 미국 성인 498명 (정상체중 264명 / 비만 234명, 남성 251 / 여성 247, 연령 19–78세). 간접열량측정(indirect calorimetry)으로 REE 측정, 회귀계수 도출 (R²=0.71).
- **원본 공식 (성별 통합)**:
  `REE = 9.99·W + 6.25·H − 4.92·A + 166·sex − 161` (남=1, 여=0)
  → 임상에서는 성별 분리 공식 (현재 Lemon-Aid 형태)으로 통용.
- **정확도**: ADA(미국영양사협회) 2005 체계적 검토(JADA, Frankenfield 2005)에서 비비만·비만 성인 양쪽 모두 *측정치 ± 10% 이내 일치율이 가장 높은 공식*으로 보고 (정상체중 약 82%, 비만 약 70% 일치).

### 2.2 Harris-Benedict (1919) / Roza-Shizgal 수정판 (1984)
- **원논문 (1919)**: Harris JA, Benedict FG. *A Biometric Study of Basal Metabolism in Man*. Carnegie Institution of Washington Publication No.279, 1919. 표본 239명 (남 136 / 여 108, 16–63세) — 100년 전 백인 위주, 표본 노후화.
- **수정판 (1984)**: Roza AM, Shizgal HM. *The Harris-Benedict equation reevaluated: resting energy requirements and the body cell mass*. **Am J Clin Nutr** 1984;40(1):168–82. **DOI: 10.1093/ajcn/40.1.168**.
  ```
  남성: BMR = 88.362 + 13.397·W + 4.799·H − 5.677·A
  여성: BMR = 447.593 + 9.247·W + 3.098·H − 4.330·A
  ```
- **정확도**: 측정치 ±10% 일치율 약 60% — Mifflin보다 약 10–15%p 낮음. 정상체중에서는 BMR을 평균 5–15% **과대평가** 경향 (Frankenfield 2005).

### 2.3 Katch-McArdle (체지방률 기반)
- **공식**: `BMR = 370 + 21.6 × LBM(kg)`
  - LBM = W × (1 − bodyFat%)
- **장점**: 근육량이 매우 많거나 매우 적은 사용자에서 체중·신장 기반 공식보다 정확.
- **한계**: 정확한 체지방률 입력이 필요 (BIA·DEXA·체지방계). 자가측정 BMI/체중만 가지고는 적용 불가.

### 2.4 Cunningham (LBM)
- **원논문**: Cunningham JJ. *Body composition as a determinant of energy expenditure: a synthetic review and a proposed general prediction equation*. **Am J Clin Nutr** 1991;54(6):963–9. **DOI: 10.1093/ajcn/54.6.963**.
- **공식**: `BMR = 500 + 22 × LBM(kg)` (1980 원형) / `BMR = 370 + 21.6 × LBM` (1991 갱신, Katch-McArdle와 수치 일치).
- **사용**: 운동선수·근육량이 많은 사용자에서 Mifflin보다 5–10% 정확.

### 2.5 WHO / FAO / UNU 2001 (Schofield 기반)
- **공식 문서**: FAO/WHO/UNU. *Human Energy Requirements: Report of a Joint FAO/WHO/UNU Expert Consultation*. FAO Food and Nutrition Technical Report Series 1, Rome 2001/2004. <https://www.fao.org/4/y5686e/y5686e07.htm>.
- **Schofield 회귀식 (kg → MJ/day; 1 MJ ≈ 239 kcal)**:
  | 연령 | 남성 BMR (MJ/d) | 여성 BMR (MJ/d) |
  |---|---|---|
  | 18–30 | 0.063·W + 2.896 | 0.062·W + 2.036 |
  | 30–60 | 0.048·W + 3.653 | 0.034·W + 3.538 |
  | ≥ 60  | 0.049·W + 2.459 | 0.038·W + 2.755 |
- **표본**: Schofield WN et al. *Hum Nutr Clin Nutr* 1985;39C Suppl 1:5–41. 7,173명 BMR 측정 데이터 통합 — 단, 60% 이상이 이탈리아·유럽 표본이라 아시아인 BMR을 평균 5–15% **과대평가**한다는 후속 비판이 다수.

### 2.6 아시아인·한국인 검증 연구
- **중국인 검증**: Liu HY, Lu YF, Chen WJ. *Predictive equations for basal metabolic rate in Chinese adults: a cross-validation study*. **J Am Diet Assoc** 1995;95(12):1403–8. → 서구식 공식이 중국인 BMR을 일관되게 과대평가하며, Liu 자체 공식이 가장 정확함을 보고.
- **재검증 (Yang 등 2016)**: Yang X, Li M, Mao D, *Estimation of basal metabolic rate in Chinese: are the current prediction equations applicable?* **Nutr J** 2016;15:79. **DOI: 10.1186/s12937-016-0197-2** — Harris-Benedict·Schofield·Henry·Mifflin 모두 중국인 BMR을 평균 5–13% 과대평가; Liu 식이 가장 근접.
- **열대·아시아 일반화**: BMR이 유럽·미국 백인 대비 약 **15–20% 낮다**고 보고됨 (열대기후·체격·근육량 차이).
- **한국인 자료**: 보건복지부·한국영양학회 *2020/2025 한국인 영양소 섭취기준(KDRIs)*에서 에너지필요추정량(EER)은 미국 IOM 2002 공식(연령·성별·체중·신장·PA 계수 기반)을 한국인 표본 보정 없이 차용. 한국인 자체 BMR 회귀식은 KDRIs 본문에 *명시되어 있지 않으며*, 따라서 BMR 자체는 여전히 서구 공식에 의존한다.
- **함의**: Mifflin-St Jeor는 한국인에게 BMR을 *약 5–10% 과대추정*할 가능성이 있으나, 현재 임상·앱 영역에서 보편 사용되는 차선책으로 합의된 수준이다.

### 2.7 비교 표 (요약)
| 공식 | 입력 변수 | 표본 출처 | 한국인 적용 | ±10% 일치율 |
|---|---|---|---|---|
| Mifflin-St Jeor (1990) | W, H, A, Sex | 미국 백인 498명 | 5–10% 과대 가능 | **약 70–82%** |
| Harris-Benedict 1919 | W, H, A, Sex | 미국 백인 239명 (1900년대) | 10–15% 과대 | 약 45–60% |
| Roza-Shizgal 1984 | 동일 | 미국 337명 | 좌동 | 약 55–65% |
| Katch-McArdle / Cunningham | LBM | 운동생리학 표본 | LBM 정확 시 양호 | 데이터 불충분 |
| Schofield (WHO/FAO/UNU) | W (연령·성별 분리) | 7,173명 (유럽 다수) | 아시아인 10–15% 과대 | 약 60–70% |
| Liu (1995) | W, H, A, Sex | 중국인 | **아시아 적합 ↑** | 중국인 한정 ≥80% |

→ **결론**: 현 시점 *범용*으로는 Mifflin-St Jeor가 여전히 최선의 기본값. 한국인 보정·LBM 옵션은 Phase 2 이후 고려.

---

## 3. 활동계수 (PAL) 검토

### 3.1 WHO/FAO/UNU 2001 PAL 표준
- **PAL 정의**: `PAL = TEE / BMR` (총에너지소비량을 기초대사로 나눈 무차원 배수).
- **공식 분류**:
  | 생활방식 | PAL 범위 |
  |---|---|
  | Sedentary / light activity | **1.40 – 1.69** |
  | Active / moderately active | **1.70 – 1.99** |
  | Vigorous / vigorously active | **2.00 – 2.40** (장기 유지 곤란) |
- 단일 대표값으로는 1.40(좌식), 1.55(중간), 1.75(활동), 1.90~2.10(고강도) 사용이 합의문에 명시.

### 3.2 Harris-Benedict 활동계수 (앱 업계 관행)
- 1.200 (좌식), 1.375 (가벼움), 1.550 (보통), 1.725 (강함), 1.900 (매우 강함).
- 사실 Harris-Benedict 본 논문(1919)에는 *활동계수 표가 존재하지 않는다*. 이는 후대(1980년대 영양사 교재·Katch 교재 등)에서 임상 편의용으로 만든 *준-합의값*이며 별도의 1차 논문 출처가 없다 — 문헌적 근거는 WHO/FAO/UNU 2001의 PAL 범위가 더 견고하다.
- Lemon-Aid가 사용하는 1.2/1.375/1.55/1.725/1.9 5단계는 이 관행을 따른 것.

### 3.3 걸음수 → PAL 매핑의 타당성

#### Tudor-Locke 5단계 분류
- **원논문**: Tudor-Locke C, Bassett DR Jr. *How many steps/day are enough? Preliminary pedometer indices for public health*. **Sports Med** 2004;34(1):1–8. **DOI: 10.2165/00007256-200434010-00001**.
- **2013 갱신 (성인 sedentary 정의)**: Tudor-Locke C, Craig CL, Thyfault JP, Spence JC. *A step-defined sedentary lifestyle index: <5000 steps/day*. **Appl Physiol Nutr Metab** 2013;38(2):100–14. **DOI: 10.1139/apnm-2012-0235**.

| 걸음수/일 | Tudor-Locke 분류 | Lemon-Aid 활동계수 | WHO/FAO/UNU PAL 범위 부합? |
|---|---|---|---|
| < 5,000 | Sedentary | 1.200 | 1.40 하한보다 *낮음* — 과소평가 가능 |
| 5,000 – 7,499 | Low active | 1.375 | 1.40 하한 미달 — 경계 |
| 7,500 – 9,999 | Somewhat active | 1.550 | 1.40–1.69 부합 |
| 10,000 – 12,499 | Active | 1.725 | 1.70–1.99 부합 |
| ≥ 12,500 | Highly active | 1.900 | 1.70–1.99 상한 / 2.0+ 경계 |

- **타당성 평가**: 5단계 *구간 경계*는 Tudor-Locke 분류와 정확히 일치하여 근거가 충분 (근거수준 B). 다만 *수치값*은 Harris-Benedict 관행을 따른 것으로, WHO PAL과 비교 시 하단(1.2, 1.375)은 약간 보수적.

#### 한계
1. **걸음 외 활동 미반영**: 수영·자전거·근력운동은 보수에 잡히지 않음 → 운동선수·근력 위주 사용자 과소평가.
2. **강도(intensity) 미반영**: 같은 10,000보라도 산책 vs 빠른 걷기의 에너지소비량은 1.5배 차이 가능.
3. **NEAT(비운동성 활동열발생)**: 서 있는 시간, 가사노동 등 — 걸음수로 일부만 포착.

### 3.4 METs 기반 대안

#### Tudor-Locke 케이던스(Cadence) 가이드 (2018)
- **원논문**: Tudor-Locke C, Han H, Aguiar EJ, *et al.* *How fast is fast enough? Walking cadence (steps/min) as a practical estimate of intensity in adults: a narrative review*. **Br J Sports Med** 2018;52(12):776–88. **DOI: 10.1136/bjsports-2017-097628**.
- **CADENCE-Adults 연구 (21–40세)**: Tudor-Locke C *et al.* *Walking cadence and intensity in 21–40 year olds: CADENCE-adults*. **Int J Behav Nutr Phys Act** 2019;16:8. **DOI: 10.1186/s12966-019-0769-6**.
- **케이던스 → METs 휴리스틱**:
  | 케이던스 (steps/min) | METs | 강도 |
  |---|---|---|
  | < 100 | < 3 | Light |
  | 100 | 3 | **Moderate 하한** |
  | 110 | 4 | Moderate |
  | 120 | 5 | Moderate |
  | ≥ 130 | ≥ 6 | **Vigorous 하한** |

#### 2011 Compendium of Physical Activities (Ainsworth 2011)
- **원논문**: Ainsworth BE, Haskell WL, Herrmann SD, *et al.* *2011 Compendium of Physical Activities: a second update of codes and MET values*. **Med Sci Sports Exerc** 2011;43(8):1575–81. **DOI: 10.1249/MSS.0b013e31821ece12**.
- **활동별 METs 예시**:
  - 천천히 걷기 (3.2 km/h): 2.0 METs
  - 보통 걷기 (4.8 km/h): 3.5 METs
  - 빠른 걷기 (6.4 km/h): 5.0 METs
  - 조깅 (8 km/h): 8.3 METs
  - 달리기 (10 km/h): 9.8 METs
  - 자전거 (중간 강도): 6.8 METs
  - 근력운동 (중간): 5.0 METs

#### 에너지소비량 환산 공식
```
kcal/min = METs × 3.5 × W(kg) / 200
```

---

## 4. 평가

### 4.1 BMR — Mifflin-St Jeor 선택의 타당성
**강점**
- ADA·미국영양사협회 권고 1순위 공식 (Frankenfield 2005).
- 정상체중·비만 모두에서 ±10% 일치율 최고 (약 70–82%).
- 입력 변수가 적고(W, H, A, Sex) UX 마찰 최소.

**약점**
- **표본의 백인 편향**: 1990년 표본 100%가 미국 거주자, 한국인 표본 없음. 한국인 BMR을 약 5–10% 과대평가할 가능성 (간접근거: 중국인·일본인 검증 연구 외삽).
- **비만에서 과대평가 가능**: BMI > 30에서 평균 5% 과대 (지방조직은 근육의 약 1/3 대사율) — Mifflin이 가장 적게 과대평가하나 여전히 존재.
- **사르코페니아(근감소)**: 체중·신장이 같아도 LBM이 낮으면 실제 BMR은 더 낮음. 노인·만성질환자에서 5–15% 과대평가 (Brazil 노인여성 연구 등에서 27% 과대 보고된 Schofield보다는 양호하나 무시 불가).
- **노인 (>65세)**: Mifflin이 가장 큰 편향(bias)을 보인다는 보고 (Anderegg 2022 등) — 65세 이상에서는 WHO 또는 Harris-Benedict가 오히려 더 정확하다는 결과도 존재.

### 4.2 TDEE — 활동계수 평가
**적합한 부분**
- 5,000보 미만 = 1.2: Tudor-Locke "sedentary lifestyle index" 정의(<5,000)와 일치 — 근거 충실.
- 12,500보 이상 = 1.9: "highly active"와 일치하며 WHO PAL "active" 범위 상단/vigorous 하단에 부합.
- 5단계 구간 경계 자체는 Tudor-Locke 표준 그대로.

**누락·약점**
1. **운동 강도 미반영**: 동일 걸음수라도 케이던스(보/분)에 따라 METs가 2–3배 차이.
2. **운동 시간(min) 무시**: 의도적 운동(예: 30분 조깅, 7 METs ≈ +260 kcal)이 걸음수에 비례 반영되지 않음.
3. **수영·자전거·근력**은 0 보로 잡혀 과소평가.
4. **체중에 따른 PAL 보정 부재**: 같은 PAL이라도 체중이 큰 사용자는 절대 kcal 증가폭이 더 큼 (BMR×PAL이라 자동 반영되긴 하나, 운동 단위 시간당 추가 소비는 별도 계산이 더 정확).

---

## 5. 수정 권고

### 5.1 BMR — 단계별 도입
- **Phase 1 (현재 → 유지)**: Mifflin-St Jeor 기본 공식.
- **Phase 2 (선택 입력)**: 사용자가 체지방률 입력 시 **Katch-McArdle / Cunningham** 자동 전환.
  - 트리거: BIA 체중계 연동 또는 수동 입력 (≥10% & ≤55% 범위 검증).
- **Phase 3 (한국인 보정)**: 자체 사용자 데이터(BIA + 식사기록 + 체중변화) 1,000명 이상 수집 후 한국인 보정 계수(α) 학습.
  - 잠정 권고: 한국인 사용자에게 `BMR_adj = Mifflin × 0.95` 적용 옵션 (간접근거 기반, 임상의 검토 필요).

### 5.2 TDEE — 단계별 보강
- **Phase 1 (현재)**: 걸음수 기반 5단계 PAL.
- **Phase 2 (의도 운동 가산)**:
  ```
  TDEE = BMR × PAL_steps + Σ (METs_i × 3.5 × W / 200) × duration_i(min)
  ```
  - 예: 50 kg 여성이 30분 조깅(7 METs) → 50 × 7 × 3.5 / 200 × 30 ≈ 184 kcal 가산.
  - 입력 UX: 운동 종류 → METs 자동 매핑 (Compendium 2011 기반 내장 테이블).
- **Phase 3 (웨어러블 통합)**:
  - 케이던스(steps/min) 기반 METs 자동 산출 (Tudor-Locke 2018 휴리스틱).
  - 심박수 기반 보정 (HRR%·VO₂max 추정 — Keytel 식 등).

### 5.3 만성질환자 분기 — 의학적 근거

> **결론 한 줄**: 표준 BMR/TDEE 공식은 *건강한 유로이드(euthyroid)·비당뇨·정상 신기능* 성인에서 도출·검증되었기에, 만성질환자는 **공식 적용 자체가 임상적 오차원**(±20–100%)이 되어 *체중·영양 권고를 신뢰할 수 없다*. 따라서 분리·전문가 위임이 필수다.

#### 5.3.1 갑상선 질환
- **갑상선 기능 저하증 (Hypothyroidism)**:
  - BMR/REE가 **10–30% 감소** — 표준 공식 사용 시 *과대평가* → 권장 칼로리 과다 → 체중 증가.
  - 근거: Brunova J *et al.*; Kim B. *Thyroid hormone as a determinant of energy expenditure and the basal metabolic rate*. **Thyroid** 2008;18(2):141–4. **DOI: 10.1089/thy.2007.0266**.
- **갑상선 기능 항진증 (Hyperthyroidism / Graves)**:
  - BMR이 **30–100% 증가** — 측정 REE가 예측치보다 평균 40% 높다는 보고 (Kim 등 2018, *Int J Endocrinol* 9863050).
  - 표준 공식 사용 시 *과소평가* → 체중 감소·근손실 가속.

#### 5.3.2 당뇨병
- **2형 당뇨 (특히 비만 동반)**: 인슐린 저항성 자체가 BMR을 변화시키지는 않으나, 저BMR이 당뇨 발병 위험인자로 보고됨 (Mtintsilana A *et al.* 2020, *PMC7373309*).
- **인슐린 사용 환자**: 인슐린은 동화호르몬 → 약물 용량·식사 타이밍에 따라 실제 에너지 활용이 다름. **단순 칼로리 권고로 혈당 관리 위험** → 영양사·내분비내과 협진 필수.

#### 5.3.3 신장 질환
- 만성신부전(CKD)은 REE를 **독립적으로 감소시킴** (Kamimura MA *et al.* 2017, *Clin Nutr ESPEN*).
- 단백질 권고량이 일반인의 절반 이하(0.6–0.8 g/kg)로 제한되므로, TDEE와 별개로 **단백질 분리 계산** 필요.

#### 5.3.4 사르코페니아·노쇠 (Frailty)
- 근육량 감소 → 실제 BMR이 공식 추정치보다 10–15% 낮음.
- 표준 공식 사용 시 칼로리 과다 권고 → 추가 체지방 증가 + 근손실 가속 (sarcopenic obesity 악화).

#### 5.3.5 시스템 분기 권고
1. **온보딩 설문에 질환 플래그 추가**: 갑상선 / 당뇨 / 신장 / 간질환 / 심부전 / 사르코페니아.
2. **플래그 활성화 시**:
   - 자동 BMR/TDEE 계산을 *참고용*으로만 표시 (오차 가능성 경고 배너).
   - "이 수치는 전문의 상담 결과로 조정되어야 합니다" 모달 강제.
   - 임상영양사·주치의 연계(예: 영양상담실·EHR 연동) 옵션 우선 노출.
3. **알고리즘 절대 자동 처방 금지**: 칼로리·매크로 자동 권고를 *비활성화* 또는 "전문의 미상담" 워터마크 표시.

### 5.4 수정된 의사 코드 (Python)
```python
from dataclasses import dataclass
from enum import Enum
from typing import Optional

class Sex(Enum):
    MALE = "male"
    FEMALE = "female"

class ChronicCondition(Enum):
    HYPOTHYROIDISM = "hypothyroid"
    HYPERTHYROIDISM = "hyperthyroid"
    DIABETES_T2 = "t2dm"
    CKD = "ckd"
    SARCOPENIA = "sarcopenia"

@dataclass
class UserProfile:
    weight_kg: float
    height_cm: float
    age: int
    sex: Sex
    body_fat_pct: Optional[float] = None  # 0–1
    conditions: list[ChronicCondition] = None
    ethnicity_korean: bool = True

def bmr_mifflin(p: UserProfile) -> float:
    base = 10 * p.weight_kg + 6.25 * p.height_cm - 5 * p.age
    return base + (5 if p.sex == Sex.MALE else -161)

def bmr_katch_mcardle(p: UserProfile) -> float:
    lbm = p.weight_kg * (1 - p.body_fat_pct)
    return 370 + 21.6 * lbm

def calc_bmr(p: UserProfile) -> tuple[float, str]:
    """Phase 2 우선 적용: 체지방률 있으면 Katch-McArdle, 없으면 Mifflin."""
    if p.body_fat_pct and 0.05 <= p.body_fat_pct <= 0.55:
        bmr = bmr_katch_mcardle(p)
        method = "Katch-McArdle"
    else:
        bmr = bmr_mifflin(p)
        method = "Mifflin-St Jeor"

    # Phase 3: 한국인 보정 (잠정 5% 감산, 임상 검토 필요)
    if p.ethnicity_korean:
        bmr *= 0.95
        method += " + KR-adj(0.95)"

    return bmr, method

# 걸음수 → PAL
def pal_from_steps(steps: int) -> float:
    if steps < 5000:   return 1.20
    if steps < 7500:   return 1.375
    if steps < 10000:  return 1.55
    if steps < 12500:  return 1.725
    return 1.90

# METs 기반 운동 에너지
def kcal_from_mets(mets: float, weight_kg: float, minutes: int) -> float:
    return mets * 3.5 * weight_kg / 200 * minutes

def calc_tdee(
    p: UserProfile,
    steps: int,
    intentional_exercises: list[tuple[float, int]] = None,  # [(METs, min), ...]
) -> dict:
    # 만성질환자 가드
    if p.conditions:
        return {
            "status": "REFER_SPECIALIST",
            "reason": "Chronic condition detected; standard formula not applicable.",
            "advisory_bmr": None,
            "advisory_tdee": None,
        }

    bmr, method = calc_bmr(p)
    pal = pal_from_steps(steps)
    base_tdee = bmr * pal

    exercise_kcal = 0.0
    if intentional_exercises:
        for mets, minutes in intentional_exercises:
            exercise_kcal += kcal_from_mets(mets, p.weight_kg, minutes)

    return {
        "status": "OK",
        "bmr": round(bmr),
        "bmr_method": method,
        "pal": pal,
        "base_tdee": round(base_tdee),
        "exercise_kcal": round(exercise_kcal),
        "tdee_total": round(base_tdee + exercise_kcal),
    }
```

---

## 6. 근거 수준 재평가

| 항목 | 이전 | 수정 후 | 비고 |
|---|---|---|---|
| BMR — Mifflin-St Jeor 채택 | A | **A (유지)** | 한국인 보정은 Phase 3에서 도입 |
| BMR — Katch-McArdle 옵션 | – | **B** | 체지방률 정확도에 의존 |
| TDEE — 걸음수 5단계 PAL | B | **B (유지)** | Tudor-Locke 분류와 일치 |
| TDEE — METs 가산 (Phase 2) | – | **A** | Compendium 2011·Tudor-Locke 2018 견고 |
| 만성질환자 분기 | C (암묵) | **A (필수)** | 갑상선·신장·당뇨 임상 근거 충분 |
| 한국인 0.95 보정 계수 | – | **C** | 자체 데이터 수집 후 재추정 필요 |

---

## 7. 참고 문헌

### 7.1 BMR 공식
1. Mifflin MD, St Jeor ST, Hill LA, Scott BJ, Daugherty SA, Koh YO. A new predictive equation for resting energy expenditure in healthy individuals. **Am J Clin Nutr** 1990;51(2):241–7. DOI: [10.1093/ajcn/51.2.241](https://doi.org/10.1093/ajcn/51.2.241).
2. Harris JA, Benedict FG. *A Biometric Study of Basal Metabolism in Man*. Carnegie Institution of Washington, 1919. Publication No. 279.
3. Roza AM, Shizgal HM. The Harris-Benedict equation reevaluated: resting energy requirements and the body cell mass. **Am J Clin Nutr** 1984;40(1):168–82. DOI: [10.1093/ajcn/40.1.168](https://doi.org/10.1093/ajcn/40.1.168).
4. Cunningham JJ. Body composition as a determinant of energy expenditure: a synthetic review and a proposed general prediction equation. **Am J Clin Nutr** 1991;54(6):963–9. DOI: [10.1093/ajcn/54.6.963](https://doi.org/10.1093/ajcn/54.6.963).
5. Katch FI, McArdle WD. *Nutrition, Weight Control, and Exercise* (1977/1983) — BMR = 370 + 21.6 × LBM.
6. Schofield WN. Predicting basal metabolic rate, new standards and review of previous work. **Hum Nutr Clin Nutr** 1985;39 Suppl 1:5–41. PMID: 4044297.
7. FAO/WHO/UNU. *Human Energy Requirements: Report of a Joint FAO/WHO/UNU Expert Consultation*. FAO Food and Nutrition Technical Report Series 1, 2001/2004. <https://www.fao.org/4/y5686e/y5686e00.htm>.
8. Frankenfield D, Roth-Yousey L, Compher C. Comparison of predictive equations for resting metabolic rate in healthy nonobese and obese adults: a systematic review. **J Am Diet Assoc** 2005;105(5):775–89. DOI: [10.1016/j.jada.2005.02.005](https://doi.org/10.1016/j.jada.2005.02.005).

### 7.2 한국인 / 아시아인 검증
9. Liu HY, Lu YF, Chen WJ. Predictive equations for basal metabolic rate in Chinese adults: a cross-validation study. **J Am Diet Assoc** 1995;95(12):1403–8. DOI: [10.1016/S0002-8223(95)00369-X](https://doi.org/10.1016/S0002-8223(95)00369-X).
10. Yang X, Li M, Mao D, *et al.* Estimation of basal metabolic rate in Chinese: are the current prediction equations applicable? **Nutr J** 2016;15:79. DOI: [10.1186/s12937-016-0197-2](https://doi.org/10.1186/s12937-016-0197-2).
11. 보건복지부·한국영양학회. *2020 한국인 영양소 섭취기준*. 2020. <https://www.kns.or.kr/FileRoom/FileRoom_view.asp?idx=108&BoardID=Kdr>.
12. 보건복지부·한국영양학회. *2025 한국인 영양소 섭취기준*. 2025.

### 7.3 활동계수·METs
13. Tudor-Locke C, Bassett DR Jr. How many steps/day are enough? Preliminary pedometer indices for public health. **Sports Med** 2004;34(1):1–8. DOI: [10.2165/00007256-200434010-00001](https://doi.org/10.2165/00007256-200434010-00001).
14. Tudor-Locke C, Craig CL, Thyfault JP, Spence JC. A step-defined sedentary lifestyle index: <5000 steps/day. **Appl Physiol Nutr Metab** 2013;38(2):100–14. DOI: [10.1139/apnm-2012-0235](https://doi.org/10.1139/apnm-2012-0235).
15. Tudor-Locke C, Han H, Aguiar EJ, *et al.* How fast is fast enough? Walking cadence (steps/min) as a practical estimate of intensity in adults: a narrative review. **Br J Sports Med** 2018;52(12):776–88. DOI: [10.1136/bjsports-2017-097628](https://doi.org/10.1136/bjsports-2017-097628).
16. Tudor-Locke C, Ducharme SW, Aguiar EJ, *et al.* Walking cadence (steps/min) and intensity in 21 to 40 year olds: CADENCE-adults. **Int J Behav Nutr Phys Act** 2019;16:8. DOI: [10.1186/s12966-019-0769-6](https://doi.org/10.1186/s12966-019-0769-6).
17. Ainsworth BE, Haskell WL, Herrmann SD, *et al.* 2011 Compendium of Physical Activities: a second update of codes and MET values. **Med Sci Sports Exerc** 2011;43(8):1575–81. DOI: [10.1249/MSS.0b013e31821ece12](https://doi.org/10.1249/MSS.0b013e31821ece12).

### 7.4 만성질환 BMR 영향
18. Kim B. Thyroid hormone as a determinant of energy expenditure and the basal metabolic rate. **Thyroid** 2008;18(2):141–4. DOI: [10.1089/thy.2007.0266](https://doi.org/10.1089/thy.2007.0266).
19. Kim MJ, Cho SW, Choi S, *et al.* Changes in body compositions and basal metabolic rates during treatment of Graves' disease. **Int J Endocrinol** 2018;2018:9863050. DOI: [10.1155/2018/9863050](https://doi.org/10.1155/2018/9863050).
20. Avesani CM, Draibe SA, Kamimura MA, *et al.* Resting energy expenditure of chronic kidney disease patients: influence of renal function and subclinical inflammation. **Am J Kidney Dis** 2004;44(6):1008–16. DOI: [10.1053/j.ajkd.2004.08.023](https://doi.org/10.1053/j.ajkd.2004.08.023).
21. Mtintsilana A, Micklesfield LK, Chorell E, *et al.* Low basal metabolic rate as a risk factor for development of insulin resistance and type 2 diabetes. **BMJ Open Diabetes Res Care** 2020;8(1):e000970. PMC: [PMC7373309](https://pmc.ncbi.nlm.nih.gov/articles/PMC7373309/).
22. Batsis JA, Villareal DT. Sarcopenic obesity in older adults: aetiology, epidemiology and treatment strategies. **Nat Rev Endocrinol** 2018;14(9):513–37. DOI: [10.1038/s41574-018-0062-9](https://doi.org/10.1038/s41574-018-0062-9).

---

**리뷰 권고**: 본 문서의 *한국인 0.95 보정 계수*와 *만성질환자 분기 규칙*은 임상영양사·내분비내과 자문 후 확정해야 한다. 알고리즘 자동 처방을 제공하기 전, IRB 또는 의료기기 SaMD(Software as a Medical Device) 분류 검토가 필요할 수 있다.
