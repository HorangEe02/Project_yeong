# 2026-05-27 다음 Phase TODO

## 기준 정보

- 작성일: 2026-05-27
- 대상 repo: `/Users/yeong/99_me/00_github/03_lemon_healthcare/Lemon-Aid`
- 작업 브랜치: `feat/db-internal-learning-pipeline`
- 현재 HEAD: `703bee2 feat(algorithm): 건강 계산 기준 정렬`
- 작성 목적: 현재 미커밋 알고리즘 보강분, Android OCR smoke, Supabase live preflight를 순서대로 이어가기 위한 실행 TODO를 남긴다.

## 브랜치/커밋 범위

- 이미 push된 오늘자 기준점: `703bee2`
- 다음 저장 단위: core algorithm 추가 보강 WIP
- 커밋/푸시 대상 브랜치: `origin/feat/db-internal-learning-pipeline`

## 수행한 작업

- core algorithm 문서 기반 구현을 1차로 반영했다.
  - 건강 계산 기준 정렬 phase는 commit `703bee2`로 push 완료했다.
  - 이후 추가 보강으로 목적별 영양제 매트릭스, 약물-영양제 caution, HRrest 기반 target HR, alcohol kcal 변환을 진행 중이다.

- Android smoke 기준을 정리했다.
  - Android emulator는 backend 접근에 `10.0.2.2` loopback을 사용한다.
  - Flutter debug run은 `LEMON_API_BASE_URL=http://10.0.2.2:8000/api/v1` 기준으로 맞춘다.
  - iPhone 실기기/ngrok smoke는 보류하고 Android Studio 우선으로 진행한다.

- endpoint 연결 문제와 OCR 품질 문제를 분리했다.
  - 요청이 backend에 도달하고 provider가 실행되면 endpoint 자체는 1차 원인이 아니다.
  - ingredients 후보가 비면 OCR text 품질, parser/domain correction, YOLO ROI, provider 비교 순서로 본다.
  - `YOLO ROI: off`는 backend `ENABLE_VISION_CLASSIFIER=false` 상태라면 정상이다.

## 검증 결과

- 현재 WIP 기준 확인된 gate 상태:
  - `black --check`: 통과
  - `ruff check`: `backend/Nutrition-backend/src/prediction/weight.py`의 magic value blocker 1건

- 아직 완료하지 않은 gate:
  - WIP 수정 후 focused pytest 재실행
  - full backend unit 또는 unit collection
  - `git diff --check`
  - `detect-secrets scan` on changed files
  - commit/push

## 남은 TODO

### Phase 1: 알고리즘 WIP 마무리

1. `backend/Nutrition-backend/src/prediction/weight.py` lint blocker를 수정한다.
2. alcohol volume + ABV 변환 로직이 selector path와 API path에서 중복/누락 없이 반영되는지 확인한다.
3. `wellness_goal_targets`가 API schema, analysis result, test fixture에서 일관되게 보이는지 확인한다.
4. safety caution 우선순위가 high-risk profile warning을 먼저 노출하는지 확인한다.

### Phase 2: Backend 검증

1. focused tests를 실행한다.
   - `backend/Nutrition-backend/tests/unit/algorithms`
   - `backend/Nutrition-backend/tests/unit/prediction`
   - `backend/Nutrition-backend/tests/unit/nutrition`
2. supplement comprehensive와 parser/schema regression을 다시 확인한다.
3. 가능한 경우 full backend unit을 실행한다.
4. 품질 gate와 secret scan을 통과시킨다.

### Phase 3: 저장 Commit/Push

1. 변경 파일 중 알고리즘 WIP와 관련된 파일만 stage한다.
2. unrelated untracked 항목은 stage하지 않는다.
3. 팀 규칙에 맞춰 commit한다.
   - 예시: `feat(algorithm): 목적별 안전 분기 보강`
4. `origin/feat/db-internal-learning-pipeline`로 push한다.

### Phase 4: Android OCR Smoke 재개

1. Docker backend가 최신 code를 반영 중인지 확인한다.
2. Android emulator에서 Flutter 앱을 실행한다.
3. provider selector별로 OCR analyze 요청을 확인한다.
   - `configured`
   - `paddleocr`
   - `clova`
   - `google_vision`은 credential 상태를 별도 판단한다.
4. OCR preview에서 ingredients가 0이면 endpoint보다 parser/domain correction 문제로 분기한다.
5. local Ollama explanation은 기존 recommendation explanation endpoint로만 확인한다.

### Phase 5: Supabase Live Preflight

1. local ignored `.env`만 사용한다.
2. read-only/security preflight를 먼저 실행한다.
3. storage round-trip은 live gate가 명시된 경우에만 실행한다.
4. object URI, signed URL, service role key, provider payload는 문서와 commit에 남기지 않는다.

## 주의할 파일/커밋 제외 항목

- stage 금지:
  - `.omc/`
  - `mobile/assets/mascot/Mascot_AppIcon_Rebuild_Assets/`

- 보안상 commit 금지:
  - `.env`
  - ngrok authtoken 또는 public tunnel URL
  - Supabase service role key
  - raw OCR text
  - provider raw payload
  - image bytes
  - object URI/path
  - signed/public URL

- 협업 규칙:
  - branch: `feat/db-internal-learning-pipeline`
  - commit: Conventional Commits 형식
  - `--no-verify` 금지
  - lease 없는 force push 금지
  - feature -> develop은 Squash, develop -> main은 Merge commit

