# 2026-05-27 운동 METs lookup 적용 요약

## 기준 정보

- 작성일: 2026-05-27
- 대상 repo: `/Users/yeong/99_me/00_github/03_lemon_healthcare/Lemon-Aid`
- 작업 브랜치: `feat/db-internal-learning-pipeline`
- 적용 커밋: `414d39c feat(algorithm): 운동 METs lookup 추가`
- 기준 문서:
  - `docs/Nutrition-docs/core-algorithm/03-bmr-tdee.md`
  - `docs/Nutrition-docs/core-algorithm/04-weight-prediction.md`
- 확인 근거:
  - 2011 Compendium of Physical Activities supplementary table: https://cdn-links.lww.com/permalink/mss/a/mss_43_8_2011_06_13_ainsworth_202093_sdc1.pdf
  - Ainsworth BE et al. 2011 Compendium PubMed entry: https://pubmed.ncbi.nlm.nih.gov/21681120/

## 브랜치/커밋 범위

- 직전 기준 head: `8d92efe docs(todo): Hall-lite 체지방률 적용 요약`
- 이번 phase head: `414d39c feat(algorithm): 운동 METs lookup 추가`
- push 대상: `origin/feat/db-internal-learning-pipeline`

## 수행한 작업

- `backend/Nutrition-backend/src/algorithms/metabolism.py`에 `ExerciseActivityCode`와 `EXERCISE_ACTIVITY_METS` lookup table을 추가했다.
- 기존 `calculate_exercise_kcal_from_mets()` raw METs 계산은 유지했다.
- 활동 코드 기반 helper를 추가했다.
  - `lookup_exercise_activity_mets()`
  - `calculate_exercise_kcal_from_activity()`
  - `calculate_tdee_with_activity_codes()`
- 지원 코드는 문서의 Phase 2 의도 운동 가산 UX에 맞춰 걷기, 조깅, 달리기, 자전거, 근력운동, 요가의 대표 활동으로 제한했다.
- `backend/Nutrition-backend/tests/unit/algorithms/test_metabolism_weight.py`에 Compendium METs mapping과 TDEE 가산 경로를 고정하는 테스트를 추가했다.

## 검증 결과

- `black --check` on changed files: passed
- `ruff check` on changed files: passed
- focused metabolism test: 28 passed
- algorithms + prediction tests: 72 passed
- full backend unit: 1186 passed
- `git diff --check`: passed
- `detect-secrets scan` on changed files: no findings
- `414d39c` push 완료

## 남은 TODO

1. `core-algorithm/03-bmr-tdee.md`
   - Cunningham BMR 선택 옵션은 아직 별도 구현되지 않았다.
   - cadence/HR 기반 wearable 보정은 아직 없다.
   - API request schema에서 활동 코드 입력을 받을지는 product UX와 함께 별도 설계가 필요하다.

2. `core-algorithm/04-weight-prediction.md`
   - Hall-lite는 feature flag와 engine selector 뒤에 있으며 production sign-off 전 기본값은 static이다.
   - 예측-실측 mismatch 2주 연속 안내 카드와 개인별 보정 계수 학습은 아직 없다.
   - full Hall/NIDDK BWP 재현이 아니라 현재는 Hall-lite FM/FFM 동적 근사다.

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
