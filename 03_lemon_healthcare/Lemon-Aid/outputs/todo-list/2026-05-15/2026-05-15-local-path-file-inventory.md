# Lemon Healthcare 로컬 경로 파일 인벤토리

작성일: 2026-05-15
대상 경로: `/Users/yeong/99_me/00_github/03_lemon_healthcare`
확인 기준: 실제 로컬 파일시스템 + `git status --short` + 핵심 문서/엔트리포인트 확인

## 1. 전체 판단

현재 루트는 하나의 순수 앱 저장소라기보다, Lemon Aid 프로젝트의 코드, 문서, 발표 산출물, 회의 자료, 로컬 에이전트 상태가 함께 놓인 작업 루트다.

실제 제품 구현의 중심은 `yeong-Lemon-Aid/`이며, 그중에서도 `yeong-Lemon-Aid/backend/`가 현재 가장 많은 기능을 가진 런타임 코드다. `mobile/`은 현재 `CLAUDE.md`만 존재해 실제 Flutter 앱 구현체는 아직 이 경로에 없다.

현재 워킹트리는 깨끗하지 않다. 백엔드 OCR, regulated OCR intake, learning/vector DB, 문서 일부가 수정 또는 신규 파일 상태이므로, 이 문서는 커밋된 기준이 아니라 현재 로컬 스냅샷 기준이다.

## 2. 루트 폴더 및 파일

| 경로 | 현재 존재 파일/하위 폴더 | 의미 |
| --- | --- | --- |
| `PROJECT_GUIDE.md` | 루트 프로젝트 가이드 | Lemon Aid 전체 기획/포지셔닝 문서. 현재 프로젝트 설명의 최상위 참조 문서다. |
| `guide.html` | 루트 가이드 HTML | `PROJECT_GUIDE.md`를 브라우저로 보기 위한 동기화 산출물 성격이다. |
| `yeong-Lemon-Aid/` | backend, config, data, docs, mobile 등 | 실제 제품 코드와 주요 문서가 들어 있는 핵심 프로젝트 폴더다. |
| `.github/` | workflows, issue template, PR template, CODEOWNERS | GitHub 협업/CI 정책 파일이다. |
| `yeong-Lemon-Aid/assets/mascot/` | Lemon Aid 캐릭터/로고 zip | 브랜드 캐릭터와 Lottie/이미지 번들 보관 폴더다. |
| `yeong-Lemon-Aid/records/meetings/` | week-01, mentoring-01, CTO_meeting_data | 주차별 회의, 멘토링, CTO 미팅 원본 문서와 발표자료 보관 폴더다. |
| `yeong-Lemon-Aid/outputs/reports/` | pdf | 팀 공유 보고서와 PDF 결과물을 보관하는 정리용 산출물 폴더다. |
| `yeong-Lemon-Aid/outputs/generated/` | manual 작업별 폴더, preview 이미지, 보정 스크립트 | 발표자료/PDF 수동 생성 및 보정 산출물이 들어 있다. |
| `yeong-Lemon-Aid/outputs/todo-list/` | 날짜별 Markdown/PDF 보고서 | 팀 공유 보고서와 로컬 정리 기록을 날짜별로 보관한다. |
| `tmp/` | pdf 생성 스크립트, 렌더링 preview 이미지 | 임시 PDF/이미지 생성 작업물이다. 장기 보존 대상과 분리하는 편이 좋다. |
| `.claude/`, `.omx/`, `.omc/` | worktree, logs, state | 로컬 에이전트/자동화 실행 상태다. 프로젝트 소스라기보다 도구 상태 파일이다. |
| `.DS_Store` | macOS Finder metadata | 정리 대상. 기능 의미는 없다. |

## 3. `yeong-Lemon-Aid/` 핵심 구조

| 경로 | 주요 파일 | 의미 |
| --- | --- | --- |
| `README.md` | 프로젝트 소개/빠른 시작 | 외부용 소개 문서지만 일부 기술 버전은 현재 `pyproject.toml`/CI와 다를 수 있어 갱신 후보다. |
| `PROJECT_GUIDE.md`, `guide.html` | 프로젝트 가이드와 HTML 뷰 | 루트 가이드와 유사한 핵심 설명 문서다. 문서 수정 시 둘의 동기화가 필요하다. |
| `01_HANDOFF.md`, `HANDOFF.md`, `CLAUDE.md` | 인수인계/에이전트 작업 지침 | 작업 맥락과 협업 규칙을 담은 보조 문서다. |
| `backend/` | FastAPI 백엔드 코드, 테스트, 마이그레이션 | 현재 구현의 중심. API, DB, OCR, LLM, 영양 분석, 개인정보/동의, 테스트가 들어 있다. |
| `config/` | `implementation-readiness.settings.json`, `service-segmentation.settings.json` | 기능 플래그, 런타임 정책, 서비스 세그먼트 기준을 고정하는 설정 문서다. |
| `data/` | food_images, supplement_images, nutrition_reference | 음식/영양제 이미지 데이터와 KDRIs/MFDS/nutrient 기준 데이터를 분리해 관리한다. |
| `docs/` | 01-42 문서, dev-guides, previous-version, templates | 기획, 설계, 구현 상태, 실행 계획, 템플릿 문서 허브다. |
| `mobile/` | `CLAUDE.md` | 모바일 구현 폴더 이름은 있으나 실제 앱 코드는 아직 없다. |
| `api-key/` | 공공 API 설명 Markdown 다수 | 농진청/식약처 등 외부 데이터 API 문서 보관 성격이다. 실제 비밀 키값은 확인하거나 노출하지 않았다. |
| `htmlcov/`, `.pytest_cache/`, `.ruff_cache/`, `.mypy_cache/`, `.coverage` | 테스트/정적분석 산출물 | 생성물이다. 기능 구현 파일로 보지 않는 편이 맞다. |

## 4. `backend/` 주요 파일과 의미

| 경로 | 의미 |
| --- | --- |
| `pyproject.toml` | Python 3.13, Black, Ruff, mypy strict, pytest coverage 기준을 정의한다. |
| `requirements.txt`, `requirements-dev.txt` | 런타임/개발 의존성 목록이다. |
| `.env.example` | 환경변수 예시다. 실제 `.env` 값은 비밀 취급 대상이다. |
| `alembic.ini`, `alembic/` | PostgreSQL DB migration 설정과 버전 파일이다. |
| `scripts/` | KDRIs 검증/디지타이징, OIDC discovery 점검, OCR 3-tier 평가, learning worker 실행 스크립트다. |
| `src/main.py` | FastAPI 앱 생성, `/health`, 보안 미들웨어, `/api/v1` 라우터 등록 엔트리포인트다. |
| `src/config.py` | 모든 런타임 설정, feature flag, production guard, env file 로딩 정책을 담당한다. |
| `tests/` | unit/integration 테스트. 현재 API, 보안, DB, OCR, learning, regulated, nutrition, prediction 검증이 있다. |

## 5. `backend/src/` 모듈별 의미

| 모듈 | 주요 파일 | 현재 역할 |
| --- | --- | --- |
| `api/v1/` | `router.py`, `supplements.py`, `regulated_inputs.py`, `nutrition.py`, `predictions.py`, `privacy.py`, `health.py`, `dashboard.py`, `analysis_results.py`, `activity.py` | HTTP 계약 계층. 인증, 동의, request/response 변환, 서비스 호출을 담당한다. |
| `services/` | `supplement_image_analysis.py`, `supplement_intake.py`, `supplement_parser.py`, `supplement_registration.py`, `privacy.py`, `dashboard.py`, `health_sync.py`, `nutrition_diagnosis.py` | 실제 유스케이스 orchestration 계층. API에서 받은 요청을 DB/알고리즘/OCR/LLM 흐름으로 연결한다. |
| `models/schemas/` | supplement, regulated, privacy, learning, health, dashboard, nutrition 등 | Pydantic API schema와 서비스 DTO를 정의한다. |
| `models/db/` | user, supplement, privacy, health, analysis_result, learning, regulated 등 | SQLAlchemy ORM 모델이다. |
| `db/` | `base.py`, `session.py`, `dependencies.py` | DB Base, async session, FastAPI dependency를 담당한다. |
| `security/` | `auth.py`, `scopes.py`, `oidc.py`, `privacy.py`, `subjects.py` | JWT/OIDC 검증, scope 권한, 사용자 subject, privacy hash를 담당한다. |
| `privacy/` | `consent_policies.py` | 활성 동의 정책 정의다. OCR, 민감 건강 분석, 데이터 보존, 외부 OCR, 처방전/검사표 intake 동의가 포함된다. |
| `algorithms/` | `activity.py`, `bmi.py`, `metabolism.py` | 활동 점수, BMI, BMR/TDEE 계열 계산 로직이다. |
| `prediction/` | `weight.py`, `hall.py`, `selector.py`, `body_composition.py` | 체중 예측. 기본 7-step과 Hall-lite 후보 경로를 feature flag로 선택한다. |
| `nutrition/` | `kdris.py`, `deficiency_analysis.py`, `chronic_priority.py`, `unit_converter.py`, `source_manifest.py` | KDRIs 조회, 부족 영양소 분석, 만성질환 우선순위, 단위 변환, 데이터 출처 manifest 검증을 담당한다. |
| `ocr/` | `base.py`, `factory.py`, `preprocessing.py`, `providers/*` | OCR adapter 계약과 provider factory. 현재 Google Vision, PaddleOCR, CLOVA, Noop adapter 파일이 존재한다. |
| `llm/` | `base.py`, `ollama.py`, `ollama_vision.py` | 로컬 Ollama 기반 구조화 parser와 vision assist 계약이다. |
| `vision/` | `base.py`, `yolo.py`, `ultralytics_runner.py`, `preprocessing.py`, `taxonomy.py` | YOLO ROI helper. 제품/성분 추출이 아니라 OCR 전 라벨 영역 후보를 찾는 역할이다. |
| `learning/` | `consent_gate.py`, `retention.py`, `embeddings.py`, `vector_store.py`, `factory.py`, `object_storage.py`, `pgvector_store.py`, `pipeline.py`, `upsert_worker.py` | 이미지 학습 재사용/임베딩/vector DB 파이프라인 골격. 기본은 fail-closed 비활성화다. |
| `regulated/` | `ocr_intake.py`, `factory.py` | 처방전/검사표 OCR intake. 사용자 확인 preview를 만들고, 복용량 변경 직접 안내 등 금지 출력을 차단한다. |
| `utils/`, `cache/` | `logger.py`, `__init__.py` | 공통 로깅과 향후 캐시 모듈 자리다. |

## 6. 현재 구현 기능 기준 요약

- FastAPI 앱은 `/health`와 `/api/v1/*` 라우터를 가진다.
- `/api/v1/supplements/analyze`는 영양제 이미지 intake, 동의 확인, 이미지 검증, OCR/vision/LLM adapter 선택 흐름을 가진다.
- `/api/v1/supplements/analyses/{analysis_id}/ocr-text`는 OCR text를 직접 받아 Ollama structured parser 경로로 preview를 갱신한다.
- `/api/v1/supplements`는 사용자 확인 후 영양제 등록/조회/삭제를 담당한다.
- `/api/v1/nutrition/*`는 KDRIs 조회와 부족 영양소 분석을 담당한다.
- `/api/v1/predictions/weight`는 static 7-step 기본값과 Hall-lite feature-flag 경로를 가진다.
- `/api/v1/me/privacy/*`는 동의, 철회, 삭제 요청, audit log 흐름을 담당한다.
- `/api/v1/health/sync`와 `/api/v1/dashboard/summary`는 건강 데이터 집계와 대시보드 요약을 연결한다.
- `/api/v1/regulated-inputs/*`는 처방전/검사표 OCR intake 코드가 있으나 feature flag 기본값은 비활성이다.
- OCR 3-tier 관련 provider 파일은 현재 로컬에 존재하지만, 외부 OCR/로컬 OCR/멀티모달/YOLO/learning 기능은 설정과 동의 게이트가 켜져야 동작한다.

## 7. 문서 폴더 정리 기준

| 문서 범위 | 의미 |
| --- | --- |
| `docs/01`-`18` | 프로젝트 개요, 배경, 의도, 시장, 기술스택, 알고리즘, 데이터, 컴플라이언스, 로컬 LLM, 규제 가능성 등 상위 설계 문서다. |
| `docs/20`-`24` | 백엔드 구조, 현재 구현 상태, P1 안정화, PostgreSQL 전환 계획이다. |
| `docs/25`-`35` | OCR, Ollama, Google Vision, PaddleOCR, YOLO, LLM serving 관련 계획/가이드다. |
| `docs/36`-`42` | post-P1 실행 계획, CI/PR gate, commit splitting, OCR 3-tier, learning vector DB, 처방전/검사표 intake 설계다. |
| `docs/Nutrition-docs/dev-guides/` | 기능별 개발 가이드와 운영/시연/최종 산출물 체크리스트다. |
| `docs/Nutrition-docs/previous-version/` | 과거 스냅샷 문서다. 현재 구현 판단의 1차 근거로 쓰면 안 된다. |
| `docs/Nutrition-docs/templates/` | OCR 평가 리포트 템플릿 등 재사용 문서 양식이다. |

## 8. 데이터 폴더 정리 기준

| 경로 | 의미 |
| --- | --- |
| `data/nutrition_reference/kdris/kdris_2025.csv` | 현재 주요 KDRIs 2025 데이터셋이다. |
| `data/nutrition_reference/kdris/kdris_2020.csv` | 이전 또는 비교용 KDRIs 데이터다. |
| `data/nutrition_reference/kdris/review/2025/` | 2025 데이터 검수 산출물. 후보 row, 이슈, source artifact, schema decision이 있다. |
| `data/nutrition_reference/kdris/raw/2025/` | 원본 PDF/HWPX/ZIP 등 공식 원천 파일 보관 폴더다. |
| `data/nutrition_reference/nutrient/` | 영양소 코드, 만성질환별 영양 우선순위 reference JSON이다. |
| `data/nutrition_reference/mfds/unit_conversions.json` | 식약처/영양 단위 변환 기준이다. |
| `data/supplement_images/manifests/fixtures/supplement_labels/manifest.example.jsonl` | OCR 3-tier 평가 fixture manifest 예시다. |

## 9. Git 상태에서 주의할 점

현재 수정 파일은 백엔드 설정/라우터/서비스/테스트/문서 전반에 걸쳐 있고, 신규 파일은 OCR provider, regulated intake, learning/vector DB, OCR 평가 스크립트, 새 설계 문서에 집중되어 있다.

정리 작업을 이어갈 때는 다음 순서가 안전하다.

1. `yeong-Lemon-Aid/backend/src`와 `tests`의 신규/수정 파일을 먼저 기능 단위로 묶는다.
2. `docs/Nutrition-docs/22-current-implementation-status-map.md`와 `docs/Nutrition-docs/21-backend-file-structure-guide.md`는 현재 새 파일보다 뒤처진 표현이 있을 수 있으므로 코드 기준으로 재정렬한다.
3. `assets/mascot`, `records/meetings`, `outputs/reports`, `outputs/generated`, `outputs/todo-list`는 기능 커밋과 분리해 산출물 커밋으로 관리한다.
4. `.DS_Store`, cache, coverage, pycache, local state 파일은 정리 대상이다.
5. `.env`와 `api-key/` 이름의 폴더는 비밀정보 노출 위험을 기준으로 별도 점검하되, 실제 키값은 문서나 커밋에 포함하지 않는다.

## 10. 1차 결론

정리 기준의 중심축은 다음처럼 두면 된다.

- `yeong-Lemon-Aid/backend/`: 실제 구현 코드
- `yeong-Lemon-Aid/docs/`: 설계/상태/실행 계획
- `yeong-Lemon-Aid/data/`: 공식 데이터와 검수 산출물
- `yeong-Lemon-Aid/outputs/`: 보고서, 수동 생성물, todo-list 산출물
- `yeong-Lemon-Aid/records/meetings/`, `yeong-Lemon-Aid/assets/mascot/`: 회의/브랜드 자료
- `.claude/`, `.omx/`, `.omc/`, cache류: 로컬 도구 상태 또는 생성물

따라서 다음 단계에서 세부 정리를 한다면, 먼저 `backend/src`와 `backend/tests`를 기능 단위로 묶고, 그 다음 문서가 그 구현 상태를 정확히 반영하도록 `docs/21`, `docs/22`, `docs/33`, `docs/35`, `docs/36` 순서로 정리하는 것이 적합하다.
