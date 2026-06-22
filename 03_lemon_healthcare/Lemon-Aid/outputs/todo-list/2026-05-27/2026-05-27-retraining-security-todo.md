# 2026-05-27 재학습/보안 TODO

## 기준 정보

- 작성일: 2026-05-27
- 대상 repo: `/Users/yeong/99_me/00_github/03_lemon_healthcare/Lemon-Aid`
- 작업 브랜치: `feat/db-internal-learning-pipeline`
- 기준 head: `dd3aebc refactor(food): Food-backend 분리 및 계획 갱신`
- 기준 문서: `docs/Nutrition-docs/53-postgresql-multimodal-health-storage-retraining-plan.md`
- 목적: 오늘 추가된 backend 저장소와 operator CLI를 다음 단계 live smoke, Supabase 보안 점검, OCR/YOLO/Ollama endpoint 검증으로 이어가기 위한 TODO를 정리한다.

## 브랜치/커밋 범위

- 현재 요약 대상: `257a48e`부터 `dd3aebc`까지
- 이 문서는 추가 구현 코드가 아니라, 다음 실행 순서와 보안 금지 항목을 고정하기 위한 repo-local TODO다.

## 수행한 작업

- backend-only multimodal storage 경계를 만들었다.
  - media object lifecycle, meal image analysis, health profile/metric, medical record, learning dataset/model registry를 PostgreSQL 중심으로 저장할 수 있게 했다.
  - Supabase Storage와 vector DB를 사용할 때도 client-visible ref나 raw payload가 외부 응답에 섞이지 않도록 backend 경계를 유지했다.

- regulated OCR 결과의 저장 경계를 분리했다.
  - 사용자가 확인한 OCR 결과만 medical record로 승격한다.
  - 확인 전 raw OCR/provider payload는 장기 medical store로 복사하지 않는다.

- retraining operator CLI 흐름을 만들었다.
  - dataset version 생성
  - annotation review import
  - dataset lifecycle transition
  - training manifest export
  - model training run registration
  - model candidate registration
  - eval metric registration
  - promotion dry-run/apply
  - retirement dry-run/apply

- 보안 preflight를 강화했다.
  - public table/RLS/revoke 점검에 더해 public view/materialized view 노출을 점검한다.
  - client role에서 조회 가능한 view 계층을 fail-closed로 다룬다.

- 식단 YOLO/Food-backend 작업을 분리했다.
  - food image analysis 코드는 `backend/Food-backend/`로 분리되어 현재 Nutrition-backend retraining storage와 직접 결합하지 않는다.
  - 식단 YOLO 학습 계획 문서는 `docs/superpowers/`에 별도 보관했다.

## 검증 결과

- 오늘 추가된 CLI와 보안 preflight는 focused pytest로 검증했다.
- backend unit collection은 오늘 작업 전후로 `1081 collected`에서 `1140 collected`까지 증가한 상태를 확인했다.
- 각 phase commit 전에 다음 게이트를 반복 실행했다.
  - `black --check`
  - `ruff check`
  - focused pytest/regression slice
  - backend unit `--collect-only`
  - `git diff --check`
  - `detect-secrets scan`
- 최신 커밋 `dd3aebc`까지 `origin/feat/db-internal-learning-pipeline`에 push 완료 상태다.

## 남은 TODO

1. Supabase live read-only/security preflight
   - `.env`는 local ignored 파일로만 사용한다.
   - `check_learning_vector_db_security.py --strict`를 실제 Supabase/PostgreSQL 연결로 실행한다.
   - 결과는 sanitized status, schema, table/view, role, reason 수준으로만 기록한다.

2. Storage live smoke
   - 명시 opt-in 환경 변수로만 실행한다.
   - smoke object는 생성 후 삭제한다.
   - 출력과 문서에는 bucket 내부 object ref, signed URL, public URL을 남기지 않는다.

3. Vector DB live smoke
   - 필요하면 storage smoke와 분리된 opt-in script로 synthetic vector upsert/query/delete를 검증한다.
   - 실제 OCR text, 사용자 이미지, provider payload 기반 vector는 smoke에 사용하지 않는다.

4. Operator CLI end-to-end dry-run
   - sanitized fixture로 dataset lifecycle 전체를 이어서 실행한다.
   - promotion apply는 metric rule과 rollback 조건을 다시 확인한 뒤 별도 단계로 진행한다.

5. OCR/YOLO/Ollama endpoint 연결 재검증
   - Android emulator는 `LEMON_API_BASE_URL=http://10.0.2.2:8000/api/v1`을 사용한다.
   - physical device는 token-gated gateway와 HTTPS tunnel을 사용하되 token/URL은 커밋하지 않는다.
   - OCR provider 값은 `configured`, `paddleocr`, `google_vision`, `clova`만 사용한다.
   - YOLO ROI는 backend `ENABLE_VISION_CLASSIFIER`, Ollama assist는 backend `ENABLE_MULTIMODAL_LLM`으로만 제어한다.

6. 품질 판단 순서
   - endpoint 도달 여부와 provider 선택값부터 확인한다.
   - provider가 정상 실행되는데 ingredients 후보가 비면 parser/domain correction을 먼저 본다.
   - parser가 정상인데 텍스트 품질이 낮으면 이미지 품질, YOLO ROI, provider 비교, PaddleOCR fine-tuning 순서로 판단한다.

7. Food-backend 후속 분리 검증
   - Food-backend는 Nutrition-backend와 별도 test target으로 유지한다.
   - 식단 endpoint를 모바일에 붙이기 전 raw image 저장, OCR/vision payload redaction, model artifact 경로, auth/consent 정책을 먼저 고정한다.
   - 모델 weight와 로컬 학습 산출물은 git에 넣지 않는다.

## 주의할 파일/커밋 제외 항목

- 문서와 커밋에 포함 금지:
  - `.env`
  - Supabase service role key
  - ngrok token/public URL
  - raw OCR text
  - provider raw payload
  - image bytes
  - storage object URI/path
  - signed URL/public URL
  - owner hash, reviewer hash, operator hash 원문
- 현재 untracked 항목은 이번 TODO 문서 대상이 아니다.
  - `.omc/`
  - `docs/Nutrition-docs/core-algorithm/`
  - `mobile/assets/mascot/Mascot_AppIcon_Rebuild_Assets/`
- Android/iOS UIUX 이식 작업과 backend retraining storage 작업은 같은 브랜치에 있지만, 커밋과 검증 단위는 분리해 유지한다.
- feature branch push 대상은 계속 `origin/feat/db-internal-learning-pipeline`이다.
