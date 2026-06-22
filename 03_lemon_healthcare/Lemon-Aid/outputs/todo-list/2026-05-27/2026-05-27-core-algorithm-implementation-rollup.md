# 2026-05-27 Core Algorithm 적용 누적 요약

## 기준 정보

- 작성일: 2026-05-27
- 대상 repo: `/Users/yeong/99_me/00_github/03_lemon_healthcare/Lemon-Aid`
- 작업 브랜치: `feat/db-internal-learning-pipeline`
- 현재 기준 head: `0cf6946 docs(todo): 체중 mismatch 경고 적용 요약`
- push 대상: `origin/feat/db-internal-learning-pipeline`
- 기준 문서: `docs/Nutrition-docs/core-algorithm/`
- 작성 목적: 오늘 적용한 core algorithm 관련 backend 변경과 검증 상태를 다음 작업자가 한눈에 이어갈 수 있게 정리한다.

## 브랜치/커밋 범위

| 범위 | 내용 |
| --- | --- |
| `257a48e` - `550bf08` | 멀티모달 저장소, medical/OCR 승격, learning dataset/model registry CLI, Supabase 보안 preflight |
| `c26b546` - `dd3aebc` | 식단 YOLO/RDA 데이터 파이프라인 선별 이식 및 `backend/Food-backend/` 분리 |
| `703bee2` - `0cf6946` | core algorithm 문서 기반 backend 알고리즘, nutrition, prediction contract 정렬 |

## 수행한 작업

- BMI/건강 계산 기준 정렬
  - Korea/Asia 기준과 WHO 기준을 분리하는 방향으로 계산 기준을 정리했다.
  - 결과 표현은 의료 판단이 아니라 스크리닝/안내 중심으로 유지했다.

- 활동/생활습관 안내 보강
  - 활동 점수와 생활습관 안내가 문서 기준에 맞게 위험군 메시지와 분기 조건을 갖도록 보강했다.
  - 사용자 노출 문구에서 진단, 치료, 처방처럼 의료행위로 오해될 수 있는 표현을 줄였다.

- BMR/TDEE 보강
  - body fat 기반 Katch-McArdle 경로를 정렬했다.
  - 운동 activity code 기반 METs lookup과 exercise kcal 계산 helper를 추가했다.
  - Cunningham BMR helper와 lean body mass 계산 helper를 추가했다.

- 체중 예측 보강
  - Hall-lite selector에서 body fat 입력이 반영되도록 정렬했다.
  - 예측 range와 실측 check-in을 비교해 2주 연속 범위 이탈 시 mismatch warning을 반환하는 contract를 추가했다.
  - audit metadata에는 민감한 실측 체중값 대신 check-in 개수만 남기도록 제한했다.

- 영양 분석/목표 matrix 보강
  - 목적별 안전 분기와 영양 상호작용 경고를 보강했다.
  - 임신/수유, 고위험 질환, 일부 복약 profile은 일반 자동 평가 대신 전문가 확인 route로 분기하도록 했다.
  - AUDIT-KR 점수화와 질환별 영양 가이드 routing을 추가했다.

## 검증 결과

- 주요 phase별로 `black --check`, `ruff check`, focused pytest, `git diff --check`, `detect-secrets scan`을 실행했다.
- exercise METs phase:
  - focused metabolism tests: 28 passed
  - algorithms + prediction tests: 72 passed
  - full backend unit: 1186 passed
- Cunningham BMR phase:
  - focused metabolism tests: 29 passed
  - algorithms + prediction tests: 73 passed
  - full backend unit: 1187 passed
- weight mismatch warning phase:
  - focused prediction mismatch/selector/metabolism tests: 42 passed
  - algorithms + prediction tests: 79 passed
  - full backend unit: 1193 passed
- 최신 push 완료 head: `0cf6946 docs(todo): 체중 mismatch 경고 적용 요약`

## 남은 TODO

1. `05-nutrition-diagnosis.md`
   - 소아/청소년 profile은 성인 자동 평가와 분리해 `referral_required` 또는 평가 보류 route로 고정한다.
   - 임신 profile의 vitamin A 경고는 retinol-only 기준과 총 vitamin A 기준을 분리할지 결정한다.

2. `06-goal-matrix.md`
   - 현재 rule-based 상호작용 경고는 유지한다.
   - DrugBank/Lexicomp급 상호작용 DB 연동은 별도 source/license/API 검토 후 진행한다.

3. `03-bmr-tdee.md`
   - cadence/heart-rate 기반 wearable 보정은 아직 미구현이다.
   - `lean_body_mass_kg` 직접 입력을 API contract로 열지는 데이터 신뢰도와 UX 확인 후 결정한다.

4. `04-weight-prediction.md`
   - 개인별 Bayesian posterior 보정과 장기 학습은 아직 없다.
   - mismatch warning을 mobile dashboard/card에 노출하는 UI 작업은 별도 phase로 남아 있다.

5. OCR/YOLO/Ollama smoke
   - Android emulator 기준 endpoint는 `http://10.0.2.2:8000/api/v1`이다.
   - provider가 실행되는데 ingredients 후보가 비면 endpoint보다 OCR 품질, parser, domain normalization 순서로 확인한다.

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
- 현재 제외 유지 항목:
  - `.omc/`
  - `mobile/assets/mascot/Mascot_AppIcon_Rebuild_Assets/`
- 오늘 생성된 이 문서는 운영 값이나 private image 내용을 포함하지 않는다.
