# 26. 알고리즘 수정 근거와 논문 참고 이유

> 문서 정보
> 버전: v1.0
> 작성일: 2026-05-12
> 기준 코드 범위: `backend/src/algorithms`, `backend/src/prediction`, `backend/src/nutrition`, `backend/src/services`, `backend/src/llm`
> 목적: 현재 구현된 알고리즘을 왜 해당 논문과 공식 기준을 참고해 수정했는지 팀 리뷰용으로 정리한다.

---

## 1. 요약

이번 알고리즘 수정의 핵심은 "논문으로 직접 근거가 있는 공식"과 "제품 구현을 위한 휴리스틱"을 분리한 것이다. BMI, BMR, HRmax, 정적 체중 변화, KDRIs/DRI 해석처럼 논문 또는 공식 기준이 직접 존재하는 부분은 코드에 명확히 반영했다. 반대로 성별/나이/BMI 걸음수 계수, 만성질환 점수 가중치, 영양소 상태 분류 임계값, 영양제 매칭 점수 가중치처럼 논문이 직접 보장하지 않는 값은 프로젝트 계수로 남기고 운영 검증 대상으로 표시했다.

현재 구현은 의료 진단, 치료, 처방, 복용량 변경 안내가 아니라 건강관리 참고 정보를 만드는 방향이다. 그래서 알고리즘 출력 문구도 "진단"이 아니라 "부족 가능성", "섭취량 확인", "전문가 상담 권장"처럼 안전한 표현으로 제한했다.

---

## 2. 수정 원칙

| 원칙 | 적용 이유 | 구현 반영 |
| --- | --- | --- |
| 논문 공식과 제품 계수 분리 | 논문이 특정 수식은 지지해도 앱의 모든 점수 가중치를 보장하지는 않는다. | 상수명과 알고리즘 버전으로 추적하고, 휴리스틱은 추후 설정값 분리 대상으로 둔다. |
| 한국 사용자 기준 우선 | BMI와 영양 기준은 서구 범용 기준보다 한국/아시아 기준이 서비스 대상과 더 맞다. | 한국/아시아 BMI cutoff, KDRIs 기반 룩업을 사용한다. |
| 단기 예측과 장기 예측 분리 | 정적 kcal/kg 모델은 장기 대사 적응을 반영하지 못한다. | 90일 이상 예측에 동적 모델 검토 경고를 추가했다. |
| 민감정보 보호 | OCR 원문과 건강정보가 외부 LLM으로 전송되면 개인정보 위험이 커진다. | Ollama localhost 구조화 파서를 기본으로 두고, OCR 원문은 raw 저장 대신 HMAC hash로 추적한다. |
| 결과 저장 가능성 | API 결과가 나중에 재현되어야 한다. | `algorithm_version`, `kdris_source_manifest_version`, 입력/결과 snapshot 저장 구조를 사용한다. |

---

## 3. 알고리즘별 수정 근거

### 3.1 BMI 분류

**현재 코드**

- `backend/src/algorithms/bmi.py`
- `UNDERWEIGHT_CUTOFF=18.5`
- `OVERWEIGHT_CUTOFF=23.0`
- `OBESE_1_CUTOFF=25.0`
- `OBESE_2_CUTOFF=30.0`

**참고한 논문과 이유**

WHO Expert Consultation의 Lancet 논문은 아시아 인구에서 BMI와 건강위험의 관계가 유럽 인구와 다르게 나타날 수 있고, 공중보건 action point로 23.0 등을 제시한다. 이 프로젝트는 한국 사용자를 대상으로 하므로 서구식 `25 이상 과체중`만 쓰는 것보다 `23 이상 과체중` 기준이 서비스 맥락에 더 맞다.

**수정한 이유**

기존 설명만으로는 BMI가 "진단"처럼 오해될 가능성이 있었다. 그래서 구현에서는 한국/아시아 cutoff를 유지하되, 문서에서는 BMI가 체지방률, 근육량, 질환을 직접 판정하지 않는 스크리닝 지표임을 분리했다.

**적용 방안**

- UI 표기는 "BMI 기준 분류"로 제한한다.
- "비만 진단", "질환 위험 확정" 같은 표현은 사용하지 않는다.
- 향후 체성분 데이터가 들어오면 BMI 단독 판단이 아니라 체지방률/근육량 보조 지표로 확장한다.

**출처**

- WHO Expert Consultation. Appropriate body-mass index for Asian populations and its implications for policy and intervention strategies. The Lancet. 2004. https://pubmed.ncbi.nlm.nih.gov/14726171/
- ScienceDirect article page. https://www.sciencedirect.com/science/article/pii/S0140673603152683

---

### 3.2 활동점수 v1: 권장 걸음수와 기본 점수

**현재 코드**

- `backend/src/algorithms/activity.py`
- `BASE_STEPS=8000`
- 성별, 나이, BMI 계수 적용
- 달성률은 `1.2`에서 cap 처리

**참고한 논문과 이유**

Paluch et al. 2022 메타분석은 10,000보가 절대 기준이 아니며, 연령에 따라 사망위험 감소가 완만해지는 걸음수 범위가 다를 수 있음을 보여준다. 이 근거는 앱의 기본 목표를 과도한 10,000보로 고정하지 않고 8,000보 중심으로 두는 방향을 지지한다.

Lee et al. 2019는 고령 여성 집단에서 step volume과 사망률의 관련성을 분석했다. 이 근거는 60세 이상 사용자에게 동일한 고강도 목표를 강제하지 않고 나이 계수를 두는 방향을 설명하는 데 사용했다.

**수정한 이유**

논문은 8,000보 전후의 방향성은 지지하지만, 현재 코드의 성별계수 `0.95`, 나이계수 `0.9/0.8`, BMI계수 `0.9~1.15`를 직접 제시하지 않는다. 따라서 해당 계수는 논문 기반 공식이 아니라 회사 가이드 재현 및 제품 휴리스틱으로 분류했다.

**적용 방안**

- `BASE_STEPS=8000`은 유지한다.
- 성별/나이/BMI 계수는 `EvidenceLevel.C` 성격으로 문서화한다.
- 실제 사용자 데이터가 쌓이면 계수 변경 전후의 점수 분포, 이탈률, 건강행동 지속률을 비교한다.
- 걸음수 목표는 "건강 행동 목표"이지 질환 개선 효과 보장값이 아니다.

**출처**

- Paluch AE, et al. Daily steps and all-cause mortality: a meta-analysis of 15 international cohorts. The Lancet Public Health. 2022. https://www.sciencedirect.com/science/article/pii/S2468266721003029
- PubMed record. https://pubmed.ncbi.nlm.nih.gov/35247352/
- Lee IM, et al. Association of Step Volume and Intensity With All-Cause Mortality in Older Women. JAMA Internal Medicine. 2019. https://pubmed.ncbi.nlm.nih.gov/31141585/

---

### 3.3 활동점수 v2: 심박수 가중과 HRmax 공식

**현재 코드**

- `backend/src/algorithms/activity.py`
- 기본 HRmax: `220 - age`
- 대안 HRmax: `208 - 0.7 * age`
- 목표 심박 구간: HRmax의 `50%~70%`
- 목표 심박 30분이면 full credit
- 웨어러블 미연동 시 `NO_WEARABLE_HR_FACTOR=0.7`

**참고한 논문과 이유**

Tanaka et al. 2001은 `208 - 0.7 * age` 형태의 HRmax 추정식을 제안한다. 기존 `220 - age`는 널리 쓰이는 간단한 경험식이지만 개인차와 연령대별 오차가 있을 수 있으므로, 논문 기반 선택지를 함께 제공하는 것이 더 안전하다.

AHA와 CDC/HHS 계열 가이드는 신체활동 강도와 심박수/중등도 활동 해석의 기준으로 참고했다. 특히 `50%~70%`는 중등도 활동 구간 설명에 사용된다.

**수정한 이유**

회사 가이드 예시와 기존 테스트를 깨지 않기 위해 기본값은 `guide_220_age`로 유지했다. 대신 `tanaka_2001` 옵션을 추가해 근거 기반 계산을 선택할 수 있게 했다. 이 방식은 기존 산출물 재현성과 논문 근거 보강을 동시에 만족한다.

**적용 방안**

- API 요청에서 `hrmax_formula`를 명시적으로 받는다.
- 기본은 가이드 호환식, 향후 운영 기본값은 `tanaka_2001` 전환을 검토한다.
- 베타 테스트에서는 두 공식의 심박 구간 차이와 사용자 운동 기록 적합성을 비교한다.
- 심박 점수는 운동 강도 참고값이며 의료적 운동 처방으로 표시하지 않는다.

**출처**

- Tanaka H, Monahan KD, Seals DR. Age-predicted maximal heart rate revisited. Journal of the American College of Cardiology. 2001. https://pubmed.ncbi.nlm.nih.gov/11153730/
- American Heart Association. Target Heart Rates Chart. https://www.heart.org/en/healthy-living/fitness/fitness-basics/target-heart-rates
- CDC. How to Measure Physical Activity Intensity. https://www.cdc.gov/physical-activity-basics/measuring/index.html

---

### 3.4 활동점수 v3: 백분위 보너스

**현재 코드**

- `backend/src/algorithms/activity.py`
- 최소 비교군 표본 수: `30`
- 상위 10%, 20%, 30% 구간별 보너스
- 표본이 부족하면 보너스 `0`

**참고한 논문과 이유**

이 부분은 현재 직접 참조한 의학 논문 공식이 없다. 백분위 보너스는 행동 유도와 동기부여를 위한 제품 UX 로직이다.

**수정한 이유**

표본이 적을 때 순위 점수를 계산하면 개인정보 노출과 점수 불안정 문제가 생긴다. 그래서 최소 표본 수를 두고, 표본 부족 시 보너스를 비활성화했다.

**적용 방안**

- 비교군은 성별, 연령대, 선택적으로 BMI 구간처럼 충분히 큰 그룹으로만 구성한다.
- 그룹 크기가 작으면 순위 또는 percentile을 노출하지 않는다.
- 실제 운영에서는 k-anonymity 기준과 동점 처리 정책을 추가한다.

**출처**

- 현재 v3 백분위 보너스는 논문 공식이 아니라 제품 휴리스틱이다. 따라서 별도 논문 성과나 의학적 효과를 주장하지 않는다.

---

### 3.5 활동점수 v4: 만성질환 가중치

**현재 코드**

- `backend/src/algorithms/activity.py`
- 질환 코드별 `0.10` 또는 `0.15` 가중
- 최대 multiplier `1.3`

**참고한 공식 기준과 이유**

CDC와 HHS 신체활동 가이드는 만성질환자도 가능한 범위에서 신체활동의 이점을 얻을 수 있다고 설명한다. 다만 현재 코드의 질환별 가중치 숫자 자체가 해당 문서에서 나온 것은 아니다.

**수정한 이유**

만성질환자를 활동에서 배제하지 않되, 질환별 점수 가중치가 치료 효과나 위험도 계산처럼 오해되지 않게 제한했다. 또한 최대 multiplier를 `1.3`으로 제한해 점수가 과도하게 커지는 문제를 막았다.

**적용 방안**

- 질환별 가중치는 제품 우선순위 계수로 표기한다.
- 질환 관련 안내에는 "전문가 상담", "개인 상태에 맞는 활동" 표현을 사용한다.
- 특정 질환 개선 효과, 치료, 처방 대체 표현은 금지한다.

**출처**

- CDC. Chronic Conditions & Disabilities Activity. https://www.cdc.gov/physical-activity-basics/guidelines/chronic-health-conditions-and-disabilities.html
- HHS. Physical Activity Guidelines for Americans, 2nd edition. https://odphp.health.gov/healthypeople/tools-action/browse-evidence-based-resources/physical-activity-guidelines-americans-2nd-edition

---

### 3.6 BMR/TDEE 산출

**현재 코드**

- `backend/src/algorithms/metabolism.py`
- BMR: Mifflin-St Jeor 공식
- TDEE: BMR에 걸음수 기반 활동계수 적용

**참고한 논문과 이유**

Mifflin et al. 1990은 건강한 성인의 resting energy expenditure 예측식을 제시한다. 현재 구현의 계수 `10`, `6.25`, `5`, 남성 `+5`, 여성 `-161`은 이 공식과 직접 대응한다.

**수정한 이유**

BMR 공식은 논문 기반이지만 TDEE 활동계수 `1.2~1.9`는 현재 프로젝트에서 걸음수 구간에 맞춘 휴리스틱이다. 따라서 API와 문서에서 `estimated_bmr`, `estimated_tdee`처럼 예측값임을 드러내도록 했다.

**적용 방안**

- BMR은 논문 기반 수식으로 유지한다.
- TDEE 활동계수는 추후 `activity_factor_policy` 설정으로 분리한다.
- 사용자의 실제 체중 변화, 운동량, 식단 기록이 쌓이면 개인화 보정계수를 별도 모델로 둔다.

**출처**

- Mifflin MD, et al. A new predictive equation for resting energy expenditure in healthy individuals. American Journal of Clinical Nutrition. 1990. https://pubmed.ncbi.nlm.nih.gov/2305711/
- ScienceDirect article page. https://www.sciencedirect.com/science/article/pii/S0002916523166986

---

### 3.7 7-step 체중 예측과 장기 예측 경고

**현재 코드**

- `backend/src/prediction/weight.py`
- `KCAL_PER_KG_FAT=7700.0`
- 감량 보정 `LOSS_CORRECTION=0.85`
- 증량 보정 `GAIN_CORRECTION=0.95`
- `90`일 이상 예측 시 동적 모델 검토 경고

**참고한 논문과 이유**

Wishnofsky 1958은 체중 변화의 정적 에너지 등가 규칙과 연결된다. 그래서 짧은 기간의 설명 가능한 데모 모델로 `7700 kcal/kg`을 사용했다.

반대로 Hall et al. 2011은 장기 체중 변화가 단순 누적 열량만으로 설명되지 않고 에너지 소비 적응, 체성분, 시간 지연을 반영해야 한다고 설명한다. 따라서 장기 예측에서는 단순 7-step 모델을 그대로 확정값처럼 제공하면 안 된다.

Deurenberg et al. 1991과 Forbes 2000은 향후 Hall 계열 모델에서 초기 체지방률 추정 및 FM/FFM 변화 비율을 설계할 때 참고할 근거로 남겼다.

**수정한 이유**

초기 구현에서는 계산 재현성과 API 단순성이 필요하므로 7-step 모델을 유지했다. 대신 장기 예측에서 잘못된 확신을 주지 않기 위해 90일 이상에는 경고를 붙였다. `0.85`, `0.95` 보정값은 논문 공식이 아니라 현재 프로젝트 보정계수로 분류했다.

**적용 방안**

- 1~4주 수준의 단기 예측은 7-step 모델로 제공한다.
- 90일 이상 또는 목표 체중 시뮬레이션은 Hall 동적 모델로 분기한다.
- Hall 모델 구현 전까지 장기 결과는 "참고용" 경고를 유지한다.
- 보정계수는 실제 체중 로그 기반으로 검증하기 전까지 공식 효과값으로 설명하지 않는다.

**출처**

- Wishnofsky M. Caloric equivalents of gained or lost weight. American Journal of Clinical Nutrition. 1958. https://pubmed.ncbi.nlm.nih.gov/13594881/
- Hall KD, et al. Quantification of the effect of energy imbalance on bodyweight. The Lancet. 2011. https://stacks.cdc.gov/view/cdc/33652
- Deurenberg P, Weststrate JA, Seidell JC. Body mass index as a measure of body fatness. British Journal of Nutrition. 1991. https://pubmed.ncbi.nlm.nih.gov/2043597/
- Forbes GB. Body fat content influences the body composition response to nutrition and exercise. Annals of the New York Academy of Sciences. 2000. https://pubmed.ncbi.nlm.nih.gov/10865771/

---

### 3.8 KDRIs 룩업과 source manifest

**현재 코드**

- `backend/src/nutrition/kdris.py`
- `data/kdris/kdris_source_manifest.json`
- 기준값 우선순위: `RNI/RDA`, `AI`, `EER`, `EAR`, `CDRR`, `AMDR`, `UL`
- 연령은 월 단위로 비교 가능하게 보강
- `dataset_status`, `dataset_version`, `source_manifest_version` 반환

**참고한 공식 기준과 이유**

한국 사용자의 영양 기준은 KDRIs가 가장 직접적인 공식 기준이다. 2025 KDRIs가 현재 공식 기준으로 발표되었고, 한국영양학회 페이지에는 2026-03-16 정오표 적용 정보가 확인된다. 다만 현재 로컬 CSV는 운영 공식 테이블이 아니라 2020 sample fixture와 2025 digitization pending 후보를 포함한다.

National Academies DRI 자료는 EAR, RDA, AI, UL의 의미와 개인/집단 평가에서의 해석 차이를 설명하므로, KDRIs 값을 앱에서 어떻게 조심스럽게 사용할지 결정하는 데 필요하다.

**수정한 이유**

단순 CSV 조회만 있으면 어떤 기준값을 사용했는지 사후 재현이 어렵다. 그래서 source manifest를 추가해 데이터셋 버전, 정오표 버전, 검수 상태, production gate를 추적하도록 수정했다.

**적용 방안**

- 운영 전에는 2025 KDRIs 공식 자료를 허용된 방식으로 디지털화하고, row별 source page/table/cell을 기록한다.
- `review_status`가 승인되지 않은 row는 production에서 차단한다.
- 저장 API에는 `kdris_source_manifest_version`을 함께 저장한다.
- KDRIs는 건강한 집단 기준이므로 질환자 치료 용량으로 사용하지 않는다.

**출처**

- 보건복지부. 2025 한국인 영양소 섭취기준 보도자료. https://www.korea.kr/briefing/pressReleaseView.do?newsId=156737581
- 한국영양학회. 2025 KDRI 공개자료 및 정오표 안내. https://kns.or.kr/fileroom/fileroom_view.asp?BoardID=Kdr&idx=167
- 보건복지부. 2020 한국인 영양소 섭취기준 배포. https://www.mohw.go.kr/board.es?act=view&bid=0019&list_no=362385&mid=a10411010100
- National Academies. Dietary Reference Intakes: Applications in Dietary Assessment. https://www.ncbi.nlm.nih.gov/books/NBK222890/
- National Academies. What are Dietary Reference Intakes? https://www.ncbi.nlm.nih.gov/books/NBK45182/

---

### 3.9 부족 영양소 상태 분류

**현재 코드**

- `backend/src/nutrition/deficiency_analysis.py`
- `DEFICIENT_THRESHOLD=0.35`
- `LOW_THRESHOLD=0.70`
- `EXCESSIVE_THRESHOLD=1.30`
- UL 초과 시 `RISKY`
- 사용자 문구 금지어 검사: `진단`, `치료`, `처방`, `복용량 변경`

**참고한 공식 기준과 이유**

DRI/KDRIs는 RDA, AI, UL 같은 기준값의 의미를 제공한다. 특히 UL은 상한 섭취량을 넘을 때 위해 가능성을 경고하는 기준으로 사용할 수 있다.

**수정한 이유**

`35%`, `70%`, `130%`는 공식 결핍 진단 cutoff가 아니다. 그래서 결과명을 "deficient"라고 내부 enum에 두더라도 사용자 메시지는 "부족 가능성", "섭취량 확인 필요"처럼 완화했다. 또한 금지어 검사를 추가해 저장된 메시지 또는 노출 문구가 의료행위처럼 보이지 않게 했다.

**적용 방안**

- 현재 threshold는 MVP 분류용 휴리스틱으로 유지한다.
- 운영 전에는 영양사/의료 자문을 통해 영양소별 개별 threshold 또는 EAR 기반 확률 접근을 검토한다.
- UL 초과는 "위험 가능성"과 전문가 상담 권고로 제한한다.
- 부족 영양소 우선순위는 낮은 ratio 순으로 정렬하지만, 진단 순위처럼 표현하지 않는다.

**출처**

- National Academies. Dietary Reference Intakes: Applications in Dietary Assessment. https://www.ncbi.nlm.nih.gov/books/NBK222890/
- National Academies. What are Dietary Reference Intakes? https://www.ncbi.nlm.nih.gov/books/NBK45182/

---

### 3.10 영양소 단위 환산

**현재 코드**

- `backend/src/nutrition/unit_converter.py`
- g, mg, ug 상호 환산
- vitamin D 한정 `1 IU = 0.025 ug`

**참고한 기준과 이유**

영양제 라벨은 `mg`, `ug`, `IU`가 혼재된다. 같은 영양소를 KDRIs 기준 단위와 비교하려면 단위 환산이 먼저 필요하다. 단, IU는 영양소별 의미가 다르므로 범용 변환으로 처리하지 않고 vitamin D에만 제한했다.

**수정한 이유**

모든 IU를 동일하게 환산하면 비타민 A, 비타민 D, 비타민 E 등에서 잘못된 결과가 나올 수 있다. 그래서 현재 구현은 vitamin D에만 명시적으로 허용하고, 나머지는 `UnitConversionError`로 실패하게 했다.

**적용 방안**

- IU 환산은 영양소별 conversion table을 공식 출처와 함께 확장한다.
- 변환 불가 값은 조용히 추정하지 않고 API validation error로 반환한다.
- 사용자 확인 전에는 영양제 총량 분석에 반영하지 않는다.

**출처**

- NIH Office of Dietary Supplements. Vitamin D Fact Sheet. https://ods.od.nih.gov/factsheets/VitaminD-HealthProfessional/

---

### 3.11 Ollama 구조화 파서와 영양제 OCR 파싱

**현재 코드**

- `backend/src/llm/ollama.py`
- `backend/src/services/supplement_parser.py`
- Ollama `/api/chat` 사용
- `format`에 Pydantic JSON Schema 전달
- `temperature` 설정
- localhost가 아니면 차단 가능
- OCR 원문 raw 저장 대신 HMAC-SHA256 hash 저장

**참고한 공식 문서와 이유**

이 부분은 의학 논문 기반 알고리즘이 아니라 개인정보 보호와 구조화 출력 안정성을 위한 엔지니어링 설계다. Ollama 공식 문서는 Chat API의 `format` 필드에 `json` 또는 JSON Schema를 전달할 수 있다고 설명한다. 또한 structured outputs 문서는 Pydantic schema를 `format`에 전달하고 응답을 다시 검증하는 흐름을 제시한다.

**수정한 이유**

기존 외부 LLM 중심 설계는 OCR 원문과 건강정보가 외부 서버로 전송될 수 있다. 실제 사용자 앱을 전제로 하면 기본 경로는 local LLM이어야 하므로 Ollama localhost만 허용하는 구조로 수정했다. 또한 모델 출력은 신뢰하지 않고 Pydantic 검증을 통과해야만 저장한다.

**적용 방안**

- `ALLOW_EXTERNAL_LLM=false`일 때 `127.0.0.1`, `localhost`, `::1`만 허용한다.
- OCR 텍스트는 정규화 후 HMAC hash만 저장한다.
- 파서 결과는 `requires_confirmation` 상태로 저장하고, 사용자가 확인하기 전에는 영양제 등록값으로 확정하지 않는다.
- 모델 prompt에는 OCR 블록을 "명령"이 아니라 "데이터"로 취급하도록 명시한다.

**출처**

- Ollama Structured Outputs. https://docs.ollama.com/capabilities/structured-outputs
- Ollama Chat API. https://docs.ollama.com/api/chat
- Pydantic BaseModel API. https://docs.pydantic.dev/latest/api/base_model/

---

### 3.12 영양제 매칭 알고리즘

**현재 코드**

- `backend/src/services/supplement_matching.py`
- 제품명 similarity `72%`
- 제조사 similarity `18%`
- 성분 overlap `10%`
- 자동 매칭 threshold `0.92`
- 제품명 threshold `0.90`
- 후보 최대 `5`

**참고한 근거와 이유**

현재 매칭 점수 가중치는 논문 공식이 아니라 MVP용 deterministic matching 휴리스틱이다. 영양제 제품명, 제조사, 성분 후보를 보수적으로 대조하기 위한 설계이며, 자동 확정 기준을 높게 잡아 잘못된 제품 매칭 위험을 줄이는 것이 목적이다.

**수정한 이유**

LLM 또는 OCR 결과만으로 제품을 확정하면 잘못된 제품, 잘못된 성분량, 잘못된 복용량이 저장될 수 있다. 그래서 자동 매칭 threshold를 높게 두고, 후보 목록과 source manifest version을 함께 반환해 사용자 확인과 감사 추적이 가능하게 했다.

**적용 방안**

- `AUTO_MATCH_THRESHOLD=0.92`는 운영 전 실제 제품 DB 샘플로 precision/recall을 측정한다.
- 자동 확정이 아니라 "후보 추천"을 기본 UX로 둔다.
- 성분명 synonym table과 식약처 제품/성분 DB를 연결한 뒤 threshold를 재검토한다.
- 복용량 변경 안내는 이 매칭 결과만으로 제공하지 않는다.

**출처**

- 현재 영양제 매칭 점수는 프로젝트 휴리스틱이다. 논문 기반 성능 수치나 공식 recommended threshold는 확인된 바 없으므로 문서에 성능값을 주장하지 않는다.

---

## 4. 왜 알고리즘을 이렇게 수정했는가

### 4.1 기존 가이드 재현성과 근거 기반 개선을 동시에 만족하기 위해

회사 가이드 계산 예시를 바로 깨면 구현 검증이 어려워진다. 그래서 `220 - age`, 8,000보 기준, 7-step 체중 예측처럼 기존 가이드와 연결된 계산은 유지했다. 대신 Tanaka HRmax, Hall 동적 모델, KDRIs source manifest 같은 근거 기반 개선점을 옵션 또는 다음 단계로 추가했다.

### 4.2 논문이 보장하지 않는 계수를 과학적 사실처럼 보이지 않게 하기 위해

성별/나이/BMI 걸음수 계수, 질환별 점수 가중치, 부족/낮음/과다 threshold, 영양제 매칭 가중치는 현재 논문 공식이 아니다. 따라서 코드에는 동작을 구현하되, 문서에서는 "프로젝트 계수" 또는 "휴리스틱"으로 명시했다. 이 구분이 없으면 팀원이 추후 발표나 서비스 문구에서 근거를 과장할 위험이 있다.

### 4.3 실제 사용자 앱의 개인정보와 의료 리스크를 줄이기 위해

OCR 텍스트, 영양제 라벨, 건강 데이터는 민감정보가 될 수 있다. 그래서 외부 LLM 전송을 기본 경로에서 배제하고, local Ollama + schema validation + user confirmation 구조로 수정했다. 또한 결과 문구에서 진단/치료/처방/복용량 변경 표현을 차단했다.

### 4.4 결과를 사후 재현할 수 있게 하기 위해

영양 기준과 알고리즘은 시간이 지나면서 바뀔 수 있다. 같은 입력이라도 KDRIs 버전, 정오표, 알고리즘 버전이 다르면 결과가 달라질 수 있다. 따라서 분석 결과 저장 구조에는 입력 snapshot, 결과 snapshot, 알고리즘 버전, KDRIs source manifest version을 남기는 방향으로 수정했다.

---

## 5. 현재 한계와 다음 수정 방안

| 영역 | 현재 한계 | 다음 방안 |
| --- | --- | --- |
| 걸음수 계수 | 성별/나이/BMI 계수는 논문 공식이 아니다. | 설정 파일로 분리하고 베타 데이터로 보정한다. |
| 심박수 | `220 - age` 기본값은 가이드 호환성이 크지만 개인차가 있다. | `tanaka_2001`을 운영 기본값으로 전환할지 비교 테스트한다. |
| TDEE | 걸음수 기반 활동계수는 간단하지만 운동 강도와 비운동 활동을 충분히 반영하지 못한다. | HealthKit/Health Connect의 운동, 심박, active energy 데이터를 추가한다. |
| 체중 예측 | 7-step은 장기 대사 적응을 반영하지 못한다. | Hall 동적 모델, FM/FFM 추정, 90일 이상 자동 분기를 구현한다. |
| KDRIs | 현재 로컬 운영 데이터는 sample fixture와 2025 후보 데이터가 섞여 있다. | 2025 KDRIs 공식 자료를 검수 완료한 production dataset으로 전환한다. |
| 부족 영양소 threshold | `35/70/130%`는 MVP 휴리스틱이다. | 영양소별 EAR/RDA/AI/UL 해석 정책과 전문가 자문을 반영한다. |
| 영양제 매칭 | similarity threshold는 실제 제품 DB에서 검증되지 않았다. | 식약처 제품 DB 샘플로 precision/recall을 측정하고 threshold를 재조정한다. |
| LLM 파서 | 구조화 출력이어도 OCR 오류와 모델 오추출 가능성이 있다. | OCR confidence, low confidence field, 사용자 확인 UI, audit log를 함께 운영한다. |

---

## 6. 팀 리뷰 체크리스트

- [ ] 논문 기반 공식과 프로젝트 휴리스틱이 문서와 코드에서 분리되어 있는가?
- [ ] 사용자 화면 문구가 진단, 치료, 처방, 복용량 변경으로 오해되지 않는가?
- [ ] `algorithm_version`과 `kdris_source_manifest_version`이 저장 API에 남는가?
- [ ] KDRIs row마다 source table/page/cell, reviewer, errata version을 추적하는가?
- [ ] 장기 체중 예측에서 7-step 결과를 확정 예측처럼 보여주지 않는가?
- [ ] OCR/LLM 결과가 사용자 확인 전 확정 데이터로 저장되지 않는가?
- [ ] 영양제 자동 매칭 threshold를 실제 reference DB로 검증했는가?

---

## 7. 출처 목록

### 논문

- WHO Expert Consultation. Appropriate body-mass index for Asian populations and its implications for policy and intervention strategies. The Lancet. 2004. https://pubmed.ncbi.nlm.nih.gov/14726171/
- Paluch AE, et al. Daily steps and all-cause mortality: a meta-analysis of 15 international cohorts. The Lancet Public Health. 2022. https://www.sciencedirect.com/science/article/pii/S2468266721003029
- Lee IM, et al. Association of Step Volume and Intensity With All-Cause Mortality in Older Women. JAMA Internal Medicine. 2019. https://pubmed.ncbi.nlm.nih.gov/31141585/
- Tanaka H, Monahan KD, Seals DR. Age-predicted maximal heart rate revisited. Journal of the American College of Cardiology. 2001. https://pubmed.ncbi.nlm.nih.gov/11153730/
- Mifflin MD, et al. A new predictive equation for resting energy expenditure in healthy individuals. American Journal of Clinical Nutrition. 1990. https://pubmed.ncbi.nlm.nih.gov/2305711/
- Wishnofsky M. Caloric equivalents of gained or lost weight. American Journal of Clinical Nutrition. 1958. https://pubmed.ncbi.nlm.nih.gov/13594881/
- Hall KD, et al. Quantification of the effect of energy imbalance on bodyweight. The Lancet. 2011. https://stacks.cdc.gov/view/cdc/33652
- Deurenberg P, Weststrate JA, Seidell JC. Body mass index as a measure of body fatness: age- and sex-specific prediction formulas. British Journal of Nutrition. 1991. https://pubmed.ncbi.nlm.nih.gov/2043597/
- Forbes GB. Body fat content influences the body composition response to nutrition and exercise. Annals of the New York Academy of Sciences. 2000. https://pubmed.ncbi.nlm.nih.gov/10865771/

### 공식 기준과 문서

- 보건복지부. 2025 한국인 영양소 섭취기준 보도자료. https://www.korea.kr/briefing/pressReleaseView.do?newsId=156737581
- 한국영양학회. 2025 KDRI 공개자료 및 정오표 안내. https://kns.or.kr/fileroom/fileroom_view.asp?BoardID=Kdr&idx=167
- 보건복지부. 2020 한국인 영양소 섭취기준 배포. https://www.mohw.go.kr/board.es?act=view&bid=0019&list_no=362385&mid=a10411010100
- National Academies. Dietary Reference Intakes: Applications in Dietary Assessment. https://www.ncbi.nlm.nih.gov/books/NBK222890/
- National Academies. What are Dietary Reference Intakes? https://www.ncbi.nlm.nih.gov/books/NBK45182/
- CDC. Chronic Conditions & Disabilities Activity. https://www.cdc.gov/physical-activity-basics/guidelines/chronic-health-conditions-and-disabilities.html
- CDC. How to Measure Physical Activity Intensity. https://www.cdc.gov/physical-activity-basics/measuring/index.html
- American Heart Association. Target Heart Rates Chart. https://www.heart.org/en/healthy-living/fitness/fitness-basics/target-heart-rates
- HHS. Physical Activity Guidelines for Americans, 2nd edition. https://odphp.health.gov/healthypeople/tools-action/browse-evidence-based-resources/physical-activity-guidelines-americans-2nd-edition
- NIH Office of Dietary Supplements. Vitamin D Fact Sheet. https://ods.od.nih.gov/factsheets/VitaminD-HealthProfessional/
- Ollama Structured Outputs. https://docs.ollama.com/capabilities/structured-outputs
- Ollama Chat API. https://docs.ollama.com/api/chat
- Pydantic BaseModel API. https://docs.pydantic.dev/latest/api/base_model/
