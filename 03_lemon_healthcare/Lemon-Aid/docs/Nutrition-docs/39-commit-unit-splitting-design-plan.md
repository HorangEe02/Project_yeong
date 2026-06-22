# 39. 커밋 단위 정리 상세 설계 및 구현 플랜

> 작성일: 2026-05-15
> 상태: 구현 전 상세 설계
> 대상: P1 stabilization 변경 묶음, KDRIs 2025 데이터, JWT/OIDC, 만성질환 우선순위, 문서/CI/PR gate

---

## 1. 목표

현재 worktree에는 config, KDRIs 데이터, JWT/OIDC 보안, 만성질환 우선순위, P1 상태 문서, CI/PR gate 변경이 함께 쌓여 있다. 이 변경을 하나의 커밋으로 묶으면 리뷰어가 원인과 영향을 분리하기 어렵고, 특정 변경만 revert하거나 cherry-pick하기도 어렵다.

이번 설계의 목표는 변경을 의미 단위로 나누어 다음 세 가지를 보장하는 것이다.

1. 각 커밋 제목이 Conventional Commits 형식을 따른다.
2. 각 커밋은 하나의 이유와 검증 기준을 가진다.
3. 각 커밋은 가능한 한 path 기반으로 stage할 수 있게 구성한다.

---

## 2. 현재 변경량 요약

현재 변경은 크게 여섯 범주로 나뉜다.

| 범주 | 대표 변경 |
| --- | --- |
| config/default-off | `backend/src/config.py`, `.env.example`, `config/implementation-readiness.settings.json`, `tests/unit/test_config.py` |
| KDRIs 2025 데이터 | `data/nutrition_reference/kdris/kdris_2025.csv`, source manifest, review artifacts, KDRIs validator/scripts/tests |
| JWT/OIDC 보안 | `backend/src/security/auth.py`, `backend/src/security/oidc.py`, JWT/OIDC tests |
| 만성질환 우선순위 | `backend/src/nutrition/chronic_priority.py`, `data/nutrition_reference/nutrient/chronic_nutrient_priorities.json`, nutrition schema/analysis tests |
| 상태/계획 문서 | `docs/22`, `docs/23`, `docs/31`~`docs/39`, `docs/Nutrition-docs/dev-guides/*`, PR template |
| CI gate | root `.github/workflows/17-lemon-backend-ci.yml`, project-local `ci-backend.yml` |

커밋 대상에서 제외해야 하는 항목도 있다.

- `00_plusultra/**`: 이번 Lemon Healthcare P1 stabilization 범위가 아니다.
- `03_lemon_healthcare/yeong-Lemon-Aid/assets/mascot/**`: 브랜드 asset 작업으로 보이며 P1 backend stabilization 범위가 아니다.
- `03_lemon_healthcare/yeong-Lemon-Aid/outputs/generated/**`: 발표/수동 산출물로 보이며 이번 6개 커밋에 섞지 않는다.
- `03_lemon_healthcare/yeong-Lemon-Aid/records/meetings/**`: 회의자료/문서 원본으로 보이며 별도 문서 관리 커밋이 필요하다.

---

## 3. 브레인스토밍 결과

### 선택지 A: 하나의 stabilization 커밋

장점:

- staging이 단순하다.
- 전체 변경을 한 번에 push할 수 있다.

단점:

- 데이터 변경, 보안 변경, 문서 변경, CI 변경이 한 diff에 섞인다.
- 리뷰어가 어떤 테스트가 어떤 변경을 검증하는지 파악하기 어렵다.
- 문제가 생기면 일부만 되돌리기 어렵다.

판단:

- 현재 변경량에는 부적합하다.

### 선택지 B: 권장 6개 커밋으로 분리

장점:

- 사용자가 제시한 의미 단위와 일치한다.
- 리뷰와 revert가 쉽다.
- 각 커밋마다 검증 명령을 붙일 수 있다.

단점:

- `docs/23`, `tests/unit/nutrition/test_kdris_analysis.py`, `backend/src/config.py`처럼 여러 주제가 섞인 파일은 hunk 단위 staging이 필요할 수 있다.
- path 기반 staging만으로는 완전히 깨끗한 분리가 어려울 수 있다.

판단:

- 이번 작업의 기본 전략으로 채택한다.

### 선택지 C: 6개 커밋 + PR gate 전용 7번째 커밋

장점:

- root PR template, project-local PR template, `docs/38` 변경을 더 명확히 분리할 수 있다.

단점:

- 사용자가 제시한 6개 권장 커밋 구조에서 벗어난다.
- P1 상태 문서와 PR gate 문서를 따로 리뷰해야 한다.

판단:

- 엄격하게 분리하려면 가능하지만, 이번 계획에서는 `docs(status)` 커밋 안에 PR gate 문서와 template 변경을 포함한다.

---

## 4. 최종 커밋 순서

### 1. `fix(config): default non-P1 regulated flags to disabled`

이유:

- 아직 검증되지 않은 기능이 production에서 실수로 켜지지 않도록 하기 위함.

주요 파일:

- `03_lemon_healthcare/yeong-Lemon-Aid/backend/src/config.py`
- `03_lemon_healthcare/yeong-Lemon-Aid/backend/.env.example`
- `03_lemon_healthcare/yeong-Lemon-Aid/config/implementation-readiness.settings.json`
- `03_lemon_healthcare/yeong-Lemon-Aid/backend/tests/unit/test_config.py`
- `03_lemon_healthcare/yeong-Lemon-Aid/backend/tests/unit/llm/test_ollama_vision_assist.py`
- `03_lemon_healthcare/yeong-Lemon-Aid/backend/tests/unit/vision/test_yolo_detector.py`
- `03_lemon_healthcare/yeong-Lemon-Aid/docs/Nutrition-docs/dev-guides/00-setup-environment.md`

검증:

```bash
cd 03_lemon_healthcare/yeong-Lemon-Aid/backend
.venv/bin/python -m pytest tests/unit/test_config.py tests/unit/llm/test_ollama_vision_assist.py tests/unit/vision/test_yolo_detector.py -q --no-cov
```

커밋 본문에 들어갈 Why:

```text
Non-P1 regulated and AI/vision/learning features must stay disabled by default so unreviewed flows cannot be enabled accidentally in production.
```

### 2. `data(kdris): import reviewed 2025 KDRIs reference rows`

이유:

- 영양 분석 기준을 샘플 데이터에서 승인된 2025 데이터로 바꾸기 위함.

주요 파일:

- `03_lemon_healthcare/yeong-Lemon-Aid/data/nutrition_reference/kdris/kdris_2025.csv`
- `03_lemon_healthcare/yeong-Lemon-Aid/data/nutrition_reference/kdris/kdris_dataset_schema.md`
- `03_lemon_healthcare/yeong-Lemon-Aid/data/nutrition_reference/kdris/kdris_source_manifest.json`
- `03_lemon_healthcare/yeong-Lemon-Aid/data/nutrition_reference/kdris/review/2025/**`
- `03_lemon_healthcare/yeong-Lemon-Aid/data/nutrition_reference/kdris/raw/2025/README.md`
- `03_lemon_healthcare/yeong-Lemon-Aid/data/nutrition_reference/kdris/raw/2025/kns_2025_kdri_books_summaries_errata_f4/**`
- `03_lemon_healthcare/yeong-Lemon-Aid/backend/scripts/__init__.py`
- `03_lemon_healthcare/yeong-Lemon-Aid/backend/scripts/digitize_kdris_2025_summary.py`
- `03_lemon_healthcare/yeong-Lemon-Aid/backend/scripts/prepare_kdris_2025_digitization.py`
- `03_lemon_healthcare/yeong-Lemon-Aid/backend/scripts/validate_kdris_candidate_rows.py`
- `03_lemon_healthcare/yeong-Lemon-Aid/backend/scripts/validate_kdris_dataset.py`
- `03_lemon_healthcare/yeong-Lemon-Aid/backend/src/nutrition/kdris.py`
- `03_lemon_healthcare/yeong-Lemon-Aid/backend/src/nutrition/source_manifest.py`
- `03_lemon_healthcare/yeong-Lemon-Aid/backend/src/nutrition/unit_converter.py`
- `03_lemon_healthcare/yeong-Lemon-Aid/backend/tests/unit/scripts/**`
- `03_lemon_healthcare/yeong-Lemon-Aid/backend/tests/unit/nutrition/test_kdris_2025_dataset.py`
- `03_lemon_healthcare/yeong-Lemon-Aid/backend/tests/unit/nutrition/test_kdris_source_manifest.py`

주의:

- `data/nutrition_reference/kdris/raw/**`의 PDF 원본은 크기와 라이선스를 확인한 뒤 stage한다.
- 원본 PDF를 Git에 넣지 않기로 결정하면 이 커밋에는 `review/2025`의 source metadata와 text artifact만 포함하고 PDF는 외부 보관 위치를 문서화한다.

검증:

```bash
cd 03_lemon_healthcare/yeong-Lemon-Aid/backend
.venv/bin/python scripts/validate_kdris_dataset.py --require-approved
.venv/bin/python -m pytest tests/unit/scripts tests/unit/nutrition/test_kdris_2025_dataset.py tests/unit/nutrition/test_kdris_source_manifest.py -q --no-cov
```

커밋 본문에 들어갈 Why:

```text
The nutrition analysis baseline must use reviewed 2025 KDRIs rows instead of sample data, with source metadata and validator coverage kept together for traceability.
```

### 3. `fix(security): harden JWT JWKS verification path`

이유:

- 운영 로그인 토큰 검증에서 잘못된 토큰을 더 안전하게 거부하기 위함.

주요 파일:

- `03_lemon_healthcare/yeong-Lemon-Aid/backend/src/security/auth.py`
- `03_lemon_healthcare/yeong-Lemon-Aid/backend/src/security/oidc.py`
- `03_lemon_healthcare/yeong-Lemon-Aid/backend/scripts/check_oidc_discovery.py`
- `03_lemon_healthcare/yeong-Lemon-Aid/backend/tests/unit/security/test_auth.py`
- `03_lemon_healthcare/yeong-Lemon-Aid/backend/tests/unit/security/test_oidc.py`
- `03_lemon_healthcare/yeong-Lemon-Aid/backend/tests/integration/security/test_jwt_production_path.py`

검증:

```bash
cd 03_lemon_healthcare/yeong-Lemon-Aid/backend
.venv/bin/python -m pytest tests/unit/security tests/integration/security/test_jwt_production_path.py -q --no-cov
```

커밋 본문에 들어갈 Why:

```text
Production JWT verification must reject malformed, incorrectly scoped, or mismatched JWKS/OIDC tokens before protected healthcare API paths can trust user identity.
```

### 4. `feat(nutrition): apply chronic-condition nutrient priority lookup`

이유:

- 만성질환 정보가 있을 때 확인 우선순위를 더 잘 보여주기 위함.

주요 파일:

- `03_lemon_healthcare/yeong-Lemon-Aid/data/nutrition_reference/nutrient/chronic_nutrient_priorities.json`
- `03_lemon_healthcare/yeong-Lemon-Aid/backend/src/nutrition/chronic_priority.py`
- `03_lemon_healthcare/yeong-Lemon-Aid/backend/src/nutrition/deficiency_analysis.py`
- `03_lemon_healthcare/yeong-Lemon-Aid/backend/src/models/schemas/nutrition.py`
- `03_lemon_healthcare/yeong-Lemon-Aid/backend/tests/unit/nutrition/test_chronic_priority.py`
- `03_lemon_healthcare/yeong-Lemon-Aid/backend/tests/unit/nutrition/test_kdris_analysis.py`
- `03_lemon_healthcare/yeong-Lemon-Aid/backend/tests/integration/api/test_phase1_api.py`

검증:

```bash
cd 03_lemon_healthcare/yeong-Lemon-Aid/backend
.venv/bin/python -m pytest tests/unit/nutrition/test_chronic_priority.py tests/unit/nutrition/test_kdris_analysis.py tests/integration/api/test_phase1_api.py -q --no-cov
```

커밋 본문에 들어갈 Why:

```text
Chronic-condition context should affect review priority without turning nutrient analysis into diagnosis, treatment, or dosage guidance.
```

### 5. `docs(status): refresh P1 stabilization map`

이유:

- 팀이 현재 구현 상태와 남은 범위를 같은 기준으로 보게 하기 위함.

주요 파일:

- `.github/PULL_REQUEST_TEMPLATE.md`
- `03_lemon_healthcare/.github/PULL_REQUEST_TEMPLATE.md`
- `03_lemon_healthcare/yeong-Lemon-Aid/docs/Nutrition-docs/22-current-implementation-status-map.md`
- `03_lemon_healthcare/yeong-Lemon-Aid/docs/Nutrition-docs/23-p1-stabilization-plan.md`
- `03_lemon_healthcare/yeong-Lemon-Aid/docs/Nutrition-docs/31-backend-feature-specifications.md`
- `03_lemon_healthcare/yeong-Lemon-Aid/docs/Nutrition-docs/32-paddleocr-local-fallback-plan.md`
- `03_lemon_healthcare/yeong-Lemon-Aid/docs/Nutrition-docs/33-three-tier-ocr-pipeline-implementation-guide.md`
- `03_lemon_healthcare/yeong-Lemon-Aid/docs/Nutrition-docs/34-llm-serving-engines-multi-environment-setup-guide.md`
- `03_lemon_healthcare/yeong-Lemon-Aid/docs/Nutrition-docs/35-google-vision-ocr-provider-implementation-plan.md`
- `03_lemon_healthcare/yeong-Lemon-Aid/docs/Nutrition-docs/36-post-p1-execution-plan.md`
- `03_lemon_healthcare/yeong-Lemon-Aid/docs/Nutrition-docs/38-stabilization-pr-gate-design-plan.md`
- `03_lemon_healthcare/yeong-Lemon-Aid/docs/Nutrition-docs/39-commit-unit-splitting-design-plan.md`
- `03_lemon_healthcare/yeong-Lemon-Aid/docs/Nutrition-docs/dev-guides/07-ocr-pipeline.md`
- `03_lemon_healthcare/yeong-Lemon-Aid/docs/Nutrition-docs/dev-guides/29-final-deliverables-index.md`
- `03_lemon_healthcare/yeong-Lemon-Aid/docs/Nutrition-docs/dev-guides/30-post-p1-execution-checklist.md`
- `03_lemon_healthcare/yeong-Lemon-Aid/01_HANDOFF.md`
- `03_lemon_healthcare/yeong-Lemon-Aid/HANDOFF.md`

검증:

```bash
git diff --check
rg -n "[[:blank:]]$" .github/PULL_REQUEST_TEMPLATE.md 03_lemon_healthcare/.github/PULL_REQUEST_TEMPLATE.md 03_lemon_healthcare/yeong-Lemon-Aid/docs 03_lemon_healthcare/yeong-Lemon-Aid/*.md
```

커밋 본문에 들어갈 Why:

```text
The team needs a shared current-state map for what is complete, what remains gated, and which PR checks protect the P1 baseline.
```

### 6. `ci(backend): add data and settings stabilization gates`

이유:

- 로컬 검증 기준을 GitHub Actions에서도 반복 가능하게 만들기 위함.

주요 파일:

- `.github/workflows/17-lemon-backend-ci.yml`
- `03_lemon_healthcare/.github/workflows/ci-backend.yml`
- `03_lemon_healthcare/yeong-Lemon-Aid/docs/Nutrition-docs/37-ci-hardening-design-plan.md`

검증:

```bash
ruby -e 'require "yaml"; YAML.load_file(".github/workflows/17-lemon-backend-ci.yml"); puts "yaml ok"'
cd 03_lemon_healthcare/yeong-Lemon-Aid/backend
.venv/bin/python -m json.tool ../config/implementation-readiness.settings.json > /tmp/implementation-readiness.settings.json
.venv/bin/python scripts/validate_kdris_dataset.py --require-approved
.venv/bin/python - <<'PY'
from src.config import Settings

s = Settings(_env_file=None)
assert not s.allow_external_llm
assert not s.enable_multimodal_llm
assert not s.enable_vision_classifier
assert not s.enable_image_learning_pipeline
assert not s.enable_pgvector_storage
assert not s.feature_prescription_ocr_intake
assert not s.feature_lab_result_ocr_intake
assert not s.feature_dosage_change_recommendation
assert not s.feature_medication_safety_alert
PY
```

커밋 본문에 들어갈 Why:

```text
Backend CI must run for data and settings changes so GitHub Actions enforces the same KDRIs and default-off gates as local validation.
```

---

## 5. Staging 전략

원칙:

1. path 기반 staging을 우선한다.
2. 같은 파일에 여러 주제가 섞였으면 커밋 의미가 더 큰 쪽에 넣는다.
3. 엄격한 분리가 필요한 파일만 hunk 단위 staging을 사용한다.
4. untracked 대형 산출물은 기본 제외한다.

권장 흐름:

```bash
git status --short
git diff --name-status
git add -- <commit-1-files>
git diff --cached --check
git commit -m "fix(config): default non-P1 regulated flags to disabled" -m "<why body>"
```

반복할 때마다 다음을 확인한다.

```bash
git status --short
git diff --cached --name-status
git diff --cached --check
```

주의:

- `git add .`는 사용하지 않는다.
- `00_plusultra/**`, `assets/mascot/**`, `outputs/generated/**`, `records/meetings/**`는 이번 6개 커밋에 포함하지 않는다.
- raw KDRIs PDF는 포함 전 라이선스와 파일 크기를 확인한다.

---

## 6. 전체 검증 순서

커밋을 모두 나눈 뒤 마지막에 실행한다.

```bash
cd 03_lemon_healthcare/yeong-Lemon-Aid/backend
.venv/bin/black --check src tests alembic
.venv/bin/ruff check src tests alembic
.venv/bin/mypy src tests --strict
.venv/bin/python scripts/validate_kdris_dataset.py --require-approved
.venv/bin/python -m pytest --cov-report=term-missing
```

repo root:

```bash
git diff --check
ruby -e 'require "yaml"; YAML.load_file(".github/workflows/17-lemon-backend-ci.yml"); puts "yaml ok"'
```

---

## 7. 공식 문서 근거

- Conventional Commits 1.0.0: https://www.conventionalcommits.org/en/v1.0.0/
- Git `add` documentation: https://git-scm.com/docs/git-add
