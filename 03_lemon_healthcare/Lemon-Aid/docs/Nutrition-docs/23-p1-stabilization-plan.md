# P1 Stabilization Plan

작성일: 2026-05-13

이 문서는 AI/이미지/학습 기능을 더 붙이기 전에 P1 backend 기준선을 고정하는 상세 설계와 구현 플랜이다. 목표는 새 AI 기능이 기존 API, 동의, 보안, 설정, OpenAPI contract 위에만 안전하게 올라가도록 만드는 것이다.

## 공식 문서 확인

- pytest invocation: <https://docs.pytest.org/en/stable/how-to/usage.html>
- GitHub Actions workflow syntax: <https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax>
- FastAPI `openapi_extra`: <https://fastapi.tiangolo.com/advanced/path-operation-advanced-configuration/#openapi-extra>
- Pydantic settings: <https://docs.pydantic.dev/latest/concepts/pydantic_settings/>
- mypy command line: <https://mypy.readthedocs.io/en/stable/command_line.html>
- Ruff linter: <https://docs.astral.sh/ruff/linter/>
- Black `--check`: <https://black.readthedocs.io/en/stable/usage_and_configuration/the_basics.html#check>

## 현재 기준선 확인 결과

작업 디렉터리: `03_lemon_healthcare/yeong-Lemon-Aid/backend`

| 항목 | 명령 | 현재 결과 |
| --- | --- | --- |
| 전체 backend test + coverage gate | `.venv/bin/python -m pytest --cov-report=term-missing` | `313 passed, 1 skipped`, total coverage `87.75%` |
| formatting | `.venv/bin/black --check src tests alembic` | pass |
| lint | `.venv/bin/ruff check src tests alembic` | pass |
| type check | `.venv/bin/mypy src tests --strict` | pass, `155 source files` |
| settings JSON parse | `.venv/bin/python -m json.tool ../config/implementation-readiness.settings.json` | pass |
| OpenAPI generation | `create_app().openapi()` | OpenAPI `3.1.0`, `21 paths` |
| AI flag defaults | `Settings(_env_file=None)` default check | `allow_external_llm`, `enable_multimodal_llm`, `enable_vision_classifier`, `enable_image_learning_pipeline`, `enable_pgvector_storage` all `false` |
| regulated flag defaults | `Settings(_env_file=None)` and readiness JSON default check | `feature_prescription_ocr_intake`, `feature_lab_result_ocr_intake`, `feature_medication_safety_alert`, `FEATURE_HOSPITAL_MOCK_FHIR` all `false` |

2026-05-15 재검증에서는 KDRIs 2025 전환 후 남아 있던 2020 sample 기대값 7건과 `google_cloud_api_key` 테스트의 `SecretStr` 타입 불일치 mypy 1건을 정리했다.

검증 중 `tests/unit/services/test_supplement_image_analysis.py`의 fake session id 보정 코드가 mypy `unreachable`을 발생시켰고, `getattr(..., "id", None)`로 런타임 의도를 유지하면서 수정했다.

## 브레인스토밍 결과

P1 안정화에서 가장 위험한 실패 모드는 네 가지다.

| 위험 | 왜 위험한가 | 안정화 방향 |
| --- | --- | --- |
| API contract drift | AI 기능 추가 중 기존 모바일/API 호출이 깨질 수 있음 | OpenAPI `x-contract-status`, scopes, consents, response examples를 테스트로 고정 |
| test baseline drift | 새 모듈 추가 후 전체 테스트는 통과하지만 CI path와 다르게 검증될 수 있음 | 로컬 검증 명령과 `17-lemon-backend-ci.yml` 명령을 동일하게 유지 |
| feature flag default drift | 비검증 AI/규제 기능이 기본 활성화될 수 있음 | 새 기능 플래그 기본값은 `false`; production에서는 sign-off 없이는 true 거부 |
| 설정/문서 불일치 | 운영자가 잘못된 env 또는 오래된 문서를 기준으로 배포할 수 있음 | `Settings`, `config/*.settings.json`, docs의 feature flag 표를 하나의 baseline으로 맞춤 |

## P1 안정화 범위

### 포함

- 기존 API와 OpenAPI contract 고정
- backend 전체 테스트 기준선 고정
- CI path와 로컬 검증 명령 정렬
- 설정 기본값과 production validation 검증
- 기능 플래그 default-off 원칙 확정
- AI/이미지/학습 모듈은 import 가능하되 runtime은 fail-closed 유지

### 제외

- YOLO inference 구현
- Ollama multimodal Image-to-Text 구현
- pgvector migration 또는 embedding 저장
- OCR 외부 provider 연결
- Hall-lite 동적 체중 모델 구현
- prescription/lab OCR 전용 endpoint 구현

## 안정화 설계

### 1. API Contract Freeze

현재 P1 contract 기준 파일은 `backend/tests/integration/api/test_p1_api_contract.py`다. P1 안정화에서는 이 테스트를 baseline gate로 승격한다.

고정할 항목:

- `POST /api/v1/supplements/analyze`
- `POST /api/v1/supplements`
- `GET /api/v1/supplements`
- `GET /api/v1/supplements/{supplement_id}`
- `DELETE /api/v1/supplements/{supplement_id}`
- `POST /api/v1/health/sync`
- `GET /api/v1/dashboard/summary`
- `GET /api/v1/nutrition/diagnosis/latest`

각 endpoint는 아래 OpenAPI extension을 유지해야 한다.

- `x-contract-status`
- `x-required-scopes`
- `x-required-consents`
- `security: [{"BearerAuth": []}]` for protected P1 endpoints

변경 규칙:

- 기존 path, method, scope, consent를 삭제하거나 완화하지 않는다.
- response status code를 변경할 때는 contract test를 먼저 변경하고 변경 이유를 PR에 기록한다.
- 501 contract stub은 P1 ready endpoint에 남기지 않는다.

### 2. Backend Test Baseline

P1 안정화 완료 조건은 로컬과 CI 모두 같은 검증 묶음을 통과하는 것이다.

필수 명령:

```bash
cd 03_lemon_healthcare/yeong-Lemon-Aid/backend
.venv/bin/black --check src tests alembic
.venv/bin/ruff check src tests alembic
.venv/bin/mypy src tests --strict
.venv/bin/python -m pytest --cov-report=xml --cov-report=term-missing
```

로컬에서 coverage artifact 생성을 피하고 기준선만 빠르게 볼 때는 다음을 사용한다.

```bash
COVERAGE_FILE=/private/tmp/lemon_p1_coverage \
  .venv/bin/python -m pytest --cov=src --cov-report=term-missing --cov-fail-under=80 -q
```

### 3. CI Path Freeze

현재 git root는 `/Users/yeong/99_me/00_github`이고 이 프로젝트 prefix는 `03_lemon_healthcare/`다. 따라서 root workflow `.github/workflows/17-lemon-backend-ci.yml`의 path filter와 `defaults.run.working-directory`는 이 prefix를 유지해야 한다.

현재 backend CI path:

- trigger path: `03_lemon_healthcare/yeong-Lemon-Aid/backend/**`
- workflow path: `.github/workflows/17-lemon-backend-ci.yml`
- working directory: `03_lemon_healthcare/yeong-Lemon-Aid/backend`
- Python matrix: `3.11`, `3.13`
- dependency file: `requirements.txt`, `requirements-dev.txt`
- PostgreSQL service: `postgres:16`, DB smoke job uses `DATABASE_URL` and `TEST_DATABASE_URL` both with `postgresql+asyncpg://postgres:postgres@localhost:5432/lemon_test`

P1 안정화 중 바꿀 수 없는 항목:

- Python `3.13`
- `black --check src tests alembic`
- `ruff check src tests alembic`
- `mypy src tests --strict`
- pytest coverage gate with `--cov-fail-under=80`
- `alembic upgrade head` against live PostgreSQL before pytest

### 4. Settings And Feature Flags

P1 안정화 원칙은 default-off다. 특히 AI/이미지/학습 플래그는 기본 `false`를 유지해야 한다.

현재 `Settings()` 기준으로 이미 default-off인 항목:

- `allow_external_llm=false`
- `enable_multimodal_llm=false`
- `enable_vision_classifier=false`
- `enable_image_learning_pipeline=false`
- `enable_pgvector_storage=false`

P1-S2 보정 완료 항목:

| 설정 | 보정 후 기본값 | P1 안정화 목표 |
| --- | --- | --- |
| `feature_prescription_ocr_intake` | `false` | `false` |
| `feature_lab_result_ocr_intake` | `false` | `false` |
| `feature_medication_safety_alert` | `false` | `false` |
| `FEATURE_PRESCRIPTION_OCR_INTAKE` in `implementation-readiness.settings.json` | `false` | `false` |
| `FEATURE_LAB_RESULT_OCR_INTAKE` in `implementation-readiness.settings.json` | `false` | `false` |
| `FEATURE_HOSPITAL_MOCK_FHIR` in `implementation-readiness.settings.json` | `false` | `false` |
| `FEATURE_MEDICATION_SAFETY_ALERT` in `implementation-readiness.settings.json` | `false` | `false` |

구현 완료 테스트:

- development 기본값에서 모든 non-P1 feature flag가 `false`인지 확인
- production에서 AI/vision/learning/regulated flag가 true이면 validation error
- `ALLOW_EXTERNAL_LLM=true`는 production에서 계속 거부
- feature flag 문서와 `Settings` 기본값이 충돌하지 않는지 검사

### 5. OpenAPI Contract Gate

FastAPI는 path operation의 `openapi_extra`를 OpenAPI schema에 병합한다. 현재 `route_contract()`가 이 경로를 사용하므로, contract gate는 생성된 `/openapi.json`을 직접 검사해야 한다.

P1 안정화 구현 시 검사할 항목:

- OpenAPI schema 생성 성공
- P1 endpoint path/method 존재
- `x-contract-status` 값 고정
- `x-required-scopes` 값 고정
- `x-required-consents` 값 고정
- protected endpoint에 Bearer auth security 표시
- OpenAPI examples에 금지 의료 표현이 포함되지 않음

기존 테스트:

- `tests/integration/api/test_p1_api_contract.py`
- `tests/integration/api/test_openapi_examples.py`

추가 권장:

- `tests/integration/api/test_p1_openapi_freeze.py`를 만들고 path/method/extension table을 한 곳에 둔다.
- snapshot 파일을 만들 경우 JSON 전체 snapshot 대신 P1 subset snapshot만 저장한다. 전체 OpenAPI snapshot은 사소한 schema 정렬 변경에도 과도하게 깨질 수 있다.

## 상세 구현 플랜

### P1-S0: Baseline Fix

목표: 현재 기준선이 CI 명령으로 완전히 통과하게 만든다.

작업:

- mypy/test/lint/format failure를 먼저 0으로 만든다.
- 새 기능 구현 없이 테스트 fake, 타입 annotation, docstring만 정리한다.
- 전체 backend test와 coverage gate를 통과시킨다.

완료 조건:

- `black`, `ruff`, `mypy`, `pytest` coverage gate 모두 pass
- 전체 backend test `313 passed, 1 skipped` 이상 유지

### P1-S1: Contract Freeze

목표: 기존 API contract를 테스트로 고정한다.

작업:

- `test_p1_api_contract.py`의 endpoint table을 현재 P1 API 기준으로 정리한다.
- OpenAPI generated schema에서 P1 subset만 검사하는 helper를 만든다.
- route별 scope, consent, contract status, auth security를 검증한다.

완료 조건:

- P1 endpoint 삭제, scope 완화, consent 제거가 테스트 실패로 드러난다.
- `POST /api/v1/supplements/analyze` 기본 동작은 intake-only로 유지된다.

### P1-S2: Feature Flag Default-Off Correction

상태: 완료.

목표: AI/규제/학습 기능이 실수로 기본 활성화되지 않게 한다.

작업:

- `backend/src/config.py`의 non-P1 feature flag 기본값을 `false`로 맞춘다.
- `config/implementation-readiness.settings.json`의 동일 flag 기본값도 `false`로 맞춘다.
- `docs/Nutrition-docs/22-current-implementation-status-map.md`와 관련 dev-guide의 flag 표를 갱신한다.
- production validation test를 보강한다.

완료 조건:

- `Settings()`에서 non-P1 feature flag가 모두 `false`
- production에서 sign-off 대상 flag true가 모두 거부됨
- 기존 P1 API 기능은 flag 변경과 무관하게 테스트 통과

### P1-S3: CI Path Hardening

상세 설계: [37-ci-hardening-design-plan.md](./37-ci-hardening-design-plan.md)

목표: 로컬 기준선과 GitHub Actions 기준선이 다르지 않게 한다.

작업:

- `.github/workflows/17-lemon-backend-ci.yml`의 path filter, working-directory, Python matrix를 재확인한다.
- backend workflow trigger에 `data/nutrition_reference/kdris/**`, `data/nutrition_reference/nutrient/**`, `config/**`를 포함한다.
- backend workflow에 `python scripts/validate_kdris_dataset.py --require-approved`를 추가한다.
- backend workflow에서 settings/OpenAPI contract smoke command를 명시적으로 실행한다.
- settings smoke는 regulated flag와 AI/OCR/YOLO/학습 flag의 default-off 상태를 함께 확인한다.
- docs-only 변경이 backend CI를 불필요하게 트리거하지 않는지 path filter를 확인한다.

권장 추가 command:

```bash
python -m json.tool ../config/implementation-readiness.settings.json > /tmp/implementation-readiness.settings.json
python scripts/validate_kdris_dataset.py --require-approved
python -c "from src.config import Settings; s=Settings(_env_file=None); assert not s.allow_external_llm and not s.enable_multimodal_llm and not s.enable_vision_classifier and not s.enable_image_learning_pipeline and not s.enable_pgvector_storage and not s.feature_prescription_ocr_intake and not s.feature_lab_result_ocr_intake and not s.feature_dosage_change_recommendation and not s.feature_medication_safety_alert"
python -c "from src.main import create_app; schema=create_app().openapi(); assert schema['openapi'].startswith('3.'); assert '/api/v1/supplements/analyze' in schema['paths']; assert '/api/v1/supplements/analyses/{analysis_id}/ocr-text' in schema['paths']; assert '/api/v1/nutrition/kdris' in schema['paths']; assert '/api/v1/nutrition/analyze' in schema['paths']"
```

현재 backend CI에는 위 설정/OpenAPI smoke, KDRIs 승인 데이터 검증, PostgreSQL `alembic upgrade head` smoke가 포함되어 있다.

완료 조건:

- backend 변경 PR에서 backend CI가 반드시 실행됨
- KDRIs/reference/config 변경 PR에서 backend CI가 반드시 실행됨
- docs-only 변경 PR에서 docs CI만 실행되어도 무방함
- 승인되지 않은 KDRIs 데이터가 CI에서 실패함
- regulated flag와 AI/OCR/YOLO/학습 flag가 기본 ON으로 바뀌면 CI에서 실패함
- CI 실패 원인이 local 재현 가능한 명령으로 대응됨

### P1-S4: Stabilization Manifest

상태: 완료.

상세 설계: [38-stabilization-pr-gate-design-plan.md](./38-stabilization-pr-gate-design-plan.md)

목표: 이후 AI 기능 PR이 기준선을 침범하지 않도록 사람이 읽는 변경 기준을 남긴다.

작업:

- 이 문서를 P1 안정화 source document로 사용한다.
- [22-current-implementation-status-map.md](./22-current-implementation-status-map.md)의 구현 상태와 충돌하면 이 문서를 갱신한다.
- PR template 또는 GitHub guideline에 P1 안정화 체크 항목을 추가한다.
- KDRIs validator, JWT/OIDC production-path test, 만성질환 우선순위 금지 표현 검토를 PR checklist에 포함한다.
- feature flag를 `true`로 바꾸는 PR은 sign-off 문서와 production guard test를 함께 요구한다.
- OCR/LLM/이미지 변경 PR은 raw image/raw OCR text 저장 금지 확인을 명시한다.

완료 조건:

- AI/YOLO/Ollama multimodal/pgvector PR은 이 문서의 gate를 통과해야 merge 가능
- feature flag true 변경은 별도 sign-off 문서와 테스트 없이는 금지
- KDRIs/nutrition_reference/config 변경은 승인 데이터 검증 없이는 merge 금지
- JWT/OIDC/security 변경은 production-path 테스트 없이는 merge 금지

## 이후 AI 기능 진입 조건

AI 기능 구현은 아래 조건이 모두 충족된 뒤 시작한다.

- P1 backend CI path pass
- P1 OpenAPI contract tests pass
- settings default-off tests pass
- production security validation tests pass
- raw image/raw OCR text 저장 금지 테스트 유지
- AI/vision/learning adapter는 flag off에서 import와 앱 boot를 깨지 않음

## 커밋 단위 제안

상세 설계: [39-commit-unit-splitting-design-plan.md](./39-commit-unit-splitting-design-plan.md)

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
