# 02. P0 Repo Structure And CI Migration Plan

> Status: implemented locally, pending staging/commit
> Date: 2026-05-15
> Scope: `03_lemon_healthcare/yeong-Vision-Nutrition` to `03_lemon_healthcare/yeong-Lemon-Aid` canonical migration and root GitHub CI repair

## Purpose

This document defines the P0 migration needed before additional product work.
The goal is to make the repository layout, Git tracking, CI workflows, PR
template, and CODEOWNERS rules point to the same canonical project path.

The current local implementation is usable, but the collaboration gate is at
risk because the real Git root is:

```text
/Users/yeong/99_me/00_github
```

The active GitHub Actions workflow directory is therefore:

```text
/Users/yeong/99_me/00_github/.github/workflows
```

GitHub Actions does not treat this nested folder as the repository workflow
directory:

```text
/Users/yeong/99_me/00_github/03_lemon_healthcare/.github/workflows
```

## Official Documentation Checked

Use the following official GitHub documentation as the implementation boundary:

- GitHub Actions searches `.github/workflows` in the root of the repository for workflow files present in the event commit or ref: <https://docs.github.com/en/actions/concepts/workflows-and-actions/workflows>
- Branch and path filters can skip workflows; if such checks are required, skipped checks can remain pending and block merges: <https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax>
- `defaults.run.working-directory` is valid for run steps, and more specific defaults override broader defaults: <https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/set-default-values-for-jobs>
- CODEOWNERS must be in `.github/`, repository root, or `docs/`, and GitHub searches those locations in order: <https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners>
- Pull request templates can be stored at `.github/pull_request_template.md` or `.github/PULL_REQUEST_TEMPLATE/...`: <https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/creating-a-pull-request-template-for-your-repository>

## Implementation Update (2026-05-15)

- Root Lemon workflows now live under `/Users/yeong/99_me/00_github/.github/workflows/`.
- Root `17-lemon-backend-ci.yml` targets `03_lemon_healthcare/yeong-Lemon-Aid/backend`.
- Root docs and mobile workflows were added as `17-lemon-docs-ci.yml` and `17-lemon-mobile-ci.yml`.
- Root PR/Issue templates, CODEOWNERS, and Dependabot now include Lemon Healthcare paths.
- Root `.gitignore` now preserves the previous-version Lemon Aid PDF exception while continuing to ignore generated PDFs.
- Tracked nested `03_lemon_healthcare/.github` workflow/template files were removed so only the repository root `.github` remains active.

Remaining release task: stage the old `yeong-Vision-Nutrition` deletions and new
`yeong-Lemon-Aid` additions intentionally in the migration commit.

## Pre-Implementation Local Facts

| Item | Current fact | Risk |
| --- | --- | --- |
| Git root | `/Users/yeong/99_me/00_github` | CI paths must be root-relative from this directory. |
| Current work branch | `codex/p1-5-stabilization` | Migration should be reviewed before publish to team branches. |
| Old tracked path | `03_lemon_healthcare/yeong-Vision-Nutrition/` deleted in working tree | Needs formal rename/migration staging, not accidental deletion. |
| New local path | `03_lemon_healthcare/yeong-Lemon-Aid/` untracked | Must be added selectively, excluding secrets and generated files. |
| Root workflow before implementation | `.github/workflows/17-lemon-backend-ci.yml` | Repaired to target `yeong-Lemon-Aid` in the local implementation above. |
| Nested workflow before implementation | `03_lemon_healthcare/.github/workflows/*.yml` | Removed from tracked files in the local implementation above. |
| Backend validation | `390 passed, 2 skipped`; black, ruff, mypy, KDRIs validator pass locally | Keep this as the post-migration acceptance bar. |

## Decision

Adopt `03_lemon_healthcare/yeong-Lemon-Aid/` as the canonical Lemon Aid
workspace inside the current monorepo, and migrate all active GitHub
collaboration files to the repository root `.github/`.

Do not keep two active-looking workflow directories. The nested
`03_lemon_healthcare/.github/` folder should either be removed from tracked
source or converted into non-authoritative documentation. The recommended P0
implementation is to remove nested workflow files after their useful content is
merged into the root `.github/` files.

## Alternatives Considered

| Option | Decision | Reason |
| --- | --- | --- |
| Keep `yeong-Vision-Nutrition` and discard `yeong-Lemon-Aid` | Reject | Current project structure, README, docs, data layout, and team reports now use Lemon Aid as the product root. Reverting would lose the team integration work. |
| Make `03_lemon_healthcare/` a separate Git repository | Reject for P0 | The current repository root contains multiple projects and existing root GitHub workflows. Splitting the repo is a larger GitHub/remote migration, not a P0 repair. |
| Keep active CI in `03_lemon_healthcare/.github/` | Reject | GitHub Actions scans `.github/workflows` at the repository root. Nested workflows are misleading for this repo shape. |
| Duplicate workflows in root and nested `.github` | Reject | Duplication will drift and make PR gating ambiguous. |
| Migrate `yeong-Lemon-Aid` and repair root `.github` | Accept | Matches current local implementation and GitHub's documented workflow lookup behavior. |

## Target Repository Layout

```text
/Users/yeong/99_me/00_github/
├── .github/
│   ├── PULL_REQUEST_TEMPLATE.md
│   ├── CODEOWNERS
│   └── workflows/
│       ├── 17-lemon-backend-ci.yml
│       ├── 17-lemon-docs-ci.yml
│       └── 17-lemon-mobile-ci.yml
└── 03_lemon_healthcare/
    ├── PROJECT_GUIDE.md
    ├── guide.html
    └── yeong-Lemon-Aid/
        ├── README.md
        ├── backend/
        ├── config/
        ├── data/
        ├── docs/
        ├── frontend/
        ├── mobile/
        ├── outputs/
        └── records/
```

`03_lemon_healthcare/.github/` should not contain workflow files after P0. If
the team wants to keep a copy for reference, store that reference in a normal
documentation path and mark it as inactive.

## CI Design

### Required root workflows

| Workflow | Root path | Trigger policy | Responsibility |
| --- | --- | --- | --- |
| Lemon backend CI | `.github/workflows/17-lemon-backend-ci.yml` | `pull_request`, `push`, `workflow_dispatch` | Python quality, KDRIs data gate, OpenAPI smoke, Alembic smoke, pytest |
| Lemon docs CI | `.github/workflows/17-lemon-docs-ci.yml` | `pull_request`, `push`, `workflow_dispatch` | Markdown lint/link checks or at minimum whitespace/link-sensitive docs gate |
| Lemon mobile CI | `.github/workflows/17-lemon-mobile-ci.yml` | `pull_request`, `push`, `workflow_dispatch` | Flutter checks when `mobile/flutter_app/pubspec.yaml` exists; otherwise explicit skip |

### Path filtering rule

If branch protection requires a Lemon CI check, avoid top-level `paths` filters
on that required workflow. GitHub documents that skipped workflows can leave
required checks pending. Prefer one of these designs:

1. Required workflow without top-level `paths`, with per-job conditional logic.
2. Non-required path-filtered component workflows plus one always-on required
   summary workflow.

For P0, use the simpler safe design:

- `17-lemon-backend-ci.yml` runs on `pull_request` and `push` for `main`,
  `develop`, and `yeong-tech`.
- It can keep backend commands scoped by `working-directory`, but should not be
  hidden inside the nested `.github`.
- If runtime cost becomes high, add job-level change detection later rather than
  blocking the P0 path repair.

### Backend job contract

Use this canonical working directory:

```yaml
defaults:
  run:
    shell: bash
    working-directory: 03_lemon_healthcare/yeong-Lemon-Aid/backend
```

Use Python `3.13`, because `backend/pyproject.toml` requires `>=3.13`.

Required commands:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt -r requirements-dev.txt

black --check Nutrition-backend/src Nutrition-backend/tests food_image_analysis/src food_image_analysis/tests ai_agent_chat/src ai_agent_chat/tests alembic scripts
ruff check Nutrition-backend/src Nutrition-backend/tests food_image_analysis/src food_image_analysis/tests ai_agent_chat/src ai_agent_chat/tests alembic scripts
mypy --explicit-package-bases Nutrition-backend/src Nutrition-backend/tests food_image_analysis/src food_image_analysis/tests ai_agent_chat/src ai_agent_chat/tests --strict

python -m json.tool ../config/implementation-readiness.settings.json
python -m json.tool ../config/service-segmentation.settings.json
python scripts/validate_kdris_dataset.py --require-approved

alembic upgrade head
alembic current
pytest -q --no-cov
```

Coverage can remain a later CI enhancement. The local P0 acceptance command is
`pytest -q --no-cov` because it already proves the current 390-test suite
without making branch migration slower.

## Git Migration Strategy

### Commit unit 1: canonical workspace migration

Suggested commit:

```text
chore(repo): migrate Lemon Aid workspace root

Move the Lemon Healthcare project workspace from the old
yeong-Vision-Nutrition path to the team-facing yeong-Lemon-Aid path so team
members can work against one canonical product root.
```

Implementation steps:

1. Confirm current root:

   ```bash
   git rev-parse --show-toplevel
   ```

2. Stage old path deletion and new path addition selectively.

3. Exclude secrets and generated files from staging:

   ```text
   03_lemon_healthcare/yeong-Lemon-Aid/.env
   03_lemon_healthcare/yeong-Lemon-Aid/api-key/
   03_lemon_healthcare/yeong-Lemon-Aid/.venv/
   03_lemon_healthcare/yeong-Lemon-Aid/.pytest_cache/
   03_lemon_healthcare/yeong-Lemon-Aid/.ruff_cache/
   03_lemon_healthcare/yeong-Lemon-Aid/.mypy_cache/
   03_lemon_healthcare/yeong-Lemon-Aid/htmlcov/
   03_lemon_healthcare/yeong-Lemon-Aid/**/__pycache__/
   03_lemon_healthcare/yeong-Lemon-Aid/**/.DS_Store
   ```

4. Review rename detection:

   ```bash
   git diff --cached --summary
   git diff --cached --name-status --find-renames
   ```

5. If rename detection is poor because content also changed, keep the commit
   message explicit that this is a migration snapshot, not a pure rename.

### Commit unit 2: root GitHub CI repair

Suggested commit:

```text
ci(lemon): point root workflows to Lemon Aid workspace

Move active Lemon CI ownership to the repository root .github directory because
GitHub Actions only discovers workflows from the root .github/workflows folder.
```

Implementation steps:

1. Update root `.github/workflows/17-lemon-backend-ci.yml` from old paths:

   ```text
   03_lemon_healthcare/yeong-Vision-Nutrition/...
   ```

   to new paths:

   ```text
   03_lemon_healthcare/yeong-Lemon-Aid/...
   ```

2. Add or update root Lemon docs and mobile workflows if the team wants those
   checks in GitHub Actions.

3. Remove or de-authorize nested workflow files:

   ```text
   03_lemon_healthcare/.github/workflows/ci-backend.yml
   03_lemon_healthcare/.github/workflows/ci-docs.yml
   03_lemon_healthcare/.github/workflows/ci-mobile.yml
   ```

4. Update root `.github/PULL_REQUEST_TEMPLATE.md` to reference
   `yeong-Lemon-Aid`, not `yeong-Vision-Nutrition`.

5. Add root `.github/CODEOWNERS`, or move the nested CODEOWNERS content to root
   `.github/CODEOWNERS`, with root-relative path patterns.

### Commit unit 3: docs alignment

Suggested commit:

```text
docs(integration): document P0 repo and CI migration plan

Record the canonical Lemon Aid path, active GitHub workflow location, migration
steps, and validation gate so future implementation work does not restart the
same repository-structure decision.
```

Implementation steps:

1. Keep this document in `docs/Integration-docs/`.
2. Link it from `docs/Integration-docs/README.md`.
3. Update `docs/05-github-guidelines.md` if it still says the nested
   `.github/` directory is active.
4. Update root and project README references to current validation counts only
   after rerunning the commands.

## Acceptance Criteria

P0 is done only when all checks below are true.

### Repository shape

- `git status --short` shows no accidental deletion-only state for
  `yeong-Vision-Nutrition` without corresponding `yeong-Lemon-Aid` additions.
- `git diff --cached --name-only` does not include `.env`, `api-key/`,
  `.DS_Store`, `__pycache__`, `.venv`, `htmlcov`, `.coverage`, local cache
  folders, or raw credential files.
- `03_lemon_healthcare/yeong-Lemon-Aid/README.md` is the canonical project
  README.
- `03_lemon_healthcare/yeong-Vision-Nutrition/` is absent or intentionally
  archived outside active runtime paths.

### Root GitHub metadata

- Active workflows are under repository root `.github/workflows`.
- Root Lemon workflows use `03_lemon_healthcare/yeong-Lemon-Aid/...` paths.
- Root PR template refers to Lemon Aid and current validation gates.
- Root CODEOWNERS has entries for:
  - `03_lemon_healthcare/yeong-Lemon-Aid/backend/`
  - `03_lemon_healthcare/yeong-Lemon-Aid/docs/`
  - `03_lemon_healthcare/yeong-Lemon-Aid/data/`
  - `03_lemon_healthcare/yeong-Lemon-Aid/mobile/`
  - `03_lemon_healthcare/yeong-Lemon-Aid/frontend/`
  - `.github/`

### Local validation

Run from `03_lemon_healthcare/yeong-Lemon-Aid/backend`:

```bash
./.venv/bin/python -m black --check .
./.venv/bin/python -m ruff check .
./.venv/bin/python -m mypy Nutrition-backend/src Nutrition-backend/tests food_image_analysis/src food_image_analysis/tests ai_agent_chat/src ai_agent_chat/tests
./.venv/bin/python scripts/validate_kdris_dataset.py --require-approved
./.venv/bin/python -m pytest -q --no-cov
```

Run from repository root:

```bash
git diff --check -- .github 03_lemon_healthcare/yeong-Lemon-Aid
git diff --cached --name-only | rg '(^|/)(\.env|\.DS_Store|__pycache__|\.venv|htmlcov|\.coverage|api-key)(/|$)' && exit 1 || true
```

### Remote validation after push

- GitHub Actions shows Lemon backend CI from root `.github/workflows`.
- The workflow log uses working directory
  `03_lemon_healthcare/yeong-Lemon-Aid/backend`.
- The old `yeong-Vision-Nutrition` path does not appear in root Lemon workflow
  logs.
- Required checks are not left pending because of top-level branch/path filters.

## Implementation Order

1. Freeze product feature work during P0 migration.
2. Update root `.gitignore` and project `.gitignore` if any generated or secret
   files still appear in `git status`.
3. Stage the canonical workspace migration and inspect staged paths.
4. Update root workflows, PR template, and CODEOWNERS.
5. Remove or retire nested `03_lemon_healthcare/.github` workflow files.
6. Run local backend validation.
7. Run repository diff checks and secret-path checks.
8. Commit with Conventional Commits.
9. Push to a review branch.
10. Confirm GitHub Actions runs from root `.github/workflows`.
11. Open PR to `develop` or the agreed team integration branch.

## Rollback Plan

If CI fails after the migration:

1. Do not restore `yeong-Vision-Nutrition` as the canonical path immediately.
2. First check whether the failure is path-related in root workflow
   `working-directory`, cache paths, or `PYTHONPATH`.
3. If the failure is caused by accidental generated files or secrets in the
   staged set, remove them from the index and update `.gitignore`.
4. If the failure is caused by missing files in the new path, compare staged
   old/new path lists with `git diff --cached --name-status --find-renames`.
5. Only if the new workspace is structurally incomplete should the migration be
   paused and re-split into a pure rename commit followed by functional changes.

## Team Review Decisions And Remaining Questions

- Decision: Lemon CI now runs on `main`, `develop`, and `yeong-tech`, plus
  manual `workflow_dispatch`.
- Decision: tracked nested `03_lemon_healthcare/.github` workflow/template
  files were deleted to remove ambiguity.
- Decision: `17-lemon-backend-ci.yml` retains `pip-audit` in P0 because
  dependency risk is part of the collaboration gate.
- Remaining: should branch protection require one always-on Lemon CI summary check, or
  only component-specific checks?
- Remaining: should output reports and generated presentation assets stay in the repo, or
  move to release artifacts/external storage after the migration?
