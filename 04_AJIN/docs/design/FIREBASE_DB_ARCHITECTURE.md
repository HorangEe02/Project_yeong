# Firebase 풀스택 아키텍처 — 브레인스토밍 결과

> **주제**: Firebase Hosting (웹) + Firebase Realtime Database (DB) 풀스택 사용 가능성
> **작성일**: 2026-04-27
> **컨텍스트**: 본선 2주 일정 / 6대 기능 / Streamlit→React 마이그레이션
> **결론 미리보기**: **순수 Firebase 풀스택은 어렵다 — RTDB는 일부 기능에만 적합. 하이브리드 + Firestore 권장.**

---

## 목차

1. [사용자 아이디어 정리](#1-사용자-아이디어-정리)
2. [Firebase Realtime Database 본질 분석](#2-firebase-realtime-database-본질-분석)
3. [현재 프로젝트 데이터 인벤토리](#3-현재-프로젝트-데이터-인벤토리)
4. [4가지 아키텍처 옵션 비교](#4-4가지-아키텍처-옵션-비교)
5. [RTDB vs Firestore 비교](#5-rtdb-vs-firestore-비교)
6. [6대 기능별 호환성 매트릭스](#6-6대-기능별-호환성-매트릭스)
7. [비용 시뮬레이션 (본선 데모 기준)](#7-비용-시뮬레이션-본선-데모-기준)
8. [최종 추천 아키텍처](#8-최종-추천-아키텍처)
9. [마이그레이션 복잡도 + 위험](#9-마이그레이션-복잡도--위험)
10. [결정 필요 사항](#10-결정-필요-사항)

---

## 1. 사용자 아이디어 정리

### 제안 내용
- **Firebase Hosting**: React 정적 빌드 호스팅 ✓ 이미 결정됨
- **Firebase Realtime Database**: 모든 DB를 RTDB로 통합 (신규 아이디어)

### 의도 추정
- Google 생태계 일관성 (Hosting + DB + Auth 단일 콘솔)
- 인프라 단순화 (서버 운영 부담 ↓)
- 무료 티어 활용 (Spark Plan)
- 본선 데모 시 외부 인터넷만 있으면 동작

### 풀스택 Firebase 의 매력
```
Firebase Auth + Hosting + Realtime DB + Storage + Functions
        ↓
      ✅ 단일 콘솔 / 단일 SDK / 단일 결제
      ✅ Service Worker / SSL / CDN 자동
      ✅ 본선 데모 시연 무대에서 인터넷만 있으면 됨
```

---

## 2. Firebase Realtime Database 본질 분석

### 2-1. RTDB의 정체
| 항목 | 내용 |
|---|---|
| **데이터 구조** | **단일 거대한 JSON 트리** (key-value, 깊이 제한 32) |
| **스키마** | 없음 (NoSQL, 자유) |
| **쿼리** | 단일 필드 정렬·필터 (orderByChild + startAt + endAt) |
| **JOIN** | ❌ 없음 (denormalize 필수) |
| **인덱스** | `.indexOn` 규칙으로 1개 필드 단위 |
| **트랜잭션** | 단일 노드만 |
| **실시간** | ✅ WebSocket 기반 자동 sync (장점) |
| **오프라인** | ✅ 디스크 캐싱 + 재연결 동기화 |
| **클라이언트** | 직접 접근 (보안 규칙으로 제어) |

### 2-2. RTDB가 잘 하는 것
- 🟢 **실시간 알림** — 한 곳에서 데이터 변경 → 모든 클라이언트 즉시 반영
- 🟢 **채팅 / 상태 동기화** — 온라인 인디케이터, 라이브 메시지
- 🟢 **시계열 append** — 로그, 활동 피드 (역시간순 정렬)
- 🟢 **모바일 우선** — 오프라인 큐 + 자동 재동기화
- 🟢 **빠른 프로토타이핑** — 스키마 정의 불필요

### 2-3. RTDB가 못 하는 것 ⚠️
- 🔴 **복합 쿼리** — `WHERE dept='QA' AND position='차장' AND plant='본사'` 직접 표현 불가
- 🔴 **전문 검색 (FTS)** — 한국어 토큰화·BM25·하이라이트 → 외부 엔진 필수
- 🔴 **벡터 검색** — ChromaDB / Pinecone 대체 불가 (BGE-M3 임베딩 1024차원 → 코사인 유사도)
- 🔴 **JOIN/집계** — 부서 × 기능 히트맵, ROI 계산, MTBF 분석 → 클라이언트 측 가공 필요
- 🔴 **이진 파일** — XGBoost 모델, sklearn pickle, Plotly JSON 등 → Firebase Storage 별도
- 🔴 **서버 사이드 LLM** — Ollama, LM Studio 호스팅 불가 (Functions 시간 제한 9분)
- 🔴 **대용량 페이지네이션** — 깊이 nested 객체에서 cursor 기반 페이징 어려움
- 🔴 **Few-shot RAG** — 584건 문서 임베딩 후 cosine similarity 검색 → 별도 벡터 DB 필수

### 2-4. 결정적 한계 — 핵심 차별 기능 6 종이 안 됨
| 기능 | 구현 의존성 | RTDB로 가능? |
|---|---|:--:|
| **A 시맨틱 하이브리드 검색** | FTS5 + ChromaDB + RRF | ❌ |
| **B Few-shot RAG 584건** | ChromaDB BGE-M3 코사인 | ❌ |
| **C SSE 스트리밍 LLM** | Ollama / LM Studio / Gemini | 🟡 Gemini만 가능 |
| **C 비전 모델** | Gemma 4 / Gemini Vision | 🟡 Gemini만 |
| **D 9 크롤러** | Python Beautifulsoup / requests | ❌ |
| **D Plotly Network 영향 그래프** | networkx + 사이클 분석 | ❌ |
| **E AI 활용 ROI** | 사용 로그 집계 + 부서별 시간 절감 추정 | 🟡 클라이언트 가공 가능 |
| **F TF-IDF 에러 검색** | sklearn TfidfVectorizer + 코사인 | ❌ |
| **F SPC Nelson 8 Rules** | 시계열 통계 + 8 패턴 검사 | 🟡 클라이언트 가능하지만 부담 |
| **F XGBoost 금형 수명** | XGBoost 모델 추론 | ❌ |
| **F Markov 연쇄 예측** | Markov Chain 행렬 + DFS | ❌ |
| **F MTBF 예측 정비** | 240건 수리 이력 통계 | 🟡 가능하지만 느림 |

> **결론**: 6대 기능 중 **B, C(일부), D, F의 핵심 ML/RAG 기능은 RTDB 단독으로 불가능**.

---

## 3. 현재 프로젝트 데이터 인벤토리

### 3-1. SQLite DB 13개
| DB | 크기 | 용도 | RTDB 적합? |
|---|:--:|---|:--:|
| `auth.db` | 40KB | 33 계정 + JWT + RBAC | 🟢 가능 |
| `audit.db` | 20KB | API 호출 감사 로그 | 🟢 우수 (append-only) |
| `compliance.db` | 3.3MB | 9 크롤러 결과 + 시나리오 | 🟡 가능 (BLOB → JSON) |
| `compliance_changes.db` | 12KB | 규제 변경 diff | 🟢 가능 |
| `employees.db` | 240KB | 329 사원 (FTS5 인덱스 포함) | 🟡 가능, FTS5 분리 |
| `feedback.db` | 20KB | 사용자 피드백 | 🟢 우수 |
| `draft_versions.db` | 36KB | 문서 버전 | 🟢 가능 |
| `error_codes.db` | ? | 201 에러코드 | 🟢 가능 |
| `error_history.db` | ? | 685건 에러 발생 이력 | 🟢 우수 |
| `mold_lifecycle.db` | ? | 25 금형 + 수리이력 240 | 🟢 가능 |
| `drawings.db` | ? | 15 도면 | 🟢 가능 |
| `inspection.db` | ? | 9 점검 템플릿 | 🟢 가능 |
| `search_feedback.db` | ? | 검색 피드백 | 🟢 가능 |

### 3-2. 비-SQLite 데이터
| 자산 | 위치 | RTDB 적합? |
|---|---|:--:|
| **ChromaDB 인덱스** | `vectorstore/` (15MB) | 🔴 절대 불가 — 벡터 DB 별도 필수 |
| **BM25 코퍼스** | `vectorstore/bm25_corpus.json` | 🟡 가능 (메모리 부담) |
| **Few-shot 인덱싱 584건** | ChromaDB | 🔴 불가 |
| **ML 학습 데이터** | `data/intent_ml/`, `spc_ml/`, `mold_ml/`, `regulation_ml/`, `markov_ml/` | 🟡 가능 (5MB+) |
| **사내 문서 PDF/DOCX** | `data/documents/` | 🔴 Firebase Storage 사용 |
| **용어집 297항목** | `data/knowledge_base/glossary/` (21 JSON) | 🟢 우수 |
| **Jinja2 템플릿** | `data/templates/` | 🔴 Firebase Storage |
| **시나리오 9 JSON** | `data/scenarios/`, `data/demo_scenarios/` | 🟢 우수 |
| **시설 19개소** | `data/facility_db/plants.json` | 🟢 우수 |
| **AJIN Sans 폰트** | `public/fonts/` | ✅ Hosting 정적 자산 |

### 3-3. 데이터 분류 결과
- **RTDB에 적합 (🟢)**: 약 60% — 구조화된 메타데이터 / 로그 / 설정
- **RTDB에 부분 적합 (🟡)**: 약 25% — 가능하지만 비효율
- **RTDB에 부적합 (🔴)**: 약 15% — 벡터·이진·LLM 호스팅

---

## 4. 4가지 아키텍처 옵션 비교

### 옵션 A: 순수 Firebase 풀스택 (RTDB 단독)

```
┌─────────────────────────┐
│  React (Firebase Host)  │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ Firebase Realtime DB    │
│ (모든 데이터 통합)      │
└─────────────────────────┘
         │
         ▼
┌─────────────────────────┐
│ Gemini API (브라우저)   │
└─────────────────────────┘
```

| 평가 | 결과 |
|:--:|---|
| 인프라 단순도 | 🟢 매우 단순 |
| 비용 | 🟢 본선 무료 티어 충분 |
| 6대 기능 구현도 | 🔴 **40% 미만** — RAG/벡터/ML 모두 손실 |
| 본선 평가 | 🔴 *"실동작 ML 4종"* 차별점 소멸 |
| **추천 여부** | ❌ **비추천** |

---

### 옵션 B: 하이브리드 (Firebase + FastAPI 사내) ⭐ 권장

```
┌─────────────────────────────────┐
│  React (Firebase Hosting)       │
└──┬─────────────────┬────────────┘
   │                 │
   ▼                 ▼
┌──────────────┐  ┌─────────────────────────┐
│ Firebase     │  │ FastAPI (사내 GPU)      │
│ RTDB / Auth  │  │ + Cloudflare Tunnel     │
│ (실시간/단순)│  │ + Ollama / LM Studio    │
└──────────────┘  │ + ChromaDB / SQLite     │
                  │ + 7 ML 모델             │
                  └─────────────────────────┘
                            │
                            ▼
                  ┌─────────────────────────┐
                  │ Gemini API (서버 측)    │
                  └─────────────────────────┘
```

**RTDB 사용처** (실시간 + 단순 데이터):
- `live_alarms/` — 실시간 SPC 위반·법규 변경 알람
- `audit_log/` — API 호출 감사 로그 (append-only)
- `feedback/` — 👍/👎 사용자 피드백
- `presence/` — 온라인 사용자 인디케이터
- `notifications/` — 사용자별 알림
- `recent_activity/` — 최근 활동 피드

**FastAPI 백엔드 사용처** (복잡 / ML / 벡터):
- 인증·RBAC·세션
- 시맨틱 하이브리드 검색 (ChromaDB)
- Few-shot RAG 문서 작성
- 7 ML 모델 추론
- Ollama / LM Studio LLM
- Plotly 차트 데이터 가공
- 9 크롤러 실행

| 평가 | 결과 |
|:--:|---|
| 인프라 단순도 | 🟡 중 (2 시스템) |
| 비용 | 🟢 본선 무료 |
| 6대 기능 구현도 | 🟢 **100%** |
| 실시간 알림 | 🟢 RTDB 활용 |
| 본선 평가 | 🟢 차별점 모두 살림 |
| **추천 여부** | ✅ **최고 추천** |

---

### 옵션 C: Firebase + Cloud Functions

```
┌─────────────────────────┐
│  React (Firebase Host)  │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ Cloud Functions (Python)│
│ (FastAPI 대체)          │
└─┬───────────────────────┘
  │
  ├─→ Firestore (구조 데이터)
  ├─→ Realtime DB (실시간)
  ├─→ Cloud Storage (PDF/모델/폰트)
  └─→ Gemini API
```

| 평가 | 결과 |
|:--:|---|
| 인프라 단순도 | 🟢 단일 Google |
| 비용 | 🟡 Cold start + 함수 호출당 과금 |
| 6대 기능 구현도 | 🟡 **70%** — Ollama/LM Studio 불가 |
| Cold start | 🔴 첫 호출 5~10초 (본선 시연 치명적) |
| 함수 시간 제한 | 🔴 9분 (LLM 스트리밍 OK, ML 학습 X) |
| 메모리 제한 | 🟡 8GB (XGBoost OK) |
| GPU | 🔴 없음 (Ollama 불가) |
| **추천 여부** | 🟡 **본선 후 고려** |

---

### 옵션 D: Firebase + Cloud Run + RTDB

```
┌─────────────────────────┐
│  React (Firebase Host)  │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ Cloud Run (FastAPI 컨테이너)│
└─┬───────────────────────┘
  │
  ├─→ RTDB (실시간/단순)
  ├─→ Firestore (구조)
  ├─→ Cloud Storage (모델/PDF)
  ├─→ Vertex AI / Gemini
  └─→ ChromaDB (Persistent Volume)
```

| 평가 | 결과 |
|:--:|---|
| 인프라 단순도 | 🟡 Google 통합 + Cloud Run |
| 비용 | 🟡 Cloud Run 인스턴스 시간당 |
| 6대 기능 구현도 | 🟡 **80%** — Ollama 불가 |
| Cold start | 🟡 1~3초 (gen2) |
| GPU | 🟡 가능 (NVIDIA L4, $0.5/h) |
| **추천 여부** | 🟡 **장기 운영용** |

---

## 5. RTDB vs Firestore 비교

본선 데모를 Firebase로 한다면, **RTDB 보다 Firestore 가 더 적합**할 가능성이 높습니다.

| 항목 | Realtime Database | Firestore |
|---|---|---|
| **데이터 모델** | 단일 JSON 트리 | 컬렉션 / 도큐먼트 / 서브컬렉션 |
| **쿼리** | 단일 필드 정렬 | 복합 쿼리 (`where().where()`) |
| **인덱스** | 단일 필드 `.indexOn` | 자동 + 복합 인덱스 |
| **JOIN** | ❌ | ❌ (denormalize) |
| **트랜잭션** | 단일 노드 | 다중 도큐먼트 |
| **확장성** | 동시 연결 200k | 무제한 (자동 샤딩) |
| **실시간** | ✅ (WebSocket) | ✅ (gRPC streaming) |
| **오프라인** | ✅ | ✅ (더 강력) |
| **가격 모델** | GB 저장 + GB 다운로드 | 도큐먼트 read/write 회수 |
| **무료 티어 / 월** | 1GB 저장 + 10GB 다운로드 | 1GiB 저장 + 50k read + 20k write/일 |
| **복합 검색** | ❌ | 🟡 (단일 필드만, FTS 별도) |
| **본선 데이터 적합도** | 🟡 단순 키-값 | 🟢 사원 329명·계정 33개 잘 어울림 |
| **모바일 SDK** | ✅ | ✅ |
| **추천** | 실시간 알람·로그 | 구조화된 메타·문서 |

### 결정적 차이 — 본선 사용 시
- **사원 329명 검색**: RTDB는 단일 필드만 정렬 가능 → 부서·직급·사업장 다중 필터 불가. **Firestore는 복합 쿼리 가능**.
- **에러 이력 685건 페이지네이션**: RTDB cursor 어려움 / **Firestore startAfter() 우수**.
- **알람 실시간 수신**: 둘 다 가능, 비슷.

### 권장
- **RTDB**: `live_alarms/`, `audit_log/`, `presence/`, `notifications/`
- **Firestore**: `employees/`, `accounts/`, `error_codes/`, `documents/`, `scenarios/`

---

## 6. 6대 기능별 호환성 매트릭스

각 기능을 옵션 B (하이브리드) 기준으로 어디에 배치할지:

### 기능 A — 인원 검색
| 데이터 | 배치 | 사유 |
|---|:--:|---|
| 사원 329명 메타 | **Firestore** | 복합 쿼리 (`where dept== AND position==`) |
| FTS5 인덱스 | **FastAPI/SQLite** | RTDB/Firestore 둘 다 FTS 미지원 |
| ChromaDB 시맨틱 | **FastAPI** | 벡터 DB 필요 |
| 검색 이력 | **RTDB** | append-only + 실시간 동기화 |
| 가시성 마스킹 | **클라이언트 (Firestore Rules)** | 부서별 필드 노출 통제 |

### 기능 B — 문서 작성
| 데이터 | 배치 | 사유 |
|---|:--:|---|
| 문서 유형 메타 | **Firestore** | 13종 정적 데이터 |
| Few-shot RAG 인덱싱 | **FastAPI/ChromaDB** | 벡터 검색 필수 |
| 버전 이력 | **Firestore** | 사용자별 컬렉션 |
| Jinja2 템플릿 | **Firebase Storage** | 파일 |
| 양식 PDF/DOCX | **Firebase Storage** | 파일 |
| LLM 호출 | **FastAPI → Gemini/Ollama** | LLM 라우팅 |

### 기능 C — AI 도우미
| 데이터 | 배치 | 사유 |
|---|:--:|---|
| 대화 메시지 (실시간) | **RTDB** | 실시간 스트리밍 결과 표시 |
| 메시지 이력 (장기) | **Firestore** | 사용자별 컬렉션 |
| 용어집 297 | **Firestore** | 검색 가능 |
| SOP 8종 | **Firestore** | 정적 + 단계 정보 |
| 협업 시나리오 5 | **Firestore** | 정적 |
| LLM 스트리밍 | **FastAPI SSE** | 백엔드에서 멀티 프로바이더 라우팅 |
| 비전 분석 | **FastAPI → Gemini Vision** | 백엔드 폴백 체인 |
| 파일 업로드 | **Firebase Storage** | 멀티미디어 |
| 피드백 | **RTDB** | 실시간 집계 |

### 기능 D — 법규 모니터링
| 데이터 | 배치 | 사유 |
|---|:--:|---|
| 시나리오 9개 | **Firestore** | 정적 + 검색 |
| 변경 이력 | **RTDB** | append-only + 실시간 알림 |
| 9 크롤러 실행 | **FastAPI** | Python 환경 |
| 영향 네트워크 | **FastAPI** | networkx 처리 |
| 관세 시뮬레이션 | **클라이언트** | 단순 곱셈 |

### 기능 E — 인사 관리
| 데이터 | 배치 | 사유 |
|---|:--:|---|
| 33 계정 + RBAC | **Firebase Auth** + **Firestore** | Firebase Auth 활용 |
| 로그인 이력 | **RTDB** | append-only |
| 보안 감사 | **FastAPI** (룰 엔진) | Python 통계 |
| 인력 통계 7차트 | **Firestore 집계** + **FastAPI** | Plotly 차트 |
| 비밀번호 정책 | **클라이언트** + **Functions** | 둘 다 검증 |

### 기능 F — 설비/공정 AI
| 데이터 | 배치 | 사유 |
|---|:--:|---|
| 에러코드 201 | **Firestore** | 카테고리별 쿼리 |
| 에러 이력 685 | **Firestore** + **RTDB 라이브** | 과거는 Firestore, 현재는 RTDB |
| 25 금형 + 수리 240 | **Firestore** | 메타 + 이력 |
| TF-IDF 에러 검색 | **FastAPI** | sklearn 필요 |
| Markov 25상태 | **FastAPI** | 알고리즘 |
| SPC Nelson 8 Rules | **FastAPI** + 결과만 RTDB | 패턴 분석 |
| XGBoost 금형 | **FastAPI** | 모델 추론 |
| MTBF | **FastAPI** | 통계 |
| 매뉴얼 PDF | **Firebase Storage** | 파일 |

---

## 7. 비용 시뮬레이션 (본선 데모 기준)

### 7-1. 가정
- **본선 데모 시연**: 3~5명 동시 접속, 약 30분
- **연습/테스트**: 본인 + 팀원 4명, 일 평균 2시간
- **시연 후**: 1주일 보존

### 7-2. Firebase 무료 티어 (Spark Plan)
| 서비스 | 무료 한도 / 월 | 본선 사용량 추정 | 초과? |
|---|---|---|:--:|
| **Hosting** | 10GB 저장 + 360MB/일 다운로드 | 빌드 ~5MB × 200 다운로드 = 1GB/일 | 🟢 |
| **Auth** | 무제한 | 33 계정 | 🟢 |
| **RTDB** | 1GB 저장 + 10GB 다운로드 | 알람·로그 ~50MB | 🟢 |
| **Firestore** | 1GiB 저장 + 50k read/일 + 20k write/일 | 사원 329 + 시연 약 5k read | 🟢 |
| **Storage** | 5GB 저장 + 1GB/일 다운로드 | PDF·모델 ~500MB | 🟢 |
| **Functions** | 125k 호출/월 + 40k GB-sec | Cloud Run 사용 시 별개 | 🟢 |

### 7-3. 사내 GPU 서버 + Cloudflare Tunnel
- **Cloudflare Tunnel**: 무료 (개인용)
- **GPU 비용**: 사내 자원
- **전기료**: 무시

### 7-4. Cloud Run + GPU (옵션 D 선택 시)
- **CPU 인스턴스**: ~$0.024/h × 10h = **$0.24** (본선)
- **GPU L4**: ~$0.5/h × 10h = **$5** (본선)

### 7-5. 결론
**모든 옵션 본선 데모 비용 ≈ $0** (사내 자원 활용 시) — 비용은 결정 요인이 아님.

---

## 8. 최종 추천 아키텍처

### 🏆 권장: 옵션 B (하이브리드) + RTDB + Firestore + Firebase Auth + Storage

```
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│             React 18 + TypeScript (Vite)                     │
│             Firebase Hosting (https://*.web.app)             │
│                                                              │
└──┬───────────────────┬────────────────────┬────────────────┬─┘
   │                   │                    │                │
   ▼                   ▼                    ▼                ▼
┌─────────┐    ┌──────────────┐    ┌───────────────┐    ┌────────────┐
│ Firebase│    │  Firestore   │    │ Realtime DB   │    │  Storage   │
│  Auth   │    │ (구조 데이터)│    │ (실시간/로그) │    │ (파일)     │
├─────────┤    ├──────────────┤    ├───────────────┤    ├────────────┤
│ 33 계정 │    │ employees    │    │ live_alarms   │    │ pdfs/      │
│ JWT     │    │ error_codes  │    │ audit_log     │    │ templates/ │
│ 6 RBAC  │    │ scenarios    │    │ presence      │    │ ml_models/ │
│ 부서    │    │ molds        │    │ notifications │    │ images/    │
│         │    │ glossary     │    │ feedback      │    │ fonts/     │
└─────────┘    │ documents    │    │ recent_act    │    └────────────┘
               │ sop_guides   │    └───────────────┘
               │ depts (29)   │
               └──────────────┘
                       │
                       │  복잡 쿼리/검색은 백엔드 호출
                       ▼
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│             FastAPI (사내 GPU) + Cloudflare Tunnel           │
│             https://api.ajin.your-domain.com                 │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  • ChromaDB (벡터 검색 + Few-shot RAG 584건)                  │
│  • SQLite (FTS5 한국어 전문 검색)                             │
│  • 7 ML 모델 (sklearn, XGBoost, Markov)                       │
│  • Ollama (Qwen 3.5, EXAONE, Gemma 4)                         │
│  • LM Studio (백업 LLM)                                       │
│  • 9 크롤러 (법규 모니터링)                                   │
│  • Jinja2 템플릿 렌더링                                       │
│                                                              │
└────────┬─────────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────────┐
│  Gemini 1.5 Pro / Vision API (외부)                          │
└──────────────────────────────────────────────────────────────┘
```

### 8-1. Firebase 사용 영역 명세

#### **Firebase Auth**
- 33 테스트 계정 임포트
- JWT 자동 갱신 (Firebase ID Token)
- 비밀번호 정책 (Security Rules)
- 사용자 프로필에 `role_level`, `department` 커스텀 클레임

#### **Firestore (구조화된 데이터)**
```
collections/
├── employees/{emp_id}             # 329 사원
├── accounts/{emp_id}              # 33 계정 (Auth와 별도 메타)
├── departments/{dept_id}          # 29 부서
├── plants/{plant_id}              # 19 사업장
├── error_codes/{code}             # 201 에러
├── molds/{mold_id}                # 25 금형
├── scenarios/{scenario_id}        # 9 법규 시나리오
├── documents/{doc_id}             # 사용자 문서 메타
├── glossary/{term}                # 297 용어
└── sop_guides/{sop_id}            # 8 SOP
```

#### **Realtime Database (실시간/로그)**
```
/live_alarms/{alarm_id}            # 진행 중 알람 (실시간)
/audit_log/{timestamp_id}          # API 호출 감사 (append-only)
/login_history/{user_id}/{ts}      # 로그인 이력
/feedback/{message_id}             # 사용자 피드백
/presence/{user_id}                # 온라인 인디케이터
/notifications/{user_id}/{ts}      # 사용자별 알림
/spc_realtime/{process_id}         # 라이브 SPC 데이터 (옵션)
```

#### **Firebase Storage**
```
/pdfs/manuals/                     # 설비 매뉴얼 PDF
/pdfs/regulations/                 # 법규 문서 PDF
/templates/                        # Jinja2 템플릿
/templates/reference/              # 양식 참고
/ml_models/                        # XGBoost/sklearn pickle
/images/                           # 사용자 업로드 이미지
/fonts/                            # AJIN Sans (Hosting public/도 가능)
```

#### **FastAPI (사내) — 변경 없음**
- 비즈니스 로직 그대로 유지
- ChromaDB / Ollama / 7 ML 그대로
- Firebase Admin SDK로 Firestore/RTDB 쓰기/읽기

### 8-2. 데이터 흐름 예시

#### 시나리오 1: 사원 검색 "QA 차장"
```
React → Firestore.query('employees')
         .where('team', '==', '품질보증팀')
         .where('position', '==', '차장')
         → 즉시 결과 (서버 부담 X)
```

#### 시나리오 2: 시맨틱 검색 "8D 보고서 담당자"
```
React → FastAPI POST /api/employee/search
         → ChromaDB cosine + FTS5 RRF
         → 결과 + 의도 분류
         → React 표시
```

#### 시나리오 3: 라이브 SPC 알람
```
FastAPI 분석 → Firestore admin SDK write
            → /live_alarms/{id} 푸시
            → 모든 React 클라이언트 즉시 수신
            → Toast 알림 + 사이드바 점멸
```

#### 시나리오 4: AI 도우미 스트리밍
```
React → FastAPI POST /api/onboarding/chat (SSE)
         → Gemini → 실패 시 Ollama → 실패 시 LM Studio
         → 토큰 단위 스트리밍 React 표시
         → 메시지 종료 시 Firestore 'chat_history' 저장
```

#### 시나리오 5: 문서 다운로드
```
React → FastAPI POST /api/draft/export
         → Jinja2 → DOCX 바이트
         → Firebase Storage 업로드
         → Storage URL React에 반환
         → React 다운로드 트리거
```

---

## 9. 마이그레이션 복잡도 + 위험

### 9-1. 추가 작업량 추정 (14일 일정 영향)

| 작업 | 추정 시간 | 영향 |
|---|:--:|:--:|
| Firebase 프로젝트 생성 + 콘솔 설정 | 1h | Day 1 추가 |
| Firebase SDK 통합 (frontend) | 2h | Day 2 추가 |
| Firebase Auth 마이그레이션 (33 계정 import) | 3h | Day 13 |
| Firestore 데이터 시드 (12 컬렉션) | 5h | Day 13 |
| RTDB 시드 + 보안 규칙 | 2h | Day 13 |
| Storage 파일 업로드 (PDF·템플릿·모델) | 3h | Day 13 |
| FastAPI에 Firebase Admin SDK 통합 | 4h | Day 13 |
| 보안 규칙 (Firestore + RTDB) | 4h | Day 13~14 |
| 통합 테스트 | 4h | Day 14 |
| **합계** | **28h** | **3.5일 추가** |

### 9-2. 위험 요소

| 위험 | 영향 | 완화 |
|---|:--:|---|
| **2주 일정 압박 + 28h 추가** | 🔴 | Day 13~14를 4일로 확장 또는 일부 기능 mock 유지 |
| **Firebase Auth ↔ FastAPI JWT 동기화** | 🟡 | Firebase ID Token을 FastAPI에서 검증 (Admin SDK) |
| **Firestore 보안 규칙 복잡도** | 🟡 | 본선 데모는 단순 (인증된 사용자만 read) |
| **RTDB ↔ Firestore 데이터 일관성** | 🟡 | 한 곳만 source of truth (FastAPI 또는 Functions trigger) |
| **무료 티어 일일 한도** | 🟢 | 본선 트래픽 ↓ 충분 |
| **사내 FastAPI 다운 시 핵심 기능 중단** | 🔴 | Cloudflare Tunnel + UPS 백업 |
| **Firebase Functions 9분 제한** | 🟡 | Functions 사용 안 함 (FastAPI로 우회) |
| **OAuth 도메인 등록** | 🟢 | Firebase 콘솔에서 5분 |

---

## 10. 결정 필요 사항

### 핵심 질문 5개

#### Q1. 백엔드 (FastAPI) 호스팅 위치
| 옵션 | 추천 |
|:--:|---|
| **A) 사내 GPU + Cloudflare Tunnel** | ✅ 본선 데모 |
| **B) Cloud Run + GPU L4** | 🟡 본선 후 운영 시 |
| **C) FastAPI 제거 + 모든 것 Firebase Functions** | ❌ Ollama 불가 |

#### Q2. 데이터베이스 분배
| 옵션 | 권장 |
|:--:|---|
| **A) RTDB만** | ❌ 복합 쿼리 약점 |
| **B) Firestore만** | 🟡 가능하나 실시간 약함 |
| **C) RTDB + Firestore 혼합** | ✅ 강력 추천 |
| **D) RTDB + 기존 SQLite (FastAPI)** | 🟡 기존 코드 유지 |

#### Q3. 인증 시스템
| 옵션 | 권장 |
|:--:|---|
| **A) Firebase Auth만** | ✅ JWT 자동 + 비번 정책 |
| **B) FastAPI JWT만 (기존)** | 🟡 기존 유지 |
| **C) Firebase Auth + FastAPI 검증** | ✅ 둘의 장점 |

#### Q4. 본선 데모 시 인터넷 의존도
| 옵션 | 결과 |
|:--:|---|
| **A) 완전 클라우드 (인터넷 필수)** | 회장 와이파이 의존 |
| **B) 사내 호스팅 (인트라넷)** | 자체 와이파이 가능 |
| **C) 하이브리드 (현재 추천)** | Firebase 정적 + 사내 백엔드 |

#### Q5. 일정 vs 완성도 트레이드오프
| 옵션 | 결과 |
|:--:|---|
| **A) 14일 그대로 + Mock으로 시연** | Day 14에 Firebase 통합 시도 |
| **B) 14일 → 17일 연장 (3일 추가)** | Firebase 풀 통합 |
| **C) 본선 후 Firebase 마이그레이션** | 본선은 Mock + 사내, 본선 후 Firebase |

---

## 11. 강력 추천 결론

### 🎯 추천 시나리오

**본선 (2주 데모)**:
- React + Firebase Hosting (정적)
- 사내 FastAPI + Ollama + ChromaDB (현재 그대로)
- Mock API 데이터 시드 (Day 2 작업)
- **Firebase 통합은 본선 후 진행**

**본선 후 (장기 운영)**:
- 사용자 데이터 → Firestore + Firebase Auth
- 실시간 알람 → RTDB
- 비즈니스 로직 → FastAPI 사내 그대로
- 파일 → Firebase Storage

### 이유
1. **2주 일정 압박**: Firebase 풀 통합 28h 추가 작업은 위험 (B/C/D/F 핵심 기능 시간 부족 가능)
2. **본선 평가 핵심**: 7 ML 모델 / Few-shot RAG / Nelson SPC 등 *실동작* 시연이 본질 — Firebase는 평가 가산점 거의 없음
3. **데모 환경 안정성**: 사내 호스팅은 회장 와이파이 의존 ↓
4. **Firebase 가치는 운영 단계**: 다중 사용자 + 모바일 + 실시간 알람이 필요한 배포 단계에서 빛남

### 그래도 Firebase 풀 통합을 원한다면
- **일정 17일로 연장** (3일 Day 13.5~14.5 추가)
- **Firestore 우선** (RTDB는 알람·로그만)
- **Firebase Auth + FastAPI 검증** 방식
- **본선 데모 환경 안정성 ↑**

---

## 12. 다음 단계 제안

### 옵션 1 (추천): **본선까지 현재 계획 유지 + 본선 후 Firebase 마이그레이션**
- Day 2~14 그대로 진행 (Mock + FastAPI)
- Day 14에 React 빌드만 Firebase Hosting 업로드 (정적)
- 본선 후 1~2주에 걸쳐 Firestore/RTDB/Storage 마이그레이션

### 옵션 2: **2주 내 Firebase 풀 통합 시도**
- Day 13~14를 Day 11.5~14.5로 연장 (3일 추가)
- Day 11~12 작업을 압축 또는 일부 mock 유지
- 위험: 본선 시연 직전 통합 이슈 발생 가능

### 옵션 3: **하이브리드 — Firestore Auth + RTDB만 본선 적용, FastAPI 그대로**
- Day 2 Mock 데이터 시드 → Firestore 시드로 변경
- Firebase Auth 통합 (JWT 자동)
- RTDB로 알람·피드백 라이브 시연 가능
- 추가 작업: 약 12h (1.5일)
- 위험: 중간

---

## 변경 이력

| 버전 | 날짜 | 변경 |
|---|---|---|
| **1.0** | 2026-04-27 | 초안 — Firebase RTDB 풀스택 가능성 분석 + 4 아키텍처 + 6대 기능 매트릭스 |

---

**관련 문서**:
- [REACT_MIGRATION_PLAN.md](REACT_MIGRATION_PLAN.md) — 14일 로드맵
- [DAY2_PLAN.md](DAY2_PLAN.md) — Day 2 상세
- [WEB_DESIGN_SPECIFICATION.md](WEB_DESIGN_SPECIFICATION.md) — 디자인 사양
- [FEATURE_SPECIFICATION.md](../features/FEATURE_SPECIFICATION.md) — 6대 기능
