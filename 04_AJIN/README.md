# AJIN AI Assistant

> 아진산업 KDT 졸업 프로젝트 — 사내 업무용 AI Assistant.
> Mac Ollama × Cloud Run × Firebase Hosting 운영급 연동.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Frontend](https://img.shields.io/badge/Frontend-React%20%2B%20Vite-61dafb)](frontend/)
[![Backend](https://img.shields.io/badge/Backend-FastAPI-009688)](backend/)
[![LLM](https://img.shields.io/badge/LLM-Ollama%20qwen3.5%2Fgemma4%20%7C%20Gemini-FF6B6B)](#-llm-아키텍처)

🌐 **Live demo**: https://ajin-cb.web.app

## 📌 한 줄 요약

사내 직원이 자연어로 질문하면 — **신입 온보딩, 법규 준수 점검, 검사 보고서 자동 작성, 동료·설비 검색** — 까지 한 번에 처리해주는 AI Assistant. 사내 데이터는 Mac 호스트의 Ollama 가, 일반 작업은 Gemini 가 답하는 **하이브리드 자가 호스팅** 아키텍처.

## ✨ 주요 기능

| 모듈 | 기능 | 사용 LLM |
|---|---|---|
| **A. 인원 검색** | 이름·부서·직급으로 동료 정보 빠르게 찾기 | Ollama (bge-m3 임베딩 + qwen3.5) |
| **B. 문서 작성** | 메일·보고서 초안을 AI 가 대신 작성 (Word·PDF·HWP 7가지로 저장) | Ollama qwen3.5:9b |
| **C. AI 도우미** | 사내 용어·업무 절차를 24시간 알려주는 AI (이미지 첨부 시 vision) | Ollama (text) + Gemini (vision) |
| **D. 법규 모니터** | 산업안전보건법 등 변경 사항 추적·알람 (Meilisearch + 임베딩) | Ollama embedding |
| **E. 인사 관리** | 계정·권한·인력 통계 한 곳에서 관리 (RBAC L1~L5) | — |
| **F. 설비/공정 AI** | 설비 이상 사전 감지·예측 | Ollama qwen3.5:9b |

## 🏗 LLM 아키텍처 (Plan A 변형)

```
사용자
  │ HTTPS
  ▼
ajin-cb.web.app  ────── /api/**  ──────► Cloud Run (asia-northeast3)
(Firebase Hosting)                       ajin-backend (FastAPI)
                                            │ X-AJIN-Secret 헤더
                                            ▼
                                  *.trycloudflare.com (임시 URL, watchdog 자동 갱신)
                                            │
                                            ▼
                                  Cloudflare Edge
                                            │
                                            ▼
                                  Mac (M4 Pro, 24GB RAM)
                                  ├─ cloudflared (launchd)
                                  ├─ Caddy :8434 (header 검증)
                                  └─ Ollama :11434
                                       (qwen3.5:9b/4b, gemma4:e4b/e2b, bge-m3)
```

- **Mac on**: 채팅 = Ollama qwen3.5:9b (자가 호스팅, 사내 데이터 안전)
- **Mac off**: maintenance banner 자동 표시 + 채팅 입력 비활성
- **임베딩**: 항상 Gemini text-embedding-004 (Mac 무관)
- **사고 시**: `LLM_ROUTER_PRIMARY=gemini` env 1줄로 즉시 Gemini-only 환원

자세한 다이어그램·흐름: [`ARCHITECTURE.md`](ARCHITECTURE.md)

## 🚀 빠른 시작 (로컬)

```bash
# 1. clone
git clone https://github.com/HorangEe02/Project_yeong.git
cd Project_yeong/04_AJIN

# 2. 1-클릭 셋업
bash scripts/setup-host.sh

# 3. 백엔드 dev 서버
source .venv/bin/activate
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload

# 4. (다른 터미널) 프론트엔드 dev 서버
cd frontend && npm run dev
# → http://localhost:5173

# 5. (선택) 시연 환경 활성화 (Cloudflare Tunnel + Cloud Run env 자동 동기화)
bash scripts/demo/start_local_demo.sh
```

상세 가이드: [`INSTALL.md`](INSTALL.md)

## 📂 디렉토리 구조

```
04_AJIN/
├── backend/             # FastAPI — REST/SSE API
├── core/                # LLM router (provider chain) + auth + scenarios
├── features/            # A~F 모듈 (search/draft/onboarding/compliance/admin/equipment)
├── frontend/            # React + Vite — Liquid Glass 디자인
├── docker/demo-tunnel/  # cloudflared 컨테이너 (시연용)
├── infra/               # Caddyfile, launchd plist, watchdog 스크립트 (예시)
├── scripts/             # setup·deploy·reindex 스크립트
├── docs/                # 설계 문서·로드맵
├── secrets/             # secret 파일 (git ignore, README 참고)
├── data/                # 데모 데이터 (git ignore, setup-demo-data.py 로 생성)
├── Dockerfile           # multi-stage (slim/full)
├── cloudbuild.yaml      # Cloud Build 파이프라인
├── firebase.json        # Firebase Hosting 설정
└── .env.example         # 환경변수 템플릿
```

## 🛠 기술 스택

| 영역 | 사용 기술 |
|---|---|
| Frontend | React 19 + Vite + TypeScript + Tailwind v4 (Liquid Glass) + Zustand + react-router-dom |
| Backend | FastAPI + uvicorn + Pydantic v2 + langchain (Ollama/Gemini) |
| 데이터베이스 | SQLite (auth/employees/compliance) + ChromaDB (vectorstore) + Meilisearch (전문검색) |
| LLM | Ollama (qwen3.5/gemma4/bge-m3) + Gemini 2.5 Pro (cloud fallback + vision) |
| 인증 | Firebase Auth + JWT + RBAC (L1~L5) |
| 인프라 | Cloud Run + Firebase Hosting + Cloudflare Tunnel + Caddy reverse proxy |
| CI/CD | GitHub Actions (lint + build + auto deploy) |

## 🤝 기여하기

PR 환영합니다. 기여 전 [`CONTRIBUTING.md`](CONTRIBUTING.md) 의 브랜치 명명·커밋 컨벤션·PR 규칙을 확인해 주세요.

main 브랜치는 보호되어 있으므로 직접 push 가 불가능합니다 — feature/* 브랜치에서 작업 → PR → 1명 review + CI 통과 → squash merge.

## 🐛 문제 해결

흔한 문제 (`ModuleNotFoundError`, `Mac off 시 503`, `cloudflared URL 변경` 등) 는 [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md).

## 🔒 보안

- secret 노출 의심 시 즉시 [`SECURITY.md`](SECURITY.md) 의 보고 절차 참고
- `data/employees.db`, `data/compliance.db` 등 사내 데이터는 PUBLIC repo 에 절대 commit 금지
- `.env`, `secrets/*` 는 `.gitignore` 처리됨

## 📄 라이선스

[MIT](LICENSE) © 2026 박준영 (HorangEe02) — KNU SILLI 2026

## 👤 팀

- **박준영** ([@HorangEe02](https://github.com/HorangEe02)) — Lead, Backend, LLM/Infra
- **박성훈, 이현아, 정유진** — Frontend, Compliance, Equipment, UX

원 저장소: [`HorangEe02/Project_yeong/04_AJIN`](https://github.com/HorangEe02/Project_yeong/tree/main/04_AJIN)
