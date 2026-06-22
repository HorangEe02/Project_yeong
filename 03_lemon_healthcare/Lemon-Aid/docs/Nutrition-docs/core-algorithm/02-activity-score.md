# 02. 활동점수 v1~v4 알고리즘 평가 및 수정안

> Lemon-Aid 활동점수(Activity Score) 알고리즘에 대한 논문·공식 가이드 기반 평가 및 개선안.
> 사용자 핵심 질문 — **"왜 만성질환 환자와 일반 사용자를 분리해서 가중치를 적용하는가"** 에 대한 의학적·UX적 근거를 §3.4 / §4.4에 명시.

---

## 1. 현재 구현 요약

### 1.1 v1 — 기본 활동점수 (걸음수 기반)

| 항목 | 값 / 공식 |
|------|-----------|
| 권장걸음수 | `8,000 × 성별계수 × 나이계수 × BMI계수` |
| 성별계수 | 남 1.0 / 여 0.95 |
| 나이계수 | <40세 1.0 / 40~59세 0.9 / 60+ 0.8 |
| BMI계수 | 저체중 0.9 / 정상 1.0 / 과체중 1.1 / 비만 1.15 |
| 기본점수 | `min(실제걸음수 ÷ 권장걸음수, 1.2) × 83.33` |
| 점수 상한 | 100점 (1.2 × 83.33 = 100) |

### 1.2 v2 — 심박수 보정

| 항목 | 값 / 공식 |
|------|-----------|
| HRmax | `220 − 나이` (Fox 1971, 기본값) |
| 옵션 | `208 − 0.7 × 나이` (Tanaka 2001) |
| 목표심박 영역 | 50~70% HRmax |
| 기준 시간 | 30분/일 목표심박 영역 |
| 최종점수 | `v1 × (0.7 + 0.3 × 심박계수)` |

### 1.3 v3 — 백분위 비교 가산점

| 항목 | 값 |
|------|-----|
| 비교 그룹 | 동성 + 동연령대 (10세 단위) |
| 최소 표본 | 30명 |
| 상위 10% | +10점 |
| 상위 20% | +5점 |
| 상위 30% | +3점 |

### 1.4 v4 — 만성질환 가중

| 질환 | 가중치 |
|------|--------|
| 당뇨 | +0.10 |
| 고혈압 | +0.10 |
| 심혈관 | +0.15 |
| 관절(근골격) | +0.15 |
| 호흡기 | +0.10 |
| 최대 multiplier | 1.30 (cap) |

---

## 2. 논문·공식 자료 근거

### 2.1 걸음수 권장 (8,000 vs 10,000)

| 출처 | 핵심 발견 | 권장값 |
|------|----------|--------|
| **Tudor-Locke et al., 2011** *(Int J Behav Nutr Phys Act)* | 건강한 성인 평균 4,000~18,000보/일. 30분 MVPA = 약 8,000보 | 성인 ≈ 10,000보 (단, 8,000도 합리적) |
| **Tudor-Locke et al., 2011 (특수 인구)** | 노인 평균 2,000~9,000보/일, 만성질환자 1,200~8,800보/일 | 노인 7,000~10,000 |
| **Lee et al., 2019** *(JAMA Internal Medicine)* | 노인 여성 16,741명. **약 4,400보**에서 사망률 유의 감소, **7,500보**에서 plateau | 노인 여성 ≈ 7,500보 |
| **Paluch et al., 2022** *(Lancet Public Health, meta-analysis 15 cohorts, n≈47k)* | **60세 미만 8,000~10,000보**, **60세 이상 6,000~8,000보**에서 사망률 감소 plateau | 연령별 차등 |
| **Paluch et al., 2021** *(JAMA Network Open, CARDIA)* | 중년 성인 ≥7,000보/일 vs <7,000보/일 → 사망률 50~70% 감소 | 중년 ≥7,000보 |
| **WHO Global Action Plan 2018–2030** | 성인 주 150분 중강도 신체활동 권고. (걸음수는 명시 X, 행동 환산 시 ≈ 7,000~8,000보) | 150min MVPA/주 |

**시사점**:
- 노인(60+)에서 7,500보는 충분하다는 강력한 근거 → 현재 v1의 60+ 계수 0.8(= 6,400보) 은 **공교롭게 Paluch 노인 범위(6,000~8,000) 하단에 부합**하나, "왜 0.8인가"라는 *이론적 근거*는 부재.
- 8,000보 ≈ Tudor-Locke "30분 MVPA 환산"의 합리적 절충 → v1의 8,000보 기준 자체는 방어 가능.

출처:
- Tudor-Locke et al. (2011) *How many steps/day are enough? For adults*. DOI: 10.1186/1479-5868-8-79. PMID: 21798015.
- Tudor-Locke et al. (2011) *How many steps/day are enough? For older adults and special populations*. DOI: 10.1186/1479-5868-8-80. PMID: 21798044.
- Lee I-M et al. (2019) *Association of Step Volume and Intensity With All-Cause Mortality in Older Women*. JAMA Intern Med. PMID: 31141585.
- Paluch AE et al. (2022) *Daily steps and all-cause mortality: a meta-analysis of 15 international cohorts*. Lancet Public Health. PMID: 35247352.
- Paluch AE et al. (2021) *Steps per Day and All-Cause Mortality in Middle-aged Adults (CARDIA)*. JAMA Netw Open.
- WHO (2018) *Global Action Plan on Physical Activity 2018–2030*. ISBN 978-92-4-151418-7. https://www.who.int/publications/i/item/9789241514187

---

### 2.2 HRmax 추정식 비교 표

| 공식 | 식 | 표본 / 출처 | 60세 예측값 | 평균 오차 (SEE) |
|------|-----|------------|------------|----------------|
| **Fox 1971** (220 − age) | `220 − age` | 비-임상 회고 추정, 원전 약함 | 160 bpm | ±10~15 bpm |
| **Tanaka 2001** | `208 − 0.7 × age` | Meta 351 연구 / n=18,712 + 검증 n=514 | 166 bpm | ±7 bpm (r = −0.90) |
| **Gellish 2007** | `207 − 0.7 × age` | 132명, 종단 908 트레드밀 검사 | 165 bpm | Tanaka와 거의 동일 |
| **Nes 2013** (HUNT) | `211 − 0.64 × age` | HUNT Fitness Study, n=3,320 | 172.6 bpm | ±10.8 bpm |

**핵심 결론**:
- **220 − age 는 60세에서 Tanaka 대비 약 −6 bpm 과소평가**. 노인일수록 오차 누적.
- Tanaka 공식은 메타 분석 + 독립 검증으로 가장 광범위하게 사용됨 (ACSM, AHA 권고).
- Nes 공식은 활동적인 사람에서 더 정확하나 표본 편향(노르웨이 백인).

출처:
- Tanaka H, Monahan KD, Seals DR (2001) *Age-predicted maximal heart rate revisited*. J Am Coll Cardiol 37(1):153–6. DOI: 10.1016/S0735-1097(00)01054-8. PMID: 11153730.
- Gellish RL et al. (2007) *Longitudinal modeling of the relationship between age and maximal heart rate*. Med Sci Sports Exerc 39(5):822–9. PMID: 17468581.
- Nes BM et al. (2013) *Age-predicted maximal heart rate in healthy subjects: The HUNT Fitness Study*. Scand J Med Sci Sports 23(6):697–704. DOI: 10.1111/j.1600-0838.2012.01445.x. PMID: 22376273.

---

### 2.3 운동 강도 영역 (ACSM)

**ACSM Guidelines for Exercise Testing and Prescription (11th ed., 2021)** — 강도 분류:

| 강도 | %HRmax | %HRR (Karvonen) | RPE (0–10) |
|------|--------|-----------------|-----------|
| 매우 약함 | <57% | <30% | <2 |
| 약함 (Light) | 57~63% | 30~39% | 2~3 |
| **중강도 (Moderate)** | **64~76%** | **40~59%** | 3~4 |
| **고강도 (Vigorous)** | **77~95%** | **60~89%** | 5~7 |
| 최대 | ≥96% | ≥90% | ≥8 |

**Karvonen 공식 (HRR 기반)**:
```
목표심박수 = (HRmax − HRrest) × 강도(%) + HRrest
```
- 안정시 심박수(HRrest)를 반영하여 개인화 정확도 ↑
- ACSM이 1차 권고 (특히 고령자·만성질환자에서 더 안전)

**Lemon-Aid v2의 50~70% HRmax 영역 의미**:
- 50~63%는 ACSM "Light" 영역 → "운동 효과" 보장 부족
- 64~70%만 "Moderate" 영역에 해당
- → **권장 영역을 64~76% HRmax (또는 40~59% HRR)** 로 좁히는 것이 ACSM 정합

출처:
- Garber CE et al. (2011) *ACSM position stand: Quantity and quality of exercise...*. Med Sci Sports Exerc 43(7):1334–59. PMID: 21694556.
- ACSM (2021) *ACSM's Guidelines for Exercise Testing and Prescription* (11th ed.).
- ACSM (2020) *Tips for Monitoring Aerobic Exercise Intensity* (Zuhl M). https://acsm.org/wp-content/uploads/2025/02/Exercise-intensity-infographic-PDF.pdf
- Karvonen MJ, Kentala E, Mustala O (1957) *The effects of training on heart rate: a longitudinal study*. Ann Med Exp Biol Fenn 35(3):307–15.

---

### 2.4 백분위 비교 동기 (행동과학)

**이론적 토대**:
1. **Festinger Social Comparison Theory (1954)** — 사람은 자신의 능력·의견을 평가하기 위해 타인과 비교한다. 상향 비교(upward)는 자기개선 동기, 하향 비교(downward)는 자존감 회복.
2. **Self-Determination Theory (Deci & Ryan)** — 자율성(autonomy)·유능감(competence)·관계성(relatedness)이 내재적 동기의 세 축. 백분위 피드백은 **유능감** 지각을 강화.

**경험적 근거 (gamification + 사회비교)**:
- Cugelman B (2013) *Gamification: what it is and why it matters to digital health behavior change*. JMIR Serious Games. — 리더보드/포인트 효과 메타.
- Sailer M et al. (2017) *How gamification motivates: An experimental study*. Computers in Human Behavior. — 사회 비교 요소가 *유능감*과 *관계성* 욕구를 충족.
- Tu R et al. (2019) *Users' intention to continue using social fitness-tracking apps: ECT and Social Comparison Theory perspective*. — 사회 비교가 지속 사용 의도를 예측.
- Wu Y et al. (2025) *The code of sustainable success in fitness apps: social comparison mechanism enabled by user facilitated supports*. Frontiers Public Health.

**주의 — 부정적 효과**:
- 하위 사용자에서 **사회적 좌절(social demotivation)** 위험 → 하위권 노출 최소화 필요.
- "본인 vs 자기 과거" 비교(temporal self-comparison)가 SDT 자율성 침해 없이 안전.

**Lemon-Aid v3 의 함의**:
- 상위 10/20/30%에만 가산점 → **상향 비교 동기 활용**, 하위 표시 없음 → 좌절 방지. 설계는 SDT 정합.
- 최소 30명 표본은 정규근사(CLT) 기준선이지만 백분위 추정 안정성에는 부족 (n≥100 권장).

---

### 2.5 만성질환 운동 가이드 (HHS / ACSM / ESC / ADA)

| 가이드 | 핵심 권고 |
|--------|----------|
| **HHS Physical Activity Guidelines for Americans, 2nd ed. (2018)** | 만성질환자는 가능한 한 일반 권고(150min/주 MVPA)를 따르고, 불가능하면 "as physically active as their abilities and conditions allow". 10대 만성질환 중 7개가 신체활동으로 호전. |
| **ACSM's Exercise Management for Persons With Chronic Diseases and Disabilities (4th ed., 2016)** | 질환별 FITT(Frequency, Intensity, Time, Type) 처방. CAD, COPD, T2DM, 관절염, 비만 별도 챕터. |
| **ESC 2020 Sports Cardiology Guidelines** *(Eur Heart J 42:17–96)* | 안정형 관상동맥질환자: 중강도 유산소 ≥150min/주, 위험층화 후 강도 결정. 고혈압 환자: 동적 유산소 + 저강도 저항운동 권고. |
| **ADA Standards of Care 2024** | T2DM: 중강도 ≥150min/주 (또는 고강도 ≥75min/주), 저항운동 주 2~3회, 30분 이상 좌식 시 휴식. 활동량 부족 시 HbA1c 0.6~0.7% 추가 감소 효과. |
| **Arthritis Foundation / OARSI 2019** | 무릎/고관절 골관절염: 저강도 유산소 (수영·자전거·걷기) + 근력. **통증 없는 범위 내** 일일 활동. |
| **GOLD 2024 (COPD)** | 폐재활 핵심으로 유산소 + 저항운동. 호흡곤란 척도(mMRC)에 맞춘 점진 증가. |

**핵심: 만성질환자의 운동 이득은 동일 활동량에서 상대적으로 더 큼**
- T2DM: 150 min/주 MVPA → HbA1c −0.6~0.7%, 인슐린 감수성 ↑↑ (Colberg SR et al., 2016 ADA Position Statement, *Diabetes Care* 39:2065–79)
- CAD: 심장재활(운동 포함) → 심혈관 사망률 26% 감소 (Anderson L et al., 2016 Cochrane Review)
- COPD: 폐재활 → 6분 보행거리 +50m, 입원 빈도 감소 (Spruit MA et al., 2013 ATS/ERS Statement)
- 골관절염: 운동 → NSAID 사용량 감소, 통증 VAS −2~3점 (Fransen M et al., 2015 Cochrane)

**→ 임상적으로 만성질환자의 "한 걸음의 한계 이득(marginal health benefit)"이 더 크다는 강력한 근거.**

출처:
- U.S. HHS (2018) *Physical Activity Guidelines for Americans, 2nd ed.* https://health.gov/sites/default/files/2019-09/Physical_Activity_Guidelines_2nd_edition.pdf
- Moore GE, Durstine JL, Painter PL (2016) *ACSM's Exercise Management for Persons With Chronic Diseases and Disabilities*, 4th ed., Human Kinetics.
- Pelliccia A et al. (2021) *2020 ESC Guidelines on sports cardiology and exercise in patients with cardiovascular disease*. Eur Heart J 42(1):17–96. DOI: 10.1093/eurheartj/ehaa605. PMID: 32860412.
- American Diabetes Association (2024) *Standards of Care in Diabetes — 2024*. Diabetes Care 47(Suppl 1).
- Colberg SR et al. (2016) *Physical Activity/Exercise and Diabetes: A Position Statement of the ADA*. Diabetes Care 39(11):2065–79.

---

## 3. 평가

### 3.1 v1 — 강점·약점

**강점**
- 8,000보 기준은 Tudor-Locke "30분 MVPA ≈ 8,000보" 등가성에 부합.
- 1.2 cap (= 9,600보 또는 권장의 120%) 은 *over-exercise* 패널티 방지 측면에서 합리적.
- 점수 산식이 단순·투명 (사용자 설명 용이).

**약점 및 검토 사항**

| 항목 | 문제 | 근거 |
|------|------|------|
| **8,000보 고정 기준** | 연령·성별·체력 분리 없이 단일 베이스라인 사용. Paluch 2022 메타에 따르면 노인 6,000~8,000, 청장년 8,000~10,000 plateau. | Paluch 2022 Lancet Public Health |
| **나이계수 60+ = 0.8 (6,400보)** | Lee 2019(7,500보), Paluch 2022(노인 6,000~8,000)와 비교 시 **하한선에 위치**. 임상적으로 안전하나 *과도하게 관대*. | Lee 2019 JAMA Intern Med |
| **BMI계수 비만 = 1.15** | 의도("비만일수록 더 많이 걸어야 함") 자체는 체중 감량 가이드 부합. 단, **임상적으로 비만자는 관절 부하 + 체력 부족으로 같은 걸음수를 달성하기 더 힘듦** → "권장량을 올림"은 *목표 달성률을 떨어뜨려 동기 저해* 우려. | BASS / Marathon Handbook reviews; 임상 GPP |
| **BMI계수 저체중 = 0.9** | 저체중에서 권장을 낮추는 의학적 근거 부족. 저체중은 근감소·골다공증 위험으로 *오히려 근력+활동* 권고. | ACSM 일반 권고 |
| **성별계수 여성 = 0.95** | 신장·근육량 차이 반영이라면 합리적 (보폭 차이로 동일 거리 시 여성이 +5% 걸음). 단, 명시적 근거 인용 필요. | Tudor-Locke 2011 (보폭 보정) |

### 3.2 v2 — HRmax 공식 선택

**현황**
- 기본값: `220 − age` (Fox 1971) — 임상에서 가장 널리 사용되나 60세에서 −6~−10 bpm 오차.
- 옵션: `208 − 0.7 × age` (Tanaka 2001) — 메타·검증 모두 우수.
- 목표 영역 50~70% HRmax: ACSM 기준 "Light~Moderate 하한" → 운동 효과 보장 약함.

**평가**
1. **기본 공식을 Tanaka로 전환 권고**. 60세에서 220−60=160 → 50~70% = 80~112 bpm. Tanaka 적용 시 208−42=166 → 50~70% = 83~116 bpm. *임상적으로 더 안전하고 과소 처방 방지*.
2. 다만, "회사 가이드 재현용 기본값 유지" 정책일 경우 `220−age`를 default로 두되, **UI에서 "더 정확한 추정"으로 Tanaka 토글 노출** 권장.
3. **Karvonen HRR 옵션 추가**: HRrest 입력 가능한 사용자(웨어러블 사용자)에게 개인화된 목표 심박 제공.

### 3.3 v3 — 백분위 비교

**강점**
- 상위권에만 가산 → 하향 사회비교의 좌절 회피 (SDT 정합).
- 가산 폭(+3/+5/+10)이 보수적이라 점수 왜곡 적음.

**약점**
- **최소 표본 30명**은 평균의 정규근사 기준이지 *백분위(quantile) 안정성* 기준이 아님. 백분위 90% 추정에는 n≥100 권장. n=30이면 90백분위의 표준오차가 매우 큼.
- 동성·동연령대 그룹화는 좋으나 **활동 환경 (직업/거주지/계절)** 미반영.
- "상위 10%"의 절대값이 그룹별로 매우 다름 → 일부 그룹에서는 7,000보, 일부는 15,000보가 상위 10%. 사용자가 *왜 같은 점수를 받았는지* 설명 어려움.
- Outlier(이상치) 처리 부재. 1명의 20,000보 사용자가 상위 컷오프를 왜곡.

### 3.4 v4 — 만성질환 가중

**현 가중치의 의미 (수치 해석)**

| 질환 | +가중치 | 의미 (실제걸음/권장 ratio = 1.0일 때) |
|------|--------|------|
| 당뇨 +0.10 | 1.10 multiplier | 점수 100 → 110 (cap 100이면 무효, cap 130까지 허용 시 +10) |
| 고혈압 +0.10 | 1.10 | 동일 |
| 심혈관 +0.15 | 1.15 | +15점 |
| 관절 +0.15 | 1.15 | +15점 |
| 호흡기 +0.10 | 1.10 | +10점 |
| 최대 cap | 1.30 | 2개 이상 합산 시 1.30 상한 |

**평가 — 왜 만성질환자에게 가중치를 더 주는가**

1. **의학적 근거 (marginal benefit 차이)**
   - 일반 성인이 8,000보를 걸을 때 얻는 사망률 감소(약 40~50%, Paluch 2022)에 비해,
   - T2DM 환자가 동일 활동량에서 얻는 추가 이득: HbA1c −0.6~0.7%, 심혈관 사건 감소, 인슐린 감수성 ↑↑ (Colberg 2016 ADA).
   - CAD 환자: 심장재활 운동 → 사망률 추가 26% 감소 (Anderson 2016 Cochrane).
   - COPD: 6분 보행거리 +50m, 입원 −40% (Spruit 2013).
   - → **동일 1보의 건강 효용이 만성질환자에서 더 크다**는 근거가 강력함.

2. **UX/행동과학 근거 (지속 가능성)**
   - 만성질환자는 *낮은 체력 기저*로 절대 걸음수가 낮음 (Tudor-Locke 2011: 1,200~8,800보).
   - 일반 권장(8,000보)을 그대로 적용 시 점수가 항상 낮아 **자기효능감(self-efficacy) 저하 → 중도 이탈** 위험.
   - 가중치는 "노력 대비 보상 비율" 을 정상화하여 *상대적 성공 경험*을 제공.
   - SDT의 **유능감 욕구** 충족 → 내재적 동기 보존.

3. **약물–운동 시너지 (treatment synergy)**
   - 메트포민 + 운동: 단독 대비 인슐린 감수성 +25~40% (Boulé NG et al., 2003 Diabetes Care).
   - β-blocker 복용 CAD 환자: HRmax가 약 20~30 bpm 낮음 → **%HRmax 기반 강도 처방이 의미 없음** → Karvonen 또는 RPE 사용 필요.
   - ACE 억제제 / 이뇨제: 운동 중 저혈압 위험 → 강도 보수적 설정.

4. **약점 / 주의사항**
   - 가중치 +0.10, +0.15는 **현재 임상 효과 크기가 아닌 "우선순위" 휴리스틱**. 정량적 근거(예: 메타분석 효과크기)와 직접 매핑되지 않음.
   - 다중 질환(comorbidity)의 가산 방식이 단순 덧셈 → cap 1.30 적용 전 비현실적으로 누적 가능 (예: 5개 질환 합 = 0.60 → cap 1.30).
   - **UX 위험**: "질환이 있으면 점수가 잘 나온다"가 *"질환을 권장한다"*로 오해될 가능성. → **"질환 개선 점수"로 표기 금지**, "활동 동기 점수" 또는 "맞춤형 보상"으로 표현.
   - 일부 질환(예: 불안정 협심증, 급성 관절염 flare)은 **운동 제한**이 우선 → 가중치 적용 전 의료진 클리어런스 확인 필요.

---

## 4. 수정 권고

### 4.1 v1 우선 수정

**(A) 연령대별 권장 걸음수 옵션화** — Tudor-Locke + Paluch 2022 근거.

```python
def base_steps_by_age(age: int) -> int:
    if age < 40:   return 9000   # Paluch <60세 8k~10k 중간값
    elif age < 60: return 8000   # 회사 기본값 유지
    elif age < 75: return 7000   # Paluch 60+ 6k~8k 중간값
    else:          return 6000   # Lee 2019 노인여성 7,500 plateau, 75+ 보수적
```

**(B) BMI계수 의미 명확화 — *목표(target)* vs *부담(load)***

| BMI | 현 계수 | 권고 계수 | 비고 |
|-----|--------|----------|------|
| <18.5 (저체중) | 0.9 | **1.0** | 활동량 감소 권고 근거 없음. 동일 권장. |
| 18.5~24.9 (정상) | 1.0 | 1.0 | 유지 |
| 25~29.9 (과체중) | 1.1 | **1.05** | 체중 관리 목적, 단 점진 증가 |
| ≥30 (비만) | 1.15 | **1.05** *(목표용)* 또는 **0.95** *(달성용)* | 정책 선택: 체중 감량 목표 시 ↑, 동기 유지 목적 시 ↓ |

**핵심**: BMI계수가 "더 많이 걷자(목표)"인지 "달성 가능한 권장량(adjusted target)"인지 *제품 정책*을 명문화. 권장: 비만에서 권장량을 ↑하지 않고, 대신 **운동 종류 다양화 (수영·자전거)** 옵션을 UI에서 제공.

**(C) Cap 조정**
- 현재 1.2 (= 9,600~12,000보 cap)는 합리적. 유지 권고.

### 4.2 v2 수정

```python
# 기본 공식 변경: Tanaka 2001
def hr_max(age: int, formula: str = "tanaka") -> float:
    if formula == "tanaka":   return 208 - 0.7 * age   # 권장 default
    elif formula == "fox":    return 220 - age          # 기존 호환
    elif formula == "gellish":return 207 - 0.7 * age
    elif formula == "nes":    return 211 - 0.64 * age   # 활동적 사용자
    raise ValueError

# Karvonen 옵션 추가 (HRrest 입력 시)
def target_hr(age, intensity_pct, hr_rest=None, formula="tanaka"):
    hrmax = hr_max(age, formula)
    if hr_rest is None:
        return hrmax * intensity_pct  # %HRmax 방식
    else:
        return (hrmax - hr_rest) * intensity_pct + hr_rest  # Karvonen HRR
```

**목표 영역 재정의**:
- 기존 50~70% HRmax → **64~76% HRmax (Moderate)** 또는 **40~59% HRR (Karvonen Moderate)** 으로 좁힘. ACSM 정합.
- 만성질환자(특히 β-blocker 복용자)는 %HRmax 무효 → **RPE 12~14 (Borg 6-20)** 또는 talk-test 사용 권고. UI에서 "약 복용 중" 토글 시 자동 전환.

### 4.3 v3 수정

**(A) 표본 부족 시 확장 로직**

```
1. 동성 × 동연령대(5세 단위) → n ≥ 100이면 사용
2. 동성 × 동연령대(10세 단위) → n ≥ 100이면 사용
3. 동성 × 광연령대 (<40 / 40~59 / 60+) → n ≥ 100이면 사용
4. 동연령대(10세) 만 → n ≥ 100
5. 전체 사용자 → fallback
각 단계 메타데이터 함께 노출 ("당신은 30대 여성 254명 중 상위 12%입니다")
```

**(B) Outlier 처리**
- 상위 1% (또는 일일 25,000보 초과) 는 백분위 계산에서 제외 (winsorization).
- 하위 0%(=0보) 7일 이상 연속은 *비활성 사용자*로 별도 cohort.

**(C) Temporal self-comparison 추가 (SDT 자율성 보존)**
- 사회 비교 외에 "지난 4주 평균 대비 +12%" 같은 *자기 비교* 점수도 동시 제공. → 하위권 사용자에게도 긍정 피드백.

### 4.4 v4 수정 — **사용자 핵심 질문에 대한 답**

#### 왜 만성질환 환자와 일반 사용자를 분리해서 가중치를 적용하는가

**3중 근거**:

**(1) 의학적 — 한계 이득(Marginal Health Benefit)이 더 큼**
- HHS 2018 가이드 §"Adults with Chronic Conditions": *"For people with chronic conditions, the benefits of physical activity often exceed those for the general population."*
- 정량 근거:
  - T2DM: 150 min/주 → HbA1c −0.6~0.7%, 심혈관 사건 ↓ (Colberg 2016).
  - CAD: 심장재활 → 사망률 −26% (Anderson 2016 Cochrane).
  - COPD: 폐재활 → 6분 보행 +50m, 입원 −40% (Spruit 2013).
  - 골관절염: 운동 → 통증 VAS −2~3 (Fransen 2015 Cochrane).
  - 고혈압: 유산소 운동 → 수축기 혈압 −5~7 mmHg (Cornelissen 2013 J Am Heart Assoc).
- 즉, **동일 활동의 *건강 효용 단가*가 만성질환자에서 더 큼** → 점수에 반영하는 것이 의학적으로 합당.

**(2) UX/행동과학 — 자기효능감과 지속 가능성**
- 만성질환자의 절대 체력 기저가 낮음 (Tudor-Locke 2011: 평균 1,200~8,800보).
- 동일 권장량 + 동일 점수 산식 → 점수가 항상 50점대 → **학습된 무력감(learned helplessness)** 위험.
- 가중치는 "노력 대비 점수 비율"을 정상화 → SDT의 **유능감(competence) 욕구** 충족 → 내재적 동기 보존 → 장기 참여율 ↑.
- 행동변화 이론(Self-Efficacy Theory, Bandura)에 따르면 *작은 성공 경험의 누적*이 운동 습관 형성의 핵심.

**(3) 약물–운동 시너지 — 처방 정확성**
- 메트포민 + 운동 → 인슐린 감수성 +25~40% (Boulé 2003).
- β-blocker 복용 시 HRmax −20~30 bpm → %HRmax 기준 무효 → **별도 강도 처방 필요**.
- 가중치는 "다른 처방 체계"를 시스템에 신호로 주는 메타-마커 역할.

#### 단, 명확히 할 사항

⚠️ **"질환 개선 점수"로 표현 금지**.
- UI 명칭은 **"활동 동기 점수(Activity Motivation Score)"** 또는 **"개인 맞춤 보상"** 으로.
- 가중치 노출은 "당신의 건강 상태를 고려한 보상 +12점" 정도로 일반화.
- "질환이 점수를 높인다"는 인상이 *질환을 권장*하는 모럴 해저드로 오해될 가능성 차단.

#### 권고: 질환별 권장량·가중치 매핑 (수정안)

| 질환군 | 일반 권장 (가이드) | Lemon-Aid 권장 걸음수 | 가중치 | 강도 처방 메타 | 근거 |
|--------|-------------------|---------------------|--------|---------------|------|
| T2DM (제2형 당뇨) | 150min MVPA/주 + 저항 2~3회 | 7,000~8,000 | +0.10 | 식후 보행 권장 (혈당 spike ↓) | ADA 2024 |
| 고혈압 | 150min/주 동적 유산소 + 저강도 저항 | 7,000~8,000 | +0.10 | Valsalva 회피, 강도 64~76% HRmax | ESC 2018 |
| CAD/심혈관 (안정) | 위험층화 후 ≥150min/주 | 6,000~7,000 | +0.15 | β-blocker 시 RPE 사용 | ESC 2020 |
| 골관절염 | 무릎/고관절 부하 ↓ 운동, 통증 없는 범위 | 5,000~7,000 | +0.15 | 수영·자전거 옵션 동시 제공 | OARSI 2019 |
| COPD/호흡기 | 폐재활, mMRC 따라 점진 | 4,000~6,000 | +0.10 | 호흡곤란 척도 모니터 | GOLD 2024 |
| 비만 (BMI≥30) | 점진 증가, 60min/일 목표 | 6,000~8,000 (점진) | (별도) | 관절 부하 고려 | ACSM EIM |

#### 수정된 v4 의사 코드

```python
@dataclass
class UserProfile:
    age: int
    sex: str          # "M"|"F"
    bmi: float
    hr_rest: int | None = None
    on_beta_blocker: bool = False
    chronic_conditions: list[str] = field(default_factory=list)
    # e.g. ["t2dm", "htn", "cad", "oa", "copd"]

# 질환별 가이드 매핑 (걸음수 권장 + 가중치)
CONDITION_PROFILE = {
    "t2dm":  {"steps": 7500, "weight": 0.10, "intensity_cap": 0.76},
    "htn":   {"steps": 7500, "weight": 0.10, "intensity_cap": 0.76},
    "cad":   {"steps": 6500, "weight": 0.15, "intensity_cap": 0.70, "rpe_only_if_bb": True},
    "oa":    {"steps": 6000, "weight": 0.15, "intensity_cap": 0.70},
    "copd":  {"steps": 5000, "weight": 0.10, "intensity_cap": 0.65},
}
MAX_MULTIPLIER = 1.30
MAX_WEIGHT_SUM = 0.30   # cap before multiplication


def chronic_weight(conditions: list[str]) -> float:
    raw = sum(CONDITION_PROFILE[c]["weight"] for c in conditions
              if c in CONDITION_PROFILE)
    return min(raw, MAX_WEIGHT_SUM)


def recommended_steps(profile: UserProfile) -> int:
    # 1) 질환이 있으면 질환별 권장의 최솟값 (가장 보수적)
    if profile.chronic_conditions:
        cond_steps = [CONDITION_PROFILE[c]["steps"]
                      for c in profile.chronic_conditions
                      if c in CONDITION_PROFILE]
        if cond_steps:
            return min(cond_steps)
    # 2) 없으면 연령대 기반
    return base_steps_by_age(profile.age)


def activity_score(profile: UserProfile, actual_steps: int,
                   minutes_in_target_hr: int) -> float:
    rec = recommended_steps(profile)
    base = min(actual_steps / rec, 1.2) * 83.33      # v1
    hr_factor = min(minutes_in_target_hr / 30, 1.0)
    v2 = base * (0.7 + 0.3 * hr_factor)              # v2
    # v3: 백분위 가산 (별도 함수, 본문 §4.3 참조)
    v3 = v2 + percentile_bonus(profile, actual_steps)
    # v4: 만성질환 multiplier
    multiplier = 1.0 + chronic_weight(profile.chronic_conditions)
    multiplier = min(multiplier, MAX_MULTIPLIER)
    final = min(v3 * multiplier, 130)                # absolute cap
    return round(final, 1)
```

**UX 노출 문안 (권고)**:
- ❌ "당신의 당뇨로 인해 +10% 보너스가 적용되었습니다"
- ✅ "맞춤형 활동 보너스 +10% (당신의 건강 프로필 반영)"

---

## 5. 근거 수준 재평가

| 항목 | 근거 수준 (GRADE-like) | 비고 |
|------|----------------------|------|
| 성인 7,000~10,000보 권장 | **High** | Paluch 2022 Lancet PH meta n≈47k, 다수 RCT/cohort |
| 노인 6,000~8,000보 권장 | **High** | Lee 2019 JAMA IM + Paluch 2022 |
| Tanaka 공식 220-age 보다 정확 | **High** | Tanaka 2001 meta + 독립검증 |
| ACSM 강도 영역 64~76%/77~95% | **High** (가이드라인) | ACSM 11th ed |
| 사회비교 동기 효과 | **Moderate** | 다수 관찰연구, RCT 일부 |
| 만성질환자 운동 marginal benefit ↑ | **High** | HHS, ACSM, ESC, ADA 가이드 |
| 가중치 +0.10/+0.15 *절대값* | **Low** | 휴리스틱, 효과크기 직접 매핑 없음 |
| BMI계수 1.15의 정당성 | **Low** | 임상 합의 부재, 제품 정책 영역 |

---

## 6. 참고 문헌

### 걸음수
1. Tudor-Locke C, Craig CL, Brown WJ, et al. *How many steps/day are enough? For adults*. Int J Behav Nutr Phys Act. 2011;8:79. DOI: 10.1186/1479-5868-8-79. PMID: 21798015. https://pubmed.ncbi.nlm.nih.gov/21798015/
2. Tudor-Locke C, Craig CL, Aoyagi Y, et al. *How many steps/day are enough? For older adults and special populations*. Int J Behav Nutr Phys Act. 2011;8:80. PMID: 21798044. https://pmc.ncbi.nlm.nih.gov/articles/PMC3169444/
3. Lee I-M, Shiroma EJ, Kamada M, et al. *Association of Step Volume and Intensity With All-Cause Mortality in Older Women*. JAMA Intern Med. 2019;179(8):1105–12. PMID: 31141585. https://jamanetwork.com/journals/jamainternalmedicine/fullarticle/2734709
4. Paluch AE, Bajpai S, Bassett DR, et al. *Daily steps and all-cause mortality: a meta-analysis of 15 international cohorts*. Lancet Public Health. 2022;7(3):e219–28. PMID: 35247352. https://www.thelancet.com/journals/lanpub/article/PIIS2468-2667(21)00302-9/fulltext
5. Paluch AE, Gabriel KP, Fulton JE, et al. *Steps per Day and All-Cause Mortality in Middle-aged Adults in the CARDIA Study*. JAMA Netw Open. 2021;4(9):e2124516. https://jamanetwork.com/journals/jamanetworkopen/fullarticle/2783711
6. WHO. *Global Action Plan on Physical Activity 2018–2030*. Geneva: World Health Organization; 2018. https://www.who.int/publications/i/item/9789241514187

### HRmax / 강도
7. Tanaka H, Monahan KD, Seals DR. *Age-predicted maximal heart rate revisited*. J Am Coll Cardiol. 2001;37(1):153–6. PMID: 11153730. https://www.sciencedirect.com/science/article/pii/S0735109700010548
8. Gellish RL, Goslin BR, Olson RE, et al. *Longitudinal modeling of the relationship between age and maximal heart rate*. Med Sci Sports Exerc. 2007;39(5):822–9. PMID: 17468581.
9. Nes BM, Janszky I, Wisløff U, et al. *Age-predicted maximal heart rate in healthy subjects: The HUNT Fitness Study*. Scand J Med Sci Sports. 2013;23(6):697–704. PMID: 22376273. https://onlinelibrary.wiley.com/doi/full/10.1111/j.1600-0838.2012.01445.x
10. Garber CE, Blissmer B, Deschenes MR, et al. *ACSM position stand: Quantity and quality of exercise for developing and maintaining cardiorespiratory, musculoskeletal, and neuromotor fitness in apparently healthy adults*. Med Sci Sports Exerc. 2011;43(7):1334–59. PMID: 21694556.
11. American College of Sports Medicine. *ACSM's Guidelines for Exercise Testing and Prescription*. 11th ed. Wolters Kluwer; 2021.
12. Karvonen MJ, Kentala E, Mustala O. *The effects of training on heart rate: a longitudinal study*. Ann Med Exp Biol Fenn. 1957;35(3):307–15.

### 행동과학
13. Festinger L. *A theory of social comparison processes*. Hum Relat. 1954;7(2):117–40.
14. Deci EL, Ryan RM. *Self-determination theory: A macrotheory of human motivation, development, and health*. Can Psychol. 2008;49(3):182–5.
15. Teixeira PJ, Carraça EV, Markland D, et al. *Exercise, physical activity, and self-determination theory: A systematic review*. Int J Behav Nutr Phys Act. 2012;9:78. PMID: 22726453. https://pmc.ncbi.nlm.nih.gov/articles/PMC3441783/
16. Sailer M, Hense JU, Mayr SK, Mandl H. *How gamification motivates: An experimental study of the effects of specific game design elements on psychological need satisfaction*. Comput Human Behav. 2017;69:371–80.
17. Tu R, Hsieh P, Feng W. *Users' intention to continue using social fitness-tracking apps: ECT and Social Comparison Theory*. Behav Inf Technol. 2019;38(8):793–810.
18. Johnson D, Deterding S, Kuhn KA, et al. *Gamification for health and wellbeing: A systematic review*. Internet Interv. 2016;6:89–106. PMID: 30135818. https://pmc.ncbi.nlm.nih.gov/articles/PMC6096297/

### 만성질환 운동 가이드
19. U.S. Department of Health and Human Services. *Physical Activity Guidelines for Americans*. 2nd ed. Washington, DC; 2018. https://health.gov/sites/default/files/2019-09/Physical_Activity_Guidelines_2nd_edition.pdf
20. Moore GE, Durstine JL, Painter PL, eds. *ACSM's Exercise Management for Persons With Chronic Diseases and Disabilities*. 4th ed. Champaign, IL: Human Kinetics; 2016.
21. Pelliccia A, Sharma S, Gati S, et al. *2020 ESC Guidelines on sports cardiology and exercise in patients with cardiovascular disease*. Eur Heart J. 2021;42(1):17–96. PMID: 32860412. https://academic.oup.com/eurheartj/article/42/1/17/5898937
22. American Diabetes Association. *Standards of Care in Diabetes — 2024*. Diabetes Care. 2024;47(Suppl 1):S1–S321.
23. Colberg SR, Sigal RJ, Yardley JE, et al. *Physical Activity/Exercise and Diabetes: A Position Statement of the American Diabetes Association*. Diabetes Care. 2016;39(11):2065–79. PMID: 27926890.
24. Anderson L, Oldridge N, Thompson DR, et al. *Exercise-based cardiac rehabilitation for coronary heart disease: Cochrane systematic review and meta-analysis*. J Am Coll Cardiol. 2016;67(1):1–12. PMID: 26764059.
25. Spruit MA, Singh SJ, Garvey C, et al. *ATS/ERS Statement: Key concepts and advances in pulmonary rehabilitation*. Am J Respir Crit Care Med. 2013;188(8):e13–64. PMID: 24127811.
26. Fransen M, McConnell S, Harmer AR, et al. *Exercise for osteoarthritis of the knee: a Cochrane systematic review*. Br J Sports Med. 2015;49(24):1554–7.
27. Boulé NG, Kenny GP, Haddad E, et al. *Meta-analysis of the effect of structured exercise training on cardiorespiratory fitness in Type 2 diabetes mellitus*. Diabetologia. 2003;46(8):1071–81.
28. Cornelissen VA, Smart NA. *Exercise training for blood pressure: a systematic review and meta-analysis*. J Am Heart Assoc. 2013;2(1):e004473. PMID: 23525435.

---

*문서 버전: 2026-05-26 / 작성: Lemon-Aid Core Algorithm Team*
