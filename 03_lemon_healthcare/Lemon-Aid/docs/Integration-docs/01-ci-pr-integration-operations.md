# 01. CI, PR, And Integration Operations

> Status: integration operations guide
> Primary collaboration rules: [../05-github-guidelines.md](../05-github-guidelines.md)

## Purpose

This document defines how Nutrition, Food, Chat, and Integration work should be combined without breaking shared CI or hiding ownership boundaries.

## Ownership Model

| Area | Primary Paths | Integration Responsibility |
|------|---------------|----------------------------|
| Nutrition | `backend/Nutrition-backend/`, `docs/Nutrition-docs/`, `data/supplement_images/`, `data/nutrition_reference/` | keep nutrition APIs, OCR/text parsing, and tests green |
| Food | `backend/food_image_analysis/`, `docs/Food-docs/`, `data/food_images/` | keep food classification and taxonomy contracts isolated |
| Chat | `backend/ai_agent_chat/`, `docs/Chat-docs/` | keep chat behavior aligned with compliance and product wording |
| Integration | repository root `.github/`, `docs/`, root README/handoff/output reports | keep CI, PR templates, release notes, and demo flows consistent |

## Required PR Checks

Backend changes should pass, from `yeong-Lemon-Aid/backend`:

```bash
.venv/bin/python -m black --check Nutrition-backend/src Nutrition-backend/tests food_image_analysis ai_agent_chat alembic scripts
.venv/bin/python -m ruff check Nutrition-backend/src Nutrition-backend/tests food_image_analysis ai_agent_chat alembic scripts
.venv/bin/python -m mypy Nutrition-backend/src Nutrition-backend/tests food_image_analysis/src food_image_analysis/tests ai_agent_chat/src ai_agent_chat/tests --strict
.venv/bin/python -m pip_audit -r requirements.txt
.venv/bin/python scripts/validate_kdris_dataset.py --require-approved
.venv/bin/python -m pytest Nutrition-backend/tests/integration/api/test_p1_api_contract.py Nutrition-backend/tests/integration/api/test_openapi_examples.py -q --no-cov
.venv/bin/python -m pytest -q --no-cov
```

Live PostgreSQL checks require a running PostgreSQL database and the same
async SQLAlchemy URL used by CI:

```bash
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/lemon_ci \
TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/lemon_ci \
PYTHONPATH=Nutrition-backend:food_image_analysis/src:ai_agent_chat/src \
  alembic upgrade head

DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/lemon_ci \
TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/lemon_ci \
PYTHONPATH=Nutrition-backend:food_image_analysis/src:ai_agent_chat/src \
  .venv/bin/python -m pytest Nutrition-backend/tests/integration/db/test_db_session.py -q --no-cov
```

Docs changes should pass:

```bash
git diff --check -- .github 03_lemon_healthcare/yeong-Lemon-Aid/docs
```

## Integration Checklist

- Update common docs only when a rule applies to more than one part.
- Keep part-specific design details inside `Nutrition-docs/`, `Food-docs/`, or `Chat-docs/`.
- Update `.github/CODEOWNERS` when ownership paths move.
- Update CI paths when runtime folders move.
- Run the smallest relevant test first, then the shared gate before handoff.
- Record unresolved cross-part assumptions in the PR body or handoff note.

## Release/Demo Checklist

- Confirm backend tests and data validators pass.
- Confirm mobile/demo flow uses the same API contract as backend tests.
- Confirm regulated or health-sensitive outputs use the wording in [../10-compliance-checklist.md](../10-compliance-checklist.md).
- Confirm the demo explains which features are implemented, planned, or gated.
