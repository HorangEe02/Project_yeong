# 2026-05-28 소아·청소년 영양 평가 라우팅 적용 요약

## 기준 정보

- 작성일: 2026-05-28
- 대상 repo: `/Users/yeong/99_me/00_github/03_lemon_healthcare/Lemon-Aid`
- 작업 브랜치: `feat/db-internal-learning-pipeline`
- 적용 커밋: `00093d2 feat(nutrition): 소아 청소년 평가 보류`
- 기준 문서:
  - `docs/Nutrition-docs/core-algorithm/05-nutrition-diagnosis.md`
- 공식 확인 근거:
  - 보건복지부/정책브리핑 2025 한국인 영양소 섭취기준 개정 보도자료: https://m.korea.kr/briefing/pressReleaseView.do?newsId=156737581
  - 문서 내 KDRIs 2020/2025 lifecycle 기준과 현행 `kdris_2025.csv` dataset contract

## 브랜치/커밋 범위

- 직전 기준 head: `19b4e9d docs(todo): 알고리즘 작업 요약 추가`
- 이번 phase head: `00093d2 feat(nutrition): 소아 청소년 평가 보류`
- push 대상: `origin/feat/db-internal-learning-pipeline`

## 수행한 작업

- `backend/Nutrition-backend/src/nutrition/deficiency_analysis.py`
  - `ADULT_NUTRITION_ANALYSIS_MIN_AGE = 19` 상수를 추가했다.
  - `profile.age < 19`이면 일반 성인 자동 영양 평가 결과를 생성하지 않고 `referral_required` route로 분기하도록 했다.
  - 사용자 노출 메시지는 "소아·청소년은 성장 단계별 기준과 보호자·전문가 확인이 필요해 일반 성인 자동 평가를 보류합니다."로 제한했다.
  - 금지 표현인 진단, 치료, 처방, 복용량 변경은 포함하지 않았다.

- `backend/Nutrition-backend/tests/unit/nutrition/test_kdris_analysis.py`
  - `test_pediatric_profile_routes_to_referral_required()`를 추가했다.
  - 만 16세 profile이 `referral_required`를 반환하고 `results == []`임을 검증했다.
  - safety message에 `소아·청소년`이 포함되고 금지 표현이 없는지 확인했다.

## 검증 결과

- `black --check backend/Nutrition-backend/src/nutrition/deficiency_analysis.py backend/Nutrition-backend/tests/unit/nutrition/test_kdris_analysis.py`: passed
- `ruff check backend/Nutrition-backend/src/nutrition/deficiency_analysis.py backend/Nutrition-backend/tests/unit/nutrition/test_kdris_analysis.py`: passed
- focused KDRIs analysis tests: 18 passed
- nutrition unit tests: 58 passed
- full backend unit: 1194 passed
- `git diff --check`: passed
- `detect-secrets scan` on changed source/test files: no findings
- `00093d2` push 완료

## 남은 TODO

1. `05-nutrition-diagnosis.md`
   - pregnancy vitamin A 경고를 retinol-only 기준과 총 vitamin A 기준으로 분리할 수 있는지 schema와 데이터 source를 먼저 확인한다.
   - 현재 nutrition diagnosis 경로는 pregnancy/lactation을 referral route로 보류하므로 중복 경고가 생기지 않게 설계한다.

2. `06-goal-matrix.md`
   - 현재 rule-based 상호작용 경고는 유지한다.
   - DrugBank/Lexicomp급 상호작용 DB 연동은 라이선스와 API credential, offline fallback, citation 정책을 먼저 검토한다.

3. `03-bmr-tdee.md`
   - wearable cadence/heart-rate 기반 TDEE 보정은 아직 없다.
   - `lean_body_mass_kg` 직접 입력 API는 데이터 신뢰도와 audit redaction 정책을 먼저 정해야 한다.

4. `04-weight-prediction.md`
   - mismatch warning 이후 개인별 posterior update 또는 보정계수 학습은 아직 없다.
   - mobile UI에서 warning card를 노출하는 작업은 별도 phase다.

## 주의할 파일/커밋 제외 항목

- 이번 phase에서 커밋하지 않은 기존 제외 항목:
  - `.omc/`
  - `mobile/assets/mascot/Mascot_AppIcon_Rebuild_Assets/`
- 계속 커밋 금지:
  - `.env`
  - Supabase service role key
  - ngrok token/public URL
  - raw OCR text
  - provider raw payload
  - image bytes
  - object URI/path
  - signed URL/public URL
  - 개인 로컬 절대 경로가 포함된 metadata
