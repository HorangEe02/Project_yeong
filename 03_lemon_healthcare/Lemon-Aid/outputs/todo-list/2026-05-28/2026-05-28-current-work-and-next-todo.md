# 2026-05-28 현재 작업 요약 및 다음 TODO

## 기준 정보

- 작성일: 2026-05-28
- 대상 repo: `/Users/yeong/99_me/00_github/03_lemon_healthcare/Lemon-Aid`
- 작업 브랜치: `feat/db-internal-learning-pipeline`
- 현재 기준 head: `953c492 feat(prediction): 보행 cadence TDEE 보정 추가`
- 작성 목적: 오늘 진행한 core algorithm phase를 한 문서에서 이어받을 수 있도록 정리한다.

## 브랜치/커밋 범위

- 오늘자 커밋 범위: `b556b11`부터 `953c492`까지
- 오늘 완료된 주요 커밋:
  - `b556b11 feat(prediction): 체중 예측 mismatch 경고 추가`
  - `0cf6946 docs(todo): 체중 mismatch 경고 적용 요약`
  - `19b4e9d docs(todo): 알고리즘 작업 요약 추가`
  - `00093d2 feat(nutrition): 소아 청소년 평가 보류`
  - `465f516 docs(todo): 소아 청소년 영양 라우팅 요약`
  - `d596214 fix(nutrition): 임신 비타민A 형태 분기`
  - `44eb337 docs(todo): 임신 비타민A 분기 요약`
  - `953c492 feat(prediction): 보행 cadence TDEE 보정 추가`
- push 대상: `origin/feat/db-internal-learning-pipeline`
- push 상태: `953c492`까지 팀 remote 반영 완료

## 수행한 작업

- 체중 예측 mismatch warning을 추가했다.
  - 예측 후 check-in 실측이 기대 범위를 2주 연속 벗어나는지 판정한다.
  - audit metadata에는 check-in count만 남기고 실측 체중 raw 값을 남기지 않도록 제한했다.
- core algorithm 적용 상황과 다음 작업 TODO를 문서화했다.
  - `outputs/todo-list/2026-05-27/2026-05-27-core-algorithm-implementation-rollup.md`
  - `outputs/todo-list/2026-05-27/2026-05-27-core-algorithm-next-todo.md`
- 소아/청소년 영양 평가를 성인 자동 평가에서 분리했다.
  - `age < 19` profile은 일반 성인 자동 deficiency analysis 대신 전문가 확인 route로 보낸다.
- 임신 중 vitamin A 경고를 retinol/preformed vitamin A 중심으로 정밀 분기했다.
  - beta-carotene은 retinol UL high caution으로 취급하지 않는다.
  - IU 단위는 mcg RAE로 변환해 판정할 수 있도록 보강했다.
- 보행 cadence 기반 TDEE 보정을 추가했다.
  - cadence와 duration이 함께 들어온 경우 휴리스틱 METs로 운동 열량을 계산해 static/Hall-lite weight prediction에 반영한다.
  - API audit metadata에는 `walking_cadence_used` boolean만 남긴다.

## 검증 결과

- 최근 보행 cadence phase 기준:
  - `black --check` on changed files: passed
  - `ruff check` on changed files: passed
  - focused metabolism/selector tests: 47 passed
  - algorithms + prediction tests: 90 passed
  - analysis result / nutrition diagnosis service tests: 7 passed
  - full backend unit: 1207 passed
  - `git diff --check`: passed
  - `detect-secrets scan` on changed files: no findings
- 이전 phase별 문서에 기록된 기준:
  - 체중 mismatch warning phase full backend unit: 1193 passed
  - Cunningham BMR phase full backend unit: 1187 passed
  - 각 phase 커밋 후 `origin/feat/db-internal-learning-pipeline` push 완료

## 남은 TODO

1. 상호작용 DB 연동 범위 분리
   - DrugBank/Lexicomp급 외부 DB는 license, API credential, offline fallback, citation 정책이 필요하다.
   - 검증되지 않은 interaction claim은 추가하지 않는다.

2. 체중 예측 개인화
   - mismatch warning 이후 개인별 보정계수 또는 posterior update 설계가 필요하다.
   - raw check-in weight는 audit/log/document에 남기지 않는 현재 정책을 유지한다.

3. BMR/TDEE wearable 후속
   - cadence는 반영했지만 심박 기반 보정은 아직 남아 있다.
   - wearable source 신뢰도와 사용자가 확인 가능한 설명 문구가 필요하다.

4. mobile 표시 및 OCR smoke
   - weight prediction warning과 cadence safety warning을 앱에서 어떻게 노출할지 정해야 한다.
   - Android emulator OCR smoke는 `LEMON_API_BASE_URL=http://10.0.2.2:8000/api/v1` 기준으로 재검증한다.

5. quality/security 반복
   - 각 phase마다 focused test, 관련 backend unit, `git diff --check`, secret scan을 유지한다.
   - docs는 raw OCR/provider payload, object URI, public tunnel URL, token을 포함하지 않는다.

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
- stage 제외 유지:
  - `.omc/`
  - `mobile/assets/mascot/Mascot_AppIcon_Rebuild_Assets/`
- 기존 team repo remote와 branch를 유지한다.
  - remote: `origin=https://github.com/Lemon-Aid-KDT/Lemon-sin.git`
  - branch: `feat/db-internal-learning-pipeline`
