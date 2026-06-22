# 37. CI Hardening 상세 설계 및 구현 플랜

> 작성일: 2026-05-15
> 상태: 구현 전 상세 설계
> 대상: `.github/workflows/17-lemon-backend-ci.yml`, `backend/scripts/validate_kdris_dataset.py`, `backend/src/config.py`

---

## 1. 목표

로컬에서 통과한 backend 검증 기준이 GitHub Actions에서도 같은 기준으로 반복 실행되도록 보강한다. 특히 KDRIs 2025 데이터, reference 데이터, runtime config 변경이 backend 동작에 영향을 주는데도 CI가 실행되지 않는 상황을 막는다.

이번 CI hardening의 핵심은 네 가지다.

1. backend CI trigger가 backend 코드뿐 아니라 `data/nutrition_reference/kdris/**`, `data/nutrition_reference/nutrient/**`, `config/**` 변경도 감지한다.
2. CI에서 승인된 KDRIs 데이터만 통과하도록 `validate_kdris_dataset.py --require-approved`를 실행한다.
3. settings smoke에서 regulated flag와 AI/OCR/YOLO/학습 flag의 default-off 상태를 확인한다.
4. docs-only 변경은 docs CI로 분리하고, backend/data/config 변경은 backend CI로 검증한다.

---

## 2. 브레인스토밍 결과

### 선택지 A: backend CI path filter만 확장

장점:

- 구현이 가장 단순하다.
- GitHub Actions의 기본 `paths` 필터만 사용하므로 유지보수 부담이 작다.
- 현재 monorepo 구조와 잘 맞는다.

단점:

- docs-only 변경과 backend/data 변경이 섞인 PR에서는 backend CI도 실행된다.
- path filter 자체가 의도대로 작동하는지 별도 회귀 테스트는 GitHub Actions에서만 최종 확인된다.

판단:

- 이번 요구사항에는 가장 적합하다. docs-only 변경을 불필요하게 backend CI로 보내지 않으면서, backend/data/config 변경은 빠짐없이 잡을 수 있다.

### 선택지 B: backend CI를 항상 실행

장점:

- path filter 누락 위험이 없다.
- required check pending 문제를 줄일 수 있다.

단점:

- docs-only PR에서도 PostgreSQL, mypy, pytest가 모두 실행되어 시간이 늘어난다.
- 현재 사용자 요구의 "docs-only 변경과 backend/data 변경 path filter 재확인" 방향과 맞지 않는다.

판단:

- 비용 대비 이득이 낮다. 이번 설계에서는 채택하지 않는다.

### 선택지 C: dorny/paths-filter 같은 별도 action으로 job 내부 분기

장점:

- 하나의 workflow 안에서 docs/backend/data/config 변경 여부를 세밀하게 분기할 수 있다.

단점:

- 외부 action 의존성이 늘어난다.
- 현재 요구 범위보다 복잡하다.
- GitHub 기본 `paths` 필터로 해결 가능한 문제다.

판단:

- 향후 monorepo가 더 커지고 package별 job 분리가 필요할 때 재검토한다.

---

## 3. 최종 설계

### 3.1 Path filter 설계

현재 Git repository root는 `/Users/yeong/99_me/00_github`이고, Lemon Healthcare checkout은 그 아래 `03_lemon_healthcare` 디렉터리다. GitHub Actions `paths` 패턴은 repository root 기준으로 평가되므로 backend CI에는 다음 접두어를 포함해야 한다.

```yaml
on:
  push:
    paths:
      - '03_lemon_healthcare/yeong-Lemon-Aid/backend/**'
      - '03_lemon_healthcare/yeong-Lemon-Aid/data/nutrition_reference/kdris/**'
      - '03_lemon_healthcare/yeong-Lemon-Aid/data/nutrition_reference/nutrient/**'
      - '03_lemon_healthcare/yeong-Lemon-Aid/config/**'
      - '.github/workflows/17-lemon-backend-ci.yml'
  pull_request:
    paths:
      - '03_lemon_healthcare/yeong-Lemon-Aid/backend/**'
      - '03_lemon_healthcare/yeong-Lemon-Aid/data/nutrition_reference/kdris/**'
      - '03_lemon_healthcare/yeong-Lemon-Aid/data/nutrition_reference/nutrient/**'
      - '03_lemon_healthcare/yeong-Lemon-Aid/config/**'
      - '.github/workflows/17-lemon-backend-ci.yml'
```

설계 이유:

- `backend/**`: Python code, alembic, tests, scripts 변경 검증
- `data/nutrition_reference/kdris/**`: KDRIs 2025 CSV, manifest, review artifact 변경 검증
- `data/nutrition_reference/nutrient/**`: 만성질환 우선순위, nutrient reference 등 backend 분석 기준 변경 검증
- `config/**`: feature flag와 readiness manifest 변경 검증
- workflow 자체: CI 변경 시 CI가 자기 자신을 검증

주의:

- GitHub 공식 문서 기준으로 같은 event에서 `paths`와 `paths-ignore`를 동시에 사용할 수 없다. 이번 설계는 include-only `paths`만 사용한다.
- `branches`와 `paths`가 함께 있으면 두 조건이 모두 만족되어야 workflow가 실행된다. 따라서 대상 branch 목록은 현재 팀 브랜치 정책과 맞는지 별도 확인한다.

### 3.2 Backend CI step 순서

권장 순서:

1. Checkout
2. Python setup
3. Dependency install
4. Black
5. Ruff
6. mypy
7. Settings/OpenAPI smoke
8. KDRIs dataset gate
9. Alembic PostgreSQL smoke
10. Pytest with coverage
11. Coverage upload

설계 이유:

- Black/Ruff/mypy는 빠르게 실패해야 한다.
- settings/OpenAPI smoke는 앱 boot와 route contract를 빠르게 확인한다.
- KDRIs validator는 data/config 변경 PR에서 테스트 전체를 기다리지 않고 데이터 승인 상태를 먼저 확인한다.
- Alembic과 pytest는 그 다음에 실행한다.

### 3.3 KDRIs dataset gate

CI command:

```bash
python scripts/validate_kdris_dataset.py --require-approved
```

검증 의도:

- KDRIs CSV row가 schema와 단위 규칙을 만족하는지 확인한다.
- 승인되지 않은 review row가 production dataset으로 들어오는 것을 막는다.
- `KDRIS_DATA_VERSION=2025`, `ALLOW_SAMPLE_KDRIS=false` 전환 이후 sample data 회귀를 막는다.

실패 기준:

- 필수 column 누락
- unit/category 값 오류
- 승인되지 않은 row 포함
- manifest와 dataset 불일치

### 3.4 Settings smoke

CI에서 `.env` 영향을 받지 않는 기본값을 확인하기 위해 `Settings(_env_file=None)`을 사용한다.

권장 command:

```bash
python -m json.tool ../config/implementation-readiness.settings.json > /tmp/implementation-readiness.settings.json
python - <<'PY'
from src.config import Settings

settings = Settings(_env_file=None)
assert settings.database_url.startswith("postgresql+asyncpg://")
for flag_name in (
    "allow_external_llm",
    "enable_multimodal_llm",
    "enable_vision_classifier",
    "enable_image_learning_pipeline",
    "enable_pgvector_storage",
    "feature_prescription_ocr_intake",
    "feature_lab_result_ocr_intake",
    "feature_dosage_change_recommendation",
    "feature_medication_safety_alert",
):
    assert getattr(settings, flag_name) is False, flag_name
PY
```

검증 의도:

- 외부 LLM, multimodal, YOLO, image learning, pgvector가 기본 OFF인지 확인한다.
- 처방전 OCR intake, 검사표 OCR intake, 복용량 변경 추천, 복약 안전 알림이 기본 OFF인지 확인한다.
- readiness JSON이 JSON 문법을 만족하는지 확인한다.

추가 보강 후보:

- readiness JSON의 동일 flag default도 함께 읽어 `false`인지 검사하는 전용 script 추가
- production mode에서 sign-off 대상 flag가 `true`이면 `Settings` validation error가 나는지 별도 unit test 유지

### 3.5 OpenAPI smoke

권장 command:

```bash
python - <<'PY'
from src.main import create_app

schema = create_app().openapi()
required_paths = {
    "/api/v1/supplements/analyze",
    "/api/v1/supplements/analyses/{analysis_id}/ocr-text",
    "/api/v1/nutrition/kdris",
    "/api/v1/nutrition/analyze",
}
assert schema["openapi"].startswith("3.")
assert required_paths.issubset(schema["paths"]), required_paths - set(schema["paths"])
PY
```

검증 의도:

- 앱 import와 route registration이 CI에서 깨지지 않는지 확인한다.
- supplement OCR intake/parse preview와 nutrition/KDRIs 핵심 API route가 유지되는지 확인한다.

### 3.6 Docs-only와 backend/data/config 변경 분리

현재 하위 프로젝트에 있는 docs CI reference는 다음 경로를 본다. 단, GitHub Actions가 실제로 읽는 workflow는 repository root의 `.github/workflows/**`이므로 docs CI를 실제 required check로 쓰려면 root workflow로 승격해야 한다.

- `03_lemon_healthcare/PROJECT_GUIDE.md`
- `03_lemon_healthcare/yeong-Lemon-Aid/docs/**`
- `03_lemon_healthcare/yeong-Lemon-Aid/**/*.md`
- `03_lemon_healthcare/.github/workflows/ci-docs.yml`

backend CI는 다음 경로를 본다.

- `03_lemon_healthcare/yeong-Lemon-Aid/backend/**`
- `03_lemon_healthcare/yeong-Lemon-Aid/data/nutrition_reference/kdris/**`
- `03_lemon_healthcare/yeong-Lemon-Aid/data/nutrition_reference/nutrient/**`
- `03_lemon_healthcare/yeong-Lemon-Aid/config/**`
- `.github/workflows/17-lemon-backend-ci.yml`

예상 동작:

| 변경 내용 | Docs CI | Backend CI | 이유 |
| --- | --- | --- | --- |
| `docs/**`만 변경 | 실행 | 미실행 | 문서 검증만 필요 |
| `backend/src/**` 변경 | 미실행 | 실행 | backend 코드 검증 필요 |
| `data/nutrition_reference/kdris/**` 변경 | markdown이면 실행 가능 | 실행 | 데이터가 backend 분석 결과에 영향 |
| `data/nutrition_reference/nutrient/**` 변경 | markdown이면 실행 가능 | 실행 | reference가 backend 분석 결과에 영향 |
| `config/**` 변경 | 미실행 | 실행 | feature flag/readiness가 runtime에 영향 |
| docs + backend 혼합 변경 | 실행 | 실행 | 두 영역 모두 영향 |
| workflow 파일 변경 | 해당 workflow 실행 | 해당 workflow 실행 | CI 정의 자체 검증 |

---

## 4. 구현 플랜

### Step 1. 현재 workflow 상태 확인

확인 파일:

- `.github/workflows/17-lemon-backend-ci.yml`
- `03_lemon_healthcare/.github/workflows/ci-docs.yml` (project-local reference)

확인 항목:

- path filter가 repository root 기준 경로인지 확인
- `push`와 `pull_request`에 같은 path filter가 들어갔는지 확인
- `defaults.run.working-directory`가 `03_lemon_healthcare/yeong-Lemon-Aid/backend`인지 확인
- Python version과 local 개발 기준이 맞는지 확인

### Step 2. backend CI path filter 보강

변경 파일:

- `.github/workflows/17-lemon-backend-ci.yml`

추가 경로:

- `03_lemon_healthcare/yeong-Lemon-Aid/data/nutrition_reference/kdris/**`
- `03_lemon_healthcare/yeong-Lemon-Aid/data/nutrition_reference/nutrient/**`
- `03_lemon_healthcare/yeong-Lemon-Aid/config/**`

완료 기준:

- `push.paths`와 `pull_request.paths`가 동일하다.
- docs-only 경로는 backend CI path에 넣지 않는다.

### Step 3. settings/OpenAPI smoke 보강

변경 파일:

- `.github/workflows/17-lemon-backend-ci.yml`

작업:

- readiness JSON parse 추가
- `Settings(_env_file=None)` default-off assertion 추가
- supplement/nutrition 핵심 OpenAPI path assertion 추가

완료 기준:

- regulated flag가 기본 `true`로 바뀌면 CI가 실패한다.
- AI/OCR/YOLO/학습 flag가 기본 `true`로 바뀌면 CI가 실패한다.
- 핵심 route가 누락되면 CI가 실패한다.

### Step 4. KDRIs 승인 데이터 gate 추가

변경 파일:

- `.github/workflows/17-lemon-backend-ci.yml`

작업:

- `Validate KDRIs 2025 dataset` step 추가
- command는 `python scripts/validate_kdris_dataset.py --require-approved`

완료 기준:

- 승인되지 않은 KDRIs dataset 변경은 CI에서 실패한다.
- local command와 CI command가 동일하다.

### Step 5. docs CI와 backend CI 분리 재확인

변경 파일:

- 원칙적으로 없음
- 필요 시 root docs workflow를 별도 추가하거나 project-local docs CI reference 주석만 보정

확인 항목:

- docs CI가 docs와 Markdown 문서 변경을 담당한다.
- backend CI가 backend/data/config 변경을 담당한다.
- `.github/workflows/17-lemon-backend-ci.yml` 변경은 backend CI를 실행한다.
- 현재 project-local `03_lemon_healthcare/.github/workflows/ci-docs.yml` 변경은 GitHub Actions root workflow가 아니므로 자동 실행 대상으로 보지 않는다.

### Step 6. 로컬 검증

backend 디렉터리에서 실행:

```bash
python -m json.tool ../config/implementation-readiness.settings.json > /tmp/implementation-readiness.settings.json
python scripts/validate_kdris_dataset.py --require-approved
python -c "from src.config import Settings; s=Settings(_env_file=None); assert not s.allow_external_llm and not s.enable_multimodal_llm and not s.enable_vision_classifier and not s.enable_image_learning_pipeline and not s.enable_pgvector_storage and not s.feature_prescription_ocr_intake and not s.feature_lab_result_ocr_intake and not s.feature_dosage_change_recommendation and not s.feature_medication_safety_alert"
python -c "from src.main import create_app; schema=create_app().openapi(); assert '/api/v1/supplements/analyze' in schema['paths']; assert '/api/v1/supplements/analyses/{analysis_id}/ocr-text' in schema['paths']; assert '/api/v1/nutrition/kdris' in schema['paths']; assert '/api/v1/nutrition/analyze' in schema['paths']"
```

repo root에서 실행:

```bash
git diff --check
```

YAML parse 확인:

```bash
ruby -e 'require "yaml"; YAML.load_file(".github/workflows/17-lemon-backend-ci.yml"); puts "yaml ok"'
```

---

## 5. 위험 요소와 대응

| 위험 | 원인 | 대응 |
| --- | --- | --- |
| backend CI가 docs-only PR에서 pending으로 남음 | required check와 path filter 조합 | branch protection에서 docs-only PR에 required check 정책이 어떻게 적용되는지 GitHub에서 확인 |
| path filter가 실행되지 않음 | monorepo 접두어 누락 | `03_lemon_healthcare/...` 접두어를 유지 |
| local `.env` 때문에 CI smoke와 로컬 smoke 결과가 다름 | `Settings()`가 `.env`를 읽음 | CI smoke는 `Settings(_env_file=None)` 사용 |
| KDRIs data 변경이 테스트를 통과하지만 승인 상태를 놓침 | 일반 pytest만 실행 | `--require-approved` validator를 별도 step으로 고정 |
| config JSON은 parse되지만 Settings와 값이 불일치 | JSON parse만 확인 | 후속으로 readiness JSON default comparison script 추가 고려 |

---

## 6. PR 체크리스트

- [ ] `push.paths`와 `pull_request.paths`에 backend/data/config 경로가 모두 있다.
- [ ] docs-only 경로가 backend CI path에 포함되지 않았다.
- [ ] `validate_kdris_dataset.py --require-approved`가 backend CI에 있다.
- [ ] settings smoke가 regulated flag default-off를 확인한다.
- [ ] settings smoke가 AI/OCR/YOLO/학습 flag default-off를 확인한다.
- [ ] OpenAPI smoke가 supplement/nutrition 핵심 path를 확인한다.
- [ ] 로컬에서 validator와 smoke command가 통과했다.
- [ ] `git diff --check`가 통과했다.

---

## 7. 공식 문서 근거

- GitHub Actions workflow syntax: https://docs.github.com/actions/reference/workflows-and-actions/workflow-syntax
- GitHub Actions triggering workflows: https://docs.github.com/en/actions/how-tos/writing-workflows/choosing-when-your-workflow-runs/triggering-a-workflow
