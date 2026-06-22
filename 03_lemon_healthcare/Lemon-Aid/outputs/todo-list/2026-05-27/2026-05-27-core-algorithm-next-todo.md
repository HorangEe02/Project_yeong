# 2026-05-27 Core Algorithm 다음 작업 TODO

## 기준 정보

- 작성일: 2026-05-27
- 대상 repo: `/Users/yeong/99_me/00_github/03_lemon_healthcare/Lemon-Aid`
- 작업 브랜치: `feat/db-internal-learning-pipeline`
- 현재 기준 head: `0cf6946 docs(todo): 체중 mismatch 경고 적용 요약`
- 기준 문서: `docs/Nutrition-docs/core-algorithm/`
- 작성 목적: 오늘 구현된 algorithm phase 이후 남은 작업을 안전한 순서로 정리한다.

## 브랜치/커밋 범위

- 오늘 전체 작업 기준 범위: `257a48e`부터 `0cf6946`까지
- core algorithm 집중 범위: `703bee2`부터 `0cf6946`까지
- 마지막 완료 phase:
  - `b556b11 feat(prediction): 체중 예측 mismatch 경고 추가`
  - `0cf6946 docs(todo): 체중 mismatch 경고 적용 요약`

## 수행한 작업

- 이번 문서는 코드 수정이 아니라 다음 phase 실행 순서를 고정하기 위한 작업 관리 문서다.
- 오늘 완료한 backend algorithm 변경은 이미 phase별 문서에 나뉘어 정리되어 있다.
  - `2026-05-27-exercise-mets-lookup-summary.md`
  - `2026-05-27-cunningham-bmr-helper-summary.md`
  - `2026-05-27-weight-prediction-mismatch-warning-summary.md`
  - 그 외 `2026-05-27-*summary.md`, `2026-05-27-*checkpoint.md` 파일들

## 검증 결과

- 이 문서 작성 전 기준 `git status --short --branch` 결과:
  - branch는 `feat/db-internal-learning-pipeline`
  - remote tracking은 `origin/feat/db-internal-learning-pipeline`
  - 제외 유지 untracked 항목은 `.omc/`, `mobile/assets/mascot/Mascot_AppIcon_Rebuild_Assets/`
- 최신 algorithm phase의 backend 검증 결과:
  - full backend unit: 1193 passed
  - `git diff --check`: passed
  - `detect-secrets scan` on changed files: no findings

## 남은 TODO

1. 소아/청소년 영양 평가 보류
   - 파일 후보: `backend/Nutrition-backend/src/nutrition/deficiency_analysis.py`
   - 테스트 후보: `backend/Nutrition-backend/tests/unit/nutrition/test_kdris_analysis.py`
   - 목표: `age < 19` profile은 일반 성인 자동 영양 평가 대신 전문가 확인 route로 분기한다.
   - 메시지는 진단, 치료, 처방, 복용량 변경 같은 표현을 피한다.

2. pregnancy vitamin A 경고 정밀화
   - 파일 후보: `backend/Nutrition-backend/src/nutrition/comprehensive.py`
   - 테스트 후보: `backend/Nutrition-backend/tests/unit/nutrition/test_comprehensive.py`
   - 목표: retinol-only 위험과 총 vitamin A intake를 구분할 수 있는지 schema와 데이터 source를 먼저 확인한다.
   - 현재 nutrition diagnosis 쪽은 pregnancy/lactation을 referral route로 보내므로 중복 경고가 생기지 않게 설계한다.

3. interaction DB 연동 범위 분리
   - 현재 rule-based warning은 유지한다.
   - 외부 상호작용 DB는 라이선스, citation, API credential, offline fallback 정책을 먼저 문서화한다.
   - 검증되지 않은 interaction claim은 추가하지 않는다.

4. BMR/TDEE wearable 보정 설계
   - cadence, heart-rate, activity duration 입력의 source 신뢰도와 privacy surface를 먼저 정의한다.
   - 단순 계산 helper보다 request schema와 audit redaction 정책을 먼저 정한다.

5. weight prediction 개인화 후속
   - mismatch warning 이후 단계로 개인별 보정계수나 posterior update를 설계한다.
   - 실측 체중값은 audit/log/document에 직접 남기지 않는 현재 정책을 유지한다.

6. Android OCR smoke 재검증
   - Flutter Android emulator는 `LEMON_API_BASE_URL=http://10.0.2.2:8000/api/v1`로 실행한다.
   - provider selector는 `configured`, `paddleocr`, `google_vision`, `clova` 값을 유지한다.
   - raw OCR text와 provider payload는 문서와 커밋에 남기지 않는다.

## 주의할 파일/커밋 제외 항목

- 다음 phase에서도 커밋 금지:
  - `.env`
  - ngrok token/public URL
  - Supabase key
  - raw OCR text
  - provider raw payload
  - image bytes
  - object URI/path
  - signed/public URL
  - 개인 로컬 절대 경로가 포함된 metadata
- stage 시 새 문서 또는 해당 phase 코드/테스트만 선택한다.
- `.omc/`와 `mobile/assets/mascot/Mascot_AppIcon_Rebuild_Assets/`는 이번 todo 문서 작업과 무관하므로 그대로 제외한다.
