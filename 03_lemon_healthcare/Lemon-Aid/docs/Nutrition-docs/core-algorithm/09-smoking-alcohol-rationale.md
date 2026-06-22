# 09. 흡연·음주 반영 — 알고리즘 통합 근거

> **문서 정보**
> 버전: v1.0 | 작성일: 2026-05-26 | 상태: 평가 완료
> 대상: Lemon-Aid `07-core-algorithm.md` v1.1의 8개 회사 정의 알고리즘 + 4개 갭 알고리즘 전체에서 **흡연·음주 변수가 반영되지 않은 갭**을 보완

---

## 📋 한 줄 요약

> 기존 알고리즘은 **만성질환**(v4)과 **흡연자 + 베타카로틴 경고**(목적별 매트릭스)만 반영. 그러나 흡연·음주는 *조절 가능한 위험 요인*으로 모든 알고리즘에 영향을 준다. 본 문서는 6개 영역(BMR·체중 / BMR·체중·운동 / 영양·흡연 / 영양·음주 / 운동·흡연 / 운동·음주)을 *논문·공식 가이드 근거*로 종합하고, Lemon-Aid 12개 알고리즘에 어떻게 반영해야 할지 권고를 제시한다.

---

## 0. 현재 갭 확인

`docs/Nutrition-docs/core-algorithm/` 내 9개 평가 문서 grep 결과:
- 7개 문서에서 흡연/음주 언급 **0회**
- `06-goal-matrix.md` 20회 (흡연자 + 베타카로틴 경고만)
- `08-references.md` 2회 (ATBC/CARET 인용)

→ **BMI / 활동점수 v1~v4 / BMR·TDEE / 체중 예측 / 영양 진단 / 만성질환 분기 모두에서 흡연·음주가 반영 안 됨**. 본 문서가 이 갭을 채운다.

---

## A. 흡연이 BMR·체중·운동에 미치는 영향

### A.1 니코틴의 BMR / 에너지 소비 효과

- **Hofstetter A et al. NEJM 1986** — 흡연자 24h 총에너지소비 **2,230 → 2,445 kcal (+10%, p<0.001)**. 단, *BMR 자체*는 거의 변화 없음 (DOI: 10.1056/NEJM198601093140204)
- **Perkins KA. J Appl Physiol 1992** — 만성 RMR 차이는 미미. 흡연이 체중에 미치는 효과는 *급성 thermogenesis + 식욕 억제*의 합산
- **Marks BL, Perkins KA. Sports Med 1990** — 니코틴 급성 RMR +3~10%

→ **요약**: 활성 흡연 중 24h 에너지 소비 +5~10%이나, 만성 BMR은 영구적으로 오르지 않음.

### A.2 흡연자 식욕 억제 + 금연 후 식욕 증가

- **Mineur YS et al. Science 2011** — 니코틴 → 시상하부 α3β4 nAChR → POMC 뉴런 활성화 → 식이 섭취 최대 -50% (DOI: 10.1126/science.1201889)

### A.3 금연 후 체중 변화

- **Aubin HJ et al. BMJ 2012 메타분석** — 약물치료 없는 금연자:
  - 3개월: +2.85 kg
  - 6개월: +4.23 kg
  - **12개월: +4.67 kg (95% CI 3.96–5.38)**
  - 단 *변동 폭 크다* — 12개월 시점 16%는 체중 감소, 13%는 +10 kg 이상
- **Filozof C et al. Obes Rev 2004** — 원인: 에너지 소비 감소 + 식이 섭취 증가 + LPL 활성 변화
- **CDC Surgeon General Report** — 평균 약 **2.3 kg(5 lb)** 증가, 그러나 금연의 건강 이득이 *압도적으로* 큼

### A.4 흡연 + 운동 능력 (FEV1, VO2max)

- **Conway TL, Cronan TA. Prev Med 1992** — 흡연 → VO2max ↓ (Navy 코호트)
- **Su FY et al. Can Respir J 2020 (CHIEF Study)** — 3,669명, 흡연자가 모든 fitness 지표 저하 (DOI: 10.1155/2020/5968189)
- **FEV1 감소율**: 현재 흡연자(≥30개비) 비흡연자 대비 약 13~14배 빠름 (Lung Health Study)
- **CO-Hb**: CO가 Hb 친화도 약 200배 → COHb ↑ → 산소 운반 능력 ↓

### A.5 간접흡연

- **Flouris AD et al. JCEM 2008** — 1시간 간접흡연 → 안정시 에너지소비량·T3/fT4 일시 ↑
- 그러나 *급성 스트레스 반응*에 가까움 → **BMR 보정 변수로 사용 금지**

### A.6 Lemon-Aid 반영 권고

1. **BMR 공식 자체에는 흡연 보정을 넣지 말 것** (Perkins 1992 — 만성 RMR 차이 미미)
2. 흡연 상태는 별도 *behavior risk flag*로 받고 TDEE/권장 칼로리에 직접 가중하지 않음
3. **금지 표현**:
   - "흡연자는 BMR이 높으니 칼로리를 더 섭취해도 된다" → **금지**
   - "다이어트 중에는 흡연이 도움이 될 수 있다" → **금지**
4. 데이터 모델: `smoking_status ∈ {never, former_<1y, former_≥1y, current_light(<10/d), current_heavy(≥10/d)}`

---

## B. 음주가 BMR·체중·운동에 미치는 영향

### B.1 알코올 칼로리·대사

- 알코올 = **7 kcal/g** 빈 칼로리 (탄수화물·단백 4, 지방 9)
- **Suter PM 1992 NEJM / 2005 Crit Rev Clin Lab Sci** — 알코올은 우선 산화, **24h 지방 산화 ↓ → 알코올 에너지의 74%만큼 지방 저장 ↑**
- 알코올 + 만성 → PPARα, AMPK 억제로 추가 지방산 산화 차단

### B.2 한국 주류 칼로리 (참고)

| 주종 | 표준 용량 | 칼로리 |
|---|---|---|
| **소주** | 1병 (360 mL, 17~19°) | **≈ 400–410 kcal** |
| **맥주** | 500 mL | ≈ 230 |
| **막걸리** | 1병 (750 mL) | ≈ 300–400 |
| 와인 | 1잔 (150 mL) | ≈ 120–130 |
| 위스키 | 1잔 (38 mL) | ≈ 95 |

### B.3 음주량 분류 기준

#### WHO 2023 (Lancet Public Health)
> "건강에 영향을 주지 않는 안전한 음주량은 없다 (no safe amount)"

#### NIAAA 저위험
- 남성 ≤ 4잔/일 AND ≤ 14잔/주
- 여성 ≤ 3잔/일 AND ≤ 7잔/주

#### NIAAA 폭음 (Binge Drinking)
- 남 ≥ 5잔 / 여 ≥ 4잔 (2시간 내 BAC 0.08%)

#### 한국 KDCA — 표준잔 1잔 = 순알코올 ≈ 10g
- **고위험 음주**: 남 주 2회 이상 7잔/회, 여 주 2회 이상 5잔/회
- KDCA·국립암센터: 절주 아닌 **금주 권고** (소량도 암 위험 ↑)

#### AUDIT-KR (한국형, Kim et al. 2014)
- 위험 음주 cut-off: 남녀 ≥ **3점**
- 알코올 사용 장애 cut-off: 남 ≥ **10점** / 여 ≥ **8점**

### B.4 알코올 + DIT (식사 유발 열효과)

- 알코올 DIT 10–30% (단백 20–30%, 탄수화물 5–10%, 지방 0–3%)
- 그러나 식사와 함께 섭취 시 *전체 식사 DIT를 유의하게 끌어올리지 못함*
- 만성 음주자는 간 기능 저하·근감소로 장기 BMR 오히려 **감소**

### B.5 Lemon-Aid 반영 권고

1. **식단 입력 UI에 "주류" 카테고리 추가** — 소주/맥주/막걸리/와인/위스키/하이볼/칵테일 필수
2. **kcal 자동 변환**: `kcal = ml × ABV(%) × 0.789 × 7 / 100`
3. **일일 총 섭취 칼로리에 알코올 자동 합산** + `is_drinking_day=True` 플래그
4. **체중 예측 모델에 음주 보정 항** — 보수적 +30% kcal 가중 (Suter 지방 저장 효과 반영)
5. **AUDIT-KR 자가검진 모듈** — 회원가입 또는 월 1회
   - ≥ 위험: Vit B1, Mg 보강 안내
   - ≥ 의존: 1577-0199 (정신건강 상담), 중독관리통합지원센터 안내
6. **음주 다음날 운동 점수 보정 옵션**: 0.7–0.85배

---

## C. 흡연자의 영양 권장량 보정

### C.1 비타민 C — 흡연자 +35 mg/day (IOM 2000)

- **IOM 2000 DRI** — 흡연자 RDA +35 mg (남 125 mg, 여 110 mg)
- 흡연자 비타민 C 대사 회전 약 **2배** (70.0 vs 35.7 mg/day)
- **Lykkesfeldt J et al. AJCN 1997** — DHA/ascorbate 비율 ↑, *흡연 보상 위해 ~200 mg/day 필요* 추정 (보수적으로 +35 mg)

#### ⚠️ 한국 KDRIs 2020 (중요)
- 한국영양학회 2020 — *별도 흡연자 권장량을 설정하지 않음*
- 원문: *"흡연자나 만성 질환을 가진 사람들에서 비타민 C의 필요량 증가에 대한 별도의 기준을 정하는 것이 필요하다는 의견도 있지만, 과학적 근거가 부족하여 기준을 설정하지는 않았다."*
- → Lemon-Aid에서 흡연자 보정 도입 시 **"IOM/NIH ODS 기준에 따른 참고치"** 임을 라벨에 명시 필요

### C.2 ⚠️ 베타카로틴 — 흡연자에게 명확한 위험

- **ATBC Study 1994 NEJM** — 핀란드 남성 흡연자 29,133명, β-carotene 20 mg/day → **폐암 +18%, 총 사망률 +8%**
- **CARET Study 1996 NEJM (Omenn)** — 흡연자/석면 노출자 18,314명, β-carotene 30 mg + retinyl palmitate 25,000 IU → **폐암 +28%, 사망률 +17%** → 조기 중단
- **Goodman GE et al. JNCI 2004** — 중단 후에도 위해 효과 수년간 지속

→ **흡연자에게 β-carotene ≥ 6 mg 또는 Vit A ≥ 3,000 µg RAE 함유 제품 자동 경고 (강제)**

### C.3 산화 스트레스 보조 — 비타민 E, 셀레늄

- **SELECT trial (Klein EA et al. JAMA 2011)** — Vit E 400 IU/day 장기 → 전립선암 +17% → 메가도즈 비추
- **셀레늄 + SELECT** — 당뇨 위험 ↑
- → KDRIs 일반 권장량 충족이 우선 (Vit E 12 mg α-TE, Se 60 µg)

### C.4 호모시스테인 ↑ → B6/B9/B12

- **Vardavas CI et al. Matern Child Nutr 2019** — 흡연 노출 시 엽산·B12 ↓, 호모시스테인 ↑
- 그러나 B군 보충제로 심혈관 이벤트 감소는 일관되게 입증되지 않음 (VISP, HOPE-2, NORVIT)

### C.5 골다공증 위험 → Ca, Vit D

- **Ward KD & Klesges RC. Calcif Tissue Int 2001** — 흡연자 척추 골절 위험 여 +13%, 남 +32%; 고관절 골절 여 +31%, 남 +40%
- 흡연자 25(OH)D 농도 ↓, 금연 시 회복

### C.6 카드뮴 — Ca/Fe 결핍

- 담배연기는 카드뮴 주요 노출원, 폐 흡수율 10–50%
- Cd-Fe 경쟁: 철분 결핍자에서 Cd 흡수 ↑ → **철결핍성 빈혈 가속**
- 가임기 여성 흡연자 → **철분 모니터링 강화 + 식이 철분/Vit C 동반**

### C.7 Lemon-Aid 적용 (실행 체크리스트)

| 항목 | 처리 |
|---|---|
| `user.is_smoker == true` | Vit C 목표량 = KDRIs RDA + 35 mg (IOM 출처 라벨링) |
| β-carotene ≥ 6 mg 또는 Vit A ≥ 3,000 µg RAE | **흡연자에게 강한 경고**(ATBC/CARET NEJM 인용) |
| Vit E > UL(540 mg), Se > UL(400 µg) | **상한 초과 경고** |
| 우선순위 | Vit C > Vit E·Se(식이) > B6/B9/B12(식이) > Ca/Vit D |
| 50세+ 흡연자, 폐경 여성 흡연자 | Ca/Vit D 충족 점검 강화 + 골밀도 상담 권고 |
| 가임기 여성 흡연자 | 철분 모니터링 권고 |
| **금연 권고 메시지** | 영양 보정은 흡연 위해의 부분 완화에 불과함 명시 |
| KDRIs vs IOM 표기 | 흡연자 +35 mg는 IOM 기준이며 KDRIs는 미설정임을 라벨에 표시 |

---

## D. 음주자의 영양 권장량 보정

### D.1 만성 음주자 핵심 결핍 영양소

만성 알코올은 ① 식사 대체 1차 결핍 ② 위·소장 점막 손상 흡수 장애 ③ 간 저장능 저하 ④ 신장 배설 증가의 다중 기전.

- **티아민 (B1)** — 가장 중대. **베르니케 뇌병증 → 코르사코프 증후군** (Cochrane CD004033, 2013). 응급 시 포도당 투여 **전** 비경구 티아민
- **엽산 (B9)** — 만성 음주자 약 80%에서 혈청 엽산 저하
- **B12** — 위염·췌장 외분비 부전·회장 흡수 장애
- **마그네슘** — 신장 배설 ↑, 설사, 근경련·심부정맥·발작·알코올 금단 악화
- **아연** — 식이 부족 + 소변 배설 ↑ + 저알부민혈증
- **Vitamin A** — 간 저장 고갈되지만 *보충제 형태 다량 → 간 독성 ↑* (Leo MA & Lieber CS, AJCN 1999)
- **Vitamin D** — 간 25-수산화 효소 손상 → 골다공증·근감소증 위험 ↑

### D.2 ⚠️ 알코올 + 영양제·약물 위험 상호작용

| 조합 | 주요 위험 | 근거 |
|---|---|---|
| **알코올 + Vit A 다량** | CYP2E1 → 극성 레티놀 대사체 → 간세포 미토콘드리아 손상·apoptosis | Dan Z et al. FASEB J 2005; Leo & Lieber 1999 |
| **알코올 + β-carotene 고용량** | 에탄올이 레티놀 전환 방해 + 간 독성·발암성 증폭 | PMC3924697 |
| **알코올 + 아세트아미노펜** | CYP2E1 → NAPQI ↑, 글루타티온 고갈 → **치료 용량에서도 간 손상** | LiverTox NBK548162 |
| **알코올 + 항우울제/SSRI/TCA/MAOI** | CNS 억제 가중, MAOI는 티라민 위기 | NIAAA Core Resource |
| **알코올 + 벤조디아제핀/오피오이드** | 호흡억제·사망 | NIAAA |
| **알코올 + 밀크씨슬** | Cochrane: 사망률/합병증 감소 **유의한 근거 없음**, 안전성은 양호 | Rambaldi A et al. Cochrane CD003620 |
| **알코올 + NAC** | 아세트아미노펜 독성 예방은 명확, 만성 ALD 단독 치료는 근거 제한 | LiverTox NBK548401 |

### D.3 간 손상 음주자 영양 처방 (EASL CPG 2019)

- 에너지: 35 kcal/kg/day
- **단백질: 1.2–1.5 g/kg/day** (과거 단백 제한 권고 폐기, 간성뇌증에도 제한 금기)
- BCAA: 비대상성 간경변에 권고 (Grade B)
- LES (Late Evening Snack): 50 kcal CHO ± 단백질
- 미세영양소: 티아민·아연·Vit D 적극 보충, **Vit A는 결핍 확진 후 임상 감독 하에만**

### D.4 음주량 분류별 권고

| AUDIT 점수 (WHO) | 위험 수준 | 권고 |
|---|---|---|
| 0–7 | 저위험 | 일반 권장 + 절주 정보 |
| 8–15 | **위험 음주** | 간단 개입 + **B1, B9, Mg, Zn 보강** |
| 16–19 | **유해 음주** | 위 + 간 기능 검사 권고, BCAA/단백 1.2 g/kg, 간 영양제 자가복용 자제 |
| ≥20 | **알코올 의존 의심** | 즉시 전문 의료기관, **앱 내 영양제 자동 추천 중단** |

### D.5 Lemon-Aid 반영 권고

1. **사용자 프로필**: 음주 빈도(회/주), 1회 음주량, 폭음 빈도 + **AUDIT-KR 10문항** 옵션
2. **위험 음주(AUDIT-KR ≥ 위험) 자동 가산 권장**:
   - Thiamine 50–100 mg/day
   - Folate (B9) 0.4–1 mg/day
   - B12, B6 복합
   - Magnesium 200–400 mg/day
   - Zinc 15–30 mg/day
3. **자동 경고 트리거**:
   - Vit A **>3,000 µg RAE** 단일제 → 음주자에 "간 독성 위험" 경고
   - β-carotene 고용량(>20 mg) 동일
   - 아세트아미노펜 함유 종합감기약 입력 시 "음주 중 복용 금지" 강조
4. **간 건강 보조제 (밀크씨슬·NAC·UDCA)**: 자동 추천 금지, *"의사·약사 상담 후"* 안내
5. **AUDIT-KR ≥ 알코올 사용장애 cut-off**: 영양제 추천보다 **1577-0199** 안내 우선
6. **콘텐츠 톤**: "보조" / "건강기능식품" / "상담 권고" — 의학적 진단·치료 약속 금지

---

## E. 흡연이 운동·활동점수에 미치는 영향

### E.1 폐·심혈관 운동 능력 감소

#### FEV1
- **GOLD 2023** — 흡연자 *호흡 증상↑, FEV1 연간 감소율↑*
- **Fletcher & Peto 1977 BMJ** — 비흡연/금연자 ~30–37 mL/년 vs 흡연자(>15개비) ~64–80 mL/년 (**약 2배**)

#### VO2max
- 청년 여성 흡연자 vs 비흡연자: VO2max **26.5 vs 31.6 mL/min/kg (-16%)**
- **Conway & Cronan Prev Med 1992** — Navy 3,045명, 흡연이 *독립적*으로 지구력 저하와 연관

#### CO-Hb
- 흡연 3개비 후 COHb ≈ 4.5% 상승 → 즉시 VO2max ↓

#### HRmax / HR 회복
- 흡연 직후 안정 HR: 80 → 85 bpm
- 운동 중 HRmax: 흡연자 **173.2 vs 비흡연자 190.7 bpm** (-17 bpm)
- 흡연자 부교감 ↓, 교감 ↑ → HR 회복 지연

### E.2 같은 운동량에서 효과 ↓, 그러나 상대적 이득은 큼

- CO-Hb → 산소 운반 능력 ↓ → 동일 걸음수의 *생리적 부담* ↑
- **그러나** 흡연 유지하더라도 신체활동 ↑ → **전사망 -23%, 심질환 -49%, 뇌졸중 -25%**
- → "흡연자라서 운동이 의미 없다"는 *잘못된 결론*

### E.3 운동의 금연 보조 효과

- **Ussher MH et al. Cochrane 2019 (CD002295.pub6)** — 운동 *추가* 시 장기 금연율 *명확한 개선 입증 부족* (low certainty)
- 그러나 **니코틴 갈망·금단 증상·체중 증가 억제 단기 효과**는 인정

### E.4 금연자 운동 권고

- **HHS 2018 Physical Activity Guidelines** — 모든 성인 150-300분/주 중강도, 흡연자/금연자 차감 없음
- 금연자 FEV1 감소율은 비흡연자 수준으로 점진 회복

### E.5 흡연 + 부상 위험

- **골절 치유 지연**: 단순 골절 1.5배, 복합 골절 2.5배+
- 경골 골절 비유합 위험 ↑
- FRAX에 흡연 골절 위험인자로 공식 포함

### E.6 Lemon-Aid v1~v4 반영 권고

| 알고리즘 | 흡연자 분기 | 근거 |
|---|---|---|
| **v1 권장걸음수** | 동일 유지 (완화 X). 일반 8,000–10,000보. "체감 운동강도(Borg RPE) 모니터링" 안내 텍스트 추가 | GOLD, HHS |
| **v2 심박 가중** | HRmax 220-age 사용 시 흡연자 실측 약 10-17 bpm 낮을 수 있음 → THR 존 보정 옵션 검토. 점수 자체는 깎지 말 것 | Conway 1992 |
| **v3 백분위** | 흡연자 *별도 백분위 분리 X* (흡연자 평균 낮아 흡연자가 "쉽게 상위권" 역설) — 통합 백분위 유지 | 통계적 왜곡 회피 |
| **v4 가중치** | **+0.05 ~ +0.10 가중** 검토 가능 | CO-Hb 부담 ↑ + 금연 보조 (Cochrane low certainty) |

#### ⚠️ UX·윤리적 주의

1. "흡연을 보상한다"는 표현 금지 → **"흡연 중인 분께는 동일 활동이 더 큰 노력입니다. 점수를 보정해 드립니다"**
2. **금연 권고 메시지 노출 필수**
3. **만성질환 가중치와 중복 적용 금지**:
   - `weight = max(chronic_weight, smoking_weight)` 또는 `chronic_weight only`
4. **금연 후 1년 이내**: 흡연 가중치 절반 적용 + "금연 유지 보너스" 별도 메시지
5. **금연 후 1년 초과**: 흡연 가중치 제거

---

## F. 음주가 운동·체중·BMI에 미치는 영향

### F.1 음주 + 운동 회복

#### 근글리코겐 합성 (Burke et al. J Appl Physiol 2003)
- 직접 억제보다 *CHO 대체 간접 효과* 우세
- 회복기 0–4h: 1 g/kg BM CHO가 최적이나 알코올 섭취 시 CHO 섭취 감소

#### 근단백 합성 MPS (Parr EB et al. PLoS ONE 2014)
- 1.5 g/kg BM 알코올 (≈ 12 표준잔):
  - **ALC + PRO**: MPS **-24%**
  - **ALC + CHO**: MPS **-37%**
- mTOR 신호 억제 → 동화 반응 차단

#### 호르몬·수면
- 음주 후 코르티솔 ↑, 테스토스테론/코르티솔 ↓
- **Pabon et al. 2022** — 2 standard drinks부터 REM 수면 감소, 용량 의존적

### F.2 음주 + 체중·체지방

#### Suter PM NEJM 1992 / Crit Rev 2005
- 에탄올 → 24h 지질 산화 ↓ → **비산화 지질이 복부 영역에 우선 침착**
- "moderate alcohol consumption has to be regarded as a risk factor for obesity"

#### Bendsen NT et al. Nutr Rev 2013 (메타분석)
- 맥주 >500 mL/day → 허리둘레·WHR ↑
- <500 mL/day는 명확한 증거 부족

#### UK Biobank IJO 2026
- 고알코올 섭취 → **내장지방률 평균 10% 이상 ↑** (전체 체지방률과 무관하게 심대사 위험 ↑)

#### WHO Global Status Report 2024
- 연 **2.6백만 명 알코올 기인 사망** (전체 4.7%)
- 알코올 사용 장애 2.09억 명

### F.3 음주 + BMI 해석

#### 같은 BMI에서도 체지방률 ↑
- 음주자는 (a) 지방 산화 억제 → 체지방 ↑ (b) 근단백 합성 억제 → 근육량 ↓ 이중 영향

#### 사르코페니아 비만 (UK Biobank, Calcif Tissue Int 2023)
- 알코올 0→160 g/일 모델링 시 ALM/BMI 남 -3.6%, 여 -4.9%

#### WHtR 권고 (European Heart Journal, Gastro Hep Adv 2023)
- BMI <30이어도 WHtR >0.5면 관상동맥 석회화 위험 ↑
- WHR이 BMI보다 우수, **harmful alcohol use와 시너지**

### F.4 음주 + 심박·혈압

- **Cochrane (Tasnim S et al. 2020)** — 알코올 24h 이내 모든 시점 심박 ↑, 중등량 14-28g → 6h 이내 +4.6 bpm
- 혈압 biphasic: 12h ≤ ↓, 이후 ↑

### F.5 Lemon-Aid 알고리즘 반영 권고

| 알고리즘 | 음주자 분기 권고 |
|---|---|
| **BMI 분류** | 음주자(주 2회 이상 또는 회당 ≥60g)는 **WHtR/허리둘레 보조 입력 권장** |
| **체중 예측** | 일일 칼로리에 알코올 7 kcal/g 자동 산입 + 지방 산화 억제 메모. 단순 7 kcal/g는 *과소 추정* |
| **v1~v4 활동점수** | 음주 다음날 자동 보정 안 함 (UX 복잡 + 자기보고 신뢰도 ↓) — 대신 **주간 음주 패턴**으로 신뢰구간/회복 점수 별도 |
| **HRrest 입력** | 음주 다음날 outlier 처리, 7일 이동 중앙값 사용 |
| **영양 진단** | D 섹션 참조 |

#### 핵심 경고

> **음주는 ① 추가 칼로리 + ② 지방 산화 억제 + ③ 근단백 합성/글리코겐 합성 억제 + ④ 식욕·안주 유도 + ⑤ 수면·심박 교란 의 *5중 영향*. 단일 가중치로 단순화 불가** — 별도 risk modifier로 분리해 활동점수·체중 예측 *각각 독립 적용* 권장.

---

## ★ G. 통합 권고 — 12개 알고리즘 vs 흡연/음주 매트릭스

| Lemon-Aid 알고리즘 | 흡연자 분기 | 음주자 분기 |
|---|---|---|
| **3.1 BMI 분류** | (직접 영향 X) | + **WHtR/허리둘레 보조 입력** (사르코페니아 비만·복부 비만) |
| **3.2 v1 권장걸음수·기본점수** | 동일 (완화 X) + RPE 모니터링 안내 | 동일, 주간 음주 패턴은 보조 신뢰도 변수 |
| **3.3 v2 심박 가중** | HRmax 10–17 bpm 낮을 수 있음 → THR 존 보정 옵션 | 음주 다음날 HRrest +5–10 bpm → outlier 처리 |
| **3.4 v3 백분위** | 별도 분리 X (역설 회피) | 별도 분리 X |
| **3.5 v4 가중치** | **+0.05–0.10** (CO-Hb 부담 ↑ + 금연 동기). ⚠️ 만성질환과 중복 금지 (`max()` 적용) | 보정 X (자기보고 신뢰도 ↓, 5중 영향 단순화 불가) |
| **3.6 BMR (Mifflin)** | **보정 X** (Perkins 1992 — 만성 RMR 차이 미미) | 만성 음주자는 간기능 저하·근감소 가능 → 예측 신뢰도 ↓ 표시 |
| **3.7 TDEE (활동계수)** | 보정 X | 알코올 칼로리 자동 산입 |
| **3.8 7-step 체중 예측** | 금연 후 1년 이내 **+4.7 kg 평균 증가 안내** (Aubin 2012) | 알코올 kcal 자동 + 지방 저장 보정 +30% (Suter) |
| **ⓐ 영양제 OCR/LLM 파싱** | (직접 영향 X — 결과 활용 단계에서 분기) | (동일) |
| **ⓑ 식단 → 영양소 변환** | (직접 영향 X) | **주류 카테고리 추가 필수** (소주/맥주/막걸리/와인/위스키) |
| **ⓒ 부족 영양소 진단** | KDRIs + **Vit C +35 mg** (IOM 출처 라벨) | AUDIT-KR 위험 시 **B1·B9·Mg·Zn 자동 보강** |
| **ⓓ 목적별 매트릭스** | β-carotene·Vit A 다량 **경고 강화** (현재 부분 반영) | Vit A·아세트아미노펜 자동 경고, 밀크씨슬/NAC *상담 권고* |

---

## ★ H. 사용자 핵심 질문에 대한 답변

### "왜 흡연·음주를 만성질환과 별도로 가중치 적용해야 하는가"

#### 1. 흡연/음주는 *조절 가능한 행동 위험 요인*
- 만성질환은 *결과/상태*이고, 흡연·음주는 *행동·생활습관*
- 만성질환 가중치는 "현재 상태 보정"이라면, 흡연·음주는 "*변화 가능한 위험* + *동기부여*"

#### 2. 영양·약물 상호작용 분기가 *완전히 다름*
- 흡연자: **Vit C +35 mg / β-carotene·Vit A 다량 금지**
- 음주자: **B1·B9·Mg·Zn 보강 / Vit A 단일제 금지 / 간 영양제 자가복용 자제**
- 만성질환자: 질환별 (DASH / ADA / KDOQI / EASL) 가이드 라우팅
- → **세 가지가 독립 분기되어야 안전**

#### 3. 운동 점수에 미치는 영향이 정반대
- **흡연자**: 동일 활동이 *생리적으로 더 큰 부담* → 가중치 +0.05~0.10 (활동 동기 ↑)
- **음주자**: 다음날 운동 효과 자체가 ↓ — 가중치 적용 시 *과대평가 위험*
- → 흡연은 가중, 음주는 *신뢰도 보정*

#### 4. 만성질환과의 중복 적용 함정
- 흡연 + COPD/심혈관 → 만성질환 가중치 *우선*, 흡연 가중치 중복 금지 (`max()` 적용)
- 만성 음주 + 간경변 → 만성질환 가중치 *우선*, 음주 추가 가중 없음
- → **부풀려진 점수가 잘못된 안전감을 줄 위험**

#### 5. UX/메시지 톤 차이
- 만성질환: "활동 동기 점수" 보정 + 의학적 자문 안내
- 흡연: 점수 보정 + **금연 권고 메시지 필수 병기**
- 음주: 가중 없음 + **AUDIT-KR + 절주/금주 안내**

→ **세 카테고리는 알고리즘 측면뿐 아니라 *교육·동기 측면에서도 분리* 필요.**

---

## I. 데이터 모델 권장

```python
class SmokingStatus(str, Enum):
    NEVER = "never"
    FORMER_LT_1Y = "former_<1y"
    FORMER_GE_1Y = "former_≥1y"
    CURRENT_LIGHT = "current_<10/d"       # <10개비/일
    CURRENT_HEAVY = "current_≥10/d"        # ≥10개비/일

class DrinkingProfile(BaseModel):
    frequency_per_week: int                # 회/주
    soju_glasses_per_session: float        # 1회 소주잔 (10g 순알코올/잔)
    binge_frequency_per_month: int = 0
    audit_kr_score: int | None = None       # 0~40

    @property
    def is_risk_drinker(self) -> bool:
        """AUDIT-KR 위험 음주 cut-off (남녀 ≥ 3)"""
        return self.audit_kr_score is not None and self.audit_kr_score >= 3

    @property
    def is_aud_suspected(self, sex: str) -> bool:
        """알코올 사용 장애 의심 (남 ≥ 10, 여 ≥ 8)"""
        if self.audit_kr_score is None:
            return False
        threshold = 10 if sex == "male" else 8
        return self.audit_kr_score >= threshold

class HealthRiskFlags(BaseModel):
    smoking: SmokingStatus = SmokingStatus.NEVER
    drinking: DrinkingProfile | None = None
    chronic_diseases: list[ChronicDisease] = []
```

## J. Phase별 적용 로드맵

### Phase 1 (P0 — 즉시 안전 직결)
- [ ] 영양제 + 흡연자 베타카로틴/Vit A 자동 경고 (이미 부분 구현 — 강화)
- [ ] 영양제 + 음주자 Vit A·아세트아미노펜 자동 경고
- [ ] 식단 입력 UI에 **주류 카테고리 추가** + 자동 kcal 산입
- [ ] AUDIT-KR 자가검진 모듈
- [ ] AUDIT-KR ≥ 의존 cut-off → 1577-0199 / 중독관리통합지원센터 안내 + 영양제 추천 중단

### Phase 2 (P1 — 정확도 ↑)
- [ ] 흡연자 KDRIs 자동 보정 (Vit C +35 mg, IOM 출처 라벨)
- [ ] AUDIT-KR 위험군 B1·B9·Mg·Zn 자동 권장
- [ ] BMI 음주자 WHtR 보조 입력
- [ ] 체중 예측에 알코올 7 kcal/g + 지방 저장 보정 +30% (Suter)
- [ ] v4 흡연 가중치 +0.05~0.10 (만성질환 중복 회피 `max()`)

### Phase 3 (P2 — 고도화)
- [ ] HRrest 음주 다음날 outlier 처리
- [ ] 금연 후 체중 증가 (Aubin 메타분석) 안내 + 활동 동기 부여
- [ ] 자체 데이터 수집 후 가중치 보정
- [ ] 의료자문위 검수

---

## K. 참고 문헌 종합 (필수 인용)

### 흡연 + BMR/체중
- Hofstetter A et al. NEJM 1986. DOI: 10.1056/NEJM198601093140204
- Perkins KA. J Appl Physiol 1992. PMID: 1559911
- Marks BL, Perkins KA. Sports Med 1990. DOI: 10.2165/00007256-199010050-00001
- Aubin HJ et al. BMJ 2012. DOI: 10.1136/bmj.e4439
- Filozof C et al. Obes Rev 2004. DOI: 10.1111/j.1467-789X.2004.00131.x
- Mineur YS et al. Science 2011. DOI: 10.1126/science.1201889
- CDC Surgeon General. The Health Benefits of Smoking Cessation.

### 흡연 + 운동
- GOLD 2023. PMC10111975
- Fletcher C, Peto R. BMJ 1977. PMC3282601
- Conway TL, Cronan TA. Prev Med 1992. PMID: 1438118
- Su FY et al. Can Respir J 2020. DOI: 10.1155/2020/5968189
- Ussher MH et al. Cochrane CD002295.pub6 (2019)
- Vestergaard P et al. FRAX & smoking meta-analysis
- HHS 2018 Physical Activity Guidelines for Americans

### 흡연 + 영양
- IOM. *Dietary Reference Intakes for Vitamin C, Vitamin E, Selenium, and Carotenoids* (2000). NBK225480
- NIH ODS Vitamin C – Health Professional Fact Sheet
- 한국영양학회. *2020 한국인 영양소 섭취기준: 비타민 C*. J Nutr Health 2022;55(5):523
- Lykkesfeldt J et al. AJCN 1997;65:959 / AJCN 2000;71:530
- Heinonen OP, Albanes D et al. (ATBC). NEJM 1994;330:1029. PMID: 8127329
- Omenn GS et al. (CARET). NEJM 1996;334:1150. PMID: 8602180
- Goodman GE et al. JNCI 2004. PMID: 15572756
- Klein EA et al. SELECT. JAMA 2011;306:1549
- Ward KD, Klesges RC. Calcif Tissue Int 2001. PMID: 11683532
- ATSDR. Toxicological Profile for Cadmium

### 음주 + BMR/체중
- Suter PM, Schutz Y, Jéquier E. NEJM 1992;326:983-987
- Suter PM. Crit Rev Clin Lab Sci 2005;42:197-227
- Yeomans MR. Physiol Behav 2010 / Br J Nutr 2004
- Westerterp KR. PMC524030 (DIT)
- Traversy G, Chaput JP. Curr Obes Rep 2015. PMID: 25741455
- WHO. Global Status Report on Alcohol and Health and Treatment of Substance Use Disorders 2024
- NIAAA — Defining How Much Alcohol Is Too Much
- 질병관리청 국가건강정보포털 — 위험음주
- 국립암센터 — 암예방과 검진: 음주

### 음주 + 운동
- Burke LM et al. J Appl Physiol 2003;95:983
- Parr EB et al. PLoS ONE 2014;9:e88384
- Barnes MJ. Nutrients 2010. PMC3257708
- Shirreffs SM, Maughan RJ. J Appl Physiol 1997;83:1152
- Pabon E et al. Alcohol Clin Exp Res 2022;46:1875
- Tasnim S et al. Cochrane CD012787 (2020)
- Bendsen NT et al. Nutr Rev 2013;71:67
- Skinner J et al. Calcif Tissue Int 2023;113:143
- Åberg F et al. Gastro Hep Adv 2023. PMC10482890

### 음주 + 영양
- Cochrane CD004033 (2013) — Thiamine for Wernicke-Korsakoff
- EASL Clinical Practice Guidelines on nutrition in chronic liver disease. J Hepatol 2019;70:172
- Leo MA, Lieber CS. AJCN 1999;69:1071
- Dan Z et al. FASEB J 2005
- Clugston RD, Blaner WS. Nutrients 2012;4:356. PMC3367262
- Rambaldi A et al. Cochrane CD003620
- NIH LiverTox — Acetaminophen (NBK548162), Acetylcysteine (NBK548401)
- NIAAA — Alcohol-Medication Interactions
- AUDIT WHO Manual (Babor et al. 2001)
- Kim JS et al. AUDIT-K. Arch Psychiatr Nurs 2009
- Lee BO et al. AUDIT-KR. Korean J Fam Med 2014. PMC3912263

---

## 📝 변경 이력

| 버전 | 날짜 | 변경 사항 | 작성자 |
|---|---|---|---|
| v1.0 | 2026-05-26 | 6개 영역 통합 (BMR·체중/BMR·체중/영양 흡/영양 음/운동 흡/운동 음) + 12개 알고리즘 매트릭스 + Phase 로드맵 | Claude (6 agent 병렬 조사 통합) |
