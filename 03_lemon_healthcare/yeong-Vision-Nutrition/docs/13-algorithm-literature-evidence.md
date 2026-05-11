# 13. 알고리즘 논문·공식 근거 검토

> **문서 정보**
> 버전: v1.0 | 작성일: 2026-05-11 | 상태: 구현 전 근거 보강 | 작성자: 경북대학교 AI/빅데이터 전문가 양성 과정 — TBD팀

---

## 1. 목적

현재 프로젝트의 BMI, 활동점수, BMR/TDEE, 체중 예측, 영양소 진단, 목적별 분석, 식단 인식 알고리즘을 논문·공식 자료 기준으로 점검한다. 이 문서는 구현자가 어떤 수식은 그대로 코드화해도 되는지, 어떤 계수는 제품 가정으로 남겨 검증해야 하는지 구분하기 위해 작성한다.

---

## 2. 근거 수준

| 수준 | 의미 | 구현 원칙 |
|------|------|----------|
| A | 논문·공식 기준에서 직접 확인되는 수식 또는 기준값 | 코드 상수화 가능. 출처 URL을 docstring 또는 주석에 남긴다. |
| B | 임상·역학 근거가 방향성을 지지하지만 프로젝트 계수까지 직접 보장하지는 않음 | 기본 로직으로 사용할 수 있으나, 계수는 설정값으로 분리하고 검증 로그를 남긴다. |
| C | 제품 UX 또는 팀 가정에 가까운 휴리스틱 | 의료·영양 자문 전까지 진단·치료 표현 금지. 테스트는 계산 재현용으로 제한한다. |

---

## 3. 알고리즘별 보강 결과

| 알고리즘 | 현재 구현 방향 | 확인 근거 | 보강·주의 사항 |
|----------|---------------|----------|---------------|
| BMI 분류 | 한국·아시아 기준 BMI 구간 사용 | WHO Expert Consultation은 아시아 인구에서 BMI 23.0, 27.5 등을 공중보건 action point로 제시한다. | 현재 23.0 이상 과체중, 25.0 이상 비만 분류는 한국·아시아 서비스에 적합하다. 다만 BMI는 체지방률·근육량을 직접 측정하지 않는다. |
| v1 권장 걸음수 | 8,000보 기준에 성별·나이·BMI 계수 적용 | Paluch et al. 2022는 60세 이상 6,000~8,000보, 60세 미만 8,000~10,000보 부근까지 사망 위험 감소가 관찰된다고 보고했다. | 8,000보 기준은 방향성이 타당하다. 성별·나이·BMI 계수는 논문에서 직접 제시된 값이 아니므로 프로젝트 계수로 표시하고 베타 데이터로 보정한다. |
| v2 심박 가중 | HRmax 기반 목표 심박 50~70%, 30분 기준 | Tanaka et al. 2001은 HRmax 추정식으로 `208 - 0.7 * age`를 제안했다. HHS/CDC는 중등도 유산소 활동 권고를 제시한다. | 기존 가이드 테스트와 호환되는 `220 - age`를 기본값으로 유지하되, Phase 2부터 `tanaka_2001` 옵션을 추가한다. 심박 점수는 운동 질 지표이지 의료 판단값이 아니다. |
| v3 백분위 보너스 | 같은 성별·연령대 그룹 내 순위 보너스 | 직접적인 의료 효과 근거보다는 행동 유도 UX 로직에 가깝다. | 최소 표본 30명은 데모 기준으로 유지하되, 실제 서비스에서는 개인정보 보호, 동점 처리, 그룹 크기 부족 시 비활성화 정책이 필요하다. |
| v4 만성질환 가중 | 질환별 활동점수 가산 | HHS/CDC는 만성질환자도 가능한 범위에서 신체활동을 권장하고 건강상 이점을 제시한다. | 질환별 `+0.10`, `+0.15`는 임상 효과 크기가 아니라 프로젝트 우선순위 계수다. 법무·의료 자문 전에는 출시 점수로 사용하지 않는다. |
| BMR | Mifflin-St Jeor 공식 | Mifflin et al. 1990은 건강한 성인의 REE 예측식을 제시했다. | 수식 자체는 수준 A. 단, 개인별 오차가 있으므로 "예측값"으로 표기하고, 체성분 측정값이 있으면 대체 공식을 선택할 수 있게 한다. |
| TDEE | BMR에 걸음수 기반 활동계수 적용 | 활동계수 표는 Mifflin 논문에서 직접 제시된 공식이 아니다. | 활동계수는 수준 C 휴리스틱으로 분리한다. 앱 로그와 실제 체중 변화로 보정 가능한 설정값이어야 한다. |
| 7-step 체중 예측 | 누적 kcal / 7,700, 감량·증량 보정 | Wishnofsky 1958의 3,500 kcal/lb 규칙이 정적 근거다. Hall et al. 2011은 장기 체중 변화에는 동적 모델이 필요하다고 설명한다. | 1~4주 단기 예측 또는 데모용으로 제한한다. 1개월 이상은 Hall 동적 모델을 기본 후보로 둔다. `0.85`, `0.95` 보정계수는 검증 전 프로젝트 계수다. |
| Hall 동적 모델 | FM/FFM 분리, 대사 적응 반영 | Hall et al. 2011, Deurenberg et al. 1991, Forbes 2000 근거를 사용한다. | 현재 문서의 Hall 모델은 학생 프로젝트용 단순화 버전이다. 논문 풀 모델 재현 테스트는 별도 검증 태스크로 둔다. |
| KDRIs 룩업 | 성별·연령·임신/수유 상태별 기준 조회 | 보건복지부·한국영양학회 KDRIs 자료와 National Academies DRI 정의를 참조한다. | KDRIs는 건강한 집단의 기준이다. 질환자 치료 용량이나 개인 진단 기준으로 쓰면 안 된다. |
| 부족 영양소 진단 | 섭취량 / 기준값 비율로 상태 분류 | DRI는 EAR/RDA/AI/UL 해석 틀을 제공한다. | `35%`, `70%`, `130%`는 공식 진단 cutoff가 아니라 UX 분류 기준이다. 화면에는 "부족 가능성"처럼 완화 표현을 사용한다. |
| 목적별 분석 | 눈건강·간기능·피로회복 등 목표별 영양소 매트릭스 | 식품안전나라·식약처 기능성 원료 정보와 AREDS2, 비타민 D, 오메가-3 관련 논문을 참조한다. | 사용자 화면 문구는 식약처 인정 문구를 우선 사용한다. 비타민 D와 감염 예방처럼 최신 근거가 혼재된 영역은 "면역 기능 유지에 필요" 수준으로 제한한다. 질병 예방·치료, 효과 보장 표현은 금지한다. |
| 식단 이미지/텍스트 인식 | Ollama 로컬 LLM + 식품성분 DB 매칭 | AI Hub 음식 이미지 데이터, Food-101, 이미지 기반 식이평가 systematic review를 참조한다. | 이미지 1장만으로 양·열량을 확정하지 않는다. 음식명·분량·매칭 결과는 사용자 확인 단계를 거친다. |
| LLM 구조화 출력 | Ollama 로컬 Structured Outputs | Ollama 공식 문서는 `format`에 JSON 또는 JSON Schema를 전달하는 구조화 출력을 설명한다. | 환자 개인정보가 포함될 수 있으므로 기본 경로는 로컬 Ollama만 허용한다. 클라우드 LLM은 비식별 테스트 또는 승인된 환경에서만 사용한다. |

---

## 4. 구현 보강 원칙

1. `EvidenceLevel`을 문서와 코드 주석에 반영한다.
   - A: 공식 수식 또는 기준값
   - B: 방향성 근거 있음, 계수는 프로젝트 설정값
   - C: 제품 UX 휴리스틱

2. 보정계수는 하드코딩보다 설정값으로 분리한다.
   - `SEX_FACTORS`, `BMI_FACTORS`, `DISEASE_WEIGHTS`, `LOSS_CORRECTION`, `GAIN_CORRECTION`은 의료·영양 자문과 베타 데이터로 변경될 수 있다.

3. 사용자에게 보이는 문구는 진단 표현을 피한다.
   - 사용 가능: "부족 가능성", "섭취량 확인 필요", "전문가 상담 권장"
   - 금지: "결핍 진단", "질병 예방", "치료 효과", "완치"

4. 식단 인식 결과는 항상 사용자 확인을 요구한다.
   - 모델 출력은 `recognized`, `matched`, `user_confirmed` 상태를 분리한다.
   - 분량 추정에는 confidence와 수정 UI를 제공한다.

5. 테스트는 두 종류로 분리한다.
   - 가이드 재현 테스트: 회사 PPTX 계산 예시와 동일한지 확인
   - 근거 기반 테스트: Tanaka HRmax, Hall 동적 모델, KDRIs/DRI 해석 등 논문 기반 로직 확인

---

## 5. 주요 출처

### 활동·체성분·대사

- WHO Expert Consultation. Appropriate body-mass index for Asian populations and its implications for policy and intervention strategies. The Lancet. 2004. https://pubmed.ncbi.nlm.nih.gov/14726171/
- Paluch AE, et al. Daily steps and all-cause mortality: a meta-analysis of 15 international cohorts. The Lancet Public Health. 2022. https://pubmed.ncbi.nlm.nih.gov/35247352/
- Lee IM, et al. Association of Step Volume and Intensity With All-Cause Mortality in Older Women. JAMA Internal Medicine. 2019. https://pubmed.ncbi.nlm.nih.gov/31141585/
- Tanaka H, Monahan KD, Seals DR. Age-predicted maximal heart rate revisited. Journal of the American College of Cardiology. 2001. https://pubmed.ncbi.nlm.nih.gov/11153730/
- U.S. Department of Health and Human Services. Physical Activity Guidelines for Americans, 2nd edition. 2018. https://odphp.health.gov/healthypeople/tools-action/browse-evidence-based-resources/physical-activity-guidelines-americans-2nd-edition
- CDC. Physical activity for adults with chronic health conditions and disabilities. https://www.cdc.gov/physical-activity-basics/guidelines/chronic-health-conditions-and-disabilities.html
- Mifflin MD, et al. A new predictive equation for resting energy expenditure in healthy individuals. American Journal of Clinical Nutrition. 1990. https://pubmed.ncbi.nlm.nih.gov/2305711/
- Wishnofsky M. Caloric equivalents of gained or lost weight. American Journal of Clinical Nutrition. 1958. https://pubmed.ncbi.nlm.nih.gov/13594881/
- Hall KD, et al. Quantification of the effect of energy imbalance on bodyweight. The Lancet. 2011. https://stacks.cdc.gov/view/cdc/33652
- Deurenberg P, Weststrate JA, Seidell JC. Body mass index as a measure of body fatness: age- and sex-specific prediction formulas. British Journal of Nutrition. 1991. https://pubmed.ncbi.nlm.nih.gov/2043597/
- Forbes GB. Body fat content influences the body composition response to nutrition and exercise. Annals of the New York Academy of Sciences. 2000. https://pubmed.ncbi.nlm.nih.gov/10865771/

### 영양 기준·기능성 원료

- 보건복지부. 2020 한국인 영양소 섭취기준 활용자료 발표. https://eiec.kdi.re.kr/policy/materialView.do?num=223213
- Hwang JY, et al. 2020 한국인 영양소 섭취기준 활용 자료 개발. Journal of Nutrition and Health. 2022. https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART002817751
- National Academies. Dietary Reference Intakes: Applications in Dietary Assessment. https://www.ncbi.nlm.nih.gov/books/NBK222890/
- National Academies. What are Dietary Reference Intakes? https://www.ncbi.nlm.nih.gov/books/NBK45182/
- 식품안전나라. 루테인/지아잔틴복합추출물 원료별 정보. https://www.foodsafetykorea.go.kr/portal/board/boardDetail.do?bbs_no=bbs987&menu_grp=MENU_NEW01&menu_no=2660&ntctxt_no=21540
- 식품안전나라. 루테인지아잔틴추출복합물 원료별 정보. https://www.foodsafetykorea.go.kr/portal/board/boardDetail.do?ans_yn=N&bbs_no=bbs987&bbs_type_cd=01&menu_grp=MENU_NEW01&menu_no=2660&ntctxt_no=1097691&nticmatr_yn=N
- AREDS2 Research Group. Lutein + zeaxanthin and omega-3 fatty acids for age-related macular degeneration. JAMA. 2013. https://pubmed.ncbi.nlm.nih.gov/23644932/
- Martineau AR, et al. Vitamin D supplementation to prevent acute respiratory tract infections. BMJ. 2017. https://www.bmj.com/content/356/bmj.i6583.abstract
- Jolliffe DA, et al. Vitamin D supplementation to prevent acute respiratory infections: systematic review and meta-analysis of stratified aggregate data. The Lancet Diabetes & Endocrinology. 2025. https://pubmed.ncbi.nlm.nih.gov/39993397/
- Bernasconi AA, et al. Effect of Omega-3 Dosage on Cardiovascular Outcomes. Mayo Clinic Proceedings. 2021. https://pubmed.ncbi.nlm.nih.gov/32951855/

### 식단 인식·로컬 LLM

- AI Hub. 음식 이미지 및 영양정보 텍스트 데이터. https://aihub.or.kr/aihubdata/data/view.do?dataSetSn=74
- AI Hub. 한국 이미지(음식) 데이터. https://www.aihub.or.kr/aihubdata/data/view.do?aihubDataSe=&currMenu=&dataSetSn=79&topMenu=
- Bossard L, Guillaumin M, Van Gool L. Food-101. ECCV. 2014. https://data.vision.ee.ethz.ch/cvl/datasets_extra/food-101/
- Dalakleidi K, et al. Applying Image-Based Food-Recognition Systems on Dietary Assessment: A Systematic Review. Advances in Nutrition. 2022. https://pubmed.ncbi.nlm.nih.gov/35803496/
- Lo FPW, et al. Image-Based Food Classification and Volume Estimation for Dietary Assessment: A Review. IEEE Journal of Biomedical and Health Informatics. 2020. https://pubmed.ncbi.nlm.nih.gov/32365038/
- Ollama official documentation. Structured Outputs. https://docs.ollama.com/capabilities/structured-outputs
- Ollama official documentation. Chat API. https://docs.ollama.com/api/chat
