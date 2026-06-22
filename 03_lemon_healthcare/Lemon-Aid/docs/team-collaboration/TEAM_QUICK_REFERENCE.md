# 🍋 Lemon Aid — 팀 협업 치트시트 (한 페이지)

> 자주 쓰는 명령·규칙·패턴을 한 페이지에. 책상에 인쇄해 두거나 IDE 한쪽에 띄워 두세요.

---

## 🌳 브런치

```
main           ← 배포 (protected, 2명 승인)
└── develop    ← 통합/테스트 (protected, 1명 승인)
    └── feat/<영역>-<주제>   ← 본인 작업 (단명)
```

**영역(scope)**: `mobile` `backend` `ai` `ocr` `db` `auth` `ux` `infra` `docs` `team` `test` `data`

**type**: `feat` `fix` `docs` `style` `refactor` `perf` `test` `chore` `ci` `build` `revert` `data` `ops`

---

## ✍️ 커밋 메시지 (Conventional Commits)

```
<type>(<scope>): <한글/영문 명령형 subject>

[선택: 왜 변경했는지]

[선택: Closes #N]
```

✅ `feat(mobile): 메인 대시보드 5탭 셸 추가`
✅ `fix(ocr): naver-chronic-0001 스냅샷 미스매치 수정`
✅ `chore(infra): Python 3.13 호환 의존성 상향`
❌ `[mobile] dashboard update` ← 옛 패턴
❌ `update.` ← 마침표, type 없음

---

## ⚡ 일상 명령

```bash
# 새 작업 시작
git fetch team
git checkout -b feat/<영역>-<주제> team/develop

# develop 최신화 (작업 중)
git fetch team && git rebase team/develop

# 커밋
git add -p                 # 부분 스테이징 (권장)
git commit -m "feat(scope): subject"

# 푸시
git push -u team feat/<영역>-<주제>

# PR
gh pr create --base develop --fill

# CI 상태
gh pr checks

# 안전한 강제 푸시 (rebase 후)
git push team feat/<영역>-<주제> --force-with-lease

# 머지된 로컬 정리
git branch --merged | grep -vE '\*|main|develop' | xargs git branch -D
```

---

## 🔀 PR 체크리스트

- [ ] 제목: `<type>(<scope>): <subject>`
- [ ] 본문: 요약 / 변경 / 검증 / 체크리스트 / 관련 이슈
- [ ] develop rebase 동기화
- [ ] pre-commit 통과
- [ ] CI green
- [ ] 비밀키·.env·2MB+ 파일 없음
- [ ] 문서 업데이트 (해당 시)
- [ ] 본인 영역 외 1명 리뷰 요청

**머지 방식**: feature → develop = **Squash**, develop → main = **Merge commit**

---

## ⚔️ 충돌 해결 5단계

```bash
1. git fetch team
2. git rebase team/develop          # 충돌 발생
3. <파일 열어서 마커 정리>
4. git add <해결한 파일>
5. git rebase --continue            # 끝까지 반복
6. git push team <브런치> --force-with-lease
```

**reflog로 복구**: `git reflog` → `git reset --hard HEAD@{N}`

---

## 🚦 게이트 (CI)

| 게이트 | 로컬 명령 |
|--------|-----------|
| pre-commit | `pre-commit run --all-files` |
| backend test | `pytest backend/tests -x` |
| mobile analyze | `cd mobile && flutter analyze && flutter test` |
| security | `gitleaks detect --no-git` |

---

## 🛡️ 절대 금지

- ❌ `git push --force` (lease 없이)
- ❌ `git commit --no-verify`
- ❌ `git push team develop` / `git push team main` (직접)
- ❌ `.env` / 비밀키 커밋
- ❌ 본인 PR 셀프 머지
- ❌ 작업자 이름 브런치 (`yeong-tech`, `taedong-design` 등 — 영역 기반으로 변경)

---

## 🆘 한 줄 트러블슈팅

| 상황 | 해결 |
|------|------|
| pre-commit 실패 | `pre-commit run --all-files` 후 자동 수정된 파일 add |
| CI lint 실패 | `black .` + `ruff check --fix .` |
| 충돌 났음 | `git rebase --abort`로 일단 멈추고 [`MERGE_AND_CONFLICT.md`](./MERGE_AND_CONFLICT.md) |
| 잘못 push 함 | `git reflog` → 이전 상태로 `--force-with-lease` |
| 리뷰가 안 와요 | 24시간 후 다른 리뷰어 추가 + Slack `#dev` |
| `.env` 실수로 커밋 | **즉시** 키 회전 + `git filter-repo` + 팀 공지 |

---

## 👥 영역 매핑 (현재 팀)

| 팀원 | GitHub | 주 영역 | 자주 머지하는 곳 |
|------|--------|---------|------------------|
| changmin | @changmin5957-sys | `ai` | `feat/ai-*` |
| yeong | @HorangEe02 | `backend` `ocr` | `feat/backend-*` `feat/ocr-*` |
| sunghoon | @ParkSungHoon | `db` `auth` | `feat/db-*` `feat/auth-*` |
| jongpil | @jongpil-Mun | `backend` `test` `data` | `feat/backend-*` `test/*` `data/*` |
| taedong | @neong0819 | `mobile` `ux` | `feat/mobile-*` `feat/ux-*` |

> 영역이 겹치는 PR끼리는 Slack에서 머지 순서 협의.

---

## 📅 정기 일정

| 시점 | 이벤트 |
|------|--------|
| 매일 18:00 | 데일리 스탠드업 (10분) |
| 매주 화 17:00 | develop → main 후보 검토 |
| 매주 금 17:00 | release 태그 + main 머지 |
| 매월 마지막 금 | 회고 + 규칙 업데이트 검토 |

---

## 🎯 황금률

1. **작게 자주** — PR ≤ 500줄, 3-7일 안에 머지
2. **매일 sync** — `git fetch team && git rebase team/develop`
3. **CI 빨갛게 두지 않기** — 본인 PR이 빨가면 즉시 조치
4. **리뷰는 코드를 비판, 사람은 비판하지 않기** — 칭찬도 자주
5. **막히면 1분 안에 도움 요청** — 30분 혼자 헤매지 말 것

---

## 🔗 전체 문서

- 시작 → [`README.md`](./README.md)
- 브런치 → [`BRANCH_STRATEGY.md`](./BRANCH_STRATEGY.md)
- 커밋 → [`COMMIT_CONVENTION.md`](./COMMIT_CONVENTION.md)
- PR → [`PR_GUIDELINES.md`](./PR_GUIDELINES.md)
- 워크플로우 → [`DEVELOP_WORKFLOW.md`](./DEVELOP_WORKFLOW.md)
- 로컬 설정 → [`LOCAL_SETUP.md`](./LOCAL_SETUP.md)
- 충돌 → [`MERGE_AND_CONFLICT.md`](./MERGE_AND_CONFLICT.md)
- 리뷰 → [`CODE_REVIEW_CHECKLIST.md`](./CODE_REVIEW_CHECKLIST.md)
- CI → [`CI_CD_GATES.md`](./CI_CD_GATES.md)
