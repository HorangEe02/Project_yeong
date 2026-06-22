# 2026-05-28 운동 심박 TDEE 보정 적용 요약

## 기준 정보

- 작성일: 2026-05-28
- 대상 repo: `/Users/yeong/99_me/00_github/03_lemon_healthcare/Lemon-Aid`
- 작업 브랜치: `feat/db-internal-learning-pipeline`
- 적용 커밋: `96180af feat(prediction): 운동 심박 TDEE 보정 추가`
- 기준 문서:
  - `docs/Nutrition-docs/core-algorithm/03-bmr-tdee.md`
  - `docs/Nutrition-docs/core-algorithm/04-weight-prediction.md`
- 확인 근거:
  - Keytel et al. 2005 heart-rate energy expenditure equation: https://pubmed.ncbi.nlm.nih.gov/15966347/

## 브랜치/커밋 범위

- 직전 기준 head: `de39beb docs(todo): 2026-05-28 작업 요약 추가`
- 이번 phase head: `96180af feat(prediction): 운동 심박 TDEE 보정 추가`
- push 대상: `origin/feat/db-internal-learning-pipeline`
- push 상태: `96180af` 팀 remote push 완료

## 수행한 작업

- `backend/Nutrition-backend/src/algorithms/metabolism.py`에 평균 운동 심박 기반 운동 열량 helper를 추가했다.
  - `calculate_exercise_kcal_from_heart_rate()`
  - Keytel 2005 남녀별 kJ/min 회귀식을 사용하고 kcal로 환산한다.
  - 낮은 심박 잡음으로 음수가 나오는 경우 TDEE를 낮추지 않도록 0 kcal로 제한한다.
- `calculate_tdee()`가 optional 심박 입력을 받아 기존 BMR/활동계수 결과에 운동 열량을 더하도록 확장했다.
  - `exercise_average_heart_rate_bpm`
  - `heart_rate_exercise_minutes`
  - 심박 보정에는 `weight_kg`, `age`, `sex`를 함께 요구한다.
- `WeightPredictionRequest`에 심박 입력 필드를 추가하고 pair validation을 고정했다.
  - 평균 운동 심박만 있거나 시간만 있는 요청은 validation error로 거부한다.
- static weight prediction, Hall-lite baseline, selector, 저장 서비스 경로가 모두 같은 심박 기반 TDEE 보정을 사용하도록 연결했다.
- API request example에 심박 필드를 추가했다.
- audit metadata에는 raw heart-rate/minutes 값을 남기지 않고 `exercise_heart_rate_used` boolean만 기록하도록 제한했다.
- safety warning에 Keytel 2005 회귀식 기반 보정 사용 사실을 명시했다.
- 테스트를 추가해 심박 kcal 계산, TDEE 증가, request validation, static/Hall-lite selector 연동을 고정했다.

## 검증 결과

- focused metabolism/selector tests: 52 passed
- algorithms + prediction tests: 95 passed
- analysis result / nutrition diagnosis service tests: 7 passed
- full backend unit: 1212 passed
- `black --check` on changed files: passed
- `ruff check` on changed files: passed
- `git diff --check`: passed
- `detect-secrets scan` on changed files: no findings
- `96180af` push 완료

## 남은 TODO

1. `core-algorithm/03-bmr-tdee.md`
   - VO2max 추정 또는 HRR%별 정밀 보정은 아직 적용하지 않았다.
   - 현재 phase는 평균 운동 심박 기반 kcal add-on까지만 범위를 제한했다.

2. wearable/mobile source
   - 평균 운동 심박 입력의 source가 wearable sync인지 수동 입력인지 표시하는 신뢰도 레이어가 필요하다.
   - mobile에서 심박 보정 safety warning을 어떻게 노출할지 정해야 한다.

3. `core-algorithm/04-weight-prediction.md`
   - 사용자별 posterior 또는 learned coefficient 기반 보정은 아직 남아 있다.
   - 예측 mismatch warning 이후 dashboard/card UI 반영은 mobile 작업으로 남아 있다.

## 주의할 파일/커밋 제외 항목

- 커밋 금지:
  - `.env`
  - Supabase service role key
  - ngrok token/public URL
  - raw OCR text
  - provider raw payload
  - image bytes
  - object URI/path
  - signed URL/public URL
  - 개인 로컬 절대 경로가 포함된 metadata
- 현재 유지 중인 untracked 제외 항목:
  - `.omc/`
  - `mobile/assets/mascot/Mascot_AppIcon_Rebuild_Assets/`
- 음식 YOLO `best.pt`는 로컬 ignored artifact로 유지한다.
  - `runs/food_yolo/exp01_yolov8n_baseline_pc1_b48_w8_cache_disk_det_true/weights/best.pt`
