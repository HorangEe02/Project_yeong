# 🚦 CI / CD 게이트

> develop으로 가는 모든 PR은 자동 게이트를 통과해야 합니다. 로컬 pre-commit이 1차 방어선, GitHub Actions가 2차.

---

## 1. 게이트 개요

| 게이트 | 위치 | 차단 조건 | 우회 가능? |
|--------|------|-----------|-----------|
| pre-commit | 로컬 | trailing-whitespace, EOF, merge-conflict, large-files, private-key, sync-guide | `--no-verify` (금지) |
| commit-msg | 로컬 | Conventional Commits 형식 위반 | `--no-verify` (금지) |
| GitHub Actions: lint | CI | black/ruff 실패 | 불가 |
| GitHub Actions: test | CI | 단위/통합 테스트 실패 | 불가 |
| GitHub Actions: build | CI | Flutter/Docker 빌드 실패 | 불가 |
| GitHub Actions: security | CI | secret 누출 감지 | 불가 |
| Branch protection | GitHub | 보호 규칙 위반 | 불가 (관리자도 우회 금지) |

> ❌ **`git commit --no-verify` 금지** — 게이트를 우회한 흔적이 PR에 남으면 변경 요청 대상.

---

## 2. pre-commit (`.pre-commit-config.yaml`)

`main` 브런치의 현재 설정 (그대로 사용):

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: trailing-whitespace
        exclude: \.md$
      - id: end-of-file-fixer
      - id: check-merge-conflict
      - id: check-added-large-files
        args: ["--maxkb=2000"]
      - id: detect-private-key

  - repo: local
    hooks:
      - id: sync-guide
        name: sync guide.html with PROJECT_GUIDE.md
        entry: python scripts/sync_guide.py
        language: system
        files: '^(PROJECT_GUIDE\.md|guide\.html|scripts/sync_guide\.py)$'
        pass_filenames: false
        stages: [commit]
```

### 권장 추가 (develop 통합 시 PR로 제안)

```yaml
  # Python 포매팅 + 린트
  - repo: https://github.com/psf/black
    rev: 24.10.0
    hooks:
      - id: black
        language_version: python3.13

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.6.9
    hooks:
      - id: ruff
        args: [--fix]

  # Conventional Commits 검증
  - repo: https://github.com/commitizen-tools/commitizen
    rev: v3.29.1
    hooks:
      - id: commitizen
        stages: [commit-msg]

  # YAML/JSON 포매팅
  - repo: https://github.com/pre-commit/mirrors-prettier
    rev: v3.1.0
    hooks:
      - id: prettier
        types_or: [yaml, json, markdown]
```

설치:

```bash
pre-commit install --hook-type pre-commit --hook-type commit-msg --hook-type pre-push
pre-commit autoupdate
```

---

## 3. GitHub Actions 워크플로

`.github/workflows/ci.yml` (예시 — 각 영역에 맞게 조정):

```yaml
name: CI

on:
  pull_request:
    branches: [develop, main]
  push:
    branches: [develop, main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - run: pip install pre-commit
      - run: pre-commit run --all-files

  backend-test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_PASSWORD: test
        ports: ["5432:5432"]
        options: >-
          --health-cmd pg_isready --health-interval 10s --health-timeout 5s --health-retries 5
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - run: pip install -r backend/requirements.txt -r backend/requirements-dev.txt
      - run: pytest backend/tests --cov --cov-report=xml
      - uses: codecov/codecov-action@v4
        if: always()

  mobile-build:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v4
      - uses: subosito/flutter-action@v2
        with:
          flutter-version: "3.24.x"
      - run: cd mobile && flutter pub get
      - run: cd mobile && flutter analyze
      - run: cd mobile && flutter test
      - run: cd mobile && flutter build apk --debug

  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

---

## 4. CI 실패 디버깅

### Step 1. 실패한 job 확인

```bash
gh pr checks                 # PR의 모든 체크 요약
gh run view --log-failed     # 실패 로그
gh run watch                 # 진행 중인 실행 watch
```

### Step 2. 로컬에서 재현

| CI job | 로컬 명령 |
|--------|-----------|
| lint | `pre-commit run --all-files` |
| backend-test | `pytest backend/tests --cov` |
| mobile-build | `cd mobile && flutter analyze && flutter test` |
| security | `gitleaks detect --no-git` |

### Step 3. 고친 뒤 push

```bash
git add <고친 파일>
git commit -m "fix(ci): black 포매팅 적용"
git push team feat/<영역>-<주제>
# CI 자동 재실행
```

---

## 5. 필수 status checks (Branch protection)

`develop`에 다음 체크가 통과해야 머지 가능:

- `lint`
- `backend-test`
- `mobile-build`
- `security`

`main`은 추가로:

- 코드 커버리지 ≥ 70% (선택)
- 통합 테스트 (`integration-test` job)

---

## 6. CI 캐시 전략

빌드 속도를 위해 캐시 사용:

```yaml
      - uses: actions/cache@v4
        with:
          path: ~/.cache/pip
          key: pip-${{ hashFiles('backend/requirements*.txt') }}
          restore-keys: pip-

      - uses: actions/cache@v4
        with:
          path: |
            ~/.gradle/caches
            ~/.gradle/wrapper
          key: gradle-${{ hashFiles('mobile/android/**/*.gradle*') }}
```

캐시가 꼬일 때:

- GitHub UI → Actions → Caches → 해당 캐시 삭제
- 또는 `key`에 `v2` 같은 suffix 추가

---

## 7. 비밀값 관리

| 위치 | 용도 |
|------|------|
| GitHub Secrets (Settings → Secrets) | CI에서 쓰는 API 키, DB 비번 |
| `.env` (로컬) | 개발자 본인 PC 환경변수 |
| `.env.example` (커밋) | 키 이름·예시값만, 실제 값 X |
| 1Password / Bitwarden | 팀 공유 비밀 |

❌ 절대 금지:
- 코드에 하드코딩
- `.env` 커밋
- PR 본문에 비밀값 첨부

---

## 8. 자주 발생하는 CI 실패와 해법

### ❌ `trailing-whitespace` failed
```bash
pre-commit run trailing-whitespace --all-files
git add -A && git commit -m "style: trim trailing whitespace"
```

### ❌ `check-added-large-files` failed (2MB+)
- 파일이 정말 필요한지 확인
- 데이터셋이면 → `data/` 디렉토리 + Git LFS
- 빌드 산출물이면 → `.gitignore`에 추가
- 스크린샷이면 → 압축

### ❌ `detect-private-key` failed
- 진짜 키면 → **즉시 키 회전** + `git filter-repo`로 히스토리 제거
- 예시/테스트용 키면 → 파일명을 `*.example` 또는 exclude 패턴 추가

### ❌ `black` formatting failed
```bash
pip install black==24.10.0
black backend/
git add -A && git commit -m "style(backend): black 포매팅 적용"
```

### ❌ `pytest` failed
- 로컬에서 같은 명령 재현
- 환경변수 누락 확인 (`.env.example`)
- 의존성 버전 확인 (`pip freeze | grep <패키지>`)

### ❌ `flutter analyze` failed
- IDE의 lint 무시 설정이 CI와 다름 — `analysis_options.yaml`이 권위
- `import` 순서, unused import 자주 발생

### ❌ `gitleaks` failed
- 정말 키가 누출되었으면 → 회전 후 히스토리 제거
- false positive면 → `.gitleaks.toml`에 allowlist

---

## 9. 로컬 빠른 검증 스크립트

`scripts/preflight.sh` (권장 — 없으면 PR로 추가):

```bash
#!/usr/bin/env bash
set -e
echo "▶ pre-commit"
pre-commit run --all-files

echo "▶ backend tests"
pytest backend/tests -x

echo "▶ mobile analyze"
(cd mobile && flutter analyze)

echo "✓ all checks passed"
```

PR 올리기 전:

```bash
bash scripts/preflight.sh
```

---

## 10. 정기 유지보수

| 주기 | 작업 |
|------|------|
| 매주 | pre-commit autoupdate (`pre-commit autoupdate`) |
| 매월 | GitHub Actions 버전 점검 (`actions/*@vN`) |
| 분기 | 의존성 보안 감사 (`pip-audit`, `flutter pub outdated`) |
| 분기 | CI 시간 점검 — 캐시·병렬화 |

---

## 관련 문서

- [`LOCAL_SETUP.md`](./LOCAL_SETUP.md)
- [`PR_GUIDELINES.md`](./PR_GUIDELINES.md)
- [`CODE_REVIEW_CHECKLIST.md`](./CODE_REVIEW_CHECKLIST.md)
