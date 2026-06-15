# 기능 F — 설비·공정 AI / SPC (Equipment · Process · Statistical Process Control)

> **이 문서는 누구를 위한 것인가요?**
> 개발자가 아닌 분 (생산관리·품질보증·자동화·정비·금형 담당자) 도 끝까지 읽을 수 있도록 작성했습니다.
> 어려운 용어는 처음 등장할 때 _기울임_ 으로 표시하고 옆에 짧은 설명을 붙입니다.

---

## 1. 한 줄 요약

**"공장 설비의 모든 이상 신호를 실시간 감지하고, 다음 고장을 예측하며, 매뉴얼·도면·점검 이력까지 한 화면에서 조회하는 통합 설비 AI"입니다.**

5 공정 (EWP·CCH·범퍼·시트레일 등) 의 SPC 관리도를 **Nelson 8 규칙** 으로 실시간 감시하고, 7 장비 종류의 에러 코드를 검색하면 (1) 발생 이력, (2) Markov 연쇄 (다음 고장 예측), (3) 매뉴얼 RAG, (4) 인과 분석, (5) MTBF (평균 고장 간격) 까지 자동으로 보여줍니다. **금형 lifecycle 머신러닝 예측** + **685건 에러 이력 시딩** + **79개 동의어 사전** + **3 종 점검 (일상/정기/특별) 체크리스트** 까지 포함된 종합 콘솔.

---

## 2. 누가, 언제 쓰는가?

| 사용자 | 시나리오 | 기능 F 가 해주는 일 |
|---|---|---|
| **생산관리팀 부장** | 공장 현장에서 SPC 이상 발견 | `/equipment/spc/{process}` — Nelson 8 규칙 위반 즉시 알림 + 원인·조치 카드 |
| **품질보증팀 과장** | EWP 라인 Cpk 추세 확인 | 5 공정 신호등 + 12주 추세 그래프 + 골든 시간대 분석 |
| **자동화기술팀** | 프레스 에러 E102 처음 봄 | "프레스 끼임" 또는 "E102" 검색 → 매뉴얼 + 이력 685건 중 유사 사례 |
| **정비 담당** | 다음 정비 일정 결정 | MTBF (평균 고장 간격) + 예측 정비 스코어 |
| **금형생산팀** | 금형 수명 관리 | mold_lifecycle ML 예측 — "금형 X 는 3주 후 균열 가능성 78%" |
| **신입사원** | 에러 코드 매뉴얼 조회 | 동의어 79개로 "프레스가 안 돼요" → E102 자동 매핑 |
| **챗봇 사용자** | "EWP 라인 SPC 어때?" 자연어 | Feature C 의 spc_status 액션 → /equipment/spc 로 자동 디스패치 |

---

## 3. 전체 작동 흐름 (그림으로)

EWP 라인 R1 (Nelson Rule 1 — 한 점이 ±3σ 초과) 위반 발생 시:

```
[현장 PLC / SCADA]
  측정 데이터 (실시간 또는 CSV 업로드)
        │
        │ POST /equipment/spc/upload-csv
        ▼
─────── 사내망 ───────
                                              FastAPI
                                                 │
                                                 ▼
                                          spc_data_generator
                                          (또는 외부 데이터 import)
                                                 │
                                                 ▼
                                          spc_realtime
                                          (Nelson 8 규칙 검사)
                                                 │
                                          ┌──────┴────────┐
                                          ▼               ▼
                                       위반 감지        정상
                                          │               │
                                          ▼               ▼
                                spc_dashboard         (no-op)
                                process_health
                                  신호등 빨강 갱신
                                          │
                                          ▼
                                spc_realtime.enrich_violations()
                                  → R1 가이드 (원인/조치/심각도/차트 주석)
                                          │
                                          ▼
                                컴플라이언스 (D) 협업 티켓 자동 생성?
                                  (선택 — collab_ticket 연동)
                                          │
        ┌─────────────────────────────────┘
        ▼
[브라우저 — /equipment]
   탭 ① "SPC 분석"
     ├─ <ProcessTrafficLights>  — 5 공정 신호등
     ├─ <NelsonChart>           — Plotly 관리도 + add_vrect 음영
     └─ <ViolationsRecent>      — 최근 위반 N건 카드

   탭 ② "에러 검색"
     └─ ml_error_search 자연어 → 매뉴얼 RAG + 이력 매칭

   ...
```

핵심: **데이터 수집 → Nelson 8 규칙 → 위반 시 가이드 enrichment → 컴플라이언스 협업 + 화면**.

---

## 4. 기술 스택

### 4-1. 백엔드 (Backend)

| 카테고리 | 기술 | 역할 |
|---|---|---|
| 언어 | **Python 3.11+** | 서버 + ML |
| 웹 프레임워크 | **FastAPI** | endpoint 수는 [API 인덱스](API.md) 기준 |
| 통계 | **NumPy + SciPy** | SPC 표준편차·관리한계 계산 |
| ML | **scikit-learn** _(머신러닝 라이브러리)_ | 금형 lifecycle 예측 + Markov 연쇄 |
| Markov | **자체 구현** | 다음 에러 코드 확률 분포 |
| RAG | **ChromaDB + bge-m3** | 매뉴얼 RAG 검색 |
| 데이터베이스 | **SQLite × 여러 개** | error_codes / error_history / inspection_logs / mold_lifecycle 등 |
| 시각화 | **Plotly (백엔드 사전 렌더링 + JSON)** | Nelson 차트 + 음영 + annotation |
| LLM (옵션) | **Ollama / Vertex Gemini** | 매뉴얼 RAG 답변 (Phase 2 라우팅 미연동) |

### 4-2. 프론트엔드 (Frontend)

| 카테고리 | 기술 | 역할 |
|---|---|---|
| 언어 | **TypeScript** | 화면 코드 |
| UI | **React** + **Vite** | SPA |
| 상태 관리 | **Zustand** | `useUIStore` (탭 상태) |
| 차트 | **Plotly.js** | 관리도·산포도·MTBF 막대그래프 |
| 그리드 | **자체 카드 컴포넌트** | 5 공정 × 7 장비 매트릭스 |
| 마크다운 | **MarkdownRenderer** | 매뉴얼 RAG 응답 |

### 4-3. 인프라

| 항목 | 값 |
|---|---|
| 컨테이너 | Docker (multi-stage) |
| ML 모델 저장 | `data/mold_ml/`, `data/spc_ml/` (joblib pickle) |
| 데이터 시드 | 685건 에러 이력 (`error_history_db.py:seed`), 5 공정 SPC 합성 데이터 |

### 4-4. 보안

- **Cookie/JWT 인증** — `/api/equipment/*`, `/api/live-alarms/*` 모두 인증 필수
- **RBAC** — 설비 도메인 부서 + 역할 레벨 기준. 생산·품질·자동화·금형·안전 부서는 역할 레벨별 접근, L4+ 는 전사 조회/운영 허용
- **데이터 무결성** — CSV 업로드 시 형식 검증 + 시드 머지 충돌 방지

---

### 4-5. Release Hardening 기준

Feature F release gate는 기능 확장보다 운영 차단 조건을 고정합니다.

| 영역 | 기준 | release 판정 |
|---|---|---|
| Endpoint surface | OpenAPI 기준 `equipment=19`, `live-alarms=2` | 누락 시 fail |
| PLC stream contract | Redis Stream payload 필수 필드: `ts`, `line_id`, `process`, `value`, `lot_id`, `source` | 누락 시 fail |
| Bridge adapter contract | OPC-UA/MQTT/MES adapter는 공통 measurement event로 정규화 후 Redis Stream에 기록 | registry/normalizer 누락 시 fail |
| PLC ingest path | `process_batch()` → `violation_to_alarm()` → `live_events.insert_alarm(domain="equipment")` | persistence 누락 시 fail |
| 실제 현장 OPC-UA bridge | OPC-UA → Redis bridge는 외부 현장 커넥터 범위 | 기본 gate warn, `--require-live-plc`에서 fail/pass |
| 데이터 출처 표시 | Feature F 응답과 UI는 `data_class/source_system/source_label`을 표시. 값은 `real/synthetic/system/unknown` 기준 | lineage 누락 시 fail |
| Offline queue | `/equipment/field` 빠른 점검 제출이 online 직접 제출, offline/network failure 시 IndexedDB queue 저장, 5회 backoff 후 dead-letter | 큐/재시도 연결 누락 시 fail |
| 도면 OCR | request raw path 없이 `drawing_id`만 사용. `data/equipment/drawings*`와 `EQUIPMENT_DRAWING_OCR_ALLOWED_DIRS` 내부 이미지만 읽음 | allowlist 누락 시 fail |
| RBAC | read=L1+ 설비 부서, submit=L2+ 설비 부서, upload/ack/운영=L3+ 설비 부서, L4+ override | 누락 시 fail |

검증 명령:

```bash
make feature-f-release-check
```

현장 PLC 연결까지 운영 검수할 때만:

```bash
.venv/bin/python scripts/verify_feature_f_release.py --strict --require-live-plc --markdown outputs/feature-f-verification/$(date +%F)-feature-f-release.md
```

공식 기준 링크:

- Redis Streams `XREADGROUP`: https://redis.io/docs/latest/commands/xreadgroup/
- MQTT Specification: https://mqtt.org/mqtt-specification/
- MDN IndexedDB: https://developer.mozilla.org/en-US/docs/Web/API/IndexedDB_API
- MDN Service Worker: https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API
- MDN Web App Manifest: https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Manifest
- OPC Foundation OPC UA: https://opcfoundation.org/developer-tools/specifications-unified-architecture/

MES는 벤더별 API가 달라 범용 공식 API 문서를 특정할 수 없습니다. 실제 MES connector 구현 전에는 해당 벤더의 공식 인터페이스 문서를 별도 승인 기준으로 추가해야 합니다.

---

## 5. 백엔드 Endpoint 목록

현재 endpoint 총수는 FastAPI OpenAPI 산출물인 [API 인덱스](API.md)를 기준으로 확인합니다. Feature F release baseline은 `equipment=19`, `live-alarms=2`입니다.

| 메서드 | 경로 | 용도 | 응답 |
|---|---|---|---|
| `GET` | `/api/equipment/dashboard/overview` | 대시보드 5 공정 + 설비 + ML 엔진 통합 | `OverviewResponse` |
| `GET` | `/api/equipment/spc/{process_id}` | SPC 관리도 + Nelson 위반 | `SPCResponse` (UCL/CL/LCL + violations) |
| `GET` | `/api/equipment/spc/violations/recent` | 최근 위반 N건 | `ViolationsResponse` |
| `POST` | `/api/equipment/spc/upload-csv` | SPC 데이터 CSV 업로드 | `SPCUploadResponse` |
| `POST` | `/api/equipment/error/search` | 에러 코드 + 자연어 검색 | `ErrorSearchResponse` |
| `GET` | `/api/equipment/error/categories` | 카테고리 그룹 (7 장비 × 40 증상) | `ErrorCategoriesResponse` |
| `GET` | `/api/equipment/markov/{error_code}` | Markov 다음 고장 예측 | `MarkovResponse` (확률 분포 + cascade) |
| `GET` | `/api/equipment/molds` | 금형 lifecycle 목록 | `MoldsResponse` |
| `GET` | `/api/equipment/mtbf` | 평균 고장 간격 + Top Cost | `MTBFResponse` |
| `GET` | `/api/equipment/ml-engines/status` | 7종 ML/검색 엔진 상태 (error/spc/mold/markov/mtbf/causality/manual) | `MLEnginesStatusResponse` |
| `POST` | `/api/equipment/manual/search` | 매뉴얼 RAG 검색 | `ManualSearchResponse` |
| `GET` | `/api/equipment/inspection/checklist/{equipment_type}` | 점검 체크리스트 (일상/정기/특별) | `InspectionChecklistResponse` |

### 5-1. 응답 예시 — `/api/equipment/spc/EWP-LINE-A`

```json
{
  "process_id": "EWP-LINE-A",
  "process_name": "EWP 하우징 라인 A",
  "data": {
    "x_axis": ["2026-05-01 09:00", "..."],
    "y_values": [10.05, 10.12, ...],
    "ucl": 10.45,
    "cl":  10.00,
    "lcl":  9.55
  },
  "violations": [
    {
      "rule": 1,
      "rule_name": "한 점이 ±3σ 초과",
      "indices": [42],
      "severity": "CRITICAL",
      "cause": "측정 시스템 오류 또는 공정 급변동",
      "action": "측정 재검 + 공정 정지 + 원인 조사",
      "annotation": {"x": 42, "text": "R1 위반"}
    }
  ],
  "cpk": 1.12,
  "cp": 1.18,
  "process_health": "warning"
}
```

---

## 6. 데이터베이스 스키마

기능 F 는 **여러 SQLite DB** 를 사용 (각 도메인별 분리).

### 6-1. error_codes 테이블 (`error_code_db.py`)

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `id` | INTEGER PK | 고유 ID |
| `equipment_type` | TEXT (필수) | 장비 종류 (`프레스`, `용접`, `CNC`, `금형`, `로봇`, `컨베이어`, `검사`) |
| `equipment_model` | TEXT | 모델명 |
| `error_code` | TEXT (필수) | 에러 코드 (예: `E102`) |
| `error_name` | TEXT (필수) | 에러명 |
| `severity` | TEXT | `info` / `warning` / `critical` |
| `cause` | TEXT (필수) | 원인 |
| `action` | TEXT (필수) | 조치 |
| `prevention` | TEXT | 예방책 |
| `reference_page` | TEXT | 매뉴얼 페이지 참조 |
| `language` | TEXT | `ko` / `en` |

### 6-2. error_history 테이블 (`error_history_db.py`) — 685건 시드

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `id` | INTEGER PK | 이력 ID |
| `error_code` | TEXT (필수) | 에러 코드 (FK 의도) |
| `equipment_type` | TEXT (필수) | 장비 종류 |
| `equipment_id` | TEXT | 개별 장비 ID |
| `occurred_at` | TEXT (필수) | 발생 시각 |
| `resolved_at` | TEXT | 복구 시각 |
| `resolution_minutes` | INTEGER | 복구 소요 시간 (분) |
| `root_cause` | TEXT | 근본 원인 (사후 분석) |
| `action_taken` | TEXT | 취한 조치 |
| `operator_name` | TEXT | 작업자 |
| `shift` | TEXT | `주간` / `야간` / `심야` |
| `plant` | TEXT | 사업장 (default `경산본사`) |

### 6-3. inspection_db — 점검 체크리스트 + 이력

#### checklist_templates 테이블

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `id` | INTEGER PK | 템플릿 ID |
| `template_name` | TEXT (필수) | 템플릿명 |
| `equipment_type` | TEXT (필수) | 장비 종류 |
| `checklist_type` | TEXT (default `daily`) | `daily` / `regular` / `special` |
| `items_json` | TEXT (필수) | 체크 항목 (JSON 배열) |

#### inspection_logs 테이블

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `id` | INTEGER PK | 이력 ID |
| `equipment_id` | TEXT (필수) | 장비 ID |
| `equipment_name` | TEXT | 장비명 |
| `template_id` | INTEGER FK | 템플릿 |
| `inspector` | TEXT | 점검자 |
| `inspection_date` | TEXT | 점검일 |
| `results_json` | TEXT | 결과 (JSON) |
| `overall_status` | TEXT | `PASS` / `WARN` / `FAIL` |
| `note` | TEXT | 비고 |

### 6-4. 기타 DB·파일

| 위치 | 내용 |
|---|---|
| `data/mold_ml/` | 금형 ML 모델 (joblib pickle) |
| `data/spc_ml/` | SPC ML 모델 |
| `data/spc_samples/` | SPC 샘플 CSV |
| `data/markov_ml/` | Markov 학습 결과 |
| `data/intent_ml/` | 의도 분류 ML |
| `data/regulation_ml/` | (Feature D 와 공유) |

### 6-5. ER 다이어그램

```
┌─────────────────────────┐
│  error_codes            │ 마스터 (7 장비 × 40 증상)
│  ──────────────────     │
│  id PK                  │
│  equipment_type, code   │
│  cause, action, severity│
└──────────┬──────────────┘
           │ 1:N (error_code 매칭)
           ▼
┌─────────────────────────┐
│  error_history          │ 685건 시드 + 운영 누적
│  ──────────────────     │
│  id PK, error_code (FK) │
│  equipment_id, plant    │
│  occurred_at, resolved  │
│  resolution_minutes     │
│  operator, shift        │
└─────────────────────────┘

┌─────────────────────────┐         ┌──────────────────────┐
│  checklist_templates    │ 1:N     │  inspection_logs     │
│  ──────────────────     │────────▶│  ────────────────    │
│  id PK                  │         │  id PK               │
│  equipment_type         │         │  equipment_id        │
│  checklist_type         │         │  template_id (FK)    │
│  items_json             │         │  results_json        │
│  (daily/regular/special)│         │  overall_status      │
└─────────────────────────┘         └──────────────────────┘
```

---

## 7. SPC + Nelson 8 규칙 (가장 핵심)

기능 F 의 가장 중요한 부분. SPC 관리도에서 통계적 이상을 감지하는 8가지 규칙.

### 7-1. SPC 란?

_Statistical Process Control (통계적 공정 관리)_ — 공정의 측정값이 정규분포를 따른다는 가정 하에, 평균 (CL) 과 ±3σ (UCL/LCL) 한계로 이상을 감지.

```
        UCL ─── (Upper Control Limit, +3σ)
            │
            │   ┌─ 측정값
        CL  ─ (Center Line, 평균)
            │
            │
        LCL ─── (Lower Control Limit, -3σ)
```

이상 신호 (out-of-control) 가 있으면 **공정에 문제 있음** 을 의미.

### 7-2. Nelson 8 Rules (`spc_realtime.py:NELSON_RULE_GUIDE`)

각 규칙별 원인·조치·심각도·차트 주석이 사전 정의됨.

| 규칙 | 패턴 | 의미 | 심각도 |
|---|---|---|---|
| **R1** | 한 점이 ±3σ 초과 | 명백한 이상 (특이 원인) | **CRITICAL** |
| **R2** | 9 연속 점이 같은 쪽 (CL 위 또는 아래) | 평균 이동 (mean shift) | HIGH |
| **R3** | 6 연속 점이 일정 방향 (증가 또는 감소) | 추세 (trend) | HIGH |
| **R4** | 14 연속 점이 교대로 진동 (위·아래 교번) | 측정 시스템 또는 작업자 교대 | MEDIUM |
| **R5** | 3 점 중 2 점이 ±2σ 초과 | 분산 증가 | HIGH |
| **R6** | 5 점 중 4 점이 ±1σ 초과 | 분산 증가 (덜 명확) | MEDIUM |
| **R7** | 15 연속 점이 ±1σ 안 (너무 좁음) | **층화** (다른 공정 혼재) | MEDIUM |
| **R8** | 8 연속 점 모두 ±1σ 밖 | 양극화 (이중 분포) | HIGH |

### 7-3. 차트 주석 자동 생성

`spc_realtime.enrich_violations()` 가 위반 발견 시:
- Plotly `add_vrect()` — 위반 구간 음영 표시
- `add_annotation()` — 텍스트 풍선 ("R1 위반: 측정 재검 필요")
- 색상 매핑 — CRITICAL=빨강 / HIGH=주황 / MEDIUM=노랑

### 7-4. 5 공정 데모 데이터

`spc_data_generator.py` 가 정규분포 시뮬레이션 + Nelson 패턴 주입:

| 공정 | 주입된 패턴 | 의도 |
|---|---|---|
| EWP 하우징 | R2 + R3 | 평균 이동 + 추세 동시 |
| CCH (쿨링채널 하우징) | R1 | 명백한 이상점 |
| 범퍼 | R5 | 2점 ±2σ 초과 |
| 시트레일 | R3 | 단순 추세 |
| (5번째 — 백업) | (정상) | 비교용 |

---

## 8. ⓐ 에러 검색 영역 (5 모듈)

자연어 또는 코드 입력 → 매뉴얼·이력·인과 통합 응답.

### 8-1. 모듈

| 파일 | 역할 |
|---|---|
| `error_code_db.py` | 에러 코드 마스터 (7 장비 × 40 증상) |
| `error_history_db.py` | 685건 시드 + 운영 누적 |
| `error_causality.py` | 인과 관계 그래프 (이 에러 → 다음 가능성) |
| `ml_error_search.py` | ML 의미 매칭 (동의어 79개) |
| `manual_rag.py` | 매뉴얼 RAG (ChromaDB) |

### 8-2. 동의어 사전 (79개)

`EQUIPMENT_SYMPTOM_SYNONYMS` — 7 장비 × 40 카테고리. 예시:
- "프레스가 안 돼요" → 프레스 정지 카테고리 → E102, E103, E105 후보
- "용접 불량" → 용접 너겟 결함 → W201, W203
- "CNC 멈춤" → CNC 시스템 오류 → C301, C302

### 8-3. 검색 응답 예시

`POST /equipment/error/search` 입력 `{"query": "프레스가 멈춰요"}`:
```json
{
  "results": [
    {
      "error_code": "E102",
      "error_name": "프레스 끼임 감지",
      "severity": "critical",
      "cause": "센서 오작동 또는 부품 비정상 위치",
      "action": "전원 차단 → 부품 위치 확인 → 센서 점검",
      "history_count_3m": 5,
      "avg_resolution_minutes": 23,
      "trend": "decreasing",
      "primary_cause": "센서 오류 (60%)"
    }
  ],
  "manual_excerpts": [
    {"page": 42, "snippet": "...프레스 끼임 시 절대 손을..."}
  ],
  "causality": {
    "next_likely": ["E103 안전문 열림", "E101 비상정지"],
    "probabilities": [0.45, 0.32]
  }
}
```

---

## 9. ⓑ Markov 연쇄 예측 (`markov_predictor.py`)

다음 고장이 무엇일지 확률 분포로 예측.

### 9-1. 동작

`error_history` 의 시간 순서 데이터로 **전이 행렬** 학습:
```
P(다음 에러 = E105 | 현재 에러 = E102) = 0.34
P(다음 에러 = E108 | 현재 에러 = E102) = 0.21
P(다음 에러 = (정상) | 현재 에러 = E102) = 0.45
```

### 9-2. cascade chain

`/equipment/markov/{error_code}` 응답에 **N 단계 cascade** 포함:
```
E102 (프레스 끼임)
   ↓ 0.34
E105 (안전문 자동 차단)
   ↓ 0.42
E108 (라인 정지)
   ↓ 0.55
(정상 복귀)
```

→ 운영자가 "E102 발생 시 다음 5분 내 E105·E108 가능성 높음" 인지 후 선제 대응.

---

## 10. ⓒ 금형 lifecycle ML (`mold_lifecycle.py` + `mold_ml_predictor.py`)

금형 (mold) 의 균열·마모 시점을 ML 예측.

### 10-1. 학습 데이터

- 사용 횟수 (shot count)
- 누적 사용 시간
- 정비 횟수
- 검사 결과 (균열·마모도 측정값)

### 10-2. 예측 응답

`/equipment/molds`:
```json
{
  "molds": [
    {
      "mold_id": "MOLD-EWP-001",
      "name": "EWP 하우징 금형 #1",
      "shot_count": 45000,
      "expected_lifespan": 80000,
      "remaining_pct": 43.75,
      "predicted_failure": {
        "type": "crack",
        "probability": 0.78,
        "estimated_at": "2026-06-01"
      },
      "recommended_action": "정밀 검사 + 균열 부위 보강"
    }
  ]
}
```

---

## 11. ⓓ MTBF + 예측 정비 (`maintenance_predictor.py`)

### 11-1. MTBF (Mean Time Between Failures)

평균 고장 간격. `error_history` 의 `occurred_at` 차이 평균.

`/equipment/mtbf`:
```json
{
  "by_equipment": [
    {"equipment_type": "프레스", "mtbf_hours": 320, "fail_count": 12},
    {"equipment_type": "용접 로봇", "mtbf_hours": 180, "fail_count": 8}
  ],
  "top_cost": [
    {"error_code": "E102", "total_downtime_hours": 45, "estimated_cost_krw": 12500000}
  ]
}
```

### 11-2. 예측 정비 (v3.3)

수리 이력 기반으로 다음 정비 일정 추천. 정비를 너무 일찍 하면 비용 낭비, 너무 늦으면 고장. **최적 시점** 자동 계산.

---

## 12. ⓔ 7종 ML/검색 엔진 + 매뉴얼 RAG

### 12-1. 7종 엔진 상태

`/equipment/ml-engines/status`:

| 엔진 | 모듈 | 상태 |
|---|---|---|
| **TF-IDF 에러 검색** | `ml_error_search` | 에러코드 DB + TF-IDF 캐시 기반 검색 |
| **Isolation Forest SPC** | `spc_ml_predictor` | SPC CSV 기반 이상 탐지 |
| **XGBoost 금형 수명** | `mold_ml_predictor` | XGBoost 또는 sklearn fallback 회귀 예측 |
| **Markov 연쇄** | `markov_predictor` | 이벤트 시퀀스/모델 기반 다음 고장 예측 |
| **MTBF 예측** | `maintenance_predictor` | 수리 이력 기반 평균 고장 간격/정비 시점 계산 |
| **에러 인과 규칙** | `error_causality` | 규칙 기반 원인/조치 및 Markov 시퀀스 보강 |
| **매뉴얼 RAG** | `manual_rag` | ChromaDB 검색, 경량 배포에서는 로컬 텍스트 검색 fallback |

`accuracy`는 검증된 평가 산출물이 있을 때만 채운다. 임의의 정적 정확도 숫자는 운영 상태로 표시하지 않는다.

### 12-2. 매뉴얼 RAG (`manual_rag.py`)

장비 매뉴얼 (PDF) 을 ChromaDB 인덱싱. 자연어 질문 → 관련 페이지 + 발췌 반환.

`/equipment/manual/search`:
```json
{
  "results": [
    {
      "manual": "프레스 600톤 운영 매뉴얼",
      "page": 42,
      "snippet": "...끼임 발생 시 절차...",
      "relevance": 0.91
    }
  ]
}
```

---

## 13. 프론트엔드 컴포넌트 트리

`/equipment` 페이지의 **8 탭** 구조 (실은 4 메인 탭 × 일부 sub-탭).

### 13-1. 탭 구조

```
/equipment 라우트 (frontend/src/routes/equipment.tsx)
│
└─ <Equipment>
   │
   ├─ 메인 탭 ① "개요" (5 sub)
   │  ├─ 설비개요    — 5 공정 신호등 + 7 장비 카드
   │  ├─ 긴급조치    — 최근 위반 + 즉시 조치 가이드
   │  ├─ 장비유형별   — 7 장비 × MTBF 매트릭스
   │  ├─ 예측정비    — maintenance_predictor 추천
   │  └─ ML엔진     — 5 ML 엔진 상태 카드
   │
   ├─ 메인 탭 ② "SPC 분석"
   │  ├─ <ProcessTrafficLights> — 5 공정
   │  ├─ <NelsonChart>          — Plotly 관리도
   │  ├─ <CpkSummary>           — Cp/Cpk 통합
   │  └─ <CsvUpload>            — SPC 데이터 업로드
   │
   ├─ 메인 탭 ③ "에러 검색"
   │  ├─ <SymptomSelector>      — 2단계 (장비→증상)
   │  ├─ <SearchInput>          — 자연어 입력
   │  ├─ <ErrorResultCard>      — 이력+Markov+매뉴얼 통합
   │  └─ <FeedbackButton>       — 👍/👎
   │
   └─ 메인 탭 ④ "매뉴얼 AI" (3 sub)
      ├─ 에러코드 조회   — error_codes 직접
      ├─ 증상별 검색 가이드  — 79 동의어 사전
      └─ 매뉴얼 AI 질의   — manual_rag RAG
```

### 13-2. 차트 컴포넌트

| 컴포넌트 | Plotly 사양 |
|---|---|
| `<NelsonChart>` | line + scatter + add_vrect (위반 음영) + add_annotation (R 번호 풍선) |
| `<MTBFBarChart>` | bar + sort by mtbf_hours desc |
| `<MarkovGraph>` | sankey 또는 directed graph |
| `<MoldLifeCard>` | progress bar + estimated_at 텍스트 |

---

## 14. 18 모듈 가이드 — 6 카테고리

### 14-1. SPC 영역 (6 모듈)

| 파일 | 역할 |
|---|---|
| `spc_analyzer.py` | 통계 분석 (평균·표준편차·Cp/Cpk) |
| `spc_realtime.py` | **Nelson 8 규칙 + NELSON_RULE_GUIDE + enrich_violations** |
| `spc_dashboard.py` | 5 공정 신호등 (`get_all_process_health()`) |
| `spc_ml_predictor.py` | SPC ML 예측 |
| `spc_data_generator.py` | 정규분포 + Nelson 패턴 주입 (5 공정 합성) |
| `spc_report_generator.py` | SPC 보고서 PDF 생성 |

### 14-2. 에러 영역 (5 모듈)

| 파일 | 역할 |
|---|---|
| `error_code_db.py` | 마스터 (7 장비 × 40 증상) |
| `error_history_db.py` | 이력 685건 시드 |
| `error_causality.py` | 인과 그래프 |
| `ml_error_search.py` | 의미 매칭 (동의어 79) |
| `markov_predictor.py` | Markov 연쇄 |

### 14-3. 금형 영역 (2 모듈)

| 파일 | 역할 |
|---|---|
| `mold_lifecycle.py` | 금형 lifecycle 데이터 |
| `mold_ml_predictor.py` | 균열·마모 시점 예측 |

### 14-4. 정비·점검 (2 모듈)

| 파일 | 역할 |
|---|---|
| `maintenance_predictor.py` | v3.3 — 예측 정비 엔진 |
| `inspection_db.py` | 일상/정기/특별 점검 체크리스트 + 이력 |

### 14-5. 검색·매뉴얼 (2 모듈)

| 파일 | 역할 |
|---|---|
| `drawing_search.py` | 도면 / BOM 검색 |
| `manual_rag.py` | 매뉴얼 RAG (ChromaDB) |

### 14-6. 통합 (1 모듈)

| 파일 | 역할 |
|---|---|
| `dashboard_data.py` | 5 공정 + 7 장비 + 5 ML 엔진 통합 응답 빌더 |

---

## 15. 챗봇 연동 (Feature C 와 통합)

Feature F 는 `equipment_*` 데이터를 챗봇에 직접 노출. 사용자가 "EWP 라인 SPC 어때?" 라고 물으면:

```
[챗봇]
  사용자 질문
        │
        ▼
[Feature C action_handlers]
  work_actions.match_action() → "spc_status"
        │
        ▼
[Feature C → Feature F bridge]
  내부 함수 호출 (또는 GET /equipment/spc/EWP-LINE-A)
        │
        ▼
  응답 카드 — 5 공정 신호등 + 위반 + 추세
        │
        ▼
[챗봇 응답]
  ActionCard 형태로 화면에 카드 렌더링
```

---

## 16. 운영·확장 노트

### 16-1. ENABLE_FEATURE_F 플래그

```
ENABLE_FEATURE_F=true
```
이면 `/api/equipment/...` 활성. ML 엔진들은 lazy-load (첫 요청 시 모델 pickle 로드).

### 16-2. 데이터 시드

```bash
# 시드 데이터 생성 (개발용)
docker compose exec backend python3 -c "
from features.equipment.error_history_db import seed_error_history
seed_error_history(685)  # 685건 합성
"

# SPC 5 공정 합성
docker compose exec backend python3 -c "
from features.equipment.spc_data_generator import generate_all_processes
generate_all_processes(samples_per_process=200)
"
```

### 16-3. ML 엔진 재학습

```bash
# 금형 lifecycle ML
docker compose exec backend python3 -m features.equipment.mold_ml_predictor --retrain

# Markov
docker compose exec backend python3 -m features.equipment.markov_predictor --retrain
```

### 16-4. 성능 — 응답 시간 목표

| 작업 | 목표 | 현재 |
|---|---|---|
| `/dashboard/overview` | < 500ms | ~200-400ms |
| `/spc/{process}` (200 데이터점) | < 300ms | ~100-200ms |
| `/error/search` (자연어) | < 500ms | ~200-400ms |
| `/markov/{code}` | < 200ms | ~50-100ms |
| `/molds` (50 금형) | < 300ms | ~150ms |
| `/manual/search` (RAG) | < 1s | ~500-800ms |

### 16-5. 향후 확장

- [x] **실시간 PLC/SCADA ingest** — Redis Stream 기반 ingest 파이프라인 + backend `live_alarms` 저장/API 구현 완료. 실 OPC-UA → Redis bridge는 별도 커넥터 작업
- [x] **Vision OCR 파일럿** — `drawing_search.extract_part_numbers()` + `POST /drawing/{id}/ocr` 구현 완료 (v4.8). Gemini 2.5 Pro 기반, GEMINI_API_KEY 발급 후 즉시 활성
- [ ] **Vision 검사** — 카메라 이미지 → 결함 탐지 (YOLO 등)
- [ ] **에너지 모니터링** — 전력 소비 추세 분석
- [ ] **3D 도면** — `drawing_search` 에 STEP/IGES 3D 뷰어 통합
- [ ] **AR 매뉴얼** — 모바일 카메라 + AR 가이드

---

## 17. 자주 묻는 질문 (FAQ)

**Q1. SPC 데이터를 어떻게 입력하나요?**
> 두 방법:
> 1. CSV 업로드 (`/spc/upload-csv`) — 형식: `timestamp, process_id, value`
> 2. PLC/SCADA 연동 — Redis Stream ingest 와 `/api/equipment/plc/status` 는 구현되어 있습니다. 실제 현장 PLC 연결은 OPC-UA → Redis bridge 어댑터를 붙이는 운영/커넥터 작업입니다.

**Q2. Nelson 8 규칙이 너무 자주 위반돼요.**
> 정상 공정에서도 R4 / R7 같은 패턴은 작은 노이즈에서도 발생 가능. `spc_realtime.py` 의 시그니처 길이 (예: R3=6점) 를 도메인에 맞춰 조정 가능. 또는 심각도 임계 (CRITICAL/HIGH 만 알림) 를 변경.

**Q3. 685건 시드 데이터로 학습한 ML 엔진이 정확한가요?**
> 시드는 데모용. 실 운영 데이터 (수천~만건) 누적 후 재학습 필요. `mold_ml_predictor` 등은 자체 정확도 메트릭 (`/ml-engines/status`) 으로 추적.

**Q4. 매뉴얼 RAG 가 답을 못 찾아요.**
> 매뉴얼이 ChromaDB 에 인덱싱돼 있어야 함. 기본 시드만으로는 부족 — 운영자가 PDF 업로드 + `manual_rag.index()` 호출 필요.

**Q5. Markov 연쇄 예측이 비현실적이에요.**
> 685건 시드는 통계적 의미 한계. 운영 누적 후 정확도 향상. 또는 도메인 전문가가 cascade 룰을 수동 정의 (`error_causality.py` 의 graph 직접 편집).

**Q6. 챗봇에서 "EWP SPC" 물었는데 답이 비어있어요.**
> Feature F endpoint (`/equipment/spc/EWP-LINE-A`) 가 정상 작동하는지 확인. ENABLE_FEATURE_F=false 면 챗봇이 spc_status 액션 처리 못함.

**Q7. 점검 체크리스트는 어떻게 추가하나요?**
> `inspection_db.py:checklist_templates` 에 새 템플릿을 추가합니다. 현장 제출은 `/equipment/field`의 빠른 점검 제출 패널과 `/api/equipment/inspection/submit` 경로를 사용하며, 템플릿 관리 UI는 별도 운영 백로그입니다.

**Q8. 5 ML 엔진 중 일부가 "미학습" 으로 표시돼요.**
> 첫 부팅 시 모델 pickle 이 없으면 표시. `--retrain` 옵션으로 학습 후 재기동.

---

## 18. 용어집

| 용어 | 풀이 |
|---|---|
| **SPC** | Statistical Process Control — 통계적 공정 관리 |
| **Cp / Cpk** | 공정 능력 지수 — 공정 산포 vs 규격 한계 비율 |
| **UCL / CL / LCL** | Upper / Center / Lower Control Limit (관리 한계 ±3σ) |
| **σ (시그마)** | 표준편차 — 데이터 산포 척도 |
| **Nelson Rules** | SPC 관리도 8 가지 이상 패턴 규칙 |
| **MTBF** | Mean Time Between Failures — 평균 고장 간격 |
| **Markov 연쇄** | 다음 상태가 현재 상태에만 의존하는 확률 모델 |
| **cascade** | 한 고장이 다음 고장을 연쇄적으로 유발 |
| **Lifecycle** | 금형의 사용 → 마모 → 폐기 까지 전체 수명 주기 |
| **Shot count** | 금형이 찍어낸 부품 수 (프레스 1회 = 1 shot) |
| **PLC** | Programmable Logic Controller — 공장 자동제어 장치 |
| **SCADA** | Supervisory Control and Data Acquisition — 생산 모니터링 |
| **OPC UA** | 산업용 통신 표준 (PLC ↔ IT 시스템) |
| **RAG** | Retrieval-Augmented Generation — 검색 + LLM 답변 |
| **ChromaDB** | 벡터 DB |
| **bge-m3** | 한국어·다국어 임베딩 모델 |
| **층화 (Stratification)** | 다른 공정·작업자 데이터가 섞임 (R7 원인) |
| **양극화** | 데이터가 두 개 분포로 나뉨 (R8 원인) |
| **mean shift** | 공정 평균이 갑자기 이동 (R2 원인) |
| **trend** | 일정 방향으로 증가·감소 (R3 원인) |
| **shift (작업)** | 주간/야간/심야 근무 교대 |

---

## 19. 변경 이력 (Feature F 한정)

| 버전 | 날짜 | 주요 변경 |
|---|---|---|
| v3.0 | 2026-? | 기본 설비 AI 도우미 |
| v3.3 | 2026-? | 예측 정비 엔진 (`maintenance_predictor`) 도입 |
| v3.4 | 2026-04 | **대대적 확장** — SPC 분석 탭 (4탭) + Nelson 8 규칙 가이드 + 동의어 79 + 에러 이력 685건 + 카드 UI + Markov inline + 매뉴얼 AI 3 sub + 챗봇 연동 (`spc_status` 액션) + 피드백 |
| v3.5 | 2026-04 | SPC 데이터 관리 — CSV 업로드 + 5 공정 일괄 재생성 |

---

## 20. 한눈 요약 카드

```
┌──────────────────────────────────────────────────────────────┐
│  기능 F — 설비·공정 AI / SPC                                │
├──────────────────────────────────────────────────────────────┤
│  🏭 공장 설비의 모든 이상을 실시간 감지·예측                  │
│                                                              │
│  💻 Backend     FastAPI + NumPy/SciPy + scikit-learn         │
│                  + ChromaDB (manual RAG) + Plotly             │
│  🖥  Frontend    React + Vite + TS + Plotly.js                │
│                  4 메인 탭 + 8 sub 탭                        │
│  🔐 보안         JWT + RBAC (생산·품질·자동화·금형)          │
│                                                              │
│  🌐 Endpoint    OpenAPI 기준 — docs/API.md 자동 산정        │
│                  overview/spc/error/markov/inspection 등    │
│  📊 다중 SQLite  error_codes / error_history (685) /         │
│                  inspection_logs / mold_lifecycle 등         │
│                                                              │
│  📁 18 Module — 6 카테고리                                   │
│   • SPC (6)      analyzer/realtime/dashboard/ml/generator/  │
│                  report_generator                            │
│   • 에러 (5)     code_db/history_db/causality/ml_search/    │
│                  markov                                      │
│   • 금형 (2)     lifecycle/ml_predictor                      │
│   • 정비·점검 (2) maintenance_predictor/inspection_db       │
│   • 검색·매뉴얼 (2) drawing_search/manual_rag               │
│   • 통합 (1)     dashboard_data                              │
│                                                              │
│  📐 Nelson 8 규칙 — R1~R8                                    │
│     원인·조치·심각도·차트 주석 사전 정의                     │
│     5 공정 합성 데이터에 R1/R2/R3/R5 패턴 주입               │
│                                                              │
│  🤖 5 ML 엔진    mold lifecycle / SPC 예측 / Markov /        │
│                  예측 정비 / 에러 의미 매칭 (동의어 79)      │
│                                                              │
│  🔗 챗봇 연동    Feature C `spc_status` action → 자동 카드  │
└──────────────────────────────────────────────────────────────┘
```

---

문서 작성: 2026-05-10 | 본 문서는 향후 feature 변경 시 함께 갱신해주세요.
