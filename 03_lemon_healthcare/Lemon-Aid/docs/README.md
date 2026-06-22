# Docs Structure

This directory keeps team-wide documentation separate from each member or feature-area document set.

> **Last updated**: 2026-05-21 — added `team-collaboration/` folder (develop 통합 브랜치 협업 규칙 모음).

## Current Layout

### Team-wide summaries (root)

- `01-project-overview.md`: common project summary for the whole team. (영역 → commit scope 매핑 표 포함)
- `03-project-intent.md`: common product intent and positioning summary. (네이밍 ↔ 표현 정합성 표 포함)
- `05-github-guidelines.md`: common GitHub collaboration rules (legacy detailed). v1.2부터 신규 단명 브랜치 패턴(`<type>/<scope>-<주제>`)을 권장.
- `06-tech-stack.md`: common architecture and validation summary. (pre-commit/commit-msg/pre-push hook 포함)
- `10-compliance-checklist.md`: common compliance guardrails. (Repository operations compliance 추가)

### Collaboration rules (develop 통합용, 2026-05-21 신설)

- `team-collaboration/README.md`: 협업 가이드 인덱스
- `team-collaboration/BRANCH_STRATEGY.md`: 브랜치 전략 (Git Flow 변형 + 영역 scope)
- `team-collaboration/COMMIT_CONVENTION.md`: Conventional Commits + 도메인 scope 매핑
- `team-collaboration/PR_GUIDELINES.md`: PR 작성·리뷰·머지 절차
- `team-collaboration/DEVELOP_WORKFLOW.md`: feature → develop 통합 워크플로우
- `team-collaboration/LOCAL_SETUP.md`: 로컬 hook/별칭/IDE 설정
- `team-collaboration/MERGE_AND_CONFLICT.md`: rebase·충돌 해결·복구
- `team-collaboration/CODE_REVIEW_CHECKLIST.md`: 리뷰 체크리스트
- `team-collaboration/CI_CD_GATES.md`: 자동 게이트 정의
- `team-collaboration/TEAM_QUICK_REFERENCE.md`: 한 페이지 치트시트

### Part-specific folders

- `Nutrition-docs/`: detailed Nutrition and supplement-analysis documents maintained by the Nutrition part. See `Nutrition-docs/43-ocr-3-tier-fixture-evaluation-report-plan.md` for the current OCR fixture evaluation gate.
- `Food-docs/`: reserved for food image analysis documents.
- `Chat-docs/`: reserved for AI agent chat documents.
- `Integration-docs/`: reserved for final integration, deployment, and demo documents.

## Rule

Keep detailed feature work inside the matching part folder. Keep only team-wide summaries, collaboration rules, and cross-part operating guides in this root directory.

신규 협업 규칙 변경(브랜치/커밋/PR/CI 관련)은 `team-collaboration/` 폴더에서 PR로 제안합니다. 기존 `05-github-guidelines.md`는 legacy detailed 레퍼런스로 유지하며, 새 결정은 `team-collaboration/` 쪽이 우선합니다.

## Where to start

1. 처음 보는 팀원 → [`team-collaboration/README.md`](./team-collaboration/README.md) → [`team-collaboration/LOCAL_SETUP.md`](./team-collaboration/LOCAL_SETUP.md)
2. 매일 작업할 때 치트시트 → [`team-collaboration/TEAM_QUICK_REFERENCE.md`](./team-collaboration/TEAM_QUICK_REFERENCE.md)
3. 컴플라이언스 확인 → [`10-compliance-checklist.md`](./10-compliance-checklist.md)
4. 기획 의도 / 영역 정의 → [`01-project-overview.md`](./01-project-overview.md) + [`03-project-intent.md`](./03-project-intent.md)
