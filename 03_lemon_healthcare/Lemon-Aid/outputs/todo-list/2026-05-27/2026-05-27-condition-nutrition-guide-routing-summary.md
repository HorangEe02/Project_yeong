# 2026-05-27 질환별 영양 가이드 라우팅 적용 요약

## 기준 정보

- 작성일: 2026-05-27
- 대상 repo: `/Users/yeong/99_me/00_github/03_lemon_healthcare/Lemon-Aid`
- 작업 브랜치: `feat/db-internal-learning-pipeline`
- 적용 커밋: `aba4996 feat(nutrition): 질환별 영양 가이드 라우팅`
- 기준 문서:
  - `docs/Nutrition-docs/core-algorithm/05-nutrition-diagnosis.md`
  - `docs/Nutrition-docs/core-algorithm/07-chronic-disease-rationale.md`
  - `docs/Nutrition-docs/core-algorithm/08-references.md`

## 브랜치/커밋 범위

- 직전 기준 head: `81f3915 docs(todo): 2026-05-27 AUDIT-KR 이후 요약 추가`
- 이번 phase head: `aba4996 feat(nutrition): 질환별 영양 가이드 라우팅`
- push 대상: `origin/feat/db-internal-learning-pipeline`

## 수행한 작업

- `NutritionAnalysisResponse`에 `condition_nutrition_guides` 필드를 추가했다.
- 새 라우터 `src/nutrition/chronic_nutrition_guidance.py`를 추가했다.
- 당뇨 입력은 ADA diabetes nutrition route로 연결한다.
- 고혈압/심혈관 입력은 NHLBI DASH eating plan route로 연결한다.
- CKD 입력은 KDOQI nutrition in CKD route로 연결하고 기존 `referral_required` 흐름을 유지한다.
- 간질환/간경변 입력은 EASL chronic liver disease nutrition route로 연결하고 기존 `referral_required` 흐름을 유지한다.
- 당뇨/고혈압은 기존 KDRIs 자동 분석과 chronic priority boost를 유지하면서 guide metadata만 추가했다.
- 사용자 메시지는 진단·치료·처방·복용량 변경 표현을 피하도록 테스트에 포함했다.

## 검증 결과

- `black --check` on changed files: passed
- `ruff check` on changed files: passed
- Focused guide/KDRIs tests: 19 passed
- Nutrition/service/security slice: 64 passed
- Full backend unit: 1177 passed
- `git diff --check`: passed
- `detect-secrets scan` on changed files: no findings
- `aba4996` push 완료

## 남은 TODO

1. `core-algorithm/03-bmr-tdee.md`
   - Cunningham BMR 선택 옵션은 아직 별도 구현되지 않았다.
   - 운동 종류별 METs lookup table과 cadence/HR 기반 wearable 보정은 아직 구현되지 않았다.

2. `core-algorithm/04-weight-prediction.md`
   - full Hall dynamic model은 아직 구현되지 않았다.
   - 예측-실측 mismatch 2주 연속 안내 카드와 개인별 보정 계수 학습은 남아 있다.

3. `core-algorithm/05-nutrition-diagnosis.md`
   - 소아/청소년 세부 라우팅은 아직 backend API에 별도 guard로 노출되지 않았다.
   - retinol-only vitamin A pregnancy UL 분리는 아직 정밀 구현되지 않았다.

4. `core-algorithm/06-goal-matrix.md`
   - DrugBank/Lexicomp급 상호작용 DB 연동은 아직 없다.
   - 현재는 고위험 약물/성분 rule 기반 안전 경고까지 구현된 상태다.

5. 모바일/Android smoke
   - Android emulator에서 OCR provider selector와 `POST /api/v1/supplements/analyze` 실제 흐름을 계속 검증해야 한다.
   - ingredients 0 문제는 endpoint 도달 후 parser/domain correction, 이미지 품질, YOLO ROI, provider별 OCR 품질 순서로 분리한다.

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
