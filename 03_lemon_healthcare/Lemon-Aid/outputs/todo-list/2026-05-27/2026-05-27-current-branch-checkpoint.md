# 2026-05-27 현재 브랜치 Checkpoint TODO

## 기준 정보

- 작성일: 2026-05-27
- 대상 repo: `/Users/yeong/99_me/00_github/03_lemon_healthcare/Lemon-Aid`
- 작업 브랜치: `feat/db-internal-learning-pipeline`
- remote: `origin` = `https://github.com/Lemon-Aid-KDT/Lemon-sin.git`
- 최신 push head: `1b49bea docs(todo): 2026-05-27 작업 요약 갱신`
- 작성 목적: 오늘 push된 작업과 현재 미커밋 작업을 분리해서 기록하고, 다음 단계에서 실수로 unrelated 파일을 stage하지 않도록 checkpoint를 남긴다.

## 브랜치/커밋 범위

| 범위 | 상태 | 내용 |
| --- | --- | --- |
| `257a48e` - `1b49bea` | push 완료 | 멀티모달 저장소, regulated OCR 승격, learning/model registry CLI, Supabase 보안 preflight, Food-backend 분리, 오늘자 todo 문서 갱신 |
| current working tree | 진행 중 | core algorithm 문서 기반 backend 알고리즘 적용 |

## 수행한 작업

- PostgreSQL/Supabase backend 저장소 기반을 확장했다.
  - media, meal, health profile/metric, medical record, learning dataset/model registry 흐름을 backend-only 경계로 정리했다.
  - public view/materialized view 노출 점검을 Supabase 보안 preflight에 추가했다.

- regulated OCR 저장 경계를 정리했다.
  - 사용자 확인 전 raw OCR/provider payload는 장기 medical store로 승격하지 않는 원칙을 유지했다.
  - 확인된 결과만 medical record로 승격하는 흐름을 추가했다.

- learning/retraining operator CLI를 추가했다.
  - dataset version 생성
  - annotation review import
  - dataset lifecycle transition
  - training manifest export
  - training run registration
  - candidate/eval/promotion/retirement flow

- Food-backend 분리를 완료했다.
  - 식단 YOLO/RDA 파이프라인은 `backend/Food-backend/`로 분리했다.
  - 현재 Nutrition-backend OCR/YOLO/Ollama endpoint와 혼동되지 않도록 별도 backend/test/doc 구조로 정리했다.

- 오늘자 todo-list 문서를 갱신했다.
  - `outputs/todo-list/2026-05-27/` 아래 기존 summary/checkpoint 문서를 보강했다.
  - 최신 push head는 `1b49bea`다.

- 현재 진행 중인 core algorithm 적용을 시작했다.
  - BMI, activity, metabolism, weight prediction, nutrition diagnosis, supplement comprehensive caution 영역을 문서 기준으로 수정 중이다.
  - 아직 검증과 커밋은 완료하지 않았다.

## 검증 결과

- 오늘 push된 이전 phase들은 각 커밋 body 기준으로 focused tests, backend unit collection, formatting/lint/security gate를 통과한 뒤 push되었다.
- 현재 core algorithm 미커밋 변경분은 아직 최종 검증 전이다.
- 이 checkpoint 문서는 검증 대상이 문서 파일이므로, 생성 후 아래 gate를 실행한다.
  - `git diff --check`
  - `detect-secrets scan outputs/todo-list/2026-05-27`
  - `git status --short --branch`

## 남은 TODO

1. core algorithm 구현분을 정리한다.
   - schema와 algorithm helper 사이 contract가 깨지지 않는지 확인한다.
   - 선택식과 disabled/referral 상태가 API 응답에서 일관되게 보이는지 확인한다.

2. 테스트를 갱신한다.
   - algorithms focused tests
   - prediction focused tests
   - nutrition diagnosis focused tests
   - supplement comprehensive focused tests
   - backend unit collection

3. Android OCR/YOLO/Ollama smoke를 다시 이어간다.
   - Android emulator는 `LEMON_API_BASE_URL=http://10.0.2.2:8000/api/v1` 기준으로 실행한다.
   - OCR provider selector는 `configured`, `paddleocr`, `google_vision`, `clova`만 사용한다.
   - YOLO/Ollama는 mobile fake endpoint가 아니라 backend runtime env로만 제어한다.

4. Supabase live preflight를 별도 단계로 실행한다.
   - local ignored `.env`만 사용한다.
   - live object URI, signed URL, public URL, service role key, ngrok token/URL은 출력이나 문서에 남기지 않는다.

5. phase 단위로 저장한다.
   - 알고리즘 구현 검증이 끝나면 관련 코드와 필요한 문서만 stage한다.
   - unrelated untracked 폴더는 stage하지 않는다.
   - 커밋 메시지는 팀 규칙에 맞춰 Conventional Commits 형식을 사용한다.

## 주의할 파일/커밋 제외 항목

- 현재 stage 금지 항목:
  - `.omc/`
  - `mobile/assets/mascot/Mascot_AppIcon_Rebuild_Assets/`
- 구현 검증 전까지 보류할 항목:
  - `docs/Nutrition-docs/core-algorithm/`
- 항상 커밋 금지:
  - `.env`
  - secret
  - raw OCR text
  - provider raw payload
  - image bytes
  - storage object URI/path
  - signed URL/public URL
  - ngrok token/public URL
- GitHub push 대상:
  - `origin/feat/db-internal-learning-pipeline`
