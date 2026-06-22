# 2026-05-28 보행 cadence TDEE 보정 적용 요약

## 기준 정보

- 작성일: 2026-05-28
- 대상 repo: `/Users/yeong/99_me/00_github/03_lemon_healthcare/Lemon-Aid`
- 작업 브랜치: `feat/db-internal-learning-pipeline`
- 적용 커밋: `953c492 feat(prediction): 보행 cadence TDEE 보정 추가`
- 기준 문서:
  - `docs/Nutrition-docs/core-algorithm/03-bmr-tdee.md`
  - `docs/Nutrition-docs/core-algorithm/04-weight-prediction.md`
- 확인 근거:
  - Tudor-Locke et al. 2018 cadence intensity review: https://doi.org/10.1136/bjsports-2017-097628
  - CADENCE-Adults 2019 cadence thresholds: https://doi.org/10.1186/s12966-019-0769-6
  - 2011 Compendium of Physical Activities MET reference: https://doi.org/10.1249/MSS.0b013e31821ece12

## 브랜치/커밋 범위

- 직전 기준 head: `44eb337 docs(todo): 임신 비타민A 분기 요약`
- 이번 phase head: `953c492 feat(prediction): 보행 cadence TDEE 보정 추가`
- push 대상: `origin/feat/db-internal-learning-pipeline`
- push 상태: `953c492` 팀 remote push 완료

## 수행한 작업

- `backend/Nutrition-backend/src/algorithms/metabolism.py`에 보행 cadence 기반 METs helper를 추가했다.
  - `lookup_walking_cadence_mets()`
  - `calculate_exercise_kcal_from_walking_cadence()`
  - `calculate_tdee()`의 optional cadence/minutes 입력 반영
- cadence 기준은 보수적인 휴리스틱으로 고정했다.
  - 0 steps/min: 0.0 MET
  - 80 steps/min 미만: 2.0 MET
  - 100 steps/min 이상: 3.0 MET
  - 110 steps/min 이상: 4.0 MET
  - 120 steps/min 이상: 5.0 MET
  - 130 steps/min 이상: 6.0 MET
- `WeightPredictionRequest`에 wearable smoke용 입력을 추가했다.
  - `walking_cadence_steps_per_min`
  - `walking_cadence_minutes`
  - 둘 중 하나만 들어오는 요청은 model validator에서 거부한다.
- static weight prediction, Hall-lite baseline, selector 경로가 모두 같은 cadence 기반 TDEE 보정을 사용하도록 연결했다.
- API request example에 cadence 필드를 추가했다.
- audit metadata에는 raw cadence/minutes 값을 남기지 않고 `walking_cadence_used` boolean만 기록하도록 제한했다.
- `store_weight_prediction_result()`가 기존 request field와 새 cadence field를 누락 없이 prediction 저장 경로로 전달하도록 보강했다.
- 테스트를 추가해 cadence lookup, kcal 계산, TDEE 증가, request validation, static/Hall-lite selector 연동을 고정했다.

## 검증 결과

- `black --check` on changed files: passed
- `ruff check` on changed files: passed
- focused metabolism/selector tests: 47 passed
- algorithms + prediction tests: 90 passed
- analysis result / nutrition diagnosis service tests: 7 passed
- full backend unit: 1207 passed
- `git diff --check`: passed
- `detect-secrets scan` on changed files: no findings
- `953c492` push 완료

## 남은 TODO

1. `core-algorithm/03-bmr-tdee.md`
   - 심박 기반 HRR/VO2max/Keytel 계열 보정은 아직 적용하지 않았다.
   - cadence 입력의 실제 source가 mobile wearable인지 수동 입력인지에 따라 신뢰도 표시가 필요하다.

2. `core-algorithm/04-weight-prediction.md`
   - 0.85/0.95 보정 계수를 사용자별 posterior 또는 learned coefficient로 대체하는 작업은 남아 있다.
   - mismatch warning 이후 dashboard/card UI 반영은 mobile 작업으로 남아 있다.

3. mobile/API 표시
   - cadence 기반 TDEE 보정이 사용됐다는 safety warning을 앱에서 어떻게 노출할지 정해야 한다.
   - raw cadence 값은 audit/log/report에 그대로 남기지 않는 현재 정책을 유지한다.

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
