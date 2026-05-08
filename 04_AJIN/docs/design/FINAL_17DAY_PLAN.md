# 본선 최종 17일 통합 계획서 — 옵션 B (하이브리드) + Firebase 풀 통합

> **버전**: 1.0
> **작성일**: 2026-04-27
> **본선까지**: **17 작업일** (2026-04-27 ~ 2026-05-13)
> **데모 머신**: **MacBook Pro M4 Pro 24GB** (단일 머신 — 개발 + 데모 + LLM)
> **인터넷**: ✅ Wifi 확보
> **운영 규모**: 30명 (본선 후)

---

## 목차

1. [최종 결정 사항 요약](#1-최종-결정-사항-요약)
2. [MacBook Pro M4 Pro 환경 분석](#2-macbook-pro-m4-pro-환경-분석)
3. [최종 아키텍처](#3-최종-아키텍처)
4. [17일 Day-by-Day 일정](#4-17일-day-by-day-일정)
5. [Firebase 프로젝트 셋업 가이드](#5-firebase-프로젝트-셋업-가이드)
6. [LLM 모델 선택 + 메모리 최적화](#6-llm-모델-선택--메모리-최적화)
7. [Cloudflare Tunnel 설정](#7-cloudflare-tunnel-설정)
8. [데이터 시드 마이그레이션 전략](#8-데이터-시드-마이그레이션-전략)
9. [점진적 Firebase 통합 패턴](#9-점진적-firebase-통합-패턴)
10. [위험 요소 + 완화](#10-위험-요소--완화)
11. [본선 데모 시나리오 (15분)](#11-본선-데모-시나리오-15분)
12. [본선 후 30명 운영 로드맵](#12-본선-후-30명-운영-로드맵)

---

## 1. 최종 결정 사항 요약

### 사용자 결정 (2026-04-27)
| # | 항목 | 결정 |
|:--:|---|---|
| 1 | 아키텍처 | **옵션 B (하이브리드)** — Firebase 풀스택 + FastAPI 사내 |
| 2 | 일정 | **시나리오 3 (17일)** — Day 14~17 Firebase 풀 통합 |
| 3 | 데모 환경 | **MacBook Pro M4 Pro 24GB** (개발기 = 데모기 = LLM 호스트) |
| 4 | 인터넷 | **Wifi 확보** (Firebase / Cloudflare Tunnel 가능) |
| 5 | 운영 규모 | **30명** (본선 후 사내 사용자) |

### Firebase 통합 범위
- ✅ **Firebase Hosting**: React 정적 빌드
- ✅ **Firebase Auth**: 33 계정 + JWT + 6 RBAC
- ✅ **Firestore**: 구조 데이터 (12 컬렉션)
- ✅ **Realtime Database**: 실시간 알람/감사 로그/피드백
- ✅ **Firebase Storage**: 파일 (PDF/모델/이미지)
- ❌ Cloud Functions: 사용 안 함 (Ollama 호환성 X)

### MacBook 사이드 (FastAPI)
- FastAPI + Ollama + ChromaDB + 7 ML 모델 + 9 크롤러
- Cloudflare Tunnel로 HTTPS 노출 (`https://api-ajin.your-domain.com`)
- Firebase Admin SDK로 Firestore/RTDB 쓰기

---

## 2. MacBook Pro M4 Pro 환경 분석

### 2-1. M4 Pro 24GB 사양
| 항목 | 사양 |
|---|---|
| **CPU** | 12-core (8 perf + 4 eff) |
| **GPU** | 16-20 cores (M4 Pro 표준 16 / 상위 20) |
| **메모리** | **24GB Unified Memory** (CPU↔GPU 공유) |
| **가용 메모리 (실제)** | ~20GB (macOS + Chrome + Cursor + ... 약 4GB 점유) |
| **Metal 가속** | ✅ Ollama 자동 감지 |
| **CUDA** | ❌ (Metal 사용) |

### 2-2. Ollama 성능 추정 (M4 Pro 16-core GPU 기준)
| 모델 | 파라미터 | RAM 사용 | 토큰 속도 | 권장도 |
|---|:--:|:--:|:--:|:--:|
| **bge-m3** (임베딩) | 567M | 1.1GB | <100ms / 쿼리 | ✅ 필수 |
| **qwen3.5:9b** | 9B | 6.1GB | **30~50 tok/s** | ✅ 메인 LLM |
| **qwen3.5:4b** | 4B | 3.2GB | **60~90 tok/s** | 🟢 빠른 응답용 |
| **exaone3.5:7.8b** | 7.8B | 4.4GB | **35~55 tok/s** | ✅ 한국어 특화 |
| **gemma4:latest (8b)** | 8B | 8.9GB | **30~45 tok/s** | 🟢 비전 + 균형 |
| **gemma4:e2b (5b)** | 5B | 6.7GB | **40~60 tok/s** | ✅ 경량 비전 |
| **gemma4:26b** | 26B | 16.8GB | 8~15 tok/s | 🟡 메모리 압박 |
| **gpt-oss:20b** | 20B | 12.8GB | 12~20 tok/s | 🟡 고품질이지만 느림 |
| **nemotron-cascade-2** | 31B | 22.6GB | ❌ OOM 위험 | ❌ 사용 불가 |

### 2-3. 데모용 모델 조합 (24GB 안전 운용)

#### Configuration A: **빠른 응답 우선** (권장)
```
- bge-m3 (1.1GB) — 항상 로드 (RAG 임베딩)
- qwen3.5:9b (6.1GB) — 기본 LLM
- gemma4:e2b (6.7GB) — 비전 모델 (필요 시)
─────────────────────
합계: ~14GB (안전 마진 ~6GB)
```

#### Configuration B: **품질 우선** (시연용)
```
- bge-m3 (1.1GB)
- qwen3.5:9b (6.1GB)
- exaone3.5 (4.4GB)  # 한국어 응답 시 자동 전환
─────────────────────
합계: ~12GB (안전 마진 ~8GB)
```

#### Configuration C: **비전 + 한국어 풀스펙**
```
- bge-m3 (1.1GB)
- qwen3.5:4b (3.2GB) — 빠른 답변
- exaone3.5 (4.4GB) — 한국어
- gemma4:e2b (6.7GB) — 비전
─────────────────────
합계: ~15GB (안전 마진 ~5GB)
```

### 2-4. 모델 라우팅 정책 (LLM Multi-Provider Router)

```python
# core/llm_router.py (신규)
async def route_llm(prompt: str, mode: str, has_image: bool = False):
    # 1순위: Gemini API (인터넷 가능 시 + 빠름)
    if internet_available() and not has_image:
        try:
            return await gemini_call(prompt)
        except QuotaExceeded:
            pass
    
    # 2순위: 로컬 Ollama
    if has_image:
        return await ollama_call(prompt, model='gemma4:e2b')
    
    if mode == 'korean_priority':
        return await ollama_call(prompt, model='exaone3.5')
    
    if mode == 'fast_response':
        return await ollama_call(prompt, model='qwen3.5:4b')
    
    return await ollama_call(prompt, model='qwen3.5:9b')  # 기본
    
    # 3순위: LM Studio (Ollama 다운 시)
    if ollama_down():
        return await lm_studio_call(prompt)
```

### 2-5. 30명 동시 사용 가능성?
- **본선 데모 (3~5명)**: ✅ 충분
- **30명 동시 LLM**: ❌ 동시 1~2명만 가능 (10초 응답 → 큐잉)
- **30명 동시 검색·CRUD**: ✅ Firebase로 처리되므로 무관
- **30명 결론**: 본선 후 LLM은 **Cloud Run GPU** 또는 **사내 GPU 서버 추가** 필요

---

## 3. 최종 아키텍처

```
┌─────────────────────────────────────────────────────────────────────┐
│  사용자 (30명, 본선 후)                                             │
│  본선 무대: 5명 동시                                                │
└──────┬──────────────────────────────────────┬───────────────────────┘
       │                                      │
       │ HTTPS                                │ Wifi
       ▼                                      ▼
┌──────────────────────────────────────────────────────────────────────┐
│                Firebase (https://ajin-ai.web.app)                    │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Firebase Hosting    │  React + TypeScript + Vite (정적 빌드)        │
│  ─────────────────   │  ─ Liquid Glass + AJIN Sans + 한·영          │
│                                                                      │
│  Firebase Auth       │  33 계정 + JWT + Custom Claims (RBAC)         │
│  ─────────────────   │  ─ 비밀번호 정책 6 조건 + 5회 잠금            │
│                                                                      │
│  Firestore (12)      │  employees · accounts · departments · plants  │
│  ─────────────────   │  error_codes · molds · scenarios · documents  │
│                      │  glossary · sop_guides · regulations · stats  │
│                                                                      │
│  Realtime Database   │  /live_alarms · /audit_log · /presence        │
│  ─────────────────   │  /notifications · /feedback · /spc_realtime   │
│                                                                      │
│  Firebase Storage    │  /pdfs/ · /templates/ · /ml_models/ · /images/│
│                                                                      │
└──────────┬───────────────────────────────────────────────────────────┘
           │
           │ Firebase Admin SDK (서버↔Firebase)
           │ Firebase ID Token 검증
           ▼
┌──────────────────────────────────────────────────────────────────────┐
│  MacBook Pro M4 Pro 24GB                                             │
│  + Cloudflare Tunnel (https://api-ajin.your-domain.com)              │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  FastAPI (port 8000)                                                 │
│  ├─ /api/auth/* (Firebase ID Token 검증)                             │
│  ├─ /api/employee/search (FTS5 + ChromaDB RRF)                       │
│  ├─ /api/draft/generate (SSE + Few-shot RAG)                         │
│  ├─ /api/onboarding/chat (SSE + 멀티 LLM 라우터)                      │
│  ├─ /api/compliance/* (9 크롤러 + 시나리오)                           │
│  ├─ /api/equipment/* (TF-IDF + Markov + XGBoost + SPC)                │
│  └─ /api/admin/* (RBAC + 감사 로그 + 통계)                            │
│                                                                      │
│  Ollama (port 11434)                                                 │
│  ├─ bge-m3 (1.1GB) — RAG 임베딩                                       │
│  ├─ qwen3.5:9b (6.1GB) — 기본 LLM                                     │
│  ├─ exaone3.5 (4.4GB) — 한국어 특화                                   │
│  └─ gemma4:e2b (6.7GB) — 비전                                         │
│                                                                      │
│  ChromaDB (15MB)                                                     │
│  ├─ ajin_documents (사내 문서)                                        │
│  ├─ employee_profiles (329명)                                         │
│  ├─ draft_fewshot_samples (584건)                                     │
│  └─ glossary (297항목)                                                │
│                                                                      │
│  SQLite (FTS5 한국어 전문 검색만 유지)                                │
│  └─ employees_fts.db (사원 검색 인덱스)                               │
│                                                                      │
│  ML 모델 (joblib pickle 파일)                                         │
│  └─ Intent · Error TF-IDF · SPC IF · Mold XGB · Markov · DocQual     │
│                                                                      │
└──────────┬───────────────────────────────────────────────────────────┘
           │ 외부 API 호출
           ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Gemini 1.5 Pro / Vision API (1순위 LLM, 인터넷 의존)                │
└──────────────────────────────────────────────────────────────────────┘
```

### 3-1. 데이터 흐름 결정 매트릭스

| 데이터 | Firebase | FastAPI | 사유 |
|---|:--:|:--:|---|
| 인증 토큰 | Auth | 검증만 | Firebase Auth 활용 |
| 사원 메타 (329) | Firestore | — | 복합 쿼리 |
| 시맨틱 검색 인덱스 | — | ChromaDB | 벡터 DB 필수 |
| FTS5 인덱스 | — | SQLite | 한국어 토큰화 |
| 실시간 알람 | RTDB | 쓰기만 | WebSocket 푸시 |
| 감사 로그 | RTDB (append) | 쓰기 | 시계열 |
| 사용자 피드백 | RTDB | 집계 시 읽기 | 즉시 반영 |
| 9 시나리오 | Firestore | — | 정적 메타 |
| 9 크롤러 결과 | Firestore (메타) + Storage (원본) | 크롤링 | Python 환경 |
| LLM 응답 | — | Ollama/Gemini | 모델 추론 |
| 7 ML 추론 | — | sklearn/XGBoost | Python |
| 문서 메타 | Firestore | — | 사용자별 |
| 문서 파일 (DOCX/PDF) | Storage | 생성 | Jinja2 |
| 매뉴얼 PDF | Storage | RAG 인덱싱 | 파일 |
| SOP 8종 | Firestore | — | 정적 |
| 용어집 297 | Firestore | — | 정적 |
| 사용자 프로필 | Auth + Firestore | — | Custom Claims |
| 부서 매핑 30 | Firestore | — | 정적 |
| 비밀번호 정책 | Firebase Rules | — | 검증 |

---

## 4. 17일 Day-by-Day 일정

### 일정 개요

| Day | 날짜 | Phase | 작업 | Firebase 관련 작업 추가 |
|:--:|:--:|:--:|---|---|
| **1** | 04-27 | 1 | ✅ 부트스트랩 (Vite+TS+i18n+셸+라우트) | — |
| **2** | 04-28 | 1+ | Login/Dashboard 폴리싱 + Mock | **Firebase 콘솔 프로젝트 생성** |
| **3** | 04-29 | 2 | 공통 컴포넌트 (Button/Card/Tabs/PlotlyChart/MapView) | **Firebase SDK 설치 + 환경변수** |
| **4** | 04-30 | 4 | C 도우미 시작 (SSE + 챗 레이아웃) | **LLM 멀티 라우터 (Gemini/Ollama)** |
| **5** | 05-01 | 4 | C 도우미 (SOP/시나리오/비전/파일/다운로드) | **메시지를 Firestore 저장** |
| **6** | 05-02 | 6 | F 설비 (OVERVIEW + Plotly Nelson SPC) | **알람을 RTDB 푸시** |
| **7** | 05-03 | 6 | F 설비 (에러 검색 + Markov + 금형 + MTBF) | **이력을 Firestore** |
| **8** | 05-04 | 5 | B 문서 (3탭 + SSE + 7포맷 + 품질) | **문서 메타 Firestore + 파일 Storage** |
| **9** | 05-05 | 7 | D 법규 (4탭 + Plotly Gantt + 관세) | **시나리오 Firestore + 변경 이력 RTDB** |
| **10** | 05-06 | 3 | A 인원 검색 (조직도 + 6 필터 + 지도) | **사원 329 Firestore 마이그레이션** |
| **11** | 05-07 | 8 | E 인사 (6탭 + Plotly 7차트 + 위저드) | **로그인 이력 RTDB + 33 계정 Auth** |
| **12** | 05-08 | — | i18n 영문 보강 + 모바일 폴리싱 | **Firebase Storage UI 통합** |
| **13** | 05-09 | 9 | 백엔드 API 22개 신규 + LLM 라우터 통합 | **Firebase Admin SDK FastAPI 통합** |
| **14** | 05-10 | 10 | Firestore 보안 규칙 + RTDB 규칙 | **rules-test 검증** |
| **15** | 05-11 | 10 | E2E 통합 테스트 + Cloudflare Tunnel | **MacBook + Tunnel 안정화** |
| **16** | 05-12 | 10 | 본선 데모 폴리싱 + 최종 UI 점검 | **Firebase 배포 (본선 빌드)** |
| **17** | 05-13 | — | **본선 데모 리허설 + 백업 시나리오** | **현장 점검 + 폴백 테스트** |

### 4-1. Day별 상세 (Day 2 이후 핵심)

#### Day 2 (04-28) — Login/Dashboard 폴리싱 + Firebase 콘솔
**기존 작업** (이미 작성한 [DAY2_PLAN.md](DAY2_PLAN.md) 그대로):
- A. Login 폴리싱 (3h)
- B. Dashboard 폴리싱 (2.5h)
- C. Mock API + 시드 (2h)
- D. 공통 보강 (0.5h)

**Firebase 추가 작업** (1h):
- Firebase Console 접속 → 프로젝트 생성 (`ajin-ai-assistant`)
- Web 앱 추가 → SDK 키 발급
- 4 서비스 활성화: Authentication, Firestore, Realtime DB, Storage
- 무료 Spark 플랜 확인
- `.env.development.local` 에 SDK 환경변수 저장:
  ```
  VITE_FIREBASE_API_KEY=...
  VITE_FIREBASE_AUTH_DOMAIN=ajin-ai-assistant.firebaseapp.com
  VITE_FIREBASE_PROJECT_ID=ajin-ai-assistant
  VITE_FIREBASE_DATABASE_URL=https://....firebaseio.com
  VITE_FIREBASE_STORAGE_BUCKET=ajin-ai-assistant.appspot.com
  VITE_FIREBASE_MESSAGING_SENDER_ID=...
  VITE_FIREBASE_APP_ID=...
  ```

#### Day 3 (04-29) — 공통 컴포넌트 + Firebase SDK 통합
**작업**:
- npm install firebase
- `src/lib/firebase.ts` — initializeApp + Auth/Firestore/RTDB/Storage exports
- 공통 컴포넌트 라이브러리:
  - Button, Card, Badge (Day 2에서 일부 추출됨)
  - Tabs, Stepper, Modal, Tooltip, Toast
  - DataTable (TanStack)
  - PlotlyChart (코드 스플리팅 lazy import)
  - MapView (react-leaflet)
  - MarkdownRenderer (react-markdown)
  - GlassPanel
  - FormField (react-hook-form + Zod)

#### Day 4 (04-30) — C 도우미 시작 + LLM 멀티 라우터
**프론트엔드**:
- `src/routes/chat.tsx` 본격 구현 (uiux Chat.jsx → TSX)
- SSE 클라이언트 (`@microsoft/fetch-event-source`)
- `src/api/onboarding.ts` — 백엔드 호출
- 듀얼 모드 토글 UI
- 메시지 리스트 + 입력 composer + Liquid Glass

**백엔드 (FastAPI 사내)**:
- `core/llm_router.py` 신규 — Gemini → Ollama → LM Studio 폴백
- `backend/routers/onboarding.py` 갱신 — SSE 스트리밍 멀티 프로바이더
- `.env` 백엔드: `GEMINI_API_KEY`, `OLLAMA_URL=http://localhost:11434`, `LM_STUDIO_URL=http://localhost:1234/v1`

#### Day 5 (05-01) — C 도우미 (SOP/시나리오/비전/파일) + Firestore 메시지
**프론트엔드**:
- SOP 8종 단계별 가이드 카드
- 협업 시나리오 5종 트리거
- 비전 모델 이미지 업로드 (multipart)
- 파일 업로드 20+ 확장자
- 다운로드 영구화 (DOCX/XLSX/CSV/TXT)
- 피드백 이모지 (👍/👎)

**Firebase 통합**:
- 메시지 종료 시 Firestore `chat_history/{user_id}/{message_id}` 저장
- 피드백을 RTDB `/feedback/{message_id}` 푸시
- 파일 업로드 → Firebase Storage `/images/{user_id}/{ts}.png`

#### Day 6 (05-02) — F 설비 OVERVIEW + Plotly Nelson SPC + 알람 RTDB
**프론트엔드**:
- `src/routes/equipment.tsx` 본격 구현
- 5 하위탭: 설비개요/긴급조치/장비유형/예측정비/ML엔진
- 5공정 건강 카드 (CCH/OBC/범퍼빔/도어/볼시트)
- Plotly 관리도 차트 + Nelson 8 Rules 위반 음영
- ML 엔진 상태 표시기 7종

**Firebase 통합**:
- SPC 위반 감지 → FastAPI → RTDB `/live_alarms/{id}` 푸시
- React에서 RTDB 구독 → Toast 알림 + 사이드바 점멸

#### Day 7 (05-03) — F 설비 (에러 검색 + Markov + 금형 + MTBF)
**프론트엔드**:
- 에러 검색 패널 (입력 + 카테고리 + ML 결과 카드)
- Markov 연쇄 트리 시각화 (Plotly Network)
- 금형 25개 게이지 + XGBoost 잔여수명
- MTBF 차트 (15대 × 240건)
- CSV 업로드 인터페이스
- 매뉴얼 RAG 3 하위탭

**Firebase 통합**:
- 에러 발생 이력 685건 Firestore 저장
- 금형 25개 Firestore (실시간 동기화)
- 매뉴얼 PDF 업로드 → Storage → ChromaDB 인덱싱 (FastAPI)

#### Day 8 (05-04) — B 문서 작성 + Firestore 메타 + Storage 파일
**프론트엔드**:
- `src/routes/draft.tsx` 본격 구현
- 3탭 (내부/외부/이력)
- 어조 + 문서유형 셀렉터
- SSE 스트리밍 생성
- 품질 평가 5기준 카드
- CC 추천 칩
- 버전 diff
- 7포맷 다운로드

**Firebase 통합**:
- 문서 메타 Firestore `documents/{user_id}/{doc_id}`
- 생성된 DOCX/PDF Storage `/pdfs/drafts/{user_id}/{doc_id}.docx`
- Firestore의 메타에 Storage URL 저장
- 사용자 다운로드 시 Storage signed URL 사용

#### Day 9 (05-05) — D 법규 + Firestore 시나리오 + RTDB 변경 알림
**프론트엔드**:
- `src/routes/compliance.tsx` 본격 구현
- 4탭 구조
- 시나리오 TOP-3 카드 + 시뮬레이션
- Plotly Gantt 타임라인
- 관세 슬라이더 → Plotly Bar (6품목)
- 변경 감지 메트릭 + CSV 내보내기
- 9 크롤러 패널
- Plotly Network 영향 그래프
- Folium → react-leaflet 사업장 지도

**Firebase 통합**:
- 9 시나리오 Firestore 시드
- 9 크롤러 결과 → FastAPI 실행 → Firestore + RTDB
- 규제 변경 감지 시 RTDB `/regulation_changes/{id}` 푸시
- 사용자 알림 → React Toast

#### Day 10 (05-06) — A 인원 검색 + Firestore 사원 마이그레이션
**프론트엔드**:
- `src/routes/search.tsx` 본격 구현 (uiux Search.jsx → TSX)
- 인터랙티브 조직도 (6 본부 × 19 팀)
- 6 필터 + 5종 정렬 + 검색 이력 칩
- 가시성 마스킹 (3-Tier)
- react-leaflet 사업장 지도 19개소
- 교차 네비 (이메일/문서 작성)

**Firebase 통합**:
- 사원 24명 → 329명 자동 확장 함수 → Firestore `employees` 컬렉션
- 시맨틱 검색은 FastAPI 호출
- 결과 카드의 가시성 마스킹은 클라이언트 (Firestore Rules 보강)

#### Day 11 (05-07) — E 인사 + Firebase Auth + RTDB 로그인 이력
**프론트엔드**:
- `src/routes/admin.tsx` 본격 구현
- 6탭 (Tier 4) / 4탭 (Tier 3) RBAC 분기
- 사용자 인라인 편집 7항목
- 3단계 사용자 생성 위저드
- 보안 감사 3종 카드
- Plotly 7차트 (인력 통계)
- 부서 × 기능 히트맵 (AI 활용 분석)
- 로그인 이력 다운로드 (CSV/XLSX)

**Firebase 통합**:
- 33 계정 → Firebase Auth 임포트 (Admin SDK 또는 콘솔 CSV)
- Custom Claims 설정: `role_level`, `department`, `must_change_pw`
- 로그인 시 RTDB `/login_history/{user_id}/{ts}` 자동 기록
- 보안 감사 → RTDB 구독 + 룰 엔진 (FastAPI)
- AI 활용 통계 → Firestore 집계 + Plotly

#### Day 12 (05-08) — i18n 영문 보강 + 모바일 + Storage UI
**작업**:
- 6대 기능 페이지의 모든 한국어 문자열 → i18n 영문 키 추가
- 모바일 768px 미만 햄버거 사이드바 (이미 Day 2에서 추가, 폴리싱)
- 모바일 챗 컴포저 sticky bottom
- 모바일 SPC 차트 가로 스크롤
- 본선 영문 시연 가능

**Firebase 통합**:
- Storage 업로드 진행률 표시
- Storage signed URL 캐싱

#### Day 13 (05-09) — 백엔드 API + LLM 멀티 라우터 + Firebase Admin SDK
**백엔드 작업**:
- E·F 신규 22개 엔드포인트 작성:
  - `/api/admin/users` (GET/POST/PATCH)
  - `/api/admin/security/audit`
  - `/api/admin/login-history/export`
  - `/api/admin/analytics/usage`
  - `/api/admin/analytics/roi`
  - `/api/admin/stats/headcount`
  - `/api/equipment/dashboard`
  - `/api/equipment/error-search`
  - `/api/equipment/spc/{process}`
  - `/api/equipment/molds`
  - `/api/equipment/markov`
  - `/api/equipment/maintenance/mtbf`
  - ... (총 22개)
- LLM 멀티 라우터 통합 (`core/llm_router.py`)
- Firebase Admin SDK 설치 + 토큰 검증 미들웨어
- FastAPI에서 Firestore 쓰기 (Admin SDK)

**프론트엔드**:
- API 호출 부분 mock → 실제 백엔드로 전환
- `VITE_USE_MOCK=false` 로 설정

#### Day 14 (05-10) — Firestore + RTDB 보안 규칙 + rules-test
**작업**:
- `firestore.rules` 작성:
  ```js
  rules_version = '2';
  service cloud.firestore {
    match /databases/{database}/documents {
      match /employees/{empId} {
        allow read: if request.auth != null;
        allow write: if request.auth.token.role_level >= 4;
      }
      match /chat_history/{userId}/{msgId} {
        allow read, write: if request.auth.uid == userId;
      }
      // ... 12 컬렉션
    }
  }
  ```
- `database.rules.json` 작성 (RTDB):
  ```json
  {
    "rules": {
      "live_alarms": {
        ".read": "auth != null",
        ".write": "auth.token.role_level >= 3"
      },
      "audit_log": {
        ".read": "auth.token.role_level >= 5",
        ".write": false
      }
    }
  }
  ```
- Storage 규칙: 사용자별 파일만 자기가 접근
- `firebase emulators:exec --only firestore,database` 로 rules-test 실행

#### Day 15 (05-11) — E2E 통합 테스트 + Cloudflare Tunnel 안정화
**작업**:
- Playwright E2E 테스트 5 시나리오 (본선 데모 시나리오 자동화)
- Cloudflare Tunnel 셋업:
  ```bash
  brew install cloudflared
  cloudflared tunnel login
  cloudflared tunnel create ajin-ai-api
  cloudflared tunnel route dns ajin-ai-api api-ajin.your-domain.com
  cloudflared tunnel run ajin-ai-api
  ```
- `~/.cloudflared/config.yml`:
  ```yaml
  tunnel: ajin-ai-api
  ingress:
    - hostname: api-ajin.your-domain.com
      service: http://localhost:8000
    - service: http_status:404
  ```
- LaunchAgent 등록 (재부팅 시 자동 시작)
- HTTPS + 도메인 검증

#### Day 16 (05-12) — Firebase 배포 + UI 폴리싱
**작업**:
- `npm run build` → `dist/` 생성
- `firebase deploy --only hosting,firestore:rules,database,storage`
- 배포 URL 확인 (`https://ajin-ai-assistant.web.app`)
- 본선 시나리오 1차 시연 (5명 동시 접속 부하 테스트)
- 발견 버그 수정
- UI 마무리 (애니메이션 / 호버 / 글래스 디테일)
- 백엔드 .env 본선 모드 (Mock=false, 모든 LLM 활성)

#### Day 17 (05-13) — 본선 리허설 + 백업 시나리오
**작업**:
- 본선 무대 환경 (Wifi / 화면 / 노트북 어댑터) 점검
- 15분 데모 3회 리허설
- **백업 시나리오 준비**:
  - Plan A: 정상 — Firebase + 사내 MacBook
  - Plan B: 인터넷 다운 — Mock + 로컬 백업 (오프라인 시연)
  - Plan C: MacBook 슬립 — 자동 깨우기 스크립트
  - Plan D: Ollama OOM — Gemini만 사용
- 데모 영상 캡처 (백업)

---

## 5. Firebase 프로젝트 셋업 가이드

### 5-1. Firebase Console 셋업 (Day 2)

1. **프로젝트 생성**
   - https://console.firebase.google.com → Add project
   - 이름: `ajin-ai-assistant`
   - 지역: `asia-northeast3` (Seoul) — 한국 사용자 최저 지연
   - Analytics: 비활성 (개인 정보 우려, 본선 단순화)

2. **Web 앱 추가**
   - 앱 닉네임: `AJIN AI Web`
   - Firebase Hosting 활성: ✅
   - SDK 설정 코드 복사 → `.env.development.local` 저장

3. **서비스 활성화**:
   - **Authentication**: 이메일/비밀번호 + 사용자 정의 클레임
   - **Firestore**: 프로덕션 모드, 위치 `asia-northeast3`
   - **Realtime Database**: 프로덕션 모드, 위치 `asia-southeast1` (RTDB는 Seoul 미지원, 도쿄도 미지원, 싱가포르)
   - **Storage**: 프로덕션 모드, `asia-northeast3`

4. **Firebase CLI 설치 (로컬)**
   ```bash
   npm install -g firebase-tools
   firebase login
   firebase init
   # 선택: Hosting, Firestore, Realtime Database, Storage
   # public dir: frontend/dist
   # SPA: yes
   ```

5. **firebase.json 구성**
   ```json
   {
     "hosting": {
       "public": "frontend/dist",
       "ignore": ["firebase.json", "**/.*", "**/node_modules/**"],
       "rewrites": [{"source": "**", "destination": "/index.html"}]
     },
     "firestore": {
       "rules": "firestore.rules",
       "indexes": "firestore.indexes.json"
     },
     "database": {
       "rules": "database.rules.json"
     },
     "storage": {
       "rules": "storage.rules"
     }
   }
   ```

### 5-2. SDK 환경변수

**Frontend (`.env.development.local`)** — gitignore 필수:
```
VITE_FIREBASE_API_KEY=AIza...
VITE_FIREBASE_AUTH_DOMAIN=ajin-ai-assistant.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=ajin-ai-assistant
VITE_FIREBASE_DATABASE_URL=https://ajin-ai-assistant-default-rtdb.asia-southeast1.firebasedatabase.app
VITE_FIREBASE_STORAGE_BUCKET=ajin-ai-assistant.appspot.com
VITE_FIREBASE_MESSAGING_SENDER_ID=123456789
VITE_FIREBASE_APP_ID=1:123:web:abc
VITE_API_URL=https://api-ajin.your-domain.com
VITE_USE_MOCK=false
```

**Backend (`.env`)** — gitignore 필수:
```
GEMINI_API_KEY=AIza...
OLLAMA_URL=http://localhost:11434
LM_STUDIO_URL=http://localhost:1234/v1
FIREBASE_SERVICE_ACCOUNT_PATH=./firebase-admin-key.json
JWT_SECRET=...
```

### 5-3. Firebase SDK 통합 (`src/lib/firebase.ts`)

```ts
import { initializeApp } from 'firebase/app';
import { getAuth } from 'firebase/auth';
import { getFirestore } from 'firebase/firestore';
import { getDatabase } from 'firebase/database';
import { getStorage } from 'firebase/storage';

const config = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  databaseURL: import.meta.env.VITE_FIREBASE_DATABASE_URL,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
};

export const app = initializeApp(config);
export const auth = getAuth(app);
export const firestore = getFirestore(app);
export const rtdb = getDatabase(app);
export const storage = getStorage(app);
```

---

## 6. LLM 모델 선택 + 메모리 최적화

### 6-1. M4 Pro 24GB 권장 Configuration A
```bash
# 본선 데모용 설치 (Day 4)
ollama pull bge-m3
ollama pull qwen3.5:9b
ollama pull exaone3.5
ollama pull gemma4:e2b

# 총 ~18GB 디스크 사용
# 동시 활성화: bge-m3 + qwen3.5:9b 만 상시 (~7GB RAM)
# exaone3.5 / gemma4:e2b 는 on-demand 로드
```

### 6-2. Ollama 최적화 설정
```bash
# ~/.ollama/config.json
{
  "num_keep": 4,
  "num_predict": 512,
  "temperature": 0.7,
  "num_gpu": -1,           # 전체 Metal GPU 사용
  "main_gpu": 0,
  "low_vram": false,
  "f16_kv": true,
  "vocab_only": false,
  "use_mmap": true,
  "use_mlock": false,
  "num_thread": 8
}
```

### 6-3. 멀티 LLM 라우터 (백엔드 `core/llm_router.py`)

```python
"""LLM 멀티 프로바이더 라우터 — Gemini → Ollama → LM Studio 폴백"""
from enum import Enum
import httpx
import os
from google import genai

class LLMProvider(str, Enum):
    GEMINI = "gemini"
    OLLAMA = "ollama"
    LM_STUDIO = "lm_studio"

class LLMRouter:
    def __init__(self):
        self.gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        self.lm_studio_url = os.getenv("LM_STUDIO_URL", "http://localhost:1234/v1")
    
    async def stream(
        self,
        prompt: str,
        feature: str = "onboarding",
        has_image: bool = False,
        image_bytes: bytes | None = None,
    ):
        provider, model = self._select_provider(feature, has_image)
        
        try:
            if provider == LLMProvider.GEMINI:
                async for tok in self._gemini_stream(prompt, model, image_bytes):
                    yield tok
            elif provider == LLMProvider.OLLAMA:
                async for tok in self._ollama_stream(prompt, model):
                    yield tok
            else:
                async for tok in self._lm_studio_stream(prompt, model):
                    yield tok
        except Exception as e:
            # 폴백 체인 발동
            yield from self._fallback_chain(prompt, feature, has_image, exclude=provider)
    
    def _select_provider(self, feature: str, has_image: bool):
        # 1순위: Gemini (인터넷 있고 일반 텍스트)
        if has_image:
            return LLMProvider.GEMINI, "gemini-1.5-pro-vision"
        if self._gemini_available() and feature != "onboarding_korean":
            return LLMProvider.GEMINI, "gemini-1.5-pro"
        
        # 2순위: Ollama (한국어 / 오프라인)
        if feature == "onboarding_korean":
            return LLMProvider.OLLAMA, "exaone3.5"
        if feature == "draft":
            return LLMProvider.OLLAMA, "qwen3.5:9b"
        if feature == "search_summary":
            return LLMProvider.OLLAMA, "qwen3.5:4b"
        
        # 3순위: LM Studio (Ollama 다운 시)
        return LLMProvider.OLLAMA, "qwen3.5:9b"
    
    def _gemini_available(self) -> bool:
        # 빠른 health check
        try:
            httpx.get("https://generativelanguage.googleapis.com", timeout=1)
            return True
        except:
            return False
```

### 6-4. 메모리 모니터링 스크립트
```bash
# scripts/monitor_ollama.sh
while true; do
  echo "=== $(date +%H:%M:%S) ==="
  ollama ps
  echo "Memory: $(memory_pressure | head -1)"
  echo ""
  sleep 5
done
```

---

## 7. Cloudflare Tunnel 설정

### 7-1. Tunnel 셋업 (Day 15)
```bash
# 설치
brew install cloudflared

# 인증
cloudflared tunnel login
# → Cloudflare 대시보드에서 도메인 선택

# Tunnel 생성
cloudflared tunnel create ajin-ai-api

# DNS 라우팅 (your-domain.com 보유 시)
cloudflared tunnel route dns ajin-ai-api api-ajin.your-domain.com

# 또는 Cloudflare 무료 도메인 (yourname.cfargotunnel.com)
```

### 7-2. config.yml
```yaml
# ~/.cloudflared/config.yml
tunnel: <tunnel-id>
credentials-file: /Users/<you>/.cloudflared/<tunnel-id>.json

ingress:
  - hostname: api-ajin.your-domain.com
    service: http://localhost:8000
    originRequest:
      connectTimeout: 10s
      tcpKeepAlive: 30s
      noTLSVerify: false
  - service: http_status:404

# 메트릭 (선택)
metrics: localhost:43657
```

### 7-3. macOS LaunchAgent (자동 실행)
```bash
# ~/Library/LaunchAgents/com.cloudflare.cloudflared.plist
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.cloudflare.cloudflared</string>
    <key>ProgramArguments</key>
    <array>
        <string>/opt/homebrew/bin/cloudflared</string>
        <string>tunnel</string>
        <string>run</string>
        <string>ajin-ai-api</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>

# 등록
launchctl load ~/Library/LaunchAgents/com.cloudflare.cloudflared.plist
```

### 7-4. 본선 당일 안정화
- MacBook 절전 모드 비활성화 (`pmset -c sleep 0`)
- 화면 잠금 비활성화 (시스템 설정)
- Tunnel 상태 모니터링: `cloudflared tunnel info ajin-ai-api`
- 백업 옵션: ngrok 무료 (긴급 시)

---

## 8. 데이터 시드 마이그레이션 전략

### 8-1. SQLite → Firestore 시드 스크립트 (Day 13)

```python
# scripts/firebase_seed.py
import firebase_admin
from firebase_admin import credentials, firestore
import sqlite3
from pathlib import Path

cred = credentials.Certificate("firebase-admin-key.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

def seed_employees():
    conn = sqlite3.connect("data/employees.db")
    cursor = conn.execute("SELECT * FROM employees")
    batch = db.batch()
    count = 0
    for row in cursor:
        emp = dict(row)
        ref = db.collection("employees").document(emp["employee_id"])
        batch.set(ref, emp)
        count += 1
        if count % 500 == 0:  # Firestore 배치 한도
            batch.commit()
            batch = db.batch()
    batch.commit()
    print(f"✓ Seeded {count} employees")

def seed_error_codes():
    # 201 에러코드 → Firestore
    ...

def seed_scenarios():
    # 9 시나리오 JSON → Firestore
    ...

if __name__ == "__main__":
    seed_employees()
    seed_error_codes()
    seed_scenarios()
    # ...
```

### 8-2. 33 계정 → Firebase Auth 임포트
```bash
# scripts/import_users.py
firebase auth:import accounts.json --hash-algo=BCRYPT
```

### 8-3. 파일 → Firebase Storage
```python
# scripts/upload_storage.py
from firebase_admin import storage
bucket = storage.bucket()

# 매뉴얼 PDF 업로드
for pdf in Path("data/equipment/manuals").glob("*.pdf"):
    blob = bucket.blob(f"pdfs/manuals/{pdf.name}")
    blob.upload_from_filename(str(pdf))
    print(f"✓ {pdf.name}")
```

---

## 9. 점진적 Firebase 통합 패턴

### 9-1. 패턴: 기능 페이지 빌드와 동시에 Firebase 연동

**예시: F 설비 (Day 6) — 알람 RTDB 통합**

```tsx
// src/routes/equipment.tsx
import { ref, onValue } from 'firebase/database';
import { rtdb } from '@/lib/firebase';

function EquipmentDashboard() {
  const [alarms, setAlarms] = useState<Alarm[]>([]);

  useEffect(() => {
    const alarmsRef = ref(rtdb, 'live_alarms');
    const unsub = onValue(alarmsRef, (snap) => {
      const data = snap.val();
      setAlarms(Object.values(data || {}));
    });
    return () => unsub();
  }, []);

  return (
    <div>
      {alarms.map(a => <AlarmCard key={a.id} alarm={a} />)}
    </div>
  );
}
```

### 9-2. 패턴: Firestore Hook
```tsx
// src/hooks/useFirestoreCollection.ts
import { collection, onSnapshot, query, where, QueryConstraint } from 'firebase/firestore';

export function useFirestoreCollection<T>(
  path: string,
  ...constraints: QueryConstraint[]
) {
  const [data, setData] = useState<T[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const q = query(collection(firestore, path), ...constraints);
    const unsub = onSnapshot(q, (snap) => {
      setData(snap.docs.map(d => ({ id: d.id, ...d.data() } as T)));
      setLoading(false);
    });
    return () => unsub();
  }, [path]);

  return { data, loading };
}

// 사용
const { data: employees } = useFirestoreCollection<Employee>('employees',
  where('department', '==', '품질보증팀'),
  where('position', '==', '차장'),
);
```

### 9-3. FastAPI ↔ Firebase 통합 (Admin SDK)
```python
# backend/auth_middleware.py
from firebase_admin import auth as fb_auth, firestore
from fastapi import Header, HTTPException

async def get_current_user(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Bearer token required")
    token = authorization[7:]
    try:
        decoded = fb_auth.verify_id_token(token)
        return {
            "uid": decoded["uid"],
            "email": decoded.get("email"),
            "role_level": decoded.get("role_level", 1),
            "department": decoded.get("department"),
        }
    except Exception as e:
        raise HTTPException(401, f"Invalid token: {e}")

# Firestore 쓰기 예
def log_audit(user_uid: str, endpoint: str, detail: str):
    db = firestore.client()
    db.collection("audit_log").add({
        "uid": user_uid,
        "endpoint": endpoint,
        "detail": detail,
        "timestamp": firestore.SERVER_TIMESTAMP,
    })
```

---

## 10. 위험 요소 + 완화

### 10-1. 일정 위험

| 위험 | 영향 | 완화 |
|---|:--:|---|
| **17일 일정 + 28h Firebase = 막판 통합 폭발** | 🔴 | Day 4부터 점진적 통합 (한꺼번에 X) |
| **Day 13 백엔드 22 API 신규** | 🔴 | 우선순위 1 8개만 작성 + 나머지 mock 유지 |
| **Day 14~17 4일 모든 Firebase + 테스트** | 🟡 | Day 12까지 i18n + 모바일 끝내고 마지막 5일 집중 |

### 10-2. MacBook 위험

| 위험 | 영향 | 완화 |
|---|:--:|---|
| **24GB 메모리 OOM (LLM + Chrome + ...)** | 🔴 | Configuration A (qwen3.5:9b만 상시) + 비전은 on-demand |
| **데모 중 MacBook 절전** | 🔴 | `caffeinate -dimsu &` 실행 + LaunchAgent |
| **Wifi 끊김 → Cloudflare Tunnel 다운** | 🔴 | Plan B: 로컬 mock 폴백 자동 전환 |
| **Ollama 모델 로드 시간 (첫 호출)** | 🟡 | 데모 5분 전 사전 warm-up 스크립트 |
| **본선 무대 화면 해상도 (외부 모니터)** | 🟡 | 미리 1920×1080 + 4K 시연 검증 |

### 10-3. Firebase 위험

| 위험 | 영향 | 완화 |
|---|:--:|---|
| **Firestore 보안 규칙 오류로 데이터 노출** | 🔴 | rules-test 의무 + 본선 전 보안 감사 |
| **Custom Claims 갱신 지연 (1시간)** | 🟡 | 사용자 재로그인 또는 강제 refreshToken |
| **무료 티어 일일 read 50k 초과** | 🟢 | 본선 시연 약 5k → 충분 |
| **Realtime DB 도쿄 미지원** | 🟢 | 싱가포르 사용 (지연 ~50ms 추가) |
| **Firebase Storage 업로드 실패 (CORS)** | 🟡 | gsutil cors set + storage.rules 검증 |

### 10-4. 백업 시나리오 (본선 당일)

| 상황 | 자동 폴백 |
|---|---|
| **Wifi 정상** | 정상 — Firebase + 사내 + Gemini |
| **Wifi 다운** | 1) Cloudflare Tunnel 끊김 → React 가 mock 자동 전환 / 2) Ollama 로컬 호출 |
| **Gemini 다운** | LLM 라우터가 자동 Ollama 폴백 |
| **Ollama OOM** | LLM 라우터가 LM Studio 또는 Gemini 자동 폴백 |
| **Firebase 인증 실패** | 로컬 mock 인증 (DEV 모드 빠른 로그인 칩) |
| **MacBook 슬립** | `caffeinate` + 외부 마우스 5초 단위 jiggler |

---

## 11. 본선 데모 시나리오 (15분)

### Plan A: 정상 (모든 시스템 작동)

| 분 | 페이지 | 시연 포인트 |
|:--:|:--:|---|
| **0~1** | Login | • Wifi 확인 → Firebase Auth 로그인<br>• 비밀번호 정책 6 조건 실시간 점등<br>• `QA-0001` `Demo!2026` 시연 |
| **1~2** | Dashboard | • 환영 헤더 (김민수 차장 / 품질보증팀)<br>• 메트릭 4 카드 카운트업<br>• 6 모듈 RBAC 필터링 (E 모듈 잠금)<br>• 빠른 액션: SPC 위반 알람 (RTDB 라이브) |
| **2~4** | A 인원 검색 | • 시맨틱 검색 "QA 차장" → 0.3초<br>• 인터랙티브 조직도 (6 본부 클릭)<br>• 가시성 마스킹 (타부서 이메일 ***)<br>• react-leaflet 지도 19개소<br>• 교차 네비 → B 페이지 |
| **4~7** | B 문서 작성 | • "현대차 SQ팀에 PPAP 제출 안내"<br>• Gemini 1순위 → 토큰 스트리밍<br>• 품질 평가 87/100 (5기준 분해)<br>• CC 추천 칩 (필수/권장)<br>• 7포맷 다운로드 (DOCX 시연) |
| **7~10** | C AI 도우미 | • 듀얼 모드 (교육 모드)<br>• "프레스 트라이 SOP" → 8단계 가이드<br>• 진행률 바 + 체크리스트<br>• 퀴즈 1문제 → 오답 → "Step 3 다시 보기"<br>• 비전 모델 — 부품 사진 분석 (Gemma 4)<br>• 업무 모드 → "에러코드 E101" → DB 즉답 |
| **10~12** | D 법규 모니터링 | • 시나리오 TOP-3 (산안법 85점, 트럼프 78점, REACH 52점)<br>• 산안법 시뮬레이션 → 영향 시설 3곳<br>• Plotly Gantt 타임라인<br>• 관세 슬라이더 25% → JOON INC 400억 영향<br>• Plotly Network 영향 그래프 |
| **12~14** | F 설비/공정 | • 5공정 건강 (CCH/OBC/범퍼빔/도어/볼시트)<br>• Plotly Nelson Rule 위반 음영 + 풍선<br>• 에러 검색 "이상한 소리" → TF-IDF<br>• 결과: E-101 베어링 마모 0.87 cosine<br>• Markov 후속 → E-205 윤활 0.62 → E-310 모터 0.31<br>• MTBF 차트 + 다음 정비 예측 |
| **14~15** | E 인사 관리 | • 보안 감사 3종 (무차별/야간/비활성)<br>• AI 활용 분석 — 부서×기능 히트맵<br>• ROI 산출: 950만 원/월 절감 추정<br>• 로그인 이력 CSV 다운로드 |

### Plan B: Wifi 다운

전환 자동화 — `useNetworkStatus()` 훅이 감지 후:
- API 호출이 mock 폴백
- Firestore 구독은 cached data 사용
- LLM 호출은 로컬 Ollama만
- 데모 시연 가능 (단 Firebase 실시간 알람 시연 X)

---

## 12. 본선 후 30명 운영 로드맵

### 12-1. 30명 동시 운영 시 병목

| 컴포넌트 | 30명 가능? | 대안 |
|---|:--:|---|
| Firebase Hosting | ✅ 무제한 | — |
| Firebase Auth | ✅ 무제한 | — |
| Firestore | ✅ 무료 50k read/일 충분 | — |
| RTDB | ✅ 무료 1GB/10GB | — |
| Storage | ✅ 무료 5GB | — |
| **MacBook FastAPI** | 🟡 30 동시 검색 OK, LLM 1~2명만 | **Cloud Run + GPU** |
| **MacBook Ollama** | ❌ 30 LLM 큐잉 | 사내 GPU 서버 또는 Cloud GPU |

### 12-2. 30명 운영 단계별 마이그레이션 (본선 후 1~2개월)

#### Phase A (본선 직후, 1주)
- 사내 GPU 서버 1대 추가 (NVIDIA RTX 4090 24GB)
- Ollama 같은 모델 → 50 tok/s × 4~5 동시 처리 가능
- MacBook은 백업으로

#### Phase B (1개월차)
- Cloud Run 컨테이너 (FastAPI)
- Cloud SQL (PostgreSQL) — SQLite 대체
- ChromaDB → Pinecone 또는 Cloud Run + Persistent Volume
- 30명 동시 검색 OK

#### Phase C (2개월차, 100명 확장 대비)
- Cloud Run with GPU L4 ($0.5/h × 24h × 30 = $360/월)
- Vertex AI Gemini 통합
- 모니터링 (Cloud Logging + Sentry)

---

## 13. 17일 산출물 체크리스트

### Day 1~17 누적 산출물 예상
- React 페이지 9개 (login + dashboard + 7 모듈)
- 공통 컴포넌트 ~20개
- Firebase SDK 통합 (4 서비스)
- FastAPI 라우터 22개 신규 + 기존 8개 보강
- LLM 멀티 라우터
- Firestore 12 컬렉션 시드 (~5MB)
- RTDB 6 노드 구조
- Storage 파일 ~500MB 업로드
- 보안 규칙 3종 (Firestore/RTDB/Storage)
- E2E 테스트 5 시나리오
- Cloudflare Tunnel 셋업
- 본선 데모 영상 (백업)

### 일정 종료 시 본선 준비도
- Phase 1~10 모두 ✅
- Firebase 풀 통합 ✅
- 30명 운영 가능 (LLM 제외) ✅
- 한·영 i18n ✅
- 모바일 반응형 ✅
- 본선 데모 3회 리허설 완료 ✅

---

## 14. 즉시 시작 가능한 다음 액션

### 다음 단계 (Day 2 작업)
사용자 결정에 따라 다음 중 선택:

| 선택 | 작업 |
|:--:|---|
| **A** | **Day 2 시작** — Mock API + 시드 + Login/Dashboard 폴리싱 + Firebase 콘솔 프로젝트 생성 |
| **B** | **Day 2 + Firebase 콘솔만 먼저** — Firebase 프로젝트 생성·SDK 키 발급만 진행 후 Day 2는 내일 |
| **C** | **이 계획서 검토 후 시작** — 추가 조정 사항 논의 |
| **D** | **MacBook 환경 사전 점검** — Ollama 설치, 모델 다운로드, 메모리 검증 후 Day 2 |

### 권장: **D + A** (사전 환경 점검 후 Day 2 본격 시작)

#### D 단계 작업 (~30분):
```bash
# 1. Ollama 설치
brew install ollama
ollama serve  # 백그라운드

# 2. 모델 다운로드 (디스크 ~18GB)
ollama pull bge-m3        # 1.1GB
ollama pull qwen3.5:9b    # 6.1GB
ollama pull exaone3.5     # 4.4GB
ollama pull gemma4:e2b    # 6.7GB

# 3. 메모리 + 속도 검증
ollama run qwen3.5:9b "안녕하세요. 자기소개 부탁드립니다."
# → 토큰 속도 30~50 tok/s 확인

# 4. 메모리 모니터링
ollama ps
# → bge-m3 + qwen3.5:9b 동시 로드 시 ~7GB
```

---

## 변경 이력

| 버전 | 날짜 | 변경 |
|---|---|---|
| **1.0** | 2026-04-27 | 초안 — 17일 일정 + Firebase 풀 + MacBook M4 Pro 환경 |

---

**관련 문서**:
- [REACT_MIGRATION_PLAN.md](REACT_MIGRATION_PLAN.md) — 14일 원안 (이 문서가 대체)
- [DAY2_PLAN.md](DAY2_PLAN.md) — Day 2 상세 (Firebase 콘솔 추가 1h 적용)
- [FIREBASE_DB_ARCHITECTURE.md](FIREBASE_DB_ARCHITECTURE.md) — 아키텍처 브레인스토밍
- [WEB_DESIGN_SPECIFICATION.md](WEB_DESIGN_SPECIFICATION.md) — 디자인 사양
- [FEATURE_SPECIFICATION.md](../features/FEATURE_SPECIFICATION.md) — 6대 기능
