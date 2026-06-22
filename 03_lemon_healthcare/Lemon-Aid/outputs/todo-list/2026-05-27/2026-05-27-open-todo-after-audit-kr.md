# 2026-05-27 AUDIT-KR 이후 Open TODO

## 기준 정보

- 작성일: 2026-05-27
- 대상 repo: `/Users/yeong/99_me/00_github/03_lemon_healthcare/Lemon-Aid`
- 작업 브랜치: `feat/db-internal-learning-pipeline`
- 기준 head: `b04238f feat(nutrition): AUDIT-KR 자가검진 점수화`
- 작성 목적: 오늘 완료된 phase 이후 다음 작업자가 우선순위를 잃지 않도록 남은 TODO를 실행 단위로 정리한다.

## 브랜치/커밋 범위

- 현재 push 완료 범위: `257a48e`부터 `b04238f`까지
- 최신 구현 완료 커밋:
  - `e45cd7b test(nutrition): 노인 KDRIs 라우팅 고정`
  - `3e72fb6 feat(algorithm): 활동 생활습관 안내 보강`
  - `b04238f feat(nutrition): AUDIT-KR 자가검진 점수화`
- 다음 작업은 새 phase commit으로 분리한다.

## 수행한 작업

- KDRIs
  - 노인 profile에서 75세 이상 Vitamin D 기준을 잘못 선택하지 않도록 unit test를 추가했다.

- 활동/생활습관
  - 흡연 상태와 AUDIT-KR 점수 기반의 안전 메시지를 `ActivityScoreResponse`에 포함했다.
  - 점수 가중치만으로 건강 위험을 숨기지 않도록 사용자 노출 메시지를 분리했다.

- AUDIT-KR
  - backend에 `src/nutrition/audit_kr.py`를 추가했다.
  - `AuditKRRequest`, `AuditKRResponse` schema를 추가했다.
  - `/api/v1/nutrition/audit-kr` endpoint를 추가했다.
  - 질문 원문과 민감한 응답 텍스트는 backend 저장/로그 대상이 아니며, backend는 숫자 점수만 처리한다.

## 검증 결과

- focused AUDIT-KR test: 5 passed
- nutrition/service/security slice: 61 passed
- backend unit: 1174 passed
- `black --check`: passed
- `ruff check`: passed
- `git diff --check`: passed
- `detect-secrets scan` on changed AUDIT-KR files: no findings
- `b04238f` push 완료

## 남은 TODO

1. Android emulator OCR smoke
   - Android Studio에서 emulator를 띄운 뒤 Flutter app을 실행한다.
   - `LEMON_API_BASE_URL=http://10.0.2.2:8000/api/v1`로 backend에 직접 연결한다.
   - gallery와 camera 입력이 모두 `analyzeSupplementImage` 경로를 타는지 확인한다.

2. supplement OCR 품질 분리
   - app 화면이 `OCR Auto: Intake`에 머무르면 runtime/env/gateway 문제로 본다.
   - provider가 `paddleocr_local`, `clova_ocr`, `google_vision` 계열로 바뀌고 ingredients가 0이면 parser/domain correction 문제로 본다.
   - Google Vision credential 이슈는 별도 secret/runtime 작업으로 분리한다.

3. YOLO/Ollama smoke
   - YOLO ROI는 backend `ENABLE_VISION_CLASSIFIER` 상태를 먼저 확인한다.
   - Ollama explanation은 기존 recommendation explanation endpoint로 확인한다.
   - 모바일에 fake YOLO/Ollama endpoint를 추가하지 않는다.

4. core algorithm 후속 구현
   - 식단 alcohol category와 `alcohol_kcal` 입력을 meal/nutrition 흐름에 연결한다.
   - full Hall dynamic model은 별도 검증 가능한 phase로 분리한다.
   - 질환별 guide routing은 source guideline, contraindication, referral boundary를 먼저 문서화한다.
   - supplement interaction DB는 검증된 데이터 소스가 없으면 고위험 placeholder와 referral message까지만 둔다.

5. 문서와 코드 동기화
   - 기존 2026-05-27 checkpoint 문서 중 head가 오래된 파일은 historical snapshot으로 유지한다.
   - 최신 handoff는 이 파일과 `2026-05-27-current-work-summary-after-audit-kr.md`를 기준으로 본다.

## 주의할 파일/커밋 제외 항목

- stage 금지:
  - `.omc/`
  - `mobile/assets/mascot/Mascot_AppIcon_Rebuild_Assets/`
  - local `.env`
  - provider credential/config dump
  - raw OCR/provider payload
  - private image/object path
- push 대상은 계속 `origin/feat/db-internal-learning-pipeline`이다.
- phase commit은 Conventional Commits 형식과 팀 commit 길이 규칙을 유지한다.
