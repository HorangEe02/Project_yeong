# 2026-05-27 Core Algorithm 적용 진행 현황

## 기준 정보

- 작성일: 2026-05-27
- 대상 repo: `/Users/yeong/99_me/00_github/03_lemon_healthcare/Lemon-Aid`
- 작업 브랜치: `feat/db-internal-learning-pipeline`
- 최신 원격 동기화 head: `1b49bea docs(todo): 2026-05-27 작업 요약 갱신`
- 기준 문서: `docs/Nutrition-docs/core-algorithm/`
- 작성 목적: 새로 작성된 core algorithm 문서 요구사항을 backend 코드에 반영 중인 상태와 남은 검증 작업을 다음 작업자가 바로 이어갈 수 있게 정리한다.

## 브랜치/커밋 범위

- 오늘 완료되어 push된 범위: `257a48e`부터 `1b49bea`까지
- 현재 진행 중인 미커밋 범위: core algorithm 문서 적용을 위한 backend 코드 수정
- 현재 문서 폴더 상태: `docs/Nutrition-docs/core-algorithm/`는 untracked 상태이며, 구현 검증 후 관련 코드와 함께 stage 여부를 판단한다.

## 수행한 작업

- core algorithm 문서 10개를 기준으로 요구사항을 분류했다.
  - `00-overview-and-evaluation.md`
  - `01-bmi-classification.md`
  - `02-activity-score.md`
  - `03-bmr-tdee.md`
  - `04-weight-prediction.md`
  - `05-nutrition-diagnosis.md`
  - `06-goal-matrix.md`
  - `07-chronic-disease-rationale.md`
  - `08-references.md`
  - `09-smoking-alcohol-rationale.md`

- BMI 분류 적용을 시작했다.
  - Korea/Asia 기준 `asia_kr`와 WHO 기준 `who_standard`를 구분하는 구조를 추가했다.
  - KSSO 2022 기준 `obese_3` 구간을 추가했다.
  - `criteria_source`, WHtR, central obesity, body fat, sarcopenic obesity suspect, 고령/만성질환 안내 note를 결과 모델에 추가했다.
  - 표현은 진단이 아니라 `BMI 분류(스크리닝)` 중심으로 정리했다.

- 활동 점수 적용을 시작했다.
  - HRmax 기본식을 Tanaka 2001 방식으로 바꾸고, 기존 220-age 방식은 선택 옵션으로 유지했다.
  - Gellish/Nes 선택식을 추가했다.
  - ACSM moderate intensity 범위에 맞춰 target HR 비율을 64-76%로 조정했다.
  - 나이 기반 step target과 BMI factor, 만성질환별 recommended steps를 문서 기준에 맞춰 보정했다.
  - 흡연과 만성질환 가중치는 중복 합산이 아니라 더 큰 위험 가중치를 선택하는 방향으로 변경했다.

- BMR/TDEE 적용을 시작했다.
  - 기존 Mifflin-St Jeor 기반 계산은 유지했다.
  - `body_fat_pct`가 유효할 때 Katch-McArdle BMR을 선택할 수 있게 했다.
  - METs 기반 운동 kcal helper와 TDEE exercise kcal 추가 구조를 만들었다.

- 체중 예측 적용을 시작했다.
  - short-term, 8-30일, 장기 horizon별 kcal/kg 보정 factor를 반영했다.
  - 결과 표현을 단일 예측값보다 `expected_weight_range_kg` 중심으로 확장했다.
  - 갑상선, CKD/투석, heart failure edema, cirrhosis, steroid 계열 등 고위험 조건에서는 예측을 disabled 처리하는 구조를 추가했다.
  - PCOS, insulin, GLP-1 조건은 low confidence 경고로 분리했다.
  - 별도 alcohol kcal 입력을 daily intake에 합산할 수 있게 했다.

- 영양 진단 적용을 시작했다.
  - EAR/RDA/AI/UL 기반 status 체계를 확장했다.
  - `at_risk_inadequate`, `below_rda`, `excessive_near_ul`, `referral_required` 상태를 추가했다.
  - 고위험 만성질환은 일반 자동 평가보다 referral route로 분기하는 구조를 추가했다.

- supplement comprehensive goal matrix 보강을 시작했다.
  - 흡연자 beta-carotene/Vitamin A caution을 추가했다.
  - 음주와 높은 Vitamin A 조합 warning을 추가했다.
  - high-risk medication review caution과 AUDIT-KR cutoff 기반 상담 우선 메시지를 추가했다.

## 검증 결과

- 아직 현재 core algorithm 코드 수정분에 대한 최종 검증은 완료하지 않았다.
- 현재까지 확인된 미커밋 변경 파일은 backend source 13개다.
  - `backend/Nutrition-backend/src/algorithms/activity.py`
  - `backend/Nutrition-backend/src/algorithms/bmi.py`
  - `backend/Nutrition-backend/src/algorithms/metabolism.py`
  - `backend/Nutrition-backend/src/api/v1/predictions.py`
  - `backend/Nutrition-backend/src/models/schemas/algorithm.py`
  - `backend/Nutrition-backend/src/models/schemas/nutrition.py`
  - `backend/Nutrition-backend/src/models/schemas/supplement_comprehensive.py`
  - `backend/Nutrition-backend/src/models/schemas/user.py`
  - `backend/Nutrition-backend/src/nutrition/comprehensive.py`
  - `backend/Nutrition-backend/src/nutrition/deficiency_analysis.py`
  - `backend/Nutrition-backend/src/prediction/selector.py`
  - `backend/Nutrition-backend/src/prediction/weight.py`
  - `backend/Nutrition-backend/src/services/nutrition_diagnosis.py`

## 남은 TODO

1. 현재 미커밋 코드의 문법과 포맷을 먼저 확인한다.
   - `black`
   - `ruff check`
   - focused pytest

2. selector/weight prediction 연결부를 재점검한다.
   - Hall-lite path에서 alcohol kcal가 동일하게 반영되는지 확인한다.
   - disabled/low confidence 상태가 API 응답과 audit metadata에 일관되게 반영되는지 확인한다.

3. 테스트를 문서 기준에 맞춰 갱신한다.
   - BMI `obese_3`, `asia_kr`, `who_standard`
   - Tanaka HRmax, target HR 64-76%
   - chronic disease recommended steps
   - Katch-McArdle BMR, METs exercise kcal
   - horizon-based weight prediction range
   - EAR/RDA/AI/UL nutrition status
   - smoking/alcohol/medication caution

4. focused 검증 후 backend unit collection을 실행한다.
   - algorithms
   - prediction
   - nutrition
   - supplement comprehensive
   - backend unit `--collect-only`

5. 구현과 문서 source를 함께 커밋할지 최종 판단한다.
   - `docs/Nutrition-docs/core-algorithm/`는 현재 untracked 상태다.
   - 구현 근거 문서로 포함할 경우 raw payload, secret, private URI가 없는지 먼저 확인한다.

## 주의할 파일/커밋 제외 항목

- 이번 알고리즘 작업에서 커밋 금지:
  - `.env`
  - Supabase service role key
  - ngrok token/public URL
  - raw OCR text
  - provider raw payload
  - image bytes
  - storage object URI/path
  - signed URL/public URL
  - 개인 로컬 절대 경로가 포함된 metadata
- 현재 untracked 중 이번 checkpoint 문서와 무관한 항목:
  - `.omc/`
  - `mobile/assets/mascot/Mascot_AppIcon_Rebuild_Assets/`
- push 대상은 계속 `origin/feat/db-internal-learning-pipeline`이다.
