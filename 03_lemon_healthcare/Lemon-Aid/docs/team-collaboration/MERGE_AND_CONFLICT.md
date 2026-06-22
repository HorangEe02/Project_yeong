# ⚔️ 머지 & 충돌 해결 가이드

> develop은 **모든 팀원의 변경이 모이는 지점**입니다. 충돌은 자연스러운 것 — 안전하게 해결하는 법.

---

## 1. 기본 정책

| 상황 | 정책 |
|------|------|
| **feature → develop** | PR + **Squash Merge** |
| **develop → main** | PR + **Merge commit (no-ff)** |
| **hotfix → main** | PR + **Merge commit** |
| **hotfix → develop** | **Cherry-pick** |
| **feature 브런치 최신화** | `rebase team/develop` (merge 금지) |
| **develop 최신화 (다른 PR 머지 후)** | `rebase` |

> ❌ **feature 브런치에서 `git merge develop` 하지 마세요** — 머지 커밋이 PR에 섞여 리뷰가 어려워집니다.

---

## 2. develop 최신화 — Rebase

가장 흔한 시나리오: 본인 PR을 작성하는 동안 develop에 다른 PR이 머지되었을 때.

```bash
# 1) 작업 브런치에서
git fetch team

# 2) develop 위로 rebase
git rebase team/develop

# 3) 충돌이 없으면 완료. 있으면 다음 단계로.
```

---

## 3. 충돌 해결 — 단계별

### Step 1. 충돌 파일 식별

```bash
git status
# both modified: backend/.../service.py
# both added:    docs/team-collaboration/README.md
```

### Step 2. 파일 열어서 충돌 마커 찾기

```python
<<<<<<< HEAD (current change — develop의 코드)
def evaluate(snapshot):
    return new_evaluator(snapshot)
||||||| (ancestor — 공통 조상, zdiff3 설정 시 표시)
def evaluate(snapshot):
    return legacy_evaluator(snapshot)
=======
def evaluate(snapshot):
    return llm_aware_evaluator(snapshot, locale="ko")
>>>>>>> feat/ocr-llm-aware (incoming change — 내 브런치)
```

### Step 3. 어느 쪽을 살릴지 결정

- **둘 다 필요** → 코드 직접 작성 (가장 흔함)
- **develop 쪽** → 내 변경을 버림
- **내 쪽** → develop 변경을 버림
- **로직 충돌** → 작성자와 짧게 의논 (Slack 1분)

### Step 4. 마커 제거하고 저장

```python
def evaluate(snapshot):
    # 둘 다 살리기
    if snapshot.locale == "ko":
        return llm_aware_evaluator(snapshot, locale="ko")
    return new_evaluator(snapshot)
```

### Step 5. 해결 마킹 + rebase 진행

```bash
git add backend/.../service.py
git rebase --continue
```

### Step 6. 모든 커밋이 처리될 때까지 반복

여러 커밋이 있으면 Step 1-5를 각 커밋마다 반복.

### Step 7. 테스트 + 푸시

```bash
# 로컬 검증
pre-commit run --all-files
pytest tests/ -x

# 안전한 강제 푸시
git push team feat/<영역>-<주제> --force-with-lease
```

---

## 4. 충돌 해결 도구

### CLI: `git mergetool`

```bash
git config --global merge.tool vimdiff   # 또는 vscode, meld 등
git mergetool
```

### VS Code / Cursor

- 충돌 파일을 열면 상단에 `Accept Current` / `Accept Incoming` / `Accept Both` 버튼
- "Merge in Editor" 클릭하면 3-pane 머지 에디터

### JetBrains

- VCS → Resolve Conflicts → 시각적 3-pane 머지

---

## 5. rebase 중단 / 되돌리기

### 잠시 멈추고 작업 저장

```bash
git rebase --abort                 # rebase 완전 취소, 원상태로
git stash push -m "wip"            # 변경을 임시 보관
git stash pop                       # 다시 꺼냄
```

### 모든 게 꼬였을 때 — 리플로그 활용

```bash
git reflog                          # 최근 HEAD 이동 기록
# 예: HEAD@{5}: rebase 시작 직전
git reset --hard HEAD@{5}
```

> 🛟 **reflog**는 90일간 보관됩니다. 잘못된 force-push 후에도 복구 가능.

---

## 6. develop ↔ feature 흐름이 꼬였을 때

### 시나리오: 실수로 feature에서 develop을 merge 했음

```bash
# 머지 커밋을 되돌리고 rebase로 다시
git reset --hard team/<내브런치>@{원격마지막}  # 원격 상태로 리셋
git fetch team
git rebase team/develop
```

### 시나리오: 동료가 같은 브런치에서 작업 중이었음

`--force-with-lease`가 거부하면:

```bash
git fetch team
git rebase team/<내브런치>           # 동료 변경 먼저 합치고
git rebase team/develop              # develop도 합치고
git push team <내브런치> --force-with-lease
```

---

## 7. Squash 머지 후 develop 동기화

Squash로 머지되면 feature 브런치의 커밋 해시는 develop과 다릅니다. 다음 작업을 develop에서 새로 분기하면 안전:

```bash
git checkout main          # 또는 base 브런치
git fetch team
git pull team develop      # develop 최신화
# 다음 작업
git checkout -b feat/<영역>-<다음주제> team/develop
```

머지된 로컬 브런치 정리:

```bash
git branch -D feat/<영역>-<이전주제>
```

---

## 8. 큰 충돌이 예상될 때 — 사전 조치

1. **PR을 작게** — [`PR_GUIDELINES.md`](./PR_GUIDELINES.md) 사이즈 가이드
2. **자주 rebase** — 매일 `git sync` (별칭 권장)
3. **영역 경계 명확히** — `feat(backend)`와 `feat(mobile)`이 같은 파일을 건드리지 않게
4. **사전 협의** — 같은 모듈 변경이 겹치면 Slack `#dev`에서 순서 협의
5. **드래프트 PR 일찍** — 큰 변경은 Draft PR로 진행 상황 노출

---

## 9. 머지 후 회복 — 머지 커밋 되돌리기 (revert)

이미 develop에 머지된 PR이 문제를 일으킬 때:

```bash
# GitHub UI: PR 페이지 → "Revert" 버튼 → 자동으로 revert PR 생성
# 또는 CLI
git fetch team
git checkout -b revert/feat-mobile-dashboard team/develop
git revert -m 1 <머지커밋해시>
git push team revert/feat-mobile-dashboard
gh pr create --base develop --title "revert: feat(mobile) 대시보드 5탭 셸 (#42)"
```

> `-m 1` — Squash 머지에는 불필요. Merge commit (--no-ff)에서만 사용.

---

## 10. 충돌 예방 체크리스트

- [ ] 매일 시작 전 `git sync` (= `git fetch team && git rebase team/develop`)
- [ ] PR은 작게 (≤ 500줄 권장)
- [ ] 같은 모듈을 건드리는 PR끼리 머지 순서 협의
- [ ] 머지 직전에 다시 한 번 `git fetch team && git rebase team/develop`
- [ ] Draft PR로 작업 노출 — 사전 코디네이션 가능
- [ ] 큰 리팩토링은 별도 PR (`refactor: ...`) → 머지 → 그 위에 feature PR

---

## 11. 위험한 명령 — 절대 금지 / 제한

| 명령 | 정책 |
|------|------|
| `git push --force` (lease 없이) | ❌ 절대 금지 — `--force-with-lease`만 사용 |
| `git push team develop` (직접) | ❌ 보호 규칙이 차단 |
| `git push team main` | ❌ 보호 규칙이 차단 |
| `git reset --hard <원격>`  | ⚠️ 본인 로컬 브런치에서만 |
| `git rebase main` (feature에서) | ❌ develop 위로 rebase |
| `git checkout .` / `git restore .` | ⚠️ 변경 영구 손실 — 사용 전 `git stash` |
| `git clean -fd` | ⚠️ untracked 영구 삭제 — 사용 전 확인 |

---

## 관련 문서

- [`DEVELOP_WORKFLOW.md`](./DEVELOP_WORKFLOW.md)
- [`PR_GUIDELINES.md`](./PR_GUIDELINES.md)
- [`LOCAL_SETUP.md`](./LOCAL_SETUP.md)
