# CAD Vision v5.6 — AI Drawing Search Engine

산업용 CAD 도면을 AI로 분류 · 검색 · 분석하는 풀스택 시스템

## Overview

| 항목 | 내용 |
|------|------|
| **데이터** | 9개 소스, 68,649건 산업용 도면 (PNG/DXF) |
| **분류** | YOLO-cls v2 — 81 카테고리, Top-1 **93.87%** |
| **검색** | 3채널 하이브리드: OpenCLIP(0.1) + E5(0.6) + GNN(0.3) |
| **GNN** | GIN 구조 검색 — DXF 그래프 임베딩, R@5 = **0.765** |
| **벡터DB** | ChromaDB 3채널 — image 61,475 / text 68,649 / gnn 61,454 |
| **탐지** | YOLO-det mAP50 = 0.552 |
| **분석** | Ollama Gemma 4 / Qwen3.5 (RAM+설치 모델 자동 선택, 수동 전환 가능) |
| **Reranker** | Cross-encoder 2차 정밀 정렬 |
| **Backend** | FastAPI REST API (25+ 엔드포인트) |
| **Frontend** | React (Next.js 16 + Tailwind v4) + Streamlit (Legacy) |
| **배포** | Docker Compose (app + ollama, ChromaDB 임베디드) |
| **테스트** | 540+ tests |

## Architecture

```
                        ┌─────────────────────────────────┐
                        │         CAD Vision v5.6          │
                        └─────────────┬───────────────────┘
                                      │
        ┌─────────────┬───────────────┼───────────────┬─────────────┐
        ▼             ▼               ▼               ▼             ▼
   YOLO-cls      OpenCLIP        PaddleOCR       GNN (GIN)     YOLO-det
   (81 cat)    ViT-L/14 768d    텍스트 추출    DXF→Graph→256d   영역 탐지
        │             │               │               │             │
        └─────────────┴───────┬───────┴───────────────┘             │
                              ▼                                     │
                    ChromaDB 3채널 벡터 DB                           │
                  (image + text + gnn)                              │
                              │                                     │
                              ▼                                     │
                   Reranker (Cross-Encoder)                         │
                              │                                     │
                              ▼                                     ▼
              Ollama Gemma4/Qwen3.5 LLM  ◄──────── 컨텍스트 주입
              (스트리밍 응답, 언어 선택)     (YOLO/OCR/탐지 결과)
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
        React (Next.js)  Streamlit UI    FastAPI REST
        :3000            :8501           :8000/docs
```

## v5.5~v5.6 New Features

### v5.6: AI Language + IGES
- **AI 응답 언어 선택**: Settings에서 English / 한국어 / Both 전환
- **IGES 2D 와이어프레임 감지**: 3D 변환 불가 시 명확한 안내 메시지
- **IGES → STL 변환 개선**: BRepMesh + CadQuery exportStl fallback

### v5.5: React Frontend + Dark/Light Mode
- **React 프론트엔드**: Next.js 16 + React 19 + Tailwind v4 (7페이지)
- **다크/라이트 모드**: next-themes + CSS 변수, Settings에서 전환
- **3D 뷰어**: react-three-fiber (STL/STEP/IGES), 줌 +/- 버튼
- **LLM 모델 수동 선택**: Settings에서 Gemma 4 / Qwen3.5 전환
- **카테고리 드롭다운**: Tools에서 카테고리→도면 캐스케이딩 선택
- **DXF Diff 상세 결과**: 일치율 %, 해석 가이드, 레이어/요약 표시

### v5.4: Core Architecture Integration
- **6개 통합 엔진**: CAD Router, Unified Search, VLM Orchestrator, Comparison Engine, Universal Renderer, Models
- **Multi-CAD 포맷**: DWG(ODA), STEP(CadQuery), IGES(OCP), STL(numpy-stl)
- **UI/UX 리디자인**: Engineering Terminal 다크 테마

### v5.0~v5.3: REST API + Docker
- **FastAPI**: 25+ REST 엔드포인트, SSE 스트리밍, Rate Limiting
- **Docker Compose**: 2-서비스 배포 (app·ollama)
- **DXF Reranker**: 구조 검색 후처리 리랭킹
- **한/영 동의어 사전**: 140+ 기계부품 동의어

## Project Structure

```
01_CAD/
├── app/                        # 메인 애플리케이션
│   ├── app/                    # Streamlit UI + FastAPI
│   │   ├── streamlit_app.py    # Streamlit 풀스택 UI (Legacy)
│   │   └── api/                # FastAPI REST API
│   │       ├── routers/        # 9개 라우터
│   │       └── schemas.py      # Pydantic 스키마
│   ├── config/settings.py      # 전역 설정 (Gemma4/Qwen3.5 자동선택)
│   ├── core/                   # 핵심 엔진 (20+ 모듈)
│   ├── scripts/                # 유틸리티 스크립트
│   ├── tests/                  # 540+ 테스트
│   ├── docs/                   # 가이드 문서
│   ├── CHANGELOG.md            # v4.0 → v5.6 전체 변경 이력
│   └── README.md               # 상세 README
├── web/                        # React 프론트엔드 (v5.5+)
│   ├── src/app/                # Next.js 16 App Router (7페이지)
│   ├── src/components/         # UI 컴포넌트 (20+)
│   └── src/lib/                # API 클라이언트, 타입
├── training/                   # 학습 파이프라인
└── data/                       # 카테고리 매핑 메타데이터
```

## Key Results

| 모델 | 지표 | 성능 |
|------|------|------|
| YOLO-cls v2 | 81 카테고리, Top-1 / Top-5 | **93.87%** / **98.04%** |
| GNN (GIN) v2 | R@1 / R@5 / R@10 | **0.614** / **0.765** / **0.827** |
| OpenCLIP Fine-tune | Image→Text R@5 | **11.6%** (16x 향상) |
| 메타데이터 | 부품번호 / 재질 | 60,456건 / 60,721건 |

## Tech Stack

| 영역 | 기술 |
|------|------|
| Language | Python 3.11 + TypeScript 5 |
| Deep Learning | PyTorch, YOLO, OpenCLIP ViT-L/14, E5-multilingual-small |
| GNN | PyTorch Geometric, GIN (Graph Isomorphism Network) |
| Vector DB | ChromaDB (3-channel: image/text/gnn) |
| OCR | PaddleOCR |
| LLM | Ollama + Gemma 4 / Qwen3.5 (auto/manual selection) |
| Reranker | Cross-encoder (ms-marco-MiniLM-L-6-v2) |
| Backend | FastAPI (25+ endpoints) |
| Frontend (New) | Next.js 16 + React 19 + Tailwind v4 + Three.js |
| Frontend (Legacy) | Streamlit (Engineering Terminal theme) |
| Deploy | Docker Compose (3 services) |
| Testing | pytest (540+ tests) |

## Quick Start

```bash
# 1. 백엔드 (FastAPI)
cd app
pip install -r requirements.txt
python run_api.py --port 8000

# 2. React 프론트엔드 (v5.5+)
cd web
npm install
npm run dev    # → http://localhost:3000

# 3. Streamlit (Legacy)
cd app
streamlit run app/streamlit_app.py --server.port 8501

# Docker
cd app
./docker-start.sh            # 빌드 + 시작
./docker-start.sh --down     # 종료
```

## Documentation

- [`app/README.md`](app/README.md) — 메인 앱 상세 README (v5.6)
- [`app/CHANGELOG.md`](app/CHANGELOG.md) — 전체 변경 이력 (v4.0 → v5.6)
- [`app/docs/GUIDE_DEVELOPER.md`](app/docs/GUIDE_DEVELOPER.md) — 개발자 가이드
- [`app/docs/GUIDE_USER.md`](app/docs/GUIDE_USER.md) — 사용자 가이드
- [`web/README.md`](web/README.md) — React 프론트엔드 가이드
- [`training/PROJECT_GUIDE.md`](training/PROJECT_GUIDE.md) — 학습 파이프라인 가이드

## Note

> 이미지 데이터, 모델 가중치(`.pt`), 벡터DB는 저작권 및 용량 문제로 포함되지 않습니다.
> 모델과 데이터는 별도 준비가 필요합니다.

---

**v5.6** | 2026-04-06
