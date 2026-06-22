# 만성질환자 영양제 카테고리 확장 — 브레인스토밍 분석 보고서

> 작성일: **2026-05-21**
> 작성자: Claude Code
> 짝 문서: [project-status-report.md](./project-status-report.md) (현황), [next-steps-user-actions.md](./next-steps-user-actions.md) (실행 가이드)
> 페르소나: **B형 김건강, 52세 만성질환자** (필라이즈 대비 차별화 영역)

---

## 0. Executive Summary

### 발견사항

1. **외장 SSD 카테고리 인벤토리 부족 활용**: `/Volumes/Corsair EX300U Media/.../tampermonkey/naver/` 에 **43 개 카테고리** 폴더가 있으나, 현재 Stage 0 manifest 는 그 중 **16 개 (37%)** 만 사용. 만성질환 관련 핵심 카테고리(오메가3, 코엔자임Q10, 혈관_낫토_폴리코사놀, 식이섬유 등)는 모두 미활용 27 개 안에 있음.
2. **만성질환별 영양제 매핑 정량 자료 확보**: NCBI/JACC/Medical News Today 의 EBM 자료에 따르면 오메가3 (1.8g/day) · CoQ10 (50mg/day) · 마그네슘 · 커큐민이 만성질환 outcome 에 강한 증거를 가짐. 한국 식약처도 환자용식품 표준제조기준을 2026 년까지 확장 중.
3. **차별화 전략 명확**: 외장 SSD 미활용 카테고리 27 개 중 **약 11 개**가 만성질환 직접 타겟. 페르소나 B형(필라이즈 대비) 차별화에 즉시 활용 가능.

### 결론

**작업 가능성: 매우 높음.** 4 가지 옵션 분석 결과, **옵션 C (매트릭스 JSON) + 옵션 D (worksheet Tier 4)** 를 Phase 1 로, **옵션 A (가중 샘플링) + 옵션 B (V3 schema 확장)** 를 Phase 2 로 진행하는 단계적 접근이 최적.

---

## 1. 외장 SSD 카테고리 인벤토리 분석

### 1.1 전체 43 개 카테고리

마운트 확인: ✅ `/Volumes/Corsair EX300U Media/00_work_out/00_data_set/pr/downloads_tampermonkey/lemon-aid/_inbox/tampermonkey/naver/`

| 구분 | 개수 | 카테고리 |
|---|---:|---|
| **현재 manifest 사용** | **16** | BCAA_EAA, HMB_타우린, 강황_커큐민, 관절_MSM_콘드로이친, 글루코사민, 기타, 남성_쏘팔메토, 뇌_은행잎, 다이어트_체지방, 단백질_프로틴, 루테인_눈, 마그네슘, 멀티비타민, 밀크씨슬_간, 비타민A, 비타민B |
| **미활용 (추가 가능)** | **27** | 비타민C, 비타민D, 비타민E, 비타민K, 수면_멜라토닌, 스트레스_아쉬와간다, 스피루리나_클로렐라, 식이섬유, 아르기닌_시트룰린, 아사이_베리류, 아연, 어린이_키성장, 여성영양제, 오메가3, 유산균_프로바이오틱, 종합영양제, 철분, 카페인_각성, 칼슘, 코엔자임Q10, 콜라겐, 크레아틴, 프로폴리스_벌, 프리워크아웃, 항산화, 혈관_낫토_폴리코사놀, 효소_소화 |

**현재 활용률**: 16/43 = **37%**. 만성질환 핵심 카테고리는 모두 미활용 27 개 안에 위치.

### 1.2 페르소나별 카테고리 분류

- **B형 핵심 (만성질환 직접 타겟, 11 개)**: 오메가3, 코엔자임Q10, 혈관_낫토_폴리코사놀, 강황_커큐민, 마그네슘, 식이섬유, 칼슘, 비타민D, 비타민K, 밀크씨슬_간, 항산화
- **B형 동반 (만성질환자 동반 흔함, 8 개)**: 수면_멜라토닌, 스트레스_아쉬와간다, 유산균_프로바이오틱, 아르기닌_시트룰린, 여성영양제, 뇌_은행잎, 비타민B, 비타민C
- **A형 (예방·일반 직장인, 16 개)**: 비타민A, 비타민E, 멀티비타민, 종합영양제, 어린이_키성장, 콜라겐, 프로폴리스_벌, 스피루리나_클로렐라, 아사이_베리류, 아연, 철분, 효소_소화 등
- **회피 권장 (만성질환자 부적합, 3 개)**: 카페인_각성, 프리워크아웃, 크레아틴 (운동 보충제, 신장 부담 등)
- **운동·근력 (5 개)**: BCAA_EAA, HMB_타우린, 단백질_프로틴, 글루코사민, 관절_MSM_콘드로이친

---

## 2. 만성질환별 권장 영양제 매트릭스 (EBM 기반)

웹 검색 (NCBI / JACC / 식약처 / Medical News Today, 출처는 §7 참조) 으로 확보한 evidence-based 매핑:

| 만성질환 | 강한 증거 영양제 | 외장 SSD 카테고리 | 증거 수준 / 권장 용량 |
|---|---|---|---|
| **심혈관 질환** | 오메가3, CoQ10, 마그네슘, 폴산 | `오메가3` · `코엔자임Q10` · `마그네슘` · `혈관_낫토_폴리코사놀` | CoQ10 50 mg/day → all-cause mortality ↓ (heart failure) / 오메가3 1.8 g/day → MI risk ↓ |
| **고지혈증** (이상지질혈증) | 오메가3, 폴리코사놀, 식이섬유 | `오메가3` · `혈관_낫토_폴리코사놀` · `식이섬유` | 식약처 이상지질혈증 치료지침 명시 |
| **2형 당뇨** | CoQ10, 커큐민, 마그네슘 | `코엔자임Q10` · `강황_커큐민` · `마그네슘` | 커큐민 → 인슐린 ↓ (high quality), CoQ10 → HbA1c ↓ (moderate) |
| **고혈압** | 마그네슘, CoQ10, L-arginine/citrulline | `마그네슘` · `코엔자임Q10` · `아르기닌_시트룰린` | L-arginine/citrulline 혈관 확장 효과 |
| **골다공증** (50+ 여성·남성) | 칼슘, 비타민D, 비타민K (K2) | `칼슘` · `비타민D` · `비타민K` | 식약처 7대 환자용식품 기준 확장 예정 |
| **간 건강 / 약물 복용자** | 밀크씨슬 (실리마린) | `밀크씨슬_간` | 만성질환자 = 만성 약물 복용자 → 간 보호 |
| **만성 염증 / 항산화** | 커큐민, 항산화 일반 | `강황_커큐민` · `항산화` · `아사이_베리류` | 만성질환 공통 메커니즘 |
| **장 건강 / 면역** | 프로바이오틱스 | `유산균_프로바이오틱` | 만성질환자 면역 보강 |
| **만성 수면 장애** | 멜라토닌, 마그네슘 | `수면_멜라토닌` · `마그네슘` | 만성질환자 동반 흔함 |
| **만성 스트레스** | 아쉬와간다, 마그네슘 | `스트레스_아쉬와간다` · `마그네슘` | 코르티솔 조절 |
| **갱년기·여성 만성질환** | 칼슘, 비타민D | `여성영양제` · `칼슘` · `비타민D` | |
| **인지 / 뇌 건강** | 은행잎, 오메가3, 비타민B | `뇌_은행잎` · `오메가3` · `비타민B` | 만성질환자 인지 저하 예방 |
| **빈혈 (만성신장질환 동반)** | 철분 (의사 처방 우선) | `철분` | 신장질환자 식약처 표준제조기준 존재 |
| **만성 신장질환** | (보충제 제한적, 식이 위주) | (해당 카테고리 없음) | 단백질 제한 → `단백질_프로틴` 회피 |

### 2.1 카테고리별 만성질환 인디케이션 매트릭스 (역방향)

| 외장 SSD 카테고리 | 만성질환 타겟 | 증거 수준 | 비고 |
|---|---|---|---|
| `오메가3` | 심혈관 / 고지혈증 / 당뇨 / 인지 | strong / strong / moderate / moderate | 고용량 부정맥 위험 ⚠️ |
| `코엔자임Q10` | 심혈관 / 당뇨 / 고혈압 | strong / moderate / moderate | |
| `혈관_낫토_폴리코사놀` | 심혈관 / 고지혈증 | strong / strong | 항응고제 상호작용 ⚠️ |
| `마그네슘` | 심혈관 / 당뇨 / 고혈압 / 수면 / 스트레스 | moderate / moderate / moderate / moderate / moderate | 신장기능 저하 시 주의 ⚠️ |
| `강황_커큐민` | 당뇨 / 만성염증 | strong / moderate | 담석·간기능 주의 |
| `식이섬유` | 고지혈증 / 당뇨 | strong / moderate | |
| `비타민D` | 골다공증 / (결핍 보충) | strong / strong | 일반예방효과 약함 |
| `비타민K` | 골다공증 (K2) | moderate | 와파린 상호작용 ⚠️ |
| `칼슘` | 골다공증 | strong | |
| `밀크씨슬_간` | 간 건강 (만성 약물 복용자) | moderate | |
| `유산균_프로바이오틱` | 장·면역 | moderate | |
| `수면_멜라토닌` | 만성 수면 장애 | strong | |
| `스트레스_아쉬와간다` | 만성 스트레스 | moderate | SSRI 상호작용 ⚠️ |
| `뇌_은행잎` | 인지 | moderate | 항응고제 상호작용 ⚠️ |
| `비타민B` | 인지 / 메트포민 복용자 결핍 보충 | moderate | |
| `아르기닌_시트룰린` | 고혈압 | moderate | |
| `항산화` | 만성염증 | weak | |
| `여성영양제` | 갱년기·골다공증 | weak | |
| `철분` | 빈혈 (의사 처방) | moderate | 신장 환자 주의 |
| (그 외) | (만성질환 직접 타겟 아님) | — | |

---

## 3. 만성질환자 보충제 안전성 주의사항

라벨링 / UI / 추천 알고리즘에 반드시 반영:

### 3.1 용량 / 부작용 주의

- **고용량 오메가3 (>3 g/day)**: 부정맥 위험 ↑, 항응고제(와파린 등) 복용 시 출혈 위험 ↑
- **비타민 C / D / E / 셀레늄**: 장기 심혈관·당뇨 outcome 효과 약함. **결핍 보충 OK**, 일반 예방 효과 주장 금지 (CLAUDE.md Rule 1)
- **마그네슘 + 신장 기능 저하**: 고마그네슘혈증 위험

### 3.2 약물 상호작용 (의약품 ↔ 보충제)

| 약물 | 보충제 | 위험 |
|---|---|---|
| 와파린 (항응고제) | 비타민K | 효능 감소 |
| 와파린 / 항응고제 | 오메가3 고용량, 은행잎, 낫토 | 출혈 위험 ↑ |
| SSRI (항우울제) | 아쉬와간다 | 세로토닌 증후군 |
| 메트포민 (당뇨약) | 비타민B12 | 결핍 가능 (모니터링) |
| 스타틴 (콜레스테롤약) | CoQ10 | 스타틴이 CoQ10 합성 억제 → CoQ10 보충 권장 |

### 3.3 한국 식약처 환자용식품 정책

식약처가 환자용식품 표준제조기준을 단계적 확장 중. 현재 7종, 2026 년까지 고혈압·폐질환 등 추가 예정.

**기존 7종**:
1. 일반환자용
2. 당뇨환자용
3. 신장질환자용
4. 암환자용
5. 장질환자용
6. 열량·영양공급용
7. 연하곤란자용 점도조절식품

**예정 추가** (~2026):
- 고혈압환자용
- 폐질환환자용
- 기타 3 종

→ 우리 OCR 시스템이 식약처 분류와 일치하면 규제 추적 / B2B 가치 ↑.

---

## 4. 작업 옵션 4 가지 비교

### 옵션 A — 만성질환 가중 샘플링으로 manifest 재생성

| 항목 | 내용 |
|---|---|
| 무엇 | `prepare_supplement_ocr_live_manifest.py` 에 `--chronic-disease-priority` 옵션 추가. 카테고리별 가중치 기반 sampling |
| 가중치 예시 | 만성질환 타겟=3 / 동반=2 / 일반=1 / 회피=0 |
| 산출물 | `stage0_naver_chronic` 워크스페이스 + 30~50 fixture |
| 장점 | 페르소나 B형 시나리오 직접 매칭 |
| 단점 | 기존 stage0_naver 와 별도 비교 필요 |

### 옵션 B — V2/V3 schema 에 만성질환 메타데이터 필드 추가

| 항목 | 내용 |
|---|---|
| 무엇 | V3 schema 에 `chronic_disease_indications: list[ChronicCondition]` 필드 신규 |
| 8 종 condition | `diabetes`, `hypertension`, `dyslipidemia`, `cardiovascular`, `osteoporosis`, `chronic_kidney_disease`, `liver_disease`, `cognitive_decline` |
| 산출물 | 평가 보고서에서 만성질환별 정확도 분리 |
| 장점 | 페르소나 B형 시나리오의 의료 데이터 차별화 명확 |
| 단점 | 라벨링 비용 ↑ (사람이 매핑 판단 필요) |

### 옵션 C — 카테고리 ↔ 만성질환 매트릭스 JSON 추가 (정적 매핑) **[추천]**

| 항목 | 내용 |
|---|---|
| 무엇 | `data/nutrition_reference/chronic_disease_supplement_matrix.json` 신규 |
| 구조 | 카테고리명 → `chronic_disease_targets[]` + `cautions[]` |
| 산출물 | 추천 / 분석 알고리즘에서 자동 매핑 가능. schema 영향 없음 |
| 장점 | schema 변경 없이 동적 매핑. 라벨링 비용 변화 없음. EBM 근거 한 곳 |
| 단점 | 카테고리명 ↔ 매트릭스 키 동기화 유지 비용 |

### 옵션 D — 만성질환 관련 카테고리만 우선 추가 라벨링 **[추천]**

| 항목 | 내용 |
|---|---|
| 무엇 | worksheet 에 Tier 4 (만성질환 우선 15 fixture) 추가 |
| 대상 카테고리 | 오메가3, 코엔자임Q10, 혈관_낫토_폴리코사놀, 식이섬유, 비타민D, 비타민K, 스트레스_아쉬와간다, 수면_멜라토닌 |
| 산출물 | worksheet 30 → 45 fixture |
| 장점 | 기존 인프라 그대로 활용. 사용자 라벨링 부담 점진적 |
| 단점 | 단독으로는 메트릭 분리 효과 없음 (옵션 C 와 결합 필요) |

---

## 5. 추천 시퀀스

### Phase 1 (1~2 일) — **옵션 C + D 조합**

1. **C-1**: 매트릭스 JSON 작성 (43 카테고리 × 만성질환 8 종)
2. **C-2**: Pydantic schema 정의 (`ChronicDiseaseSupplementMatrix`)
3. **C-3**: 로더 유틸 + 단위 테스트
4. **D-1**: worksheet Tier 4 (15 fixture) 추가 → 총 45
5. **D-2**: `prepare_supplement_ocr_live_manifest.py` 에 `--category-filter` 옵션 추가

### Phase 2 (1 주) — **옵션 A + B**

1. **A**: `--chronic-disease-priority` 가중 샘플링 옵션 추가
2. **B**: V3 schema 에 `chronic_disease_indications` 필드 추가 (backward compatible default `[]`)
3. **추가 1**: `evaluate_ocr_three_tier.py` 에 만성질환별 그룹 메트릭 추가
4. **추가 2**: `label_ground_truth.py` 에 `--chronic-disease-targets` 옵션 추가

### 결합 시너지

옵션 C 매트릭스 + 옵션 D 라벨링 + 옵션 B schema → 평가 보고서에 **B형 페르소나 시나리오 별도 섹션** 가능:
- `cer_ko_avg_for_cardiovascular`
- `ingredient_name_exact_rate_for_diabetes`
- `accuracy_by_condition: {"cardiovascular": 0.94, "diabetes": 0.88, ...}`

---

## 6. 작업 가능성 평가

### 기술적 가능성: 🟢 매우 높음

- 외장 SSD 마운트 정상, 43 개 카테고리 즉시 활용 가능
- 기존 `prepare_supplement_ocr_live_manifest.py` 가 manifest 생성 인프라 제공
- 매트릭스는 정적 데이터 → 의학적 정확성만 검증되면 즉시 사용
- V3 schema 확장은 기존 fixture 와 backward compatible (`default = []`)

### 의학적 정확성: 🟡 중간 (의사 / 약사 검수 권장)

- 웹 검색 기반 EBM 매핑은 1차 자료. 한국 식약처 / 의학회 공식 자료로 보강 필요
- 약물 상호작용 표는 1차 추정. 실제 임상 가이드라인 cross-check 필요
- 페르소나 B형 (52세) 외 다른 연령대 (어린이·청소년·노인) 별도 검토 필요

### 비즈니스 임팩트: 🟢 매우 높음

- 핵심 메시지 "**필라이즈가 못하는 만성질환자 + 의료데이터 영역으로 차별화**" 와 직접 일치
- 식약처 환자용식품 기준 추적 → B2B 가치 (의료기관, 보험사)
- 약물 상호작용 명시 → 안전성 차별화

### 리스크: 🟡 중간

- 의학적 표현 금지 규칙 (CLAUDE.md Rule 1) 위반 위험 — `prescribe`, `cure`, `treat` 등 피하고 `may help`, `recommend`, `support` 사용
- 라벨링 비용 증가 (Tier 4 추가) — 사용자 시간 부담
- 매트릭스 ground truth 검증 비용 — 의료 전문가 리뷰 필요 (장기)

---

## 7. 출처 (References)

### 영문 의학 자료
- [Study finds heart health benefits for Omega-3, curcumin, and CoQ10 — Medical News Today](https://www.medicalnewstoday.com/articles/supplements-for-heart-health-which-ones-are-beneficial-and-which-ones-are-not)
- [Micronutrient Supplementation to Reduce Cardiovascular Risk — JACC](https://www.jacc.org/doi/10.1016/j.jacc.2022.09.048)
- [Use of Dietary Supplements Among People With Atherosclerotic Cardiovascular Disease — JAHA](https://www.ahajournals.org/doi/10.1161/JAHA.123.033748)
- [Systematic Review of Nutrition Supplements in Chronic Kidney Diseases — NCBI](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7911108/)
- [Key Micronutrients: Study Identifies Supplements That Benefit Cardiovascular Health — SciTech Daily](https://scitechdaily.com/key-micronutrients-study-identifies-supplements-that-benefit-cardiovascular-health/)
- [Heart Health Supplements That Work — Cooper Complete Blog](https://coopercomplete.com/blog/best-supplements-for-heart-health/)
- [Advances in cardiovascular supplementation: mechanisms, efficacy, and clinical perspectives — PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC12883399/)

### 한국 의학·정책 자료
- [식약처 고혈압·폐질환 등 환자용식품 5종 기준 마련 — 아시아엔](https://kor.theasian.asia/archives/326406)
- [이상지질혈증 치료지침 — 한국지질·동맥경화학회](https://lipid.or.kr/uploaded/board/guideline/_baea1c7741a8ccf9c377b428a77fbf3c1.pdf)
- [Sociodemographic and Lifestyle Factors of Dietary Supplements in a Korean Population — NCBI](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3900841/)
- [노인성 만성질환 연구의 새로운 패러다임 및 정책제언 — KHIDI](https://www.khidi.or.kr/kohes/fileDownload?titleId=159289&fileId=1&fileDownType=C&paramMenuId=MENU01435)
- [질병관리청 보도자료](https://www.kdca.go.kr/kdca/2848/subview.do)

---

## 부록 — 페르소나 매핑 다이어그램 (텍스트)

```
                    B형 김건강 (52세, 만성질환)
                    ┌────────────────────────┐
                    │  당뇨, 고지혈증, 고혈압 │
                    └────────────┬───────────┘
                                 │
                ┌────────────────┼────────────────┐
                │                │                │
        심혈관 보호      혈당·지질 관리      간·신장 보호
                │                │                │
   ┌────────────┼─────┐    ┌─────┴────┐    ┌─────┴─────┐
   │            │     │    │          │    │           │
오메가3   코엔자임Q10  마그네슘  강황_커큐민  식이섬유  밀크씨슬_간
   │       (CoQ10)        │       (커큐민)              │
혈관_낫토_                                          (스타틴 부작용
폴리코사놀                                           완화 동반)

                    A형 박직장 (38세, 예방)
                    ┌────────────────────────┐
                    │  과로, 영양 결핍 예방   │
                    └────────────┬───────────┘
                                 │
            ┌────────────────────┼────────────────────┐
            │                    │                    │
     일반 영양 보충         피로 회복           면역 강화
            │                    │                    │
멀티비타민, 종합영양제, 비타민B, 비타민C, 유산균_프로바이오틱
            등                   카페인_각성          
                                 (단, B형 회피)        
```

---

**보고서 끝.** 다음 단계: Phase 1 구현 (옵션 C + D) → Phase 2 구현 (옵션 A + B).
