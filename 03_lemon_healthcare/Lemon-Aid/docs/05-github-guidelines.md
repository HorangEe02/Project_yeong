# 05. GitHub 협업 규칙 (GitHub Collaboration Guidelines)

> **문서 정보**
> 버전: v1.2 | 작성일: 2026-05-03 | 수정일: 2026-05-21 | 상태: 운영 중 | 작성자: 경북대학교 AI/빅데이터 전문가 양성 과정 — Lemon Aid팀

> ⚠️ **이 문서는 legacy detailed 레퍼런스입니다.** 2026-05-21부터 신규 협업 결정은 [`docs/team-collaboration/`](./team-collaboration/README.md) 폴더가 **우선**합니다. 두 문서가 충돌할 경우 team-collaboration 쪽이 정본(source of truth)입니다.

---

## 📋 한 줄 요약

> 학생 팀 + 발주처 협업 + 다양한 GitHub 숙련도를 모두 고려해, **충돌 없이 코딩하고 발표 시 "협업 체계까지 갖춘 팀"이라는 인상을 주는 표준 + CI + Branch Protection + 린터** 통합 규칙.
> **2026-05-21 업데이트**: `develop` 통합 브랜치를 정식 도입하고, 신규 작업은 단명 `<type>/<scope>-<주제>` 패턴으로 전환합니다. 기존 `<member>-<part>` 고정 브랜치는 점진적으로 마이그레이션합니다.

---

## 목차
- [1. 폴더 구조 표준](#1-폴더-구조-표준)
- [2. 브랜치 전략 (Git Flow 변형)](#2-브랜치-전략-git-flow-변형)
- [3. 커밋 메시지 컨벤션 (Conventional Commits)](#3-커밋-메시지-컨벤션-conventional-commits)
- [4. Pull Request (PR) 규칙](#4-pull-request-pr-규칙)
- [5. Issue 관리](#5-issue-관리)
- [6. .gitignore 표준](#6-gitignore-표준)
- [7. 코드 린터·포매터 설정](#7-코드-린터포매터-설정)
- [8. GitHub Actions CI/CD](#8-github-actions-cicd)
- [9. Branch Protection Rules](#9-branch-protection-rules)
- [10. Secret Management](#10-secret-management)
- [11. 팀원 온보딩 가이드 (Day 1)](#11-팀원-온보딩-가이드-day-1)

---

## 1. 폴더 구조 표준

> 실제 Git repository root는 `/Users/yeong/99_me/00_github`이며, GitHub Actions, CODEOWNERS, PR/Issue template는 repository root의 `.github/`에서 관리한다.

```
03_lemon_healthcare/
└── yeong-Lemon-Aid/                 # Lemon Aid 제품 코드·문서·산출물 루트
    ├── README.md
    ├── docs/                        # 팀 공통 문서 루트
    │   ├── 01-project-overview.md   # 팀 공통 프로젝트 요약
    │   ├── 03-project-intent.md     # 팀 공통 기획 의도·포지셔닝 요약
    │   ├── 05-github-guidelines.md  # 공통 GitHub 협업 규칙
    │   ├── 06-tech-stack.md         # 팀 공통 기술 구조·검증 요약
    │   ├── 10-compliance-checklist.md # 팀 공통 컴플라이언스 가드레일
    │   ├── README.md                # 문서 폴더 안내
    │   ├── Nutrition-docs/          # 영양제·영양 분석 담당 문서
    │   │   ├── 01-project-overview.md
    │   │   ├── 02-background-problem.md
    │   │   ├── ...
    │   │   ├── 42-prescription-lab-ocr-intake-design-plan.md
    │   │   ├── dev-guides/          # Nutrition 담당 기능별 개발 가이드
    │   │   ├── templates/           # Nutrition 반복 산출물 템플릿
    │   │   ├── previous-version/    # Nutrition 과거 스냅샷
    │   │   └── pdf/                 # Nutrition 문서 PDF 산출물
    │   ├── Food-docs/               # 음식 이미지 분석 담당 문서
    │   ├── Chat-docs/               # AI agent chat 담당 문서
    │   └── Integration-docs/        # 최종 통합·배포·시연 문서
    │       └── 01-ci-pr-integration-operations.md
    │
    ├── backend/                     # Python 백엔드
    │   ├── Nutrition-backend/       # 영양제·영양 분석 담당 런타임
    │   │   ├── src/                 # FastAPI 런타임, OCR, LLM, DB, 동의 gate
    │   │   ├── tests/               # unit/integration 테스트
    │   │   └── README.md
    │   ├── food_image_analysis/     # 음식 사진 분석 기능
    │   │   ├── src/
    │   │   │   └── food_image_analysis/
    │   │   ├── tests/
    │   │   └── README.md
    │   ├── ai_agent_chat/           # AI agent chat 기능
    │   │   ├── src/
    │   │   │   └── ai_agent_chat/
    │   │   ├── tests/
    │   │   └── README.md
    │   ├── alembic/                 # 공통 DB migration
    │   ├── scripts/                 # 검증·운영 보조 스크립트
    │   ├── requirements.txt
    │   ├── requirements-dev.txt
    │   └── pyproject.toml           # Black, Ruff, mypy, pytest 설정
    │
    ├── frontend/                    # 웹 대시보드·관리자·시연 UI
    │   ├── public/
    │   ├── src/
    │   ├── tests/
    │   └── README.md
    │
    ├── mobile/                      # UI/UX + Flutter + Xcode
    │   ├── uiux/
    │   │   ├── wireframes/
    │   │   └── design-assets/
    │   ├── flutter_app/
    │   │   ├── lib/
    │   │   ├── ios/                 # Xcode iOS project
    │   │   ├── android/
    │   │   ├── test/
    │   │   ├── pubspec.yaml
    │   │   └── analysis_options.yaml
    │   └── README.md
    │
    ├── data/                        # 데이터셋과 공식 reference
    │   ├── supplement_images/       # 영양제 이미지 데이터
    │   │   ├── raw/
    │   │   ├── interim/
    │   │   ├── processed/
    │   │   ├── splits/
    │   │   ├── manifests/
    │   │   ├── quarantine/
    │   │   └── scripts/
    │   ├── food_images/             # 음식 이미지 데이터
    │   │   ├── raw/
    │   │   ├── interim/
    │   │   ├── processed/
    │   │   ├── splits/
    │   │   ├── manifests/
    │   │   ├── quarantine/
    │   │   └── scripts/
    │   └── nutrition_reference/     # KDRIs, MFDS, nutrient code
    │       ├── kdris/
    │       ├── mfds/
    │       └── nutrient/
    │
    ├── assets/                      # 브랜드·시각 자산
    │   └── mascot/                  # 기존 마스코트/Lottie/캐릭터 번들
    ├── records/
    │   └── meetings/                # 회의록, 멘토링, 발주처 자료
    ├── outputs/
    │   ├── reports/                 # PDF·보고서 산출물
    │   ├── generated/               # 발표자료·수동 생성 작업 산출물
    │   └── todo-list/               # 날짜별 팀 공유/정리 문서
    │
    ├── .gitignore
    ├── .gitattributes               # Git LFS 설정 (필요 시)
    ├── .pre-commit-config.yaml      # pre-commit 훅 설정
    ├── .editorconfig                # 에디터 통일 설정
    └── LICENSE                      # 라이선스 (MIT 권장)
```

### 핵심 원칙
- **기능 단위 backend 분리**: 영양제 분석, 음식 사진 분석, AI agent chat은 각각 독립 폴더에서 `src/`와 `tests/`를 가진다.
- **팀별 작업 폴더와 런타임 폴더 일치**: Nutrition 담당 문서와 산출물은 `docs/Nutrition-docs/`, 실제 backend 런타임은 `backend/Nutrition-backend/`에서 관리한다.
- **Nutrition 런타임 경로**: 기존 `supplement_analysis` 런타임은 `Nutrition-backend/`로 이동했으며, 설정·CI·테스트 경로는 이 폴더명을 기준으로 유지한다.
- **`frontend/` 별도 생성**: 웹 대시보드, 관리자 화면, 시연 화면은 모바일과 분리한다.
- **`mobile/`은 UI/UX와 Flutter/Xcode 분리**: Figma/와이어프레임 산출물은 `uiux/`, 실제 앱은 `flutter_app/`에서 관리한다.
- **이미지 데이터는 수집원·가공단계·분할·manifest 분리**: 원본은 `raw/`, 임시 산출물은 `interim/`, 학습 입력은 `processed/`, split 파일은 `splits/`, taxonomy와 전체 인덱스는 `manifests/`에 둔다.
- **웹 크롤링 데이터는 클래스 단위 평탄 구조**: `raw/web_crawl/{class_name_en}/images/{hash}.jpg`와 source metadata를 기본 단위로 사용하고, 계층 정보는 `manifests/taxonomy.json`에서 관리한다.
- **품질 이슈는 quarantine으로 격리**: 중복, 저품질, 애매한 라벨은 `quarantine/duplicates`, `quarantine/low_quality`, `quarantine/ambiguous`로 이동해 학습 split에 섞이지 않게 한다.
- **영양 reference는 공통 폴더로 통합**: KDRIs, MFDS, nutrient code처럼 음식·영양제 분석 모두에서 재사용 가능한 기준 데이터는 `data/nutrition_reference/`에 둔다.
- **대용량 이미지는 Git LFS 또는 외부 스토리지**: Git에는 manifest, 샘플 fixture, 검증 스크립트만 우선 포함한다.
- **기능 플래그 기본 OFF**: OCR provider, YOLO, multimodal LLM, image learning, regulated intake는 발주처/동의 게이트 전까지 OFF다.
- **GitHub 협업 설정은 repository root 유지**: `.github/`는 `/Users/yeong/99_me/00_github/.github/`에 두고, workflow와 CODEOWNERS는 `03_lemon_healthcare/yeong-Lemon-Aid/**` 경로를 바라본다.
- **프로젝트 산출물은 내부 통합**: 마스코트, 회의록, 보고서, 수동 생성물, todo-list는 각각 `assets/`, `records/`, `outputs/` 아래로 모아 코드와 같은 제품 루트에서 관리한다.

---

## 2. 브랜치 전략 (Hybrid Flow — 단명 작업 브랜치 우선)

이 프로젝트는 두 가지 브랜치 패턴을 **공존**시키되, **신규 작업은 단명 `<type>/<scope>-<주제>` 패턴을 권장**한다. 기존 `<member>-<part>` 고정 브랜치는 점진적으로 새 패턴으로 마이그레이션한다.

> 📖 신규 패턴 상세: [`team-collaboration/BRANCH_STRATEGY.md`](./team-collaboration/BRANCH_STRATEGY.md)

### 2.1 브랜치 종류

```
main (production)                              ← 발표/시연용 안정 버전 (protected, 2명 승인)
  ↑
  │ (release PR — 매주 금 17:00 정기 머지)
  │
develop (integration)                          ← 통합·테스트 브랜치 (protected, 1명 승인)
  ↑
  │ (PR + CI green + 리뷰 1명 → Squash Merge)
  │
  ├─ <type>/<scope>-<주제>   ← 권장 (단명, 3-7일 안에 머지)
  │   예: feat/mobile-dashboard-5tab-shell
  │       fix/ocr-naver-chronic-snapshot
  │       chore/infra-python-3.13-bump
  │       docs/team-develop-rules
  │
  └─ <member>-<part>          ← 레거시 (점진적 마이그레이션)
      예: changmin-aiagent, changmin-plan, taedong-design,
          yeong-tech, jongpil-tech, sunghoon-database

hotfix/<scope>-<주제>          ← main 긴급 수정 → main + develop cherry-pick
```

| 브랜치 | 역할 | 머지 대상 | 머지 방식 | 보호 수준 |
|--------|------|----------|-----------|----------|
| `main` | 발표·시연용 안정 버전 | 직접 푸시 금지 | Merge commit (no-ff) | 🔴 최고 (2명 승인 + CI) |
| `develop` | 통합 개발 브랜치 | 모든 작업 브랜치의 PR 대상 | Squash Merge | 🟡 중간 (1명 승인 + CI) |
| `<type>/<scope>-<주제>` | **신규 권장** — 단명 작업 브랜치 | develop으로 PR | Squash Merge | — |
| `<member>-<part>` | **레거시** — 팀원 고정 작업 브랜치 | develop으로 PR | Squash Merge | — |
| `hotfix/<scope>-<주제>` | main 긴급 수정 | main + develop | Merge commit | — |

### 2.2 현재 팀 브랜치 기준

| 브랜치 | 담당 성격 | 주 작업 경로 |
|--------|-----------|--------------|
| `changmin-aiagent` | AI agent chat 기능 | `backend/ai_agent_chat/`, `docs/Chat-docs/` |
| `changmin-plan` | 기획·일정·문서 플랜 | `docs/`, `records/meetings/`, `outputs/todo-list/` |
| `taedong-design` | UI/UX, 모바일·프론트 디자인 | `mobile/uiux/`, `mobile/flutter_app/`, `frontend/`, `assets/` |
| `yeong-tech` | Nutrition 기술 구현·통합 | `backend/Nutrition-backend/`, `docs/Nutrition-docs/`, `data/supplement_images/`, `data/nutrition_reference/` |
| `jongpil-tech` | 기술 구현 보조·파트 기능 개발 | 담당 기능 확정 후 `backend/*`, `frontend/`, `mobile/` 중 해당 경로 |
| `sunghoon-database` | DB·데이터 구조·마이그레이션 | `backend/alembic/`, `backend/scripts/`, `data/`, `config/` |

### 2.3 브랜치 네이밍 규칙

#### 2.3.1 신규 권장 패턴 (단명 작업 브랜치)

```
형식: <type>/<scope>-<kebab-case-주제>

예시:
  feat/mobile-dashboard-5tab-shell
  feat/nutrition-chronic-disease-matrix
  fix/ocr-naver-chronic-snapshot-mismatch
  chore/infra-python-3.13-bump
  docs/team-develop-rules
  refactor/backend-supplement-service-split
  test/aiagent-meal-compliance
```

규칙:
- `<type>`은 [§3.2 Type 종류](#32-type-종류)와 동일한 목록 사용
- `<scope>`은 [§3.3 Scope](#33-scope-선택적)와 동일한 목록 사용 (예: `mobile`, `backend`, `nutrition`, `food`, `aiagent`, `ocr`, `db`, `auth`, `ux`, `infra`, `docs`, `team`, `data`)
- `<주제>`는 kebab-case (소문자 + 하이픈), 작업자 이름 포함 금지
- 3–7일 안에 머지 가능한 단위로 분할
- 머지 후 브랜치는 즉시 삭제

#### 2.3.2 레거시 패턴 (팀원-파트 고정 브랜치, 점진적 마이그레이션)

```
형식: <member>-<part>

현재 사용 중:
  changmin-aiagent
  changmin-plan
  taedong-design
  yeong-tech
  jongpil-tech
  sunghoon-database
```

이미 작업 중인 브랜치는 유지하되, **develop에 PR 머지한 다음 작업부터는 §2.3.1 패턴**으로 분기합니다.

레거시 규칙 (계속 유지):
- 모두 **소문자** 사용 / 단어 구분은 **하이픈(-)** / 언더스코어 X
- 자기 담당 브랜치에서만 직접 push, 다른 사람 브랜치에는 직접 push 금지
- `feature/*`, `docs/*`, `bugfix/*` 같은 옛 prefix는 신규 작업에 사용하지 않음

### 2.4 브랜치 라이프사이클

#### 2.4.1 신규 패턴 라이프사이클 (권장)

```
1. develop 최신 동기화      → git fetch team && git switch develop && git pull team develop
2. 단명 브랜치 분기         → git switch -c feat/<scope>-<주제> team/develop
3. 작업·커밋               → 의미 단위로 git add -p / git commit
4. develop 변경 동기화      → git fetch team && git rebase team/develop  (작업 중 정기적으로)
5. 푸시                    → git push -u team feat/<scope>-<주제>
6. PR 생성                 → gh pr create --base develop --fill
7. CI 통과 + 리뷰 1명 승인  → Squash and Merge
8. 원격·로컬 브랜치 삭제    → 다음 작업은 다시 1번부터
```

#### 2.4.2 레거시 패턴 라이프사이클 (마이그레이션 중)

```
1. 자기 담당 브랜치 이동    → git switch yeong-tech
2. 통합 브랜치 최신 반영    → git fetch team && git rebase team/develop  (merge 대신 rebase 권장)
3. 작업·커밋
4. push                    → git push team yeong-tech
5. PR 생성 (base: develop, compare: yeong-tech)
6. CI 통과 + 리뷰 통과
7. Squash & Merge
8. 다음 작업은 §2.4.1의 단명 브랜치 패턴으로 분기
```

> 📖 충돌 해결 / `--force-with-lease` 사용법 / reflog 복구: [`team-collaboration/MERGE_AND_CONFLICT.md`](./team-collaboration/MERGE_AND_CONFLICT.md)

---

## 3. 커밋 메시지 컨벤션 (Conventional Commits)

### 3.1 형식

```
<type>(<scope>): <subject>

<body>

<footer>
```

### 3.2 Type 종류

| Type | 의미 | 예시 |
|------|------|------|
| `feat` | 새 기능 추가 | `feat(nutrition): add v1 step score calculation` |
| `fix` | 버그 수정 | `fix(aiagent): handle empty user question edge case` |
| `docs` | 문서만 변경 | `docs(readme): update setup instructions` |
| `style` | 코드 스타일 변경 (포매터 등) | `style(backend): apply black formatter` |
| `refactor` | 리팩토링 (기능 변화 없음) | `refactor(api): split nutrition router` |
| `perf` | 성능 개선 | `perf(prediction): cache BMR calculation` |
| `test` | 테스트 추가/수정 | `test(nutrition): add edge cases for BMI categories` |
| `chore` | 빌드, 설정 등 | `chore(deps): upgrade fastapi to 0.110` |
| `ci` | CI 설정 변경 | `ci(infra): add docs lint workflow` |
| `build` | 빌드 시스템·외부 의존성 변경 | `build(mobile): pubspec.yaml dio 5.4 상향` |
| `revert` | 이전 커밋 되돌리기 | `revert(ocr): textline_orientation 기본값 복구` |
| `data` | 데이터셋·픽스처 추가/변경 | `data(ocr-eval): 16개 만성질환 픽스처 추가` |
| `ops` | 운영·배포·모니터링 | `ops(ocr): 스테이징 vision api_key 모드 경고` |

> 📖 type별 상세 가이드: [`team-collaboration/COMMIT_CONVENTION.md`](./team-collaboration/COMMIT_CONVENTION.md)

### 3.3 Scope (선택적)

영역을 명시할 수 있습니다. 두 가지 scope 체계가 공존하며, **도메인 scope를 우선**하되 인프라·UX 등 도메인 외 변경은 일반 scope를 사용합니다.

#### 3.3.1 도메인 scope (제품 기능 영역)

| Scope | 영역 |
|-------|------|
| `nutrition` | `backend/Nutrition-backend/`, `docs/Nutrition-docs/`, 영양제·영양 분석 |
| `food` | `backend/food_image_analysis/`, `data/food_images/`, 음식 사진 분석 |
| `aiagent` | `backend/ai_agent_chat/`, `docs/Chat-docs/`, AI agent chat |
| `ocr` | OCR provider, Vision API, 영양 라벨 파싱 (Nutrition 하위지만 PR 단위가 클 때 분리) |
| `auth` | OAuth, 세션, 이메일 인증, secure storage |

#### 3.3.2 일반 scope (인프라·UX 영역)

| Scope | 영역 |
|-------|------|
| `mobile` | `mobile/flutter_app/`, Flutter/Xcode 앱 |
| `backend` | backend 전반 (한 영역에 국한되지 않을 때) |
| `ai` | LLM 어댑터·프롬프트 (chat 외 사용처) |
| `db` | 데이터베이스 스키마·마이그레이션 |
| `data` | 데이터셋, manifests, splits, taxonomy |
| `design` / `ux` | `mobile/uiux/`, `frontend/`, `assets/`, 디자인 토큰 |
| `docs` | 문서 (이 폴더 포함) |
| `team` | 협업 규칙 (`docs/team-collaboration/`) |
| `integration` | 통합 운영, 릴리스, 시연, cross-part coordination |
| `infra` / `ci` | CI/CD, Docker, GitHub Actions, 배포 인프라 |
| `test` | 테스트 인프라 전반 (단위 테스트는 해당 영역 scope) |

#### 3.3.3 scope 선택 우선순위

1. 변경이 단일 도메인에 국한 → 해당 **도메인 scope** (`nutrition`, `food`, `aiagent`, `ocr`, `auth`)
2. 단일 도메인이지만 PR 단위가 너무 클 때 → 하위 scope 분리 (예: `nutrition` 전체 대신 `ocr`)
3. 도메인을 가로지르는 인프라/UX → **일반 scope** (`mobile`, `infra`, `db`, `data`, `design` 등)
4. 둘 다 해당될 때 → PR 본문에 보조 영역 명시, 제목에는 가장 핵심인 scope 하나만

### 3.4 좋은 커밋 vs 나쁜 커밋

#### ✅ 좋은 예시
```
feat(nutrition): add v4 chronic disease weighting

Implement v4 score calculation that applies disease-specific
multipliers (diabetes +0.10, hypertension +0.10, etc.) capped at 1.3.

Closes #42
```

#### ❌ 나쁜 예시
```
update                          ← 무엇을 업데이트?
fix bug                         ← 어떤 버그?
WIP                             ← 작업 중이면 push 자제
ㅁㄴㅇㄻㄴㅇㄹ                  ← 한글 키 실수 그대로
asdf                            ← 의미 없음
"수정함"                        ← 한국어도 OK이지만 구체적이어야
```

### 3.5 한국어 커밋 메시지 (선택)

영어가 부담스럽다면 한국어도 허용. 단 형식은 동일:
```
feat(nutrition): v1 활동점수 산출 함수 구현
fix(aiagent): 빈 사용자 질문 입력 시 에러 처리
docs(readme): 설치 가이드 업데이트
```

> 💡 **권장**: 영어를 기본으로 하되, 팀 회의에서 한국어 사용을 합의해도 무방. 단, **혼용은 피할 것** (한 PR 내에서 영어/한국어가 섞이면 가독성 ↓).

---

## 4. Pull Request (PR) 규칙

### 4.1 PR 생성 전 체크리스트

PR 작성자가 먼저 확인:
- [ ] 자기 담당 브랜치가 현재 규칙(`<member>-<part>`)을 따름
- [ ] base 브랜치가 `develop`인지 확인. 단, release/hotfix는 `main` 대상 가능
- [ ] `develop` 최신 내용을 자기 브랜치에 반영
- [ ] 로컬에서 린터·테스트 모두 통과
- [ ] 커밋 메시지가 컨벤션에 맞음
- [ ] 관련 이슈 번호를 PR 설명에 명시
- [ ] 스크린샷/데모 (UI 변경 시)
- [ ] 새 의존성 추가 시 이유 설명
- [ ] 다른 팀원 담당 경로를 수정했다면 PR 설명에 이유와 리뷰 요청자를 명시

### 4.2 PR 제목 규칙

커밋 메시지와 동일한 형식:
```
feat(nutrition): add v1 step score calculation
docs(integration): update branch workflow rules
```

### 4.3 PR 템플릿

`.github/PULL_REQUEST_TEMPLATE.md` 파일을 두면 PR 생성 시 자동으로 채워집니다. (별도 파일로 제공)

### 4.4 코드 리뷰 규칙

| 항목 | 규칙 |
|------|------|
| **최소 리뷰어 수** | 1명 (develop 머지) / 2명 (main 머지) |
| **리뷰 응답 시간** | 영업일 기준 24시간 이내 |
| **자기 PR 머지 가능 시점** | 모든 리뷰어 Approve + CI 통과 후 |
| **리뷰 시 사용 언어** | "Approve / Request Changes / Comment" |

### 4.5 리뷰 코멘트 톤 가이드

| 상황 | ❌ 나쁜 표현 | ✅ 좋은 표현 |
|------|-------------|-------------|
| 개선 제안 | "이거 왜 이렇게 했어요?" | "여기를 X 방식으로 바꾸면 Y 이점이 있을 것 같아요. 어떻게 생각하세요?" |
| 버그 발견 | "여기 버그임" | "여기서 N=0일 때 ZeroDivisionError 발생할 것 같습니다. 가드를 추가하면 어떨까요?" |
| 칭찬 | (생략하지 말 것) | "👍 이 부분 깔끔하네요!" |

> 💡 **원칙**: 사람을 비판하지 말고 코드를 비판한다. 항상 *"왜 그렇게 했는지"* 가 아니라 *"이렇게 하면 어떨지"* 의 톤으로.

### 4.6 머지 방식

- **Squash and Merge** (권장): 담당 브랜치의 여러 커밋을 한 개로 압축
- **Rebase and Merge**: 커밋 히스토리를 살릴 가치가 있을 때만
- **Merge Commit**: 사용 X (히스토리 복잡)

### 4.7 PR 머지 후 작업

팀원 담당 브랜치(`<member>-<part>`)는 계속 사용하는 작업 공간이므로 PR 머지 후 삭제하지 않는다.

1. 통합 브랜치 최신화:
   ```bash
   git checkout develop
   git pull origin develop
   ```
2. 자기 담당 브랜치 최신화:
   ```bash
   git switch yeong-tech
   git merge origin/develop
   git push origin yeong-tech
   ```
3. `hotfix-*`처럼 임시 브랜치만 머지 후 삭제한다.

---

## 5. Issue 관리

### 5.1 Issue 생성 시점

- 새로운 기능을 시작하기 전 (Feature Request)
- 버그를 발견했을 때 (Bug Report)
- 질문이 있을 때 (Question)
- 리팩토링 또는 기술 부채 (Tech Debt)

### 5.2 Issue 라벨 시스템

#### 카테고리 라벨
- `type:bug` 🔴
- `type:feature` 🟢
- `type:docs` 🔵
- `type:refactor` 🟡
- `type:question` 🟣

#### 우선순위 라벨
- `priority:critical` 🚨 (즉시 처리)
- `priority:high` 🔥
- `priority:medium` 🌡️
- `priority:low` ❄️

#### 영역 라벨
- `area:backend`
- `area:mobile`
- `area:nutrition`
- `area:food`
- `area:aiagent`
- `area:design`
- `area:database`
- `area:integration`
- `area:data`
- `area:docs`
- `area:ci`

#### 상태 라벨
- `status:in-progress`
- `status:blocked`
- `status:needs-review`
- `status:wontfix`

#### 난이도 라벨 (학생 팀용)
- `good-first-issue` (신규 멤버용)
- `help-wanted`

### 5.3 Issue 템플릿

`.github/ISSUE_TEMPLATE/` 폴더에 다음 3개 템플릿 제공 (별도 파일):
- `bug_report.md`
- `feature_request.md`
- `question.md`

### 5.4 Issue → PR 연결

PR 설명에 다음 키워드 사용 시 머지 시 자동으로 이슈 close:
```
Closes #42
Fixes #43
Resolves #44
```

---

## 6. .gitignore 표준

Python + Flutter + 일반 개발 환경 모두 커버하는 통합 .gitignore 사용 (별도 파일).

핵심 무시 항목:
- Python: `__pycache__/`, `*.pyc`, `.venv/`, `*.egg-info/`
- Flutter/Dart: `build/`, `.dart_tool/`, `*.g.dart`, `Pods/`
- 환경 변수: `.env`, `.env.local`
- IDE: `.vscode/`, `.idea/` (단 일부 공유 설정은 예외)
- OS: `.DS_Store`, `Thumbs.db`
- 데이터: `data/raw/`, `*.db`, `*.sqlite3`
- 모델 가중치: `*.h5`, `*.pth`, `models/checkpoints/`

> ⚠️ **절대 금지**: API 키, 비밀번호, 사용자 데이터를 커밋하지 말 것. 한 번 커밋되면 git history에 영구 보존됨 (force-push 해도 fork에서 복원 가능).

---

## 7. 코드 린터·포매터 설정

### 7.1 Python (Backend)

#### 도구 스택
| 도구 | 역할 | 설정 파일 |
|------|------|----------|
| **Black** | 코드 포매터 | `pyproject.toml` |
| **Ruff** | 린터 + import 정렬 | `pyproject.toml` |
| **mypy** | 타입 체크 | `pyproject.toml` |
| **pytest** | 테스트 러너 | `pyproject.toml` |

#### `pyproject.toml` 예시 (backend/pyproject.toml)
```toml
[tool.black]
line-length = 100
target-version = ["py313"]

[tool.ruff]
line-length = 100
target-version = "py313"
select = ["E", "F", "I", "N", "W", "UP"]
ignore = ["E501"]  # line-length는 black이 처리

[tool.mypy]
python_version = "3.13"
strict = true
ignore_missing_imports = true
explicit_package_bases = true

[tool.pytest.ini_options]
pythonpath = ["Nutrition-backend"]
testpaths = [
    "Nutrition-backend/tests",
    "food_image_analysis/tests",
    "ai_agent_chat/tests",
]
python_files = "test_*.py"
addopts = "-v --cov=src --cov-report=term-missing"
```

#### 사용법
```bash
# 포매팅
black Nutrition-backend/src Nutrition-backend/tests food_image_analysis/src food_image_analysis/tests ai_agent_chat/src ai_agent_chat/tests alembic scripts

# 린트
ruff check Nutrition-backend/src Nutrition-backend/tests food_image_analysis/src food_image_analysis/tests ai_agent_chat/src ai_agent_chat/tests alembic scripts
ruff check Nutrition-backend/src Nutrition-backend/tests food_image_analysis/src food_image_analysis/tests ai_agent_chat/src ai_agent_chat/tests alembic scripts --fix

# 타입 체크
mypy --explicit-package-bases Nutrition-backend/src Nutrition-backend/tests food_image_analysis/src food_image_analysis/tests ai_agent_chat/src ai_agent_chat/tests

# 테스트
pytest
```

### 7.2 Dart/Flutter (Mobile)

#### 도구 스택
| 도구 | 역할 |
|------|------|
| **dart format** | 코드 포매터 (내장) |
| **dart analyze** | 정적 분석 (내장) |
| **flutter_lints** | 추가 린트 규칙 |

#### `mobile/flutter_app/analysis_options.yaml` 예시
```yaml
include: package:flutter_lints/flutter.yaml

analyzer:
  errors:
    invalid_annotation_target: ignore
  exclude:
    - "**/*.g.dart"
    - "**/*.freezed.dart"

linter:
  rules:
    - prefer_const_constructors
    - prefer_const_literals_to_create_immutables
    - avoid_print
    - sort_child_properties_last
    - use_key_in_widget_constructors
```

#### 사용법
```bash
flutter format lib test
flutter analyze
flutter test
```

### 7.3 Pre-commit Hooks

커밋 전 자동으로 린터/포매터 실행. **로컬에서 실수를 막아 CI 시간을 절약**.

#### `.pre-commit-config.yaml` (별도 파일)

설치 방법 (팀원 온보딩 시):
```bash
pip install pre-commit
pre-commit install
```

이후 모든 `git commit`이 자동으로 린트 검사를 통과해야 진행됨.

---

## 8. GitHub Actions CI/CD

### 8.1 CI 목표

PR이 develop/main에 머지되기 전에 다음을 자동 검증:
- 코드 스타일 (black, dart format)
- 린트 (ruff, dart analyze)
- 타입 체크 (mypy)
- 단위 테스트 (pytest, flutter test)
- 빌드 가능 여부

### 8.2 워크플로 구성

세 개 Lemon Healthcare 워크플로 파일을 repository root `.github/workflows/`에서 분리해 운영:

#### `17-lemon-backend-ci.yml`
- 트리거: `main`, `develop`, `yeong-tech` 대상 PR/push 및 수동 실행
- Python 3.13 환경
- black --check / ruff / mypy / pip-audit / Alembic migration / pytest
- AI/OCR/YOLO/학습 파이프라인 변경 시 feature flag 기본값 OFF와 consent gate 테스트 확인

#### `17-lemon-mobile-ci.yml`
- 트리거: `main`, `develop`, `yeong-tech` 대상 PR/push 및 수동 실행
- Flutter 안정 버전 환경
- dart format --output=none --set-exit-if-changed
- flutter analyze
- flutter test

#### `17-lemon-docs-ci.yml`
- 트리거: `main`, `develop`, `yeong-tech` 대상 PR/push 및 수동 실행
- trailing whitespace 검사
- 마크다운 린트 (markdownlint)
- 깨진 링크 체크

> 별도 워크플로 파일들은 함께 제공됩니다.

### 8.3 CI 실패 시 대응

```
1. PR 페이지에서 빨간 X 클릭 → "Details" 클릭
2. 어떤 단계에서 실패했는지 확인 (formatting / lint / test)
3. 로컬에서 동일 명령 실행하여 재현
4. 수정 후 push → CI 자동 재실행
```

### 8.4 CI 캐싱

빌드 시간을 단축하기 위해:
- pip 캐시 (Python)
- pub 캐시 (Flutter)
- gradle 캐시 (Android 빌드)

설정은 GitHub Actions의 `actions/cache@v4` 사용.

---

## 9. Branch Protection Rules

### 9.1 main 브랜치 (최고 보호)

GitHub Settings → Branches → Add rule:

| 규칙 | 설정 |
|------|------|
| `Require a pull request before merging` | ✅ |
| `Require approvals` | ✅ 2명 |
| `Dismiss stale pull request approvals when new commits are pushed` | ✅ |
| `Require review from Code Owners` | ✅ |
| `Require status checks to pass before merging` | ✅ |
| `Require branches to be up to date before merging` | ✅ |
| `Required status checks` | `Backend quality and integration`, `Documentation quality`, `Flutter quality` |
| `Require conversation resolution before merging` | ✅ |
| `Require signed commits` | (선택) |
| `Require linear history` | ✅ |
| `Do not allow bypassing the above settings` | ✅ |

### 9.2 develop 브랜치 (중간 보호)

| 규칙 | 설정 |
|------|------|
| `Require a pull request before merging` | ✅ |
| `Require approvals` | ✅ 1명 |
| `Require status checks to pass before merging` | ✅ |
| `Required status checks` | 변경된 영역의 CI |

### 9.3 작업 브랜치 (신규/레거시 모두)

#### 신규 단명 브랜치 (`<type>/<scope>-<주제>`)
- 직접 push 허용 (보호 규칙 없음)
- develop에 PR 머지 후 **즉시 삭제** (GitHub: Automatically delete head branches 활성화)
- force push는 본인 브랜치에서만, `--force-with-lease` 사용

#### 레거시 고정 브랜치 (`<member>-<part>`)
`changmin-aiagent`, `changmin-plan`, `taedong-design`, `yeong-tech`, `jongpil-tech`, `sunghoon-database`는 개인 작업 브랜치이므로 직접 push를 허용한다. 단, 다음 규칙을 지킨다.

- 자기 담당 브랜치에서만 직접 push한다.
- 다른 팀원 브랜치에 직접 push하지 않는다.
- `main`과 `develop`에는 직접 push하지 않는다.
- 자기 브랜치가 오래되면 PR 전에 `develop`을 rebase(권장) 또는 merge해 충돌을 먼저 해결한다.
- **신규 작업은 §2.3.1 패턴으로 분기**한다. 이미 작업 중인 변경만 기존 브랜치에서 마무리한다.

### 9.4 CODEOWNERS 파일

`.github/CODEOWNERS`로 영역별 자동 리뷰어 지정:

```
# 기본 리뷰어
*                      @팀장

# 실제 GitHub 계정 또는 GitHub team handle로 교체해서 사용
/03_lemon_healthcare/yeong-Lemon-Aid/backend/Nutrition-backend/ @yeong-tech
/03_lemon_healthcare/yeong-Lemon-Aid/docs/Nutrition-docs/       @yeong-tech
/03_lemon_healthcare/yeong-Lemon-Aid/backend/ai_agent_chat/     @changmin-aiagent
/03_lemon_healthcare/yeong-Lemon-Aid/docs/Chat-docs/            @changmin-aiagent
/03_lemon_healthcare/yeong-Lemon-Aid/mobile/uiux/               @taedong-design
/03_lemon_healthcare/yeong-Lemon-Aid/mobile/flutter_app/        @taedong-design
/03_lemon_healthcare/yeong-Lemon-Aid/frontend/                  @taedong-design
/03_lemon_healthcare/yeong-Lemon-Aid/backend/alembic/           @sunghoon-database
/03_lemon_healthcare/yeong-Lemon-Aid/backend/scripts/           @sunghoon-database
/03_lemon_healthcare/yeong-Lemon-Aid/data/                      @sunghoon-database
/03_lemon_healthcare/yeong-Lemon-Aid/docs/                      @changmin-plan
/.github/                                                       @팀장
```

---

## 10. Secret Management

### 10.1 절대 커밋하지 말아야 할 것

```
❌ API 키 (Google Cloud Vision, CLOVA OCR, Firebase, ...)
❌ 데이터베이스 비밀번호
❌ JWT secret key
❌ AWS/NCP 액세스 키
❌ 사용자 개인정보 샘플
❌ 의료기관 인증서
❌ Apple Developer 인증서·프로비저닝 프로파일
❌ Google Service Account JSON
```

### 10.2 환경변수 관리

#### 로컬 개발
```
backend/.env (gitignore 됨)
GOOGLE_CLOUD_API_KEY=...
GOOGLE_VISION_AUTH_MODE=api_key
OCR_PRIMARY_PROVIDER=none
ALLOW_EXTERNAL_OCR=false
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen3.5:9b
DATABASE_URL=postgresql://...
```

`.env.example` 파일은 커밋 (값은 비워두고 키만):
```
backend/.env.example
GOOGLE_CLOUD_API_KEY=
GOOGLE_VISION_AUTH_MODE=api_key
OCR_PRIMARY_PROVIDER=none
ALLOW_EXTERNAL_OCR=false
OLLAMA_BASE_URL=
OLLAMA_MODEL=
DATABASE_URL=
```

#### CI 환경
GitHub Repository → Settings → Secrets and variables → Actions → New repository secret

#### 모바일 (API 키 보호)
- ❌ `apikey.dart`에 하드코딩 X
- ✅ 백엔드 API를 거쳐서 호출하도록 설계 (앱에서 직접 외부 API 호출 X)

### 10.3 실수로 키 커밋했을 때

```
1. 즉시 해당 키 폐기·재발급 (Google Cloud Console 등에서)
2. 새 키로 교체
3. git history에서 제거: BFG Repo-Cleaner 또는 git filter-branch
4. force push (팀원에게 미리 공지)
5. 모든 팀원이 git pull --rebase
```

> ⚠️ **주의**: 한 번 public repo에 커밋된 키는 **즉시 폐기**가 원칙. force-push 해도 GitHub fork·캐시·검색 봇이 이미 수집했을 가능성.

---

## 11. 팀원 온보딩 가이드 (Day 1)

새 팀원이 프로젝트에 합류할 때 따라야 할 1시간 체크리스트.

### Step 1. 저장소 클론
```bash
git clone https://github.com/<team>/lemon-healthcare-project.git
cd lemon-healthcare-project
```

### Step 2. 백엔드 환경 세팅
```bash
cd 03_lemon_healthcare/yeong-Lemon-Aid/backend
python -m venv .venv
source .venv/bin/activate          # macOS/Linux
# .venv\Scripts\activate            # Windows
pip install -r requirements.txt
cp .env.example .env               # 그리고 값 채우기
pytest                             # 테스트 통과 확인
```

### Step 3. 모바일 환경 세팅
```bash
cd ../mobile
flutter pub get
flutter doctor                     # iOS/Android 환경 확인
flutter test
```

### Step 4. Pre-commit 훅 설치
```bash
cd ..
pip install pre-commit
pre-commit install
```

### Step 5. 첫 커밋·PR 연습

`good-first-issue` 라벨이 붙은 이슈 중 하나를 골라:
1. 자기 담당 브랜치 확인 또는 생성 (`<member>-<part>`)
2. 작은 변경 (예: README 오타 수정)
3. 커밋 → push → PR
4. CI 통과 확인 → 리뷰 요청

### Step 6. 도구 추천 (선택)

| 도구 | 역할 |
|------|------|
| **VS Code** | 통합 IDE (Python + Dart 모두 지원) |
| **GitHub Desktop** | Git 초보자용 GUI |
| **Postman** | API 테스트 |
| **DBeaver** | DB 관리 |

VS Code 추천 확장:
- Python (Microsoft)
- Pylance
- Black Formatter
- Ruff
- Flutter (Dart Code)
- GitLens
- GitHub Pull Requests and Issues

---

## 📝 변경 이력

| 버전 | 날짜 | 변경 사항 | 작성자 |
|-----|------|---------|-------|
| v1.2 | 2026-05-21 | develop 통합 브랜치 정식 도입, 단명 `<type>/<scope>-<주제>` 패턴 추가, type에 `build`/`revert`/`data`/`ops` 보강, scope를 도메인/일반으로 분리, `docs/team-collaboration/` 연계 | Lemon Aid 팀 |
| v1.1 | 2026-05-15 | 팀원-파트 브랜치 Flow, Nutrition-backend 이동 후 폴더 트리, 공통 docs/Integration-docs 운영 기준 반영 | TBD |
| v1.0 | 2026-05-03 | 초안 작성. 폴더구조·브랜치·커밋·PR·CI·Branch Protection 통합 | TBD |

## 🔗 관련 문서

### 신규 협업 규칙 (정본 — 2026-05-21~)
- [`team-collaboration/README.md`](./team-collaboration/README.md) — 인덱스
- [`team-collaboration/BRANCH_STRATEGY.md`](./team-collaboration/BRANCH_STRATEGY.md) — 브랜치 전략
- [`team-collaboration/COMMIT_CONVENTION.md`](./team-collaboration/COMMIT_CONVENTION.md) — 커밋 메시지
- [`team-collaboration/PR_GUIDELINES.md`](./team-collaboration/PR_GUIDELINES.md) — PR 작성·리뷰
- [`team-collaboration/DEVELOP_WORKFLOW.md`](./team-collaboration/DEVELOP_WORKFLOW.md) — develop 통합 흐름
- [`team-collaboration/LOCAL_SETUP.md`](./team-collaboration/LOCAL_SETUP.md) — 로컬 hook/별칭
- [`team-collaboration/MERGE_AND_CONFLICT.md`](./team-collaboration/MERGE_AND_CONFLICT.md) — 충돌 해결
- [`team-collaboration/CODE_REVIEW_CHECKLIST.md`](./team-collaboration/CODE_REVIEW_CHECKLIST.md) — 리뷰 체크리스트
- [`team-collaboration/CI_CD_GATES.md`](./team-collaboration/CI_CD_GATES.md) — 자동 게이트
- [`team-collaboration/TEAM_QUICK_REFERENCE.md`](./team-collaboration/TEAM_QUICK_REFERENCE.md) — 한 페이지 치트시트

### 팀 전체 요약 문서
- [01. 프로젝트 개요](./01-project-overview.md)
- [03. 기획 의도](./03-project-intent.md)
- [06. 기술 스택](./06-tech-stack.md)
- [10. 컴플라이언스 체크리스트](./10-compliance-checklist.md)
- [CI/PR/통합 운영](./Integration-docs/01-ci-pr-integration-operations.md)
- [Nutrition 상세 구현 계획](./Nutrition-docs/08-implementation-plan.md)

## 🔗 함께 제공되는 설정 파일

- [.github/PULL_REQUEST_TEMPLATE.md](../../../.github/PULL_REQUEST_TEMPLATE.md)
- [.github/ISSUE_TEMPLATE/bug_report.md](../../../.github/ISSUE_TEMPLATE/bug_report.md)
- [.github/ISSUE_TEMPLATE/feature_request.md](../../../.github/ISSUE_TEMPLATE/feature_request.md)
- [.github/workflows/17-lemon-backend-ci.yml](../../../.github/workflows/17-lemon-backend-ci.yml)
- [.github/workflows/17-lemon-mobile-ci.yml](../../../.github/workflows/17-lemon-mobile-ci.yml)
- [.github/workflows/17-lemon-docs-ci.yml](../../../.github/workflows/17-lemon-docs-ci.yml)
- [.gitignore](../.gitignore)
- [.pre-commit-config.yaml](../.pre-commit-config.yaml)
