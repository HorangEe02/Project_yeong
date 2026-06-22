# 상세 구현 전 설정값 누락 검토

## 1. 검토 목적

상세 구현을 시작하기 전에 현재 가이드 문서와 설정 파일을 교차 확인하여, 실제 코드 작성 전에 고정해야 하는 값이 더 있는지 점검했다.

검토 결과, 기존 `config/service-segmentation.settings.json`은 제품 방향, 사용자 우선순위, 규제 기능 범위를 정리하기에는 충분하지만, 실제 구현에 필요한 환경변수, 보안, DB, OCR, LLM, 동의, 데이터 보관, API 차단 규칙, 테스트 게이트 설정은 별도 파일로 분리하는 것이 필요했다.

## 2. 확인한 기준 문서

- `PROJECT_GUIDE.md`
- `guide.html`
- `docs/Nutrition-docs/06-tech-stack.md`
- `docs/Nutrition-docs/08-implementation-plan.md`
- `docs/Nutrition-docs/09-data-catalog.md`
- `docs/Nutrition-docs/10-compliance-checklist.md`
- `docs/Nutrition-docs/11-detailed-feature-implementation-plan.md`
- `docs/Nutrition-docs/12-local-llm-ollama-migration.md`
- `docs/Nutrition-docs/14-pre-implementation-scope-and-rules.md`
- `docs/Nutrition-docs/15-regulated-feature-feasibility-and-compliance-plan.md`
- `docs/Nutrition-docs/dev-guides/00-setup-environment.md`
- `docs/Nutrition-docs/dev-guides/07-ocr-pipeline.md`
- `docs/Nutrition-docs/dev-guides/08-llm-supplement-parsing.md`
- `docs/Nutrition-docs/dev-guides/09-supplement-registration-api.md`
- `docs/Nutrition-docs/dev-guides/12-mobile-healthkit-integration.md`
- `docs/Nutrition-docs/dev-guides/26-operations-manual.md`
- `docs/Nutrition-docs/dev-guides/27-incident-runbook.md`

## 3. 추가로 설정해야 하는 값

### 3.1 환경변수 기준

실제 `backend/src/config.py`와 `.env.example`을 만들기 전에 다음 값을 고정해야 한다.

- 앱 실행 환경: `APP_ENV`, `APP_NAME`, `API_PREFIX`, `LOG_LEVEL`
- DB/캐시: `DATABASE_URL`, `REDIS_URL`, `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`
- 인증/보안: `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`, `ENCRYPTION_KEY`
- 로컬 LLM: `LLM_PROVIDER`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `OLLAMA_TIMEOUT_SEC`, `ALLOW_EXTERNAL_LLM`
- OCR: `OCR_PRIMARY_PROVIDER`, `GOOGLE_APPLICATION_CREDENTIALS`, `OCR_FALLBACK_PROVIDER`, `CLOVA_OCR_API_URL`, `CLOVA_OCR_SECRET`, `OCR_CONFIDENCE_THRESHOLD`
- 데이터 소스: `MFDS_API_KEY`, `KDRIS_DATA_VERSION`, `KDRIS_DATA_PATH`, `UNIT_CONVERSION_PATH`
- 저장소: `OBJECT_STORAGE_PROVIDER`, `STORE_ORIGINAL_IMAGES`, `STORE_SENSITIVE_DOCUMENT_IMAGES`
- 기능 플래그: 처방전 OCR, 검사표 OCR, mock FHIR, 복용량 변경 차단, 약물 안전 알림

이 값들은 `config/implementation-readiness.settings.json`에 반영했다.

### 3.2 동의 및 민감정보 설정

기존 문서에는 민감정보 별도 동의 필요성이 정리되어 있지만, 코드에서 바로 사용할 수 있는 동의 카테고리 설정은 부족했다.

추가한 동의 카테고리는 다음과 같다.

- 일반 프로필
- 만성질환 정보
- 복약 정보
- 처방전 OCR
- 검사표 OCR
- HealthKit 또는 Health Connect 데이터
- 병원 API 연동

각 동의 기록은 `consent_type`, `purpose`, `data_categories`, `retention_period`, `accepted_at`, `revoked_at`, `policy_version`을 가져야 한다.

### 3.3 데이터 보관 및 삭제 정책

구현 전에 보관 기간을 명확히 고정해야 한다.

- 일반 영양제/식단 이미지 캐시: 30일
- 처방전/검사표 원본 이미지: 기본 저장하지 않음
- OCR/LLM 운영 로그: 90일
- 접근 감사 로그: 365일
- 회원탈퇴 또는 삭제 요청 후 백업 폐기: 90일 이내
- 운영 로그에 prompt 전문 또는 OCR 원문 전문 저장 금지

### 3.4 API 차단 규칙

구현자가 실수로 의료행위처럼 보이는 endpoint를 만들지 않도록 차단 패턴을 설정했다.

차단해야 하는 endpoint 예시:

- `/api/v1/diagnosis/*`
- `/api/v1/treatment/*`
- `/api/v1/prescriptions/create`
- `/api/v1/medications/change-dose`

대신 다음 구조로 우회 구현한다.

- `/api/v1/regulated-inputs/prescriptions/*`
- `/api/v1/regulated-inputs/lab-results/*`
- `/api/v1/medication-safety/*`
- `/api/v1/professional-review/*`

### 3.5 DB와 감사 로그 기준

상세 구현 전에 반드시 필요한 테이블을 분리했다.

먼저 만들어야 하는 공통 테이블:

- `users`
- `consent_records`
- `access_audit_logs`
- `user_profiles`
- `regulated_documents`
- `ocr_extraction_jobs`
- `llm_parse_jobs`

규제 기능용 테이블:

- `prescription_items`
- `lab_result_items`
- `health_record_imports`
- `medication_safety_alerts`
- `professional_review_requests`

감사 로그가 필요한 이벤트:

- 동의 수락/철회
- 민감정보 생성/조회/내보내기/삭제
- 처방전/검사표 OCR 시작 및 사용자 확인
- 약물 안전 알림 생성
- 전문가 검토 요청

### 3.6 테스트와 릴리즈 게이트

구현 시작 전부터 테스트 게이트를 설정해야 한다.

백엔드 기본 게이트:

- `pytest`
- `ruff`
- `black --check`
- `mypy`

프론트엔드 기본 게이트:

- `flutter analyze`
- `flutter test`

규제 기능 릴리즈 전 게이트:

- secret scan
- 민감정보 로그 scan
- 금지 표현 테스트
- 동의 플로우 테스트
- 삭제 플로우 테스트
- 감사 로그 테스트

## 4. 가이드 문서 간 불일치

기존 가이드 문서에는 일부 오래된 방향이 남아 있었고, 이번 수정에서 핵심 구현 기준을 반영했다.

| 위치 | 현재 문제 | 적용 기준 |
| --- | --- | --- |
| `PROJECT_GUIDE.md`, `guide.html` | 외부 LLM 런타임과 이전 Agent 구조 기준이 남아 있었음 | Ollama 로컬 LLM 기본, 4개 모듈형 Agent, 처방전·검사표 OCR intake, 복용량 변경 직접 안내 금지로 수정 |
| `docs/Nutrition-docs/dev-guides/00-setup-environment.md` | Settings 예시에 `anthropic_api_key`가 있고 Ollama, CLOVA, regulated feature 설정이 부족했음 | Ollama, CLOVA, 처방전 OCR, 검사표 OCR, 복용량 변경 차단 feature flag를 반영 |
| `docs/Nutrition-docs/08-implementation-plan.md` | 이전 MVP 제외 범위와 외부 LLM 흐름이 일부 남아 있음 | 병원 데이터는 mock FHIR/수동 업로드/API 후보, 처방전·검사표는 OCR intake로 단계화 |

상세 구현에서는 가이드 문서가 아니라 `config/*.settings.json`을 우선 기준으로 삼는다. 문서와 설정이 충돌하면 설정 파일을 기준으로 구현하고, 이후 문서를 따라 수정한다.

## 5. 최종 판단

상세 구현을 시작하기 위해 추가 설정이 필요했다. 다음 파일을 새로 생성하여 누락 설정을 보완했다.

- `config/implementation-readiness.settings.json`

이제 구현자는 다음 순서로 작업하면 된다.

1. `config/service-segmentation.settings.json`으로 제품 범위와 규제 기능 범위를 확인한다.
2. `config/implementation-readiness.settings.json`으로 `.env.example`, `backend/src/config.py`, feature flag, DB schema, audit log, release gate를 만든다.
3. `docs/Nutrition-docs/12-local-llm-ollama-migration.md` 기준으로 Ollama 모델 실행 가능 여부를 확인한다.
4. 처방전, 검사표, 병원 데이터, 복용량 관련 기능은 `regulated_input_policy`와 `release_gates`를 통과한 범위에서만 노출한다.

## 6. 구현 시작 전 남은 확인 질문

다음 항목은 실제 코드 작성 전에 팀 또는 멘토에게 한 번 더 확인하는 것이 좋다.

- 처방전 OCR 결과를 복약 알림으로 저장하는 기능을 공개 B2C에 포함할지
- 검사표 OCR 결과에서 참고범위 이탈 표시를 어느 수준까지 허용할지
- 건강정보 고속도로 API를 이번 프로젝트에서 실제 신청할지, mock FHIR로만 시연할지
- 전문가 검토 큐를 화면만 만들지, 실제 운영 워크플로까지 만들지
- 원본 이미지 저장을 완전히 금지할지, 영양제/식단 이미지만 선택 저장할지
- 백엔드 배포 환경을 로컬 데모, NCP, AWS, GCP 중 어디로 둘지
