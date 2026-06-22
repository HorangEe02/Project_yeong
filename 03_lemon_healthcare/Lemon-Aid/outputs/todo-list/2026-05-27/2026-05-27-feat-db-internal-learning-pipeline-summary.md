# 2026-05-27 feat/db-internal-learning-pipeline 작업 요약

## 기준 정보

- 작성일: 2026-05-27
- 대상 repo: `/Users/yeong/99_me/00_github/03_lemon_healthcare/Lemon-Aid`
- remote: `origin` = `https://github.com/Lemon-Aid-KDT/Lemon-sin.git`
- 작업 브랜치: `feat/db-internal-learning-pipeline`
- 최종 확인 head: `dd3aebc refactor(food): Food-backend 분리 및 계획 갱신`
- 작성 목적: `53-postgresql-multimodal-health-storage-retraining-plan.md` 기준으로 진행한 PostgreSQL 중심 멀티모달 건강 저장소, regulated OCR 저장, 학습 dataset/model registry operator flow, Supabase 보안 preflight 보강 작업과 이후 식단 YOLO/Food-backend 분리 작업을 다음 작업자가 이어서 검증할 수 있게 정리한다.

## 브랜치/커밋 범위

오늘 현재 브랜치에서 확인한 작업 범위는 `257a48e`부터 `dd3aebc`까지다.

| commit | 요약 |
| --- | --- |
| `257a48e` | `feat(db): 멀티모달 저장소 Phase 1-6 추가` |
| `3f9ab4f` | `feat(api): 건강 의료 저장 API 추가` |
| `732b2a8` | `feat(medical): OCR 확인 기록 승격 추가` |
| `3982359` | `feat(learning): 학습 manifest export CLI 추가` |
| `83cdde8` | `feat(learning): 모델 promotion CLI 추가` |
| `f59e809` | `feat(learning): 모델 학습 실행 등록 CLI 추가` |
| `26c34a5` | `feat(learning): dataset version 생성 CLI 추가` |
| `c000673` | `feat(learning): annotation review import CLI 추가` |
| `4e057d2` | `fix(security): Supabase view 노출 preflight 보강` |
| `eff8102` | `feat(learning): 모델 candidate 등록 CLI 추가` |
| `44a695b` | `feat(learning): 모델 eval metric 등록 CLI 추가` |
| `5114052` | `feat(learning): 모델 retirement CLI 추가` |
| `550bf08` | `feat(learning): dataset lifecycle 전환 CLI 추가` |
| `c26b546` | `feat(meal): 식단 YOLO 데이터 파이프라인 이식` |
| `dd3aebc` | `refactor(food): Food-backend 분리 및 계획 갱신` |

## 수행한 작업

- PostgreSQL 멀티모달 저장소 기반 추가
  - backend-only media table, meal table, health profile/metric table, medical record status table, learning dataset/model registry table migration을 추가했다.
  - `src/media` 계층을 추가해 object storage, retention, deletion retry 흐름을 backend 내부 경계에서 다룰 수 있게 했다.
  - DB와 export manifest에는 raw image, raw OCR text, provider payload, public URL, signed URL, secret이 남지 않도록 sanitizer와 테스트를 함께 추가했다.

- 건강/의료 저장 API 추가
  - health profile, metric sample, daily summary, medical record, patient status 저장 API를 backend scope와 consent gate 뒤에 연결했다.
  - API 응답과 audit metadata에서 owner hash, source hash, source document id, consent snapshot, raw payload 계열 값이 외부 응답으로 새지 않도록 정리했다.
  - API contract, integration, service tests를 추가해 저장 경로와 권한 경계를 확인했다.

- regulated OCR 확인 기록 승격
  - 사용자가 확인한 regulated OCR 결과를 longitudinal medical record로 승격하는 경로를 추가했다.
  - 승격 시 owner hash와 source document id만 연결하고, raw document image, raw OCR text, provider payload, object URI, signed/public URL은 복사하지 않도록 제한했다.
  - regulated OCR focused test와 Phase regression slice로 기존 intake 흐름이 깨지지 않는지 확인했다.

- 학습 dataset/operator CLI 흐름 추가
  - privacy-reviewed learning dataset을 operator 전용 training manifest로 export하는 CLI를 추가했다.
  - model promotion, model training run registration, dataset version creation, annotation review import, model candidate registration, model eval metric registration, model retirement, dataset lifecycle transition CLI를 순차적으로 추가했다.
  - 각 CLI는 DB write 전에 unsafe state를 차단하고, stdout에는 artifact ref, storage ref, manifest hash, operator hash, reviewer hash, label snapshot, raw OCR/provider payload를 출력하지 않도록 설계했다.

- Supabase/Data API 보안 preflight 보강
  - `backend/scripts/check_learning_vector_db_security.py`에 public view와 materialized view 노출 점검을 추가했다.
  - `security_invoker` 없는 public view와 client role에 노출되는 materialized view를 fail-closed로 처리한다.
  - view definition SQL은 출력하지 않고 schema, view, role, reason만 보고하도록 제한했다.

- 식단 YOLO/RDA 데이터 파이프라인 이식
  - `origin/docs/data-yolo-food-detection`에서 식단 이미지 분석, RDA matcher, fixture, manifest, 변환 script를 현재 브랜치로 선별 이식했다.
  - UIUX 브랜치 전체 복원 대신 현재 OCR/YOLO/Ollama endpoint 구조를 유지하고, food image analysis에 필요한 backend/test/data 자산만 분리해서 가져왔다.
  - 로컬 PC 절대 경로와 모델 weight, raw OCR/provider payload, object URI, signed/public URL은 커밋하지 않는 기준을 유지했다.

- Food-backend 분리
  - 식단 이미지 분석 코드는 현재 Nutrition API endpoint에 직접 붙은 runtime 코드가 아니므로 `backend/Food-backend/` 작업 공간으로 분리했다.
  - 기존 `backend/Nutrition-backend/src/meal`과 관련 테스트는 제거하고, Food-backend 자체 `pyproject.toml`, README, unit/integration test 구조를 추가했다.
  - `docs/superpowers/plans`와 `docs/superpowers/specs`에 AIHub YOLO balanced500/yolo11s 계획 문서를 추가해 다음 식단 모델 학습 단계를 분리된 backend 기준으로 이어갈 수 있게 했다.

## 검증 결과

- Phase 1-6
  - `black --check` on changed Python files
  - `ruff check`
  - Phase 1-6 regression slice: 192 passed
  - backend unit collection: 1081 collected
  - `git diff --check`
  - `detect-secrets scan`

- Phase 7
  - Phase 1-7 regression slice: 221 passed
  - backend unit collection: 1090 collected
  - `black --check`, `ruff check`, `git diff --check`, `detect-secrets scan`

- Phase 8
  - regulated focused: 9 passed
  - Phase 1-8 regression slice: 230 passed
  - backend unit collection: 1090 collected
  - `black --check`, `ruff check`, `git diff --check`, `detect-secrets scan`

- Phase 9-13
  - `export_training_manifest` and retraining focused: 13 passed
  - `promote_model_candidate` and retraining focused: 13 passed
  - `register_model_training_run` and retraining focused: 14 passed
  - `create_learning_dataset_version` and retraining focused: 14 passed
  - `import_annotation_review` and retraining focused: 14 passed
  - backend unit collection advanced from 1094 to 1113 collected
  - each phase passed `black --check`, `ruff check`, `git diff --check`, `detect-secrets scan`

- Phase 14-18
  - `check_learning_vector_db_security` focused: 4 passed
  - `register_model_candidate` and promotion focused: 10 passed
  - `register_model_eval_results` and promotion focused: 10 passed
  - `retire_model_version` and promotion focused: 11 passed
  - `transition_learning_dataset_version` and manifest export focused: 11 passed
  - backend unit collection advanced from 1114 to 1140 collected
  - each phase passed `black --check`, `ruff check`, `git diff --check`, `detect-secrets scan`

- Meal/Food backend
  - `PYTHONPATH=backend/Nutrition-backend:backend python -m pytest backend/Nutrition-backend/tests/unit/meal backend/Nutrition-backend/tests/unit/nutrition/test_rda_matcher.py backend/Nutrition-backend/tests/integration/meal -q --no-cov`
  - `PYTHONPATH=backend/Nutrition-backend:backend python -m pytest backend/Nutrition-backend/tests/unit --collect-only -q --no-cov`
  - `python -m pytest backend/Food-backend/tests/unit/meal backend/Food-backend/tests/unit/nutrition/test_rda_matcher.py backend/Food-backend/tests/integration/meal -q --no-cov`
  - `PYTHONPATH=backend/Nutrition-backend:backend python -m pytest backend/Nutrition-backend/tests/unit --collect-only -q --no-cov`
  - `black --check`, `ruff check`, `git diff --check`, `detect-secrets scan`

- push 상태
  - `dd3aebc refactor(food): Food-backend 분리 및 계획 갱신`까지 `origin/feat/db-internal-learning-pipeline`에 push 완료

## 남은 TODO

- Supabase live preflight를 실제 환경 변수 기반으로 재실행한다.
  - `backend/scripts/check_learning_vector_db_security.py --strict`
  - 결과에는 schema/table/view/role/reason 수준의 sanitized 상태만 남긴다.
- learning/vector DB live smoke는 opt-in 환경 변수로만 실행한다.
  - raw OCR text, provider raw payload, object URI, signed/public URL, storage path는 출력하거나 문서화하지 않는다.
- operator CLI end-to-end dry-run을 synthetic/sanitized fixture로 연결한다.
  - dataset 생성
  - annotation review import
  - dataset freeze/training transition
  - training manifest export
  - training run registration
  - candidate registration
  - eval metric registration
  - promotion dry-run
  - retirement dry-run
- 실제 OCR/YOLO/Ollama 모바일 smoke와 연결할 때는 mobile endpoint 계약을 유지한다.
  - `POST /api/v1/supplements/analyze`
  - multipart field: `image`
  - form fields: `client_request_id`, `ocr_provider`
  - YOLO와 Ollama는 backend runtime 설정으로만 제어한다.
- Food-backend는 현재 Nutrition API runtime과 분리된 실험/학습 작업 공간이므로, 모바일 식단 endpoint에 연결하기 전 별도 API contract와 보안 gate를 설계한다.
- `docs/Nutrition-docs/core-algorithm/`에 추가된 알고리즘 문서는 아직 untracked 상태이므로, 적용 전 문서 내용과 현재 `src/algorithms`, `src/prediction`, `src/nutrition` 코드의 차이를 별도 구현 단계로 매핑한다.

## 주의할 파일/커밋 제외 항목

- `.env`, secret, ngrok token/URL, raw OCR text, provider raw payload, image bytes, object URI, signed URL, public URL은 문서와 커밋에 포함하지 않는다.
- 현재 untracked 항목은 이번 문서 작업과 무관하므로 건드리지 않는다.
  - `.omc/`
  - `docs/Nutrition-docs/core-algorithm/`
  - `mobile/assets/mascot/Mascot_AppIcon_Rebuild_Assets/`
- `HorangEe02/Project_yeong` 개인 repo와 team repo 작업을 섞지 않는다.
- feature branch는 계속 `origin/feat/db-internal-learning-pipeline`에 push한다.
