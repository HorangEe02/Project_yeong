# 2026-05-28 임신 Vitamin A 형태별 안전 분기 적용 요약

## 기준 정보

- 작성일: 2026-05-28
- 대상 repo: `/Users/yeong/99_me/00_github/03_lemon_healthcare/Lemon-Aid`
- 작업 브랜치: `feat/db-internal-learning-pipeline`
- 적용 커밋: `d596214 fix(nutrition): 임신 비타민A 형태 분기`
- 기준 문서:
  - `docs/Nutrition-docs/core-algorithm/05-nutrition-diagnosis.md`
  - `docs/Nutrition-docs/core-algorithm/06-goal-matrix.md`
- 공식 확인 근거:
  - NIH ODS Vitamin A Health Professional Fact Sheet: https://ods.od.nih.gov/factsheets/VitaminA-HealthProfessional/
  - NIH ODS Pregnancy Health Professional Fact Sheet: https://ods.od.nih.gov/factsheets/Pregnancy-HealthProfessional/

## 브랜치/커밋 범위

- 직전 기준 head: `465f516 docs(todo): 소아 청소년 영양 라우팅 요약`
- 이번 phase head: `d596214 fix(nutrition): 임신 비타민A 형태 분기`
- push 대상: `origin/feat/db-internal-learning-pipeline`

## 수행한 작업

- `backend/Nutrition-backend/src/nutrition/comprehensive.py`
  - 임신 중 vitamin A high caution을 `preformed vitamin A(retinol/retinyl ester)` 형태에만 적용하도록 분리했다.
  - `retinol_ug`, `vitamin_a_retinol_ug`, `retinyl_palmitate_ug` 코드와 `retinol`, `retinyl`, `레티놀`, `레티닐` 표시명을 preformed vitamin A로 판별한다.
  - `IU` 단위 vitamin A 표기는 `1 IU = 0.3 mcg RAE`로 환산해 기존 raw amount 비교보다 안전하게 만들었다.
  - 임신 중 preformed vitamin A UL은 성인 3,000 mcg RAE, 19세 미만은 2,800 mcg RAE로 분리했다.
  - beta-carotene 표기는 `pregnancy_vitamin_a_ul_risk` high caution으로 분류하지 않도록 했다.
  - generic `vitamin_a_ug`가 고함량이지만 retinol/retinyl 형태가 불명확하면 `pregnancy_vitamin_a_form_review` medium caution으로 라벨 확인을 요구한다.

- `backend/Nutrition-backend/tests/unit/nutrition/test_comprehensive.py`
  - retinol 10,000 IU가 임신 high caution으로 분기되는 테스트를 추가했다.
  - beta-carotene 표기가 retinol UL high caution을 만들지 않는지 검증했다.
  - generic high vitamin A는 high가 아니라 medium form review로 분리되는지 검증했다.

## 검증 결과

- `black --check backend/Nutrition-backend/src/nutrition/comprehensive.py backend/Nutrition-backend/tests/unit/nutrition/test_comprehensive.py`: passed
- `ruff check backend/Nutrition-backend/src/nutrition/comprehensive.py backend/Nutrition-backend/tests/unit/nutrition/test_comprehensive.py`: passed
- focused comprehensive tests: 18 passed
- nutrition unit tests: 60 passed
- full backend unit: 1196 passed
- `git diff --check`: passed
- `detect-secrets scan` on changed source/test files: no findings
- `d596214` push 완료

## 남은 TODO

1. `06-goal-matrix.md`
   - 현재는 rule-based caution이다.
   - DrugBank/Lexicomp급 상호작용 DB 연동은 라이선스, API credential, offline fallback, citation 정책 확인 후 별도 phase로 진행한다.

2. `03-bmr-tdee.md`
   - wearable cadence/heart-rate 기반 TDEE 보정은 아직 없다.
   - 직접 `lean_body_mass_kg` 입력을 API에 열지는 데이터 신뢰도와 audit redaction 기준을 먼저 정한다.

3. `04-weight-prediction.md`
   - mismatch warning 이후 개인별 posterior update 또는 보정계수 학습은 아직 없다.

4. mobile/UI 후속
   - `pregnancy_vitamin_a_form_review`와 `pregnancy_vitamin_a_ul_risk`를 같은 카드에 노출하되 severity 차이를 명확히 보여주는 UI 정렬이 필요하다.

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
