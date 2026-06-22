# 2026-05-27 참고 브랜치 선별 이식 분석

## 기준 정보

- 작성일: 2026-05-27
- 대상 repo: `/Users/yeong/99_me/00_github/03_lemon_healthcare/Lemon-Aid`
- 작업 브랜치: `feat/db-internal-learning-pipeline`
- 현재 기준 head: `dd3aebc refactor(food): Food-backend 분리 및 계획 갱신`
- 참고 UIUX 브랜치: `origin/feat/mobile-dashboard-redesign`
- 참고 음식 데이터 브랜치: `origin/docs/data-yolo-food-detection`
- 목적: 팀원이 작업한 mobile UIUX 브랜치와 음식 YOLO/data 브랜치를 현재 backend-connected OCR/YOLO/Ollama 흐름에 맞춰 어디까지 가져올지 정리하고, 선별 이식된 항목과 제외 항목을 다음 작업자가 이어서 검증할 수 있게 남긴다.

## 브랜치/커밋 범위

| 구분 | 기준 |
| --- | --- |
| 현재 브랜치 | `feat/db-internal-learning-pipeline` |
| 현재 head | `dd3aebc` |
| UIUX 참고 브랜치 head | `e50114c68147` |
| 음식 데이터 참고 브랜치 head | `c1a2fb2cb91f` |

## 수행한 작업

- `origin/feat/mobile-dashboard-redesign` 분석
  - mobile 전체 tree를 그대로 가져오면 현재 `mobile/lib/core/api`, `mobile/lib/core/config`, consent/dashboard/supplements feature 구조, 테스트, Android signing guardrail, iOS project 일부가 삭제 또는 대체되는 것을 확인했다.
  - source branch에는 `API_BASE_URL`, `.env` asset loading, mock analysis/auth 흐름, OAuth 중심 코드가 섞여 있어 현재 `LEMON_API_BASE_URL`, `LEMON_API_TOKEN`, `LEMON_DEV_GATEWAY_TOKEN`, `LEMON_CERTIFICATE_PINS` 기반 흐름과 충돌한다.
  - 현재 브랜치에는 이미 17 Pro 스타일의 dashboard/camera/settings/gallery 하단 navigation 흐름이 선별 반영되어 있으므로, 이번 단계에서는 UIUX 브랜치에서 추가 파일을 무작정 restore하지 않는 것으로 판단했다.

- `origin/docs/data-yolo-food-detection` 분석
  - 음식 이미지 인식과 RDA 매칭에 필요한 `meal` domain code, RDA matcher, unit/integration tests, meal vision fixture, RDA reference data, food image manifest/script, YOLO baseline result artifact를 확인했다.
  - source branch의 backend root는 `backend/src/...` 구조였기 때문에 현재 repo의 실제 backend root인 `backend/Nutrition-backend/src/...`로 포팅해야 한다고 판단했다.
  - source branch의 일부 run metadata와 과거 planning 문서에는 로컬 Windows path가 포함되어 있어, 해당 파일들은 그대로 가져오지 않는 대상으로 분리했다.

- 현재 브랜치로 선별 이식한 항목
  - `backend/Food-backend/src/meal/`
  - `backend/Food-backend/src/nutrition/rda_matcher.py`
  - `backend/Food-backend/tests/unit/meal/`
  - `backend/Food-backend/tests/integration/meal/`
  - `backend/Food-backend/tests/unit/nutrition/test_rda_matcher.py`
  - `data/meal_vision/`
  - `data/rda/`
  - `data/food_images/manifests/roboflow_aihub_class_map_50.csv`
  - `data/food_images/manifests/roboflow_autolabel_food_prompts_50_aihub_aligned.csv`
  - `data/food_images/scripts/convert_aihub_50_to_yolo.py`
  - `runs/food_yolo/exp01_yolov8n_baseline_pc1_b48_w8_cache_disk_det_true/results.csv`
  - `docs/superpowers/plans/2026-05-27-aihub-yolo-todo.md`
  - `docs/superpowers/plans/2026-05-27-aihub-yolo-balanced500-yolo11s-plan.md`
  - `docs/superpowers/specs/2026-05-27-aihub-yolo-balanced500-yolo11s-design.md`

- 이식 중 보정한 항목
  - `backend/src/...` 기반 import/test 경로를 현재 backend layout인 `backend/Nutrition-backend/src/...` 기준으로 이동했다.
  - 테스트의 `REPO_ROOT` 계산을 현재 파일 깊이에 맞게 조정했다.
  - `convert_aihub_50_to_yolo.py`의 hard-coded Windows 기본 경로를 repo-relative 기본 경로로 바꿨다.
  - `7z` executable 기본값은 PATH 기반 탐색으로 바꿔, 특정 PC 절대 경로에 의존하지 않게 했다.
  - 이후 `meal` domain은 현재 Nutrition API runtime과 혼동되지 않도록 `backend/Food-backend/`로 다시 분리했다.

## 검증 결과

- 참고 브랜치 head 확인
  - `origin/feat/mobile-dashboard-redesign`: `e50114c68147`
  - `origin/docs/data-yolo-food-detection`: `c1a2fb2cb91f`
- food/RDA focused pytest
  - 실행 범위: meal unit tests, RDA matcher unit test, meal integration test
  - 결과: `284 passed`
  - 비고: `/private/tmp/lemon-p1-quality-venv/bin/python`에는 `pytest`가 없어, 현재 local Python 환경으로 focused test를 실행했다.
- Food-backend 분리 후 focused pytest
  - 실행 범위: `backend/Food-backend/tests/unit/meal`, `backend/Food-backend/tests/unit/nutrition/test_rda_matcher.py`, `backend/Food-backend/tests/integration/meal`
  - commit body 기준으로 분리 후 focused test, Nutrition-backend unit collection, formatting/lint/security gate를 통과한 뒤 push했다.
- formatting/lint
  - `ruff check --fix`로 import sort 10건을 정리했다.
  - `black`으로 새 Python 파일 formatting 12건을 정리했다.
  - `black --check`: 통과
  - `ruff check`: 통과
- backend unit collection
  - `backend/Nutrition-backend/tests/unit --collect-only`: `1418 tests collected`
- 보안/로컬 경로 1차 점검
  - 이식 대상 경로에서 `.env`, ngrok token/URL, provider payload, private key, service role key, `/Users/`, `D:\`, `C:\` 패턴이 커밋 대상 코드/데이터에 섞이지 않았는지 grep 기준으로 확인했다.
- secret scan
  - `detect-secrets scan` on selected import/docs paths: findings 없음
- 아직 완료되지 않은 검증
  - Android mobile OCR/YOLO/Ollama smoke는 다음 단계에서 이어서 실행해야 한다.

## 남은 TODO

1. mobile/UIUX 반영 판단 유지
   - UIUX 브랜치의 전체 `mobile/` tree restore는 하지 않는다.
   - 현재 앱의 endpoint 계약, debug provider selector, Android emulator base URL, token guardrail을 유지한다.
   - 필요한 경우 source 화면 단위 component만 다시 비교하되 mock auth/mock analysis 코드는 제외한다.

2. Android OCR/YOLO/Ollama smoke
   - Android emulator는 `LEMON_API_BASE_URL=http://10.0.2.2:8000/api/v1`로 실행한다.
   - OCR provider는 `configured`, `paddleocr`, `google_vision`, `clova` selector가 backend까지 전달되는지 먼저 본다.
   - YOLO와 Ollama는 mobile fake endpoint가 아니라 backend runtime env로만 켠다.

3. 단계 커밋/푸시
   - formatting, tests, secret check가 끝난 뒤 선별 이식 diff만 stage한다.
   - 기존 untracked 개인/생성 폴더는 stage하지 않는다.
   - 커밋 메시지는 팀 규칙에 맞춰 `feat(meal): 식단 YOLO 데이터 파이프라인 이식`처럼 Conventional Commits 형식을 사용한다.

4. Food-backend 연결 설계
   - Food-backend는 분리된 작업 공간이므로 Nutrition-backend 모바일 OCR endpoint에 바로 섞지 않는다.
   - 식단 촬영 endpoint가 필요하면 별도 API contract, auth/consent, raw image retention, YOLO model loading 정책을 먼저 문서화한다.

## 주의할 파일/커밋 제외 항목

- UIUX 브랜치에서 그대로 가져오지 않을 항목
  - `mobile/.env.example`
  - `mobile/docs/integration_notes.md`
  - source auth/password/OAuth mock flow
  - source mock analysis result flow
  - full Android/iOS replacement diff
  - `.env` asset loading과 `flutter_dotenv` 기반 runtime config
  - 현재 `android/key.properties.example`을 삭제하는 변경

- 음식 데이터 브랜치에서 그대로 가져오지 않을 항목
  - 로컬 Windows path가 포함된 historical docs
  - 로컬 training path가 들어간 `args.yaml`
  - 사용자 PC 절대 경로에 의존하는 script 기본값

- 계속 커밋 금지
  - `.env`
  - Supabase service role key
  - ngrok token/public URL
  - raw OCR text
  - provider raw payload
  - image bytes
  - storage object URI/path
  - signed URL/public URL
  - private local absolute path가 포함된 metadata

- 현재 건드리지 않은 untracked 항목
  - `.omc/`
  - `docs/Nutrition-docs/core-algorithm/`
  - `mobile/assets/mascot/Mascot_AppIcon_Rebuild_Assets/`

## 참고 공식 문서

- Flutter CLI: <https://docs.flutter.dev/reference/flutter-cli>
- Android emulator networking: <https://developer.android.com/studio/run/emulator-networking-address>
- Flutter camera plugin: <https://pub.dev/packages/camera>
- ngrok CLI: <https://ngrok.com/docs/agent/cli/>
