# Day 6-7 — F 설비/공정 AI (Equipment & Process AI · Module F)

> **작성일**: 2026-04-27 (Day 5++.4 폴리싱 직후, Day 8 PLAN 작성됐으나 Day 6-7 우선 처리 결정)
> **선행**: Day 4 채팅 + Day 5 SOP/시나리오 + Day 5+ Firebase Auth + Day 5++ HUD 폴리싱 / 백엔드 LLM 라우터 30 PASS / `features/equipment/*` **19 모듈 ~6,200줄** 보존
> **대상**: F-2-1 ~ F-2-15 사양 (FEATURE L1177~1320) — Nelson 8 Rules SPC, ML 7종, Markov, XGBoost, MTBF, 매뉴얼 RAG
> **본선 평가 핵심**: **#2 실동작 ML 7종** + **#5 Nelson 8 Rules SPC** ⭐
> **목표 시간**: 3.5~4시간 (Day 6 + Day 7 통합, Phase 분할)
> **본선까지**: 13 작업일 남음

---

## 목차

1. [목적 + 요구사항](#1-목적--요구사항)
2. [기존 자산 인벤토리 (19 모듈)](#2-기존-자산-인벤토리-19-모듈)
3. [본선 평가 매칭](#3-본선-평가-매칭)
4. [아키텍처](#4-아키텍처)
5. [5 Sub-Tab UI 사양](#5-5-sub-tab-ui-사양)
6. [SPC Nelson 8 Rules + Plotly 시각화](#6-spc-nelson-8-rules--plotly-시각화)
7. [5공정 건강 대시보드](#7-5공정-건강-대시보드)
8. [ML 7종 엔진 상태 표시](#8-ml-7종-엔진-상태-표시)
9. [에러 검색 (ML 기반)](#9-에러-검색-ml-기반)
10. [Markov 연쇄 예측 트리](#10-markov-연쇄-예측-트리)
11. [금형 25개 게이지 + XGBoost](#11-금형-25개-게이지--xgboost)
12. [MTBF 예측 정비](#12-mtbf-예측-정비)
13. [매뉴얼 RAG (3 Sub-Tab)](#13-매뉴얼-rag-3-sub-tab)
14. [RTDB live_alarms 실시간 알림](#14-rtdb-live_alarms-실시간-알림)
15. [파일 구조](#15-파일-구조)
16. [단계 분할 — Phase 1~5](#16-단계-분할--phase-15)
17. [검증 체크리스트](#17-검증-체크리스트)
18. [위험 + 완화](#18-위험--완화)
19. [Day 6-7 비스코프](#19-day-6-7-비스코프)
20. [시간 분배표](#20-시간-분배표)
21. [사용자 결정 대기](#21-사용자-결정-대기)

---

## 1. 목적 + 요구사항

### 1-1. 목표
백엔드 `features/equipment/*` 19 모듈을 React UI로 노출 + Plotly 시각화 + Firebase 실시간 통합. **본선 평가 핵심 #2 (실동작 ML 7종) + #5 (Nelson 8 Rules SPC)** 의 차별점 시연.

### 1-2. 비즈니스 요구사항

| # | 요구사항 | 근거 | 사양 |
|:--:|---|---|---|
| 1 | 5 Sub-Tab (설비개요/긴급조치/장비유형/예측정비/ML엔진) | F-2-12 | Day 6 |
| 2 | 5공정 건강 카드 (CCH/OBC/범퍼빔/도어/볼시트) | F-2-5 | 신호등 + Cpk + 위반 수 |
| 3 | Plotly 관리도 + Nelson 8 Rules 위반 음영 | F-2-5 | Day 6 ⭐ |
| 4 | ML 7종 엔진 상태 표시기 | F-2-12 | 모델별 상태 |
| 5 | 에러 검색 (ML 의도 분류 + 카테고리) | F-2-2 | Day 7 |
| 6 | Markov 연쇄 트리 시각화 (Plotly Network) | F-2-4 | Day 7 |
| 7 | 금형 25개 게이지 + XGBoost 잔여수명 | F-2-8 | Day 7 |
| 8 | MTBF 차트 (15대 × 240건) | F-2-9 | Day 7 |
| 9 | CSV 업로드 인터페이스 | F-2-7 | Day 7 |
| 10 | 매뉴얼 RAG 3 Sub-Tab (에러코드/증상/AI질의) | F-2-13 | Day 7 |
| 11 | SPC 위반 → RTDB `/live_alarms/{id}` 푸시 | Day 6 Firebase | Toast + 사이드바 점멸 |
| 12 | 에러 발생 이력 685건 Firestore | Day 7 Firebase | F-2-10 |
| 13 | 금형 25개 Firestore 실시간 동기화 | Day 7 | mold_lifecycle |
| 14 | 매뉴얼 PDF Storage → ChromaDB 인덱싱 | Day 7 | F-2-13 |

### 1-3. 비기능 요구사항

| 항목 | 목표 |
|---|---|
| Plotly 관리도 렌더 | <500ms (lazy import + 200 데이터 포인트) |
| Nelson 8 Rules 검출 | <100ms (백엔드 spc_analyzer) |
| ML 모델 추론 | <200ms (이미 트레이닝됨, 추론만) |
| RTDB 알람 latency | <300ms (push → 구독 갱신) |
| 5 Sub-Tab 전환 | <50ms (lazy mount) |
| TS strict | 0 오류 |

### 1-4. 비범위 (Day 6-7)
- ❌ 매뉴얼 PDF 업로드 UI (Day 12) — 인덱싱 endpoint 만
- ❌ 도면 검색 풀 UI (drawing_search.py) — Day 11 또는 비범위
- ❌ 점검 체크리스트 풀 UI (F-2-11, inspection_db.py) — Day 12
- ❌ 부서 기반 접근 제어 풀 통합 (F-2-14) — Day 11 인사
- ❌ Cloud Functions 트리거 — Day 14
- ❌ XGBoost 재학습 UI — 운영 범위

---

## 2. 기존 자산 인벤토리 (19 모듈)

### 2-1. `features/equipment/*` (~6,200줄)

| 모듈 | 줄 | 역할 | Day 6-7 활용 |
|---|---:|---|---|
| `spc_ml_predictor.py` | 649 | ML SPC 이상 탐지 (Isolation Forest) | ⭐ Phase 3 |
| `ml_error_search.py` | 569 | TF-IDF + 의도 분류 ML 에러 검색 | ⭐ Phase 4 |
| `mold_ml_predictor.py` | 553 | XGBoost 금형 잔여수명 | ⭐ Phase 4 |
| `spc_realtime.py` | 542 | Nelson 8 Rules + 5공정 대시보드 | ⭐ Phase 3 |
| `markov_predictor.py` | 427 | Markov 연쇄 고장 예측 | ⭐ Phase 4 |
| `maintenance_predictor.py` | 359 | MTBF 예측 정비 | ⭐ Phase 5 |
| `inspection_db.py` | 314 | 점검 체크리스트 DB | △ Phase 2 (메타만) |
| `spc_analyzer.py` | 284 | SPC 통계 + 평균/표준편차 | ⭐ Phase 3 |
| `error_causality.py` | 281 | 에러 인과 규칙 | ⭐ Phase 4 |
| `mold_lifecycle.py` | 263 | 금형 25개 라이프사이클 | ⭐ Phase 4 |
| `manual_rag.py` | 256 | 매뉴얼 RAG (PDF 인덱싱 + 검색) | ⭐ Phase 5 |
| `drawing_search.py` | 225 | 도면 검색 | △ 비스코프 |
| `error_history_db.py` | ~150 | 에러 발생 이력 685건 | ⭐ Phase 4 |
| `error_code_db.py` | ~150 | 에러코드 DB (F-2-1) | ⭐ Phase 5 |
| `dashboard_data.py` | ~150 | 통합 대시보드 데이터 | ⭐ Phase 2 |
| `spc_dashboard.py` | ~150 | SPC 대시보드 helper | ⭐ Phase 3 |
| `spc_data_generator.py` | ~150 | SPC 데이터 생성기 (F-2-7) | ⭐ Phase 3 |
| `spc_report_generator.py` | ~150 | SPC 리포트 PDF | △ Phase 5 |

### 2-2. `data/equipment/` (보존 자산)

- `manuals/` — PDF 매뉴얼 (ChromaDB 인덱싱 대상)
- `error_codes/` — 에러코드 DB JSON
- `mold/` — 금형 25개 메타
- `spc/` — 5공정 SPC 데이터

### 2-3. 백엔드 라우터

**현재**: `backend/routers/equipment.py` **미존재** → Phase 1 에서 신규 작성.

권장 신규 ~12 엔드포인트:
- GET `/api/equipment/dashboard/overview` — 5공정 건강 + 메트릭
- GET `/api/equipment/spc/{process_id}` — 관리도 데이터 + Nelson 위반
- GET `/api/equipment/spc/violations/recent` — 최근 위반 N개
- POST `/api/equipment/error/search` — ML 에러 검색
- GET `/api/equipment/error/categories` — 카테고리 + 39 동의어
- GET `/api/equipment/markov/{error_code}` — 연쇄 트리
- GET `/api/equipment/molds` — 25개 금형 + 잔여수명
- GET `/api/equipment/mtbf` — 15대 × 240건
- GET `/api/equipment/ml-engines/status` — 7종 모델 상태
- POST `/api/equipment/manual/search` — 매뉴얼 RAG
- POST `/api/equipment/spc/upload-csv` — CSV 업로드 + 분석
- GET `/api/equipment/inspection/checklist/{type}` — 점검 체크리스트

---

## 3. 본선 평가 매칭

| 본선 평가 # | 차별점 | Day 6-7 어디서 시연 |
|:--:|---|---|
| **#2 실동작 ML 7종** ⭐ | TF-IDF / Isolation Forest / XGBoost / Markov / RF / 인과규칙 / RAG | ML 엔진 탭 + 에러 검색 + 금형 + Markov + RAG |
| **#5 Nelson 8 Rules SPC** ⭐ | 8 패턴 자동 감지 + Plotly 음영 | 설비 개요 → 5공정 카드 → 클릭 → 관리도 + Nelson |
| #1 LLM 폴백 | (Day 4 완성) | 매뉴얼 RAG AI 질의 (LLM 사용) |
| #3 Firebase 풀스택 | RTDB 실시간 알람 + Firestore + Storage | live_alarms + 685건 이력 + 매뉴얼 PDF |
| #7 온프레미스+클라우드 하이브리드 | 사내 ML + Firebase 실시간 | 모든 ML 추론은 사내 + 알림은 Firebase |

---

## 4. 아키텍처

```
┌──────────────────────────────────────────────────────────────────┐
│  React /equipment 페이지 (HUD Command Center 패턴)               │
│                                                                   │
│  TopBar + LeftSidebar                                             │
│   ├── 사이드바 모듈 F 점멸 (RTDB live_alarms 구독 시)            │
│                                                                   │
│  메인 영역:                                                       │
│   ├── EquipmentHeader: 5공정 미니 신호등 + 알람 카운트            │
│   ├── EquipmentSubTabs (5탭):                                     │
│   │    [설비 개요][긴급 조치][장비 유형][예측 정비][ML 엔진]      │
│   │                                                                │
│   ├── 설비 개요 탭:                                                │
│   │    - ProcessHealthCards (5공정)                               │
│   │    - 핵심 메트릭 (5종)                                        │
│   │    - 7장비 카드                                                │
│   │                                                                │
│   ├── 긴급 조치 탭:                                                │
│   │    - 진행 중 알람 (RTDB live_alarms)                          │
│   │    - 우선순위 정렬                                            │
│   │                                                                │
│   ├── 장비 유형 탭:                                                │
│   │    - 7장비별 상태 + ML 경고                                   │
│   │    - SPC 관리도 + Nelson 위반 음영 (Plotly)                  │
│   │                                                                │
│   ├── 예측 정비 탭:                                                │
│   │    - MTBF 차트 (Plotly)                                       │
│   │    - 다음 정비 예측                                           │
│   │    - 비용 TOP 5                                                │
│   │                                                                │
│   └── ML 엔진 탭:                                                  │
│        - 7종 모델 상태 표시기                                     │
│        - 모델별 정확도 + 마지막 학습일                            │
│                                                                   │
│  Day 7 추가 (다른 라우트 또는 모달):                              │
│   - ErrorSearchPanel (에러 검색)                                  │
│   - MarkovTreePanel (Plotly Network)                              │
│   - MoldGaugePanel (25 게이지)                                    │
│   - ManualRagPanel (3 Sub-Tab)                                    │
└────────────┬─────────────────────────────────────────────────────┘
             │
             ▼
┌──────────────────────────────────────────────────────────────────┐
│  FastAPI :8000  backend/routers/equipment.py (신규 12 엔드포인트) │
│   features/equipment/* 19 모듈 직접 import                       │
└────────────┬─────────────────────────────────────────────────────┘
             │
             ▼
┌──────────────────────────────────────────────────────────────────┐
│  Firebase                                                         │
│  ├── RTDB: /live_alarms/{id}      (실시간 알람 푸시 + 구독)       │
│  ├── Firestore: error_history/    (685건 에러 이력)              │
│  ├── Firestore: molds/            (25 금형 실시간)                │
│  └── Storage:   /manuals/         (PDF + ChromaDB 인덱싱)         │
└──────────────────────────────────────────────────────────────────┘
```

---

## 5. 5 Sub-Tab UI 사양

### 5-1. 탭 정의 (FEATURE F-2-12)

| 탭 | id | 콘텐츠 | 차별점 |
|---|---|---|---|
| **설비 개요** | `overview` | 5공정 건강 카드 + 메트릭 5종 + 7장비 카드 | 첫 인상 |
| **긴급 조치** | `alerts` | RTDB 알람 + 우선순위 | 실시간 |
| **장비 유형** | `equipment` | 7장비별 SPC + ML 경고 + Plotly Nelson | ⭐ #5 SPC |
| **예측 정비** | `predictive` | MTBF + 다음 정비 + 비용 TOP 5 | ⭐ XGBoost |
| **ML 엔진** | `ml` | 7종 ML 모델 상태 표시기 | ⭐ #2 ML 7종 |

### 5-2. 디폴트 + 영구화

- 디폴트: `overview`
- `useUIStore.equipmentSubTab: 'overview' | 'alerts' | 'equipment' | 'predictive' | 'ml'` + persist

---

## 6. SPC Nelson 8 Rules + Plotly 시각화

### 6-1. 8 Rules (FEATURE L1209~)

| Rule | 패턴 | 색 |
|:--:|---|---|
| 1 | 1점이 ±3σ 초과 | 🔴 critical |
| 2 | 9점 연속 같은 측 (평균 이동) | 🟡 warning |
| 3 | 6점 연속 증가 또는 감소 | 🟡 |
| 4 | 14점 교대 증감 | 🟡 |
| 5 | 3점 중 2점이 ±2σ 초과 | 🟠 |
| 6 | 5점 중 4점이 ±1σ 초과 | 🟠 |
| 7 | 15점 연속 ±1σ 이내 (분산 감소) | 🟢 info |
| 8 | 8점 연속 ±1σ 외부 | 🟠 |

### 6-2. Plotly 관리도 시각화

`<SPCChart processId={id} />` (~180줄):
- 데이터: `GET /api/equipment/spc/{process_id}` → `{ values, ucl, lcl, mean, sigma, violations: [{rule, points, severity}] }`
- Plotly `Scatter` (라인 + 마커)
- UCL/LCL 점선 (`shapes: line`)
- ±1σ, ±2σ 음영 영역 (`shapes: rectangle` opacity 0.1)
- Nelson 위반 — `annotations` 풍선 + 점 색상 변경
- 위반 hover → 한국어 설명 (`spc_realtime.py` 가이드 딕셔너리)

### 6-3. 위반 카운트 + 신호등

- 5공정 건강 카드 (Section 7) 에 위반 수 + 신호등 (●●●)
- 위반 0개: 🟢 양호 / 1~2: 🟡 주의 / 3+: 🔴 위험

---

## 7. 5공정 건강 대시보드

### 7-1. 5공정 (FEATURE)

| 공정 | id | 핵심 지표 |
|---|---|---|
| **CCH** (Center Console Housing) | `cch` | Cpk + 위반 수 |
| **OBC** (On-Board Charger) | `obc` | 동일 |
| **범퍼빔** | `bumper_beam` | 동일 |
| **도어** | `door` | 동일 |
| **볼시트** | `ball_seat` | 동일 |

### 7-2. UI

```
┌─ CCH ────────┐  ┌─ OBC ────────┐  ┌─ 범퍼빔 ─────┐  ┌─ 도어 ───────┐  ┌─ 볼시트 ─────┐
│ ● 양호       │  │ ● 주의       │  │ ● 양호       │  │ ● 위험       │  │ ● 양호       │
│ Cpk 1.42     │  │ Cpk 1.18     │  │ Cpk 1.55     │  │ Cpk 0.94     │  │ Cpk 1.61     │
│ 위반 0       │  │ 위반 1 (R2)  │  │ 위반 0       │  │ 위반 3 (R1,5)│  │ 위반 0       │
│ [차트 보기 ▶]│  │ [차트 보기 ▶]│  │ [차트 보기 ▶]│  │ [차트 보기 ▶]│  │ [차트 보기 ▶]│
└──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘
```

`<ProcessHealthCards />` (~120줄), `<ProcessHealthCard />` (~80줄)

클릭 시 → 장비 유형 탭 자동 전환 + 해당 공정 SPC 차트 표시

---

## 8. ML 7종 엔진 상태 표시

### 8-1. ML 7종 (FEATURE F-2-12)

| # | 모델 | 모듈 | 종류 |
|:--:|---|---|---|
| 1 | **TF-IDF + 의도 분류** | ml_error_search.py | sklearn |
| 2 | **Isolation Forest** | spc_ml_predictor.py | sklearn |
| 3 | **XGBoost 금형 수명** | mold_ml_predictor.py | xgboost |
| 4 | **Markov Chain** | markov_predictor.py | numpy |
| 5 | **Random Forest MTBF** | maintenance_predictor.py | sklearn |
| 6 | **에러 인과 규칙** | error_causality.py | rule-based |
| 7 | **매뉴얼 RAG (bge-m3 + ChromaDB)** | manual_rag.py | embedding |

### 8-2. ML 엔진 탭 UI

```
┌─ ML ENGINES · 7종 ─────────────────────────────┐
│                                                  │
│ ① TF-IDF 의도 분류        [● 정상] 95.2% (2일 전)│
│ ② Isolation Forest SPC    [● 정상] 87.4% (오늘)  │
│ ③ XGBoost 금형 수명       [● 정상] 91.8% (3일 전)│
│ ④ Markov 연쇄 예측        [● 정상] 82.1% (1주 전)│
│ ⑤ Random Forest MTBF      [● 정상] 89.5% (5일 전)│
│ ⑥ 에러 인과 규칙          [● 정상] 100%  (정적)  │
│ ⑦ 매뉴얼 RAG (bge-m3)     [● 정상] -      (실시간)│
│                                                  │
│ [재학습 요청] [모델 정보] [추론 로그]            │
└──────────────────────────────────────────────────┘
```

`<MLEnginesTab />` (~150줄)

각 모델: 정확도 + 마지막 학습일 + 상태 (정상/경고/오류)

---

## 9. 에러 검색 (ML 기반)

### 9-1. 흐름 (F-2-2)

1. 사용자 입력: "프레스 라인 진동 심함" (자연어)
2. TF-IDF 벡터화 + 카테고리 분류 (39 동의어 매칭)
3. ML 결과 카드 — 에러코드 후보 TOP 3 + 신뢰도
4. 인과 규칙 매칭 → 원인 + 조치 제시
5. 매뉴얼 RAG → 관련 PDF 인용

### 9-2. 백엔드 — `POST /api/equipment/error/search`

```python
@router.post("/error/search")
async def error_search(req: ErrorSearchRequest, user=Depends(get_current_user)):
    # ML 검색
    results = ml_error_search.search(req.query, top_k=3)
    
    # 인과 규칙
    causality = error_causality.match(results[0].error_code) if results else None
    
    # 매뉴얼 인용
    manual_excerpts = manual_rag.search(req.query, top_k=2)
    
    return {
        "results": results,         # [{error_code, name, score, category}, ...]
        "causality": causality,     # {causes, actions}
        "manual_excerpts": manual_excerpts,
    }
```

### 9-3. Frontend `<ErrorSearchPanel />`

신규 (~180줄). 입력 + 카테고리 dropdown + ML 결과 카드 (3) + 인과 + 매뉴얼 인용.

---

## 10. Markov 연쇄 예측 트리

### 10-1. 사양 (F-2-4)

에러코드 입력 → 다음 발생 가능 에러 TOP-N + 확률 (Markov chain).

### 10-2. 백엔드 — `GET /api/equipment/markov/{error_code}`

```python
@router.get("/markov/{error_code}")
async def markov_chain(error_code: str, depth: int = 3, user=Depends(get_current_user)):
    tree = markov_predictor.predict_chain(error_code, depth=depth)
    return {"tree": tree}  # {root, children: [{code, prob, children}, ...]}
```

### 10-3. Frontend `<MarkovTree />`

Plotly Network graph (sankey 또는 tree):
- 노드: 에러코드
- 엣지: 확률 (두께)
- 색상: 심각도

신규 (~150줄)

---

## 11. 금형 25개 게이지 + XGBoost

### 11-1. UI

5×5 그리드 — 25개 금형 게이지 카드. 각 카드:
- 금형 ID
- 사용 횟수 / 한계
- XGBoost 잔여수명 예측 (일 단위)
- 색상: 잔여 30일+ 녹색 / 7~30 노랑 / <7 빨강

### 11-2. 백엔드 — `GET /api/equipment/molds`

```python
@router.get("/molds")
async def molds_list(user=Depends(get_current_user)):
    molds = mold_lifecycle.list_all()
    for m in molds:
        m["remaining_days"] = mold_ml_predictor.predict_remaining(m["id"])
    return {"items": molds}
```

### 11-3. Frontend `<MoldGrid />`

신규 (~140줄). Firestore `molds/` 실시간 동기화 (Day 3 useFirestoreCollection).

---

## 12. MTBF 예측 정비

### 12-1. 사양 (F-2-9)

15대 × 240건 정비 이력 → MTBF (Mean Time Between Failures) 차트 + 다음 정비 예측.

### 12-2. 백엔드 — `GET /api/equipment/mtbf`

```python
@router.get("/mtbf")
async def mtbf_data(user=Depends(get_current_user)):
    data = maintenance_predictor.compute_mtbf(top_n=15)
    return {
        "items": data,  # [{equipment_id, mtbf_hours, next_maintenance, cost_estimate}, ...]
        "top5_cost": maintenance_predictor.top_n_cost(5),
    }
```

### 12-3. Frontend `<MTBFChart />`

Plotly Bar (15대 MTBF) + Table (다음 정비 + 비용). 신규 (~120줄)

---

## 13. 매뉴얼 RAG (3 Sub-Tab)

### 13-1. 3 Sub-Tab (F-2-13)

| Sub-Tab | 콘텐츠 |
|---|---|
| **에러코드** | 검색 + 카테고리 필터 |
| **증상 가이드** | 39 동의어 + 카테고리 매칭 |
| **AI 질의** | LLM + RAG (bge-m3 임베딩) |

### 13-2. 백엔드

- `GET /api/equipment/error/categories` — 39 동의어 + 카테고리
- `POST /api/equipment/manual/search` — RAG 검색

AI 질의는 LLM 라우터 `chat` 모드 + manual_rag 컨텍스트 주입.

### 13-3. Frontend `<ManualRagPanel />`

3 Sub-Tab + 검색 + 결과 카드. 신규 (~200줄)

---

## 14. RTDB live_alarms 실시간 알림

### 14-1. 흐름

```
백엔드 SPC ML 검출 → 위반 발생 → RTDB push /live_alarms/{id}
   { severity, process, rule, timestamp, message }
        ↓
React useRTDBValue 구독 (Day 3 훅)
        ↓
Toast 알림 + 사이드바 모듈 F 점멸
```

### 14-2. 백엔드 푸시 (cron 또는 SSE 트리거)

옵션 B (Firebase 직접) — Frontend 가 5초 폴링 + 검출 시 RTDB push.
또는 백엔드 admin SDK (옵션 A) — 위반 시 자동 push. Day 5+ 결정상 옵션 B 유지.

권장: **Frontend 5초 폴링 → 검출 시 RTDB push**:
```typescript
// useSPCAlarms.ts
useEffect(() => {
  const id = setInterval(async () => {
    const newAlarms = await fetchSPCViolationsRecent(lastSeenTs);
    newAlarms.forEach((a) => {
      pushToRTDB(`live_alarms/${a.id}`, a);
      addToast({ type: a.severity, message: a.message });
    });
  }, 5000);
  return () => clearInterval(id);
}, [lastSeenTs]);
```

### 14-3. 사이드바 점멸

`useUIStore.activeAlarmCount` 증가 시 `LeftSidebar` 의 모듈 F 카드에 점멸 애니메이션 (CSS keyframe).

---

## 15. 파일 구조

### 15-1. 신규/갱신 파일

```
ajin-ai-assistant-react/
├── backend/
│   ├── routers/
│   │   └── equipment.py                  ⭐ 신규 (~350줄, 12 엔드포인트)
│   └── schemas/
│       └── equipment.py                  ⭐ 신규 (~150줄)
└── frontend/src/
    ├── routes/
    │   └── equipment.tsx                 갱신 (19 → ~280)
    ├── components/
    │   └── equipment/                    ⭐ 신규 디렉토리
    │       ├── EquipmentSubTabs.tsx      ⭐ ~80
    │       ├── OverviewTab.tsx           ⭐ ~150
    │       ├── AlertsTab.tsx             ⭐ ~120
    │       ├── EquipmentTypeTab.tsx      ⭐ ~140
    │       ├── PredictiveTab.tsx         ⭐ ~120
    │       ├── MLEnginesTab.tsx          ⭐ ~150
    │       ├── ProcessHealthCards.tsx    ⭐ ~120
    │       ├── ProcessHealthCard.tsx     ⭐ ~80
    │       ├── SPCChart.tsx              ⭐ ~180 (Plotly)
    │       ├── ErrorSearchPanel.tsx      ⭐ ~180
    │       ├── MarkovTree.tsx            ⭐ ~150 (Plotly Network)
    │       ├── MoldGrid.tsx              ⭐ ~140
    │       ├── MoldGaugeCard.tsx         ⭐ ~70
    │       ├── MTBFChart.tsx             ⭐ ~120 (Plotly)
    │       ├── ManualRagPanel.tsx        ⭐ ~200 (3 Sub-Tab)
    │       └── MLEngineStatusCard.tsx    ⭐ ~70
    ├── hooks/
    │   ├── useSPCAlarms.ts               ⭐ ~80 (5초 폴링 + RTDB push)
    │   └── useEquipmentRTDB.ts           ⭐ ~50
    ├── api/
    │   └── equipment.ts                  ⭐ 신규 (~180)
    ├── store/
    │   ├── equipment.ts                  ⭐ 신규 (~100)
    │   └── ui.ts                         갱신 (+10, equipmentSubTab + activeAlarmCount)
    ├── lib/
    │   └── firestore-equipment.ts        ⭐ 신규 (~80)
    ├── types/
    │   └── equipment.ts                  ⭐ 신규 (~80)
    ├── styles/
    │   └── components.css                갱신 (+~250)
    └── i18n/
        ├── ko/common.json                갱신 (+~60 키)
        └── en/common.json                갱신 (+~60 키)
```

### 15-2. 줄 수 합계

| 카테고리 | 신규 | 갱신 |
|---|---:|---:|
| 백엔드 (라우터 + 스키마) | ~500 | — |
| Frontend equipment 컴포넌트 16개 | ~2,090 | — |
| hooks/api/store/lib/types | ~570 | +10 |
| equipment.tsx | — | +260 |
| styles | — | +250 |
| i18n | — | +120 |
| **합계** | **~3,160** | **~640** |

총 **~3,800줄** (Day 6+7 통합).

---

## 16. 단계 분할 — Phase 1~5

### Phase 1 — 백엔드 12 신규 엔드포인트 (~60분)
- [ ] `backend/schemas/equipment.py` 신규 (요청/응답 스키마)
- [ ] `backend/routers/equipment.py` 신규 — 12 엔드포인트
- [ ] `backend/main.py` 에 `app.include_router(equipment.router, prefix="/api")` 추가
- [ ] `features/equipment/*` 모듈 import 검증 (st.* 의존 없는지)

검증: 12 엔드포인트 OpenAPI 등록 + curl 테스트

### Phase 2 — Frontend OVERVIEW + ML 엔진 탭 (Day 6 핵심) (~60분)
- [ ] `frontend/src/types/equipment.ts`
- [ ] `frontend/src/store/{equipment,ui}.ts` 갱신
- [ ] `frontend/src/api/equipment.ts`
- [ ] `frontend/src/components/equipment/EquipmentSubTabs.tsx`
- [ ] `OverviewTab.tsx` + `ProcessHealthCards.tsx` + `ProcessHealthCard.tsx`
- [ ] `MLEnginesTab.tsx` + `MLEngineStatusCard.tsx`
- [ ] `frontend/src/routes/equipment.tsx` 본격 구현 (5탭 통합)

검증: `/equipment` 진입 → 5 sub-tab 동작 + 5공정 카드 + ML 7종 표시

### Phase 3 — SPC Plotly Nelson + 장비 유형 탭 + RTDB 알람 (~60분)
- [ ] `EquipmentTypeTab.tsx` + `SPCChart.tsx` (Plotly Nelson)
- [ ] `AlertsTab.tsx` (RTDB live_alarms 구독)
- [ ] `frontend/src/hooks/useSPCAlarms.ts` (5초 폴링 + RTDB push)
- [ ] `frontend/src/hooks/useEquipmentRTDB.ts`
- [ ] LeftSidebar 모듈 F 점멸 애니메이션

검증: 5공정 카드 클릭 → SPC 관리도 + Nelson 위반 음영 + RTDB 알람 시 Toast + 사이드바 점멸

### Phase 4 — Day 7 에러 검색 + Markov + 금형 + MTBF (~60분)
- [ ] `ErrorSearchPanel.tsx` (ML 의도 분류)
- [ ] `MarkovTree.tsx` (Plotly Network)
- [ ] `MoldGrid.tsx` + `MoldGaugeCard.tsx` (25 게이지)
- [ ] `MTBFChart.tsx` (Plotly Bar) + `PredictiveTab.tsx`
- [ ] `frontend/src/lib/firestore-equipment.ts` (685건 + 25 금형 동기화)

검증: 에러 검색 → 결과 카드 / Markov 트리 / 금형 25 게이지 / MTBF 차트

### Phase 5 — 매뉴얼 RAG + i18n + 통합 검증 (~30분)
- [ ] `ManualRagPanel.tsx` (3 Sub-Tab)
- [ ] i18n 한·영 키 60개 추가
- [ ] 본선 시연 시나리오 추가 검증 (#5 SPC + #2 ML 7종)

---

## 17. 검증 체크리스트

### 17-1. 코드
- [ ] TS strict 0 오류
- [ ] pytest `test_llm_router.py` 30/30 PASS 유지
- [ ] 외부 npm 추가 0 (`react-plotly.js` Day 3 이미 있음)
- [ ] Day 1~5++ 다른 라우트 손상 0

### 17-2. 기능
- [ ] 5 Sub-Tab 전환 정상
- [ ] 5공정 건강 카드 (CCH/OBC/범퍼빔/도어/볼시트) 신호등 + Cpk + 위반 수
- [ ] Plotly 관리도 + Nelson 8 Rules 위반 음영 + 풍선
- [ ] ML 7종 엔진 상태 표시 (정확도 + 마지막 학습일)
- [ ] 에러 검색 → ML 결과 + 인과 + 매뉴얼 인용
- [ ] Markov 트리 (Plotly Network) 시각화
- [ ] 금형 25개 게이지 + XGBoost 잔여수명
- [ ] MTBF 차트 (15대 × 240건)
- [ ] 매뉴얼 RAG 3 Sub-Tab (에러코드/증상/AI질의)
- [ ] RTDB live_alarms 푸시 + 구독 + Toast
- [ ] LeftSidebar 모듈 F 점멸 애니메이션

### 17-3. UX
- [ ] HUD Command Center 패턴
- [ ] Plotly 차트 라이트/다크 자동 (Day 3 useTheme)
- [ ] 모바일 768/1024 반응형 (5 Sub-Tab → Drawer 또는 horizontal scroll)
- [ ] 5 sub-tab persist

### 17-4. 본선 시연 추가
- 시연 7: F 진입 → 도어 공정 위반 3건 → 클릭 → Plotly Nelson Rule 1, 5 음영 표시
- 시연 8: ML 엔진 탭 → 7종 모델 정확도 + 학습일 표시 (실동작 차별점)
- 시연 9: 에러 검색 → "프레스 진동" → ML 결과 TOP 3 + 인과
- 시연 10: 금형 25 게이지 → 5번 금형 빨강 → 클릭 → XGBoost 잔여 3일 + 매뉴얼 인용

---

## 18. 위험 + 완화

| # | 위험 | 영향 | 완화 |
|:--:|---|:--:|---|
| 1 | features/equipment/* Streamlit st.* 의존 | 🔴 | Day 5/8 패턴 — 데이터 함수만 분리 검증 |
| 2 | Plotly 번들 크기 (1MB+) | 🟡 | lazy import + Day 3 PlotlyChart 컴포넌트 재사용 |
| 3 | XGBoost 모델 파일 부재 | 🟡 | mock 응답 또는 사전 학습 파일 확인 — features/equipment/models/ |
| 4 | ChromaDB 매뉴얼 인덱스 부재 | 🟡 | Phase 5 또는 mock 응답 |
| 5 | RTDB 5초 폴링 비용 | 🟢 | 본선 데모 30분 — 무시 가능 |
| 6 | Plotly Network 한국어 폰트 | 🟢 | font-family inherit |
| 7 | 19 모듈 import 시간 (cold start) | 🟡 | lifespan에서 사전 import + lazy load |
| 8 | 5 sub-tab 동시 mount 메모리 | 🟡 | React lazy + Suspense |
| 9 | 685건 에러 이력 Firestore 쓰기 | 🟢 | Day 7 시드 한 번만 |
| 10 | SPC 관리도 200 데이터 포인트 렌더 | 🟢 | Plotly 충분히 빠름 |

---

## 19. Day 6-7 비스코프

| # | 항목 | 일정 |
|:--:|---|---|
| 1 | 매뉴얼 PDF 업로드 UI | Day 12 |
| 2 | 도면 검색 풀 UI (drawing_search.py) | 비범위 |
| 3 | 점검 체크리스트 풀 UI (F-2-11) | Day 12 |
| 4 | 부서 기반 접근 제어 풀 통합 (F-2-14) | Day 11 |
| 5 | XGBoost 재학습 UI | 비범위 |
| 6 | SPC 리포트 PDF 자동 생성 (F-2-7 보강) | Day 12 |
| 7 | Cloud Functions 트리거 | Day 14 |
| 8 | 모바일 Plotly 차트 폴리싱 | Day 12 |

---

## 20. 시간 분배표 (총 3.5~4h)

| 시간대 | 작업 |
|:--:|---|
| 00:00 ~ 00:10 | features/equipment/* 호환성 검증 + 백엔드 시작 |
| 00:10 ~ 01:10 | Phase 1 — 백엔드 12 신규 엔드포인트 |
| 01:10 ~ 01:15 | Phase 1 검증 (curl + Swagger) |
| 01:15 ~ 02:15 | Phase 2 — Frontend OVERVIEW + ML 엔진 탭 (Day 6 핵심) |
| 02:15 ~ 03:15 | Phase 3 — SPC Plotly Nelson + 장비 유형 + RTDB 알람 |
| 03:15 ~ 04:15 | Phase 4 — Day 7 에러 검색 + Markov + 금형 + MTBF |
| 04:15 ~ 04:45 | Phase 5 — 매뉴얼 RAG + i18n + 통합 검증 |

---

## 21. 사용자 결정 대기

| # | 결정 | 권장 |
|:--:|---|---|
| 1 | **위임 방식** | `executor` (opus) — Day 6 (Phase 1~3) + Day 7 (Phase 4~5) 분할 |
| 2 | **디폴트 sub-tab** | `overview` (첫 인상) |
| 3 | **RTDB 알람 방식** | 옵션 B (Frontend 5초 폴링 + RTDB push) — admin SDK 미도입 |
| 4 | **Plotly 라이브러리** | Day 3 의 `react-plotly.js` 재사용 |
| 5 | **XGBoost 모델 파일 부재 시** | mock 응답 (Day 6-7 구현, Day 12+ 에 실 모델 학습) |
| 6 | **685건 에러 이력 Firestore 시드** | Phase 4 자동 또는 사용자 별도 스크립트 |
| 7 | **사이드바 점멸 애니메이션** | CSS keyframe pulse 1.6s |
| 8 | **5 sub-tab 모바일 처리** | horizontal scroll (Drawer 보단 단순) |

권장 디폴트로 진행해도 무방하면 즉시 위임 가능.

---

## 변경 이력

| 버전 | 날짜 | 변경 |
|---|---|---|
| **1.0** | 2026-04-27 | 초안 — 21 섹션 / 신규 ~3,160 + 갱신 ~640 / Phase 5분할 / 본선 평가 #2 + #5 매핑 |

---

**관련 문서**:
- [DAY5_PLAN.md](DAY5_PLAN.md) — Day 5 패턴 (features/onboarding wrapping)
- [LLM_ROUTER_PLAN.md](LLM_ROUTER_PLAN.md) — 백엔드 라우터
- [FINAL_17DAY_PLAN.md](FINAL_17DAY_PLAN.md) — Day 6 (L337) + Day 7 (L349)
- [FEATURE_SPECIFICATION.md](../features/FEATURE_SPECIFICATION.md) — F-2-1 ~ F-2-15 (L1177~1320)
- `uiux/AJIN AI Assistant Design System_v2/README.md` — HUD 패턴
