# 05. 부족 영양소 진단 알고리즘 평가 및 수정안

> **문서 목적**: Lemon-Aid의 영양 진단 알고리즘(`07-core-algorithm.md`)을 KDRIs 2020, IOM/NAM DRI, EFSA DRV, KDOQI 2020 등 공식 자료 및 학술 근거에 기반하여 평가하고, 임상적으로 안전한 수정안을 제시한다.
>
> **법적 고지**: 본 문서는 영양 평가(nutritional assessment) 관점에서 작성된 기술 사양이며 의료 행위(진단·치료)를 대체하지 않는다. "결핍/위험"이라는 어휘는 *섭취량 분류*를 의미하며 *임상 진단*을 의미하지 않는다.
>
> **작성일**: 2026-05-26
> **버전**: v1.0 (Phase 1 평가)

---

## 1. 현재 구현 요약

`07-core-algorithm.md`에 기술된 현재 영양 진단 알고리즘의 핵심 로직:

```
1. 사용자 프로필 입력 (성별, 나이, 신장, 체중, 활동량)
2. → KDRIs 매핑 → 일일 권장 섭취량(RDI) 산출
3. 실제 섭취량 / RDI = ratio
4. 분류:
   - ratio < 0.35           → DEFICIENT  (결핍)
   - 0.35 ≤ ratio < 0.7     → LOW         (저섭취)
   - 0.7  ≤ ratio < 1.3     → ADEQUATE    (적정)
   - ratio ≥ 1.3            → EXCESSIVE   (과다)
   - 실제 > UL              → RISKY       (위험)
```

**핵심 가정**:
- 단일 RDA 값을 기준으로 비례 비교
- 전 인구(영아부터 노인까지)에 단일 임계값 적용
- 영양소 간 상호작용 미반영
- 만성질환·임신·수유 상태 미반영

---

## 2. KDRIs 2020 구조

### 2.1 EAR / RDA / AI / UL 정의

KDRIs 2020은 보건복지부와 한국영양학회가 3년(2018–2020)에 걸쳐 개정하여 **2020년 12월 22일 공표**한 한국인 영양소 섭취기준이다(국민영양관리법 근거). 총 **40종 영양소**에 대해 다음 4개 지표를 산출한다.

| 지표 | 정의 | 분포 가정 | 활용 |
|------|------|----------|------|
| **EAR** (Estimated Average Requirement, 평균필요량) | 대상 인구 절반(50%)의 1일 필요량을 충족하는 섭취량 | 절반 충족 | 집단 평가, 개인 부족 위험 평가 |
| **RDA** (Recommended Dietary Allowance, 권장섭취량) | EAR + 2 × SD. 대상 인구 97–98%의 필요량 충족 | 거의 모두 충족 | 개인 권장량 |
| **AI** (Adequate Intake, 충분섭취량) | EAR 산출 데이터 부족 시 사용. 건강한 집단의 관찰 섭취량 중앙값 | 경험적 | RDA 대체 |
| **UL** (Tolerable Upper Intake Level, 상한섭취량) | 부작용 위험 없이 섭취 가능한 1일 최대량 | 안전 상한 | 과다 섭취 경고 |

> 출처: 한국영양학회, 「2020 한국인 영양소 섭취기준」 (KNS, 2020); Korean Nutr Soc / Ministry of Health and Welfare. https://www.mohw.go.kr/board.es?mid=a10411010100&bid=0019&act=view&list_no=362385

### 2.2 KDRIs 2020 주요 변경점 (2015 대비)

- **에너지 적정 비율(AMDR)** 명시: 탄수화물 55–65%, 단백질 7–20%, 지방 15–30% (성인)
- **수분 충분섭취량(AI)** 별도 산출 (이전: AI만 식수 별도, 2020년: 음식 + 식수 분리)
- **만성질환 위험 감소 섭취량(CDRR, Chronic Disease Risk Reduction)** 신규 도입 — 나트륨 등
- **연령 구간 세분화**: 65–74세 / 75세 이상 분리 (이전: 65세 이상 단일)
- 영아 0–5개월 / 6–11개월 구분
- 임신부·수유부 추가량 별도 항목

> 출처: 한국영양학회, 「2020 한국인 영양소 섭취기준 제·개정: 교훈과 도전」, J Nutr Health 2021;54(5):425. https://e-jnh.org/DOIx.php?id=10.4163/jnh.2021.54.5.425

### 2.3 30종 영양소 카탈로그 (요약)

| 분류 | 영양소 (KDRIs 2020 수록) |
|------|---------------------------|
| 다량영양소 | 탄수화물, 식이섬유, 단백질(필수아미노산 9종), 지방(n-6, n-3, EPA+DHA), 수분 |
| 비타민 (지용성) | A, D, E, K |
| 비타민 (수용성) | C, B1, B2, B3(니아신), B5(판토텐산), B6, B7(비오틴), B9(엽산), B12 |
| 다량 무기질 | Ca, P, Na, Cl, K, Mg |
| 미량 무기질 | Fe, Zn, Cu, F, Mn, I, Se, Mo, Cr |
| 만성질환 위험 감소 | Na (CDRR), K (CDRR), 식이섬유 |

> 출처: 식품안전나라 「한국인 영양소 섭취기준(2020년)」 권장섭취량. https://www.foodsafetykorea.go.kr/foodcode/01_03.jsp?idx=12131

---

## 3. 평가

### 3.1 임계값(0.35 / 0.7 / 1.3 / UL) 검토

#### (1) 0.7 ADEQUATE 하한 — 학술적 근거 존재 (조건부)

학계에서 일반적으로 **"RDA의 2/3 (≈ 0.67)"** 를 부족 의심 cutoff로 사용한다. 이는 **Nutrient Adequacy Ratio(NAR) = 0.67** 와 동일 개념으로, 현재 구현의 0.7과 근사하다.

> NAR (개인 섭취량 / RDA)의 0.67 cutoff는 IOM의 "Nutrient Adequacy" 보고서에서 *흔히 사용되나 강한 통계적 근거는 없다*고 명시한다.
> 출처: IOM (Institute of Medicine). "Nutrient Adequacy: Assessment Using Food Consumption Surveys", NAP, 1986. https://www.ncbi.nlm.nih.gov/books/NBK217527/

**현재 알고리즘의 문제**:
- **RDA가 아닌 EAR**이 *개인 부족 위험* 평가에 적합 (IOM 2000 권고). RDA는 *집단 권장* 용도.
- 0.7 cutoff를 EAR 기반으로 재정의해야 한다.

#### (2) 0.35 DEFICIENT 하한 — 근거 미약

0.35 (= RDA의 35%)는 일반적으로 사용되는 cutoff가 아니다. WHO/FAO 또는 IOM 문헌에서 표준 근거를 찾기 어렵다. 대안:
- **0.5 (50% RDA)**: 일부 분석에서 사용
- **EAR 미만**: IOM 권장 (개인 평가용)

#### (3) 1.3 EXCESSIVE 상한 — 임상 의미 불분명

RDA의 130%는 KDRIs/IOM/EFSA 어느 가이드라인에서도 "과다(excess)"의 표준 기준이 아니다.
- **올바른 과다 기준은 UL**이며, RDA × 1.3은 UL과 무관하다.
- 예: Vitamin C RDA(성인) 100 mg, UL 2,000 mg. 1.3 × RDA = 130 mg은 UL의 6.5%에 불과 — *과다가 아니다*.
- 반대로 셀레늄의 경우 RDA 60 µg, UL 400 µg, 1.3 × RDA = 78 µg는 안전 범위.
- → **EXCESSIVE 분류는 UL 단일 기준으로 통합 권장**.

#### (4) UL → RISKY — 타당

UL 초과는 KDRIs 2020 정의상 부작용 위험이 있는 섭취량이므로 RISKY 분류는 적절. 단, 일부 영양소(나트륨)는 UL 대신 **CDRR**(만성질환 위험 감소 섭취량) 사용 필요.

### 3.2 임산부·수유부·노인 분기 부재

KDRIs 2020은 임신·수유에 대해 **별도 추가량**을 명시한다(현재 알고리즘에 미반영):

| 영양소 | 일반 여성 RDA (19–49세) | 임신부 추가량 | 수유부 추가량 |
|--------|------------------------|--------------|--------------|
| 엽산 | 400 µg DFE | **+220 µg** | +150 µg |
| 철 | 14 mg | **+10 mg** (2·3기) | 0 |
| 요오드 | 150 µg | **+90 µg** | +190 µg |
| 단백질 | 50–55 g | +25 g (3기) | +25 g |
| Vit A | 650 µg RAE | +70 µg | +490 µg |
| Vit D | 10 µg AI | +0 (단, 결핍 시 보충) | +0 |
| 칼슘 | 700 mg | +0 (KDRIs 2020) | +0 |

> 출처: KDRIs 2020 권장섭취량 표; 식품안전나라. https://www.foodsafetykorea.go.kr/foodcode/01_03.jsp?idx=12131
> 임신부 엽산 권장량 국제 비교: WHO Guideline (2012) — 400 µg/d 보충 권고. https://www.ncbi.nlm.nih.gov/books/NBK132250/

**노인(65세 이상)** KDRIs 2020 변경:
- 65–74세 / 75세 이상 분리
- 칼슘 RDA 700 mg (남) / 800 mg (여, 75세 이상) — 일반 성인 동일
- Vit D AI 15 µg (이전 10 µg에서 상향) — *골다공증 예방 강조*
- 비타민 B12 흡수 저하 고려 → 권장 유지하나 보충 형태(crystalline) 권고 (IOM과 동일 입장)

### 3.3 영양소 간 상호작용 미반영

현재 알고리즘은 각 영양소를 **독립적으로** 평가하지만, 다음 상호작용은 임상적으로 중요하다:

| 상호작용 | 메커니즘 | 출처 |
|----------|---------|------|
| **Vit D ↑ → Ca 흡수 ↑** | Vit D는 장내 Ca/Mg 흡수 증가 | Nutrients 2016;8(1):3. https://pmc.ncbi.nlm.nih.gov/articles/PMC4717874/ |
| **Vit D 보충 → Mg 배설 ↑** | 동일 자료 — Mg 보충 동반 필요 가능 | 동일 |
| **Ca:Mg 비율 ↑** | 2:1 초과 시 Mg 흡수 경쟁 | 동일 |
| **Ca + 철** | 동시 섭취 시 비헴철 흡수 ↓ (최대 50–60%) | IOM DRI Iron, 2001 |
| **Zn ↔ Cu** | 고용량 Zn(>50mg) → Cu 흡수 ↓ | IOM DRI Zinc, 2001 |
| **Vit C → 비헴철 흡수 ↑** | 식사 중 동시 섭취 권장 | KDRIs 2020 |
| **Vit K ↔ 와파린** | 약물 상호작용 (4장에서 별도) | 다음 파일 06-goal-matrix.md 참조 |

### 3.4 만성질환자 분기 부재 — **임상 안전성의 핵심 결함**

현재 알고리즘은 **건강 성인 KDRIs**를 모든 사용자에게 동일 적용한다. 그러나 주요 만성질환에서는 일반 권장량이 *오히려 위험*하거나 *부족*하다.

| 질환 | 일반 KDRIs와 정반대/상이한 권장 | 출처 |
|------|--------------------------------|------|
| **CKD 3–5단계** | 칼륨·인 *제한*. 단 KDOQI 2020은 "혈청 K/P 정상 유지" 개별 조정 권고 (일률 제한 X) | KDOQI 2020. https://www.ajkd.org/article/S0272-6386(20)30726-5/fulltext |
| **CKD 비투석** | 인 800–1,000 mg/d (KDRIs 700 mg AI에 근접하나 가공식품 인 제한 강조) | 동일 |
| **고혈압** | Na <2,300 mg/d (DASH); 중증은 <1,500 mg/d. KDRIs CDRR Na 2,300 mg | NHLBI DASH. https://www.nhlbi.nih.gov/education/dash-eating-plan |
| **당뇨병** | 탄수화물 비중 ↓, 식이섬유 ↑ (KDRIs AMDR 55–65%보다 ↓ 권장) | ADA 2024 Standards of Care |
| **간경변·간성뇌증** | 단백질 1.2–1.5 g/kg/d (대상부전 시), 분지쇄 아미노산 고려 — KDRIs 0.91 g/kg보다 ↑ | EASL Clinical Guideline 2019 |
| **임신** | 엽산, 철, 요오드 *대폭* 증가; **Vit A 상한 3,000 µg RAE** (기형 위험) | NEJM 1995;333:1369. https://www.nejm.org/doi/full/10.1056/NEJM199511233332101 |
| **갑상선 기능 저하** | 요오드 *과다 주의* (한국은 평균 섭취량 이미 권장량 이상) | KNHANES 데이터 |

**왜 만성질환자와 일반 사용자를 영양 진단에서 분리해야 하는가**:

1. **방향이 정반대인 영양소가 존재한다.**
   CKD 환자에게 KDRIs 칼륨 권장량(3,500 mg AI, 성인)을 그대로 적용하면 *고칼륨혈증*을 유도할 수 있다. 일반인 권장 = "최소 이상 섭취하라"인 반면, CKD 권장 = "혈청 수치 정상 유지하도록 조정하라"이다 — *목적함수가 반대 부호*다.

2. **상한이 일반인보다 훨씬 낮다.**
   임산부의 비타민 A 상한은 3,000 µg RAE(=10,000 IU)/d로, 기형 위험을 피하기 위함이다(WHO, NEJM 1995). 일반 KDRIs UL을 그대로 사용하면 위험을 놓친다.

3. **약물–영양소 상호작용으로 약효가 변동한다.**
   와파린 복용자 + Vit K 함유 보충제 → INR 변동 (06-goal-matrix.md §4.3 참조).

4. **법적·윤리적 리스크.**
   대한민국 의료법·약사법은 "진단·치료"를 비의료인이 수행할 수 없도록 한다. Lemon-Aid가 만성질환자에 일반 권장량을 적용하면 *임상적 권고의 외관*을 띠게 되어 법적 책임이 발생할 수 있다. → **분기 자체가 안전 가드레일**.

5. **사용자 신뢰 및 사고 예방.**
   영양 권장은 "도움" 목적이나, 만성질환자에 잘못 적용되면 *해악*이 된다. 분리 라우팅으로 "의사·영양사 상담 권유" 메시지를 표출함이 윤리적 디폴트.

---

## 4. 수정 권고

### 4.1 KDRIs 2020 정확 매핑

- **개인 부족 위험 평가는 EAR 기준**, 권장량 표시는 RDA 기준으로 이원화.
  - `is_at_risk = intake < EAR`
  - `meets_recommendation = intake ≥ RDA`
- **AI 영양소(Vit D, K, 수분 등)** 는 EAR 부재 → AI 미만 시 "AI 미달" 별도 라벨.
- 40종 전 영양소 매핑 테이블을 `nutrient_kdris_2020.json`으로 외부화 (코드와 분리).

### 4.2 임산부 / 수유부 / 소아 / 노인 라우팅 추가

```python
def get_reference_intake(user, nutrient):
    base = KDRIS_2020[user.sex][user.age_band][nutrient]
    if user.is_pregnant:
        base += KDRIS_2020_PREGNANCY_DELTA[user.trimester][nutrient]
    if user.is_lactating:
        base += KDRIS_2020_LACTATION_DELTA[nutrient]
    return base  # {ear, rda, ai, ul, cdrr}
```

연령 구간(KDRIs 2020): 영아 0–5/6–11개월, 유아 1–2/3–5세, 소아 6–11세, 청소년 12–18세, 성인 19–29/30–49/50–64세, 노인 65–74/75세 이상.

### 4.3 영양소 간 상호작용 경고 (Phase 1.5)

```python
def detect_interactions(intakes):
    warnings = []
    # Ca:Mg 비율 체크
    if intakes['Ca'] / intakes['Mg'] > 2.5:
        warnings.append("Ca:Mg 비율이 높습니다. 마그네슘 흡수가 저해될 수 있습니다.")
    # Vit D 보충 시 Mg 동반 권고
    if intakes['VitD'] >= REF_VitD['rda'] and intakes['Mg'] < REF_Mg['ear']:
        warnings.append("비타민 D 충분 섭취 시 마그네슘 동반 권장 (배설 증가)")
    # Zn 고용량 시 Cu 모니터
    if intakes['Zn'] > 50:  # mg/d
        warnings.append("아연 50mg/d 초과 시 구리 결핍 위험. 장기 복용 시 모니터링.")
    return warnings
```

### 4.4 만성질환자 분기 — **Phase 1 필수 가드레일**

```python
CHRONIC_FLAGS = {'CKD', 'HTN', 'DM', 'CIRRHOSIS', 'CHF', 'THYROID', 'CANCER', 'IBD'}

def diagnose_nutrition(user, intake):
    # === 가드레일 1: 만성질환자는 일반 KDRIs 적용 거부 ===
    if user.chronic_conditions & CHRONIC_FLAGS:
        return {
            "status": "REFERRAL_REQUIRED",
            "message": (
                "만성질환이 등록된 사용자입니다. 일반 영양 권장량(KDRIs)은 "
                "본 질환에서 임상적으로 부적절할 수 있어 자동 평가를 보류합니다. "
                "주치의·임상영양사와 상담하세요."
            ),
            "disease_specific_hint": CHRONIC_NUTRITION_HINTS.get(user.primary_condition),
        }

    # === 가드레일 2: 임산부/수유부 별도 라우팅 ===
    if user.is_pregnant or user.is_lactating:
        ref = get_reference_intake(user, ...)  # 추가량 반영
        # 비타민 A는 retinol만 합산하여 UL(3,000 µg RAE) 엄격 체크
        if intake['VitA_retinol'] > 3000:
            return {"status": "TERATOGENIC_RISK", ...}

    # === 일반 성인 경로: EAR/RDA/UL 기반 분류 ===
    ref = get_reference_intake(user, nutrient)
    intake_ratio = intake / ref['rda']

    if intake > ref['ul']:
        status = "RISKY"
    elif intake < ref['ear']:
        status = "AT_RISK_INADEQUATE"   # ← 0.35/0.7 임의 cutoff 제거
    elif intake < ref['rda']:
        status = "BELOW_RDA"            # AI 영양소는 BELOW_AI
    else:
        status = "ADEQUATE"

    return {"status": status, "ratio": intake_ratio, "ref": ref,
            "interactions": detect_interactions(intake)}
```

#### 4.4.1 권장 분류 체계 (개정안)

| 신규 분류 | 기준 | 비고 |
|----------|------|------|
| `AT_RISK_INADEQUATE` | intake < EAR (또는 AI의 70%) | IOM/KDRIs 표준 부족 위험 정의 |
| `BELOW_RDA` | EAR ≤ intake < RDA | 보충 고려 가능 영역 |
| `ADEQUATE` | RDA ≤ intake ≤ UL | 안전·충족 |
| `EXCESSIVE_NEAR_UL` | UL의 80% 이상 ~ UL 미만 | 사전 경고 |
| `RISKY` | intake > UL (또는 CDRR 초과 시 Na 등) | 즉각 경고 |
| `REFERRAL_REQUIRED` | 만성질환자/임신부/약물 복용자 | 상담 권유 |

---

## 5. 근거 수준 재평가

| 항목 | 현재 | 평가 | 개정 후 |
|------|------|------|--------|
| KDRIs 매핑 | 단일 RDA | A (가이드라인 직접 인용) | A (EAR/RDA/AI/UL 모두 사용) |
| 0.35 / 0.7 / 1.3 cutoff | 명시 | **C** (0.7은 NAR 0.67과 근사하나 0.35·1.3 근거 빈약) | A (EAR/RDA/UL 표준) |
| 임신/수유 분기 | 미반영 | **F** (없음) | A (KDRIs 추가량 적용) |
| 영양소 상호작용 | 미반영 | F | B (주요 8쌍 적용) |
| 만성질환 분기 | 미반영 | **F** (안전성 결함) | A (REFERRAL 게이트) |
| 약물 상호작용 | 미반영 | F | 06-goal-matrix.md 참조 |

**Phase 1 차단성 결함**: 만성질환자 분기 부재 — 출시 전 필수 구현.

---

## 6. 참고 문헌

1. **한국영양학회·보건복지부**. 「2020 한국인 영양소 섭취기준」, 2020-12-22. https://www.mohw.go.kr/board.es?mid=a10411010100&bid=0019&act=view&list_no=362385
2. **한국영양학회**. 「2020 한국인 영양소 섭취기준 활용자료」, 2022. https://www.mohw.go.kr/board.es?mid=a10411010100&bid=0019&act=view&list_no=370012
3. 한국영양학회. "2020 한국인 영양소 섭취기준 제·개정: 교훈과 도전". J Nutr Health. 2021;54(5):425. DOI:10.4163/jnh.2021.54.5.425. https://e-jnh.org/DOIx.php?id=10.4163/jnh.2021.54.5.425
4. 식품안전나라. 「한국인 영양소 섭취기준(2020년) 권장섭취량」. https://www.foodsafetykorea.go.kr/foodcode/01_03.jsp?idx=12131
5. **IOM (Institute of Medicine)**. "Dietary Reference Intakes: Applications in Dietary Assessment". Washington, DC: NAP; 2000. https://www.ncbi.nlm.nih.gov/books/NBK222890/
6. IOM. "Nutrient Adequacy: Assessment Using Food Consumption Surveys". NAP; 1986. https://www.ncbi.nlm.nih.gov/books/NBK217527/
7. **EFSA Panel on Dietetic Products, Nutrition and Allergies (NDA)**. "Scientific Opinion on Dietary Reference Values". EFSA Journal series. https://www.efsa.europa.eu/en/topics/topic/dietary-reference-values
8. **KDOQI Clinical Practice Guideline for Nutrition in CKD: 2020 Update**. Am J Kidney Dis. 2020;76(3 Suppl 1):S1–S107. https://www.ajkd.org/article/S0272-6386(20)30726-5/fulltext
9. Lambert K, et al. "Commentary on the 2020 update of the KDOQI clinical practice guideline for nutrition in CKD". Nephrology. 2022. https://pmc.ncbi.nlm.nih.gov/articles/PMC9303594/
10. **NHLBI**. "DASH Eating Plan". National Heart, Lung, and Blood Institute. https://www.nhlbi.nih.gov/education/dash-eating-plan
11. Rothman KJ, et al. "Teratogenicity of High Vitamin A Intake". N Engl J Med. 1995;333:1369. https://www.nejm.org/doi/full/10.1056/NEJM199511233332101
12. **WHO**. "Guideline: Daily Iron and Folic Acid Supplementation in Pregnant Women". Geneva; 2012. https://www.ncbi.nlm.nih.gov/books/NBK132250/
13. Rosanoff A, et al. "Essential Nutrient Interactions: Does Low or Suboptimal Magnesium Status Interact with Vitamin D and/or Calcium Status?". Adv Nutr. 2016;7(1):25–43. https://pmc.ncbi.nlm.nih.gov/articles/PMC4717874/
14. **EASL Clinical Practice Guidelines on nutrition in chronic liver disease**. J Hepatol. 2019;70:172–193.
15. **ADA Standards of Care in Diabetes — 2024**. Diabetes Care. 2024;47(Suppl 1).

---

> **개정 이력**
> - v1.0 (2026-05-26): 초안. KDRIs 2020 정합화, 만성질환자/임신부 분기 추가, EAR/RDA/UL 표준화.
