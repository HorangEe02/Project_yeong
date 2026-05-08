# 🚀 Phase 0 — Claude Code로 환경 세팅 (실전 가이드)

> **문서 정보**  
> 버전: v1.0 | 작성일: 2026-05-03 | 상태: 활성 | 대상: 팀 전원

---

## 📋 한 줄 요약

> 이 프로젝트의 Phase 0(환경 세팅)을 **Claude Code** 로 자동화하는 실전 매뉴얼. 설치 → 저장소 세팅 → 첫 명령어 → 검증까지 약 1시간이면 완료된다.

---

## 목차
- [⚠️ 시작 전 확인](#️-시작-전-확인)
- [Step 1 — Claude Code 설치 (5분)](#step-1--claude-code-설치-5분)
- [Step 2 — 프로젝트 저장소 세팅 (10분)](#step-2--프로젝트-저장소-세팅-10분)
- [Step 3 — Claude Code 첫 실행 (10분)](#step-3--claude-code-첫-실행-10분)
- [Step 4 — 결과 검증 (5분)](#step-4--결과-검증-5분)
- [Step 5 — 첫 알고리즘 구현 (30분)](#step-5--첫-알고리즘-구현-30분)
- [💡 Claude Code 핵심 명령어](#-claude-code-핵심-명령어-cheat-sheet)
- [🚨 자주 발생하는 문제](#-자주-발생하는-문제와-해결)
- [📋 Phase 0 완료 체크리스트](#-phase-0-완료-체크리스트)
- [🎯 권장 학습 순서 (학생 팀)](#-권장-학습-순서-학생-팀)
- [🔗 추가 자료](#-추가-자료)
- [✨ Tip: VS Code 연동](#-tip-vs-code-연동)

---

## ⚠️ 시작 전 확인

| 항목 | 요구사항 |
|------|---------|
| **구독** | Claude Pro ($20/월) 또는 API 키 — Claude Code는 무료 플랜에 미포함 |
| **OS** | macOS 13+ / Ubuntu 20.04+ / Windows 10 (WSL 또는 PowerShell) |
| **Git** | 설치 필수 |
| **Docker** | 설치 권장 (PostgreSQL·Redis용) |
| **Python** | 3.11+ |

> 💡 학생 팀이라면 한 명이 Pro 구독한 후 페어 프로그래밍하거나, 팀별로 분담하는 것을 권장합니다. Claude Pro에는 Claude Code가 포함되어 있습니다.

---

## Step 1 — Claude Code 설치 (5분)

2026년 현재 권장 방식은 **네이티브 설치** (Node.js 불필요, 자동 업데이트).

### macOS / Linux

```bash
curl -fsSL https://claude.ai/install.sh | bash
```

### Windows (PowerShell)

```powershell
irm https://claude.ai/install.ps1 | iex
```

> ⚠️ PowerShell에서 `'irm'은 인식되지 않는...` 에러가 나면 CMD에서 실행한 것이니 PowerShell을 다시 여세요. 프롬프트가 `PS C:\` 로 시작하면 PowerShell, `C:\` 로 시작하면 CMD입니다.

### 설치 확인

```bash
claude --version
# 정상: 버전 번호 출력
```

### 첫 실행 + 인증

```bash
claude
# 브라우저가 열리고 Claude 계정으로 로그인 → 자동으로 인증됨
```

---

## Step 2 — 프로젝트 저장소 세팅 (10분)

### 2-1. GitHub 저장소 생성

```bash
# GitHub에서 새 저장소 생성: lemon-healthcare-project
# 그 다음 로컬에서:

mkdir lemon-healthcare-project
cd lemon-healthcare-project
git init
git remote add origin https://github.com/<your-team>/lemon-healthcare-project.git
```

### 2-2. 가이드 파일들 배치

이전 작업에서 생성된 파일들을 다음 구조로 배치:

```
lemon-healthcare-project/
├── README.md                    ← outputs/README.md
├── CLAUDE.md                    ← outputs/claude-code-guides/tier1/CLAUDE.md
├── .gitignore                   ← outputs/dotgitignore.txt (이름 변경)
├── .pre-commit-config.yaml      ← outputs/pre-commit-config.yaml
│
├── .github/
│   ├── PULL_REQUEST_TEMPLATE.md ← outputs/PULL_REQUEST_TEMPLATE.md
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.md        ← outputs/bug_report.md
│   │   └── feature_request.md   ← outputs/feature_request.md
│   └── workflows/
│       ├── ci-backend.yml       ← outputs/ci-backend.yml
│       └── ci-mobile.yml        ← outputs/ci-mobile.yml
│
├── docs/
│   ├── 01-project-overview.md   ← outputs/01~10 모두
│   ├── 02-background-problem.md
│   ├── ... (10개 모두)
│   └── dev-guides/
│       ├── 00-setup-environment.md
│       ├── 01-bmi-and-v1-algorithm.md
│       ├── ... (00~05)
│
├── backend/
│   └── CLAUDE.md                ← outputs/claude-code-guides/tier2/backend-CLAUDE.md
│
└── data/
    └── CLAUDE.md                ← outputs/claude-code-guides/tier2/data-CLAUDE.md
```

### 2-3. 첫 커밋

```bash
git add .
git commit -m "docs: initial project setup with Claude Code guidelines"
git push -u origin main
```

이제 모든 가이드가 GitHub에 올라가서 팀 전체가 공유할 수 있습니다.

---

## Step 3 — Claude Code 첫 실행 (10분)

### 3-1. 프로젝트 디렉토리에서 시작

```bash
cd lemon-healthcare-project
claude
```

Claude Code가 시작되면 **자동으로** 다음을 읽습니다:
- `CLAUDE.md` (프로젝트 루트)

`backend/` 디렉토리에서 작업하면 추가로 `backend/CLAUDE.md` 도 읽습니다 (계층적 적용).

### 3-2. 첫 명령어 — 환경 세팅 자동화

Claude Code 프롬프트에서 다음을 입력:

```
> docs/dev-guides/00-setup-environment.md 의 명세에 따라 backend 환경을 세팅해줘. 
명세에 정의된 모든 파일을 만들고, Definition of Done 체크리스트를 모두 만족하는지 
확인해줘.
```

### 3-3. Claude Code가 할 일

명령어를 던지면 Claude Code는 자동으로:

```
1. CLAUDE.md 읽음                              (전역 규칙 파악)
2. backend/CLAUDE.md 읽음                      (백엔드 규칙 파악)
3. docs/dev-guides/00-setup-environment.md 읽음 (작업 명세)
4. backend/ 폴더 구조 생성
5. pyproject.toml, requirements.txt 작성
6. src/ 모든 __init__.py 생성
7. src/main.py + src/config.py + src/utils/logger.py 작성
8. .env.example 작성
9. tests/conftest.py 골격 작성
10. (선택) "방금 만든 파일들이 모두 명세대로인지 확인할까요?" 질문
```

### 3-4. 진행 중 자주 발생하는 인터랙션

Claude Code는 파일 변경 전에 **항상 확인**합니다:

```
Claude: backend/pyproject.toml 파일을 새로 생성합니다. 진행할까요?
> y

Claude: backend/src/main.py 파일을 새로 생성합니다. 진행할까요?
> y
```

> 💡 `--dangerously-skip-permissions` 플래그로 모든 확인을 건너뛸 수 있지만, 학습 단계에서는 확인하면서 진행하는 게 좋습니다.

---

## Step 4 — 결과 검증 (5분)

Claude Code가 작업을 마치면 직접 검증:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate

pip install -r requirements-dev.txt

# 코드 품질 도구
black src tests --check        # 통과해야 함
ruff check src tests           # 통과해야 함
mypy src --strict              # 통과해야 함

# 테스트
pytest                         # 0 tests OK여야 함

# 서버 시작
uvicorn src.main:app --reload --port 8000
```

브라우저에서 확인:
- `http://localhost:8000/health` → `{"status": "ok", "version": "0.1.0"}`
- `http://localhost:8000/docs` → Swagger UI 표시

✅ **모두 통과하면 Phase 0 완료!**

---

## Step 5 — 첫 알고리즘 구현 (30분)

Phase 0가 끝났으니 바로 Phase 1으로:

```
> docs/dev-guides/01-bmi-and-v1-algorithm.md 의 명세에 따라 BMI와 v1 활동점수 
알고리즘을 구현해줘. 회사 가이드 예시 (50대 여성 비만1단계 = 7,524보, 7,000보 시 
77.5점)가 단위 테스트로 정확히 검증되어야 해.
```

→ Claude Code가 자동으로:
1. `src/models/schemas/algorithm.py` (BMICategory enum)
2. `src/models/schemas/user.py` (UserProfile)
3. `src/algorithms/bmi.py` (BMI 계산·분류)
4. `src/algorithms/activity.py` (v1 부분)
5. `tests/unit/algorithms/test_bmi.py` (12+ 테스트)
6. `tests/unit/algorithms/test_activity_v1.py` (13+ 테스트)
7. `pytest` 실행 → 모든 테스트 통과 확인

---

## 💡 Claude Code 핵심 명령어 cheat sheet

| 명령어 | 용도 |
|-------|------|
| `/help` | 도움말 표시 |
| `/clear` | 컨텍스트 초기화 (긴 작업 후 시작 시) |
| `/context` | 현재 사용 중인 컨텍스트 확인 |
| `/compact` | 컨텍스트 압축 (긴 대화 정리) |
| `/model` | 모델 전환 (Sonnet 4.6 ↔ Opus 4.7) |
| `/doctor` | 환경 진단 (문제 발생 시) |
| `/init` | CLAUDE.md 자동 생성 — 우리는 이미 있으니 **사용 X** |
| `Ctrl+C` | 현재 작업 중단 |
| `exit` | Claude Code 종료 |

### 모델 선택 가이드

| 모델 | 추천 사용처 | 사용량 |
|------|-----------|-------|
| **Sonnet 4.6** | 일반 코드 생성·수정 (대부분 작업) | 보통 |
| **Opus 4.7** | 복잡한 알고리즘·다중 파일 리팩토링 | 많이 |
| **Haiku 4.5** | 간단한 검색·요약 | 적음 |

> Pro 플랜에서는 Sonnet 4.6 + Opus 4.7 모두 접근 가능. 사용량 한도가 있으니 일반 작업은 Sonnet, 복잡한 작업만 Opus 사용 권장.

---

## 🚨 자주 발생하는 문제와 해결

### 문제 1: `claude --version` 인식 안 됨

```bash
# PATH 갱신
source ~/.bashrc           # Linux/macOS
# 또는 새 터미널 열기
```

### 문제 2: 인증 실패 / 토큰 만료

```bash
claude /doctor             # 진단
# 또는
rm -rf ~/.claude           # 재인증
claude
```

### 문제 3: pre-commit hook 실패

```bash
pre-commit install         # hooks 설치
pre-commit run --all-files # 한 번 강제 실행 (정리)
```

### 문제 4: 모델 사용량 한도 도달

```bash
/model                     # Sonnet 4.6으로 전환 (Opus 4.7보다 빠르고 사용량 ↓)
```

### 문제 5: Claude Code가 가이드를 잘못 해석함

원인은 보통 다음 중 하나:
1. CLAUDE.md를 안 읽음 (잘못된 디렉토리에서 시작)
2. dev-guide 명세가 모호함
3. 컨텍스트가 너무 길어 누락

해결:
```
> /clear
> 현재 디렉토리는 lemon-healthcare-project야. CLAUDE.md, backend/CLAUDE.md, 
docs/dev-guides/01-bmi-and-v1-algorithm.md 를 먼저 읽고 다시 시작해줘.
```

### 문제 6: 코드가 mypy/ruff를 통과 못 함

```
> 방금 작성한 코드를 black, ruff, mypy --strict 모두 통과하도록 수정해줘. 
명세는 docs/dev-guides/01-bmi-and-v1-algorithm.md 그대로.
```

### 문제 7: 회사 가이드 예시 단위 테스트 실패

값이 미세하게 차이 나는 경우 (가이드는 손계산이라 ±0.1 오차 허용):

```
> test_v1_50f_obese1_7000_guide_example 가 fail합니다. 가이드 예시는 손계산이라 
±0.1 오차 허용입니다. pytest.approx(77.5, abs=0.1) 로 수정해주세요.
```

---

## 📋 Phase 0 완료 체크리스트

Phase 1으로 넘어가기 전 모두 통과:

- [ ] Claude Code 설치 + 인증 완료
- [ ] GitHub 저장소 생성 + 모든 가이드 파일 commit
- [ ] `cd backend` + `claude` 실행 시 CLAUDE.md 자동 인식
- [ ] `dev-guides/00` 따라 backend 환경 세팅 완료
- [ ] `pytest` 실행 (0 tests OK)
- [ ] `mypy --strict` 통과
- [ ] `uvicorn src.main:app` 정상 시작
- [ ] `/health` 응답 확인
- [ ] `/docs` Swagger UI 정상 표시
- [ ] 첫 PR 생성·머지 (CI 통과 확인)

---

## 🎯 권장 학습 순서 (학생 팀)

```
Day 1:  Step 1~2 (설치 + 저장소)              ── 30분
        Step 3~4 (Phase 0 환경 세팅)          ── 30분
        Step 5 (Phase 1 시작 — BMI 알고리즘)  ── 1시간
Day 2:  dev-guides/02 (v2~v4)                ── 2시간
Day 3:  dev-guides/03 (BMR/TDEE)             ── 1.5시간
Day 4:  dev-guides/04 (7-step 예측)          ── 2시간
Day 5:  dev-guides/05 (KDRIs 룩업)           ── 3시간
─────────────────────────────────────────────
Phase 1 완료 (10주 일정 중 W2~W4 분량을 1주에 압축 가능!)
```

> 💡 **팀 작업 팁**: 각 dev-guide는 독립적이므로 팀원별로 병렬 작업 가능. 단, KDRIs 룩업(05)은 사용자 프로필 모델(01)에 의존하므로 01 이후 진행.

---

## 🤖 Claude Code 작업 의뢰 표준 패턴

### 패턴 1 — 단일 작업

```
> docs/dev-guides/01-bmi-and-v1-algorithm.md 보고 구현해줘
```

→ Claude Code가 자동으로:
1. 루트 `CLAUDE.md` 읽음 (전역 규칙)
2. `backend/CLAUDE.md` 읽음 (백엔드 규칙)
3. `dev-guides/01-*.md` 명세대로 구현
4. 테스트 자동 작성
5. mypy/ruff/pytest 자동 검증

### 패턴 2 — 연속 작업

```
> dev-guides/00부터 05까지 순서대로 모두 구현해줘. 각 단계 완료 후 pytest 통과 
확인해주고, 문제 있으면 멈춰줘.
```

→ Phase 1 전체가 자동화. 단, 사용량이 많이 들 수 있으니 한 번에 너무 많이 던지지 말 것.

### 패턴 3 — 검증 의뢰

```
> 방금 구현한 v4 알고리즘이 가이드 예시 87.2를 정확히 도출하는지 단위 테스트로 검증
```

### 패턴 4 — 디버깅

```
> tests/unit/algorithms/test_activity_v1.py::test_v1_50f_obese1_7000_guide_example 
가 fail합니다. 디버깅해주세요.
```

### 패턴 5 — 리팩토링

```
> src/algorithms/activity.py 를 더 읽기 쉽게 리팩토링해주세요. 단, 모든 단위 
테스트는 그대로 통과해야 합니다.
```

---

## 🔗 추가 자료

### 공식 문서

- **Claude Code 공식 문서**: https://docs.claude.com/en/docs/claude-code/overview
- **Claude Code GitHub**: https://github.com/anthropics/claude-code
- **CLAUDE.md 베스트 프랙티스**: Claude Code 내에서 `/help` 명령어로 확인

### 본 프로젝트 문서

- 프로젝트 개요: [`/docs/01-project-overview.md`](./01-project-overview.md)
- GitHub 협업 규칙: [`/docs/05-github-guidelines.md`](./05-github-guidelines.md)
- 기술 스택: [`/docs/06-tech-stack.md`](./06-tech-stack.md)
- 핵심 알고리즘: [`/docs/07-core-algorithm.md`](./07-core-algorithm.md)
- Claude Code 컨텍스트: [`/CLAUDE.md`](../CLAUDE.md)
- 백엔드 컨텍스트: [`/backend/CLAUDE.md`](../backend/CLAUDE.md)

---

## ✨ Tip: VS Code 연동

터미널만 사용하기 불편하면 VS Code 확장을 설치하면 인라인 diff와 conversation history를 볼 수 있습니다.

```
1. VS Code 실행
2. Extensions (Cmd+Shift+X / Ctrl+Shift+X)
3. "Claude Code" 검색
4. 설치
5. Cmd+Shift+P → "Claude Code: Open in New Tab"
```

JetBrains IDE (PyCharm, IntelliJ IDEA, WebStorm 등) 사용자는 **JetBrains Marketplace**에서 *"Claude Code"* 플러그인 설치.

---

## 💸 비용 가이드 (학생 팀 기준)

### Pro 플랜 활용

- **월 $20** (또는 연 $200, 약간 할인)
- 한 명이 구독해도 페어 프로그래밍으로 모두 활용 가능
- 사용량 한도가 있지만 학생 프로젝트엔 충분

### 사용량 절약 팁

1. **Sonnet 4.6 우선 사용** — 일반 작업은 충분
2. **`/clear` 활용** — 작업 단위마다 컨텍스트 초기화
3. **CLAUDE.md 안정화** — 잦은 수정은 캐시 무효화
4. **세션 재사용** — 관련 작업은 같은 세션에서 (캐시 활용)
5. **파일 한 번만 읽게** — 큰 파일은 세션 시작 시 한 번 읽고 재사용

### API 키 방식 (대안)

학생이 Pro 구독이 어려우면 **Anthropic Console**에서 API 키 발급 후 종량제 사용 가능. 단, 사용량 모니터링 필수.

---

## 📝 변경 이력

| 버전 | 날짜 | 변경 사항 | 작성자 |
|-----|------|---------|-------|
| v1.0 | 2026-05-03 | 초안 작성. 설치~Phase 1 시작까지 통합 가이드 | TBD |

---

**준비 다 됐습니다!** 🚀

Step 1부터 차례대로 진행하시면서 막히는 부분 있으면 팀 Slack/Discord에 공유하거나, 같은 단계를 진행 중인 다른 팀원과 함께 해결하세요. 한 명이 막히면 다른 팀원이 빠르게 도와줄 수 있도록 작업 화면을 공유하는 것도 좋습니다.
