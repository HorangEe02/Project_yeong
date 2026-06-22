# 🌳 브런치 전략 (Branch Strategy)

> Lemon Aid는 **Git Flow의 경량 변형**을 사용합니다. `main` = 배포, `develop` = 통합, 나머지는 단명(短命) 작업 브런치입니다.

---

## 1. 브런치 계층

```
main           ← 배포 가능한 안정 버전 (protected)
└── develop    ← 통합/테스트 브런치 (protected, default for PRs)
    ├── feat/<영역>-<이름>       기능 추가
    ├── fix/<영역>-<이름>        버그 수정
    ├── chore/<영역>-<이름>      빌드·도구·설정
    ├── docs/<영역>-<이름>       문서
    ├── refactor/<영역>-<이름>   리팩토링 (동작 동일)
    ├── test/<영역>-<이름>       테스트만 추가/변경
    ├── perf/<영역>-<이름>       성능 개선
    └── hotfix/<영역>-<이름>     main에서 분기되는 긴급 수정 (예외)
```

| 브런치 종류 | 기반 | 머지 대상 | 머지 방식 | 보호 |
|------------|------|-----------|----------|------|
| `main` | — | — | — | ✅ protected |
| `develop` | `main` | `main` (정기 릴리스) | merge commit | ✅ protected |
| `feat/*` `fix/*` `chore/*` `docs/*` `refactor/*` `test/*` `perf/*` | `develop` | `develop` | **Squash** | ❌ |
| `hotfix/*` | `main` | `main` + `develop` | merge commit | ❌ |

---

## 2. 영역(scope) 표준 목록

PR/커밋의 `<영역>`은 아래 목록 중에서 선택합니다. (새 영역이 필요하면 PR로 이 목록에 추가)

| 영역 | 설명 | 대표 디렉토리 |
|------|------|---------------|
| `mobile` | Flutter 앱 (UI, 상태, 라우팅) | `mobile/` |
| `backend` | FastAPI 서버 | `backend/` |
| `ai` | Claude/LLM 에이전트 | `backend/.../ai/`, `ai-agent/` |
| `ocr` | OCR · Vision · 영양 라벨 분석 | `backend/.../ocr/`, `scripts/` |
| `db` | 스키마·마이그레이션·시드 | `backend/.../db/`, `docker-compose.yml` |
| `auth` | 로그인·OAuth·세션 | `backend/.../auth/`, `mobile/.../auth/` |
| `ux` | 디자인 시스템·디자인 토큰 | `mobile/.../theme/`, `assets/` |
| `infra` | CI/CD·Docker·배포 | `.github/`, `docker-compose*.yml` |
| `docs` | 문서·기획·가이드 | `docs/`, `PROJECT_GUIDE.md` |
| `team` | 협업 도구·이 폴더 | `docs/team-collaboration/` |
| `test` | 통합 테스트 인프라 | `tests/` |
| `data` | 데이터셋·KDRIs·식약처 | `data/` |

---

## 3. 브런치 이름 규칙

```
<type>/<scope>-<kebab-case-subject>
```

**예시 (OK)**

- `feat/mobile-dashboard-5tab-shell`
- `feat/ai-agent-tool-calling`
- `fix/ocr-naver-chronic-snapshot-mismatch`
- `chore/infra-python-3.13-bump`
- `docs/team-develop-rules`
- `refactor/backend-supplement-service-split`
- `test/backend-meal-integration`

**예시 (NG)**

- `feature/mobile_dashboard` (type 표기 오류, snake_case)
- `yeong-tech` (영역·주제 식별 불가) ← 현재 브런치 중 일부가 이 패턴
- `kakao ver3` (공백, 의미 없는 버전 표기)
- `taedong-design` (작업자 이름만 들어가면 안 됨)

> 기존의 작업자 이름 기반 브런치(`yeong-tech`, `taedong-design`, `sunghoon-database` 등)는 `develop` 통합 이후 `feat/<영역>-<주제>` 패턴의 새 브런치로 재분기합니다.

---

## 4. 브런치 수명

- **단명 원칙**: feature 브런치는 **3–7일 안에 머지**되도록 작게 분할합니다.
- 한 주 이상 지연되면:
  - 매일 `git fetch team && git rebase team/develop`
  - 작업 분할(PR을 여러 개로 쪼개기)
- 머지된 브런치는 GitHub에서 **즉시 삭제**합니다 (Settings → Automatically delete head branches 권장).

---

## 5. develop ↔ main 정기 통합

| 시점 | 작업 |
|------|------|
| 매주 화 17:00 | `develop` → `main` 후보 점검 (모든 통합 테스트 green) |
| 매주 금 17:00 | release 태그 부여 후 `main` 머지 (`v0.x.y`) |
| 긴급 | `hotfix/*`는 `main`에서 분기 → `main` 머지 → `develop`에 cherry-pick |

---

## 6. 보호 규칙 (Branch Protection)

`main`과 `develop`에는 다음 규칙을 적용합니다 (GitHub Settings → Branches):

### main
- ✅ Require a pull request before merging
- ✅ Require approvals: **2명**
- ✅ Dismiss stale reviews on new commits
- ✅ Require status checks to pass (CI: `pre-commit`, `test`, `lint`)
- ✅ Require linear history
- ✅ Restrict who can push: 메인테이너만
- ❌ Allow force pushes
- ❌ Allow deletions

### develop
- ✅ Require a pull request before merging
- ✅ Require approvals: **1명**
- ✅ Require status checks to pass (CI: `pre-commit`, `test`)
- ✅ Require conversation resolution before merging
- ❌ Allow force pushes
- ❌ Allow deletions

---

## 7. 한눈에 보기

```
[작업 시작]
   └─ git fetch team
   └─ git checkout -b feat/<영역>-<주제> team/develop
   └─ <작업 + 커밋>
   └─ git push team feat/<영역>-<주제>
   └─ Pull Request → develop
        └─ CI green + 리뷰 1명 승인
        └─ Squash and Merge
        └─ 브런치 자동 삭제
[정기 릴리스]
   └─ develop → main (매주 금)
        └─ 태그 v0.x.y
```

---

## 관련 문서

- [`COMMIT_CONVENTION.md`](./COMMIT_CONVENTION.md) — 커밋 메시지 규칙
- [`PR_GUIDELINES.md`](./PR_GUIDELINES.md) — PR 작성·머지
- [`DEVELOP_WORKFLOW.md`](./DEVELOP_WORKFLOW.md) — 일상 워크플로우
