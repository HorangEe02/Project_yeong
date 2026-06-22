# 🔄 develop 브런치 통합 워크플로우

> 일상 개발 흐름: **develop에서 분기 → 작업 → PR → develop에 머지** — 이 한 페이지로 정리.

---

## 1. 일일 시작 루틴

```bash
# 1) 작업 디렉토리로 이동
cd path/to/Lemon-sin

# 2) 원격 변경 동기화
git fetch team

# 3) 현재 브런치 확인
git status

# 4) develop 기반 작업 중이면 rebase
git rebase team/develop
```

✅ **체크**: `git log --oneline -5` 했을 때 최신 develop 커밋이 들어와 있어야 함.

---

## 2. 새 작업 시작

### 시나리오 A — 새 기능

```bash
git fetch team
git checkout -b feat/<영역>-<주제> team/develop

# 예
git checkout -b feat/mobile-supplement-detail team/develop
```

### 시나리오 B — 버그 수정

```bash
git checkout -b fix/<영역>-<주제> team/develop
```

### 시나리오 C — 긴급(hotfix)

```bash
git checkout -b hotfix/<영역>-<주제> team/main
# main 머지 후 develop에 cherry-pick
```

---

## 3. 작업 중 커밋

```bash
# 변경 확인
git status
git diff

# 부분 스테이징(권장) — 의미 단위로
git add -p

# 또는 파일 단위
git add backend/.../ocr_service.py tests/...

# 커밋 (commit-msg hook이 형식 검증)
git commit -m "feat(ocr): chronic disease matrix 통합"
```

**자주 발생하는 실수**
- ❌ `git add -A` 또는 `git add .` — `.env`, 대용량 파일이 함께 들어갈 위험
- ❌ `--amend` 남발 — push된 커밋 amend는 force-push 필요
- ❌ "WIP" 커밋을 그대로 PR — 머지 전 `git rebase -i`로 정리

---

## 4. develop 최신화 (작업 중 정기적으로)

매일 또는 develop에 큰 변경이 들어왔을 때:

```bash
git fetch team
git rebase team/develop

# 충돌 발생 시 → MERGE_AND_CONFLICT.md 참고
# 충돌 해결 후
git add <충돌 해결한 파일>
git rebase --continue

# 이미 push한 브런치라면 force-with-lease로 갱신
git push team feat/<영역>-<주제> --force-with-lease
```

> 🛑 `--force` 대신 **`--force-with-lease`** 사용 — 다른 사람이 같은 브런치에 푸시한 변경을 실수로 덮어쓰지 않음.

---

## 5. PR 생성

```bash
# 마지막 push
git push -u team feat/<영역>-<주제>

# PR 생성 (gh CLI)
gh pr create \
  --base develop \
  --title "feat(mobile): 메인 대시보드 5탭 셸 추가" \
  --body-file .github/PULL_REQUEST_TEMPLATE.md \
  --label "area: mobile,size: M"

# 또는 GitHub 웹에서: Compare & pull request
```

이후 [`PR_GUIDELINES.md`](./PR_GUIDELINES.md) 따라 진행.

---

## 6. PR 리뷰 사이클

```
[리뷰어 코멘트] 
   ↓
[로컬에서 수정]
   ↓
git add ...
git commit -m "fix(mobile): 리뷰 반영 — 카드 spacing 조정"
   ↓
git push team feat/<영역>-<주제>
   ↓
[리뷰어 재확인 → Approve]
   ↓
[Squash and Merge → develop에 단일 커밋 생성]
   ↓
[원격 브런치 자동 삭제]
   ↓
git checkout main && git branch -D feat/<영역>-<주제>  # 로컬도 정리
```

---

## 7. 머지 후 정리

```bash
# develop 동기화
git checkout main          # 또는 본인이 항상 머무는 브런치
git fetch team
git pull team develop      # (develop을 베이스로 작업하는 흐름이면)

# 이미 머지된 로컬 브런치 정리
git branch --merged | grep -v '\*\|main\|develop' | xargs -n 1 git branch -D
```

---

## 8. 통합 테스트 (develop 머지 직후)

develop은 통합 테스트의 장이므로, 머지 직후:

1. **CI 자동 실행** — `.github/workflows/ci.yml`이 develop 변경마다 실행
2. **작성자 책임 확인** — 본인 PR 머지 후 CI가 빨간색이면 즉시 후속 조치
3. **다른 영역 영향 점검** — 모바일↔백엔드, 백엔드↔DB 같은 경계 변경은 통합 테스트 시나리오로 확인

---

## 9. develop → main 정기 릴리스

매주 금요일 17:00 (또는 합의된 시점):

```bash
# 1) develop 최신화 + CI green 확인
git fetch team
gh run list --branch develop --limit 5  # 최근 CI 상태

# 2) 릴리스 PR 생성
gh pr create --base main --head develop \
  --title "release: v0.x.y" \
  --body "## 포함된 변경\n- ...\n\n## 검증\n- [ ] 통합 테스트 green\n- [ ] 수동 시나리오 OK"

# 3) 2명 승인 후 Merge commit (no-ff)

# 4) 태그 부여
git checkout main && git pull team main
git tag -a v0.x.y -m "release v0.x.y"
git push team v0.x.y
```

---

## 10. 멘탈 모델

```
┌─────────────────────────────────────────────────────┐
│  main          ─●────────────●──────────●─────  v0.3 │
│                  ↑            ↑          ↑           │
│                merge        merge      merge         │
│  develop ──●─●─●──●─●─●──●──●─●─●─●──●──●─●─●─●─    │
│            ↑   ↑     ↑      ↑   ↑     ↑   ↑         │
│           PR  PR    PR     PR  PR    PR  PR         │
│  feat/*  ──●──┘     │      │   │     │   │          │
│  feat/*  ─────●─────┘      │   │     │   │          │
│  fix/*   ─────────────●────┘   │     │   │          │
│  feat/*  ────────────────●─●───┘     │   │          │
│  chore/* ──────────────────────●─────┘   │          │
│  feat/*  ────────────────────────●─●─────┘          │
└─────────────────────────────────────────────────────┘
```

---

## 11. 한 줄 명령어 모음

```bash
# 새 작업 시작
git fetch team && git checkout -b feat/<영역>-<주제> team/develop

# develop 최신화
git fetch team && git rebase team/develop

# 안전한 강제 푸시
git push team feat/<영역>-<주제> --force-with-lease

# PR 생성
gh pr create --base develop --fill

# CI 상태
gh pr checks

# 머지된 로컬 브런치 청소
git branch --merged | grep -vE '\*|main|develop' | xargs -n 1 git branch -D
```

---

## 관련 문서

- [`BRANCH_STRATEGY.md`](./BRANCH_STRATEGY.md)
- [`COMMIT_CONVENTION.md`](./COMMIT_CONVENTION.md)
- [`PR_GUIDELINES.md`](./PR_GUIDELINES.md)
- [`MERGE_AND_CONFLICT.md`](./MERGE_AND_CONFLICT.md)
- [`LOCAL_SETUP.md`](./LOCAL_SETUP.md)
