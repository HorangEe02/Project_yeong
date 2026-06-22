# 10. Compliance Checklist

> Status: team-wide summary
> Last updated: 2026-05-21 (repository operations compliance · develop merge gate 추가)
> Detailed source: [Nutrition-docs/10-compliance-checklist.md](./Nutrition-docs/10-compliance-checklist.md)

## Legal Notice

This document is an engineering and collaboration checklist. It is not legal advice. Any production release involving healthcare, prescription, lab, or sensitive personal data needs legal and domain review.

## Common Prohibitions

- Do not provide diagnosis, prescription, treatment instructions, or disease confirmation.
- Do not recommend direct dose changes for medication or supplements as a definitive instruction.
- Do not imply guaranteed treatment, cure, or prevention.
- Do not expose raw health images, OCR text, personal identifiers, or sensitive health data without explicit consent and retention rules.
- Do not call external OCR/LLM providers for sensitive data unless the feature gate, user consent, and environment policy allow it.

## Required Output Style

Use health-management wording:

| Avoid | Prefer |
|------|--------|
| "You have disease X." | "This result may require professional review." |
| "Take more of ingredient X." | "Your intake appears below the reference range; consider reviewing this with a professional." |
| "Stop/change this medication." | "Medication changes must be confirmed by a clinician or pharmacist." |
| "This food cures fatigue." | "This food may help support nutrient intake related to fatigue management." |

## Cross-Part Gates

| Gate | Applies To | Required Before Activation |
|------|------------|----------------------------|
| External OCR | supplement images, food images, regulated documents | consent, environment flag, provider review |
| Local or external LLM | chat, supplement text parsing, explanation generation | prompt/output guardrails, no raw sensitive leakage |
| Regulated document intake | prescription, lab result, medical documents | intake-only contract, no diagnosis or dose-change output |
| Learning data storage | image/text embeddings, vector DB, model improvement | explicit learning consent, retention policy, deletion support |

## Repository Operations Compliance (develop 통합 단계)

`develop`로 향하는 모든 PR은 다음 운영 규칙도 만족해야 합니다. (자동 게이트는 [`team-collaboration/CI_CD_GATES.md`](./team-collaboration/CI_CD_GATES.md))

| Operations Gate | 검증 항목 | 위반 시 조치 |
|-----------------|-----------|--------------|
| Secret hygiene | `.env`, API 키, JWT secret, 인증서, Service Account JSON 미포함 | 즉시 키 회전 → `git filter-repo`로 히스토리 제거 → 팀 공지 |
| PII / 사용자 데이터 | 실제 사용자 이메일·전화·주민번호·진료기록 미포함 | 픽스처/스냅샷 즉시 익명화, PR rebase |
| Sensitive image fixtures | 환자/사용자 식별 가능한 이미지·OCR 텍스트 미포함 | 동의 게이트 통과한 합성 데이터로 교체 |
| Large binary | 2MB 이상 파일은 LFS 또는 외부 스토리지 (`check-added-large-files` 차단) | 압축 또는 LFS 전환 |
| Commit message | Conventional Commits 형식 (`<type>(<scope>): <subject>`) | commit-msg hook으로 차단 — 메시지 재작성 |
| External API toggle | 외부 OCR/LLM provider 활성화 PR은 default OFF 유지 확인 | feature flag/환경변수 기본값 OFF로 되돌리기 |
| Medical wording | 코드/문서/UI에 `diagnose` `prescribe` `cure` `treat` 등 금지어 없음 | 단어 교체 (Required Output Style 표 참조) |

## Develop → Main Release Compliance

`develop` → `main` release PR을 머지하기 전 추가 점검:

- [ ] 새로 머지된 cross-part 변경이 모두 동의/환경 게이트를 통과
- [ ] 외부 provider 호출 흐름이 demo 시점에 의도된 상태(ON/OFF)인지 확인
- [ ] 사용자 노출 텍스트(앱·웹·문서)에 의료 표현 점검
- [ ] 변경 이력에 compliance-relevant 사항(외부 API 키 추가, 새 PII 흐름 등) 명시
- [ ] release 태그(`v0.x.y`) 본문에 면책 고지 링크 포함

## Naming Compliance

- 브랜치/PR/커밋 메시지에 사용자 식별자(이메일, 실명, 진료기관명) 포함 금지
- `feat(...): 김OO 케이스 디버그`처럼 보이는 표현은 PR description에서만 사용하고 commit subject에는 익명화

## Related Documents

- Common project overview: [01-project-overview.md](./01-project-overview.md)
- Common product intent: [03-project-intent.md](./03-project-intent.md)
- Common tech stack: [06-tech-stack.md](./06-tech-stack.md)
- CI/CD gates (자동 게이트 정의): [`team-collaboration/CI_CD_GATES.md`](./team-collaboration/CI_CD_GATES.md)
- Code review checklist (수동 게이트): [`team-collaboration/CODE_REVIEW_CHECKLIST.md`](./team-collaboration/CODE_REVIEW_CHECKLIST.md)
- Nutrition detailed compliance checklist: [Nutrition-docs/10-compliance-checklist.md](./Nutrition-docs/10-compliance-checklist.md)
