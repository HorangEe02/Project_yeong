# 00. Lemon-Aid Core Algorithm 평가·수정안 — Overview

> **문서 정보**
> 버전: v1.0 | 작성일: 2026-05-26 | 상태: 평가 완료, 수정안 제시
> 대상 원문: [`docs/Nutrition-docs/07-core-algorithm.md`](../docs/Nutrition-docs/07-core-algorithm.md) (v1.1)
> 본 폴더의 7개 상세 문서 + 1개 흡연·음주 종합 + 1개 참고문헌 일람으로 구성

---

## 📋 한 줄 요약

> Lemon-Aid의 **회사 정의 알고리즘 8개**(BMI/v1~v4/BMR/TDEE/체중예측) + **갭 영역 4개**(OCR/식단/진단/매트릭스)를 *공식 가이드라인·논문 근거로 평가*하고 수정안을 제시한다. **3가지 분리 축**:
> 1. **만성질환자** — 4가지 이유 (운동 / 영양 / BMR·체중 / 약물 상호작용) → [[07]](07-chronic-disease-rationale.md)
> 2. **흡연자** — Vit C +35mg / β-carotene 위험 / 운동 +가중치 / 골다공증 → [[09]](09-smoking-alcohol-rationale.md)
> 3. **음주자** — 알코올 7 kcal + 지방 산화 억제 / B1·B9·Mg 결핍 / Vit A 독성 / AUDIT-KR → [[09]](09-smoking-alcohol-rationale.md)

---

## 📁 폴더 구조

```
Lemon-Aid/core-algorithm/
├── 00-overview-and-evaluation.md    # 이 파일 — 전체 평가 + Phase별 수정 로드맵
├── 01-bmi-classification.md         # BMI 분류 (KSSO / WHO Asia-Pacific)
├── 02-activity-score.md             # 활동점수 v1~v4 (걸음수 / HRmax / 백분위 / 만성질환)
├── 03-bmr-tdee.md                   # BMR (Mifflin-St Jeor) + TDEE (PAL / METs)
├── 04-weight-prediction.md          # 7-step 체중 예측 (Wishnofsky → Hall 동적)
├── 05-nutrition-diagnosis.md        # 부족 영양소 진단 (KDRIs / DRI)
├── 06-goal-matrix.md                # 목적별 매트릭스 (눈건강 / 간기능 / 피로회복)
├── 07-chronic-disease-rationale.md  # ★ 만성질환자 분리 처리의 종합 근거
├── 08-references.md                 # 참고 문헌·공식 가이드 일람
└── 09-smoking-alcohol-rationale.md  # ★ 흡연·음주 반영 (v1.0, 2026-05-26 추가)
```

---

## 🎯 평가 방법론

1. **근거 수준 (A/B/C)** 재평가 — 원문의 등급을 *공식 가이드·논문 1차 출처*와 대조
2. **알고리즘별 강점·약점** 도출
3. **수정안 + 의사 코드** 제시 (즉시 / Phase 2 / Phase 3)
4. **만성질환자 분기 이유** — 모든 알고리즘 공통 축으로 명시
5. **윤리·법무 가드레일** — 진단·치료 표현 회피, 식약처 인정 문구 우선

---

## 📊 알고리즘별 평가 요약

### 🟢 회사 정의 영역 (8개)

| # | 알고리즘 | 원문 등급 | 평가 등급 | 핵심 수정 권고 | 상세 |
|---|---|---|---|---|---|
| 1 | **BMI 분류** | A | A (유지) + 보강 | KSSO 최신 6단계 (≥35.0 추가) + WHtR 보완 + 표준/Asia-Pacific 옵션 | [[01]](01-bmi-classification.md) |
| 2 | **v1 권장걸음수·기본점수** | (미명시) | B → A 가능 | Tudor-Locke 연령별 권장 옵션화, 노인 권장 4,400~7,500 보정 | [[02]](02-activity-score.md) |
| 3 | **v2 심박 가중** | B | B (유지) | **기본 공식을 Tanaka 2001로 전환**, Karvonen HRR 옵션 | [[02]](02-activity-score.md) |
| 4 | **v3 백분위 보너스** | (미명시) | B/C | 표본 부족 시 그룹 확장 로직, outlier 처리 | [[02]](02-activity-score.md) |
| 5 | **v4 만성질환 가중** | B/C | C (유지) | 가중치 *임상 효과 아님* 명시, "활동 동기 점수" UX | [[02]](02-activity-score.md) + [[07]](07-chronic-disease-rationale.md) |
| 6 | **BMR (Mifflin-St Jeor)** | A | A (유지) | 체지방률 입력 시 Katch-McArdle 옵션, 노인 보정 검토 | [[03]](03-bmr-tdee.md) |
| 7 | **TDEE (걸음수 PAL)** | (미명시) | B | METs + 운동 분(min) 입력 옵션, 웨어러블 cadence 통합 | [[03]](03-bmr-tdee.md) |
| 8 | **7-step 체중 예측** | B/C | C (단기에만 유효) | **3개월+ 예측은 Hall 동적 모델로**, 보정계수 0.85/0.95는 Phase 3 ML로 대체 | [[04]](04-weight-prediction.md) |

### 🔴 갭 영역 (4개) — 본 평가의 핵심 검토 대상

| # | 알고리즘 | 평가 등급 | 핵심 수정 권고 | 상세 |
|---|---|---|---|---|
| ⓐ | **영양제 OCR + LLM 파싱** | — | (구현 진행 중 — 본 평가 범위 밖, 별도 OCR 비교 가이드 참조) | (원문 §4.1) |
| ⓑ | **식단 → 영양소 변환** | — | (구현 진행 중) | (원문 §4.2) |
| ⓒ | **부족 영양소 진단** | B | KDRIs 2020 정확 매핑, **임산부/노인/만성질환자 라우팅** 필수 추가 | [[05]](05-nutrition-diagnosis.md) |
| ⓓ | **목적별 매트릭스** | B/C | 식약처 인정 문구 우선, **약물 상호작용 경고 시스템 1급 우선** | [[06]](06-goal-matrix.md) |

---

## ⚠️ 가장 시급한 시정 사항 (P0)

### 1. **약물·영양제 상호작용 경고 시스템** (안전 직결)

| 약물 | 영양소/영양제 | 위험 |
|---|---|---|
| **와파린** | 비타민 K (녹황색 채소, 일부 종합비타민) | 항응고 효과 변동 |
| **갑상선약 (Levothyroxine)** | 칼슘 / 철분 / 콩 / 커피 | 흡수 ↓ — 4시간 간격 필수 |
| **메트포민** | 비타민 B12 | 장기 복용 시 B12 결핍 위험 |
| **항응고제** | 오메가-3, 은행잎, 비타민 E | 출혈 위험 |
| **MAOI** | 티라민 (숙성 치즈, 발효식품) | 고혈압 위기 |
| **신부전 환자** | 칼륨·인 함유 영양제 | 축적·위험 |
| **임산부** | 비타민 A 다량 (>3,000μg) | 기형 위험 |

→ **사용자 프로필에 복용 약물 입력 필드 + 영양제 추천 시 자동 경고 분기 필수.**

### 2. **만성질환자 자동 계산 비활성 분기**

| 질환 | 영향 알고리즘 | 권고 |
|---|---|---|
| **갑상선 기능 저하/항진** | BMR / TDEE / 체중 예측 | 자동 계산 비활성 + 의사 상담 안내 |
| **PCOS** | 7-step 체중 예측 | 신뢰도 ↓ 표시, *베이지안 보정* 권장 |
| **CKD** | KDRIs 일반 적용 | DASH/KDOQI 라우팅 |
| **부신피질 호르몬 복용** | 체중 예측 | 비활성 + 안내 |

### 3. **UX 라벨 정리** (의료기기·약사법 회피)

| 금지 | 권장 |
|---|---|
| "비만 진단" | "BMI 분류 (스크리닝)" |
| "질환 개선 점수" | "활동 동기 점수" |
| "치료 효과" | "식약처 인정 기능성" 인용 |
| "체중 예측" 단정 | "기대 체중 범위 (±)" |
| "영양 결핍 진단" | "권장량 대비 섭취 비율" |

---

## 🚬🍶 흡연자·음주자 분기 매트릭스 (v1.1 추가, [[09]](09-smoking-alcohol-rationale.md))

| 알고리즘 | 흡연자 분기 | 음주자 분기 |
|---|---|---|
| **BMI 분류** | (직접 영향 X) | + **WHtR/허리둘레 보조** (사르코페니아 비만·복부 비만) |
| **v1 권장걸음수** | 동일, RPE 모니터링 안내 | 동일, 주간 음주 패턴은 보조 신뢰도 |
| **v2 심박 가중** | HRmax 10-17 bpm 낮을 수 있음 → THR 보정 옵션 | 음주 다음날 HRrest +5-10 bpm → outlier 처리 |
| **v3 백분위** | 별도 분리 X (역설 회피) | 별도 분리 X |
| **v4 가중치** | **+0.05~0.10** (CO-Hb 부담 + 금연 동기). ⚠️ 만성질환과 중복 금지 `max()` | 보정 X (5중 영향 단순화 불가) |
| **BMR (Mifflin)** | **보정 X** (Perkins 1992) | 만성 음주자 신뢰도 ↓ 표시 |
| **TDEE** | 보정 X | 알코올 칼로리 자동 산입 |
| **7-step 체중 예측** | 금연 후 1년 이내 **+4.7 kg** 안내 (Aubin 2012) | 알코올 kcal + 지방 저장 보정 **+30%** (Suter) |
| **식단 → 영양소 변환** | (직접 영향 X) | **주류 카테고리 추가 필수** |
| **부족 영양소 진단** | **Vit C +35mg** (IOM 라벨) | AUDIT-KR 위험 시 **B1·B9·Mg·Zn 자동 보강** |
| **목적별 매트릭스** | **β-carotene·Vit A 다량 경고 강화** (이미 부분 구현) | **Vit A 단일제·아세트아미노펜 자동 경고**, 밀크씨슬/NAC 상담 권고 |

### 🚨 P0 추가 (안전 직결)

| 항목 | 처리 |
|---|---|
| 식단 입력에 **주류 카테고리** | 소주/맥주/막걸리/와인/위스키 + `kcal=ml×ABV×0.789×7/100` 자동 |
| **AUDIT-KR 자가검진** 모듈 | 회원가입 또는 월 1회 |
| AUDIT-KR ≥ 의존 cut-off (남10/여8) | **1577-0199 안내 + 영양제 추천 중단** |
| 흡연자 β-carotene/Vit A 다량 | 자동 경고 (ATBC/CARET 인용) |
| 음주자 Vit A 단일제 / 아세트아미노펜 | 자동 경고 (LiverTox) |

### 3가지 분기의 중복 적용 규칙

```python
# v4 활동점수 가중 우선순위
def v4_weight_multiplier(profile: UserProfile) -> float:
    chronic_w = calc_chronic_weight(profile.diseases)       # 1.0~1.30
    smoking_w = calc_smoking_weight(profile.smoking_status)  # 1.0~1.10
    # ⚠️ 중복 금지 — 만성질환 우선 또는 max() 선택
    return max(chronic_w, smoking_w)
```

음주자는 v4 가중 적용 X (자기보고 신뢰도 ↓, 5중 영향 단순화 불가) — 대신 *주간 음주 패턴*으로 활동점수 신뢰구간 별도 표시.

---

## 🛠️ Phase별 수정 로드맵

### Phase 1 (현재 → 단기, ~4주)

**P0 안전 직결 (즉시)**:
- [ ] 약물 입력 필드 + 영양제 상호작용 경고 시스템 ([[06]](06-goal-matrix.md))
- [ ] 갑상선·신장·간 환자 자동 계산 비활성 + 상담 안내 ([[07]](07-chronic-disease-rationale.md))
- [ ] UX 라벨 의료기기·약사법 회피 정비

**P1 정확도**:
- [ ] BMI 분류에 KSSO 비만 3단계 (≥35.0) 추가, `region: 'asia' | 'who'` 옵션 ([[01]](01-bmi-classification.md))
- [ ] v2 기본 HRmax를 **Tanaka 2001**로 전환 (220-나이는 옵션 유지) ([[02]](02-activity-score.md))
- [ ] v4 가중치를 "활동 동기 점수"로 UX 라벨 변경 ([[02]](02-activity-score.md) + [[07]](07-chronic-disease-rationale.md))
- [ ] 영양 진단 임계값에 임산부·노인·만성질환자 라우팅 ([[05]](05-nutrition-diagnosis.md))

### Phase 2 (~3개월)

- [ ] 체지방률 입력 시 Katch-McArdle BMR 옵션 ([[03]](03-bmr-tdee.md))
- [ ] TDEE에 METs + 운동 분(min) 입력 보강 ([[03]](03-bmr-tdee.md))
- [ ] 체중 예측 단기/중기 보정 + UX "기대 체중 범위" ([[04]](04-weight-prediction.md))
- [ ] 영양 진단에 영양소 간 상호작용 경고 (Ca-Fe, Vit D-Ca, Mg-Ca) ([[05]](05-nutrition-diagnosis.md))
- [ ] 목적별 매트릭스에 면역/수면/장 건강 추가 ([[06]](06-goal-matrix.md))
- [ ] v1 노인 권장 걸음수 보정 (4,400~7,500) ([[02]](02-activity-score.md))
- [ ] BMI 보완 지표 WHtR 추가 ([[01]](01-bmi-classification.md))

### Phase 3 (~6개월+)

- [ ] **체중 예측 3개월+ Hall 동적 모델** 도입 ([[04]](04-weight-prediction.md))
- [ ] 한국인 BMR 자체 데이터 보정 학습
- [ ] 사용자별 ML 적응형 보정 (베이지안)
- [ ] 웨어러블 cadence·심박 데이터 통합
- [ ] 자체 임상 데이터 후 v4 가중치 보정

---

## 📐 알고리즘 vs 만성질환자 분기 매트릭스

| 알고리즘 | 일반 사용자 | 만성질환자 | 분기 이유 (요약) |
|---|---|---|---|
| **BMI 분류** | 표준 KSSO | + 사르코페니아 / obesity paradox 주의 | 노인·근육질 BMI는 mortality 예측력 약함 |
| **v1 권장걸음수** | 8,000 기본 | 질환별 권장 (당뇨 ↑, 관절 ↓) | ACSM·ACR·GOLD 가이드별 안전 강도 다름 |
| **v2 심박 가중** | HRmax 50-70% | 질환별 안전 영역 | 심혈관 환자는 더 보수적, 안정기 후 점진 증량 |
| **v4 활동 가중** | ×1.0 | ×1.10~1.30 | 만성질환자 *상대적* 건강 이득 ↑ + 지속 동기 ↑ |
| **BMR/TDEE** | Mifflin | 갑상선 환자 자동 계산 비활성 | BMR 자체가 ±20~30% 변동 |
| **체중 예측** | 7-step | PCOS·갑상선 자동 비활성 또는 신뢰도 ↓ | "약속 미달" 시 신뢰 손상 |
| **영양 진단** | KDRIs | DASH/ADA/KDOQI/EASL 라우팅 | 일반 KDRIs는 *최소 권장량* — CKD에서 정반대 위험 |
| **영양제 추천** | 일반 권장 | **약물 상호작용 체크 + 전문가 상담** | 와파린/갑상선약/MAOI 등 위험 |

→ 상세 근거: [[07-chronic-disease-rationale.md]](07-chronic-disease-rationale.md)

---

## 🔬 근거 수준 (A/B/C) 재평가 종합

| 항목 | 원문 v1.1 | 본 평가 | 변경 사유 |
|---|---|---|---|
| BMI 분류 | A | A | 유지 (단 KSSO 최신 + 보완 지표) |
| v1 기본점수 | (미명시) | B | 8,000보 기본값은 Tudor-Locke와 호환되나 노인 보정 필요 |
| v2 HRmax | B | B | Tanaka로 기본 전환 권고 |
| v3 백분위 | (미명시) | B/C | 사회적 비교 동기는 양면성 |
| v4 만성질환 | B/C | C | 임상 효과 크기가 아닌 *프로젝트 우선순위* 재확인 |
| BMR Mifflin | A | A | 유지 |
| TDEE 걸음수 PAL | (미명시) | B | METs 보강 시 A로 향상 가능 |
| 7,700 kcal/kg | B/C | C (단기만) | Hall 2011 동적 모델로 장기 보강 필요 |
| 0.85/0.95 보정 | C | C | Phase 3에 ML로 대체 |
| KDRIs 영양 진단 | (미명시) | A → B | 단순 적용은 A, 만성질환 라우팅 부재로 B |
| AREDS2/식약처 | B/C | B | 식약처 인정 문구 우선 |

---

## 📈 최종 권고 — 사용자 신뢰성 4축

1. **정확도** — 알고리즘 자체의 임상·과학적 타당성 (BMR/체중 예측의 한계 명시)
2. **안전성** — 약물 상호작용, 만성질환자 위험 회피 (P0 시급)
3. **투명성** — 근거 수준 표기, 신뢰도 범위 (±) 표시, UX 라벨 정직성
4. **법적 적합성** — 의료기기법·약사법·식약처 인정 문구 우선

---

## 🔗 상세 문서 인덱스

| 알고리즘 영역 | 문서 |
|---|---|
| BMI 분류 | [01-bmi-classification.md](01-bmi-classification.md) |
| 활동점수 v1~v4 | [02-activity-score.md](02-activity-score.md) |
| BMR / TDEE | [03-bmr-tdee.md](03-bmr-tdee.md) |
| 7-step 체중 예측 | [04-weight-prediction.md](04-weight-prediction.md) |
| 부족 영양소 진단 | [05-nutrition-diagnosis.md](05-nutrition-diagnosis.md) |
| 목적별 매트릭스 | [06-goal-matrix.md](06-goal-matrix.md) |
| **★ 만성질환자 분리 근거** | [07-chronic-disease-rationale.md](07-chronic-disease-rationale.md) |
| 참고 문헌 | [08-references.md](08-references.md) |
| **★ 흡연·음주 반영 (v1.1)** | [09-smoking-alcohol-rationale.md](09-smoking-alcohol-rationale.md) |

---

## 📝 변경 이력

| 버전 | 날짜 | 변경 사항 | 작성자 |
|---|---|---|---|
| v1.0 | 2026-05-26 | 평가 + 수정안 초안 (7개 영역 + 종합) | Claude (Lemon-Aid 자료 기반) |
| v1.1 | 2026-05-26 | **흡연·음주 반영 추가** ([[09]](09-smoking-alcohol-rationale.md)) — 6 영역 (BMR·체중 / 영양 / 운동) × (흡연 / 음주) 매트릭스 + 3가지 분기 중복 규칙 | Claude (6 agent 병렬 조사) |
