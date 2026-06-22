# Lemon Healthcare 팀 공유 보고서 - 2026-05-14 작업 내용 정리

## 한 줄 요약

이번 작업은 Lemon Healthcare 백엔드가 실제 서비스에 들어가기 전에 반드시 정리해야 할 안전장치와 기준 데이터를 맞춘 작업입니다. 핵심은 네 가지입니다. 첫째, 영양 기준 데이터를 임시 샘플이 아니라 KDRIs 2025 기준으로 바꿨습니다. 둘째, 운영 환경에서 로그인 토큰을 더 엄격하게 검증하도록 했습니다. 셋째, 만성질환 정보가 있을 때 부족 가능성이 있는 영양소를 먼저 확인할 수 있게 했습니다. 넷째, 아직 검증이 끝나지 않은 기능은 기본으로 꺼지도록 정리했습니다.

## 기준 정보

- 작업 대상일: 2026-05-14
- 문서 보정일: 2026-05-15
- 로컬 경로: `/Users/yeong/99_me/00_github/03_lemon_healthcare`
- 프로젝트 루트: `yeong-Lemon-Aid`
- 현재 브랜치: `codex/p1-5-stabilization`
- 현재 상태: 변경 파일이 아직 작업 트리에 남아 있습니다. 커밋 전에 포함할 파일과 제외할 파일을 선별해야 합니다.

## 왜 이 작업을 했나

지금 프로젝트는 AI/OCR/건강 데이터 기능을 빠르게 붙이는 단계에 있습니다. 이때 기준 데이터, 인증, 동의, 기능 켜짐/꺼짐 정책이 흔들리면 이후 기능을 붙일수록 오류와 보안 위험이 커집니다.

그래서 이번 작업의 목표는 새 기능을 더 추가하기 전에 “운영에 올려도 되는 기본선”을 맞추는 것이었습니다. 사용자가 보는 화면이 갑자기 바뀌는 작업보다는, 서버가 올바른 기준으로 판단하고 위험한 기능을 실수로 실행하지 않도록 만드는 기반 작업에 가깝습니다.

## 작업 내용 쉽게 보기

### 1. KDRIs 2025 영양 기준 데이터 전환

KDRIs는 한국인 영양소 섭취기준입니다. 서비스에서 “비타민 C가 부족한지”, “어떤 영양소를 먼저 확인해야 하는지”를 판단하려면 기준표가 필요합니다.

기존에는 구현 확인용 샘플 데이터가 남아 있었습니다. 이번 작업에서는 실제 사용 기준에 맞춰 KDRIs 2025 데이터 1,795개 행을 승인된 데이터로 정리했습니다.

이번에 한 일:

- `data/nutrition_reference/kdris/kdris_2025.csv`를 production 기준 데이터로 승격했습니다.
- 각 데이터가 어디에서 왔는지 추적할 수 있도록 manifest 파일에 상태와 checksum을 기록했습니다.
- 임신 주차, 엽산 상한, 나이 구간, 수분 기준처럼 단순 표로는 놓치기 쉬운 항목도 담을 수 있게 스키마를 확장했습니다.
- production에서는 샘플 데이터를 쓰지 못하도록 `ALLOW_SAMPLE_KDRIS=false` 기준을 정리했습니다.

팀이 알아야 할 의미:

- 앞으로 영양 분석은 샘플이 아니라 KDRIs 2025 기준으로 판단합니다.
- 데이터 파일이 바뀌면 validator를 다시 돌려야 합니다.
- 기준 데이터의 출처와 검토 상태를 함께 관리해야 합니다.

### 2. JWT production 인증 경로 강화

JWT는 사용자가 로그인한 뒤 서버에 “이 요청은 인증된 사용자 요청입니다”라고 증명할 때 쓰는 토큰입니다. production에서는 이 토큰이 진짜인지, 올바른 방식으로 서명됐는지, 다른 용도의 토큰이 잘못 들어온 것은 아닌지 확인해야 합니다.

이번 작업에서는 서버가 토큰을 더 신중하게 확인하도록 했습니다.

이번에 한 일:

- 토큰 header의 `kid`, `alg`, token type을 먼저 확인하도록 했습니다.
- `kid`가 없거나 허용하지 않은 알고리즘이면 외부 키 조회 전에 바로 거부합니다.
- JWKS key rotation, unknown `kid`, timeout, invalid algorithm, id-token confusion 상황을 테스트로 고정했습니다.
- OIDC discovery 사전 점검용 스크립트를 분리했습니다.
- OpenAPI 문서에도 Bearer 인증 계약이 노출되도록 테스트했습니다.

팀이 알아야 할 의미:

- 개발용 단순 인증과 운영용 토큰 검증은 다릅니다.
- 운영 배포 전에는 실제 IdP 설정으로 discovery preflight를 한 번 더 확인해야 합니다.
- 인증 실패 케이스도 정상 흐름만큼 중요하게 테스트해야 합니다.

### 3. 만성질환자 부족 영양소 우선순위

사용자가 만성질환 정보를 입력했을 때, 서비스가 모든 영양소를 같은 순서로 보여주면 중요한 확인 항목이 묻힐 수 있습니다. 이번 작업은 이미 “부족” 또는 “낮음”으로 판정된 영양소 중에서 만성질환과 관련이 있는 항목을 더 먼저 보이게 하는 기능입니다.

이번에 한 일:

- `backend/src/nutrition/chronic_priority.py`를 추가했습니다.
- 고혈압, 당뇨 등 질환 코드를 내부 표준 코드로 정리하는 alias 처리를 넣었습니다.
- 근거가 있는 priority/caution rule을 `data/nutrition_reference/nutrient/chronic_nutrient_priorities.json`에 분리했습니다.
- 이미 부족하거나 낮은 영양소에만 우선순위 boost가 적용되도록 했습니다.
- CKD처럼 “주의해서 봐야 하지만 부족 우선순위를 올리면 안 되는” 항목은 따로 처리했습니다.
- 사용자에게 보이는 문구는 “우선 확인 대상” 수준으로 제한했습니다.

팀이 알아야 할 의미:

- 이 기능은 치료나 복용량 안내가 아닙니다.
- 사용자가 확인해야 할 순서를 돕는 기능입니다.
- 진단, 치료, 처방, 복용량 변경 같은 표현은 사용자 문구에서 막아두었습니다.

### 4. 아직 준비되지 않은 기능은 기본으로 꺼두기

프로젝트에는 처방전 OCR, 검사표 OCR, medication safety alert, 이미지 학습, pgvector 저장 같은 기능 후보가 있습니다. 이런 기능은 개인정보, 건강정보, 외부 서비스 호출과 연결될 수 있으므로 검증 없이 켜지면 위험합니다.

이번 작업에서는 이 기능들이 기본으로 꺼져 있고, production에서 실수로 켜지지 않도록 막았습니다.

이번에 한 일:

- `feature_prescription_ocr_intake`, `feature_lab_result_ocr_intake`, `feature_medication_safety_alert` 기본값을 `false`로 맞췄습니다.
- production에서 sign-off 없이 위 기능을 `true`로 켜면 서버가 시작되지 않도록 검증을 추가했습니다.
- readiness JSON과 `.env.example`, setup guide, docs/22, docs/23 설명을 같은 기준으로 맞췄습니다.

팀이 알아야 할 의미:

- 기능 코드나 계획 문서가 있어도 기본 실행되는 것은 아닙니다.
- 위험도가 높은 기능은 별도 승인과 테스트 후 켜야 합니다.
- `.env`에서 flag를 바꿀 때는 production guard를 함께 확인해야 합니다.

### 5. 상태 문서 갱신

팀원이 현재 어디까지 끝났고 무엇이 남았는지 같은 기준으로 보도록 docs/22, docs/23을 갱신했습니다.

이번에 한 일:

- `docs/Nutrition-docs/22-current-implementation-status-map.md`에 Weekly Snapshot을 추가했습니다.
- KDRIs 2025, JWT production 경로, 만성질환 우선순위, feature flag default-off를 완료 상태로 정리했습니다.
- `docs/Nutrition-docs/23-p1-stabilization-plan.md`에서 P1-S2 Feature Flag Default-Off Correction을 완료 상태로 바꿨습니다.
- 최신 검증 결과를 문서에 반영했습니다.

팀이 알아야 할 의미:

- docs/22는 현재 구현 상태를 보는 지도입니다.
- docs/23은 P1 안정화 계획과 완료 기준을 보는 문서입니다.
- 계획 문서에 있는 모든 항목이 실제 구현 완료를 뜻하지는 않으므로, 상태값과 검증 결과를 함께 봐야 합니다.

### 6. Google Vision OCR provider 구현 계획 정리

보충제 라벨 OCR 품질을 높이기 위해 Google Vision OCR provider를 1차 성능 우선 후보로 정리했습니다. 다만 실제 외부 호출은 아직 기본 활성화하지 않았습니다.

이번에 한 일:

- `docs/Nutrition-docs/35-google-vision-ocr-provider-implementation-plan.md`를 추가했습니다.
- Google Cloud Vision `DOCUMENT_TEXT_DETECTION`을 1차 provider 후보로 정리했습니다.
- 기본값은 OCR provider 없음, 외부 OCR 호출 비활성으로 설계했습니다.
- 사용자가 외부 OCR 처리에 동의하고 운영자가 명시적으로 켰을 때만 호출하는 방향으로 정리했습니다.
- 실제 Google 호출은 CI 기본 job에서 제외하고, fake client 테스트와 opt-in smoke test로 분리하는 전략을 잡았습니다.

팀이 알아야 할 의미:

- Google Vision은 성능 개선 후보입니다.
- 기본 실행 경로는 아직 외부 OCR을 호출하지 않습니다.
- 사용자 이미지가 외부 서비스로 전송되는 흐름은 별도 동의와 운영 설정이 필요합니다.

### 7. 커밋 전 정리

작업량이 많아지면서 커밋 전에 파일 상태를 정리해야 했습니다.

이번에 한 일:

- KDRIs CSV 줄끝을 LF로 정규화해 `git diff --check` 실패 원인을 제거했습니다.
- 줄끝이 바뀐 만큼 checksum을 다시 계산해 manifest에 반영했습니다.
- `HANDOFF.md`를 현재 브랜치와 리뷰 기준에 맞게 다시 작성했습니다.
- `main` 직접 반영이 아니라 팀 브랜치 리뷰 후 반영하는 방향을 명시했습니다.

팀이 알아야 할 의미:

- CSV처럼 데이터 파일은 내용이 같아 보여도 줄끝이 바뀌면 checksum이 달라질 수 있습니다.
- 커밋 전에는 코드, 데이터, 문서, 로컬 산출물을 반드시 나눠서 봐야 합니다.

## 검증 결과

로컬 backend 기준으로 아래 검증을 통과했습니다.

| 검증 | 명령 | 결과 |
| --- | --- | --- |
| Formatting | `.venv/bin/black --check src tests alembic` | pass, 160 files unchanged |
| Lint | `.venv/bin/ruff check src tests alembic` | pass |
| Type check | `.venv/bin/mypy src tests --strict` | pass, 155 source files |
| Full pytest coverage | `.venv/bin/python -m pytest --cov-report=term-missing` | pass, `313 passed, 1 skipped`, total coverage `87.75%` |
| KDRIs validator | `.venv/bin/python scripts/validate_kdris_dataset.py --require-approved` | pass, 1,795 rows validated |
| Settings JSON parse | `.venv/bin/python -m json.tool ../config/implementation-readiness.settings.json` | pass |
| Diff whitespace | `git diff --check` | pass |

참고: 특정 테스트 파일만 따로 돌릴 때는 전체 coverage 기준 때문에 실패처럼 보일 수 있습니다. 이 경우에는 `--no-cov` 또는 `-o addopts=''`로 개별 테스트 자체만 확인하고, coverage 통과 여부는 full pytest 결과를 기준으로 봅니다.

## 주요 변경 파일 묶음

### 설정과 정책

- `backend/src/config.py`
- `backend/.env.example`
- `config/implementation-readiness.settings.json`
- `docs/Nutrition-docs/dev-guides/00-setup-environment.md`

### KDRIs 2025 데이터

- `data/nutrition_reference/kdris/kdris_2025.csv`
- `data/nutrition_reference/kdris/kdris_dataset_schema.md`
- `data/nutrition_reference/kdris/kdris_source_manifest.json`
- `data/nutrition_reference/kdris/review/2025/*`
- `data/nutrition_reference/kdris/raw/2025/*`
- `backend/scripts/validate_kdris_dataset.py`
- KDRIs digitization/validation scripts

### JWT/OIDC 보안

- `backend/src/security/auth.py`
- `backend/src/security/oidc.py`
- `backend/scripts/check_oidc_discovery.py`
- `backend/tests/integration/security/test_jwt_production_path.py`
- `backend/tests/unit/security/test_auth.py`
- `backend/tests/unit/security/test_oidc.py`
- `backend/tests/integration/api/test_p1_api_contract.py`

### 만성질환 우선순위

- `backend/src/nutrition/chronic_priority.py`
- `data/nutrition_reference/nutrient/chronic_nutrient_priorities.json`
- `backend/src/nutrition/deficiency_analysis.py`
- `backend/src/models/schemas/nutrition.py`
- `backend/tests/unit/nutrition/test_chronic_priority.py`
- `backend/tests/unit/nutrition/test_kdris_analysis.py`

### 상태 문서

- `docs/Nutrition-docs/22-current-implementation-status-map.md`
- `docs/Nutrition-docs/23-p1-stabilization-plan.md`
- `docs/Nutrition-docs/31-backend-feature-specifications.md`
- `docs/Nutrition-docs/32-paddleocr-local-fallback-plan.md`
- `docs/Nutrition-docs/33-three-tier-ocr-pipeline-implementation-guide.md`
- `docs/Nutrition-docs/34-llm-serving-engines-multi-environment-setup-guide.md`
- `docs/Nutrition-docs/35-google-vision-ocr-provider-implementation-plan.md`
- `HANDOFF.md`
- `outputs/todo-list/2026-05-14/2026-05-14-team-work-summary.md`

## 현재 작업 트리 주의사항

현재 작업 트리에는 프로젝트에 포함할 후보와 제외해야 할 로컬 산출물이 함께 있습니다. 커밋 전에 반드시 선별해야 합니다.

포함 후보:

- KDRIs 2025 데이터와 검증 스크립트
- JWT/OIDC 보안 강화 파일
- 만성질환 영양소 우선순위 파일
- feature flag default-off 설정과 테스트
- docs/22, docs/23, docs/Nutrition-docs/31-35
- `HANDOFF.md`
- 이 팀 공유 보고서 파일

제외 후보:

- `assets/mascot/`
- `records/meetings/`
- `outputs/generated/`
- `outputs/reports/`
- `../00_plusultra/`
- 기타 이번 backend 안정화와 직접 관련 없는 로컬 산출물

## 다음 작업 제안

### 1. CI hardening

로컬에서 통과한 검증이 GitHub Actions에서도 같은 기준으로 돌도록 보강해야 합니다.

- backend CI trigger에 `data/nutrition_reference/kdris/**`, `data/nutrition_reference/nutrient/**`, `config/**` 경로 추가
- CI에 `validate_kdris_dataset.py --require-approved` 추가
- CI settings smoke에 regulated flag default-off 확인 추가
- docs-only 변경과 backend/data 변경 path filter 재확인

### 2. Stabilization PR gate

P1 이후 AI/OCR/YOLO/학습 기능이 기준선을 깨지 않도록 PR checklist를 강화해야 합니다.

- KDRIs validator 통과 확인
- JWT/OIDC production-path test 통과 확인
- 만성질환 우선순위 문구에 금지 표현이 없는지 확인
- feature flag를 `true`로 바꿀 때 sign-off 문서 요구
- raw image/raw OCR text 저장 금지 확인

### 3. 커밋 단위 정리

현재 변경량이 크므로 하나의 커밋으로 묶기보다 의미 단위로 나누는 것이 안전합니다.

권장 커밋:

1. `fix(config): default non-P1 regulated flags to disabled`
   - 이유: 아직 검증되지 않은 기능이 production에서 실수로 켜지지 않도록 하기 위함.
2. `data(kdris): import reviewed 2025 KDRIs reference rows`
   - 이유: 영양 분석 기준을 샘플 데이터에서 승인된 2025 데이터로 바꾸기 위함.
3. `fix(security): harden JWT JWKS verification path`
   - 이유: 운영 로그인 토큰 검증에서 잘못된 토큰을 더 안전하게 거부하기 위함.
4. `feat(nutrition): apply chronic-condition nutrient priority lookup`
   - 이유: 만성질환 정보가 있을 때 확인 우선순위를 더 잘 보여주기 위함.
5. `docs(status): refresh P1 stabilization map`
   - 이유: 팀이 현재 구현 상태와 남은 범위를 같은 기준으로 보게 하기 위함.
6. `ci(backend): add data and settings stabilization gates`
   - 이유: 로컬 검증 기준을 GitHub Actions에서도 반복 가능하게 만들기 위함.

### 4. Google Vision OCR provider 구현 착수

docs/35 기준 다음 단계입니다.

- OCR 호출 전용 계정 또는 attached service account 방식 결정
- credential JSON을 저장소에 두지 않는 운영 규칙 확정
- `OCR_PRIMARY_PROVIDER`, `ALLOW_EXTERNAL_OCR`, `GOOGLE_CLOUD_PROJECT`, `GOOGLE_VISION_*` settings 추가
- `EXTERNAL_OCR_PROCESSING` consent type과 active policy 추가
- `GoogleVisionOCRAdapter`와 adapter factory 구현
- `/api/v1/supplements/analyze`에서 OCR+parse preview가 한 번에 동작하도록 연결
- fake client 기반 unit/integration test 작성
- 실제 Google smoke test는 명시 opt-in gate 뒤에서만 실행

### 5. OCR 3-tier 확장 구현

Google Vision MVP 이후 docs/33 기준 다음 단계입니다.

- YOLO ROI 실제 추론 연결
- Ollama multimodal fallback/verification 연결
- PaddleOCR 로컬 fallback 또는 CLOVA fallback 우선순위 재검토
- 라벨 fixture 기준 정확도/latency 리포트 작성
- 발주처 리뷰 게이트 산출물 준비

### 6. Learning/vector DB 구현

현재는 gate와 disabled adapter 골격만 있습니다. 실제 구현 전에는 아래 작업이 필요합니다.

- pgvector extension migration
- image embedding table
- 실제 embedding model runner
- vector upsert worker
- image object storage 연동

### 7. Prescription/lab OCR intake 구현

regulated flag는 default-off로 정리됐으므로, 다음 구현도 intake-only 흐름으로 진행해야 합니다.

- 처방전 OCR intake endpoint
- 검사표 OCR intake endpoint
- 별도 민감 동의
- 원문 이미지 자동삭제 정책
- 사용자 확인 단계
- 전문의 상담 CTA
- 직접 복용량 변경 안내 금지 테스트

## 팀원이 알아야 할 결정 사항

- KDRIs 2025는 production dataset으로 승격되었습니다. 샘플 fixture는 production에서 금지됩니다.
- production 인증은 OAuth/OIDC Bearer access token 검증 경로를 기준으로 봅니다.
- 만성질환자 우선순위는 치료나 복용량 안내가 아니라 확인 순서 보조입니다.
- regulated feature flag는 모두 기본 `false`입니다. production에서 `true`로 켜려면 별도 sign-off가 필요합니다.
- Google Vision OCR은 성능 우선 provider 후보지만, 외부 OCR 전송 동의와 `ALLOW_EXTERNAL_OCR=true` 없이 호출하지 않습니다.
- `main` 직접 반영은 제외하고 팀 브랜치 리뷰 후 반영하는 방향입니다.
- YOLO는 제품명이나 성분을 읽는 모델이 아니라 라벨 영역을 찾는 보조 도구입니다.
- OCR/LLM 결과는 사용자 확인 전까지 확정 데이터가 아닙니다.

## 공식 문서 참고

- PyJWT API Reference: https://pyjwt.readthedocs.io/en/stable/api.html
- OpenID Connect Discovery 1.0: https://openid.net/specs/openid-connect-discovery-1_0.html
- Pydantic Settings: https://docs.pydantic.dev/latest/concepts/pydantic_settings/
- Pydantic validators: https://docs.pydantic.dev/latest/concepts/validators/
- pytest invocation: https://docs.pytest.org/en/stable/how-to/usage.html
- mypy command line: https://mypy.readthedocs.io/en/stable/command_line.html
- Ruff linter: https://docs.astral.sh/ruff/linter/
- Black `--check`: https://black.readthedocs.io/en/stable/usage_and_configuration/the_basics.html#check
- FastAPI `openapi_extra`: https://fastapi.tiangolo.com/advanced/path-operation-advanced-configuration/#openapi-extra
- OpenAPI security schemes: https://learn.openapis.org/specification/security.html
- Cloud Vision OCR: https://cloud.google.com/vision/docs/ocr
- Cloud Vision REST `images:annotate`: https://cloud.google.com/vision/docs/reference/rest/v1/images/annotate
- Cloud Vision Data Usage FAQ: https://cloud.google.com/vision/docs/data-usage
- Google Application Default Credentials: https://cloud.google.com/docs/authentication/application-default-credentials
