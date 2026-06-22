# 06. Tech Stack

> Status: team-wide summary
> Last updated: 2026-05-21 (develop CI gates · pre-commit/commit-msg hook 반영)
> Detailed source: [Nutrition-docs/06-tech-stack.md](./Nutrition-docs/06-tech-stack.md)

## Common Architecture

```text
mobile/
  flutter_app/ or Xcode/iOS-specific implementation

backend/
  Nutrition-backend/
  food_image_analysis/
  ai_agent_chat/
  scripts/
  alembic/

data/
  nutrition_reference/
  supplement_images/
  food_images/

docs/
  common summary docs
  team-collaboration/        ← develop 통합 협업 규칙 (브랜치/커밋/PR/CI)
  Nutrition-docs/
  Food-docs/
  Chat-docs/
  Integration-docs/
```

## Shared Stack Principles

- Backend feature areas use Python/FastAPI-compatible module layouts with their own `src/` and `tests/`.
- Mobile work may use Flutter and Xcode/iOS-specific assets, but product behavior must remain aligned with backend contracts.
- OCR, LLM, vision, and external APIs must be adapter-driven and gated by settings, consent, and environment policy.
- Local/private processing is preferred for identifiable or sensitive health data.
- CI must validate formatting, lint, type checks, tests, and data gates before integration on `develop` (Squash Merge) and before release on `main`.
- Every commit passes through `pre-commit`, `commit-msg` (Conventional Commits), and `pre-push` hooks locally — bypassing via `--no-verify` is forbidden.

## Current Backend Execution Surface

| Area | Runtime Path | Test Path |
|------|--------------|-----------|
| Nutrition | `backend/Nutrition-backend/src` | `backend/Nutrition-backend/tests` |
| Food | `backend/food_image_analysis/src` | `backend/food_image_analysis/tests` |
| Chat | `backend/ai_agent_chat/src` | `backend/ai_agent_chat/tests` |
| Shared DB/scripts | `backend/alembic`, `backend/scripts` | covered by backend CI |

## Required Local Checks

Run from `yeong-Lemon-Aid/backend` before pushing to any branch that will be PR'd to `develop`:

```bash
# 0) pre-commit hooks (한 번만 설치)
pre-commit install --hook-type pre-commit --hook-type commit-msg --hook-type pre-push

# 1) 포매팅
.venv/bin/python -m black --check Nutrition-backend/src Nutrition-backend/tests food_image_analysis/src food_image_analysis/tests ai_agent_chat/src ai_agent_chat/tests alembic scripts

# 2) 린트
.venv/bin/python -m ruff check Nutrition-backend/src Nutrition-backend/tests food_image_analysis/src food_image_analysis/tests ai_agent_chat/src ai_agent_chat/tests alembic scripts

# 3) 타입 체크
.venv/bin/python -m mypy --explicit-package-bases Nutrition-backend/src Nutrition-backend/tests food_image_analysis/src food_image_analysis/tests ai_agent_chat/src ai_agent_chat/tests --strict

# 4) 테스트
.venv/bin/python -m pytest -q --no-cov

# 5) (선택) 모든 hook을 한꺼번에
pre-commit run --all-files
```

Mobile checks (from `yeong-Lemon-Aid/mobile/flutter_app`):

```bash
flutter pub get
flutter format --output=none --set-exit-if-changed lib test
flutter analyze
flutter test
```

## CI Gates (GitHub Actions)

`develop`/`main` PR이 통과해야 하는 status checks:

| Check | 무엇을 검증 | 실패 시 우회 |
|-------|------------|-------------|
| `Backend quality and integration` | black/ruff/mypy/pytest/pip-audit/Alembic 다운–업 시나리오 | 불가 (작성자 책임) |
| `Flutter quality` | dart format/flutter analyze/flutter test/debug build | 불가 |
| `Documentation quality` | markdownlint, 깨진 링크, trailing whitespace | 불가 |
| `Secrets / large files` | gitleaks, `check-added-large-files` (2MB) | 불가 — 누출 시 즉시 키 회전 |

세부 워크플로 정의는 `.github/workflows/17-lemon-*.yml` 그리고 [`team-collaboration/CI_CD_GATES.md`](./team-collaboration/CI_CD_GATES.md).

## Develop Branch — Stack 책임

- Backend, Mobile, Data, Docs PR이 모두 같은 `develop` 위에서 통합됩니다.
- 영역 경계(예: backend ↔ mobile JSON 계약)를 깨는 변경은 **두 PR을 같은 release window에 함께 머지**해야 합니다. PR 본문에 `Depends on #N`을 명시하세요.
- Adapter 인터페이스(OCR/LLM/Vision) 시그니처 변경은 모든 의존 영역 테스트가 green인 상태에서만 develop에 머지합니다.

## Related Documents

- Team collaboration entry point: [`team-collaboration/README.md`](./team-collaboration/README.md)
- Local setup (pre-commit, hooks, IDE): [`team-collaboration/LOCAL_SETUP.md`](./team-collaboration/LOCAL_SETUP.md)
- CI/CD gates: [`team-collaboration/CI_CD_GATES.md`](./team-collaboration/CI_CD_GATES.md)
- GitHub and CI rules (legacy detailed): [05-github-guidelines.md](./05-github-guidelines.md)
- Integration operations: [Integration-docs/01-ci-pr-integration-operations.md](./Integration-docs/01-ci-pr-integration-operations.md)
- Nutrition detailed architecture: [Nutrition-docs/06-tech-stack.md](./Nutrition-docs/06-tech-stack.md)
