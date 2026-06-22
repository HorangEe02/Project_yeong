# 17. API 및 논문 근거 정리와 알고리즘 수정 방안

> 문서 정보
> 버전: v1.0
> 작성일: 2026-05-11
> 검증 범위: 현재 로컬 Markdown 문서 기준 + 외부 공식 문서 및 논문 링크 확인
> 상태: 구현 전 의사결정 근거 문서

---

## 1. 목적

이 문서는 Lemon Aid / Vision Nutrition 프로젝트에서 사용할 API, SDK, 데이터셋, 논문 근거를 한 곳에 정리한다. 목표는 세 가지다.

1. 어떤 API를 왜 쓰는지 명확히 한다.
2. 어떤 논문을 어떤 알고리즘 근거로 쓰는지 분리한다.
3. 기존 문서의 알고리즘을 그대로 구현하지 않고 일부 수정해야 하는 이유와 적용 방안을 설명한다.

주의: 이 문서는 기술 설계와 구현 근거 문서다. 의료 진단, 치료, 처방, 복용량 변경 지시를 목적으로 하지 않는다.

---

## 2. 핵심 결론

현재 구현 방향은 "로컬 LLM + 공식 공공데이터 + 사용자 확인 단계"를 기본 원칙으로 둔다.

| 구분 | 최종 판단 |
| --- | --- |
| LLM | Ollama Local API를 기본값으로 사용한다. 외부 LLM은 비식별 테스트 또는 승인된 환경에서만 사용한다. |
| OCR | Google Cloud Vision을 1차 OCR로 쓰고, Naver CLOVA OCR을 한국어 라벨/템플릿 백업으로 둔다. |
| 식품 영양 | 식약처 식품영양성분DB정보 API와 농진청 국가표준식품성분 DB를 병합한다. |
| 건강기능식품 | 식약처 건강기능식품정보, 건강기능식품 영양DB, 기능성 원료인정 현황을 제품/성분 매칭에 사용한다. |
| 모바일 헬스 | iOS는 HealthKit, Android는 Health Connect를 사용한다. Google Fit API 방향은 배제한다. |
| 병원 데이터 | 초기 구현은 mock FHIR와 수동 업로드로 제한한다. 실제 연동은 건강정보 고속도로 또는 병원 공식 API 이후로 둔다. |
| 알고리즘 | 논문으로 직접 확인되는 공식은 코드화하고, 프로젝트 계수는 설정값으로 분리한다. |

---

## 3. API 및 SDK 사용 근거

### 3.1 Ollama Local API

| 항목 | 내용 |
| --- | --- |
| 용도 | OCR 텍스트와 식단 텍스트를 구조화 JSON으로 파싱 |
| 사용 위치 | `LLMAdapter`, 영양제 라벨 파싱, 식단 텍스트 정규화 |
| 채택 이유 | 민감 건강정보와 OCR 원문을 외부 LLM 서버로 보내지 않기 위해 로컬 실행을 기본값으로 둔다. |
| 구현 방식 | `POST /api/chat`, `format`에 JSON 또는 JSON Schema 전달, Pydantic `model_json_schema()`와 `model_validate_json()`으로 재검증 |
| 수정 사유 | 기존 Claude/OpenAI 중심 설계는 개인정보 전송 위험이 있다. 로컬 Ollama로 기본 경로를 바꾸고 cloud 모델은 PHI 처리에서 차단한다. |

출처:
- Ollama API Introduction: https://docs.ollama.com/api
- Ollama Chat API: https://docs.ollama.com/api/chat
- Ollama Structured Outputs: https://docs.ollama.com/capabilities/structured-outputs
- Pydantic BaseModel API: https://docs.pydantic.dev/latest/api/base_model/

적용 방안:
- `ALLOW_EXTERNAL_LLM=false`를 기본값으로 둔다.
- `OLLAMA_BASE_URL=http://127.0.0.1:11434`를 개발 기본값으로 둔다.
- `qwen3.5:9b`, `gemma4:e4b`처럼 24GB 로컬 장비에서 실행 가능한 모델을 1차 후보로 둔다.
- `deepseek-v4-pro:cloud`처럼 cloud 표기가 붙은 모델은 민감정보 처리 경로에서 차단한다.

### 3.2 Google Cloud Vision API

| 항목 | 내용 |
| --- | --- |
| 용도 | 영양제 라벨, 처방전, 검사표 이미지의 텍스트 추출 |
| 사용 위치 | `OCRAdapter`, `GoogleVisionOCR`, OCR pipeline |
| 채택 이유 | 공식 OCR 기능이 있고, 일반 이미지용 `TEXT_DETECTION`과 문서/고밀도 텍스트용 `DOCUMENT_TEXT_DETECTION`을 구분해서 쓸 수 있다. |
| 수정 사유 | 영양제 라벨과 처방전/검사표는 텍스트가 조밀하므로 기본은 `DOCUMENT_TEXT_DETECTION` 후보로 둔다. 단, 일반 라벨 사진은 샘플 비교 후 선택한다. |

출처:
- Google Cloud Vision OCR: https://cloud.google.com/vision/docs/ocr

적용 방안:
- 이미지 전처리: EXIF 회전 보정, RGB 변환, 긴 변 제한, JPEG 재인코딩.
- OCR 결과는 원문, confidence, engine, elapsed_ms를 함께 저장한다.
- confidence가 낮거나 API 오류가 나면 CLOVA OCR로 폴백한다.
- 처방전/검사표처럼 구조화 문서가 많아지면 Google Document AI를 별도 후보로 검토한다. Cloud Vision 공식 문서도 스캔 문서와 form parsing에는 Document AI를 권장한다.

### 3.3 Naver CLOVA OCR

| 항목 | 내용 |
| --- | --- |
| 용도 | Google Vision 실패 또는 낮은 신뢰도 결과의 백업 OCR |
| 사용 위치 | `ClovaOCR`, OCR fallback |
| 채택 이유 | 한국어 문서 및 템플릿 기반 OCR에 강점이 있고, REST API 형태로 통합 가능하다. |
| 수정 사유 | 단일 OCR 엔진 의존도를 줄이고, 라벨/처방전/검사표 유형별 실패율을 비교하기 위해 Adapter 패턴으로 분리한다. |

출처:
- Naver Cloud CLOVA OCR API overview: https://api.ncloud-docs.com/docs/en/ai-application-service-ocr

적용 방안:
- API Gateway Invoke URL과 `X-OCR-SECRET`은 환경변수로만 관리한다.
- 로컬 문서 또는 저장소에 실제 키 값을 기록하지 않는다.
- OCR API별 결과를 동일한 `OCRResult` DTO로 정규화한다.

### 3.4 식약처 식품영양성분DB정보 API

| 항목 | 내용 |
| --- | --- |
| 용도 | 음식명 또는 식품코드를 영양성분으로 변환 |
| 사용 위치 | 식단 입력, 음식명 매칭, 영양소 합산 |
| 채택 이유 | 식약처가 제공하는 공식 식품 영양성분 DB이며 JSON/XML REST API를 제공한다. |
| 수정 사유 | 기존 문서의 일부 예시는 오래된 서비스 ID에 가깝다. 최신 구현 기준은 공공데이터포털 `15127578` 및 식품안전나라 `I2791`을 우선한다. |

출처:
- 공공데이터포털 식품영양성분DB정보: https://www.data.go.kr/data/15127578/openapi.do
- 식품안전나라 식품영양성분DB정보: https://www.foodsafetykorea.go.kr/api/newDatasetDetail.do?svc_no=I2791

적용 방안:
- 1차 매칭 키: 식품명, 식품분류, 제조사, 1회 제공량.
- API 응답은 원본 row와 normalized nutrient row를 분리 저장한다.
- Redis 캐싱을 적용해 반복 검색과 호출 제한 위험을 줄인다.
- 사용자가 확정하기 전에는 식단 이미지/텍스트 인식 결과를 섭취량 확정값으로 쓰지 않는다.

### 3.5 식약처 건강기능식품 관련 API

| API | 용도 | 출처 |
| --- | --- | --- |
| 건강기능식품정보 | 제품명, 업체명, 섭취량, 섭취방법 등 제품 기본 정보 조회 | https://www.data.go.kr/data/15056760/openapi.do |
| 건강기능식품 영양DB | 기능성 원료와 원료 분류 매칭 | https://www.data.go.kr/data/15085712/openapi.do |
| 건강기능식품 기능성 원료인정 현황 | 기능성 인정 원료와 인정 문구 검증 | https://www.data.go.kr/data/15058359/openapi.do |

채택 이유:
- 영양제 OCR 결과를 제품/성분 DB와 대조해 LLM 추측을 줄일 수 있다.
- 목적별 분석 문구를 식약처 인정 범위 안으로 제한할 수 있다.

수정 사유:
- 논문 근거가 있더라도 서비스 화면에서는 질병 예방/치료 효과를 직접 주장하지 않는다.
- 기능성 표현은 식약처 인정 원료와 인정 문구를 우선한다.

적용 방안:
- `recognized_by_mfds`, `functional_claim_source`, `user_confirmed` 필드를 분리한다.
- LLM이 생성한 기능성 문구는 바로 노출하지 않고 식약처 DB 매칭 이후에만 사용한다.

### 3.6 농진청 국가표준식품성분 DB

| 항목 | 내용 |
| --- | --- |
| 용도 | 한식, 전통식품, 자연식품 영양성분 보강 |
| 사용 위치 | 식약처 API 누락 보완, 한국 음식 이미지 인식 후 영양성분 매칭 |
| 채택 이유 | 농촌진흥청의 한국 식품 성분 데이터이며 한식 보강에 적합하다. |
| 수정 사유 | 기존 문서의 "9개정판(2021)" 표현은 최신 기준으로 보기 어렵다. 농식품올바로에는 2026-04-28 기준 `국가표준식품성분 DB 10.4` 공개 안내가 확인된다. |

출처:
- 농식품올바로: https://koreanfood.rda.go.kr/
- 공공데이터포털 국가표준식품성분정보 조회서비스 참고: https://apis.data.go.kr/1390803/AgriFood/NationStdFood/V2

적용 방안:
- 구현 전 `data/source_manifest.yml`에 사용 버전, 다운로드일, 원본 URL, 전처리 담당자를 기록한다.
- 식품명 정규화 시 식약처 DB와 농진청 DB의 식품코드 충돌을 피하기 위해 provider namespace를 둔다.

### 3.7 KDRIs 2020

| 항목 | 내용 |
| --- | --- |
| 용도 | 성별, 연령, 임신/수유 상태별 권장섭취량, 충분섭취량, 상한섭취량 룩업 |
| 사용 위치 | 부족 영양소 분석, 목적별 분석, 영양소 기준값 제공 |
| 채택 이유 | 한국 사용자 대상 서비스에서 가장 직접적인 영양 기준이다. |
| 수정 사유 | KDRIs는 건강한 집단의 영양 기준이지 질환자 치료 용량이나 개인 진단 기준이 아니다. |

출처:
- 보건복지부 2020 한국인 영양소 섭취기준 활용자료 발표: https://eiec.kdi.re.kr/policy/materialView.do?num=223213
- 한국영양학회 KDRIs 활용자료 개발 논문: https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART002817751
- National Academies DRI definition: https://www.ncbi.nlm.nih.gov/books/NBK45182/
- National Academies DRI applications: https://www.ncbi.nlm.nih.gov/books/NBK222890/

적용 방안:
- KDRIs 원문 PDF/자료를 CSV로 디지털화하되 `kdris_metadata.json`에 버전과 검수 이력을 남긴다.
- `RDA` 우선, 없으면 `AI` fallback을 사용한다.
- `UL` 초과는 "위험 가능성" 경고로 표시하되 진단 표현을 쓰지 않는다.

### 3.8 HealthKit, Health Connect, Flutter health package

| 항목 | 내용 |
| --- | --- |
| 용도 | 걸음수, 심박수, 체중, 운동 데이터 읽기 |
| 사용 위치 | v1-v4 활동점수, BMR/TDEE, 체중 예측 |
| 채택 이유 | iOS/Android 헬스 데이터를 사용자 권한 기반으로 가져오기 위한 표준 경로다. |
| 수정 사유 | Google Fit API 신규 가입 중단 이후 Android는 Health Connect를 기본 경로로 둔다. Flutter `health` 패키지는 HealthKit과 Health Connect wrapper를 제공한다. |

출처:
- Apple HealthKit authorization: https://developer.apple.com/documentation/healthkit/authorizing-access-to-health-data
- Apple HKHealthStore: https://developer.apple.com/documentation/healthkit/hkhealthstore
- Android Health Connect aggregate data: https://developer.android.com/health-and-fitness/health-connect/aggregate-data
- Flutter health package: https://pub.dev/packages/health

적용 방안:
- 걸음수 집계는 Health Connect aggregate API 또는 `health.getTotalStepsInInterval`을 사용한다.
- iOS는 권한 요청 성공 여부와 실제 read 권한 허용 여부를 구분해 처리한다.
- "Health Connect 승인 5-10 영업일" 같은 정확한 공식 SLA는 확인하지 못했다. I cannot find the official documentation for this specific query. 따라서 일정 계획에는 가정값으로만 둔다.

### 3.9 건강정보 고속도로 및 FHIR

| 항목 | 내용 |
| --- | --- |
| 용도 | 병원 데이터 연동의 장기 후보 |
| 사용 위치 | 처방, 검사결과, 건강기록 timeline |
| 채택 이유 | 의료기관/공공기관 데이터 조회와 동적 동의 API를 공식 경로로 검토할 수 있다. |
| 수정 사유 | 병원 홈페이지 스크래핑 또는 사용자 계정 보관 방식은 배제한다. 초기 구현은 mock FHIR와 수동 업로드로 제한한다. |

출처:
- 건강정보 고속도로 API: https://www.myhealthway.go.kr/portal/index?page=Organization%2FPortal%2FMediMyData%2FMydataApi
- HL7 FHIR MedicationRequest R4: https://hl7.org/fhir/R4/medicationrequest.html
- HL7 FHIR Observation R4: https://www.hl7.org/fhir/r4/observation.html

적용 방안:
- `Patient`, `Condition`, `MedicationRequest`, `Observation`, `DiagnosticReport`, `DocumentReference` 중심으로 mock schema를 설계한다.
- 실제 API 연동 전까지는 "병원 기록을 분석해 진단"하는 기능을 만들지 않는다.

### 3.10 FastAPI, Pydantic, SQLAlchemy

| 항목 | 내용 |
| --- | --- |
| 용도 | 백엔드 REST API, OpenAPI 문서, 입력 검증, DB 접근 |
| 채택 이유 | Python 기반 알고리즘 구현과 테스트가 쉽고, Pydantic schema와 OpenAPI 문서화를 연결할 수 있다. |
| 수정 사유 | LLM/OCR/공공데이터 응답은 외부 입력이므로 Pydantic으로 재검증해야 한다. |

출처:
- FastAPI features: https://fastapi.tiangolo.com/features/
- FastAPI metadata and docs URLs: https://fastapi.tiangolo.com/tutorial/metadata/
- Pydantic BaseModel API: https://docs.pydantic.dev/latest/api/base_model/
- SQLAlchemy current documentation: https://www.sqlalchemy.org/

적용 방안:
- 모든 외부 API 응답은 raw DTO와 normalized DTO를 분리한다.
- API schema는 Pydantic v2 기준으로 작성한다.
- Alembic migration 전 DB schema 문서와 모델 정의를 먼저 맞춘다.

---

## 4. 논문 및 공식 근거 사용 이유

### 4.1 BMI 분류

| 근거 | 사용할 이유 | 적용 방식 |
| --- | --- | --- |
| WHO Expert Consultation, 2004 | 아시아 인구에서 BMI 위험 기준이 서구 기준과 다를 수 있음을 제시한다. | 한국/아시아 사용자 대상 BMI 분류에 `23`, `25`, `30` 경계값을 사용한다. |

출처:
- https://pubmed.ncbi.nlm.nih.gov/14726171/

수정 방안:
- BMI는 체지방률이나 질환을 진단하지 않는다.
- UI에는 "BMI 기준 분류"라고 표기하고 "비만 진단" 단정 표현을 피한다.

### 4.2 권장 걸음수 및 활동점수

| 근거 | 사용할 이유 | 적용 방식 |
| --- | --- | --- |
| Paluch et al., 2022 | 일일 걸음수와 all-cause mortality 사이의 관계를 대규모 메타분석으로 다룬다. | 8,000보 기준의 방향성 근거로 사용한다. |
| Lee et al., 2019 | older women에서 step volume/intensity와 mortality 관련성을 분석한다. | 고령 사용자에게 무리한 10,000보 기준을 강제하지 않는 근거로 사용한다. |
| HHS Physical Activity Guidelines | 성인 신체활동 권고의 공식 기준이다. | 활동 목표 문구와 중등도 활동 설명에 사용한다. |

출처:
- Paluch et al. 2022: https://pubmed.ncbi.nlm.nih.gov/35247352/
- Lee et al. 2019: https://pubmed.ncbi.nlm.nih.gov/31141585/
- HHS Physical Activity Guidelines: https://odphp.health.gov/healthypeople/tools-action/browse-evidence-based-resources/physical-activity-guidelines-americans-2nd-edition

수정 방안:
- `BASE_STEPS=8000`은 유지한다.
- 성별, 나이, BMI 계수는 논문에서 직접 나온 값이 아니므로 `EvidenceLevel.C`와 설정값으로 분리한다.
- 베타 데이터가 쌓이면 계수 보정 로그를 남긴다.

### 4.3 심박수 가중 알고리즘

| 근거 | 사용할 이유 | 적용 방식 |
| --- | --- | --- |
| Tanaka et al., 2001 | `208 - 0.7 * age` HRmax 추정식을 제안한다. | Phase 2부터 `tanaka_2001` 옵션으로 제공한다. |
| HHS/CDC 활동 권고 | 중등도 유산소 활동 해석의 공식 근거다. | target heart-rate zone 설명에 사용한다. |

출처:
- Tanaka et al. 2001: https://pubmed.ncbi.nlm.nih.gov/11153730/
- CDC chronic health conditions physical activity: https://www.cdc.gov/physical-activity-basics/guidelines/chronic-health-conditions-and-disabilities.html

수정 방안:
- 회사 가이드 예시 재현을 위해 기본 계산은 당장 `220 - age` 호환 모드로 유지할 수 있다.
- 구현에는 `hrmax_formula="guide_220_age" | "tanaka_2001"` 설정을 둔다.
- 심박 점수는 운동 강도 추정값이지 의료 판단값이 아니다.

### 4.4 BMR 및 TDEE

| 근거 | 사용할 이유 | 적용 방식 |
| --- | --- | --- |
| Mifflin et al., 1990 | 성인 REE 예측식을 제시한다. | BMR 계산 공식으로 코드화한다. |
| 활동계수 표 | 프로젝트 가이드 기반 휴리스틱이다. | TDEE 계산에는 쓰되 설정값으로 둔다. |

출처:
- Mifflin-St Jeor equation article: https://www.sciencedirect.com/science/article/pii/S0002916523166986

수정 방안:
- API 필드는 `estimated_bmr`, `estimated_tdee`처럼 예측값임을 드러낸다.
- 활동계수는 논문 공식이 아니므로 `activity_factor_policy.yml`로 분리한다.
- 체중 변화 로그가 생기면 사용자별 보정계수를 별도 모델로 둔다.

### 4.5 7-step 체중 예측 및 Hall 동적 모델

| 근거 | 사용할 이유 | 적용 방식 |
| --- | --- | --- |
| Wishnofsky, 1958 | 체중 변화의 정적 에너지 등가 규칙 근거다. | 7,700 kcal/kg 단기 설명용으로 사용한다. |
| Hall et al., 2011 | 장기 체중 변화는 대사 적응을 반영해야 함을 설명한다. | 1개월 이상 또는 3개월 예측에는 동적 모델 후보로 둔다. |
| Deurenberg et al., 1991 | BMI, 나이, 성별 기반 체지방률 추정 근거다. | Hall 단순화 모델의 초기 체성분 추정 후보로 사용한다. |
| Forbes, 2000 | 체지방량이 체성분 변화 반응에 영향을 준다는 근거다. | FM/FFM 분리 모델의 방향성 근거로 사용한다. |

출처:
- Wishnofsky 1958: https://pubmed.ncbi.nlm.nih.gov/13594881/
- Hall et al. 2011: https://stacks.cdc.gov/view/cdc/33652
- Deurenberg et al. 1991: https://pubmed.ncbi.nlm.nih.gov/2043597/
- Forbes 2000: https://pubmed.ncbi.nlm.nih.gov/10865771/

수정 방안:
- 7-step 결과는 1-4주 단기 예측 또는 데모용으로 제한한다.
- `LOSS_CORRECTION=0.85`, `GAIN_CORRECTION=0.95`는 회사 가이드 재현용 프로젝트 계수로 표시한다.
- 90일 이상 예측은 "Hall dynamic model required" 경고 또는 별도 엔진으로 분기한다.

### 4.6 KDRIs/DRI 기반 부족 영양소 분석

| 근거 | 사용할 이유 | 적용 방식 |
| --- | --- | --- |
| KDRIs 2020 | 한국 사용자 대상 성별/연령별 기준값이다. | reference value lookup에 사용한다. |
| National Academies DRI | EAR/RDA/AI/UL 해석 기준을 제공한다. | 데이터 필드 의미와 UI 문구의 안전 범위를 정한다. |

출처:
- 보건복지부 KDRIs 활용자료 발표: https://eiec.kdi.re.kr/policy/materialView.do?num=223213
- DRI definition: https://www.ncbi.nlm.nih.gov/books/NBK45182/
- DRI applications: https://www.ncbi.nlm.nih.gov/books/NBK222890/

수정 방안:
- `35%`, `70%`, `130%`는 공식 진단 cutoff가 아니라 UX 분류 기준이다.
- 사용자 문구는 "결핍 진단"이 아니라 "섭취량이 낮을 가능성"으로 제한한다.
- UL 초과는 "전문가 상담 권장" CTA를 포함한다.

### 4.7 목적별 분석(눈건강, 간기능, 피로회복 등)

| 근거 | 사용할 이유 | 적용 방식 |
| --- | --- | --- |
| 식약처 기능성 원료 DB | 국내 서비스 문구의 1차 기준이다. | 기능성 인정 원료와 인정 문구만 사용자 화면에 사용한다. |
| AREDS2, 2013 | 루테인/지아잔틴 및 오메가-3 관련 눈건강 연구의 대표 RCT다. | 눈건강 matrix의 배경 근거로만 사용한다. |
| Vitamin D meta-analysis 2025 | 비타민 D의 감염 예방 효과가 최신 분석에서 통계적으로 명확하지 않음을 반영한다. | "면역 기능 유지에 필요" 수준으로 제한하고 감염 예방 보장 표현을 금지한다. |
| Omega-3 meta-analysis 2021 | EPA/DHA 용량과 심혈관 outcome 분석 근거다. | 목적별 분석 배경 근거로만 사용하고 치료 표현은 금지한다. |

출처:
- 식약처 기능성 원료인정 현황: https://www.data.go.kr/data/15058359/openapi.do
- AREDS2 JAMA: https://jamanetwork.com/journals/jama/fullarticle/1684847
- Vitamin D 2025 meta-analysis: https://pubmed.ncbi.nlm.nih.gov/39993397/
- Omega-3 2021 meta-analysis: https://pubmed.ncbi.nlm.nih.gov/32951855/

수정 방안:
- 논문 근거와 식약처 인정 문구를 분리한다.
- 앱 문구는 식약처 인정 범위를 우선하고, 논문은 내부 근거 설명에만 사용한다.
- 질병 예방, 치료, 개선, 복용량 변경 표현은 금지한다.

### 4.8 식단 이미지 및 음식 인식

| 근거 | 사용할 이유 | 적용 방식 |
| --- | --- | --- |
| AI Hub 음식 이미지 및 영양정보 텍스트 | 한국 음식 400종 이상, 음식 양/영양정보 메타데이터를 포함한다. | 한국 음식 인식 모델/평가 데이터 후보로 사용한다. |
| Food-101 | 국제적으로 널리 쓰이는 음식 이미지 benchmark다. | 일반 음식 분류 실험과 baseline 비교에 사용한다. |
| Dalakleidi et al., 2022 | 이미지 기반 식이평가 시스템의 단계와 한계를 정리한다. | 음식명, 분량, 영양소 추정을 반드시 사용자 확인 단계와 분리하는 근거로 사용한다. |

출처:
- AI Hub 음식 이미지 및 영양정보 텍스트: https://aihub.or.kr/aihubdata/data/view.do?dataSetSn=74
- Food-101: https://data.vision.ee.ethz.ch/cvl/datasets_extra/food-101/
- Dalakleidi et al. 2022: https://pubmed.ncbi.nlm.nih.gov/35803496/

수정 방안:
- 이미지 1장만으로 열량과 분량을 확정하지 않는다.
- 상태를 `recognized`, `matched`, `user_confirmed`로 분리한다.
- 음식 인식 confidence가 낮으면 사용자 선택 UI로 넘긴다.

---

## 5. 알고리즘 수정 사유와 구현 방안

### 5.1 외부 LLM 중심 설계에서 로컬 LLM 중심 설계로 변경

수정 이유:
- OCR 원문, 복약 정보, 검사표 텍스트는 민감 건강정보가 될 수 있다.
- 개인정보 보호법 제23조는 건강 정보를 민감정보로 다루며 별도 동의와 안전조치를 요구한다.
- 로컬 Ollama는 기본 처리 경로에서 외부 LLM 전송을 줄일 수 있다.

출처:
- 개인정보 보호법 제23조: https://www.law.go.kr/lsLawLinkInfo.do?chrClsCd=010202&lsJoLnkSeq=1000575255
- Ollama API Introduction: https://docs.ollama.com/api

구현 방안:
- `LLMAdapter`를 유지하되 기본 구현체를 `OllamaAdapter`로 둔다.
- `ExternalLLMAdapter`는 `ALLOW_EXTERNAL_LLM=true`와 비식별 테스트 환경에서만 활성화한다.
- LLM 응답은 Pydantic schema로 2차 검증한다.

### 5.2 자유 텍스트 LLM 응답에서 JSON Schema 출력으로 변경

수정 이유:
- 자유 응답은 필드 누락, 단위 혼동, 환각 성분 생성 위험이 크다.
- Ollama 공식 문서는 `format`에 JSON Schema를 전달하는 구조화 출력을 지원한다.
- Pydantic v2는 JSON Schema 생성과 JSON validation을 지원한다.

출처:
- Ollama Structured Outputs: https://docs.ollama.com/capabilities/structured-outputs
- Pydantic BaseModel API: https://docs.pydantic.dev/latest/api/base_model/

구현 방안:
- `ParsedSupplement.model_json_schema()`를 Ollama `format`에 넣는다.
- `model_validate_json()` 검증 실패 시 최대 1회 재시도 후 사용자 수정 화면으로 넘긴다.
- 온도는 `temperature=0`을 기본값으로 둔다.

### 5.3 OCR 단일 엔진에서 Adapter + fallback 구조로 변경

수정 이유:
- 라벨, 처방전, 검사표의 텍스트 밀도와 레이아웃이 다르다.
- 단일 OCR 엔진 장애 또는 낮은 confidence에 대비해야 한다.
- 공식 문서상 Cloud Vision과 CLOVA OCR은 호출 방식과 응답 구조가 다르므로 내부 DTO 통일이 필요하다.

출처:
- Google Cloud Vision OCR: https://cloud.google.com/vision/docs/ocr
- Naver CLOVA OCR: https://api.ncloud-docs.com/docs/en/ai-application-service-ocr

구현 방안:
- `OCRAdapter.extract_text(image_bytes) -> OCRResult` 인터페이스를 고정한다.
- `confidence < 0.85` 또는 API 오류 시 backup adapter를 호출한다.
- 원본 이미지는 기본 장기 저장하지 않고, OCR 결과도 보유기간을 둔다.

### 5.4 식품영양 API 버전과 데이터 우선순위 수정

수정 이유:
- 식약처 식품영양성분DB정보는 공공데이터포털 `15127578` 기준으로 확인된다.
- 농진청 국가표준식품성분 DB는 10.4 공개 안내가 있어 기존 9개정판 표현을 최신이라고 보기 어렵다.
- 한식/전통식품은 하나의 API만으로 충분하지 않을 수 있다.

출처:
- 식약처 식품영양성분DB정보: https://www.data.go.kr/data/15127578/openapi.do
- 식품안전나라 I2791: https://www.foodsafetykorea.go.kr/api/newDatasetDetail.do?svc_no=I2791
- 농식품올바로: https://koreanfood.rda.go.kr/

구현 방안:
- 우선순위: 사용자 확정값 > 식약처 DB match > 농진청 DB match > LLM 후보.
- 동일 음식명이라도 provider, source_version, serving_basis를 함께 저장한다.
- API 호출 결과는 캐싱하고, offline seed DB를 병행 구축한다.

### 5.5 부족 영양소 "진단" 표현 완화

수정 이유:
- KDRIs/DRI는 건강한 집단 기준이며 개인 진단 기준이 아니다.
- 의료법 제27조는 비의료인의 의료행위를 금지한다.
- 건강기능식품과 영양소 정보는 치료/처방 표현으로 확장하면 규제 위험이 커진다.

출처:
- 의료법 제27조: https://law.go.kr/LSW/lsLawLinkInfo.do?chrClsCd=010202&lsJoLnkSeq=1000901296
- DRI definition: https://www.ncbi.nlm.nih.gov/books/NBK45182/
- MFDS 생성형 AI 의료기기 가이드라인: https://www.mfds.go.kr/brd/m_1060/view.do?seq=15628

구현 방안:
- 내부 enum은 `DEFICIENT`, `LOW`, `ADEQUATE`, `EXCESSIVE`, `RISKY`를 유지할 수 있다.
- 사용자 문구는 "부족 가능성", "섭취량 확인 필요", "전문가 상담 권장"으로 변환한다.
- `diagnosis`, `treatment`, `prescribe`, `change_dose` 계열 API는 만들지 않는다.

### 5.6 7-step 체중 예측의 적용 범위 제한

수정 이유:
- `7,700 kcal/kg` 규칙은 단순하고 설명하기 쉽지만 장기 체중 변화의 대사 적응을 반영하지 못한다.
- Hall et al. 2011은 장기 체중 변화 예측에는 동적 모델이 필요하다는 근거를 제공한다.

출처:
- Wishnofsky 1958: https://pubmed.ncbi.nlm.nih.gov/13594881/
- Hall et al. 2011: https://stacks.cdc.gov/view/cdc/33652

구현 방안:
- `predict_weight_n_days`는 1-90일 범위에서 warning을 포함해 제공한다.
- 90일 이상은 `HallDynamicModel` 또는 "장기 예측 미지원"으로 분기한다.
- 실제 체중 로그가 있으면 예측치와 관측치 차이를 기록해 보정 후보를 만든다.

### 5.7 병원 데이터와 복용량 변경 기능 제한

수정 이유:
- 처방전과 검사표는 민감 건강정보이며 의료 판단으로 이어질 수 있다.
- 앱이 복용량 변경을 지시하면 의료행위 또는 약사 업무 영역에 들어갈 수 있다.
- 건강정보 고속도로는 공식 연동 후보지만 초기 팀 구현 범위에서는 mock/manual이 안전하다.

출처:
- 의료법 제27조: https://law.go.kr/LSW/lsLawLinkInfo.do?chrClsCd=010202&lsJoLnkSeq=1000901296
- 개인정보 보호법 제23조: https://www.law.go.kr/lsLawLinkInfo.do?chrClsCd=010202&lsJoLnkSeq=1000575255
- 건강정보 고속도로 API: https://www.myhealthway.go.kr/portal/index?page=Organization%2FPortal%2FMediMyData%2FMydataApi

구현 방안:
- 허용: OCR 추출, 사용자 확인, 복약 알림, 참고범위 이탈 시 상담 권장.
- 금지: 복용량 변경, 질병 진단, 치료 방향 제안, 처방 생성.
- 파트너 파일럿 이후에만 clinician review queue를 검토한다.

---

## 6. 구현 우선순위

| 우선순위 | 작업 | 이유 |
| --- | --- | --- |
| P0 | API 키 환경변수화 및 기존 키 노출 점검 | 문서/코드에 실제 키가 남으면 보안 위험이 크다. |
| P0 | KDRIs CSV + source manifest 작성 | 영양 분석의 기준 데이터이므로 가장 먼저 고정해야 한다. |
| P0 | OllamaAdapter + Pydantic structured output | 환각과 민감정보 전송을 줄이는 핵심 구조다. |
| P1 | GoogleVisionOCR + ClovaOCR Adapter | OCR 파이프라인의 입력 품질을 확보한다. |
| P1 | MFDS/RDA food matcher | 식단 입력을 영양소로 변환하는 핵심 데이터 경로다. |
| P1 | HealthKit/Health Connect 권한 및 step sync | 활동점수와 TDEE 입력을 확보한다. |
| P2 | 7-step weight prediction + warning | 데모에는 필요하지만 장기 예측 제한이 필요하다. |
| P2 | 목적별 분석 matrix | 식약처 인정 문구와 논문 근거 분리가 선행되어야 한다. |
| P3 | mock FHIR/manual upload | 병원 데이터는 규제/연동 검토 후 확장한다. |

---

## 7. 최종 출처 목록

### API 및 공식 문서

- Ollama API Introduction: https://docs.ollama.com/api
- Ollama Chat API: https://docs.ollama.com/api/chat
- Ollama Structured Outputs: https://docs.ollama.com/capabilities/structured-outputs
- Google Cloud Vision OCR: https://cloud.google.com/vision/docs/ocr
- Naver CLOVA OCR: https://api.ncloud-docs.com/docs/en/ai-application-service-ocr
- 식약처 식품영양성분DB정보: https://www.data.go.kr/data/15127578/openapi.do
- 식품안전나라 식품영양성분DB정보: https://www.foodsafetykorea.go.kr/api/newDatasetDetail.do?svc_no=I2791
- 식약처 건강기능식품정보: https://www.data.go.kr/data/15056760/openapi.do
- 식약처 건강기능식품 영양DB: https://www.data.go.kr/data/15085712/openapi.do
- 식약처 건강기능식품 기능성 원료인정 현황: https://www.data.go.kr/data/15058359/openapi.do
- 농식품올바로: https://koreanfood.rda.go.kr/
- Apple HealthKit authorization: https://developer.apple.com/documentation/healthkit/authorizing-access-to-health-data
- Android Health Connect aggregate data: https://developer.android.com/health-and-fitness/health-connect/aggregate-data
- Flutter health package: https://pub.dev/packages/health
- 건강정보 고속도로 API: https://www.myhealthway.go.kr/portal/index?page=Organization%2FPortal%2FMediMyData%2FMydataApi
- HL7 FHIR MedicationRequest R4: https://hl7.org/fhir/R4/medicationrequest.html
- HL7 FHIR Observation R4: https://www.hl7.org/fhir/r4/observation.html
- FastAPI features: https://fastapi.tiangolo.com/features/
- Pydantic BaseModel API: https://docs.pydantic.dev/latest/api/base_model/
- SQLAlchemy: https://www.sqlalchemy.org/
- 개인정보 보호법 제23조: https://www.law.go.kr/lsLawLinkInfo.do?chrClsCd=010202&lsJoLnkSeq=1000575255
- 의료법 제27조: https://law.go.kr/LSW/lsLawLinkInfo.do?chrClsCd=010202&lsJoLnkSeq=1000901296
- MFDS 생성형 AI 의료기기 가이드라인: https://www.mfds.go.kr/brd/m_1060/view.do?seq=15628

### 논문 및 학술 근거

- WHO Expert Consultation. Appropriate body-mass index for Asian populations. https://pubmed.ncbi.nlm.nih.gov/14726171/
- Paluch AE et al. Daily steps and all-cause mortality. https://pubmed.ncbi.nlm.nih.gov/35247352/
- Lee IM et al. Step volume and intensity with all-cause mortality in older women. https://pubmed.ncbi.nlm.nih.gov/31141585/
- Tanaka H et al. Age-predicted maximal heart rate revisited. https://pubmed.ncbi.nlm.nih.gov/11153730/
- Mifflin MD et al. A new predictive equation for resting energy expenditure. https://www.sciencedirect.com/science/article/pii/S0002916523166986
- Wishnofsky M. Caloric equivalents of gained or lost weight. https://pubmed.ncbi.nlm.nih.gov/13594881/
- Hall KD et al. Quantification of the effect of energy imbalance on bodyweight. https://stacks.cdc.gov/view/cdc/33652
- Deurenberg P et al. BMI as a measure of body fatness. https://pubmed.ncbi.nlm.nih.gov/2043597/
- Forbes GB. Body fat content influences body composition response. https://pubmed.ncbi.nlm.nih.gov/10865771/
- National Academies. What are Dietary Reference Intakes? https://www.ncbi.nlm.nih.gov/books/NBK45182/
- National Academies. DRI Applications in Dietary Assessment. https://www.ncbi.nlm.nih.gov/books/NBK222890/
- AREDS2 Research Group. Lutein + zeaxanthin and omega-3 fatty acids for AMD. https://jamanetwork.com/journals/jama/fullarticle/1684847
- Jolliffe DA et al. Vitamin D supplementation to prevent acute respiratory infections, 2025. https://pubmed.ncbi.nlm.nih.gov/39993397/
- Bernasconi AA et al. Omega-3 dosage and cardiovascular outcomes. https://pubmed.ncbi.nlm.nih.gov/32951855/
- AI Hub 음식 이미지 및 영양정보 텍스트. https://aihub.or.kr/aihubdata/data/view.do?dataSetSn=74
- Food-101. https://data.vision.ee.ethz.ch/cvl/datasets_extra/food-101/
- Dalakleidi K et al. Image-based food-recognition systems on dietary assessment. https://pubmed.ncbi.nlm.nih.gov/35803496/
