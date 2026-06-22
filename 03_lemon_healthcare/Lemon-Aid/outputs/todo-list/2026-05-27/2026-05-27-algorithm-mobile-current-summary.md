# 2026-05-27 Algorithm/Mobile 현재 작업 요약

## 기준 정보

- 작성일: 2026-05-27
- 대상 repo: `/Users/yeong/99_me/00_github/03_lemon_healthcare/Lemon-Aid`
- 작업 브랜치: `feat/db-internal-learning-pipeline`
- remote: `origin` = `https://github.com/Lemon-Aid-KDT/Lemon-sin.git`
- 현재 HEAD: `54e4656 fix(nutrition): 사용자 노출 문구 안전화`
- 작성 목적: 오늘 현재까지 완료된 phase commit과 남은 WIP를 분리해 다음 작업에서 stage/commit/push 대상을 혼동하지 않도록 기록한다.

## 브랜치/커밋 범위

| 범위 | 상태 | 내용 |
| --- | --- | --- |
| `257a48e` - `dd3aebc` | push 완료 | PostgreSQL/Supabase 저장소, regulated OCR, learning/model registry CLI, Food-backend 분리 |
| `1b49bea` - `1620400` | push 완료 | 2026-05-27 todo/checkpoint 문서 정리 |
| `703bee2` | push 완료 | core algorithm 1차 정렬: BMI, 활동, BMR/TDEE, 체중 예측, 영양 진단, 영양제 안전 기준 |
| `1a40567` | push 완료 | 목적별 영양제 matrix, 약물/질환 caution, HRrest, alcohol kcal 보강 |
| `faec01c` | push 완료 | 영양 상호작용 warning과 활동 percentile sample guard 보강 |
| `8659cee` | push 완료 | 임신/수유, 약물 복용, 고위험 만성질환 자동 평가 보류 및 referral route |
| `54e4656` | push 완료 | 사용자 노출 문구에서 진단/치료/효능 오해 소지가 있는 표현 완화 |
| working tree | 진행 중 | KDRIs 노인 age-band routing 회귀 테스트 1건 추가, 아직 미커밋 |

## 수행한 작업

- 팀 repo 작업 경계를 유지했다.
  - 작업 경로는 `/Users/yeong/99_me/00_github/03_lemon_healthcare/Lemon-Aid`로 고정했다.
  - 개인 repo와 archive repo는 참고만 하고 현재 브랜치 commit/push 대상에서 제외했다.

- Docker/OCR/mobile smoke 상태를 정리했다.
  - stale 컨테이너와 현재 Docker Compose runtime을 구분했다.
  - `lemon-aid-demo`, `lemon-aid-team-backend`, `lemon-postgres`처럼 혼동을 만드는 오래된 컨테이너는 현재 runtime 기준에서 제외하거나 정리 대상으로 분류했다.
  - Android emulator smoke는 `LEMON_API_BASE_URL=http://10.0.2.2:8000/api/v1` 기준으로 이어간다.
  - OCR provider selector는 `configured`, `paddleocr`, `google_vision`, `clova`만 유지한다.
  - YOLO/Ollama는 mobile fake endpoint가 아니라 backend runtime 설정으로 제어한다.

- 17 Pro UIUX와 backend endpoint 연결 방향을 유지했다.
  - 참고 브랜치 `origin/feat/mobile-dashboard-redesign`의 5-tab UI, yellow theme, plus action palette, camera UX를 기준으로 삼았다.
  - 현재 backend-connected app 구조와 API contract는 보존한다.
  - supplement 분석 endpoint는 `POST /api/v1/supplements/analyze`, multipart field `image`, form field `client_request_id`, `ocr_provider` 계약을 유지한다.
  - mock analysis result로 빠지지 않고 OCR preview, review/confirmation, registration, local Ollama explanation 흐름으로 연결하는 방향을 유지한다.

- core algorithm 문서 적용을 phase 단위로 진행했다.
  - BMI, activity score, BMR/TDEE, weight prediction, nutrition diagnosis, supplement comprehensive safety branch를 현재 backend 코드에 반영했다.
  - 특수 프로필은 자동 영양 평가보다 전문가 상담/확인 route를 우선하도록 보강했다.
  - 사용자에게 노출되는 문구는 진단/치료/효능 단정이 되지 않도록 safety wording을 조정했다.

- 현재 미커밋 WIP를 진행했다.
  - `backend/Nutrition-backend/tests/unit/nutrition/test_kdris_analysis.py`에 65세 이상/75세 이상 Vitamin D AI 기준 routing 회귀 테스트를 추가했다.
  - age 64 female과 age 75 female의 Vitamin D AI 기준값 차이를 고정해 성인 기준 fallback 회귀를 막는 목적이다.

## 검증 결과

- 최신 WIP 테스트 변경 기준으로 다음 검증을 실행했다.
  - `backend/Nutrition-backend/tests/unit/nutrition/test_kdris_analysis.py`: 16 passed
  - `backend/Nutrition-backend/tests/unit/nutrition` + `backend/Nutrition-backend/tests/unit/services/test_nutrition_diagnosis.py`: 52 passed
  - `backend/Nutrition-backend/tests/unit`: 1168 passed

- 오늘 algorithm phase별로 반복한 quality gate:
  - `black`
  - `ruff check`
  - `git diff --check`
  - `detect-secrets scan`
  - focused pytest
  - backend unit pytest

- 현재 문서 작성 시점의 working tree 주의점:
  - KDRIs 노인 routing 테스트 파일은 아직 미커밋 상태다.
  - `.omc/`와 `mobile/assets/mascot/Mascot_AppIcon_Rebuild_Assets/`는 이번 작업과 무관한 untracked 항목이다.

## 남은 TODO

1. KDRIs 노인 age-band routing 테스트 phase를 마무리한다.
   - `black --check backend/Nutrition-backend/tests/unit/nutrition/test_kdris_analysis.py`
   - `ruff check backend/Nutrition-backend/tests/unit/nutrition/test_kdris_analysis.py`
   - `git diff --check`
   - `detect-secrets scan backend/Nutrition-backend/tests/unit/nutrition/test_kdris_analysis.py`
   - commit 예시: `test(nutrition): 노인 KDRIs 라우팅 고정`

2. Android OCR smoke를 이어간다.
   - Android Studio emulator에서 camera/gallery 입력을 다시 확인한다.
   - provider가 실제 backend에 도달하는지 먼저 보고, ingredients 후보가 비면 endpoint보다 OCR/parser/domain correction 품질을 분리 확인한다.
   - Google Vision은 credential 상태와 별도로 판단한다.

3. 17 Pro UIUX 정합성을 다시 점검한다.
   - plus action palette가 사라지지 않는지 확인한다.
   - 영양제/식단 카메라 모드 전환 UI가 참고 브랜치 화면과 맞는지 확인한다.
   - 현재 endpoint 연결을 유지하면서 mock-only screen은 제거하거나 neutral placeholder로 제한한다.

4. Supabase live smoke는 별도 gate로 진행한다.
   - local ignored `.env`만 사용한다.
   - `check_learning_vector_db_security.py --strict`를 먼저 실행한다.
   - storage smoke는 명시 opt-in 환경변수로만 실행한다.

## 주의할 파일/커밋 제외 항목

- 절대 커밋 금지:
  - `.env`
  - Supabase service role key
  - ngrok token/public URL
  - raw OCR text
  - provider raw payload
  - image bytes
  - storage object URI/path
  - signed URL/public URL
  - 개인 이미지/개인 로컬 private metadata

- 현재 stage 금지 항목:
  - `.omc/`
  - `mobile/assets/mascot/Mascot_AppIcon_Rebuild_Assets/`

- 참고 문서/공식 근거:
  - KDRIs 2020, Ministry of Health and Welfare: `https://www.mohw.go.kr/board.es?mid=a10411010100&bid=0019&act=view&list_no=362385`
  - Dietary Reference Intakes applications, NCBI Bookshelf: `https://www.ncbi.nlm.nih.gov/books/NBK222890/`
  - NIH ODS Vitamin K fact sheet: `https://ods.od.nih.gov/factsheets/VitaminK-HealthProfessional/`
  - NHLBI DASH eating plan: `https://www.nhlbi.nih.gov/education/dash-eating-plan`
