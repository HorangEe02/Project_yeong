# 07. 만성질환자 분리 처리의 근거 — 종합

> *Lemon-Aid 헬스케어 알고리즘 설계 문서*
> 작성: 2026-05-26
> 관련: `07-core-algorithm.md` (v4 활동점수), `10-compliance-checklist.md`

---

## 0. 한 줄 결론

> **만성질환자는 운동·영양·체중/BMR·약물 상호작용의 4개 축에서 일반인과 다른 처방이 필요하다.**
> 동일 알고리즘을 무차별 적용할 경우 (1) **수치 부정확**, (2) **잠재적 안전 위험**, (3) **사용자 동기·신뢰 손상**의 3중 문제가 발생한다.
>
> 이 문서는 Lemon-Aid가 v4 활동점수에서 만성질환자에게 +0.10 ~ +0.15 가중치를 부여하고, BMR·영양·영양제 추천을 별도 분기 처리하는 이유를 공식 가이드라인(HHS / WHO / ADA / AHA / EULAR / KDOQI / EASL / Endocrine Society)과 학술 근거로 정리한다.

---

## 1. 4개 축의 분리 이유

### 1.1 운동 처방 (v4 활동점수 가중치)

#### 의학적 근거 — *"같은 활동량이라도 만성질환자에게는 더 큰 의미"*

| 기관 | 핵심 권고 | 출처 |
|---|---|---|
| **HHS PAG 2018** (2판, Ch. 7) | 만성질환자도 *가능한 범위에서* 신체활동 권장; "**Some physical activity is better than none**" — 적은 활동량에서도 상대적 건강 이득이 큼 | [ODPHP](https://odphp.health.gov/our-work/nutrition-physical-activity/physical-activity-guidelines/current-guidelines) |
| **WHO 2020 Guidelines** | 만성질환자(당뇨·고혈압·암 생존자 등)도 18-64세 일반 성인과 동일한 기준 적용: 중강도 **주 150-300분** *또는* 고강도 **75-150분** + 근력 운동 **주 2회 이상** | [WHO 9789240015128](https://www.who.int/publications/i/item/9789240015128) |
| **ADA Standards 2025/2026** | 1형·2형 당뇨 모두: 중-고강도 유산소 **주 150분 이상** (최소 3일, 연속 2일 이상 비활동 금지), 비연속일 **저항운동 주 2-3회**, 노인은 유연성·균형 운동 주 2-3회 추가 | [Diabetes Care 48 Suppl. 1](https://diabetesjournals.org/care/article/48/Supplement_1/S6/157564) |
| **AHA / ACSM** | 심혈관 질환자는 심장재활(Cardiac Rehab) 프로그램 권장; 운동 강도는 *symptom-limited stress test* 기반으로 개인화 | [AHA Physical Activity](https://www.heart.org/en/healthy-living/fitness/fitness-basics/aha-recs-for-physical-activity-in-adults) |
| **EULAR 2023 / ACR** | 골관절염(OA)에는 운동이 **강력 권고**; Tai Chi·자전거·수영 등 저충격 유산소 + 신경근육 강화 + 균형 운동 효과 입증 | [Ann Rheum Dis 2024 EULAR update](https://ard.eular.org/article/S0003-4967(24)00129-8/fulltext) |
| **GOLD COPD** | 호흡곤란이 있어도 폐 재활(Pulmonary Rehabilitation) — 유산소+저항 — 으로 운동 능력·삶의 질·입원율 개선 | [goldcopd.org](https://goldcopd.org/) |

> **핵심 메시지**: 만성질환자에게 "활동" 자체의 *상대적 건강 이득*은 일반인보다 **크다**.
> (HHS 2018: "Health benefits of physical activity *exceed risks for nearly all people, including those with chronic conditions*.")

#### UX·동기 부여 근거 — *"활동에 대한 진입 장벽을 낮추는 가중치"*

- 만성질환자는 *낮은 활동 능력*에서 시작 → 일반인과 동일 기준 적용 시 점수가 항상 낮음 → **자기효능감 저하**, 이탈 가속.
- 동일한 5,000보 걷기라도 당뇨/고혈압/심혈관 환자에게 미치는 임상적 의미가 다름(혈당·혈압·심박변이도 개선).
- v4의 +0.10 ~ +0.15 가중치는 **"같은 노력에도 더 높은 점수 인식"**을 제공하여 행동 변화 단계(Transtheoretical Model)의 *준비기→실행기* 전환을 촉진.

#### 왜 +0.10 / +0.15인가 — *수치의 한계와 솔직한 표시*

> ⚠️ **이 가중치는 임상 효과 크기(effect size)가 아닌, 프로젝트 우선순위 계수(priority weight)다.**

- 당뇨 +0.10 / 고혈압 +0.10: 일상 활동으로도 글루코스 처리·혈압 강하 효과 누적 → 표준 권장(150분/주) 진입 격려.
- 심혈관 +0.15 / 관절 +0.15: 운동의 *잠재 위험과 이득이 모두 크다* — 작은 안전한 활동이 큰 결과로 이어지는 영역. 행동 진입을 가장 강하게 보상.
- 호흡기 +0.10: COPD/천식 → 폐 재활 진입을 격려, 단 호흡곤란·SpO₂ 모니터링 분기 필요.
- 상한 1.3: 무한 가중 방지(점수 인플레이션) + 가이드라인 표준 권장량 도달 시점 부근에서 수렴.
- **근거 수준 B/C** (관찰 연구 + 전문가 합의 + 프로젝트 가설). 자체 데이터 수집 후 보정 예정.

---

### 1.2 영양 처방 — *"질환별 핵심 영양소가 정반대로 갈리는 영역"*

#### 질환별 가이드 분기

| 질환 | 핵심 처방 | 출처 |
|---|---|---|
| **2형 당뇨 (ADA)** | 탄수화물 *비율보다 질*; 식이섬유 ↑ (최소 14g/1000kcal ≈ **25-35g/day**); 정제 탄수화물·설탕 음료 회피; 지중해/저탄수/DASH 모두 허용 | ADA Standards of Care 2025 Sec. 5 |
| **고혈압 (DASH)** | Na **<2,300mg/day** (일반) / **<1,500mg/day** (고혈압 또는 CV 위험 ↑); K·Ca·Mg ↑ 식단; 2025 AHA/ACC HTN 가이드라인 채택 | [NHLBI DASH](https://www.nhlbi.nih.gov/health/dash-eating-plan) |
| **만성신부전 CKD (KDOQI 2020)** | 단백질: 비투석 CKD 3-5 → 개별화(예: 0.55-0.60g/kg with metabolic stability); 투석 환자는 **1.0-1.2g/kg**; 가공식품 첨가 인(inorganic P) 제한; 칼륨은 *고칼륨혈증 시* 개별 조정 (전통적 일률 제한은 더 이상 권장하지 않음) | [AJKD KDOQI 2020 Update](https://www.ajkd.org/article/S0272-6386(20)30726-5/fulltext) |
| **간경변 (EASL 2019)** | 단백질 **1.2-1.5g/kg/day** (감소 금지!); 야간 간식(late evening snack) + 아침식 포함; 분지쇄아미노산(BCAA) 보충은 비대상성 환자에서 권장 | [J Hepatol 2018](https://www.journal-of-hepatology.eu/article/S0168-8278(18)32177-9/fulltext) |
| **항응고제 (와파린)** | **비타민 K 섭취는 일정하게 유지** (회피가 아닌 *일관성*); 갑작스러운 다량 섭취(예: 시금치·케일·브로콜리 400g, K 700-1500μg)는 INR을 측정 가능 수준으로 변화시킴 | [Pharmacogenetics PMC2911546](https://pmc.ncbi.nlm.nih.gov/articles/PMC2911546/) |

#### 일반 KDRIs(한국인 영양섭취기준)만 적용 시의 위험

- 신부전 환자에게 일반 단백질 1.0g/kg을 권하면 *질환 진행 가속* 가능.
- 간경변 환자에게 단백질 0.8g/kg을 권하면 *근감소·간성뇌증 악화* 위험.
- 고혈압 환자에게 일반 Na 2,300mg 상한만 적용하면 *세부 위험군(<1,500mg 필요)* 미식별.
- → **질환별 가이드 라우팅이 필수**.

---

### 1.3 BMR·체중 예측 — *"표준 공식이 깨지는 영역"*

#### 질환별 BMR 변동

| 질환 | BMR 영향 | 7-step 예측·Mifflin 적용 시 |
|---|---|---|
| **갑상선 기능 저하증** | BMR **-20 ~ -30%** | Mifflin 공식 → *과대평가* → 칼로리 권고가 사용자에게 너무 높음 → 체중 감량 실패·체중 증가 |
| **갑상선 기능 항진증** | BMR **+30 ~ +100%** | 반대로 *과소평가* → 영양실조·근손실 위험 |
| **PCOS** | 인슐린 저항성으로 *지방 분해(lipolysis) 효율 저하* (Endocrine Society 2023 PCOS Guideline) → 일반 공식 대비 감량 저항 ~33-66% 환자에게 존재 | 7-step 예측 어긋남, "약속 미달" 위험 |
| **부신피질 호르몬(스테로이드) 장기 복용** | 부종·체중 증가·체액 변동 → Mifflin은 *체구성(LBM/Fat)*을 구분하지 않음 | 체중 변화가 지방이 아닌 수분일 가능성 → 잘못된 해석 |
| **인슐린 치료 중인 당뇨** | 인슐린 자체가 체중 증가 유발(ADA 2025) | 칼로리 적자를 만들어도 예측대로 빠지지 않음 |

> 출처: [Cleveland Clinic BMR](https://my.clevelandclinic.org/health/body/basal-metabolic-rate-bmr); [PCOS guideline 2023](https://academic.oup.com/jcem/article/108/10/2447/7242360)

#### 왜 만성질환자에 일반 공식 적용이 위험한가

1. **약속 미달 → 신뢰 손상**: "X kg 감량을 약속"한 시스템이 갑상선 저하 환자에게는 *공식 자체가 틀려서* 빠지지 않음. 사용자는 자신을 자책하거나 앱을 신뢰하지 않게 됨.
2. **영양 위험**: 잘못된 칼로리 권고는 *영양실조 또는 위험한 체중 변화*로 직결.
3. **윤리적 문제**: 임상 정보 없이 BMR/TDEE를 단정하면 *의료기기성* 시비 가능.
4. → **만성질환자에게는 (a) 예측 신뢰도 표시 ↓, (b) 전문가 상담 안내, (c) 자동 계산 비활성 옵션이 필수**.

---

### 1.4 영양제·약물 상호작용 — *"가장 즉각적인 안전 위험 영역"*

#### 반드시 분기 처리해야 할 상호작용

| 약물 | 영양제/식품 | 위험 | 출처 |
|---|---|---|---|
| **와파린 (Warfarin)** | 비타민 K 다량 (시금치·케일·브로콜리·녹즙) | 항응고 효과 ↓ → 혈전 위험 ↑ (또는 갑작스러운 감소 시 출혈 ↑) | [PMC2911546](https://pmc.ncbi.nlm.nih.gov/articles/PMC2911546/) |
| **와파린 / DOAC** | 오메가-3, 은행잎(Ginkgo), 마늘 보충제 | 출혈 위험 ↑ (추가적 항혈소판 효과) | StatPearls (Warfarin) |
| **레보티록신 (Levothyroxine)** | 칼슘·철분·콩 단백질·제산제 | 흡수 ↓ → 갑상선 호르몬 부족; **최소 4시간 간격** 권장 | Mayo Clinic / ATA 가이드 |
| **CKD 환자** | 칼륨·인 함유 영양제(허브, 멀티비타민 일부), NSAID | 고칼륨혈증·고인산혈증·신기능 악화 | KDOQI 2020 |
| **MAOI (항우울제)** | 티라민 함유 식품 (숙성 치즈, 적포도주, 김치·사우어크라우트, 생맥주, 숙성육) | **고혈압 위기**; 10-25mg 티라민 섭취 시 두통·고혈압·뇌출혈 가능 | [Mayo MAOI](https://www.mayoclinic.org/diseases-conditions/depression/expert-answers/maois/faq-20058035) |
| **SSRI / SNRI** | 세인트존스워트(St. John's Wort) | 세로토닌 증후군 | StatPearls |
| **스타틴** | 자몽주스 | CYP3A4 억제 → 스타틴 농도 ↑, 횡문근융해증 위험 | FDA |

> **결론**: 약물 복용자에게 영양제를 추천할 때는 **반드시** (1) 약물 정보 입력 강제, (2) 상호작용 DB 매칭, (3) 위험 시 경고 + 약사/의사 상담 분기.

---

## 2. Lemon-Aid에 적용할 분기 설계

### 2.1 사용자 프로필 분리

```python
class HealthStatus(str, Enum):
    GENERAL = "general"           # 일반 사용자
    AT_RISK = "at_risk"           # 위험군 (가족력, 경계 수치)
    CHRONIC = "chronic"           # 만성질환 진단 (전문가 확인)

class ChronicCondition(str, Enum):
    DIABETES_T1 = "diabetes_t1"
    DIABETES_T2 = "diabetes_t2"
    HYPERTENSION = "hypertension"
    CARDIOVASCULAR = "cardiovascular"
    OSTEOARTHRITIS = "osteoarthritis"
    COPD = "copd"
    CKD = "ckd"
    CIRRHOSIS = "cirrhosis"
    HYPOTHYROIDISM = "hypothyroidism"
    HYPERTHYROIDISM = "hyperthyroidism"
    PCOS = "pcos"
    # ... 약물 정보는 별도 모듈
```

### 2.2 알고리즘별 분기 매트릭스

| 알고리즘 | 일반 사용자 | 만성질환자 |
|---|---|---|
| **BMI 분류** | 한국 KSSO 기준 (≥25 비만) | + 노인 obesity paradox 주의, 사르코페니아 비만 스크리닝 |
| **v1 권장 걸음수** | 8,000 기본 | 당뇨 ↑(혈당 처리), 관절 ↓(저충격), COPD ↓ 시작 후 점진 증량 |
| **v2 심박 가중** | 표준 50-70% HRmax | 심혈관: *symptom-limited HR*; 호흡기: Borg dyspnea 척도 병용 |
| **v4 활동 가중** | 1.0 | +0.10 ~ +0.15 (질환별), 상한 1.3 |
| **BMR / TDEE** | Mifflin-St Jeor | 갑상선 환자 → *자동 계산 비활성* + 의사 상담 권고; PCOS → 신뢰도 표시 ↓ |
| **체중 예측 (7-step)** | 표준 시뮬레이션 | 갑상선/PCOS/스테로이드 → **신뢰도 ↓ 명시** 또는 시뮬레이션 비활성 |
| **영양 진단** | KDRIs 기반 | 질환별 가이드 라우팅 (DASH / ADA / KDOQI / EASL) |
| **영양제 추천** | 일반 권장 | **약물 입력 강제 → 상호작용 체크 → 위험 시 차단 + 전문가 상담** |

### 2.3 UX 라벨 정리 (윤리 가드레일)

| 사용 금지 | 사용 권장 |
|---|---|
| "질환 개선 점수" | "활동 동기 점수" |
| "치료 효과" | "예상 활동량 변화 범위" |
| "당뇨 개선" | "혈당 관리에 도움이 될 수 있는 활동 범위" |
| "X kg 감량 약속" | "일반적 시나리오에서 X kg 변화 시뮬레이션 (개인차 큼)" |

---

## 3. 윤리·법무 가드레일

⚠️ **반드시** 다음을 준수:

1. **표현 가드**: 진단·치료·예방 단정 표현 금지. "도움이 될 수 있는", "일반적인 시나리오에서" 등 *완화 표현* 사용.
2. **전문가 분기**: 만성질환·약물 복용 입력 시 *반드시* "주치의/약사 상담 안내" UI 노출.
3. **데이터 신뢰도 표시**: 만성질환자 BMR/체중 예측은 *낮은 신뢰도 배지* 표시.
4. **의료기기법 준수**: CDSS 수준에 도달하기 전까지는 "건강 관리 보조 도구"로 명시. 자세히는 `10-compliance-checklist.md` 참고.
5. **PMDA·식약처·FDA**: 약물-영양제 상호작용 경고는 *일반 정보 제공* 범위로 한정, 개인화 처방은 금지.

---

## 4. Phase별 도입 로드맵

### Phase 1 (현재 → 단기 3개월)
- [x] v4 활동점수 가중치 명확화 (이 문서)
- [ ] **약물 + 영양제 상호작용 경고 시스템 우선 구축** (와파린, 레보티록신, MAOI, CKD 약물 우선)
- [ ] 갑상선·신부전·간경변 환자 → BMR/체중 예측 *자동 비활성* + 상담 안내 모듈
- [ ] UX 라벨 일괄 정리 (치료 어휘 제거)

### Phase 2 (중기 6-12개월)
- [ ] 질환별 영양 가이드 라우팅 (DASH / ADA / KDOQI / EASL)
- [ ] 심혈관·호흡기 환자 운동 강도 안전 영역(Symptom-limited HR / Borg) 모듈
- [ ] 자체 코호트 데이터 수집 → +0.10/+0.15 가중치 보정

### Phase 3 (장기 12-24개월)
- [ ] 의료자문위(내분비·신장·심장·정신과·약학) 검수 후 임상 의사결정 지원(CDSS) 수준 발전
- [ ] 약물-영양제·약물-약물 상호작용 DB 자동 확장(예: DrugBank / Lexicomp 연계 검토)
- [ ] 사르코페니아 비만 스크리닝 (BIA / 보행속도) 통합

---

## 5. 참고 자료

### 공식 가이드라인

- **HHS Physical Activity Guidelines for Americans, 2nd Edition** (2018). U.S. Department of Health and Human Services. <https://odphp.health.gov/our-work/nutrition-physical-activity/physical-activity-guidelines/current-guidelines>
- **WHO Guidelines on Physical Activity and Sedentary Behaviour** (2020). World Health Organization. ISBN 978-92-4-001512-8. <https://www.who.int/publications/i/item/9789240015128>
- **American Diabetes Association. Standards of Care in Diabetes — 2025 / 2026**. *Diabetes Care* 48(Suppl. 1) / 49(Suppl. 1). <https://diabetesjournals.org/care/article/48/Supplement_1/S6/157564> ; <https://diabetesjournals.org/care/article/49/Supplement_1/S6/163930>
- **AHA — Recommendations for Physical Activity in Adults**. American Heart Association. <https://www.heart.org/en/healthy-living/fitness/fitness-basics/aha-recs-for-physical-activity-in-adults>
- **ACSM's Exercise Management for Persons with Chronic Diseases and Disabilities** (4th ed., Human Kinetics, 2016). ISBN 978-1-4504-3414-0.
- **EULAR 2023 update — Non-pharmacological core management of hip and knee osteoarthritis**. *Ann Rheum Dis* 2024. <https://ard.eular.org/article/S0003-4967(24)00129-8/fulltext>
- **GOLD 2024/2025 — Global Strategy for the Diagnosis, Management, and Prevention of COPD**. <https://goldcopd.org/>
- **KDOQI Clinical Practice Guideline for Nutrition in CKD: 2020 Update**. *Am J Kidney Dis* 76(3 Suppl 1):S1-S107. <https://www.ajkd.org/article/S0272-6386(20)30726-5/fulltext>
- **EASL Clinical Practice Guidelines on nutrition in chronic liver disease** (2019). *J Hepatol* 70:172-193. <https://www.journal-of-hepatology.eu/article/S0168-8278(18)32177-9/fulltext>
- **NHLBI — DASH Eating Plan**. <https://www.nhlbi.nih.gov/health/dash-eating-plan>
- **2023 International Evidence-based Guideline for the Assessment and Management of PCOS** (Endocrine Society & ESHRE 협력). *J Clin Endocrinol Metab* 108(10):2447. <https://academic.oup.com/jcem/article/108/10/2447/7242360>
- **KDRIs — 한국인 영양섭취기준** (보건복지부·한국영양학회, 2020).
- **KSSO — 비만 진료지침** (대한비만학회, 2022 / 2024).

### 학술 근거 (선별)

- Mifflin MD, et al. *A new predictive equation for resting energy expenditure in healthy individuals*. Am J Clin Nutr 1990;51(2):241-7.
- Bao W, et al. *Influence of vitamin K on anticoagulant therapy depends on vitamin K status and the source and chemical forms of vitamin K*. Nutr Rev 2005;63(3):91-7. <https://pubmed.ncbi.nlm.nih.gov/15825811/>
- Gao Q, et al. *Prevalence of sarcopenic obesity in the older non-hospitalized population: a systematic review and meta-analysis*. BMC Geriatrics 2024. <https://pmc.ncbi.nlm.nih.gov/articles/PMC11036751/>
- Batsis JA, Villareal DT. *Sarcopenic obesity in older adults: aetiology, epidemiology and treatment strategies*. Nat Rev Endocrinol 2018;14:513-37. <https://pmc.ncbi.nlm.nih.gov/articles/PMC6241236/>
- Gillespie EL, et al. *Hypertensive crisis and cheese*. Indian J Psychiatry 2009. <https://pmc.ncbi.nlm.nih.gov/articles/PMC2738414/>

### 관련 내부 문서

- `07-core-algorithm.md` — v4 활동점수 본문 정의
- `10-compliance-checklist.md` — 의료기기법·약사법·개인정보 가드레일
- `08-nutrition-routing.md` (예정) — 질환별 영양 가이드 라우팅
- `09-drug-interaction-db.md` (예정) — 약물-영양제 상호작용 DB 설계

---

> **이 문서의 위치**: Lemon-Aid 핵심 알고리즘 의사결정의 *근거 백서*.
> 가중치·분기 로직을 변경할 때는 반드시 이 문서를 동시에 업데이트한다.
