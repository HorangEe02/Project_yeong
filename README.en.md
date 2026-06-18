[한국어](./README.md) | **English**

# Junyeong Park · AI Engineering Project Portfolio

> **Production-grade AI projects — client-commissioned, competition, and self-directed**
>
> As a statistics-trained data scientist, alongside my KDT coursework ([KNU_KDT_12th](https://github.com/HorangEe02/KNU_KDT_12th)) I built
> a **multimodal AI search engine, a healthcare platform, and a manufacturing-domain AI assistant** —
> end to end from planning through modeling, backend, frontend, and deployment (solo or in collaboration).
> The goal is never just a model, but a **real, working product**.

| | |
|------|------|
| **Author** | Junyeong Park (박준영) · B.S. in Statistics, Keimyung University |
| **GitHub** | [github.com/HorangEe02](https://github.com/HorangEe02) |
| **Related portfolios** | [KDT Cohort 12 projects (13)](https://github.com/HorangEe02/KNU_KDT_12th) · [Notion Portfolio](https://www.notion.so/31879104c6f38039a53cfaa4b64ef712) |
| **AJIN static view** | [Vercel screen preview](https://dist-two-omega-62.vercel.app/) — frontend-only portfolio view without the production backend |

---

## 📦 Projects at a Glance

| # | Project | One-liner | Type | Core Tech |
|---|---------|----------|------|----------|
| **[01](#-01_cad--cad-vision--ai-industrial-drawing-searchclassification-engine)** | **CAD Vision** | A multimodal-RAG full-stack engine that classifies, searches, and analyzes industrial CAD drawings with AI | Self-directed | YOLO · OpenCLIP · GNN · ChromaDB · Ollama · FastAPI · Next.js |
| **[02](#-02_mediway--hospital-wayfinding--senior-accessibility-web-app)** | **MediWay** | In-hospital patient wayfinding + multi-tenant SaaS + senior-accessibility web app | Self-directed | React · TypeScript · Firebase · Dijkstra · WAI-ARIA |
| **[03](#-03_lemon_healthcare--lemon-healthcare-gunganguisin)** | **Lemon Healthcare** | An AI healthcare platform delivering 5 integrated health analyses from a single supplement-label photo (OCR) | Client-commissioned | FastAPI · Flutter · PostgreSQL/TimescaleDB · Cloud Vision · Ollama |
| **[04](#-04_ajin--ajin-compliance--manufacturing-domain-ai-assistant)** | **AJIN Compliance** | An AI console that handles 6 business domains for 650 employees of a manufacturer in one screen · [static view](https://dist-two-omega-62.vercel.app/) | Competition (awarded) | FastAPI · React · Ollama/Vertex Gemini · ChromaDB RAG · Redis |

---

## 🔍 01_CAD · CAD Vision — AI Industrial Drawing Search/Classification Engine

> **Cuts industrial drawing search from "30 min – 2 hrs" down to under 1 minute with multimodal AI.**
> *(DrawingLLM — Engineering Drawing Retrieval & Classification powered by Open-Source LLM, v5.6)*

| Item | Detail |
|------|------|
| **Problem** | Inefficient drawing search (avg. 30 min – 2 hrs), non-standard taxonomies, tacit-knowledge loss when veterans retire |
| **Data** | 9 sources · **68,649** industrial drawings (PNG/DXF) |
| **Approach** | Multimodal RAG + multi-VLM pipeline — 3-channel hybrid search (image / text / structure) |
| **Classification** | YOLO-cls v2 — 81 categories · Top-1 **93.87%** / Top-5 **98.04%** |
| **Structure search** | GNN (GIN) — embeds DXF as a graph · R@1 **0.614** / R@5 **0.765** / R@10 **0.827** |
| **Image search** | OpenCLIP ViT-L/14 fine-tuned — Image→Text R@5 **11.6%** (16× improvement via fine-tuning) |
| **Region detection** | YOLO-det — title block / BOM / dimension regions, mAP50 **0.552** |
| **Vector search** | ChromaDB 3-channel (image 61,475 · text 68,649 · gnn 61,454) + Cross-encoder Reranker |
| **LLM analysis** | Ollama Gemma 4 / Qwen3.5 (RAM-based auto/manual selection) · context injection + HallucinationDetector |
| **Backend/Frontend** | FastAPI (25+ endpoints · SSE streaming) · Next.js 16 + React 19 + Tailwind v4 (7 pages) + Three.js 3D viewer / Streamlit (legacy) |
| **Multi-CAD** | DWG (ODA) · STEP (CadQuery) · IGES (OCP) · STL |
| **Deploy · Quality** | Docker Compose 3-service · **845 tests passing** · ~**95%** search-time reduction |

**Highlights** — combines 5 models (YOLO-cls/det · OpenCLIP · GNN · OCR) by role · **graph-based (GNN) structural similarity search** of DXF · LLM **hallucination verification** · full-stack + MLOps end to end (modeling → FastAPI → Next.js → Docker)

📂 [01_CAD](./01_CAD) · 📄 [Detailed README](./01_CAD/README.md) · 📄 [Problem-definition spec](./01_CAD/app/PROJECT_SPEC.md)

---

## 🏥 02_MediWay — Hospital Wayfinding + Senior-Accessibility Web App

> **A wayfinding service for patients and seniors who get lost in hospitals — evolving from a single-hospital demo into a multi-tenant SaaS.**

| Item | Detail |
|------|------|
| **Problem / Users** | Hard to navigate large hospitals · no visit-route management / patients & guardians (seniors) · staff · admins |
| **v1.0 core** | QR anonymous session (24h TTL) · **Dijkstra wayfinding** (4 floors · 30+ POI) · shared visit plans · staff-code invites · admin console |
| **Auth · Security** | Email + Kakao·Naver·Google OAuth (Cloud Functions) · RBAC · RTDB Security Rules data isolation |
| **Stack** | React 18 · TypeScript · Vite · Tailwind · Zustand · Leaflet · react-hook-form+zod · Firebase (RTDB·Auth·Functions `asia-northeast3`) · Vitest |

**Progress so far (PlusUltra v2.0 — `mediway/plusultra/*` branches, 35 pages · 91 components)**

| Phase | Work |
|-------|----------|
| **P1 · Multi-Tenant** | SaaS conversion — `/h/:slug` tenant routing · runtime white-label theme (CSS custom properties) · Custom Claims Functions · hospitalId-based security rules · platform-admin console |
| **P2 · Accessibility** | **Full-scale senior mode** · WAI-ARIA tab keyboard navigation |
| **P3 · Route expansion** | Parking adapter · inpatient/checkup indoor routes |
| **P4 · Polish** | Senior mode · **TTS voice guidance** · **emergency button** polish · visit-plan data normalization |
| **P4.U · Senior UX** | SeniorHome 4-tile launcher · family contacts · desktop 2-column home · cyan color-system migration |

**Highlights** — healthcare + **accessibility (a11y) engineering** (senior mode · TTS · emergency button · WAI-ARIA) · single demo → **multi-tenant SaaS + white-label** · **tenant data isolation** via Firebase Custom Claims

📂 [02_MediWay](./02_MediWay) · 📄 [Detailed README](./02_MediWay/README.md) · 📄 [Phase specs (A–G)](./02_MediWay/mediway/docs)

---

## 🍋 03_lemon_healthcare — Lemon Healthcare (건강의신)

> **From a single supplement-label photo plus diet info, delivers 5 analyses at once: nutrient-gap recommendations, recommended intake, weight-change prediction, exercise guidance, and goal-specific (eye/liver/fatigue) analysis.**
> *Commissioned by Lemon Healthcare Inc. · collaboration with the Kyungpook Nat'l Univ. AI/Big Data program*

| Item | Detail |
|------|------|
| **Users** | Chronic-condition managers (primary) · prevention-stage office workers (secondary) — integrated supplement/diet/activity care |
| **Core outputs** | ① nutrient-gap recommendation ② recommended intake ③ weight-change prediction ④ exercise guidance ⑤ goal-specific (eye/liver/fatigue) analysis — **5 integrated** |
| **Differentiators** | LDB (130+ medical institutions) linkage potential · **chronic-disease v4 weighting algorithm** · official KDRIs / MFDS data · 7.7M+ user base (Cheonggu-uisin) |
| **Backend** | Python 3.11 · FastAPI · PostgreSQL 16 · **TimescaleDB** (time-series health data) · Redis · Docker Compose |
| **AI / Data** | Google Cloud Vision OCR (supplement labels) · **Ollama local LLM** · KDRIs nutrient-intake data |
| **Mobile** | **Flutter 3.24** · Apple HealthKit · Google Health Connect |
| **Status** | In development (Phase 0–4) · `yeong-Vision-Nutrition` is the active deliverable; `pr2`/`pr3` are placeholders for follow-on client tasks |

**Highlights** — **real client-commissioned collaboration** · supplement-label **OCR → multimodal analysis pipeline** · chronic-disease-specific clinical weighting · full-stack mobile healthcare (FastAPI + Flutter + TimescaleDB)

📂 [03_lemon_healthcare](./03_lemon_healthcare) · 📄 [건강의신 README](./03_lemon_healthcare/yeong-Vision-Nutrition/README.md)

---

## 🏭 04_AJIN — AJIN Compliance · Manufacturing-Domain AI Assistant

> **"An AI console that handles every workflow for 650 employees — staff search / document drafting / onboarding / regulatory monitoring / HR / equipment SPC — on one screen."**
> *In-house assistant for AJIN Industries (KOSDAQ 013310) · 2026 KNU × AJIN SILLI competition (DX track) submission — 🏆 Popularity Award*

| Item | Detail |
|------|------|
| **Domain** | Auto-parts manufacturing (Hyundai·Kia supplier) — 27 depts × 6 sites × 6 overseas subsidiaries |
| **6 features** | A. search · B. drafting · C. chatbot · D. regulatory monitoring · E. HR · F. equipment SPC |
| **API scale** | FastAPI OpenAPI **215 paths / 229 endpoints** · JWT + RBAC + audit logging |
| **LLM router** | Ollama (qwen3.5 · exaone-deep · gemma4) ↔ Vertex AI Gemini (`asia-northeast3`, no-training guarantee) runtime switch |
| **Regulatory automation** | Auto-monitoring of Korean regulations — OSHA·customs·MSDS·ISO·OEM quality·EU CBAM, etc. |
| **Data** | 15+ SQLite DBs (per domain) · **ChromaDB RAG** (regulations·manuals·precedents·contracts) · Redis (LLM cache) |
| **Frontend** | React + Vite + TypeScript + Zustand + Plotly (6 feature routes) |
| **Infra** | Cloud Run · Firebase Hosting · Supabase · Docker (Celery/Postgres/Supabase compose) |
| **Status** | Portfolio archive — cost-incurring production backend resources (Cloud Run/Firebase rewrites/DB/Storage/LLM) are decommissioned; UI is previewable through the [static Vercel deployment](https://dist-two-omega-62.vercel.app/) and [`uiux/`](./04_AJIN/uiux) screenshots/design system |

**Highlights** — large **215-endpoint API surface** across 6 domains · **local-LLM ↔ cloud-Gemini hybrid router** · regulatory RAG auto-monitoring · **award-winning** entry grounded in a real manufacturing enterprise

📂 [04_AJIN](./04_AJIN) · 🌐 [Static view](https://dist-two-omega-62.vercel.app/) · 📄 [Detailed README](./04_AJIN/README.md) · 🎬 [Demo script](./04_AJIN/DEMO_SCRIPT.md)

---

## 🧰 Combined Tech Stack

| Area | Technologies |
|------|------|
| **Languages** | Python 3.11 · TypeScript 5~6 · Dart (Flutter) |
| **Deep learning · CV** | PyTorch · YOLOv8 (cls/det) · OpenCLIP ViT-L/14 · PaddleOCR · Google Cloud Vision |
| **GNN** | PyTorch Geometric · GIN (Graph Isomorphism Network) |
| **Search · RAG** | ChromaDB (multi-channel vector DB) · E5-multilingual · Cross-encoder Reranker · multimodal RAG |
| **LLM** | Ollama (qwen3.5 · exaone · gemma4) · Vertex AI Gemini · hybrid router · hallucination verification |
| **Backend** | FastAPI (REST·SSE·OpenAPI) · Firebase (RTDB·Auth·Functions) · PostgreSQL · TimescaleDB · Redis · SQLite |
| **Frontend · Mobile** | Next.js 16 · React 18/19 · Tailwind · Three.js · Vite · Zustand · Leaflet · Flutter |
| **Infra · Quality** | Docker Compose · Cloud Run · Firebase Hosting · Supabase · pytest (845) · Vitest · RBAC · Security Rules |

---

## 🔗 Links

| | |
|------|------|
| **This repo** | Client-commissioned, competition, and self-directed projects (CAD Vision · MediWay · Lemon Healthcare · AJIN) |
| **KDT Cohort 12 portfolio** | [HorangEe02/KNU_KDT_12th](https://github.com/HorangEe02/KNU_KDT_12th) — 13 course projects |
| **Notion portfolio** | [Open](https://www.notion.so/31879104c6f38039a53cfaa4b64ef712) |
| **Email** | catlife9029@gmail.com |

---

> 📌 Large/sensitive assets — data, model weights (`.pt`), vector DBs, 3D scans, production secrets — are not included in the repository.
> Each project folder contains its own detailed README with setup and architecture.
