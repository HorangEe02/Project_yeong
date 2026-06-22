# 06. 목적별 분석 매트릭스 평가 및 수정안

> **문서 목적**: Lemon-Aid의 "목적별 영양제 추천 매트릭스"(눈건강·간기능·피로회복 등)를 AREDS2, Cochrane, EFSA, 식약처 건강기능식품 공전 등 공식 자료에 기반하여 평가하고, **약물 상호작용·만성질환 분기**를 포함한 수정안을 제시한다.
>
> **법적 고지**: 본 문서는 건강기능식품 영역의 *기능성* 평가이며 의약품의 *치료 효능*과 구분된다. "도움이 될 수 있다"는 식약처 인정 문구 외 의학적 단정을 회피한다.
>
> **작성일**: 2026-05-26
> **버전**: v1.0 (Phase 1 평가)

---

## 1. 현재 구현 요약 (3 목적)

`07-core-algorithm.md`의 목적별 추천 로직:

| 목적 | 핵심 성분 | 현재 권장량 |
|------|----------|------------|
| **눈건강** | 루테인+지아잔틴, 오메가-3 DHA, Vit A | 루테인 10–20mg+지아잔틴 2mg, DHA 1–2g, Vit A KDRIs RDA |
| **간기능** | 밀크씨슬(실리마린), NAC | 실리마린 ≥130 mg, NAC 600–1,800 mg |
| **피로회복** | 비타민 B군(B1/B2/B12), CoQ10, Mg | B군 KDRIs RDA, CoQ10 90–100 mg, Mg KDRIs RDA |

**현재 구현의 가정**:
- 사용자가 목적을 선택 → 매트릭스에서 성분·용량 조회 → 일괄 출력
- 흡연/임신/약물 복용 등 위험 인자 분기 없음
- 식약처 인정 문구 vs 임상 효과 구분 모호

---

## 2. 논문·공식 자료 근거

### 2.1 눈건강

#### (1) AREDS2 (Age-Related Eye Disease Study 2)

- **출처**: AREDS2 Research Group. "Lutein + zeaxanthin and omega-3 fatty acids for age-related macular degeneration: the AREDS2 randomized clinical trial". **JAMA. 2013;309(19):2005–2015**. DOI:10.1001/jama.2013.4997
- **대상**: 진행성 AMD(나이관련 황반변성) 위험이 높은 50–85세 4,203명
- **개입**:
  - 루테인 10 mg + 지아잔틴 2 mg (vs 위약)
  - DHA 350 mg + EPA 650 mg (vs 위약)
  - 베타카로틴 제거 — 흡연자 안전성 고려
- **결과**:
  - **루테인+지아잔틴**: 진행성 AMD 진행 12% 감소 (HR 0.90, P=0.04) — *베타카로틴 제거 부문에서*
  - **오메가-3**: AMD 진행 감소 효과 *없음* (HR 0.97, P=0.70)
- **임상 적용 한계**: AREDS2는 **AMD 중등도 이상 위험군 대상**. 일반 건강 인구에서 동일 효과를 단정할 근거가 없다.

#### (2) 식약처 건강기능식품 기능성 인정

- **루테인 (마리골드꽃추출물)**: "노화로 인해 감소될 수 있는 황반색소밀도를 유지하는 데 도움을 줄 수 있음" — 1일 섭취량 10–20 mg
- **헤마토코쿠스 추출물(아스타잔틴)**: "눈의 피로도 개선에 도움을 줄 수 있음"
- **빌베리 추출물**: "눈의 피로도 개선" (개별인정형)
- **루테인지아잔틴복합추출물**: 동일 문구

> 출처: 식품의약품안전처 「건강기능식품 공전」 및 「건강기능식품 기능성 원료 인정 현황」. https://www.foodsafetykorea.go.kr/portal/board/board.do?menu_grp=MENU_NEW01&menu_no=2660

#### (3) 오메가-3 DHA/EPA 권장량 (눈건강·일반 건강)

- **일반 건강**: EPA+DHA 합 250–500 mg/d (NIH ODS)
- **AMD/Dry eye**: 일부 연구에서 1,000–2,000 mg/d 사용. **단, AREDS2에서 AMD 진행 억제 효과 미입증**
- **상한**: EPA+DHA 3 g/d 미만 (FDA GRAS 권고)

> 출처: NIH Office of Dietary Supplements, "Omega-3 Fatty Acids — Health Professional Fact Sheet". https://ods.od.nih.gov/factsheets/Omega3FattyAcids-HealthProfessional/

#### (4) ⚠️ 흡연자 + 베타카로틴 → 폐암 위험

- **ATBC Study** (Finland, 1985–1993, n=29,133 남성 흡연자): β-카로틴 20 mg/d → **폐암 발생률 18% 증가**, 전체 사망률 증가
  - 출처: Heinonen OP, et al. NEJM. 1994;330:1029. PMC:PMC3991754. https://pmc.ncbi.nlm.nih.gov/articles/PMC3991754/
- **CARET Study** (US, β-카로틴 30 mg + 레티닐 팔미테이트): 흡연자/석면 노출자에서 **폐암 발생률 28% 증가**로 조기 종료
  - 출처: Omenn GS, et al. NEJM. 1996;334:1150.
- **메타분석**: 흡연자에서 β-카로틴 보충 시 **폐암 위험 24% 증가** (109,394명)
- **AREDS2의 베타카로틴 제거 결정의 근거**가 바로 이 데이터.

### 2.2 간기능

#### (1) 밀크씨슬 (실리마린)

- **식약처 인정**: "간 건강에 도움을 줄 수 있음" — 1일 실리마린 130 mg 기준
- **Cochrane Review (Rambaldi A, 2007)**:
  > "Milk thistle for alcoholic and/or hepatitis B or C virus liver diseases" Cochrane Database Syst Rev. 2007;(4):CD003620.
  - 결론: 전체 분석에서 사망·합병증 유의 감소 *없음*. **고품질 RCT 부족** — "evidence to support or refute"가 *불가*.
  - 출처: https://www.cochrane.org/evidence/CD003620_no-evidence-supporting-or-refuting-milk-thistle-alcoholic-andor-hepatitis-b-or-c-virus-liver
- **JAMA 2012 RCT (Fried MW, et al.)**: 만성 C형 간염 인터페론 무반응자 154명에서 실리마린 420 mg/700 mg 28주간 사용 → **ALT 정상화 무효** (위약과 차이 없음).
  - DOI:10.1001/jama.2012.8265. https://jamanetwork.com/journals/jama/fullarticle/1217238
- **요약**: 식약처 *기능성 인정*은 보유하나, **임상적 치료 효과는 근거 약함**. "도움을 줄 수 있다" 수준의 표현만 허용.

#### (2) NAC (N-Acetylcysteine)

- **FDA 승인 적응증**: 아세트아미노펜(타이레놀) 과다복용 시 간독성 해독제. *건강기능식품 적응증 아님*.
  - 출처: FDA Acetadote (NAC IV) prescribing information.
- **비-아세트아미노펜 급성 간부전**: AASLD는 NAC 사용 *고려 가능*하다는 입장. 메타분석에서 *생존율 개선* 일부 보고.
  - 출처: Hu J, et al. "Role of NAC in non-acetaminophen ALF". PMC:PMC7903568. https://pmc.ncbi.nlm.nih.gov/articles/PMC7903568/
- **만성 간질환 일반에 대한 OTC NAC 보충**: 근거 *부족*. 한국에서 NAC는 **일반의약품**(거담제)으로 분류, 건강기능식품 아님.
- **권고**: 현재 알고리즘의 "NAC 600–1,800 mg" 추천은 **국내 규제상 일반인 대상 영양제 추천으로 부적절**. → 제거 또는 "처방 영역" 명시.

### 2.3 피로회복

#### (1) 비타민 B군

- **에너지 대사 보조 인자**: B1(TPP, 피루브산 탈카복실화), B2(FAD/FMN), B3(NAD+), B5(CoA), B6(아미노산 대사), B12(엽산 대사·신경)
- **결핍 시 피로감**: 학술적으로 인정 (특히 B12 결핍성 빈혈).
- **임상 효과**: 결핍 환자에서 보충 시 효과 명확. **결핍 없는 일반인에서 추가 보충의 피로 개선 효과는 RCT에서 일관되지 않음**.
- 출처: Tardy AL, et al. "Vitamins and Minerals for Energy, Fatigue and Cognition". Nutrients. 2020;12(1):228. https://pmc.ncbi.nlm.nih.gov/articles/PMC7019700/
- **식약처 인정**: B군 비타민 — "체내 에너지 생성에 필요" 영양소 기능 표시

#### (2) CoQ10 (코엔자임 Q10)

- **식약처 인정**: "항산화에 도움을 줄 수 있음", "높은 혈압 감소에 도움을 줄 수 있음" — **1일 최대 100 mg**
- **만성피로증후군(CFS)**: 일부 소규모 연구에서 효과 보고. 대규모 RCT/Cochrane 메타분석 *결정적 근거 부족*.
- **심부전**: Q-SYMBIO RCT(2014, n=420) — CoQ10 300 mg/d 2년간 → 심혈관 사망 43% 감소. *결핍 환자 한정* 가능성.
  - 출처: Mortensen SA, et al. JACC Heart Fail. 2014;2:641.
- **요약**: 식약처 인정 문구 범위 내 사용 가능. **만성피로 치료 효과 단정 불가**.

#### (3) 마그네슘

- ATP 생성·신경근 기능에 필수 (300+ 효소 보조인자)
- 결핍 시 피로감·근경련 — 명확
- KDRIs 2020 RDA: 성인 남 370 mg, 여 280 mg; UL 350 mg(보충제 형태만, 식이는 미포함)
- 한국인 평균 섭취량은 권장량 미만 (KNHANES)

### 2.4 추가 목적 권장 (Phase 2+)

| 목적 | 핵심 성분 | 근거 강도 | 식약처 인정 문구 |
|------|----------|----------|----------------|
| **면역** | Vit C, Vit D, Zn | 약~중 | Vit C "항산화·결합조직 형성"; Vit D "면역기능 유지"; Zn "면역기능에 필요" |
| **수면** | Mg, L-테아닌, GABA | 약 | L-테아닌 "스트레스·긴장 완화" |
| **장 건강** | 프로바이오틱스, 식이섬유 | 균주별 상이 | "유익균 증식·유해균 억제" |
| **관절** | 글루코사민, MSM | 약 | "관절·연골 건강" |
| **인지** | DHA, 포스파티딜세린 | 약 | "어린이/노인 인지력 유지" |

**참고**: EFSA는 프로바이오틱스 건강 표시(health claim)를 *현재까지 0건* 승인 — 유럽은 EU 규정상 "probiotic" 단어 사용 금지. 한국 식약처는 별도 기능성 원료로 인정.
> 출처: Hill C, et al. "Probiotic health claims". Brit J Nutr. 2014. https://www.cambridge.org/core/journals/british-journal-of-nutrition/article/health-benefits-and-health-claims-of-probiotics-bridging-science-and-marketing/3C143B002B0289188B006FACA906E3BE

**비타민 C/아연 감기 예방**: Cochrane Review (Hemilä 2013, Nault 2024) — 일반 인구 *예방 효과 없음*. 치료 시 감기 기간 약 *8–14% 단축*.
> 출처: Hemilä H, Chalker E. Cochrane DSR 2013;1:CD000980; Nault D, et al. Cochrane DSR 2024:CD014914.

---

## 3. 평가

### 3.1 강점

- **식약처 인정 원료 우선 사용** — 한국 건강기능식품 법령 준수 (법적 안전).
- **AREDS2 등 SOTA RCT 인용** — 근거 수준 표시 가능.
- 다중 성분 조합(루테인+오메가-3) — 시너지 가능성.

### 3.2 약점

| # | 약점 | 영향 |
|---|------|-----|
| 1 | **임상 효과 단정 위험** (특히 밀크씨슬/NAC) | 의료법·표시광고법 위반 소지 |
| 2 | **일반 인구 vs 위험군 구분 부재** | AREDS2 결과를 건강인에 일반화 |
| 3 | **흡연자 베타카로틴 경고 없음** | 폐암 위험 24% 증가 (메타분석) — 안전 결함 |
| 4 | **임신부 Vit A 분기 없음** | 기형 위험 (>10,000 IU retinol/d) |
| 5 | **약물 상호작용 체크 부재** | 와파린·갑상선약·항암제 등 |
| 6 | **NAC의 비-건강기능식품 성격** 미인지 | 국내 규제 부정합 |
| 7 | **목적 3개로 협소** | 면역·수면·장건강 등 수요 미충족 |

---

## 4. 수정 권고

### 4.1 식약처 인정 문구 우선 적용 (표시 가이드)

- 모든 성분 추천 카드에 **식약처 인정 문구를 1차 표시**, 그 외 임상 효과는 *"연구 일부에서 보고됨"* 단서와 함께 2차 표시.
- 예: 루테인 → "노화로 인해 감소될 수 있는 황반색소밀도 유지에 도움" + (참고: AREDS2에서 AMD 진행 위험군의 진행 12% 감소 보고)
- "치료·예방" 어휘 *전면 금지* — 표시광고법 §13(허위·과장 광고) 회피.

### 4.2 목적별 위험 분기

#### 4.2.1 눈건강

```python
def recommend_eye_health(user):
    items = ['루테인+지아잔틴(마리골드꽃추출물)', 'DHA·EPA(어유)']

    # 흡연자: 베타카로틴 함유 제품 *경고*
    if user.is_smoker or user.recent_smoker_within_years < 10:
        warnings.append(
            "흡연자는 베타카로틴 보충제 섭취 시 폐암 위험이 증가할 수 있습니다 "
            "(ATBC/CARET 연구). 베타카로틴 함유 제품을 피하고, "
            "AREDS2 처방(루테인+지아잔틴) 형태를 선택하세요."
        )

    # 임산부: Vit A retinol 형태 *제한*
    if user.is_pregnant:
        warnings.append(
            "임신 중 retinol 형태 비타민 A의 1일 3,000 µg RAE(10,000 IU) "
            "초과는 태아 기형 위험과 연관됩니다(NEJM 1995). β-카로틴 형태는 "
            "안전하나, retinol 함유 종합비타민 라벨을 확인하세요."
        )

    # 황반변성 가족력/진단: 안과 상담 권유
    if user.has_amd_diagnosis or user.family_amd:
        warnings.append("안과 전문의와 상담 후 AREDS2 처방 적용을 권합니다.")

    return {"items": items, "warnings": warnings}
```

#### 4.2.2 간기능

```python
def recommend_liver(user):
    if user.has_severe_liver_disease or user.is_post_transplant:
        return {
            "status": "REFERRAL_ONLY",
            "message": (
                "간이식·중증 간질환 환자의 보충제 자가 선택은 위험합니다. "
                "주치의·간장전문의 상담을 권합니다."
            )
        }

    items = ['밀크씨슬(실리마린, 식약처 인정 1일 130mg)']

    warnings.append(
        "밀크씨슬의 임상적 간질환 치료 효과는 Cochrane Review(2007)와 "
        "JAMA 2012 RCT에서 근거가 약함으로 보고되었습니다. "
        "식약처 인정 문구는 '간 건강에 도움을 줄 수 있음' 수준입니다."
    )

    # NAC는 의약품(거담제)/응급치료제 — 일반 추천에서 제외
    if user.requests_nac:
        warnings.append(
            "NAC는 국내에서 의약품으로 분류되며 건강기능식품이 아닙니다. "
            "약사·의사 상담 없이 임의 복용을 권하지 않습니다."
        )

    return {"items": items, "warnings": warnings}
```

#### 4.2.3 피로회복

```python
def recommend_fatigue(user):
    # 원인 질환 우선 확인
    referral_conditions = ['THYROID', 'CHF', 'ANEMIA', 'DEPRESSION', 'CANCER']
    if any(c in user.chronic_conditions for c in referral_conditions):
        return {
            "status": "INVESTIGATE_CAUSE",
            "message": (
                "피로의 원인이 갑상선·심부전·빈혈·우울증·암 등 기저질환일 수 "
                "있습니다. 영양제 전에 원인 진단이 우선입니다."
            )
        }

    items = ['비타민 B 복합', 'CoQ10(식약처 인정 1일 100mg)', '마그네슘']
    return {"items": items, "warnings": []}
```

### 4.3 만성질환자 / 약물 분기 — **사용자 핵심 질문**

**왜 만성질환자와 일반 사용자를 목적별 추천에서 분리해야 하는가**:

#### (1) 약물–영양소 상호작용은 약효를 변동시킨다

| 약물 | 상호작용 영양소/보충제 | 메커니즘·결과 | 출처 |
|------|----------------------|---------------|------|
| **와파린**(쿠마딘) | Vit K (녹황색채소·종합비타민) | INR 저하 → 혈전 위험; 급격한 K 감소 시 INR 상승 → 출혈. *섭취 일관성*이 핵심 | Drugs.com Pro; Blood 2007;109:2419. https://ashpublications.org/blood/article/109/6/2419 |
| 와파린 | 비타민 E 고용량, 은행잎, 마늘, 오메가-3 고용량 | 출혈 위험 ↑ | 약물 첨부문서 |
| **레보티록신**(갑상선약) | Ca, Fe, Mg, 알루미늄 | 흡수 20–50% ↓ → 갑상선 기능 저하 악화. **4시간 간격 필수** | Skelin M, et al. PMC8002057. https://pmc.ncbi.nlm.nih.gov/articles/PMC8002057/ |
| 비스포스포네이트(골다공증) | Ca, Fe, Mg | 흡수 ↓ — 30분 간격 | FDA labeling |
| **메트포르민** | Vit B12 | 장기 복용 시 B12 흡수 저하 → 보충 필요 | ADA Standards 2024 |
| MAOI/SSRI | 세인트존스워트(서양고추나물) | 세로토닌 증후군 | 약전 |
| **항암제** (5-FU 등) | 고용량 항산화제 (Vit C/E) | 항암 효과 *감소* 가능성 — 항암 중 보충 피함 | NCCN |
| 스타틴 | 자몽주스, 적색효모쌀 | 횡문근융해 위험 | FDA |

#### (2) 만성질환은 보충제 *축적·금기*를 만든다

| 질환 | 보충제 주의 | 이유 |
|------|------------|-----|
| **CKD 3–5단계** | Vit D 활성형, 고용량 Vit A, K, Mg, P 함유 종합 | 축적·고K/고P 위험. KDOQI 2020은 *의료진 조절* 권고 |
| **간경변** | NAC, 밀크씨슬, 고용량 철 | 자가 진단 금지. 의사 상담 |
| **임신** | Vit A retinol >3,000 µg RAE | 기형 위험 (NEJM 1995) |
| **임신** | β-카로틴 고용량 | 후성유전적 영향 보고 — 의학적 자문 권장 |
| **갑상선 항진/저하** | 요오드 고용량, 갈조류 추출물 | 갑상선 기능 악화 |
| **흡연자** | β-카로틴 ≥20 mg/d | 폐암 위험 ↑ (ATBC/CARET) |
| **G6PD 결핍** | 고용량 Vit C IV, 잠두 | 용혈 |

#### (3) 결론

> **약물 정보 입력 → 상호작용 경고 시스템은 Phase 1 최우선 기능이어야 한다.**
>
> 만성질환·약물 복용자에게 일반 인구 목적별 추천을 그대로 적용하는 것은 *임상적으로 위험*하며, 표시광고법·의료법 측면에서도 *법적 책임*을 유발할 수 있다. 사용자 안전과 법적 안전은 동일 방향으로 작동한다 — *분리 라우팅이 양쪽을 동시에 충족*시킨다.

### 4.4 수정된 의사 코드

```python
HIGH_RISK_DRUGS = {'WARFARIN', 'LEVOTHYROXINE', 'METHOTREXATE', 'CHEMO',
                   'BISPHOSPHONATE', 'MAOI', 'SSRI', 'STATIN', 'METFORMIN'}

def recommend_by_goal(user, goal):
    # === 가드레일 1: 약물 복용자 ===
    if user.medications & HIGH_RISK_DRUGS:
        interactions = check_drug_supplement_interactions(
            user.medications, goal_to_supplements[goal])
        if interactions:
            return {
                "status": "DRUG_INTERACTION_REVIEW",
                "interactions": interactions,
                "message": "약물–보충제 상호작용 가능성이 확인되었습니다. "
                           "약사·의사 상담 후 진행하세요.",
            }

    # === 가드레일 2: 임신·수유 ===
    if user.is_pregnant or user.is_lactating:
        return pregnancy_safe_recommend(user, goal)

    # === 가드레일 3: 만성질환자 ===
    if user.chronic_conditions:
        return chronic_disease_route(user, goal)
        # 내부에서 CKD/간/갑상선/심부전 등 분기 처리

    # === 가드레일 4: 흡연자 + 눈건강 → 베타카로틴 회피 ===
    if goal == 'EYE' and user.is_smoker:
        return eye_health_smoker_safe(user)

    # === 일반 경로 ===
    return STANDARD_GOAL_MATRIX[goal](user)
```

### 4.5 분류 표 — 목적 × 위험군

| 목적 \ 위험군 | 일반 성인 | 흡연자 | 임신·수유 | 만성질환자 | 약물 복용 |
|--------------|----------|--------|-----------|-----------|-----------|
| 눈건강 | 매트릭스 | β-카로틴 회피 | retinol UL | 안과상담 | 와파린 시 비타민 K 주의 |
| 간기능 | 밀크씨슬 (기능성 표시) | 일반 | 의사 상담 | **REFERRAL** | NAC 의약품 |
| 피로 | B군·Mg·CoQ10 | 일반 | 의사 상담 | **원인 질환 우선** | 갑상선약 흡수 간격 |
| 면역(P2) | C·D·Zn | 일반 | 일반 | CKD: D 활성형 주의 | 면역억제제 주의 |
| 수면(P2) | Mg·테아닌 | 일반 | **멜라토닌 의약품** | — | 항우울제 |
| 장건강(P2) | 프로바이오틱스 | 일반 | 균주별 상이 | 면역억제자: 신중 | 항생제와 간격 |

---

## 5. 추가 권장 목적 (Phase 2)

### 5.1 면역
- **Vit C** (KDRIs RDA 100 mg, UL 2,000 mg) — 항산화 기능 표시
- **Vit D** (AI 10 µg, UL 100 µg) — 면역기능 유지 기능 표시
- **Zn** (RDA 10 mg 남, 8 mg 여, UL 35 mg) — 면역기능에 필요
- 근거: 일반 인구 *예방 효과 근거 약함*, 결핍 시 보충 유익.

### 5.2 수면
- **Mg** (RDA 370/280 mg)
- **L-테아닌** (식약처: "스트레스로 인한 긴장 완화") — 1일 200–400 mg
- ⚠️ **멜라토닌은 한국에서 전문의약품**. 건강기능식품 추천 불가.

### 5.3 장 건강
- **프로바이오틱스**: 식약처 19개 균종 인정 — 1억–100억 CFU/d
- **식이섬유**: KDRIs AI 25 g (남) / 20 g (여)
- ⚠️ EFSA는 probiotic health claim 미승인 (한국과 차이) — 글로벌 확장 시 표현 차별화.

### 5.4 관절·인지 등은 Phase 3로 보류 (근거 정합 후)

---

## 6. 참고 문헌

1. **AREDS2 Research Group**. "Lutein + Zeaxanthin and Omega-3 Fatty Acids for Age-Related Macular Degeneration: The AREDS2 Randomized Clinical Trial". **JAMA. 2013;309(19):2005–2015**. DOI:10.1001/jama.2013.4997
2. **Heinonen OP, et al.** (ATBC Cancer Prevention Study Group). "The Effect of Vitamin E and Beta Carotene on the Incidence of Lung Cancer and Other Cancers in Male Smokers". NEJM. 1994;330:1029. https://pmc.ncbi.nlm.nih.gov/articles/PMC3991754/
3. **Omenn GS, et al.** (CARET). "Effects of a Combination of Beta Carotene and Vitamin A on Lung Cancer and Cardiovascular Disease". NEJM. 1996;334:1150–1155.
4. **Rambaldi A, et al.** "Milk thistle for alcoholic and/or hepatitis B or C virus liver diseases". Cochrane Database Syst Rev. 2007;(4):CD003620. https://www.cochrane.org/evidence/CD003620_no-evidence-supporting-or-refuting-milk-thistle-alcoholic-andor-hepatitis-b-or-c-virus-liver
5. **Fried MW, et al.** "Effect of Silymarin (Milk Thistle) on Liver Disease in Patients with Chronic Hepatitis C Unsuccessfully Treated With Interferon Therapy: A Randomized Controlled Trial". JAMA. 2012;308(3):274–282. DOI:10.1001/jama.2012.8265. https://jamanetwork.com/journals/jama/fullarticle/1217238
6. **Mortensen SA, et al.** (Q-SYMBIO). "The Effect of Coenzyme Q10 on Morbidity and Mortality in Chronic Heart Failure". JACC Heart Fail. 2014;2(6):641–649.
7. **Tardy AL, et al.** "Vitamins and Minerals for Energy, Fatigue and Cognition: A Narrative Review". Nutrients. 2020;12(1):228. https://pmc.ncbi.nlm.nih.gov/articles/PMC7019700/
8. **Hu J, et al.** "Role of N-acetylcysteine in non-acetaminophen-related acute liver failure: an updated meta-analysis". PMC7903568. https://pmc.ncbi.nlm.nih.gov/articles/PMC7903568/
9. **식품의약품안전처**. 「건강기능식품 공전」, 「건강기능식품 기능성 원료 인정 현황」. https://www.foodsafetykorea.go.kr/portal/board/board.do?menu_grp=MENU_NEW01&menu_no=2660
10. **NIH Office of Dietary Supplements**. "Omega-3 Fatty Acids — Health Professional Fact Sheet". https://ods.od.nih.gov/factsheets/Omega3FattyAcids-HealthProfessional/
11. **NHLBI**. "DASH Eating Plan". https://www.nhlbi.nih.gov/education/dash-eating-plan
12. **Skelin M, et al.** "Levothyroxine Interactions with Food and Dietary Supplements — A Systematic Review". Pharmaceuticals. 2017;10:69. https://pmc.ncbi.nlm.nih.gov/articles/PMC8002057/
13. **Rothman KJ, et al.** "Teratogenicity of High Vitamin A Intake". NEJM. 1995;333:1369–1373. https://www.nejm.org/doi/full/10.1056/NEJM199511233332101
14. **Hemilä H, Chalker E.** "Vitamin C for preventing and treating the common cold". Cochrane Database Syst Rev. 2013;1:CD000980.
15. **Nault D, et al.** "Zinc for prevention and treatment of the common cold". Cochrane Database Syst Rev. 2024. https://www.cochrane.org/evidence/CD014914_zinc-prevention-and-treatment-common-cold
16. **Hill C, et al.** "Health benefits and health claims of probiotics: bridging science and marketing". Brit J Nutr. 2014;112:1019. https://www.cambridge.org/core/journals/british-journal-of-nutrition/article/health-benefits-and-health-claims-of-probiotics-bridging-science-and-marketing/3C143B002B0289188B006FACA906E3BE
17. **Sconce E, et al.** "Vitamin K supplementation can improve stability of anticoagulation for patients with unexplained variability in response to warfarin". Blood. 2007;109(6):2419. https://ashpublications.org/blood/article/109/6/2419
18. **KDOQI Clinical Practice Guideline for Nutrition in CKD: 2020 Update**. Am J Kidney Dis. 2020;76(3 Suppl 1). https://www.ajkd.org/article/S0272-6386(20)30726-5/fulltext
19. **대한민국 표시광고의 공정화에 관한 법률** §3(부당한 표시·광고 행위 금지)
20. **건강기능식품에 관한 법률** §18(허위·과장의 표시·광고 금지)

---

> **개정 이력**
> - v1.0 (2026-05-26): 초안. AREDS2/Cochrane/식약처 정합화, 흡연자·임산부·만성질환·약물 분기 추가.
