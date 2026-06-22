# 2026-05-27 현재 작업 진행 Snapshot

## 기준 정보

- 작성일: 2026-05-27
- 대상 repo: `/Users/yeong/99_me/00_github/03_lemon_healthcare/Lemon-Aid`
- 작업 브랜치: `feat/db-internal-learning-pipeline`
- remote: `origin` = `https://github.com/Lemon-Aid-KDT/Lemon-sin.git`
- 현재 HEAD: `703bee2 feat(algorithm): 건강 계산 기준 정렬`
- 작성 목적: 오늘 현재까지 완료된 push 범위와 미커밋 WIP 범위를 분리해 기록하고, 다음 작업에서 stage/commit 대상을 잘못 섞지 않도록 남긴다.

## 브랜치/커밋 범위

| 범위 | 상태 | 내용 |
| --- | --- | --- |
| `257a48e` - `dd3aebc` | push 완료 | PostgreSQL/Supabase 저장소, regulated OCR, learning/model registry CLI, Food-backend 분리 |
| `1b49bea` - `51b5657` | push 완료 | 2026-05-27 todo/checkpoint 문서 정리 |
| `703bee2` | push 완료 | core algorithm 1차 정렬: BMI, 활동, BMR/TDEE, 체중 예측, 영양 진단, 영양제 안전 기준 |
| working tree | 진행 중 | core algorithm 추가 보강: 목적별 영양제 매트릭스, 약물-영양제 caution, HRrest, alcohol kcal 변환 |

## 수행한 작업

- 팀 repo 기준 작업 범위를 유지했다.
  - 작업 경로는 `/Users/yeong/99_me/00_github/03_lemon_healthcare/Lemon-Aid`로 고정했다.
  - 개인 repo 또는 archive repo에서 직접 커밋하지 않는 규칙을 유지했다.

- Docker/OCR/mobile smoke 정리 흐름을 진행했다.
  - stale Docker 컨테이너와 혼동되는 container 이름을 분리해서 보았다.
  - Android emulator smoke는 `LEMON_API_BASE_URL=http://10.0.2.2:8000/api/v1` 기준으로 이어가기로 정리했다.
  - OCR provider selector는 `configured`, `paddleocr`, `google_vision`, `clova`만 유지한다.
  - YOLO/Ollama는 mobile fake endpoint가 아니라 backend runtime 설정으로 제어한다.

- 17 Pro UIUX와 현재 endpoint 연결 방향을 정리했다.
  - `origin/feat/mobile-dashboard-redesign`의 UIUX를 참고하되, backend-connected 구조와 API contract를 보존하는 방향으로 정했다.
  - `POST /api/v1/supplements/analyze`, multipart field `image`, form field `client_request_id`, `ocr_provider` 계약을 유지한다.
  - mock analysis result로 빠지지 않고 review/confirmation/registration 흐름으로 연결하는 방향을 유지한다.

- core algorithm 1차 정렬을 완료하고 push했다.
  - BMI 분류 기준과 건강 계산 기준을 문서 기반으로 정리했다.
  - 활동 점수, BMR/TDEE, 체중 예측, 영양 진단, 영양제 종합 분석의 기본 계약을 보강했다.
  - commit `703bee2 feat(algorithm): 건강 계산 기준 정렬`로 push 완료했다.

- 현재 추가 보강 WIP를 진행 중이다.
  - `SupplementComprehensiveAnalysis`에 `wellness_goal_targets`를 추가했다.
  - 눈 건강, 간 건강, 피로 회복, 면역, 수면, 장 건강 목적별 영양제 후보 분기를 추가했다.
  - 흡연, 임신, 음주, warfarin, levothyroxine, metformin, SSRI/MAOI, statin, chemo/methotrexate, CKD, liver disease 관련 caution을 구체화했다.
  - caution 우선순위는 profile safety warning이 generic matrix warning에 묻히지 않도록 조정했다.
  - activity target HR은 HRrest가 있으면 Karvonen HRR 기반으로 계산하도록 확장했다.
  - 7일 resting HR moving median helper와 음주 다음날 outlier 제외 플래그를 추가했다.
  - 체중 예측 요청에 alcohol volume + ABV 입력을 추가하고 kcal 변환 helper를 연결했다.

## 검증 결과

- 현재 WIP 파일 기준 `black --check` 결과:
  - 대상 10개 파일 통과

- 현재 WIP 파일 기준 `ruff check` 결과:
  - 실패 1건
  - 위치: `backend/Nutrition-backend/src/prediction/weight.py`
  - 사유: `PLR2004` magic value `100`을 상수로 분리해야 한다.

- 이전 실행 기준 focused test 결과:
  - supplement comprehensive focused tests: 통과
  - algorithms/metabolism focused tests: 통과
  - broader nutrition/prediction regression slice: 통과
  - 최종 gate는 아직 재실행 전이다.

## 남은 TODO

1. WIP lint blocker를 먼저 해결한다.
   - `backend/Nutrition-backend/src/prediction/weight.py`의 ABV 기준값 `100`을 `MAX_ABV_PERCENT` 같은 상수로 분리한다.
   - 같은 상수를 validation과 kcal 변환식에 함께 사용한다.

2. focused test를 다시 실행한다.
   - activity algorithm tests
   - metabolism/weight prediction tests
   - supplement comprehensive tests
   - nutrition/prediction regression slice

3. 전체 backend unit 또는 가능한 범위의 unit gate를 실행한다.
   - 최소 `backend/Nutrition-backend/tests/unit --collect-only`
   - 가능하면 full backend unit `-q --no-cov`

4. quality/security gate를 실행한다.
   - `black --check`
   - `ruff check`
   - `git diff --check`
   - `detect-secrets scan` on changed tracked text files

5. WIP 구현 검증 후 phase commit/push를 진행한다.
   - 예상 메시지: `feat(algorithm): 목적별 안전 분기 보강`
   - push 대상: `origin/feat/db-internal-learning-pipeline`

## 주의할 파일/커밋 제외 항목

- 현재 untracked 중 이번 작업과 무관하게 stage 금지:
  - `.omc/`
  - `mobile/assets/mascot/Mascot_AppIcon_Rebuild_Assets/`

- 항상 커밋 금지:
  - `.env`
  - secret
  - raw OCR text
  - provider raw payload
  - image bytes
  - storage object URI/path
  - signed URL/public URL
  - ngrok token/public URL
  - 개인 로컬 절대 경로가 포함된 private metadata

