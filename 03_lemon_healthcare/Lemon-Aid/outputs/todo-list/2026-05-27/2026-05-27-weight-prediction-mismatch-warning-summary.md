# 2026-05-27 체중 예측 mismatch 경고 적용 요약

## 기준 정보

- 작성일: 2026-05-27
- 대상 repo: `/Users/yeong/99_me/00_github/03_lemon_healthcare/Lemon-Aid`
- 작업 브랜치: `feat/db-internal-learning-pipeline`
- 적용 커밋: `b556b11 feat(prediction): 체중 예측 mismatch 경고 추가`
- 기준 문서:
  - `docs/Nutrition-docs/core-algorithm/04-weight-prediction.md`
- 확인 근거:
  - NIDDK Body Weight Planner: https://www.niddk.nih.gov/health-information/weight-management/body-weight-planner
  - Hall KD et al. 2011 Lancet DOI: https://doi.org/10.1016/S0140-6736(11)60812-X
  - Thomas DM et al. 2013 static 3500 kcal rule review: https://pmc.ncbi.nlm.nih.gov/articles/PMC3859816/

## 브랜치/커밋 범위

- 직전 기준 head: `88f6910 docs(todo): Cunningham BMR 적용 요약`
- 이번 phase head: `b556b11 feat(prediction): 체중 예측 mismatch 경고 추가`
- push 대상: `origin/feat/db-internal-learning-pipeline`

## 수행한 작업

- `WeightPredictionCheckIn` schema를 추가해 예측 후 주차별 실측 체중과 해당 주차 기대 범위를 optional input으로 받을 수 있게 했다.
- `WeightPredictionMismatchWarning` schema를 추가해 최근 실측이 기대 범위를 2주 연속 벗어났는지 응답에 표시할 수 있게 했다.
- `WeightPredictionRequest.prediction_checkins`를 optional list로 추가하고 중복 `week_index`를 거부하도록 검증했다.
- `WeightPredictionResponse.mismatch_warning`을 optional field로 추가했다.
- `evaluate_weight_prediction_mismatch()`와 `is_weight_checkin_outside_expected_range()`를 추가했다.
- static 7-step, Hall-lite selector, `/api/v1/predictions/weight` 경로 모두 같은 mismatch warning contract를 사용하도록 연결했다.
- audit metadata에는 민감한 실측값 대신 `prediction_checkin_count`만 기록하도록 제한했다.
- 새 테스트 `backend/Nutrition-backend/tests/unit/prediction/test_weight_mismatch.py`를 추가했다.

## 검증 결과

- `black --check` on changed files: passed
- `ruff check` on changed files: passed
- focused prediction mismatch/selector/metabolism tests: 42 passed
- algorithms + prediction tests: 79 passed
- full backend unit: 1193 passed
- `git diff --check`: passed
- `detect-secrets scan` on changed files: no findings
- `b556b11` push 완료

## 남은 TODO

1. `core-algorithm/04-weight-prediction.md`
   - 이번 phase는 warning 판정과 API contract까지다.
   - 사용자별 Bayesian posterior 업데이트와 개인별 보정계수 학습은 아직 없다.
   - mismatch warning을 dashboard/card UI에서 어떻게 노출할지는 mobile/frontend 작업으로 남아 있다.
   - Hall-lite는 feature flag와 engine selector 뒤에 있으며 production sign-off 전 기본값은 static이다.

2. `core-algorithm/03-bmr-tdee.md`
   - cadence/HR 기반 wearable 보정은 아직 없다.
   - `lean_body_mass_kg`를 API request에서 직접 받을지는 별도 UX/데이터 신뢰도 설계가 필요하다.

3. `core-algorithm/05-nutrition-diagnosis.md`
   - 소아/청소년 별도 라우팅과 retinol-only pregnancy vitamin A UL 정밀 분리는 아직 남아 있다.

4. `core-algorithm/06-goal-matrix.md`
   - DrugBank/Lexicomp급 상호작용 DB 연동은 아직 없다.

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
