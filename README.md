# 박준영 · AI Engineering Project Portfolio

> **기업 발주 · 경진대회 · 자기주도로 설계·구현한 실무급 AI 프로젝트 모음**
>
> 통계학 기반 데이터 사이언티스트로서, KDT 교육 과정([KNU_KDT_12th](https://github.com/HorangEe02/KNU_KDT_12th))과 별개로
> **멀티모달 AI 검색 엔진 · 헬스케어 플랫폼 · 제조 도메인 AI 어시스턴트**를
> 기획부터 모델링·백엔드·프론트엔드·배포까지 단독/협업으로 구축했습니다.
> 모델을 만드는 데 그치지 않고 **실제 동작하는 제품**으로 완성하는 것을 목표로 합니다.

| | |
|------|------|
| **작성자** | 박준영 (Junyeong Park) · 계명대학교 통계학과 졸업 |
| **GitHub** | [github.com/HorangEe02](https://github.com/HorangEe02) |
| **연관 포트폴리오** | [KDT 12기 프로젝트 (13선)](https://github.com/HorangEe02/KNU_KDT_12th) · [Notion 포트폴리오](https://www.notion.so/31879104c6f38039a53cfaa4b64ef712) |

---

## 📦 프로젝트 한눈에

| # | 프로젝트 | 한 줄 소개 | 성격 | 핵심 기술 |
|---|---------|----------|------|----------|
| **[01](#-01_cad--cad-vision--ai-산업-도면-검색분류-엔진)** | **CAD Vision** | AI로 산업용 CAD 도면을 분류·검색·분석하는 멀티모달 RAG 풀스택 엔진 | 자기주도 심화 | YOLO · OpenCLIP · GNN · ChromaDB · Ollama · FastAPI · Next.js |
| **[02](#-02_mediway--병원-동선-안내--고령자-접근성-웹앱)** | **MediWay** | 병원 내 환자 동선 안내 + 멀티테넌트 SaaS + 고령자 접근성 웹앱 | 자기주도 심화 | React · TypeScript · Firebase · Dijkstra · WAI-ARIA |
| **[03](#-03_lemon_healthcare--lemon-healthcare-건강의신)** | **Lemon Healthcare (건강의신)** | 영양제 라벨 OCR 한 장으로 5종 통합 건강분석을 제공하는 AI 헬스케어 플랫폼 | 기업 발주 협업 | FastAPI · Flutter · PostgreSQL/TimescaleDB · Cloud Vision · Ollama |
| **[04](#-04_ajin--ajin-compliance--제조-도메인-ai-통합-어시스턴트)** | **AJIN Compliance** | 제조 대기업 650명의 6개 업무 도메인을 한 화면에서 처리하는 AI 통합 콘솔 | 경진대회 (수상) | FastAPI · React · Ollama/Vertex Gemini · ChromaDB RAG · Redis |

---

## 🔍 01_CAD · CAD Vision — AI 산업 도면 검색/분류 엔진

> **"필요한 도면을 찾는 데 30분~2시간" 걸리던 제조업 도면 검색을, 멀티모달 AI로 1분 이내로 단축한다.**
> *(DrawingLLM — Engineering Drawing Retrieval & Classification powered by Open-Source LLM, v5.6)*

| 항목 | 내용 |
|------|------|
| **문제** | 제조업 도면 검색 비효율(평균 30분~2시간), 비표준 분류 체계, 숙련자 퇴직 시 지식 단절 |
| **데이터** | 9개 소스 · 산업용 도면 **68,649건** (PNG/DXF) |
| **접근** | 멀티모달 RAG + 다중 VLM 파이프라인 — 이미지/텍스트/구조 3채널 하이브리드 검색 |
| **분류 모델** | YOLO-cls v2 — 81 카테고리 · Top-1 **93.87%** / Top-5 **98.04%** |
| **구조 검색** | GNN(GIN) — DXF를 그래프로 임베딩 · R@1 **0.614** / R@5 **0.765** / R@10 **0.827** |
| **이미지 검색** | OpenCLIP ViT-L/14 Fine-tune — Image→Text R@5 **11.6%** (파인튜닝으로 16배 향상) |
| **영역 탐지** | YOLO-det — 표제란·부품표·치수 영역, mAP50 **0.552** |
| **벡터 검색** | ChromaDB 3채널(image 61,475 · text 68,649 · gnn 61,454) + Cross-encoder Reranker |
| **LLM 분석** | Ollama Gemma 4 / Qwen3.5 (RAM 기반 자동·수동 선택) · 컨텍스트 주입 + HallucinationDetector 환각 검증 |
| **백엔드/프론트** | FastAPI(25+ EP · SSE 스트리밍) · Next.js 16 + React 19 + Tailwind v4(7페이지) + Three.js 3D 뷰어 / Streamlit(Legacy) |
| **Multi-CAD** | DWG(ODA) · STEP(CadQuery) · IGES(OCP) · STL 포맷 지원 |
| **배포 · 품질** | Docker Compose 3-서비스 · **845 tests passing** · 검색 시간 **~95% 단축** |

**포트폴리오 포인트** — 5종 모델(YOLO-cls/det·OpenCLIP·GNN·OCR) 역할별 조합 · DXF를 **그래프(GNN)로 구조 유사도 검색** · LLM **환각 검증** 설계 · 모델링→FastAPI→Next.js→Docker **풀스택 + MLOps 완주**

📂 [01_CAD](./01_CAD) · 📄 [상세 README](./01_CAD/README.md) · 📄 [기획·문제정의 Spec](./01_CAD/app/PROJECT_SPEC.md)

---

## 🏥 02_MediWay — 병원 동선 안내 + 고령자 접근성 웹앱

> **병원에서 길을 잃는 환자·고령자를 위한 동선 안내 서비스 — 단일 병원 데모에서 멀티테넌트 SaaS로 진화 중.**

| 항목 | 내용 |
|------|------|
| **문제 / 대상** | 대형 병원 길찾기 어려움 · 방문 동선 관리 부재 / 환자·보호자(고령자) · 의료진 · 관리자 |
| **v1.0 핵심** | QR 익명 세션(24h TTL) · **Dijkstra 길찾기**(4개 층·30+ POI) · 방문 계획 공유 · 스태프 코드 초대 · 관리자 콘솔 |
| **인증·보안** | 이메일 + Kakao·Naver·Google OAuth(Cloud Functions) · RBAC · RTDB Security Rules 데이터 격리 |
| **기술 스택** | React 18 · TypeScript · Vite · Tailwind · Zustand · Leaflet · react-hook-form+zod · Firebase(RTDB·Auth·Functions `asia-northeast3`) · Vitest |

**현재까지 작업 현황 (PlusUltra v2.0 — `mediway/plusultra/*` 브랜치, 35 pages·91 components)**

| Phase | 작업 내용 |
|-------|----------|
| **P1 · Multi-Tenant** | 멀티테넌트 SaaS 전환 — `/h/:slug` 테넌트 라우팅 · 런타임 화이트라벨 테마(CSS custom props) · Custom Claims Functions · hospitalId 기반 보안 규칙 · 플랫폼 관리자 콘솔 |
| **P2 · 접근성** | **고령자 모드 full-scale** · WAI-ARIA 탭 키보드 내비게이션 |
| **P3 · 동선 확장** | 주차 어댑터 · 입원/검진 실내 동선 |
| **P4 · Polish** | 고령자 모드·**TTS 음성 안내**·**응급 버튼** polish · 방문계획 데이터 정규화 |
| **P4.U · 시니어 UX** | SeniorHome 4-타일 런처 · 가족 연락 · 데스크톱 2컬럼 홈 · 시안 톤 컬러 마이그레이션 |

**포트폴리오 포인트** — 헬스케어 + **접근성(a11y) 엔지니어링**(고령자 모드·TTS·응급버튼·WAI-ARIA) · 단일 데모 → **멀티테넌트 SaaS + 화이트라벨** 확장 · Firebase Custom Claims로 **테넌트 데이터 격리**

📂 [02_MediWay](./02_MediWay) · 📄 [상세 README](./02_MediWay/README.md) · 📄 [Phase 스펙(A~G)](./02_MediWay/mediway/docs)

---

## 🍋 03_lemon_healthcare — Lemon Healthcare (건강의신)

> **영양제 라벨 사진 한 장과 식단 정보로, 부족 영양소·권장량·체중 예측·운동 권고·목적별 분석 5가지를 한 번에 제공하는 AI 헬스케어 플랫폼.**
> *(주)레몬헬스케어 발주 · 경북대학교 AI/빅데이터 전문가 양성 과정 협업 프로젝트*

| 항목 | 내용 |
|------|------|
| **대상** | 만성질환 관리자(1차) · 예방 단계 직장인(2차) — 영양제·식단·활동 통합 맞춤 관리 |
| **핵심 출력** | ① 부족 영양소 추천 ② 영양 권장량 ③ 체중 변화 예측 ④ 운동 권고 ⑤ 목적별(눈/간/피로) 분석 — **5종 통합** |
| **차별점** | LDB(130여 의료기관) 연계 가능성 · **만성질환 v4 가중 알고리즘** · KDRIs·식약처 공식 데이터 · 770만+ 사용자 베이스(청구의신) |
| **백엔드** | Python 3.11 · FastAPI · PostgreSQL 16 · **TimescaleDB**(시계열 건강데이터) · Redis · Docker Compose |
| **AI / 데이터** | Google Cloud Vision OCR(영양제 라벨) · **Ollama 로컬 LLM** · KDRIs 영양 권장량 데이터 |
| **모바일** | **Flutter 3.24** · Apple HealthKit · Google Health Connect 연동 |
| **상태** | 개발 진행 중 (Phase 0~4) · `yeong-Vision-Nutrition`이 활성 산출물, `pr2`·`pr3`는 후속 기업 과제 placeholder |

**포트폴리오 포인트** — **기업 발주 실무 협업** · 영양제 라벨 **OCR → 멀티모달 분석 파이프라인** · 임상 가중 알고리즘 기반 만성질환 특화 · FastAPI + Flutter + TimescaleDB **풀스택 모바일 헬스케어**

📂 [03_lemon_healthcare](./03_lemon_healthcare) · 📄 [건강의신 README](./03_lemon_healthcare/yeong-Vision-Nutrition/README.md)

---

## 🏭 04_AJIN — AJIN Compliance · 제조 도메인 AI 통합 어시스턴트

> **"650명 직원의 모든 업무 흐름 — 직원 검색 / 문서 작성 / 온보딩 / 법규 모니터링 / 인사 관리 / 설비 SPC — 을 한 화면에서 처리하는 AI 통합 콘솔."**
> *아진산업(KOSDAQ 013310) 사내 어시스턴트 · 2026 KNU × 아진산업 SILLI 경진대회(DX 부문) 제출작 — 🏆 인기상 수상*

| 항목 | 내용 |
|------|------|
| **도메인** | 자동차 부품 제조(현대·기아 협력사) — 27 부서 × 6 사업장 × 6 해외법인 |
| **6개 기능** | A.검색 · B.문서작성 · C.챗봇 · D.법규 모니터링 · E.인사관리 · F.설비 SPC |
| **API 규모** | FastAPI OpenAPI **215 paths / 229 endpoints** · JWT + RBAC + 감사 로깅 |
| **LLM 라우터** | Ollama(qwen3.5 · exaone-deep · gemma4) ↔ Vertex AI Gemini(`asia-northeast3`, 학습 미사용 보장) 런타임 전환 |
| **법규 자동화** | 산안법·관세·MSDS·ISO·OEM 품질·EU CBAM 등 한국 법규 변경 자동 모니터링 |
| **데이터** | SQLite 15+ DB(도메인별) · **ChromaDB RAG**(규제 본문·매뉴얼·판례·계약 인덱싱) · Redis(LLM 응답 캐시) |
| **프론트엔드** | React + Vite + TypeScript + Zustand + Plotly (6 Feature 라우트) |
| **인프라** | Cloud Run · Firebase Hosting · Supabase · Docker (Celery/Postgres/Supabase compose 구성) |
| **상태** | 포트폴리오 아카이브 — 대회 종료 후 운영 환경 정리(라이브 비활성), 화면은 [`uiux/`](./04_AJIN/uiux) 스크린샷·디자인 시스템으로 확인 |

**포트폴리오 포인트** — **6개 도메인 215 엔드포인트** 대규모 API surface 설계 · **로컬 LLM ↔ 클라우드 Gemini 하이브리드 라우터** · 법규 RAG 자동 모니터링 · 실제 제조 대기업 도메인 기반 경진대회 **수상작**

📂 [04_AJIN](./04_AJIN) · 📄 [상세 README](./04_AJIN/README.md) · 🎬 [데모 스크립트](./04_AJIN/DEMO_SCRIPT.md)

---

## 🧰 종합 기술 스택

| 영역 | 기술 |
|------|------|
| **언어** | Python 3.11 · TypeScript 5~6 · Dart(Flutter) |
| **딥러닝 · CV** | PyTorch · YOLOv8(cls/det) · OpenCLIP ViT-L/14 · PaddleOCR · Google Cloud Vision |
| **GNN** | PyTorch Geometric · GIN (Graph Isomorphism Network) |
| **검색 · RAG** | ChromaDB(다채널 벡터DB) · E5-multilingual · Cross-encoder Reranker · 멀티모달 RAG |
| **LLM** | Ollama(qwen3.5 · exaone · gemma4) · Vertex AI Gemini · 하이브리드 라우터 · 환각 검증 |
| **백엔드** | FastAPI(REST·SSE·OpenAPI) · Firebase(RTDB·Auth·Functions) · PostgreSQL · TimescaleDB · Redis · SQLite |
| **프론트엔드 · 모바일** | Next.js 16 · React 18/19 · Tailwind · Three.js · Vite · Zustand · Leaflet · Flutter |
| **인프라 · 품질** | Docker Compose · Cloud Run · Firebase Hosting · Supabase · pytest(845) · Vitest · RBAC · Security Rules |

---

## 🔗 링크

| | |
|------|------|
| **이 레포** | 기업 발주·경진대회·자기주도 심화 프로젝트 (CAD Vision · MediWay · Lemon Healthcare · AJIN) |
| **KDT 12기 포트폴리오** | [HorangEe02/KNU_KDT_12th](https://github.com/HorangEe02/KNU_KDT_12th) — 13개 과정 프로젝트 |
| **Notion 포트폴리오** | [바로가기](https://www.notion.so/31879104c6f38039a53cfaa4b64ef712) |
| **Email** | catlife9029@gmail.com |

---

> 📌 데이터·모델 가중치(`.pt`)·벡터DB·3D 스캔·운영 시크릿 등 대용량/민감 자산은 저장소에 포함되지 않습니다.
> 각 프로젝트 폴더의 상세 README에 실행 방법과 아키텍처가 정리되어 있습니다.
