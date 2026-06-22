# 01. Project Overview

> Status: team-wide summary
> Last updated: 2026-05-21 (develop integration branch 도입 반영)
> Detailed source: [Nutrition-docs/01-project-overview.md](./Nutrition-docs/01-project-overview.md)

## One-Line Summary

Lemon Aid is an AI healthcare project that combines supplement-label analysis, food-image analysis, health activity data, and AI chat support into a unified health-management experience.

## Team Scope

| Area | Working Folder | Responsibility | Commit Scope |
|------|----------------|----------------|--------------|
| Nutrition | `docs/Nutrition-docs/`, `backend/Nutrition-backend/`, `data/supplement_images/`, `data/nutrition_reference/` | supplement image intake, OCR/text parsing, nutrient analysis, KDRIs lookup, weight/activity/nutrition logic | `nutrition` · `ocr` · `backend` |
| Food | `docs/Food-docs/`, `backend/food_image_analysis/`, `data/food_images/` | food image classification, cuisine/category taxonomy, meal metadata | `food` · `backend` |
| Chat | `docs/Chat-docs/`, `backend/ai_agent_chat/` | AI agent chat flow, safe user guidance, context orchestration | `aiagent` · `ai` |
| Mobile / UX | `mobile/`, `frontend/`, `assets/` | Flutter app, UI/UX, design system, brand assets | `mobile` · `design` · `ux` |
| Database / Auth | `backend/alembic/`, `backend/scripts/`, OAuth modules | schema, migration, OAuth, session | `db` · `auth` |
| Integration | `docs/Integration-docs/`, `docs/team-collaboration/`, `.github/`, root README/handoff files | CI, PR, release, demo, cross-part integration | `integration` · `infra` · `ci` · `team` |

## Common Product Boundary

- The product is positioned as non-diagnostic health-management support, not medical diagnosis, prescription, or treatment.
- Nutrition, food, and chat outputs must converge into one user-facing experience instead of separate demos.
- Sensitive health data and image-derived data must follow consent, retention, and external-processing gates.
- Implementation status must be checked against runtime code and tests, not planning documents alone.
- All cross-part code changes flow through the **`develop` integration branch** before reaching `main` — see [`docs/team-collaboration/DEVELOP_WORKFLOW.md`](./team-collaboration/DEVELOP_WORKFLOW.md).

## Branch Integration Model (2026-05-21 standardization)

```
main (release)            ← 시연·발표 기준 안정 버전 (protected, 2명 승인)
  ↑
develop (integration)     ← 통합·테스트 브랜치 (protected, 1명 승인)
  ↑                         모든 cross-part PR이 합쳐지는 지점
  └─ <type>/<scope>-<주제>  ← 단명(短命) 작업 브랜치, Squash Merge
  └─ <member>-<part>         ← 기존 고정 작업 브랜치 (점진적 마이그레이션)
```

신규 작업은 `<type>/<scope>-<주제>` 패턴을 권장합니다. 기존 `<member>-<part>` 브랜치(`yeong-tech`, `taedong-design` 등)는 develop에 PR 머지 후 영역 기반 브랜치로 재분기합니다.

## Current Source Of Truth

- Team collaboration entry point: [`docs/team-collaboration/README.md`](./team-collaboration/README.md)
- Collaboration and PR rules (legacy detailed): [05-github-guidelines.md](./05-github-guidelines.md)
- Commit convention (Conventional Commits + 도메인 scope): [`docs/team-collaboration/COMMIT_CONVENTION.md`](./team-collaboration/COMMIT_CONVENTION.md)
- Develop integration workflow: [`docs/team-collaboration/DEVELOP_WORKFLOW.md`](./team-collaboration/DEVELOP_WORKFLOW.md)
- Common product intent: [03-project-intent.md](./03-project-intent.md)
- Common technical map: [06-tech-stack.md](./06-tech-stack.md)
- Common compliance guardrails: [10-compliance-checklist.md](./10-compliance-checklist.md)
- Nutrition detailed design: [Nutrition-docs/](./Nutrition-docs/)
- Integration operations: [Integration-docs/01-ci-pr-integration-operations.md](./Integration-docs/01-ci-pr-integration-operations.md)
