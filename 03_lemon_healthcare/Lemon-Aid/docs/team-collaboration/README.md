# 🍋 Lemon Aid — 팀 협업 가이드 (develop 통합 브런치)

> `develop` 브런치는 각 팀원이 자신의 `feat/*` · `fix/*` 브런치에서 구현한 기능을 **하나로 합치고, 적용하고, 통합 테스트**하는 곳입니다. `main`은 배포 가능한 안정 버전만 받습니다.

이 폴더의 모든 가이드는 **각자 로컬 환경에서 그대로 적용**할 수 있도록 작성되었습니다.

---

## 📚 문서 인덱스

| # | 문서 | 누가 읽어야 하나 | 무엇을 다루나 |
|---|------|------------------|---------------|
| 1 | [`BRANCH_STRATEGY.md`](./BRANCH_STRATEGY.md) | 전원 | 브런치 이름·수명·머지 흐름 |
| 2 | [`COMMIT_CONVENTION.md`](./COMMIT_CONVENTION.md) | 전원 | Conventional Commits + Korean scope |
| 3 | [`PR_GUIDELINES.md`](./PR_GUIDELINES.md) | 전원 | PR 작성·리뷰·머지 절차 |
| 4 | [`DEVELOP_WORKFLOW.md`](./DEVELOP_WORKFLOW.md) | 전원 | feature → develop 통합 워크플로우 |
| 5 | [`LOCAL_SETUP.md`](./LOCAL_SETUP.md) | 전원 (최초 1회) | 로컬 git hook / 도구 설치 |
| 6 | [`MERGE_AND_CONFLICT.md`](./MERGE_AND_CONFLICT.md) | 전원 | rebase / 충돌 해결 / 회복 절차 |
| 7 | [`CODE_REVIEW_CHECKLIST.md`](./CODE_REVIEW_CHECKLIST.md) | 리뷰어 + 작성자 | PR 리뷰 체크리스트 |
| 8 | [`CI_CD_GATES.md`](./CI_CD_GATES.md) | 전원 | pre-commit / GitHub Actions 게이트 |
| 9 | [`TEAM_QUICK_REFERENCE.md`](./TEAM_QUICK_REFERENCE.md) | 전원 (북마크) | 한 페이지 치트시트 |

---

## 🚦 develop 브런치 한 줄 요약

```
main (배포)
  └── develop (통합 + 테스트)  ← 모든 PR이 여기로 들어옴
        ├── feat/mobile-dashboard         (taedong)
        ├── feat/backend-ocr-baseline      (yeong)
        ├── feat/ai-agent-coaching         (changmin)
        ├── feat/db-oauth                  (sunghoon)
        └── feat/food-nutrition-tests      (jongpil)
```

- ❌ `develop` 직접 push 금지
- ✅ PR + 리뷰 1명 + CI 통과 → **Squash and Merge**
- 🔄 매주 화/금 17:00 develop → main rebase 검토 (정기 통합 시점)

---

## 🧭 처음 시작하는 팀원에게

1. [`LOCAL_SETUP.md`](./LOCAL_SETUP.md) 따라 `pre-commit install`, git hooks 설정 (10분)
2. [`BRANCH_STRATEGY.md`](./BRANCH_STRATEGY.md) + [`COMMIT_CONVENTION.md`](./COMMIT_CONVENTION.md) 읽기 (15분)
3. 본인 영역 브런치를 `develop`에서 분기:
   ```bash
   git fetch team
   git checkout -b feat/<영역>-<이름> team/develop
   ```
4. 작업 후 PR → [`PR_GUIDELINES.md`](./PR_GUIDELINES.md) 따라 작성

---

## 🆘 도움이 필요할 때

- **충돌이 났어요** → [`MERGE_AND_CONFLICT.md`](./MERGE_AND_CONFLICT.md)
- **CI가 실패해요** → [`CI_CD_GATES.md`](./CI_CD_GATES.md)
- **커밋 메시지 규칙이 헷갈려요** → [`TEAM_QUICK_REFERENCE.md`](./TEAM_QUICK_REFERENCE.md)
- **리뷰어가 뭘 봐야 하나요** → [`CODE_REVIEW_CHECKLIST.md`](./CODE_REVIEW_CHECKLIST.md)

---

## 📅 문서 관리

- 최초 작성일: 2026-05-21
- 변경 시 PR로 제안 후 머지 (이 폴더의 변경도 동일하게 `docs/<영역>` 컨벤션 적용)
- 분기별 회고에서 규칙 업데이트 검토
