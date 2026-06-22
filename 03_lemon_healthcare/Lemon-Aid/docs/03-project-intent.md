# 03. Project Intent

> Status: team-wide summary
> Last updated: 2026-05-21 (develop integration branch · collaboration rules 연계)
> Detailed source: [Nutrition-docs/03-project-intent.md](./Nutrition-docs/03-project-intent.md)

## Intent

The project should be framed as an AI healthcare and health-management service, not as a generic big-data project. Data and AI are implementation tools; the user-facing value is safer, more personalized health guidance.

## Differentiation Direction

- Connect supplement, food, activity, and chat information into one health context.
- Prioritize Korean users, Korean food context, Korean/English supplement labels, and KDRIs-based nutrition references.
- Keep chronic-condition and regulated-document features behind explicit review gates.
- Avoid claims that imply diagnosis, prescription, cure, or guaranteed treatment effect.
- Ship through one shared integration branch (`develop`) so all parts demonstrate the same product story at any moment.

## Part-Level Intent

| Part | Intent | Develop integration responsibility |
|------|--------|------------------------------------|
| Nutrition | Convert supplement/health/nutrition inputs into structured, consent-safe health-management insights. | OCR · KDRIs · 5-카드 분석 흐름이 develop에서 깨지지 않도록 fixture/통합 테스트 유지 |
| Food | Identify meal context and food categories so nutrition gaps are not inferred from supplements alone. | meal taxonomy/manifest 변경 시 develop CI에 데이터 게이트 통과 보장 |
| Chat | Explain results and collect follow-up context without crossing into medical advice. | LLM prompt/tool 변경은 compliance 테스트와 함께 develop에 PR |
| Mobile / UX | Surface backend contracts through one Pillyze-tone UI without leaking internal terms. | screen/route 변경은 develop의 mobile-build CI가 green인 상태에서만 머지 |
| Database / Auth | Provide one schema/auth contract that every part can rely on. | 마이그레이션은 develop 머지 전 down 시나리오까지 검증 |
| Integration | Ensure all parts share one product language, one CI/PR process, and one demo flow. | release PR (`develop → main`)을 매주 정기 시점에 큐레이션 |

## Decision Rule

When a feature can be described in multiple ways, choose the wording that is:

1. health-management oriented,
2. non-diagnostic,
3. evidence-aware,
4. testable in the current codebase,
5. consistent with team ownership folders,
6. consistent with the collaboration conventions in [`docs/team-collaboration/`](./team-collaboration/README.md) (브랜치명·커밋 type·scope·PR 템플릿).

## Naming ↔ Wording Alignment

기획 의도가 코드/문서/PR 제목에 일관되게 드러나도록 다음 표를 따릅니다.

| 사용자 노출 표현 | 코드/Commit scope | PR 제목 type |
|------------------|------------------|--------------|
| "영양제 라벨 분석" | `nutrition` / `ocr` | `feat(nutrition)` · `fix(ocr)` |
| "식단 인식" | `food` | `feat(food)` |
| "AI 헬스 코칭" | `aiagent` / `ai` | `feat(aiagent)` |
| "만성질환 안전 가이드" | compliance 텍스트 + 해당 scope | `docs(compliance)` 또는 해당 영역 |
| "동의·권한·약관" | `auth` / `compliance` | `feat(auth)` · `docs(compliance)` |

## Related Documents

- Project overview: [01-project-overview.md](./01-project-overview.md)
- Technical map: [06-tech-stack.md](./06-tech-stack.md)
- Compliance guardrails: [10-compliance-checklist.md](./10-compliance-checklist.md)
- Team collaboration entry point: [`team-collaboration/README.md`](./team-collaboration/README.md)
- Commit convention: [`team-collaboration/COMMIT_CONVENTION.md`](./team-collaboration/COMMIT_CONVENTION.md)
- Nutrition detailed strategy: [Nutrition-docs/03-project-intent.md](./Nutrition-docs/03-project-intent.md)
