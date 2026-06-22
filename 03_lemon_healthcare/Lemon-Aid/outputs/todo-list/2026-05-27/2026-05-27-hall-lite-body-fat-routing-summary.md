# 2026-05-27 Hall-lite 체지방률 전달 경로 적용 요약

## 기준 정보

- 작성일: 2026-05-27
- 대상 repo: `/Users/yeong/99_me/00_github/03_lemon_healthcare/Lemon-Aid`
- 작업 브랜치: `feat/db-internal-learning-pipeline`
- 적용 커밋: `3f8de27 fix(prediction): Hall-lite 체지방률 입력 반영`
- 기준 문서:
  - `docs/Nutrition-docs/core-algorithm/03-bmr-tdee.md`
  - `docs/Nutrition-docs/core-algorithm/04-weight-prediction.md`

## 브랜치/커밋 범위

- 직전 기준 head: `d14692b docs(todo): 질환별 영양 가이드 적용 요약`
- 이번 phase head: `3f8de27 fix(prediction): Hall-lite 체지방률 입력 반영`
- push 대상: `origin/feat/db-internal-learning-pipeline`

## 수행한 작업

- `predict_weight_periods_selected()`에서 받은 `body_fat_pct`를 Hall-lite simulator의 `measured_body_fat_pct`로 전달하도록 수정했다.
- 기존에는 API request/schema에 체지방률 입력이 있어도 Hall-lite 장기 예측 경로에서는 Deurenberg 추정값만 사용했다.
- 이제 체지방률 입력이 있으면 Hall-lite의 초기 fat mass / fat-free mass partitioning에 반영된다.
- `test_selector_hall_lite_uses_measured_body_fat_for_partitioning`을 추가해 저체지방률, 고체지방률, 추정 체지방률 경로가 서로 다른 예측을 만드는지 고정했다.

## 검증 결과

- `black --check` on changed files: passed
- `ruff check` on changed files: passed
- Hall/selector/body composition focused tests: 22 passed
- algorithms + prediction tests: 64 passed
- full backend unit: 1178 passed
- `git diff --check`: passed
- `detect-secrets scan` on changed files: no findings
- `3f8de27` push 완료

## 남은 TODO

1. `core-algorithm/03-bmr-tdee.md`
   - Cunningham BMR 선택 옵션은 아직 별도 구현되지 않았다.
   - METs raw tuple helper는 있지만 운동 종류별 METs lookup table은 아직 없다.
   - cadence/HR 기반 wearable 보정은 아직 없다.

2. `core-algorithm/04-weight-prediction.md`
   - Hall-lite는 feature flag와 engine selector 뒤에 있으며 production sign-off 전 기본값은 static이다.
   - 예측-실측 mismatch 2주 연속 안내 카드와 개인별 보정 계수 학습은 아직 없다.
   - full Hall/NIDDK BWP 재현이 아니라 현재는 Hall-lite FM/FFM 동적 근사다.

3. `core-algorithm/05-nutrition-diagnosis.md`
   - 소아/청소년 별도 라우팅과 retinol-only pregnancy vitamin A UL 정밀 분리는 아직 남아 있다.

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
