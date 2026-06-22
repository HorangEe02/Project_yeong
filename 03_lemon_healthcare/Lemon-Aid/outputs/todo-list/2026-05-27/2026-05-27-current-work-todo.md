# 2026-05-27 현재 작업 Rollup TODO

## 기준 정보

- 작성일: 2026-05-27
- 대상 repo: `/Users/yeong/99_me/00_github/03_lemon_healthcare/Lemon-Aid`
- 작업 브랜치: `feat/db-internal-learning-pipeline`
- 현재 기준 head: `dd3aebc refactor(food): Food-backend 분리 및 계획 갱신`
- 작성 목적: 오늘 진행된 backend 저장소, retraining operator, mobile/OCR smoke, 식단 YOLO/Food-backend 분리, 신규 core algorithm 문서 적용 대기 상태를 다음 작업자가 바로 이어갈 수 있게 정리한다.

## 브랜치/커밋 범위

| 범위 | 내용 |
| --- | --- |
| `257a48e` - `550bf08` | PostgreSQL 멀티모달 저장소, regulated OCR 승격, learning dataset/model registry CLI, Supabase 보안 preflight |
| `c26b546` | 식단 YOLO/RDA 데이터 파이프라인을 현재 브랜치로 선별 이식 |
| `dd3aebc` | 식단 이미지 분석 코드를 `backend/Food-backend/`로 분리하고 AIHub YOLO 계획 문서 갱신 |

## 수행한 작업

- PostgreSQL/Supabase 저장소 경계
  - backend-only media, meal, health profile/metric, medical record, learning dataset/model registry 흐름을 추가했다.
  - raw OCR text, provider payload, image bytes, object URI, signed/public URL을 외부 응답과 manifest에서 배제하는 sanitizer/test 흐름을 유지했다.

- retraining operator CLI
  - dataset version 생성, annotation review import, lifecycle transition, training manifest export, training run registration, candidate/eval/promotion/retirement 흐름을 추가했다.
  - operator stdout에는 manifest hash, operator hash, reviewer hash, raw payload 계열 값을 출력하지 않도록 제한했다.

- mobile/OCR/YOLO/Ollama smoke 기반
  - 17 Pro UIUX 스타일과 현재 endpoint 계약을 맞추는 작업을 진행했다.
  - Android emulator는 `LEMON_API_BASE_URL=http://10.0.2.2:8000/api/v1` 기준으로 테스트한다.
  - `POST /api/v1/supplements/analyze`, multipart field `image`, form field `client_request_id`, `ocr_provider` 계약을 유지한다.

- 식단 YOLO/Food-backend 분리
  - 식단 이미지 분석과 RDA matcher는 현재 Nutrition-backend runtime과 혼동되지 않도록 `backend/Food-backend/`로 분리했다.
  - 데이터/manifest/script와 AIHub YOLO 계획 문서는 유지하되 모델 weight, 로컬 절대 경로, raw vision payload는 커밋하지 않았다.

- 신규 core algorithm 문서 적용 대기
  - `docs/Nutrition-docs/core-algorithm/`는 현재 untracked 상태다.
  - 적용 전 BMI, activity score, BMR/TDEE, weight prediction, nutrition diagnosis, goal matrix, chronic disease, smoking/alcohol rationale 문서를 현재 코드와 매핑해야 한다.

## 검증 결과

- retraining/security phases
  - focused pytest와 backend unit collection을 phase별로 실행했다.
  - `black --check`, `ruff check`, `git diff --check`, `detect-secrets scan`을 각 phase commit 전에 반복했다.

- meal/Food backend
  - Nutrition-backend 포팅 상태에서 meal/RDA focused test와 unit collection을 실행했다.
  - Food-backend 분리 후 Food-backend focused test, Nutrition-backend unit collection, formatting/lint/security gate를 commit body에 기록했다.

- push 상태
  - `dd3aebc refactor(food): Food-backend 분리 및 계획 갱신`까지 `origin/feat/db-internal-learning-pipeline`에 push 완료 상태다.

## 남은 TODO

1. 오늘자 문서 보강 커밋
   - 이 문서와 기존 `outputs/todo-list/2026-05-27/` 문서 갱신분만 stage한다.
   - `.omc/`, `docs/Nutrition-docs/core-algorithm/`, `mobile/assets/mascot/Mascot_AppIcon_Rebuild_Assets/`는 이번 문서 커밋에 포함하지 않는다.

2. core algorithm 문서 적용
   - `docs/Nutrition-docs/core-algorithm/` 전체 내용을 먼저 읽는다.
   - 현재 `backend/Nutrition-backend/src/algorithms`, `src/prediction`, `src/nutrition` 코드와 test gap을 매핑한다.
   - 적용 단위는 BMI/활동/BMR-TDEE/체중 예측/영양 진단으로 나누고, 각 단위마다 focused test를 추가한다.

3. Android OCR smoke
   - backend, Android emulator, Flutter app의 base URL과 provider selector 전달을 다시 확인한다.
   - provider가 실행되는데 ingredients 후보가 비면 endpoint 문제가 아니라 parser/domain correction부터 본다.

4. Supabase live preflight
   - local ignored `.env`만 사용한다.
   - `check_learning_vector_db_security.py --strict`를 sanitized 출력 기준으로 실행한다.
   - object URI, signed/public URL, service role key, ngrok token/URL은 문서에 남기지 않는다.

5. Food-backend 후속 계획
   - 식단 endpoint를 모바일에 붙이기 전 API contract, auth/consent, retention, model loading 정책을 먼저 문서화한다.
   - 학습 데이터와 모델 산출물은 git이 아니라 외부 artifact 관리 경로를 사용한다.

## 주의할 파일/커밋 제외 항목

- 커밋 금지:
  - `.env`
  - Supabase service role key
  - ngrok token/public URL
  - raw OCR text
  - provider raw payload
  - image bytes
  - object URI/path
  - signed/public URL
  - local private absolute path가 포함된 metadata
- 현재 untracked 항목:
  - `.omc/`
  - `docs/Nutrition-docs/core-algorithm/`
  - `mobile/assets/mascot/Mascot_AppIcon_Rebuild_Assets/`
- push 대상:
  - `origin/feat/db-internal-learning-pipeline`
