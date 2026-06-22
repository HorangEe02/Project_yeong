# 03. P1 Nutrition Backend CI Reproducibility Plan

> Status: implemented locally, pending GitHub Actions run
> Date: 2026-05-15
> Scope: Nutrition backend stabilization gates in root GitHub CI

## Purpose

The Nutrition backend already has high implementation density and strong local
test coverage. P1 should not add product scope first. It should make the same
backend stability gates reproducible in GitHub Actions from the repository root:

- PostgreSQL-backed Alembic smoke
- root `.github/workflows/17-lemon-backend-ci.yml` pass
- `pip-audit` dependency audit
- OpenAPI contract verification

This document is the detailed design and implementation plan for that work.

## Official References Checked

- GitHub Actions workflow files must live in repository root `.github/workflows`:
  <https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax>
- GitHub Actions PostgreSQL service containers and health checks:
  <https://docs.github.com/en/actions/tutorials/use-containerized-services/create-postgresql-service-containers>
- GitHub Actions Python dependency installation and caching:
  <https://docs.github.com/en/actions/tutorials/build-and-test-code/python>
- `actions/setup-python` v6 Python version and pip cache behavior:
  <https://github.com/actions/setup-python>
- Alembic `upgrade head` migration behavior:
  <https://alembic.sqlalchemy.org/en/latest/tutorial.html#running-our-first-migration>
- FastAPI `openapi_extra` and generated `/openapi.json` behavior:
  <https://fastapi.tiangolo.com/advanced/path-operation-advanced-configuration/#openapi-extra>
- `pip-audit` requirements-file audit behavior:
  <https://github.com/pypa/pip-audit>

## Current Local Facts

Repository root:

```text
/Users/yeong/99_me/00_github
```

Backend working directory:

```text
03_lemon_healthcare/yeong-Lemon-Aid/backend
```

Current root backend CI:

```text
.github/workflows/17-lemon-backend-ci.yml
```

Observed local checks:

| Check | Result |
| --- | --- |
| P1 OpenAPI contract tests | `10 passed` for `test_p1_api_contract.py` and `test_openapi_examples.py` |
| Generated OpenAPI smoke with CI-style `PYTHONPATH` | OpenAPI `3.1.0`, `24` paths, key P1 paths present |
| Live DB smoke without `TEST_DATABASE_URL` | skipped by design |
| Pre-implementation backend CI database env | `DATABASE_URL` existed, `TEST_DATABASE_URL` was not set |

## Implementation Update (2026-05-15)

- Root backend CI now uses `postgresql+asyncpg://postgres:postgres@localhost:5432/lemon_ci`.
- Root backend CI now exports `TEST_DATABASE_URL` so `test_db_session.py` runs instead of skipping in GitHub Actions.
- `actions/setup-python` pip cache now hashes both `requirements.txt` and `requirements-dev.txt`.
- OpenAPI contract tests now run as a dedicated fail-fast CI step before Alembic.
- Alembic still runs `upgrade head` and `current` against the PostgreSQL service container.
- Live PostgreSQL smoke now runs as a dedicated CI step after Alembic.
- Full backend pytest still runs after the smoke gates.

Verification run:

- Workflow YAML parse: pass
- `git diff --check`: pass
- `Settings(_env_file=None)` accepts the CI `postgresql+asyncpg` URL
- OpenAPI contract tests: `10 passed`
- KDRIs validator: `1795` rows validated
- Full backend pytest: `390 passed, 2 skipped`
- `pip-audit`: no known vulnerabilities found

Local note: live PostgreSQL smoke still requires a running PostgreSQL service.
This is expected to run in GitHub Actions through the workflow `postgres`
service container.

Pre-implementation gap:

- `Nutrition-backend/src/config.py` requires `postgresql+asyncpg://...` for
  `DATABASE_URL`.
- The P1 CI design must use `postgresql+asyncpg://postgres:postgres@localhost:5432/lemon_ci`.
- The live DB smoke test must receive `TEST_DATABASE_URL`; otherwise
  `Nutrition-backend/tests/integration/db/test_db_session.py` skips and GitHub
  CI does not actually prove PostgreSQL connectivity.

## Brainstorming

### Option A: Keep One Backend Job, Add Explicit Fail-Fast Gates

Keep one `backend-quality` job with a PostgreSQL service, but add explicit steps
for OpenAPI contract and live DB smoke before the full test suite.

Pros:

- Smallest change to the current P0 root CI.
- One required check remains easy to protect in branch rules.
- PostgreSQL service is created once and reused for Alembic plus DB smoke.
- Failures are easier to read because contract, migration, audit, and full
  pytest are separate steps.

Cons:

- One job still runs all backend gates on every backend CI trigger.
- Full test duration is not parallelized.

Decision: adopt for P1.

### Option B: Split Into Quality, Contract, And Database Jobs

Split the workflow into independent jobs such as `backend-quality`,
`openapi-contract`, and `postgres-smoke`.

Pros:

- Faster feedback if jobs run in parallel.
- Cleaner branch protection if each gate is independently required.

Cons:

- Dependency installation is repeated unless cache behavior is perfect.
- More required checks increase branch-protection administration.
- DB service setup is duplicated for database-specific jobs.

Decision: defer until P2 or until CI runtime becomes painful.

### Option C: Rely On Full Pytest Only

Keep the current full `pytest -q --no-cov` as the only contract and DB check.

Pros:

- Minimal CI YAML.
- Existing test suite already contains contract tests.

Cons:

- OpenAPI contract failures are buried late in the suite.
- `test_db_session.py` silently skips without `TEST_DATABASE_URL`.
- Alembic and DB connectivity are not obviously proven in the GitHub UI.

Decision: reject for P1.

### Option D: Add Local Helper Scripts For CI Smoke

Create scripts such as `scripts/ci_openapi_contract_smoke.py` and
`scripts/ci_settings_smoke.py`, then call scripts from CI.

Pros:

- Complex shell heredocs disappear from workflow YAML.
- Smoke logic can be unit tested.

Cons:

- Adds code surface before we know the smoke checks are stable.
- Current contract tests already exist and should be reused.

Decision: defer. P1 should first reuse existing pytest modules and Alembic CLI.

## Final Design

### 1. Trigger Policy

Keep root workflow execution at:

```yaml
on:
  pull_request:
    branches: [main, develop, yeong-tech]
  push:
    branches: [main, develop, yeong-tech]
  workflow_dispatch:
```

Reasoning:

- For a protected branch, path-filtered workflows can leave required checks
  pending or absent depending on what changed.
- P1 is a stabilization gate, so predictable branch protection matters more
  than saving a few minutes on docs-only changes.
- Docs and mobile CI can remain separate, but the backend required check should
  be consistently visible for team integration branches.

### 2. Environment Contract

Use the same async PostgreSQL driver required by `Settings` and the DB layer:

```yaml
env:
  PYTHONPATH: Nutrition-backend:food_image_analysis/src:ai_agent_chat/src
  DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/lemon_ci
  TEST_DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/lemon_ci
```

Why:

- `DATABASE_URL` drives Alembic through `alembic/env.py`.
- `TEST_DATABASE_URL` makes `test_db_session.py` run instead of skip.
- `PYTHONPATH` must include `Nutrition-backend` for direct OpenAPI import smoke.

### 3. Step Order

Recommended order inside `backend-quality`:

1. Checkout
2. Set up Python 3.13 with pip cache
3. Install `requirements.txt` and `requirements-dev.txt`
4. Black formatting check
5. Ruff lint
6. mypy strict type check
7. `pip-audit`
8. Config JSON validation
9. KDRIs dataset validation
10. OpenAPI contract smoke
11. Alembic PostgreSQL migration smoke
12. Live PostgreSQL session smoke
13. Full pytest

Why this order:

- Formatting, lint, and mypy fail fast without touching services.
- `pip-audit` should not be suppressed because dependency vulnerabilities are
  part of the release gate.
- KDRIs and config validation should fail before slower DB/test work.
- OpenAPI contract should fail before full pytest so API drift is visible.
- Alembic should upgrade the same live PostgreSQL database that the DB smoke
  test connects to.

### 4. OpenAPI Contract Gate

Use existing tests directly:

```bash
pytest \
  Nutrition-backend/tests/integration/api/test_p1_api_contract.py \
  Nutrition-backend/tests/integration/api/test_openapi_examples.py \
  -q --no-cov
```

This verifies:

- BearerAuth OpenAPI security scheme
- P1 endpoint path/method presence
- `x-contract-status`
- `x-required-scopes`
- `x-required-consents`
- protected endpoint security metadata
- OpenAPI examples without forbidden regulated wording

Optional extra smoke:

```bash
python - <<'PY'
from fastapi.testclient import TestClient
from src.main import create_app

client = TestClient(create_app())
schema = client.get("/openapi.json").json()
required_paths = {
    "/api/v1/supplements/analyze",
    "/api/v1/supplements/analyses/{analysis_id}/ocr-text",
    "/api/v1/health/sync",
    "/api/v1/dashboard/summary",
}
missing = required_paths - set(schema["paths"])
assert schema["openapi"].startswith("3."), schema["openapi"]
assert not missing, missing
PY
```

The pytest gate is mandatory. The inline smoke is optional because the pytest
modules already cover the same contract more completely.

### 5. PostgreSQL Alembic Smoke

Use GitHub's PostgreSQL service container with health checks and then run:

```bash
alembic upgrade head
alembic current
pytest Nutrition-backend/tests/integration/db/test_db_session.py -q --no-cov
```

Minimum acceptance:

- `alembic upgrade head` reaches the latest revision against live PostgreSQL.
- `alembic current` reports the current revision without connection errors.
- `test_db_session.py` is executed, not skipped.

Implementation note:

- If CI needs a separate clean DB for pytest later, use two databases:
  `lemon_ci_migrations` for Alembic and `lemon_ci_tests` for tests. For P1, one
  `lemon_ci` database is acceptable because the current DB smoke only checks
  connectivity with `SELECT 1`.

### 6. Dependency Audit Gate

Keep:

```bash
python -m pip_audit -r requirements.txt
```

Do not append `|| true`.

Reasoning:

- The official `pip-audit` behavior intentionally exposes non-zero exit codes.
- P1 wants GitHub CI to catch dependency risk, not produce a soft warning.
- Audit only `requirements.txt` in P1 because optional `vision`, `learning`, and
  local OCR extras are gated and not part of default runtime install.

### 7. Full Test Gate

Keep the full suite after smoke gates:

```bash
pytest -q --no-cov
```

Reasoning:

- P1 is about CI reproducibility, not coverage-threshold tuning.
- The current local fast gate passed with `390 passed, 2 skipped`.
- Coverage gate can remain in normal local commands or be reintroduced later as
  a separate P2 quality threshold if CI runtime stays reasonable.

## Detailed Implementation Plan

### P1-S0: Baseline Confirmation

Status: done locally for planning.

Evidence:

- OpenAPI contract tests: `10 passed`
- Generated OpenAPI smoke: `3.1.0`, `24` paths, core P1 paths present
- DB smoke without `TEST_DATABASE_URL`: skipped, confirming the CI gap

### P1-S1: Fix CI Database URLs

Status: implemented locally.

Target file:

- `.github/workflows/17-lemon-backend-ci.yml`

Change:

- Replace `DATABASE_URL` with `postgresql+asyncpg://postgres:postgres@localhost:5432/lemon_ci`.
- Add `TEST_DATABASE_URL` with the same URL.

Acceptance:

- `Settings` validation accepts the URL.
- Alembic uses the same URL through `get_settings().database_url`.
- DB integration smoke no longer skips in GitHub CI.

### P1-S2: Add Explicit OpenAPI Contract Step

Status: implemented locally.

Target file:

- `.github/workflows/17-lemon-backend-ci.yml`

Add step before Alembic:

```yaml
- name: Run OpenAPI contract smoke
  run: |
    pytest \
      Nutrition-backend/tests/integration/api/test_p1_api_contract.py \
      Nutrition-backend/tests/integration/api/test_openapi_examples.py \
      -q --no-cov
```

Acceptance:

- The GitHub UI shows OpenAPI contract as a separate failing/passing step.
- Full pytest still runs afterward.

### P1-S3: Add Explicit Live DB Smoke Step

Status: implemented locally.

Target file:

- `.github/workflows/17-lemon-backend-ci.yml`

Add step after Alembic:

```yaml
- name: Run live PostgreSQL smoke
  run: |
    pytest Nutrition-backend/tests/integration/db/test_db_session.py -q --no-cov
```

Acceptance:

- The test is not skipped in CI.
- PostgreSQL connectivity is proven through SQLAlchemy async engine.

### P1-S4: Keep `pip-audit` As A Hard Gate

Status: implemented locally.

Target file:

- `.github/workflows/17-lemon-backend-ci.yml`

Keep:

```yaml
- name: Audit Python dependencies
  run: |
    python -m pip_audit -r requirements.txt
```

Acceptance:

- Dependency vulnerabilities fail CI.
- No `continue-on-error` and no shell suppression are added.

### P1-S5: Update Integration Operations Doc

Status: implemented locally.

Target file:

- `docs/Integration-docs/01-ci-pr-integration-operations.md`

Add the CI-equivalent commands:

```bash
PYTHONPATH=Nutrition-backend:food_image_analysis/src:ai_agent_chat/src \
  .venv/bin/python -m pytest \
  Nutrition-backend/tests/integration/api/test_p1_api_contract.py \
  Nutrition-backend/tests/integration/api/test_openapi_examples.py \
  -q --no-cov

TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/lemon_ci \
  .venv/bin/python -m pytest \
  Nutrition-backend/tests/integration/db/test_db_session.py \
  -q --no-cov
```

Acceptance:

- Team members can reproduce the GitHub gates locally when PostgreSQL is running.

### P1-S6: Verify The Implementation

Run from repository root:

```bash
ruby -e 'require "yaml"; ARGV.each { |f| YAML.load_file(f); puts "ok #{f}" }' \
  .github/workflows/17-lemon-backend-ci.yml

git diff --check -- .github 03_lemon_healthcare/yeong-Lemon-Aid/docs
```

Run from backend directory:

```bash
PYTHONPATH=Nutrition-backend:food_image_analysis/src:ai_agent_chat/src \
  ./.venv/bin/python -m pytest \
  Nutrition-backend/tests/integration/api/test_p1_api_contract.py \
  Nutrition-backend/tests/integration/api/test_openapi_examples.py \
  -q --no-cov

./.venv/bin/python scripts/validate_kdris_dataset.py --require-approved
./.venv/bin/python -m pip_audit -r requirements.txt
./.venv/bin/python -m pytest -q --no-cov
```

Live PostgreSQL smoke requires a running PostgreSQL instance:

```bash
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/lemon_ci \
TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/lemon_ci \
PYTHONPATH=Nutrition-backend:food_image_analysis/src:ai_agent_chat/src \
  alembic upgrade head

TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/lemon_ci \
  ./.venv/bin/python -m pytest \
  Nutrition-backend/tests/integration/db/test_db_session.py \
  -q --no-cov
```

## Acceptance Criteria

- Root backend CI uses `postgresql+asyncpg` for both `DATABASE_URL` and
  `TEST_DATABASE_URL`.
- `pip-audit` is a hard CI gate.
- OpenAPI P1 contract tests are a dedicated CI step.
- Alembic `upgrade head` and `current` run against GitHub PostgreSQL service.
- Live DB smoke test runs instead of skipping in CI.
- Full backend pytest remains green after the smoke gates.
- No root workflow references `yeong-Vision-Nutrition`.

## Risks And Mitigations

| Risk | Mitigation |
| --- | --- |
| GitHub service container starts slowly | Keep `pg_isready` health check and retry settings. |
| Alembic and DB smoke share one database | Accept in P1 because current smoke only does `SELECT 1`; split DBs if tests begin mutating data. |
| `pip-audit` network instability | Keep as hard gate for protected branches; if instability is frequent, move to scheduled security workflow only after team approval. |
| OpenAPI contract test duplicates full pytest | Intentional fail-fast gate; full pytest remains the final regression net. |
| Branch protection expects old check names | Update required status checks to `Backend quality and integration` after CI lands. |

## Commit Plan

Suggested commit:

```text
ci(nutrition): reproduce backend stability gates in root CI

Why:
The Nutrition backend is locally stable, but P1 requires GitHub CI to prove the
same PostgreSQL, Alembic, dependency-audit, and OpenAPI contract gates before
team integration branches are protected.

What:
- use async PostgreSQL URLs for CI database settings
- expose OpenAPI contract and live DB smoke as dedicated CI steps
- keep pip-audit as a hard dependency security gate
- document the local reproduction commands for backend handoff
```
