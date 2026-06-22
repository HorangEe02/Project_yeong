# 2026-05-27 남은 TODO 및 Git 저장 계획

## 기준 정보

- 작성일: 2026-05-27
- 대상 repo: `/Users/yeong/99_me/00_github/03_lemon_healthcare/Lemon-Aid`
- 작업 브랜치: `feat/db-internal-learning-pipeline`
- 현재 기준 head: `54e4656 fix(nutrition): 사용자 노출 문구 안전화`
- 작성 목적: 오늘 남은 작업을 phase 단위로 나누고, 각 phase가 끝날 때 커밋/푸시할 항목과 제외할 항목을 명확히 한다.

## 즉시 처리할 TODO

1. KDRIs 노인 routing test phase 저장
   - 대상 파일: `backend/Nutrition-backend/tests/unit/nutrition/test_kdris_analysis.py`
   - 목적: 75세 이상 Vitamin D AI 기준이 성인 기준으로 fallback되지 않도록 회귀 테스트를 고정한다.
   - 검증:
     - `black --check backend/Nutrition-backend/tests/unit/nutrition/test_kdris_analysis.py`
     - `ruff check backend/Nutrition-backend/tests/unit/nutrition/test_kdris_analysis.py`
     - `PYTHONPATH=backend/Nutrition-backend:backend /opt/anaconda3/bin/python -m pytest backend/Nutrition-backend/tests/unit/nutrition/test_kdris_analysis.py -q --no-cov`
     - `git diff --check`
     - `detect-secrets scan backend/Nutrition-backend/tests/unit/nutrition/test_kdris_analysis.py`
   - commit 예시: `test(nutrition): 노인 KDRIs 라우팅 고정`
   - push 대상: `origin/feat/db-internal-learning-pipeline`

2. 오늘자 todo-list 문서 저장
   - 대상 파일:
     - `outputs/todo-list/2026-05-27/2026-05-27-algorithm-mobile-current-summary.md`
     - `outputs/todo-list/2026-05-27/2026-05-27-open-todo-and-git-save-plan.md`
   - 목적: 현재까지 완료된 algorithm/mobile/OCR smoke 흐름과 남은 작업을 다음 채팅에서 바로 이어갈 수 있게 남긴다.
   - 검증:
     - `git diff --check`
     - `detect-secrets scan outputs/todo-list/2026-05-27`
   - commit 예시: `docs(todo): 2026-05-27 진행 계획 추가`
   - push 대상: `origin/feat/db-internal-learning-pipeline`

## 다음 phase TODO

1. Android camera 원인 분석
   - Android Studio emulator에서 camera permission, camera plugin initialization, emulator camera source 설정을 분리 확인한다.
   - Mac camera preview가 떠도 app 내부 camera controller가 실제 frame을 받는지 로그와 화면 상태를 같이 확인한다.
   - gallery 입력은 camera blocker와 별개로 OCR endpoint smoke에 먼저 사용할 수 있다.

2. OCR endpoint smoke 재검증
   - backend health와 mobile base URL을 확인한다.
   - Android emulator는 `http://10.0.2.2:8000/api/v1`를 사용한다.
   - provider selector 값이 request form field `ocr_provider`로 전달되는지 확인한다.
   - `OCR Auto: Intake` 상태가 계속되면 runtime/config 문제를 먼저 본다.
   - provider가 `paddleocr_local`, `clova_ocr` 등으로 바뀌고 ingredients 후보가 0이면 parser/domain 품질 문제로 분리한다.

3. 17 Pro UIUX 반영 정합성
   - 참고 브랜치 화면처럼 plus button action palette를 복구한다.
   - 영양제/식단 촬영 모드, gallery picker, review flow를 source UIUX와 맞추되 endpoint contract는 현재 backend로 유지한다.
   - mock-only result screen은 현재 real OCR flow와 충돌하지 않도록 제거하거나 neutral 상태로 제한한다.

4. core algorithm 남은 범위 audit
   - 이미 반영된 backend 계산/안전 분기와 문서 요구사항을 체크리스트로 재매핑한다.
   - 아직 product/UI/data roadmap 성격인 항목은 구현 완료로 표시하지 않는다.
   - 예: full AUDIT-KR 10문항 UI, DrugBank/Lexicomp-grade interaction DB, wearable cadence/HR integration, full Hall dynamic model은 별도 phase로 둔다.

5. Supabase/PostgreSQL live smoke
   - read-only/security preflight를 먼저 실행한다.
   - storage round-trip은 explicit live gate를 걸고 실행한다.
   - pgvector insert/query 증명이 필요하면 별도 opt-in synthetic script로 분리한다.

## 검증 체크리스트

- 문서/코드 공통:
  - `git status --short --branch`
  - `git diff --check`
  - `detect-secrets scan <changed tracked text files>`

- Backend:
  - focused pytest
  - broader nutrition/service slice
  - 가능한 경우 full backend unit
  - `black --check`
  - `ruff check`

- Mobile:
  - `cd mobile && flutter pub get`
  - `dart format --output=none --set-exit-if-changed lib test`
  - `flutter analyze`
  - `flutter test`
  - Android emulator fresh install/run

## 커밋 제외 항목

- 현재 untracked 중 제외:
  - `.omc/`
  - `mobile/assets/mascot/Mascot_AppIcon_Rebuild_Assets/`

- 모든 phase에서 제외:
  - `.env`
  - secret/key/token
  - ngrok token/public URL
  - raw OCR text
  - provider raw payload
  - image bytes
  - storage object URI/path
  - signed/public URL
  - 개인 이미지 내용
  - 개인 로컬 private metadata

## 다음 채팅 시작 프롬프트

```text
/Users/yeong/99_me/00_github/03_lemon_healthcare/Lemon-Aid 에서 이어서 작업해줘.
branch는 feat/db-internal-learning-pipeline 유지.
오늘자 todo 문서는 outputs/todo-list/2026-05-27/ 아래에 생성되어 있음.
먼저 git status를 확인하고, 미커밋 KDRIs 노인 routing test phase를 검증/커밋/푸시한 뒤 Android camera/OCR smoke 원인 분석으로 이어가줘.
.env, ngrok token/public URL, raw OCR/provider payload, image/object URI, .omc/, mobile/assets/mascot/Mascot_AppIcon_Rebuild_Assets/ 는 stage 금지.
```
