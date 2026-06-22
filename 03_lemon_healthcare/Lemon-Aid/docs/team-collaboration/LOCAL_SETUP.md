# 🛠️ 로컬 환경 설정 — 각자 한 번씩

> 이 문서 그대로 따라 하면 **커밋·푸시 규칙이 로컬에서 자동 적용**됩니다. 첫 설정에 약 10-15분 걸립니다.

---

## 1. 최초 설치 (한 번만)

### 1-1. 저장소 클론 및 remote 확인

```bash
git clone https://github.com/Lemon-Aid-KDT/Lemon-sin.git
cd Lemon-sin

# remote 확인 — team 또는 origin이 Lemon-sin을 가리키면 OK
git remote -v
```

원격 이름은 팀 컨벤션에 따라 `team` 또는 `origin`. 본 문서는 **`team`** 으로 가정 — 본인 환경에 맞게 치환하세요.

### 1-2. Python 3.13 + 가상환경

```bash
# Python 3.13 확인
python3 --version  # 3.13.x

# 가상환경
python3 -m venv .venv
source .venv/bin/activate  # zsh/bash
# Windows: .venv\Scripts\activate

# 의존성 설치
pip install -U pip
pip install -r backend/requirements.txt    # 또는 본인 영역
pip install pre-commit
```

### 1-3. pre-commit 설치 (필수)

```bash
pre-commit install                    # commit hook
pre-commit install --hook-type commit-msg   # 커밋 메시지 검증 hook
pre-commit install --hook-type pre-push     # push 전 게이트

# 첫 실행 — 모든 파일 검증
pre-commit run --all-files
```

> 🎯 이 단계가 빠지면 CI가 빨간색이 됩니다. **반드시 실행하세요**.

### 1-4. `.env` 파일 준비

```bash
# backend
cp backend/.env.example backend/.env
# mobile (있는 경우)
cp mobile/.env.example mobile/.env
```

`.env`는 절대 커밋하지 않습니다 (`.gitignore`에 포함됨).

### 1-5. 모바일 (Flutter) 환경

```bash
cd mobile
flutter pub get
flutter doctor
# iOS는 별도 설정 — 해당 가이드 참조
```

---

## 2. Git 전역 설정 (권장)

```bash
# 사용자 정보
git config --global user.name "Your Name"
git config --global user.email "you@example.com"

# 라인 엔딩 (macOS / Linux)
git config --global core.autocrlf input
git config --global core.eol lf

# 안전한 push 기본값
git config --global push.default current
git config --global push.followTags true

# rebase 우선 정책
git config --global pull.rebase true
git config --global rebase.autoStash true

# 충돌 시 diff3 표시 (혼동 줄임)
git config --global merge.conflictstyle zdiff3
```

---

## 3. Git 별칭 (Aliases) — 생산성

`~/.gitconfig` 또는 프로젝트 `.git/config`에 추가:

```ini
[alias]
    # 상태/로그
    st = status -sb
    lg = log --oneline --graph --decorate -20
    last = log -1 HEAD --stat

    # 흐름
    sync = !git fetch team && git rebase team/develop
    co = checkout
    cob = checkout -b

    # 안전한 force-push
    pushf = push --force-with-lease

    # develop 브런치에서 새 작업
    new = "!f() { git fetch team && git checkout -b $1 team/develop; }; f"

    # 머지된 브런치 청소
    cleanup = "!git branch --merged | grep -vE '\\*|main|develop' | xargs -n 1 git branch -d"
```

사용 예:

```bash
git new feat/mobile-supplement-detail   # develop에서 분기
git sync                                 # develop 최신화
git pushf                                # 안전한 강제 푸시
git cleanup                              # 로컬 정리
```

---

## 4. Conventional Commits 검증 hook (commit-msg)

프로젝트 루트에 `.git/hooks/commit-msg`가 없다면 다음 파일을 생성하세요. (pre-commit `commit-msg` hook이 이미 처리한다면 생략)

`scripts/git-hooks/commit-msg.sh`:

```bash
#!/usr/bin/env bash
# Conventional Commits 형식 검증
COMMIT_MSG_FILE="$1"
FIRST_LINE=$(head -n1 "$COMMIT_MSG_FILE")

PATTERN='^(feat|fix|docs|style|refactor|perf|test|chore|ci|build|revert|data|ops)(\([a-z0-9-]+\))?: .{1,72}$'

if ! echo "$FIRST_LINE" | grep -qE "$PATTERN"; then
  echo ""
  echo "✖  Conventional Commits 형식이 아닙니다."
  echo "   형식: <type>(<scope>): <subject>"
  echo "   허용 type: feat fix docs style refactor perf test chore ci build revert data ops"
  echo "   예: feat(mobile): 대시보드 5탭 셸 추가"
  echo ""
  echo "   현재 메시지: $FIRST_LINE"
  exit 1
fi
exit 0
```

설치:

```bash
chmod +x scripts/git-hooks/commit-msg.sh
ln -sf ../../scripts/git-hooks/commit-msg.sh .git/hooks/commit-msg
```

---

## 5. pre-commit 설정 확인

저장소 루트의 `.pre-commit-config.yaml`에 다음 hook이 활성화되어 있어야 합니다 (이미 main에 존재):

- `trailing-whitespace`
- `end-of-file-fixer`
- `check-merge-conflict`
- `check-added-large-files` (--maxkb=2000)
- `detect-private-key`
- `sync-guide` (PROJECT_GUIDE.md → guide.html)

추가 권장 (없으면 PR로 추가):

- `black` (Python 포매터)
- `ruff` (Python 린터)
- `mypy` (선택)
- `commitizen` (커밋 메시지 검증, 위 hook 대체 가능)

---

## 6. GitHub CLI (gh) 설치 — PR 생성/리뷰

```bash
# macOS
brew install gh

# 인증
gh auth login
```

자주 쓰는 명령:

```bash
gh pr create --base develop --fill
gh pr checks                # CI 상태
gh pr view --web            # PR 페이지 열기
gh pr list --author "@me"   # 내 PR 목록
```

---

## 7. IDE 통합 (선택, 권장)

### VS Code / Cursor

`settings.json`:

```json
{
  "files.eol": "\n",
  "files.insertFinalNewline": true,
  "files.trimTrailingWhitespace": true,
  "editor.formatOnSave": true,
  "python.formatting.provider": "black",
  "python.linting.ruffEnabled": true,
  "git.confirmSync": false,
  "git.autofetch": true,
  "git.enableSmartCommit": false,
  "git.allowForcePush": true
}
```

### JetBrains (IntelliJ / PyCharm / Android Studio)

- Settings → Editor → Code Style → Line separator: `Unix and macOS (\n)`
- Settings → Version Control → Git → Update method: `Rebase`
- Conventional Commits 플러그인 설치 (commit dialog에서 자동완성)

---

## 8. 설치 검증 체크리스트

설치 후 아래를 순서대로 실행하면 ✅:

```bash
# 1) pre-commit 작동
echo "test " > /tmp/x && pre-commit run --files /tmp/x trailing-whitespace
# → 결과: trailing-whitespace .................... Passed/Failed

# 2) 커밋 메시지 검증
echo "bad commit" > /tmp/msg && bash scripts/git-hooks/commit-msg.sh /tmp/msg
# → 결과: ✖  Conventional Commits 형식이 아닙니다.

echo "feat(team): 로컬 설정 가이드 추가" > /tmp/msg && bash scripts/git-hooks/commit-msg.sh /tmp/msg
# → 결과: (출력 없음, exit 0)

# 3) gh 인증
gh auth status

# 4) Python/Flutter
python3 --version
flutter --version
```

---

## 9. 자주 만나는 문제

### Q. `pre-commit install` 후에도 hook이 안 돕니다
- `.git/hooks/pre-commit`이 존재하는지 확인 (`ls -la .git/hooks/`)
- 다른 hook 매니저(husky 등)가 덮어쓰지 않는지 확인

### Q. 커밋 메시지가 한글이면 깨져요
- Git 인코딩 설정:
  ```bash
  git config --global i18n.commitEncoding utf-8
  git config --global i18n.logOutputEncoding utf-8
  ```
- 터미널이 UTF-8인지 확인

### Q. Windows에서 hook이 실행되지 않아요
- Git Bash 또는 WSL 사용 권장
- `chmod +x` 대신 `git update-index --chmod=+x scripts/git-hooks/*.sh`

### Q. macOS에서 `detect-private-key`가 SSH 공개키도 잡아요
- `.pre-commit-config.yaml`에서 해당 파일 exclude 패턴 추가

---

## 10. 미리 알아두면 좋은 것

- `.env`는 **절대로** add/commit 하지 않기 — `git add -p` 사용 권장
- 대용량 파일(2MB+)은 LFS 또는 외부 스토리지 — `check-added-large-files` hook이 차단
- 비밀키·토큰은 환경변수 또는 `.env`만 — `detect-private-key` hook이 차단
- guide.html은 직접 수정하지 말고 PROJECT_GUIDE.md → 자동 동기화

---

## 관련 문서

- [`COMMIT_CONVENTION.md`](./COMMIT_CONVENTION.md)
- [`CI_CD_GATES.md`](./CI_CD_GATES.md)
- [`DEVELOP_WORKFLOW.md`](./DEVELOP_WORKFLOW.md)
