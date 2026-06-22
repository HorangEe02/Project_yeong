# 2026-05-27 Cunningham BMR helper 적용 요약

## 기준 정보

- 작성일: 2026-05-27
- 대상 repo: `/Users/yeong/99_me/00_github/03_lemon_healthcare/Lemon-Aid`
- 작업 브랜치: `feat/db-internal-learning-pipeline`
- 적용 커밋: `fecbd2e feat(algorithm): Cunningham BMR helper 추가`
- 기준 문서:
  - `docs/Nutrition-docs/core-algorithm/03-bmr-tdee.md`
- 확인 근거:
  - Cunningham JJ. Body composition as a determinant of energy expenditure. DOI: https://doi.org/10.1093/ajcn/54.6.963

## 브랜치/커밋 범위

- 직전 기준 head: `2c97485 docs(todo): 운동 METs lookup 적용 요약`
- 이번 phase head: `fecbd2e feat(algorithm): Cunningham BMR helper 추가`
- push 대상: `origin/feat/db-internal-learning-pipeline`

## 수행한 작업

- `backend/Nutrition-backend/src/algorithms/metabolism.py`에 제지방량 기반 helper를 추가했다.
  - `calculate_lean_body_mass_from_body_fat()`
  - `calculate_cunningham_bmr()`
- 기존 `calculate_katch_mcardle_bmr()`는 체지방률 검증과 제지방량 계산 helper를 재사용하도록 정리했다.
- `calculate_bmr()` docstring을 현재 실제 동작에 맞춰 `Katch-McArdle/Cunningham 1991` 제지방량 기반 경로로 설명했다.
- `backend/Nutrition-backend/tests/unit/algorithms/test_metabolism_weight.py`에 Cunningham helper가 체지방률 기반 Katch-McArdle 경로와 같은 값을 내는지 고정했다.

## 검증 결과

- `black --check` on changed files: passed
- `ruff check` on changed files: passed
- focused metabolism test: 29 passed
- algorithms + prediction tests: 73 passed
- full backend unit: 1187 passed
- `git diff --check`: passed
- `detect-secrets scan` on changed files: no findings
- `fecbd2e` push 완료

## 남은 TODO

1. `core-algorithm/03-bmr-tdee.md`
   - Cunningham helper는 추가됐지만, API request schema에서 `lean_body_mass_kg`를 직접 받을지는 아직 별도 설계가 필요하다.
   - cadence/HR 기반 wearable 보정은 아직 없다.
   - 한국인 BMR 보정 계수는 임상 검토와 데이터 축적 전까지 적용하지 않는다.

2. `core-algorithm/04-weight-prediction.md`
   - Hall-lite는 feature flag와 engine selector 뒤에 있으며 production sign-off 전 기본값은 static이다.
   - 예측-실측 mismatch 2주 연속 안내 카드와 개인별 보정 계수 학습은 아직 없다.

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
