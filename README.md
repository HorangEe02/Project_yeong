**한국어** | [English](./README.en.md)

# 박준영 · AI Engineering Project Portfolio

> **기업 발주 · 경진대회 · 자기주도로 설계·구현한 실무급 AI 프로젝트 모음**
>
> 통계학 기반 데이터 사이언티스트로서, KDT 교육 과정([KNU_KDT_12th](https://github.com/HorangEe02/KNU_KDT_12th))과 별개로
> **멀티모달 AI 검색 엔진 · 헬스케어 플랫폼 · 제조 도메인 AI 어시스턴트 · 온디바이스 음성 AI**를
> 기획부터 모델링·백엔드·프론트엔드·배포까지 단독/협업으로 구축했습니다.
> 모델을 만드는 데 그치지 않고 **실제 동작하는 제품**으로 완성하는 것을 목표로 합니다.

| | |
|------|------|
| **작성자** | 박준영 (Junyeong Park) · 계명대학교 통계학과 졸업 |
| **GitHub** | [github.com/HorangEe02](https://github.com/HorangEe02) |
| **연관 포트폴리오** | [KDT 12기 프로젝트 (13선)](https://github.com/HorangEe02/KNU_KDT_12th) · [Notion 포트폴리오](https://www.notion.so/31879104c6f38039a53cfaa4b64ef712) |
| **AJIN 정적 화면** | [Vercel 화면 열람](https://dist-two-omega-62.vercel.app/) — 운영 백엔드 없이 포트폴리오 화면만 확인 |

---

## 📦 프로젝트 한눈에

| # | 프로젝트 | 한 줄 소개 | 성격 | 핵심 기술 |
|---|---------|----------|------|----------|
| **[01](#-01_cad--cad-vision--ai-산업-도면-검색분류-엔진)** | **CAD Vision** | AI로 산업용 CAD 도면을 분류·검색·분석하는 멀티모달 RAG 풀스택 엔진 | 자기주도 심화 | YOLO · OpenCLIP · GNN · ChromaDB · Ollama · FastAPI · Next.js |
| **[02](#-02_mediway--병원-동선-안내--고령자-접근성-웹앱)** | **MediWay** | 병원 내 환자 동선 안내 + 멀티테넌트 SaaS + 고령자 접근성 웹앱 | 자기주도 심화 | React · TypeScript · Firebase · Dijkstra · WAI-ARIA |
| **[03](#-03_lemon_healthcare--lemon-aid-음식--영양제-ai-분석-서비스-플랫폼)** | **Lemon AID** | 음식·영양제 라벨·활동 데이터를 통합 분석하는 AI 건강관리 서비스 플랫폼 | 기업 발주 협업 | FastAPI · Flutter · PostgreSQL/TimescaleDB · Cloud Vision · Ollama |
| **[04](#-04_ajin--ajin-compliance--제조-도메인-ai-통합-어시스턴트)** | **AJIN Compliance** | 제조 대기업 650명의 6개 업무 도메인을 한 화면에서 처리하는 AI 통합 콘솔 · [정적 화면 보기](https://dist-two-omega-62.vercel.app/) | 경진대회 (수상) | FastAPI · React · Ollama/Vertex Gemini · ChromaDB RAG · Redis |
| **[05](#-05_lemon-note--lemon-note--로컬-우선-ai-회의록)** | **Lemon-note** | 녹음 → 화자구분 전사 → 요약·일정 추출까지 전 과정을 로컬에서 처리하는 **런타임 비용 $0** AI 회의록 | 자기주도 심화 | faster-whisper · sherpa-onnx · Ollama(gemma4/qwen3.5) · FastAPI · SQLite/Supabase |

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
| **배포 · 품질** | Docker Compose 2-서비스(app·ollama, ChromaDB 임베디드) · **540+ tests** · 검색 시간 **~95% 단축** |

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

**현재까지 작업 현황 (PlusUltra v2.0 — ⚠️ main 미병합, `mediway/plusultra/*` 브랜치에서 진행 중 · 35 pages·91 components)**

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

## 🍋 03_lemon_healthcare — Lemon AID (음식 · 영양제 AI 분석 서비스 플랫폼)

> **음식·영양제 라벨·활동 데이터를 통합 분석해 부족 영양소·권장량·체중 예측·운동 권고·목적별 분석 5가지를 한 번에 제공하는 AI 건강관리 서비스 플랫폼.**
> *(주)레몬헬스케어 발주 · 경북대학교 AI/빅데이터 전문가 양성 과정 협업 프로젝트*

| 항목 | 내용 |
|------|------|
| **대상** | 만성질환 관리자(1차) · 예방 단계 직장인(2차) — 음식·영양제·활동 통합 맞춤 관리 |
| **핵심 출력** | ① 부족 영양소 추천 ② 영양 권장량 ③ 체중 변화 예측 ④ 운동 권고 ⑤ 목적별(눈/간/피로) 분석 — **5종 통합** |
| **차별점** | 바코드 검색 중심 등록과 DB 매칭 의존도를 낮추고, 영양제 라벨 OCR·LLM 파싱과 음식/활동 데이터 통합 분석으로 건강관리 의사결정 흐름 연결 |
| **백엔드** | Python 3.11 · FastAPI · PostgreSQL 16 · **TimescaleDB**(시계열 건강데이터) · Redis · Docker Compose |
| **AI / 데이터** | Google Cloud Vision OCR(영양제 라벨) · **Ollama 로컬 LLM** 기반 라벨 파싱 · KDRIs 영양 권장량 · 식약처 데이터 표준화 |
| **모바일** | **Flutter 3.24** · Apple HealthKit · Google Health Connect 연동 |
| **상태** | 개발 진행 중 (Phase 0~4) · `Lemon-Aid`가 활성 산출물 |

**포트폴리오 포인트** — **기업 발주 실무 협업** · 영양제 라벨 **OCR → LLM 구조화 → 공식 데이터 검증** 파이프라인 · 음식·영양제·활동 정보를 연결하는 통합 건강분석 UX · FastAPI + Flutter + TimescaleDB **풀스택 모바일 헬스케어**

- **바코드 의존도 완화**: 바코드가 없거나 인식되지 않는 제품도 라벨 이미지 기반으로 성분·함량 후보 추출
- **데이터베이스 의존도 완화**: 식약처·KDRIs 데이터는 표준화/검증 기준으로 쓰고, 라벨 원문에서 직접 정보를 구조화
- **영양제 라벨 비특화 보완**: 영양성분표·섭취량·단위(mg, μg, IU 등)를 영양제 라벨 문맥에 맞게 정규화
- **정보 통합 어려움 해결**: 음식·영양제·활동·체중 정보를 5종 분석 결과로 연결

📂 [03_lemon_healthcare](./03_lemon_healthcare) · 📄 [Lemon AID README](./03_lemon_healthcare/Lemon-Aid/README.md)

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
| **상태** | 포트폴리오 아카이브 — 비용이 발생하는 운영 백엔드(Cloud Run/Firebase rewrite/DB/Storage/LLM)는 정리, 화면은 [정적 Vercel 배포](https://dist-two-omega-62.vercel.app/)와 [`uiux/`](./04_AJIN/uiux) 스크린샷·디자인 시스템으로 확인 |

**포트폴리오 포인트** — **6개 도메인 215 엔드포인트** 대규모 API surface 설계 · **로컬 LLM ↔ 클라우드 Gemini 하이브리드 라우터** · 법규 RAG 자동 모니터링 · 실제 제조 대기업 도메인 기반 경진대회 **수상작**

📂 [04_AJIN](./04_AJIN) · 🌐 [정적 화면 보기](https://dist-two-omega-62.vercel.app/) · 📄 [상세 README](./04_AJIN/README.md) · 🎬 [데모 스크립트](./04_AJIN/DEMO_SCRIPT.md)

---

## 🎙 05_lemon-note — Lemon-note · 로컬 우선 AI 회의록

> **"녹음하면 화자별로 전사하고, 발화를 클릭하면 그 지점부터 재생되며, 요약·일정 후보는 사람이 검토·수정한다 — 전부 로컬에서, 런타임 비용 $0으로."**
> *자기주도 설계·구현 — 요구사항 분석 → 설계 문서화 → 다차원 설계 리뷰 → 데모 MVP → 실제 로컬 모델 전환*

| 항목 | 내용 |
|------|------|
| **처리 흐름** | 녹음/업로드 → 오디오 정규화 → 화자구분 전사 → 구조화 요약 → 검토·수정 → 내보내기·Slack 공유 |
| **ASR** | **faster-whisper**(small/medium/large-v3) · PyAV 디코딩으로 **ffmpeg 불필요** · hotwords 보정 |
| **화자구분** | **sherpa-onnx**(오픈 모델, HF 토큰 불필요) · pyannote 옵션 · 발화 경계 겹침 기반 화자 배정 |
| **요약 LLM** | Ollama `gemma4:e4b` / `qwen3.5` — 결정사항·할 일·일정 후보를 **근거 발화(source segment)** 와 함께 구조화 JSON 생성. 추론모델의 `<think>` 제거·JSON 추출 견고화 |
| **Provider 추상화** | 전사·요약·저장·화자구분을 인터페이스로 분리 → `stub ↔ 실제 모델`, `로컬 ↔ 서버`를 **API·스키마 변경 없이** 교체 |
| **데이터** | SQLite(로컬 기본) / **Supabase Postgres 듀얼 백엔드**(psycopg native 타입) · 전 테이블 RLS · 원본 불변성 · 녹음 동의 · 감사 로그 · soft delete |
| **프론트엔드** | **Vanilla HTML/CSS/JS**(빌드·CDN 없이 오프라인 동작) · Figma 채팅 UI 키트 기반 — 전사를 화자별 말풍선으로 렌더링, 클릭 시 해당 구간 재생(Range 스트리밍) |
| **성능** | Apple M4 Pro 기준 48초 한국어 음성 → 전사 medium ≈19s + 요약 ≈10s (**전체 ≈31s**) |
| **상태** | 로컬 실행형 데모 — `./run.sh` 로 stub 즉시 실행(모델 다운로드 0), 환경변수만 바꿔 실제 모델 전환 |

**포트폴리오 포인트** — **완전 로컬·런타임 비용 0** 온디바이스 음성 AI 파이프라인 · **Provider 추상화**로 stub↔실모델↔서버 무변경 교체 · 자체 **다차원 설계 리뷰 20 findings**를 코드에 반영 · 음성 생체정보를 다루는 서비스의 동의·보존·감사 설계

📂 [05_lemon-note](./05_lemon-note) · 📄 [상세 README](./05_lemon-note/local-worker/README.md) · 📋 [설계 리뷰 20 findings](./05_lemon-note/docs/design-review-findings.md) · 🗂 [설계 문서](./05_lemon-note/docs)

---

## 🧰 종합 기술 스택

| 영역 | 기술 |
|------|------|
| **언어** | Python 3.11 · TypeScript 5~6 · Dart(Flutter) |
| **딥러닝 · CV** | PyTorch · YOLOv8(cls/det) · OpenCLIP ViT-L/14 · PaddleOCR · Google Cloud Vision |
| **GNN** | PyTorch Geometric · GIN (Graph Isomorphism Network) |
| **검색 · RAG** | ChromaDB(다채널 벡터DB) · E5-multilingual · Cross-encoder Reranker · 멀티모달 RAG |
| **LLM** | Ollama(qwen3.5 · exaone · gemma4) · Vertex AI Gemini · 하이브리드 라우터 · 환각 검증 · 추론모델 JSON 강제 |
| **음성 AI** | faster-whisper(CTranslate2 int8) · sherpa-onnx 화자구분(diarization) · pyannote · PyAV 오디오 디코딩 |
| **백엔드** | FastAPI(REST·SSE·OpenAPI) · Firebase(RTDB·Auth·Functions) · PostgreSQL · TimescaleDB · Redis · SQLite · Supabase(Postgres·RLS) |
| **프론트엔드 · 모바일** | Next.js 16 · React 18/19 · Tailwind · Three.js · Vite · Zustand · Leaflet · Flutter · Vanilla JS(무빌드) |
| **인프라 · 품질** | Docker Compose · Cloud Run · Firebase Hosting · Supabase · pytest(540+) · Vitest · RBAC · Security Rules |

---

## 🗂 저장소 구조 규약

| 폴더 | 하위 구조 |
|------|----------|
| `01_CAD` · `04_AJIN` | 프로젝트 콘텐츠를 번호 폴더 바로 아래 배치 |
| `02_MediWay` | 소개 README + 앱 본체 `mediway/` |
| `03_lemon_healthcare` | 소개 README + 기업 발주 산출물 `Lemon-Aid/` (산출물 폴더명은 협업 당시 명칭 유지) |
| `05_lemon-note` | 소개 README + 설계 문서 `docs/` + 앱 본체 `local-worker/` (FastAPI 워커 + `web/` 프론트) |

**라이선스** — 저장소 전체는 열람용 저작권 고지([LICENSE](./LICENSE)) 적용, `04_AJIN`은 자체 [MIT](./04_AJIN/LICENSE).

---

## 🔗 링크

| | |
|------|------|
| **이 레포** | 기업 발주·경진대회·자기주도 심화 프로젝트 (CAD Vision · MediWay · Lemon AID · AJIN · Lemon-note) |
| **KDT 12기 포트폴리오** | [HorangEe02/KNU_KDT_12th](https://github.com/HorangEe02/KNU_KDT_12th) — 13개 과정 프로젝트 |
| **Notion 포트폴리오** | [바로가기](https://www.notion.so/31879104c6f38039a53cfaa4b64ef712) |
| **Email** | catlife9029@gmail.com |

---

> 📌 데이터·모델 가중치(`.pt`)·벡터DB·3D 스캔·운영 시크릿 등 대용량/민감 자산은 저장소에 포함되지 않습니다.
> 각 프로젝트 폴더의 상세 README에 실행 방법과 아키텍처가 정리되어 있습니다.
