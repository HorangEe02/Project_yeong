# 2026-05-27 현재 작업 요약

## 기준 정보

- 작성일: 2026-05-27
- 대상 repo: `/Users/yeong/99_me/00_github/03_lemon_healthcare/Lemon-Aid`
- 작업 브랜치: `feat/db-internal-learning-pipeline`
- 최신 동기화 head: `b04238f feat(nutrition): AUDIT-KR 자가검진 점수화`
- 원격 push 대상: `origin/feat/db-internal-learning-pipeline`
- 작성 목적: 오늘 진행한 backend, mobile smoke 준비, Food-backend 분리, core algorithm 적용 작업을 현재 head 기준으로 정리한다.

## 브랜치/커밋 범위

| 커밋 범위 | 요약 |
| --- | --- |
| `257a48e` - `550bf08` | 멀티모달 저장소, 건강/의료 저장 API, OCR 확인 기록 승격, learning dataset/model registry CLI, Supabase 보안 preflight |
| `c26b546` - `dd3aebc` | 식단 YOLO/RDA 데이터 파이프라인 선별 이식, `backend/Food-backend/` 분리, AIHub YOLO 계획 문서 정리 |
| `1b49bea` - `fd71cf0` | 2026-05-27 todo/checkpoint 문서화, core algorithm 적용 계획과 중간 snapshot 정리 |
| `703bee2` - `54e4656` | BMI, activity, metabolism, weight prediction, nutrition diagnosis, supplement safety 문구와 고위험 분기 정렬 |
| `e45cd7b` - `b04238f` | 노인 KDRIs 라우팅 고정, 흡연/음주 활동 안전 안내, AUDIT-KR 10문항 점수화 API 추가 |

## 수행한 작업

- PostgreSQL/Supabase 저장소와 privacy 경계
  - backend-only media, meal, health profile/metric, medical record, learning dataset/model registry 흐름을 보강했다.
  - raw OCR text, provider payload, image bytes, object URI/path, signed/public URL이 응답과 operator 출력에 노출되지 않도록 sanitizer/test 흐름을 유지했다.

- retraining operator와 learning registry
  - dataset version 생성, annotation review import, lifecycle transition, training manifest export, training run registration, candidate/eval/promotion/retirement 흐름을 추가했다.
  - operator stdout에는 manifest hash, operator hash, reviewer hash, raw payload 계열 값이 직접 출력되지 않도록 제한했다.

- mobile/OCR/YOLO/Ollama smoke 준비
  - Android emulator 기준 `LEMON_API_BASE_URL=http://10.0.2.2:8000/api/v1` 흐름을 유지했다.
  - supplement OCR endpoint 계약은 `POST /api/v1/supplements/analyze`, multipart field `image`, form field `client_request_id`, `ocr_provider`로 유지했다.
  - YOLO와 Ollama는 모바일 mock endpoint가 아니라 backend runtime 설정으로 제어하는 방향을 유지했다.

- Food-backend 분리
  - 식단 이미지 분석과 RDA matcher를 현재 Nutrition-backend runtime과 혼동하지 않도록 `backend/Food-backend/`로 분리했다.
  - 데이터/manifest/script와 AIHub YOLO 계획 문서는 유지하되 모델 weight, private path, raw vision payload는 커밋하지 않았다.

- core algorithm 적용
  - KDRIs 노인 구간 라우팅을 test로 고정했다.
  - 활동 점수 응답에 흡연 및 AUDIT-KR 기반 안전 메시지를 추가했다.
  - AUDIT-KR 10문항 숫자 점수 입력, 성별 cut-off, 위험 음주 영양 우선 안내, 의존 cut-off 도달 시 자동 영양제 추천 보류 응답을 추가했다.
  - 새 endpoint는 `/api/v1/nutrition/audit-kr`이며 입력은 질문 문구가 아닌 10개 항목 점수만 받는다.

## 검증 결과

- AUDIT-KR phase
  - `black --check backend/Nutrition-backend/src/nutrition/audit_kr.py backend/Nutrition-backend/src/models/schemas/nutrition.py backend/Nutrition-backend/src/api/v1/nutrition.py backend/Nutrition-backend/tests/unit/nutrition/test_audit_kr.py`
  - `ruff check backend/Nutrition-backend/src/nutrition/audit_kr.py backend/Nutrition-backend/src/models/schemas/nutrition.py backend/Nutrition-backend/src/api/v1/nutrition.py backend/Nutrition-backend/tests/unit/nutrition/test_audit_kr.py`
  - `PYTHONPATH=backend/Nutrition-backend:backend /opt/anaconda3/bin/python -m pytest backend/Nutrition-backend/tests/unit/nutrition/test_audit_kr.py -q --no-cov`: 5 passed
  - `PYTHONPATH=backend/Nutrition-backend:backend /opt/anaconda3/bin/python -m pytest backend/Nutrition-backend/tests/unit/nutrition backend/Nutrition-backend/tests/unit/services/test_nutrition_diagnosis.py backend/Nutrition-backend/tests/unit/test_security_middleware.py -q --no-cov`: 61 passed
  - `PYTHONPATH=backend/Nutrition-backend:backend /opt/anaconda3/bin/python -m pytest backend/Nutrition-backend/tests/unit -q --no-cov`: 1174 passed
  - `git diff --check`
  - `detect-secrets scan` on changed AUDIT-KR files: no findings

- Push 상태
  - `b04238f feat(nutrition): AUDIT-KR 자가검진 점수화`까지 `origin/feat/db-internal-learning-pipeline`에 push 완료했다.

## 남은 TODO

1. Android Studio smoke를 이어서 실행한다.
   - Android emulator에서 gallery/camera 입력이 실제 `POST /api/v1/supplements/analyze`로 도달하는지 확인한다.
   - provider selector 값 `configured`, `paddleocr`, `google_vision`, `clova` 전달 여부를 확인한다.

2. OCR 결과가 ingredients 0으로 비는 경우 원인을 분리한다.
   - endpoint 도달 여부와 provider 실행 여부를 먼저 본다.
   - 그 다음 parser/domain correction, 이미지 품질, YOLO ROI, provider별 OCR 품질 비교 순서로 본다.

3. core algorithm 남은 범위를 이어서 구현한다.
   - 식단 주류 category 입력과 alcohol kcal 연동
   - full Hall dynamic weight model
   - DASH/ADA/KDOQI/EASL 등 질환별 nutrition guide routing
   - DrugBank/Lexicomp급 상호작용 DB 연동 또는 안전한 placeholder boundary
   - wearable cadence/HR integration

4. Supabase live preflight를 별도 opt-in으로 진행한다.
   - local ignored `.env`만 사용한다.
   - `check_learning_vector_db_security.py --strict`를 sanitized 출력 기준으로 실행한다.

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
- 현재 남겨둔 untracked 항목:
  - `.omc/`
  - `mobile/assets/mascot/Mascot_AppIcon_Rebuild_Assets/`
- 오늘자 이전 checkpoint 문서는 당시 상태를 보존하는 historical snapshot으로 본다.
