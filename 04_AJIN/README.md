# AJIN Compliance — AI 통합 업무 어시스턴트

> 아진산업 (KOSDAQ 013310) 사내 통합 AI 어시스턴트.
> 6개 도메인 (검색·문서·온보딩·법규·관리·설비) 기반 OpenAPI 자동 산정 API surface.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Backend](https://img.shields.io/badge/Backend-FastAPI-009688)
![Frontend](https://img.shields.io/badge/Frontend-React%20%2B%20Vite%20%2B%20TS-61dafb)
![LLM](https://img.shields.io/badge/LLM-Ollama%20qwen3.5%2Fexaone%20%7C%20Vertex%20Gemini-FF6B6B)
![API](https://img.shields.io/badge/OpenAPI-215%20paths%20%2F%20229%20endpoints-6BA539)
[![Static View](https://img.shields.io/badge/Static%20View-Vercel-000000)](https://dist-two-omega-62.vercel.app/)

> 📦 **포트폴리오 아카이브** — 2026 KNU × 아진산업 SILLI 경진대회(DX 부문) 제출작.
> 대회·검증 기간에는 Firebase Hosting, Cloud Run backend, Supabase(Postgres/Storage), Vercel frontend 배포를 모두 진행했습니다.
> 현재는 비용이 발생하는 운영 백엔드(Cloud Run · Firebase backend rewrite · DB · Storage · LLM)를 정리한 상태입니다.
> 현재 웹 화면은 정적 열람 전용 Vercel 배포인 <https://dist-two-omega-62.vercel.app/> 에서 확인할 수 있습니다.
> 이 링크는 실제 기능 호출이 아닌 화면 검토용이며, 상세 UI 자산은 [`uiux/`](uiux/) 에도 보존되어 있습니다.

---

## 한 줄 요약

**"650명 직원의 모든 업무 흐름 — 직원 검색 / 문서 작성 / 온보딩 / 법규 모니터링 / 인사 관리 / 설비 SPC — 을 한 화면에서 처리하는 AI 통합 콘솔"입니다.**

자동차 부품 제조 도메인 (현대·기아 협력사) 의 27 부서 × 6 사업장 × 6 해외법인을 위해 설계됐고, 한국 법규 (산안법·관세·MSDS·ISO·OEM 품질·EU CBAM 등) 자동 모니터링과 도메인 특화 한국어 LLM (qwen3.5·exaone·Vertex Gemini) 통합을 핵심으로 합니다.

---

## 시스템 전체 다이어그램

```
┌──────────────────────────────────────────────────────────────────────┐
│             Frontend (Firebase Hosting → Vercel)                      │
│                                                                       │
│  React + Vite + TypeScript + Zustand + Plotly                         │
│  ┌──────┬──────┬──────┬──────┬──────┬──────┐                          │
│  │  A   │  B   │  C   │  D   │  E   │  F   │  6 Feature 라우트       │
│  │검색  │ 작성 │ 챗봇 │법규  │ 관리 │ 설비 │                          │
│  └──────┴──────┴──────┴──────┴──────┴──────┘                          │
└──────────────────────────────┬───────────────────────────────────────┘
                                │ HTTPS
                                │ /api/** rewrites
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│                  Backend (Cloud Run / Docker)                         │
│                                                                       │
│  FastAPI OpenAPI API surface  +  uvicorn ASGI                         │
│                                                                       │
│  ┌────────────────────────────────────────────────────────────┐       │
│  │  Auth Middleware (JWT + RBAC + 감사 로깅)                  │       │
│  └────────────────────────────────────────────────────────────┘       │
│       │                                                               │
│       ▼                                                               │
│  ┌──────┬──────┬──────────┬──────────┬──────┬──────────┐              │
│  │  A   │  B   │     C    │     D    │  E   │     F    │              │
│  │검색  │ 작성 │   챗봇   │   법규   │ 관리 │   설비   │              │
│  │ OpenAPI tag 기준 router 그룹핑 — 정확한 수치는 docs/API.md 기준 │
│  └──────┴──────┴──────────┴──────────┴──────┴──────────┘              │
│       │      │      │           │         │       │                   │
│       ▼      ▼      ▼           ▼         ▼       ▼                   │
│  ┌────────────────────────────────────────────────────────────┐       │
│  │                   LLM Router (Phase 2)                     │       │
│  │  ┌──────────────┐    ┌──────────────────────────────────┐  │       │
│  │  │   Ollama     │    │     Vertex AI Gemini (Phase B)   │  │       │
│  │  │  (host/local)│    │     gemini-2.0-flash             │  │       │
│  │  │  qwen3.5     │    │     asia-northeast3 region       │  │       │
│  │  │  exaone-deep │    │     학습 미사용 보장              │  │       │
│  │  │  gemma4      │    │                                  │  │       │
│  │  └──────────────┘    └──────────────────────────────────┘  │       │
│  └────────────────────────────────────────────────────────────┘       │
│       │                                                               │
│       ▼                                                               │
│  ┌────────────────────────────────────────────────────────────┐       │
│  │  SQLite × 15+ DBs                                          │       │
│  │  • employees / auth / audit         (A·E)                  │       │
│  │  • draft_versions                   (B)                    │       │
│  │  • feedback                         (C)                    │       │
│  │  • compliance / compliance_changes / scenarios /           │       │
│  │    suppliers / industry_trend       (D)                    │       │
│  │  • error_codes / error_history /                           │       │
│  │    inspection_logs / mold_lifecycle (F)                    │       │
│  │                                                            │       │
│  │  ChromaDB                                                  │       │
│  │  • 규제 본문 + 매뉴얼 + 판례 + 계약 RAG 인덱싱             │       │
│  │                                                            │       │
│  │  Redis (LLM 응답 캐시)                                     │       │
│  └────────────────────────────────────────────────────────────┘       │
└──────────────────────────────┬───────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│                          외부 시스템 통합                              │
│                                                                       │
│  ┌─────────────┬─────────────┬─────────────┬─────────────┐            │
│  │ 9 크롤 소스  │ 알림 채널    │ 협업·결재    │ 데이터·인증 │            │
│  │             │             │             │             │            │
│  │ 국내법      │ Slack       │ Atlassian   │ DART        │            │
│  │ EU         │ Naver SENS  │   Jira      │ 대법원       │            │
│  │ US/CN 통상  │ Twilio SMS  │ 자체 결재   │ Firebase    │            │
│  │ MSDS       │ SMTP 메일   │ Hancom      │ Auth        │            │
│  │ ISO        │             │  e-Approval │             │            │
│  │ APQP       │             │             │             │            │
│  │ OEM 품질   │             │             │             │            │
│  │ EV 배터리   │             │             │             │            │
│  │ 탄소·ESG   │             │             │             │            │
│  └─────────────┴─────────────┴─────────────┴─────────────┘            │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 6 Feature 진입점 — 각 도메인 상세 문서

각 Feature 문서는 비전공자도 읽을 수 있는 상세 설명을 제공하고, API 수치는 FastAPI OpenAPI 산출물에서 자동 계산합니다.

<!-- OPENAPI_SUMMARY:START -->
> 이 블록은 `scripts/generate_openapi_docs.py`가 FastAPI `app.openapi()` 기준으로 생성합니다.
> endpoint는 OpenAPI operation(`METHOD + path`) 기준이며, path 수와 구분합니다.

- **API 버전:** 1.1.0
- **OpenAPI 버전:** 3.1.0
- **총 path:** **215**
- **총 endpoint:** **229**
- **상세 인덱스:** [docs/API.md](docs/API.md)
- **머신 리더블 요약:** [docs/openapi-summary.json](docs/openapi-summary.json)

| Feature | 도메인 | OpenAPI tag | endpoint 수 |
|---|---|---|---:|
| **A** | 검색·조직도 | `search`, `employee`, `directory` | **15** |
| **B** | 문서 작성 | `draft` | **27** |
| **C** | AI 업무 도우미 | `onboarding`, `scenarios`, `feature-flags` | **39** |
| **D** | 법규 모니터링 | `compliance`, `notifications` | **25** |
| **E** | 인사·관리 | `admin`, `admin-scenarios`, `auth`, `idp` | **74** |
| **F** | 설비·SPC | `equipment` | **19** |
| **공통** | 인프라·헬스·모델 | `dashboard`, `models`, `export`, `health`, `me`, `slack`, `untagged`, `feedback`, `live-alarms`, `storage` | **30** |
| 합계 | | | **229** |

> 모듈 수는 OpenAPI에서 검증할 수 없는 코드 구조 수치이므로 이 자동 산정 표에서 제외합니다.
<!-- OPENAPI_SUMMARY:END -->

---

## 운영 가이드

| 주제 | 문서 |
|---|---|
| **API 인덱스** | [docs/API.md](docs/API.md) + [docs/openapi.json](docs/openapi.json) + [docs/openapi-summary.json](docs/openapi-summary.json) |
| **Docker 운영 (Phase 1·2 컨테이너)** | [docs/DOCKER.md](docs/DOCKER.md) |
| **백엔드 배포 (Cloud Run)** | [docs/BACKEND_DEPLOY.md](docs/BACKEND_DEPLOY.md) |
| **풀 모드 배포 (frontend + backend + Ollama)** | [docs/FULL_MODE_DEPLOY.md](docs/FULL_MODE_DEPLOY.md) |
| **변경 이력** | [CHANGELOG.md](CHANGELOG.md) |

---

## 빠른 시작 (4 단계)

```bash
# 1. 호스트 Ollama 셋업 (.env 작성 후)
make setup

# 2. 컨테이너 시작
make up

# 3. 헬스 검증
make health

# 4. (선택) 호스트 .venv 회귀 테스트
make backend-venv
make test
```

자세한 내용은 [docs/DOCKER.md](docs/DOCKER.md).

---

## 기술 스택 한눈에

### Backend
- **Python 3.11+** + FastAPI + uvicorn
- **SQLite × 15+** + ChromaDB + Redis
- **LLM**: Ollama (qwen3.5/exaone/gemma4) + Vertex AI Gemini (Phase B)
- **외부**: Atlassian Jira / Slack / Naver SENS / Twilio / Firebase Auth / DART OpenAPI

### Frontend
- **TypeScript** + React + Vite + Zustand
- **Plotly.js** + MarkdownRenderer + lucide-react
- **정적 화면 열람**: Vercel (https://dist-two-omega-62.vercel.app/)
- **배포 이력**: Firebase Hosting 배포 후 Vercel frontend 배포/전환 검토까지 진행
- **운영 기능 호출**: 비용 절감을 위해 비활성화 (Cloud Run / Firebase backend rewrite 미사용)

### 인프라
- **Docker Compose** — backend / frontend / redis / nginx-rp 4 컨테이너
- **배포 이력** — Firebase Hosting + Cloud Run backend, Supabase(Postgres/Storage), Vercel frontend
- **현재 포트폴리오 배포** — Vercel static assets only
- **운영 배포 구성** — Cloud Run + Supabase + Vercel 설계와 검증 산출물 보존, 현재는 비용 절감을 위해 중지
- **GCP** 프로젝트 `ajin-compliance` (Phase B)

---

## Phase 진행 상황

| Phase | 상태 | 내용 |
|---|---|---|
| **Phase 1** | ✅ 완료 | 통합 docker-compose + 호스트 Ollama (Mac M4 Pro Metal) |
| **Phase 2** | ✅ 완료 | LLM 풀 feature 별 라우팅 (`LLM_FEATURE_ROUTES`) — 4 feature 분리 |
| **Stage 1 dry-run** | ✅ 완료 | Mac offline / host Ollama 관측 및 Stage 1 hotfix 반영 |
| **Phase B** | ✅ 코드 완료 | Vertex AI Gemini dispatcher와 `LLM_PROVIDER=vertex` 전환 경로 구현 |
| **Stage 2 · Firebase/Cloud Run** | ✅ 배포 완료 → 정리 | Firebase Hosting + Cloud Run backend 배포/검증 후 비용 관리를 위해 운영 리소스 정리 |
| **Stage 3 · Supabase 전환** | ✅ 검증 완료 | Supabase(Postgres/Storage) remote release gate PASS, Firebase read/write fallback 비활성화, Cloud Run no-traffic tag smoke PASS |
| **Stage 4 · Vercel 전환** | ✅ 배포 완료 → 정적화 | Vercel frontend 배포/전환 검토 완료, 현재는 비용 없는 정적 화면 열람용 Vercel 배포만 유지 |
| **Phase 3** | 📅 장기 | Feature 마이크로서비스 분해 (D11 / D17 / D6 / D9 / D14·D15 순) |

---

## 사내 도메인 컨텍스트

### 회사 정보 (`config.py:COMPANY_INFO`)
- **아진산업(주)** (KOSDAQ 013310)
- 자동차 차체용 신품 부품 제조업
- 본사: 경상북도 경산시 진량읍 공단8로 26길 40
- 매출 2025: 1조 886억원 (영업이익 643억원, +99.4%)
- 주요 고객사: 현대자동차 / 기아자동차
- 인증: IATF 16949 / ISO 14001 / ISO 45001 / AEO AAA

### 조직
- **649명 직원**
- **6 본부** (재경 / 관리 / 구매 / 생산 / 개발 / 생산기술) + 기술연구소 + 독립부서
- **27 부서** (각 부서 ai_relevance: low / medium / high / critical)
- **6 국내 사업장** (경산 본사 / 경산 2공장 / 경주 구어 + 계열사 3)
- **6 해외법인** (미국 2 / 중국 3 / 베트남 1) — JOON INC (HMGMA 협력) 등

### 핵심 사용자 부서
| 부서 | ai_relevance | 핵심 사용 Feature |
|---|---|---|
| 품질보증팀 | **critical** | A · B · D · F (8D / PPAP / SPC 주관) |
| 안전보건팀 | high | D (산안법 1순위 수신) |
| 생산기술팀 | high | C · F (4M 변경 관리) |
| IT전략팀 | high | E (시스템 도구) |
| 부품개발팀 | high | A (ECN/PPAP 검색) |
| 구매팀 | high | B · D (협력사 이메일) |
| 영업팀 | high | B (납기 이메일) |
| 기술교육원 | high | C (온보딩 연계) |

전체 27 부서 매트릭스는 [config.py:DEPARTMENTS](config.py).

---

## 보안·컴플라이언스

- **JWT 인증** + RBAC 5 역할 (level 1-5)
- **가시성 3 계층** — FULL / PARTIAL / HIDDEN (부서·역할 기반 자동)
- **감사 로깅** — `api_audit_log` 테이블 (모든 요청)
- **로그인 보안** — 5회 실패 → 15분 자동 잠금, bcrypt + 90일 강제 변경
- **데이터 학습 차단** — `FEATURE_B_BLOCK_GEMINI=true` (사내 문서 보호) + Vertex AI paid tier 학습 미사용 보장
- **외부 노출 0 옵션** — Mac offline 모드 (Phase 1·Stage 1)

ISO 27001 + 개인정보보호법 + IATF 16949 컴플라이언스 정책 정합.

---

## Phase 2 LLM 라우팅 구조

**4 feature × 2 provider** 매트릭스 (`config.py:LLM_FEATURE_ROUTES`):

| Feature | tier | Ollama 모델 | Vertex 모델 | 사용처 |
|---|---|---|---|---|
| `rag_answer` | fast | qwen3.5:4b | gemini-2.0-flash | D — RAG 답변 |
| `quiz_gen` | fast | qwen3.5:4b\* | gemini-2.0-flash | D — 학습 퀴즈 |
| `short_answer_grade` | fast | qwen3.5:4b | gemini-2.0-flash | D — 단답 채점 |
| `whatif_nl_route` | large | qwen3.5:9b | gemini-2.0-flash | D — What-if 자연어 |

`LLM_PROVIDER=vertex` 1줄 swap 으로 Ollama → Vertex 자동 전환. 미설정 시 Ollama 폴백 (backward-compat).

\* 원래 `gemma4:e2b` 였으나 호스트 Ollama 0.18.2 미지원으로 hotfix.

---

## 루트 구성 파일 가이드

배포 이력이 많은 프로젝트라 루트에 구성 파일이 여럿 있습니다. 용도는 다음과 같습니다.

| 파일 | 용도 |
|------|------|
| `docker-compose.yml` | 기본 로컬 스택 (backend + frontend + redis + reverse proxy) |
| `docker-compose.celery.yml` | 비동기 작업 스택 (redis + celery worker/beat + flower) |
| `docker-compose.postgres.yml` | PostgreSQL 데이터베이스 단독 구성 |
| `docker-compose.supabase.yml` | Supabase 연동 시 backend + frontend 구성 |
| `docker-compose.cloud.yml` | 클라우드 LLM 스택 (ollama large/fast 2계열 + backend) |
| `Dockerfile` / `Dockerfile.worker` | API 서버(slim/full 통합) / Celery worker·beat·flower 공통 이미지 |
| `requirements.txt` | 전체 로컬 개발 의존성 |
| `requirements-cloudrun.txt` / `-full.txt` | Cloud Run 경량 / 전체 배포 의존성 |
| `.env.example` / `.env.docker.example` | 로컬 / 도커 환경변수 템플릿 |
| `.gcloudignore` / `.gcloudignore-full` | Cloud Run 업로드 제외 목록 (경량 / 전체) |

## 변경 이력 요약

전체 이력은 [CHANGELOG.md](CHANGELOG.md). 최근 마일스톤:

- **v3.5** (2026-04) — UX 개선·다운로드 확장·모델 정리·인코딩 수정 / 6 모듈 카드 (A~F 전체)
- **v3.4** (2026-04) — Dark 모드 가독성·SPC 분석 탭·SOP 5종 추가·demo 시나리오 엔진
- **Phase 2** (2026-05) — LLM 풀 feature 별 라우팅 도입
- **Stage 1 hotfix** (2026-05-09) — `_call_ollama` think kwarg + INFO trace + gemma4 hotfix
- **Phase B 코드** (2026-05-09) — Vertex AI Gemini dispatcher (`_call_llm`)

---

## 팀 / 크레딧

- **박준영** ([@HorangEe02](https://github.com/HorangEe02)) — Lead · Backend · LLM/Infra
- **박성훈 · 이현아 · 정유진** — Frontend · Compliance · Equipment · UX

원 저장소: [`HorangEe02/Project_yeong/04_AJIN`](https://github.com/HorangEe02/Project_yeong/tree/main/04_AJIN)

```bash
git clone https://github.com/HorangEe02/Project_yeong.git
cd Project_yeong/04_AJIN
```

## 라이선스

[MIT](LICENSE) © 2026 박준영 (HorangEe02) — KNU × 아진산업 SILLI 2026

> 사내 도메인 데이터(직원·법규 DB 등)는 데모/합성 데이터로 대체되어 있으며, 실제 사내 자료는 포함되지 않습니다.

---

문서 작성: 2026-05-10 | 시스템 마지막 검증: Phase B 코드 push (commit 8292bca)
