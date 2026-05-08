# AJIN AI ASSISTANT — 기능 설명서 (Feature Specification)

> **버전**: v3.5
> **작성일**: 2026-04-26
> **대상**: 제3회 KNU SILLI 경진대회 본선 진출 — 6대 핵심 기능 상세 사양
> **목적**: 각 기능의 비즈니스 가치 · 사용자 흐름 · 기술 구현 · 데이터 · API 엔드포인트를 React 마이그레이션 / 본선 데모 / 운영 문서로 활용 가능한 수준으로 기술

---

## 목차

- [전체 개요](#전체-개요)
- [기능 A: 인원 검색 및 조직도](#기능-a-인원-검색-및-조직도)
- [기능 B: 문서 검색 및 작성](#기능-b-문서-검색-및-작성)
- [기능 C: AI 업무 도우미](#기능-c-ai-업무-도우미)
- [기능 D: 법규/규정 모니터링](#기능-d-법규규정-모니터링)
- [기능 E: 인사 관리](#기능-e-인사-관리)
- [기능 F: 설비/공정 AI 어시스턴트](#기능-f-설비공정-ai-어시스턴트)
- [공통 기반 기능](#공통-기반-기능)
- [기능 간 교차 네비게이션 (Feature Bridge)](#기능-간-교차-네비게이션-feature-bridge)

---

## 전체 개요

### 1. 6대 기능 매트릭스

| 기능 | 영문 라벨 | RBAC | 부서 제약 | 핵심 사용자 | 구현도 |
|:--:|---|:--:|---|---|:--:|
| **A** | 인원 검색 / 조직도 | L1+ (전 직원) | 없음 | 모든 임직원 | **95%** |
| **B** | 문서 검색·작성 | L1+ | 없음 | 품질·생산기술·구매 | **85%** |
| **C** | AI 업무 도우미 | L1+ | 없음 | 신입·전 직원 | **90%** |
| **D** | 법규/규정 모니터링 | L2+ | 7개 부서 | 품질보증·환경안전·법무·구매·해외영업 | **85%** |
| **E** | 인사 관리 | L3+ (TEAM_LEAD~) | Admin 부서 | 인사·시스템 관리자 | **78%** |
| **F** | 설비/공정 AI | L1+ | 14개 부서 | 생산기술·품질·정비·금형 | **92%** |

### 2. SILLI 경진대회 5대 평가축 대응

| 평가축 | 주력 기능 | 데모 시나리오 |
|---|---|---|
| **업무 효율화** | A + B | "이재용 부장 찾아줘" 0.3초 → "8D Report 작성해줘" 자동 초안 |
| **안전성 향상** | D + F | "안전거리 300→400mm 변경" 시뮬레이션 + Nelson Rule 위반 감지 |
| **품질 개선** | B + F | 문서 품질 5기준 100점 평가 + Cpk 1.38→1.24 하락 예측 |
| **생산성 향상** | C | SOP 가이드 → 퀴즈 → 오답 재학습 완전 루프 |
| **투자비 절감** | D + E | 외부 컨설팅 1,000만 원 대체 + RBAC 자동화 |

### 3. 핵심 ML/DL 모델 (7종)

| # | 모델 | 알고리즘 | 페이지 | 응답 시간 |
|:--:|---|---|:--:|:--:|
| 1 | Intent Classifier | TF-IDF + LogisticRegression | A, C | **5ms** |
| 2 | Error Code Search | TF-IDF + Cosine Similarity | F | <50ms |
| 3 | SPC Anomaly | Isolation Forest | F | <100ms |
| 4 | Mold Lifecycle | XGBoost (10 features) | F | <50ms |
| 5 | Markov Failure | Markov Chain (25 카테고리) | F | <30ms |
| 6 | Doc Quality | Rule-based (5기준 100점) | B | <20ms |
| 7 | Reg Risk | TF-IDF + RandomForest | D | <50ms |

---

# 기능 A: 인원 검색 및 조직도

> **영문 라벨**: `EMPLOYEE SEARCH & ORG CHART`
> **페이지 파일**: [ui/page_search.py](../../ui/page_search.py) (690줄)
> **백엔드**: [backend/routers/employee.py](../../backend/routers/employee.py)
> **기능 모듈**: [features/search/](../../features/search/)
> **SILLI 부합성**: 업무 효율화

## A-1. 비즈니스 가치

### 문제 정의
- 아진산업 임직원 **649명**, 국내 12개소 + 해외 7개소 분산
- "이 업무 담당자가 누구지?"는 사내에서 가장 빈번한 질의
- 기존: 부서명/이름을 정확히 알아야 검색 가능 → 신입·타부서·약어 미지자에게 진입장벽

### 솔루션
- **시맨틱 하이브리드 검색**: 부서 약어/별칭/오타에도 적응
- **0.3초 응답**: ML 의도 분류로 LLM 호출 90% 감소
- **부서별 가시성 자동 적용**: RBAC 기반 정보 노출 통제

## A-2. 핵심 기능 목록

### A-2-1. 시맨틱 하이브리드 검색 (v3.1 신규)
| 항목 | 사양 |
|---|---|
| **알고리즘** | FTS5 (BM25 키워드) + ChromaDB (BGE-M3 시맨틱) → RRF (Reciprocal Rank Fusion) 통합 |
| **인덱싱 대상** | 사원 329명 — 이름·부서·직급·이메일·사업장·세부 업무 |
| **검색 정확도** | 부서 약어 48종 매칭 (예: "QA" → "품질보증팀") |
| **임베딩 모델** | BGE-M3 (다국어 지원, 1024차원) |
| **벡터 DB** | ChromaDB `employee_profiles` 컬렉션 |
| **응답 시간** | 평균 200~300ms (서버사이드 캐싱 시 50ms 미만) |

### A-2-2. ML 의도 분류 (v3.1 신규)
- **모델**: TF-IDF (1,500건 학습) + LogisticRegression
- **목적**: 사용자 질의가 "인원 검색" / "문서 검색" / "에러코드" / "법규" 등 어떤 의도인지 분류
- **응답**: **5ms** (LLM 호출 불필요)
- **신뢰도 임계치**: 70%+ 시 즉시 반환, 미만 시 LLM 폴백
- **위치**: [features/search/ml_intent_classifier.py](../../features/search/ml_intent_classifier.py), [features/search/intent_router.py](../../features/search/intent_router.py)

### A-2-3. 검색 이력 + 5종 정렬 (v3.1 신규)
- **이력**: 세션 기반 최근 20건 저장 (검색어 + 결과 수 + 타임스탬프)
- **바로가기**: 최근 5건을 칩(chip) 형태로 표시 → 클릭 시 재실행
- **정렬 옵션**: 관련도순 / 이름순 / 부서순 / 직급순 / 사업장순
- **위치**: [features/search/employee/search_history.py](../../features/search/employee/)

### A-2-4. FTS5 전문 검색 (v3.0)
- **토크나이저**: `unicode61` (한글 정규화)
- **인덱싱**: 329건 사원 데이터
- **고급 쿼리**: AND, OR, NOT, 구문 검색, 와일드카드 지원

### A-2-5. Text-to-SQL (v3.0)
- 자연어 → SQL 변환
- 예: "차장 이상 영업본부 사람" → `SELECT * FROM employees WHERE position_level >= 4 AND division = '영업본부'`

### A-2-6. 가시성 필터 (3-Tier)
| 레벨 | 조건 | 노출 정보 |
|:--:|---|---|
| **FULL** | 같은 부서 OR 같은 본부 | 모든 필드 (이메일·전화·내선·세부 업무) |
| **PARTIAL** | 타 부서 | 이메일 마스킹 (`***@***.com`), 전화번호 숨김 |
| **HIDDEN** | INACTIVE 계정 | 검색 결과에서 제외 |

구현: [core/auth/visibility.py](../../core/auth/visibility.py) — `determine_visibility(user, target_dept, target_role)` + `filter_employee_fields()`

### A-2-7. HTML/CSS 카드형 조직도
- **전체 조직도**: 회사 전체 → 본부 → 부서 → 인원 트리
- **부서별 조직도**: 특정 부서 1개의 인원 카드 그리드
- **카드 정보**: 이니셜 아바타 + 이름 + 직급 + 내선 + 이메일 (가시성 적용)
- **렌더링**: 순수 HTML/CSS (Plotly 미사용 → 빠른 렌더링)
- **위치**: [features/search/employee/org_chart.py](../../features/search/employee/)

### A-2-8. 사업장 지도 (Folium)
- **데이터**: [data/facility_db/plants.json](../../data/facility_db/) v4.0 — 19개소 (국내 12 + 해외 7)
- **지도**: Folium + OpenStreetMap
- **마커 정보**: 사업장명 + 주소 + 인증 (IATF 16949 등) + 주요 공정
- **상호작용**: 마커 클릭 → 팝업 정보

### A-2-9. 교차 네비게이션 (Feature Bridge, v3.0)
검색 결과 카드에 **"이메일 작성"** / **"문서 작성"** 버튼 → 기능 B로 컨텍스트 이동.
- 예: 김민수 부장 카드 → "이메일 작성" 클릭 → 기능 B로 이동 + 수신자 자동 입력
- 위치: [core/feature_bridge.py](../../core/feature_bridge.py)

## A-3. 사용자 흐름 (User Flow)

```
[로그인] → [사이드바: 인원 검색 클릭]
    ↓
[검색 입력 바: "8D 보고서 담당자"]
    ↓
[ML 의도 분류 (5ms)] → "인원 검색" 의도 70% 신뢰도 ✓
    ↓
[하이브리드 검색]
  ├─ FTS5 키워드 검색 (BM25)
  └─ ChromaDB 시맨틱 검색 (BGE-M3)
    ↓
[RRF 통합 정렬]
    ↓
[가시성 필터 적용 (3-Tier)]
    ↓
[5종 정렬 옵션 + 결과 카드 렌더링]
    ↓
[카드 클릭] → 상세 정보 모달
[교차 네비] → 기능 B (이메일 작성) / 기능 B (문서 작성)
    ↓
[검색 이력 저장] (세션 기반 20건)
```

## A-4. 데이터 자산

| 항목 | 위치 | 규모 |
|---|---|---|
| 사원 DB (시뮬레이션) | [data/employees.db](../../data/) (SQLite) | **329명** (27부서) |
| 부서 별칭 | [features/search/employee/search.py](../../features/search/employee/) | **48종** |
| 부서 레지스트리 | [core/department_config.py](../../core/) | **30개 부서** |
| 사업장 DB | [data/facility_db/plants.json](../../data/facility_db/) | **19개소** |
| ChromaDB (employee_profiles) | [vectorstore/](../../vectorstore/) | 329건 임베딩 |
| ML 의도 학습 데이터 | [data/intent_ml/](../../data/) | **1,500건** |

> **주의**: 실제 649명 대비 시뮬레이션은 약 50%. 실제 도입 시 전체 데이터 시딩 필요.

## A-5. 백엔드 API

| Method | Endpoint | 인증 | 응답 |
|:--:|---|:--:|---|
| `POST` | `/api/employee/search` | **필수** | `{mode, results[], total, formatted_markdown}` |

**요청 예시**:
```json
{ "query": "QA 차장" }
```

**응답 예시**:
```json
{
  "mode": "semantic_hybrid",
  "results": [
    {
      "name": "김민수",
      "department": "품질보증팀",
      "division": "품질본부",
      "position": "차장",
      "email": "minsu.kim@ajin.com",      // 같은 부서 → FULL
      "phone": "010-1234-5678",
      "extension": "1234",
      "plant": "본사"
    },
    {
      "name": "이영희",
      "department": "구매팀",
      "position": "차장",
      "email": "***@***",                  // 타 부서 → PARTIAL
      "phone": "",
      "plant": "본사"
    }
  ],
  "total": 2,
  "formatted_markdown": "..."
}
```

## A-6. 화면 구성

```
┌──────────────────────────────────────────────────┐
│ 인원 검색 (EMPLOYEE SEARCH)                      │
├──────────────────────────────────────────────────┤
│ [🔍 검색: "QA 차장"_____________] [실행]          │
│                                                  │
│ 최근 검색: [구매팀 부장] [#abc123] [생산기술팀]  │
│                                                  │
│ 정렬: [관련도순 ▼]                                │
│ ─────────────────────────────────────────────    │
│ 검색 결과                              일치: 2건  │
│                                                  │
│ ┌──────────────┐  ┌──────────────┐               │
│ │ [KM]         │  │ [LY]         │               │
│ │ 김민수 차장  │  │ 이영희 차장  │               │
│ │ 품질보증팀   │  │ 구매팀       │               │
│ │ ✉ minsu.kim  │  │ ✉ ***@***   │               │
│ │ ☎ 1234       │  │ ☎ -          │               │
│ │ [이메일][문서]│  │ [이메일][문서]│              │
│ └──────────────┘  └──────────────┘               │
│                                                  │
│ ─────────────── 조직도 ──────────────             │
│ [전체 조직도 보기] [부서별: 품질보증팀 ▼]        │
│                                                  │
│ [HTML 카드 트리 렌더링]                          │
│                                                  │
│ ─────────────── 사업장 지도 ──────────────        │
│ [Folium 지도 — 19개소 마커]                       │
└──────────────────────────────────────────────────┘
```

---

# 기능 B: 문서 검색 및 작성

> **영문 라벨**: `DOCUMENT SEARCH & DRAFTING`
> **페이지 파일**: [ui/page_draft.py](../../ui/page_draft.py) (940줄) + [ui/doc_search_panel.py](../../ui/doc_search_panel.py) (608줄)
> **백엔드**: [backend/routers/draft.py](../../backend/routers/draft.py), [backend/routers/search.py](../../backend/routers/search.py)
> **기능 모듈**: [features/draft/](../../features/draft/) (23 파일)
> **SILLI 부합성**: 업무 효율화 + 품질 개선

## B-1. 비즈니스 가치

### 문제 정의
- 1차 협력사 아진산업은 **현대/기아/JOON INC** 등에 8D, ECN, PPAP, FMEA 등 OEM 제출 문서를 매월 다수 제출
- 신입은 양식을 찾고 작성법을 익히는 데 **하루 1~2시간** 소요
- OEM 반려율 = 납품 자격 위협
- 외부 양식 컨설팅 비용 발생

### 솔루션
- **Few-shot RAG**: 기존 아진 문서 584건을 학습 → 신규 문서를 "아진 스타일"로 자동 생성
- **품질 자동 평가**: 5기준 100점 채점 → 사전 반려 위험 감지
- **7개 포맷 다운로드**: DOCX/ODT/PDF/XLSX/CSV/TXT/복사 (v3.5)

## B-2. 핵심 기능 목록

### B-2-1. Few-shot RAG (v3.1 신규)
| 항목 | 사양 |
|---|---|
| **인덱싱 규모** | 기존 사내 문서 **584건** |
| **저장소** | ChromaDB `draft_fewshot_samples` 컬렉션 |
| **임베딩** | BGE-M3 (1024차원) |
| **검색 전략** | 사용자 요청 → 같은 doc_type 2~3건 retrieve → LLM 프롬프트에 few-shot 예시 주입 |
| **효과** | "아진 톤"으로 제목·서두·본문 패턴 일관성 확보 |
| **위치** | [features/draft/fewshot_rag.py](../../features/draft/) |

### B-2-2. 문서 유형 13종 (Doc Type Config)
| 카테고리 | 문서 유형 |
|---|---|
| **품질** | 8D Report, ECN, PPAP, FMEA, MSA, SPC Report |
| **이메일** | 사내 이메일, OEM 영문 이메일 |
| **회의록** | 회의록, 주간 보고 |
| **인사** | 휴가 신청서, 사직원 |
| **양식** | 견적서, 출장 보고서 |

위치: [features/draft/doc_type_config.py](../../features/draft/) (36KB, 약 1000줄 — 각 유형별 메타·필드·프롬프트·CC 규칙)

### B-2-3. 가중치 BM25 검색 (v3.0)
- **알고리즘**: BM25 + 필드별 가중치 (title 3.0 / doc_type 2.0 / part_name 2.0 / content 1.0)
- **필터**: 문서 유형 / 파트명 / 날짜 범위
- **위치**: [features/draft/search_engine.py](../../features/draft/), [features/search/searcher.py](../../features/search/) (HybridSearcher 통합)

### B-2-4. 문서 품질 자동 평가 (v3.1 신규)
| 평가 기준 | 점수 | 평가 방법 |
|---|:--:|---|
| **구조** | 25점 | 제목/수신/발신/본문/서명 섹션 존재 여부 |
| **분량** | 20점 | 문서유형별 적정 길이 (예: 8D는 800~1500자) |
| **전문성** | 25점 | 도메인 용어집 매칭 (품질·공정·OEM 약어) |
| **완성도** | 15점 | placeholder/누락 필드 검출 (`[수신자]`, `__날짜__`) |
| **톤** | 15점 | 어조 일관성 (공식 ↔ 친근) |
| **합계** | 100점 | + 개선 포인트 자동 생성 |

위치: [features/draft/doc_quality_scorer.py](../../features/draft/) (9KB, 약 250줄)

### B-2-5. 버전 비교 diff (v3.1 신규)
- **diff 알고리즘**: Python `difflib`
- **출력**: 유사도 비율 (%) + 추가/삭제/변경 줄 수 + HTML 하이라이트 (녹색 추가, 빨강 삭제, 노랑 변경)
- **저장**: SQLite `draft_versions.db` — 모든 버전 자동 저장
- **위치**: [features/draft/doc_diff.py](../../features/draft/), [features/draft/version_db.py](../../features/draft/)

### B-2-6. CC 자동 추천 (v3.1 신규)
- **규칙**: 문서유형별 필수/권장/선택 CC 10종
- **예시**:
  - 8D Report → **필수**: 품질보증팀, 생산기술팀 / **권장**: 품질본부장 / **선택**: 영업
  - PPAP → **필수**: OEM SQ팀, 영업 / **권장**: 품질보증팀
- **UI**: 3색상 카드 표시 (필수=빨강, 권장=주황, 선택=회색)
- **위치**: [features/draft/cc_recommender.py](../../features/draft/)

### B-2-7. 양식 카탈로그 11종
- **양식**: APQP, MSDS, 정기 보고서, 회의록, 8D 양식, ECN 양식 등
- **위치**: [features/draft/template_catalog.py](../../features/draft/) + [data/templates/](../../data/templates/)
- **렌더링**: Jinja2 템플릿 → 변수 대입 → DOCX/PDF/ODT 변환

### B-2-8. 7포맷 내보내기 (v3.5 확장)
| 포맷 | 라이브러리 | 용도 |
|---|---|---|
| **DOCX** | `python-docx` | MS Word 표준 |
| **ODT** | 자체 변환 | LibreOffice (HWPX 대체, v3.3) |
| **PDF** | `fpdf2` | 인쇄용 |
| **XLSX** | `openpyxl` | 표/매트릭스 데이터 (v3.5 신규) |
| **CSV** | `pandas` (utf-8-sig BOM) | Excel 호환 (v3.5 신규) |
| **TXT** | 기본 | 단순 텍스트 |
| **복사** | clipboard | 즉시 붙여넣기 |

위치: [features/draft/docx_exporter.py](../../features/draft/), [pdf_exporter.py](../../features/draft/), [tabular_exporter.py](../../features/draft/) (v3.5 신규)

### B-2-9. 마크다운 → CSV/XLSX 자동 변환 (v3.5 신규)
- **파싱 전략 3단계**:
  1. 마크다운 테이블(`|...|`) 파싱
  2. Key-Value 패턴 (`항목: 값`) 파싱
  3. 줄 단위 fallback
- **CSV**: UTF-8 BOM (`utf-8-sig`) — Excel에서 한글 정상 표시
- **XLSX**: 헤더 볼드, 열 폭 자동 조절, 시트명 금지문자 치환

### B-2-10. 3탭 UI (v3.0)
| 탭 | 용도 | 라이트 모드 색상 |
|---|---|---|
| **내부용 (INTERNAL)** | 사내 이메일, 회의록 — 친근한 존댓말 | 골드 |
| **외부용 (EXTERNAL)** | OEM 제출 문서, 외부 이메일 — 공식 격식체 | 골드 |
| **문서 이력** | 사용자 작성 이력 + 버전 diff + 재편집 | 골드 |

### B-2-11. Jinja2 매핑 수정 (v3.3)
- 8D / ECN / 회의록 등 변수 매핑 불일치 **12건** 해소
- HWPX → ODT 변환 (한컴오피스 의존성 제거)
- 발신자 파싱 오류 수정

## B-3. 사용자 흐름

```
[사이드바: 문서 작성 클릭]
    ↓
[탭 선택: 내부용 / 외부용 / 문서 이력]
    ↓
[자유 텍스트 입력: "현대차 SQ팀에 PPAP Level 3 제출 안내"]
[어조 선택: 공식적 ▼]    [문서 유형: PPAP ▼ (자동 분류 가능)]
    ↓
[Few-shot RAG: 기존 PPAP 3건 retrieve]
    ↓
[LLM 프롬프트 생성 (Ollama Qwen 3.5)]
    ↓
[SSE 스트리밍 응답 — 토큰 단위 실시간 출력]
    ↓
[문서 품질 평가 카드 (5기준 100점)]
[CC 자동 추천 카드 (필수/권장/선택)]
[버전 diff (이전 버전과 비교 시)]
    ↓
[7개 다운로드 버튼: DOCX | ODT | PDF | XLSX | CSV | TXT | 복사]
    ↓
[버전 자동 저장 (draft_versions.db)]
```

## B-4. 데이터 자산

| 항목 | 위치 | 규모 |
|---|---|---|
| 사내 문서 | [data/documents/](../../data/) | 8D, ECN, PPAP, 이메일, 회의록 다수 |
| Jinja2 템플릿 | [data/templates/](../../data/templates/) | 11종 (보고서·이메일·참고 양식) |
| Few-shot 인덱싱 | ChromaDB `draft_fewshot_samples` | **584건** |
| 문서 버전 DB | [data/draft_versions.db](../../data/) | 사용자 모든 버전 자동 저장 |
| 양식 참고 파일 | [data/templates/reference/](../../data/templates/) | 4종 (v2.6 추가) |

## B-5. 백엔드 API

| Method | Endpoint | 응답 |
|:--:|---|---|
| `POST` | `/api/draft/generate` | **SSE 스트리밍** — 토큰 단위 |
| `POST` | `/api/draft/generate-pipeline` | 전체 파이프라인 결과 (분류→생성→렌더링) |
| `POST` | `/api/draft/export` | 파일 바이트 (DOCX/PDF/TXT) |
| `GET` | `/api/draft/templates` | 사용 가능한 템플릿 목록 |
| `POST` | `/api/search/documents` | 하이브리드 문서 검색 (BM25+Vector+RRF) |
| `POST` | `/api/search/summarize` | 검색 결과 요약 (SSE) |

## B-6. 화면 구성

```
┌──────────────────────────────────────────────────┐
│ 문서 검색/작성 (DOCUMENT DRAFTING)                │
├──────────────────────────────────────────────────┤
│ [내부용 INTERNAL] [외부용 EXTERNAL] [문서 이력]   │ ← 3탭 + 골드 밑줄
├──────────────────────────────────────────────────┤
│ 요청: [현대차 SQ팀에 PPAP Level 3 제출 안내_____] │
│ 어조: [공식적 ▼]  유형: [PPAP ▼]  [생성 ▶]        │
│                                                  │
│ ─── 생성 결과 (스트리밍) ──────────────            │
│ ## PPAP Level 3 제출 안내                         │
│ 수신: 현대자동차 SQ팀                             │
│ 발신: 아진산업 품질보증팀                          │
│                                                  │
│ 안녕하십니까. 아진산업 품질보증팀입니다...        │
│ ▌ 토큰 스트리밍 진행 중...                        │
│                                                  │
│ ─── 품질 평가 ────────────────────                │
│ ┌────────────────────────────────────┐            │
│ │ 종합: 87/100 (B+)                  │            │
│ │ ├ 구조 24/25 ✓                    │            │
│ │ ├ 분량 18/20 ✓                    │            │
│ │ ├ 전문성 22/25 ✓                  │            │
│ │ ├ 완성도 13/15 ⚠ (placeholder 1건)│            │
│ │ └ 톤 10/15                        │            │
│ │ 개선: __부품번호__ 채우기          │            │
│ └────────────────────────────────────┘            │
│                                                  │
│ ─── CC 자동 추천 ─────────────────                │
│ 필수: [현대차 SQ팀] [영업1팀]                    │
│ 권장: [품질본부장]                                │
│ 선택: [생산기술팀]                                │
│                                                  │
│ ─── 다운로드 (7포맷) ───────────                  │
│ [DOCX] [ODT] [PDF] [XLSX] [CSV] [TXT] [복사]     │
└──────────────────────────────────────────────────┘
```

---

# 기능 C: AI 업무 도우미

> **영문 라벨**: `AI WORK ASSISTANT`
> **페이지 파일**: [ui/page_onboarding.py](../../ui/page_onboarding.py) (1,896줄 — **최대 페이지**)
> **백엔드**: [backend/routers/onboarding.py](../../backend/routers/onboarding.py)
> **기능 모듈**: [features/onboarding/](../../features/onboarding/) (19 파일)
> **SILLI 부합성**: 생산성 향상 (핵심 취지)

## C-1. 비즈니스 가치

### 문제 정의
- 신입사원 온보딩 = **3~6개월** 학습 곡선
- 매월 다수의 신입 → "선배 한 명이 한 달 동안 신입 한 명 멘토링" = 인건비 누수
- 매뉴얼/SOP는 PDF·종이 형태 → 검색·이해 어려움
- 부서 간 협업 시나리오(8D, ECN, PPAP)는 경험치 의존

### 솔루션
- **듀얼 모드**: 교육 모드 (학습 친화) ↔ 업무 모드 (즉답)
- **SOP 8종 + 협업 시나리오 5종**: 신입이 "선배에게 묻지 않아도" 즉시 응답
- **퀴즈 + 재학습**: 학습 효과 검증 + 오답 기반 보강
- **수주 내 전력화**: SILLI가 가장 중시하는 "생산성 향상"

## C-2. 핵심 기능 목록

### C-2-1. SSE 실시간 스트리밍 (v3.1 신규)
| 항목 | 사양 |
|---|---|
| **프로토콜** | Server-Sent Events (SSE) — POST `/api/onboarding/chat` |
| **엔진** | Ollama stream API (Qwen 3.5 / EXAONE / Gemma 4) |
| **출력** | 토큰 단위 실시간 — `data: {"token": "..."}` JSON |
| **메타데이터** | model 이름, 응답 속도 (tokens/sec), 토큰 수 |
| **네비게이션 차단** | 스트리밍 중 사이드바 모듈 버튼 disabled (v3.4) — 의도치 않은 페이지 이탈 방지 |

위치: [features/onboarding/stream_response.py](../../features/onboarding/), [backend/sse.py](../../backend/sse.py)

### C-2-2. 컨텍스트 최적화 (v3.1 신규)
- **모드별 토큰 예산**:
  - **온보딩(교육)**: 3,000자 컨텍스트 (상세 설명 우선)
  - **업무(즉답)**: 2,000자 컨텍스트 (간결한 답변)
- **중복 청크 제거**: ChromaDB retrieve 결과에서 90% 이상 유사 청크 dedup
- **위치**: [features/onboarding/context_optimizer.py](../../features/onboarding/)

### C-2-3. SOP 단계별 가이드 (v3.4 — 8종)
| # | SOP | 카테고리 |
|:--:|---|---|
| 1 | 금형 교체 | 설비 |
| 2 | 용접 검사 | 설비 |
| 3 | CNC 가공 | 설비 |
| 4 | 8D Report 작성 | 업무 프로세스 |
| 5 | ECN 발행 | 업무 프로세스 |
| 6 | SPC 분석 | 업무 프로세스 |
| 7 | PPAP 제출 | 업무 프로세스 |
| 8 | 안전 점검 | 업무 프로세스 |

각 SOP는 **체크리스트** + **주의사항** + **단계별 진행률 바** + **퀴즈 재학습 경로** 포함.
위치: [features/onboarding/sop_guide.py](../../features/onboarding/) (22KB, 약 600줄)

### C-2-4. 협업 시나리오 5종 (v3.4 신규)
| # | 시나리오 | 트리거 |
|:--:|---|---|
| 1 | 품질팀 → 8D Report 요청 | "품질팀에서 8D 올려달라는데?" |
| 2 | 설계 변경 → ECN 발행 | "설계 변경 요청 왔어" |
| 3 | SPC 이상 → 시정 조치 | "Cpk 1.0 떨어졌어" |
| 4 | 신차 양산 → PPAP | "현대 신차 양산 시작" |
| 5 | 안전 사고 위험 → 점검 | "안전 점검 어떻게 해?" |

LLM 호출 없이 **즉시 응답** — 협업 단계, 담당 부서, 양식 위치, 마감 기한 명시.
위치: [features/onboarding/collaboration_guide.py](../../features/onboarding/) (9KB, 약 250줄)

### C-2-5. 대화형 퀴즈 자동 생성 (v3.1 + v3.4)
- **유형**: SOP 4지선다 / 용어집 4지선다
- **자동 생성**: SOP 단계에서 학습 종료 시 → 퀴즈 3~5문항 자동 출제
- **재학습**: 오답 시 `related_step` 메타데이터로 "Step N 다시 보기" 버튼 → 해당 SOP 단계로 이동
- **정답 해설**: 정답·오답 모두 근거 포함 답변
- **위치**: [features/onboarding/quiz_engine.py](../../features/onboarding/)

### C-2-6. 듀얼 모드 (v3.0)
| 모드 | 응답 스타일 | 컨텍스트 | 사용 시점 |
|---|---|---|---|
| **교육** | 상세 설명 + 예시 + 배경 | 3,000자 | 신입 학습, 개념 이해 |
| **업무** | 간결 즉답 + 액션 버튼 | 2,000자 | 경력자 즉답 필요 |

UI: 페이지 상단 토글 (`[교육] [업무]`).

### C-2-7. 업무 모드 액션 라우터 (v3.1 신규)
업무 모드에서 LLM 호출 **없이** 즉시 응답하는 액션:
| 트리거 | 액션 | 응답 |
|---|---|---|
| "에러코드 E001" | error_code_db 직접 조회 | 에러 상세 + 조치 방법 |
| "김민수 부장 어디?" | 인원 검색 호출 | 사원 정보 + 연락처 |
| "8D 양식 어디?" | feature_bridge 호출 | 기능 B로 이동 + 8D 자동 선택 |
| "SPC 상태?" (v3.4) | spc_dashboard 호출 | 5공정 Cpk 즉시 표시 |
| "REACH 규제 현황?" (v3.4) | compliance scenario 호출 | 시나리오 카드 |

위치: [features/onboarding/work_actions.py](../../features/onboarding/) (13KB, 약 350줄)

### C-2-8. 부서 라우터 (v3.0 + v3.3)
- **31개 부서 프로필**: 각 부서의 핵심 업무·자주 묻는 질문·관련 SOP
- **부서 자동 선택 (v3.3)**: 로그인 사용자 소속 부서를 selectbox 기본값으로 자동 설정
- **부서 변경 권한**: SYS_ADMIN / HR_ADMIN만 다른 부서 컨텍스트로 변경 가능
- **위치**: [features/onboarding/department_router.py](../../features/onboarding/) (26KB, 약 700줄)

### C-2-9. 용어집 매처 (Glossary Matcher)
- **용어집**: **297항목** (21파일, 4종 JSON 형식)
- **파서 호환**: Type A/B/C/D 4종 JSON 구조 호환 (v2.6 Type D 파서 수정)
- **사용**: LLM 프롬프트에 관련 용어 자동 주입 + 답변에서 용어 자동 하이라이트
- **위치**: [features/onboarding/glossary_matcher.py](../../features/onboarding/), [data/knowledge_base/glossary/](../../data/knowledge_base/)

### C-2-10. 대화 요약 메모리 (v3.0)
- **트리거**: 컨텍스트가 모델 한계 80% 도달 시
- **요약**: LLM이 직전 6턴 대화 → 200자 요약
- **저장**: session_state — 다음 턴부터 요약 텍스트만 컨텍스트에 포함
- **위치**: [features/onboarding/conversation_memory.py](../../features/onboarding/)

### C-2-11. 비전 모델 (Gemma 4)
- **트리거**: 사용자가 이미지 첨부 시
- **모델**: Gemma 4 멀티모달 (latest/e2b/26b)
- **용도**: 도면 분석, 부품 사진 식별, 차트 해석
- **API**: `POST /api/onboarding/chat/vision` — multipart form-data
- **위치**: [core/llm_client.py](../../core/) `invoke_vision()` + [auto_select_vision_model()](../../core/)

### C-2-12. 파일 업로드 (20+ 확장자)
| 카테고리 | 확장자 |
|---|---|
| 문서 | PDF, TXT, DOCX, DOC, HWP |
| 표 | XLSX, XLS, CSV |
| 이미지 | PNG, JPG, JPEG, GIF, BMP, WEBP (→ 비전 모델) |

- **최대 크기**: **20 MB**
- **경로 검증**: `validate_path()` — 경로 순회 공격 방어
- **API**: `POST /api/onboarding/upload`

### C-2-13. 다운로드 영구화 (v3.5 신규)
- **문제**: `st.write_stream()`은 1회성 → rerun 시 다운로드 버튼 소멸
- **해결**: session_state `_downloads` 키에 바이트 영구 저장 → 히스토리 루프에서 재렌더링
- **포맷**: DOCX / XLSX / CSV / TXT (4포맷)
- **메모리 관리**: 최근 20개 메시지만 다운로드 바이트 유지

### C-2-14. 피드백 이모지 (v3.1 + v3.5)
- **버튼**: 👍 도움됨 / 👎 아쉬움
- **저장**: SQLite `feedback.db`
- **확인 메시지**: 녹색 (도움됨) / 주황 (아쉬움)
- **분석**: Feature E 분석 탭에서 부서별 만족도 통계로 활용
- **위치**: [features/onboarding/feedback_db.py](../../features/onboarding/)

### C-2-15. 빠른 질문 데모 (v3.4 신규)
생산기술팀 6개 데모 질문 — SOP/협업 트리거.
- "프레스 트라이 SOP 알려줘"
- "품질팀에서 8D 올려달라는데?"
- "용접 검사 절차"
- ...

## C-3. 사용자 흐름

```
[로그인 (생산기술팀)]
    ↓
[사이드바: AI 업무 도우미]
    ↓
[페이지 진입 — 부서 자동 선택: "생산기술팀"]
[모드 선택: 교육 / 업무]
    ↓
[데모 빠른 질문 또는 자유 입력]
    ↓
[ML 의도 분류 (5ms, 70%+ 신뢰도)]
    ├─ "에러코드" 의도 → error_code_db 즉시 응답
    ├─ "인원 검색" 의도 → 인원 검색 라우팅
    └─ "일반 질의" → LLM (Ollama)
    ↓
[교육 모드: SOP 8종 → 단계별 가이드]
[업무 모드: 협업 시나리오 5종 → 즉시 응답]
    ↓
[SSE 스트리밍 (네비 차단)]
    ↓
[퀴즈 자동 생성 (SOP 학습 종료 시)]
    ├─ 정답 → 다음 단계
    └─ 오답 → "Step N 다시 보기" 재학습
    ↓
[다운로드 (DOCX/XLSX/CSV/TXT) — 영구화]
[피드백 (👍/👎)]
[대화 요약 (80% 도달 시)]
```

## C-4. 데이터 자산

| 항목 | 위치 | 규모 |
|---|---|---|
| 용어집 | [data/knowledge_base/glossary/](../../data/knowledge_base/) | **297항목** (21파일) |
| SOP | [data/knowledge_base/sop/](../../data/knowledge_base/) | 6종 (+ 8종 in-code) |
| 부서별 가이드 | [data/knowledge_base/department_guides/](../../data/knowledge_base/) | 31개 부서 |
| 피드백 DB | [data/feedback.db](../../data/) | 누적 사용자 평가 |
| ML 의도 학습 | [data/intent_ml/](../../data/) | 1,500건 |

## C-5. 백엔드 API

| Method | Endpoint | 응답 |
|:--:|---|---|
| `POST` | `/api/onboarding/chat` | **SSE 스트리밍** |
| `POST` | `/api/onboarding/chat/vision` | 비전 모델 응답 (이미지 + 질의) |
| `POST` | `/api/onboarding/upload` | 파일 텍스트 추출 + base64 (이미지) |

**스트리밍 요청 예시**:
```json
{
  "query": "8D Report 작성 방법",
  "department": "품질보증팀",
  "model": "qwen3.5:9b",
  "history": [{"role":"user","content":"..."},{"role":"assistant","content":"..."}],
  "file_context": null
}
```

**SSE 응답**:
```
data: {"token": "8D"}
data: {"token": " Report"}
data: {"token": "는..."}
...
data: {"done": true}
```

## C-6. 화면 구성

```
┌─────────────────────────────────────────────────┐
│ AI 업무 도우미 (AI WORK ASSISTANT)              │
│ 부서: 생산기술팀 ▼   모드: [교육 ●] [업무]       │
├─────────────────────────────────────────────────┤
│ 빠른 질문:                                      │
│ [프레스 SOP] [8D 요청] [에러코드] [SPC 상태]    │
│                                                 │
│ ─────────────── 대화 ────────────────            │
│                                                 │
│ 🧑 프레스 트라이 SOP 알려줘     [09:23]         │
│                                                 │
│ 🤖 [SOP: 프레스 트라이]         [09:23, 800ms]  │
│ Step 1 of 7 — 금형 점검                          │
│ 진행률: ▓▓▓░░░░░░ 14%                           │
│ ┌─ 체크리스트 ──────────────┐                   │
│ │ □ 금형 표면 균열 확인      │                   │
│ │ □ 가이드 핀 마모 측정      │                   │
│ │ □ 냉각 라인 누수 점검      │                   │
│ └────────────────────────────┘                   │
│ ⚠ 주의: 마모 0.3mm 초과 시 교체                  │
│ [Next ▶] [Quiz 풀어보기]                        │
│ 📥 DOCX  📥 XLSX  📥 CSV  📥 TXT                │
│ 👍 도움됨  👎 아쉬움                             │
│                                                 │
│ ─ ─ ─ AI 세션 메모리 ─ ─ ─                      │
│ 토큰: 420 / 컨텍스트: 6턴                       │
│                                                 │
├─────────────────────────────────────────────────┤
│ [📎] [질문을 입력하세요...]              [전송] │
└─────────────────────────────────────────────────┘
```

---

# 기능 D: 법규/규정 모니터링

> **영문 라벨**: `COMPLIANCE MONITORING`
> **페이지 파일**: [ui/page_compliance.py](../../ui/page_compliance.py) (2,144줄 — 두 번째로 큰 페이지)
> **백엔드**: [backend/routers/compliance.py](../../backend/routers/compliance.py)
> **기능 모듈**: [features/compliance/](../../features/compliance/) (33 파일)
> **SILLI 부합성**: 안전성 향상 + 투자비 절감

## D-1. 비즈니스 가치

### 문제 정의
- 1차 협력사는 **국내법(산안법, 화관법) + EU 규제(REACH, RoHS, ESG) + 미국 규제(트럼프 관세) + OEM 요구사항(IATF, PPAP) + 인증(ISO 14001/45001)** 동시 준수 필요
- 법규 변경 → **납품 자격 박탈** + 과징금 위험
- 외부 법무·환경 컨설팅 비용 **연 1,000만 원+**
- 매뉴얼 추적 = 인력 부담

### 솔루션
- **9종 크롤러**: 법규 사이트 자동 모니터링 + 변경 감지
- **3종 데모 시나리오**: 산안법 / 관세 / REACH — 즉시 시연 가능
- **리스크 정량화**: 100점 스코어링 (재무 40 + 가능성 30 + 긴급도 30)
- **관세 시뮬레이터**: 슬라이더 → 실시간 원가 영향 — 트럼프 25% = **400억 원** 영향

## D-2. 핵심 기능 목록

### D-2-1. 9종 크롤러 (v3.5 정리)
| # | 크롤러 | 대상 | 위치 |
|:--:|---|---|---|
| 1 | ISO Crawler | ISO 14001 / 45001 | [iso_crawler.py](../../features/compliance/iso_crawler.py) (19KB) |
| 2 | MSDS Crawler | 화학물질안전보건자료 | [msds_crawler.py](../../features/compliance/) (28KB) |
| 3 | EU Regulation Crawler | REACH, RoHS, ELV | [eu_regulation_crawler.py](../../features/compliance/) (17KB) |
| 4 | Domestic Law Crawler | 산안법, 화관법, 환경법 | [domestic_law_crawler.py](../../features/compliance/) (23KB) |
| 5 | OEM Quality Crawler | IATF 16949, PPAP, FMEA | [oem_quality_crawler.py](../../features/compliance/) (33KB) |
| 6 | APQP Crawler | APQP 단계별 요구사항 | [apqp_crawler.py](../../features/compliance/) (26KB) |
| 7 | Carbon ESG Crawler | 탄소 배출 / ESG 지표 | [carbon_esg_crawler.py](../../features/compliance/) (33KB) |
| 8 | EV Battery Crawler | EV 배터리 규제 (UN R100) | [ev_battery_crawler.py](../../features/compliance/) (31KB) |
| 9 | Global Trade Crawler | 관세, FTA, 무역 규제 | [global_trade_crawler.py](../../features/compliance/) (32KB) |

(US Trade Crawler 별도 — [us_trade_crawler.py](../../features/compliance/) 트럼프 관세 전용)

**v3.5 인코딩 수정**: 모든 크롤러 UTF-8 명시 + `_safe_truncate()` 멀티바이트 안전 잘림.

### D-2-2. 리스크 정량 스코어링 (v3.1 신규)
| 축 | 가중치 | 평가 항목 |
|---|:--:|---|
| **재무 영향** | 40점 | 매출 영향(원), 벌금, 컨설팅비 |
| **가능성** | 30점 | 변경 빈도, 정부 단속 빈도, OEM 감사 빈도 |
| **긴급도** | 30점 | 시행일까지 D-day, 적용 범위 |

총 **100점**. 점수별 카테고리: CRITICAL(80+) / HIGH(60~79) / MEDIUM(40~59) / LOW(<40).
위치: [features/compliance/risk_scorer.py](../../features/compliance/)

### D-2-3. 데모 시나리오 3종 (v3.4 신규)
| 시나리오 | 점수 | 카테고리 | 핵심 |
|---|:--:|---|---|
| **산안법 안전거리** | **85점** | CRITICAL | 프레스 안전거리 300mm → 400mm 변경 (시행 D-30) |
| **관세 시뮬레이터** | **78점** | HIGH | 트럼프 25% 관세 → JOON INC 공급 원가 400억 원 영향 |
| **REACH 신규 SVHC** | **52점** | MEDIUM | EU 신규 우려물질 등재 → 부품 재인증 |

각 시나리오는 **오프라인 실행** 가능 (네트워크 없이 내장 데이터로 시연).
위치: [features/compliance/demo_scenario_engine.py](../../features/compliance/) (13KB, 약 350줄)

### D-2-4. 데드라인 타임라인 (v3.1 신규)
- **시각화**: Plotly 간트 차트 + 잔여 일수 표시
- **색상 코딩**:
  - **CRITICAL** (D-7 이내): `#C0392B` 빨강
  - **HIGH** (D-30 이내): `#E8A317` 주황
  - **MEDIUM** (D-90 이내): `#2980B9` 파랑
  - **LOW** (D-90 초과): `#5C4E3C` 회색
- **위치**: [features/compliance/timeline_builder.py](../../features/compliance/)

### D-2-5. 관세 시뮬레이터 (v3.1 신규)
- **슬라이더**: 0% ~ 50% 관세율
- **품목**: 6종 (CCH, OBC, 범퍼빔, 도어, 볼시트, EV 배터리 케이스)
- **계산**: 슬라이더 변경 → 실시간 원가 영향 (Plotly Bar 차트)
- **샘플**: 25% 관세 시 JOON INC 공급분 약 **400억 원** 추가 부담
- **위치**: [features/compliance/tariff_simulator.py](../../features/compliance/)

### D-2-6. 규제 변경 자동 감지 (v3.1 신규)
- **방식**: 크롤링 전후 JSON diff (snapshot)
- **분류**: 신규 / 수정 / 삭제 / 미확인
- **저장**: SQLite `compliance_changes.db`
- **확인 처리**: 사용자가 "확인" 클릭 → status `confirmed` 변경
- **CSV 내보내기**: 변경 이력 다운로드
- **위치**: [features/compliance/change_detector.py](../../features/compliance/)

### D-2-7. 규제 영향 네트워크 (v3.1 신규)
- **시각화**: Plotly Network 그래프
- **노드**: 규제 → 시설(19개소) → 부서/제품
- **엣지**: 영향 관계 + 가중치
- **상호작용**: 노드 클릭 → 상세 정보 팝업 + Feature Bridge (관련 부서로 이동)
- **위치**: [features/compliance/impact_network.py](../../features/compliance/), [impact_analyzer.py](../../features/compliance/)

### D-2-8. AI 리스크 분류 (v3.1 신규)
- **모델**: TF-IDF + RandomForest
- **학습 데이터**: 450건 (HIGH/MEDIUM/LOW)
- **출력**: 리스크 레벨 + 관련 부서 + 영향 시설 + 대응 기한
- **위치**: [features/compliance/regulation_classifier.py](../../features/compliance/)

### D-2-9. 부서 기반 접근 제어 (v3.3)
**허용 7개 부서**:
- 품질보증팀, 환경안전팀, 법무팀, 구매팀, 해외영업팀, 생산기술팀, 경영기획팀

위 외 부서는 **사이드바 메뉴 자체에서 숨김** + 페이지 진입 방어 코드.
구현: `is_menu_visible(slug, dept, role)` ([core/auth/permissions.py](../../core/auth/permissions.py))

### D-2-10. 4탭 구조 (v3.5 개편)
| 탭 | 서브탭 |
|---|---|
| **법규 모니터** | 6서브탭 (시나리오 / 시설 매핑 / 리스크 / 타임라인 / 관세 / 영향 네트워크) |
| **법규 업데이트** (v3.5 메인 탭 승격) | TOP-3 시나리오 + 변경 감지 + CSV 내보내기 |
| **사업장** | 19개소 Folium 지도 + 인증 현황 |
| **법규 문서** | DOCX/PDF 변환 저장 |

### D-2-11. 한글 인코딩 수정 (v3.5)
- **U+FFFD 19개 복원**: 깨진 문자 정상 한글로 복원
- **`_safe_truncate()`**: UTF-8 멀티바이트 중간 절단 방지
- **`PRAGMA encoding='UTF-8'`**: SQLite UTF-8 명시
- **ISO 크롤러**: HTTP 응답 인코딩 명시 (`resp.encoding = "utf-8"`)

### D-2-12. 크롤링 UI 개선 (v3.5)
- **실행 컨트롤 상단**: `RUN ALL` / 선택 드롭다운 / `RUN SELECTED` 3열 레이아웃
- **빠른 현황 요약**: "N/9 크롤러 정상 | 마지막 실행: YYYY-MM-DD HH:MM"
- **테이블**: 9개 크롤러 status / 마지막 실행 시각 / 변경 건수

## D-3. 사용자 흐름

```
[로그인 (품질보증팀)]
    ↓
[사이드바: 법규 모니터링 — 부서 권한 통과]
    ↓
[탭 선택: 법규 업데이트]
    ↓
[TOP-3 시나리오 카드 (자동 정렬)]
  ├─ 산안법 안전거리 (85점, D-30)
  ├─ 트럼프 관세 (78점, D-90)
  └─ REACH 신규 SVHC (52점, D-180)
    ↓
[시나리오 카드 클릭: 산안법 안전거리]
    ↓
[시뮬레이션 실행]
  ├─ 변경 비교 (전: 300mm → 후: 400mm)
  ├─ 리스크 점수 분해 (재무 30/가능성 28/긴급도 27)
  ├─ 영향 시설 (본사 프레스 라인 3개소)
  └─ 대응 부서 (생산기술팀 + 환경안전팀)
    ↓
[관세 시뮬레이터 탭 → 슬라이더 25%]
    ↓
[6품목 원가 영향 Plotly Bar — 실시간 갱신]
    ↓
[변경 이력 CSV 내보내기]
[영향 네트워크 → 노드 클릭 → Feature Bridge → 기능 F (생산기술팀 페이지)]
```

## D-4. 데이터 자산

| 항목 | 위치 | 규모 |
|---|---|---|
| 시나리오 JSON | [data/scenarios/](../../data/scenarios/) | 9종 (TOP-3 데모 포함) |
| 데모 시나리오 | [data/demo_scenarios/](../../data/) | 3종 (오프라인 실행 가능) |
| 크롤링 결과 | [data/crawled/](../../data/) | 9 크롤러 × snapshot |
| 변경 이력 DB | [data/compliance_changes.db](../../data/) | 누적 변경 |
| 규제 ML 학습 | [data/regulation_ml/](../../data/) | **450건** |
| 시설 DB | [data/facility_db/plants.json](../../data/) | 19개소 |
| 규제 문서 | [data/compliance_docs/](../../data/) | DOCX/PDF 변환 |

## D-5. 백엔드 API

| Method | Endpoint | 인증 | 용도 |
|:--:|---|:--:|---|
| `GET` | `/api/compliance/scenarios` | 필수 | 시나리오 목록 |
| `GET` | `/api/compliance/facilities` | 필수 | 19개소 시설 목록 |
| `POST` | `/api/compliance/check` | **필수 + perm** | 키워드 기반 규정 매칭 (IATF/ISO/REACH/RoHS/PPAP/FMEA/SPC/MSDS) |

권한: `compliance.run_analysis` (관련 부서 EMPLOYEE+)

## D-6. 화면 구성

```
┌──────────────────────────────────────────────────┐
│ 법규 모니터링 (COMPLIANCE MONITORING)            │
├──────────────────────────────────────────────────┤
│ [법규 모니터] [법규 업데이트] [사업장] [법규 문서]│
├──────────────────────────────────────────────────┤
│ ─── 규제 현황 시나리오 TOP-3 ──────────             │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐            │
│ │ 산안법   │ │ 트럼프관세│ │ REACH    │            │
│ │ 85 점    │ │ 78 점    │ │ 52 점    │            │
│ │ D-30     │ │ D-90     │ │ D-180    │            │
│ │ CRITICAL │ │ HIGH     │ │ MEDIUM   │            │
│ │ [시뮬]   │ │ [시뮬]   │ │ [시뮬]   │            │
│ └──────────┘ └──────────┘ └──────────┘            │
│                                                  │
│ ─── 변경 감지 메트릭 ───────────────                │
│ 총 변경: 12  /  신규: 3  /  수정: 7  /  미확인: 2 │
│                                                  │
│ ─── 변경 상세 목록 ─────────────                  │
│ ▣ ISO 14001 — 6.1.2 환경측면 식별 (수정)         │
│   전: "..."   후: "..."   [확인] [상세]          │
│                                                  │
│ ─── 관세 시뮬레이터 ─────────                      │
│ 관세율: ━━━━●━━━━━━━━ 25%                          │
│ [Plotly Bar — 6품목 원가 영향]                   │
│ JOON INC 공급분: +400억 원                       │
│                                                  │
│ ─── 영향 네트워크 ─────────                        │
│ [Plotly Network 그래프]                          │
│  산안법 → 본사 프레스 → 생산기술팀                │
│  산안법 → 천안 1공장 → 환경안전팀                 │
└──────────────────────────────────────────────────┘
```

---

# 기능 E: 인사 관리

> **영문 라벨**: `HR ADMIN MANAGEMENT`
> **페이지 파일**: [ui/page_admin.py](../../ui/page_admin.py) (1,314줄)
> **백엔드**: [backend/routers/auth.py](../../backend/routers/auth.py) + 인사 관련 직접 호출
> **기능 모듈**: [features/admin/](../../features/admin/) (2 파일) + [core/auth/](../../core/auth/) (10 파일)
> **SILLI 부합성**: 투자비 절감 (보안 자동화)

## E-1. 비즈니스 가치

### 문제 정의
- 649명 조직 — RBAC + 부서 권한 수동 관리는 **HR 팀 인력 부담**
- 보안 사고 (계정 탈취, 무차별 대입) 사후 감지 → **사전 감지 필요**
- AI 시스템 사용 통계 부재 → 도입 효과 정량화 불가

### 솔루션
- **6탭 통합 Admin** (v3.5: 이력→보안 통합)
- **3종 보안 감지**: 무차별 대입 / 야간 접근 / 비활성 계정
- **AI 활용 분석 + ROI**: 부서별 사용 빈도, 비용 절감 추정
- **인력 통계 7종 차트**: 본부별/직급별/성별/사업장별/근속연수

## E-2. 핵심 기능 목록

### E-2-1. RBAC 6단계
| 레벨 | 역할 | 영문 | 권한 |
|:--:|---|---|---|
| **6** | 시스템 관리자 | `SYS_ADMIN` | 모든 권한 + 시스템 설정 |
| **5** | HR 관리자 | `HR_ADMIN` | 사용자·부서·계정 관리 |
| **4** | 본부장 / 팀장 | `TEAM_LEAD` | 본부 내 통계 + 인사 조회 |
| **3** | 매니저 | `MANAGER` | 부서 내 일부 관리 권한 |
| **2** | 일반 직원 | `EMPLOYEE` | 본인 정보 + 검색·문서 작성 |
| **1** | 비활성 | `INACTIVE` | 모든 접근 차단 |

위치: [core/auth/rbac.py](../../core/auth/), [core/auth/permissions.py](../../core/auth/) (22KB, 28개 세부 권한)

### E-2-2. 28개 세부 권한 (v3.0)
주요 권한 키:
- `employee.view_all`, `employee.view_dept`, `employee.edit_own`
- `draft.create`, `draft.export`, `draft.view_all_versions`
- `compliance.run_analysis`, `compliance.view_all_scenarios`
- `equipment.view_dashboard`, `equipment.run_spc_analysis`, `equipment.edit_error_codes`
- `admin.view_users`, `admin.create_user`, `admin.audit_log`, `admin.security_audit`

### E-2-3. JWT + bcrypt 인증
| 항목 | 사양 |
|---|---|
| **인증 방식** | JWT (HS256) + Refresh Token |
| **비밀번호 해싱** | bcrypt (cost=12) |
| **토큰 수명** | Access 1시간, Refresh 7일 |
| **세션 저장** | 서버사이드 (`/data/.sessions/`) + 쿠키 (`HttpOnly; Secure; SameSite`) |
| **계정 잠금** | 5회 실패 → 30분 잠금 |
| **위치** | [core/auth/jwt_handler.py](../../core/auth/), [password.py](../../core/auth/), [session_store.py](../../core/auth/) |

### E-2-4. 비밀번호 정책 (v3.3 강화)
| 조건 | 검증 |
|---|---|
| 최소 길이 8자 | ✓ |
| 대문자 1자 이상 | ✓ |
| 소문자 1자 이상 | ✓ |
| 숫자 1자 이상 | ✓ |
| 특수문자 1자 이상 | ✓ |
| 연속 3회 이상 동일 문자 금지 | ✓ |
| 비밀번호 이력 (최근 3개) 재사용 금지 | ✓ |

UI: 6개 조건 실시간 강도 표시 (체크박스 점등).
위치: [core/auth/password.py](../../core/auth/)

### E-2-5. 보안 감사 (v3.1 — 3종 감지)
| 감지 | 트리거 | 액션 |
|---|---|---|
| **무차별 대입** | 동일 IP 5분 내 5회 실패 | 빨강 카드 + IP 자동 블록 |
| **야간 접근** | 22:00 ~ 06:00 로그인 | 주황 카드 + HR_ADMIN 알림 |
| **비활성 계정** | 90일 미접속 | 회색 카드 + 자동 비활성화 옵션 |

위치: [features/admin/security_monitor.py](../../features/admin/) (9KB)

### E-2-6. AI 활용 분석 (v3.1 신규)
- **메트릭**: 기능별 사용량 / 부서별 빈도 / 시간대별 사용 / 활성 사용자 (DAU/WAU/MAU)
- **시각화**: 부서 × 기능 히트맵 + DAU 추이 라인 차트
- **ROI 산출**: 추정 절감 시간 (분/일) × 시간당 인건비 = 비용 절감 추정
- **위치**: [features/admin/usage_analytics.py](../../features/admin/) (10KB)

> **참고 (V3.4 점검)**: AI가 AI ROI를 계산하는 자기 참조성 우려 — 데모에서 "경영진 보고용 대시보드"로 포지셔닝 권장.

### E-2-7. 인력 통계 7종 차트 (v3.1 신규)
| 차트 | 종류 | 데이터 |
|---|---|---|
| 본부별 인원 분포 | Bar | 본부 × 인원 |
| 직급별 분포 | Pie | 사원/대리/과장/차장/부장 |
| 성별 분포 | Pie | M/F |
| 사업장별 분포 | Bar | 19개소 |
| 근속연수 분포 | Histogram | 1년/3년/5년/10년+ |
| 본부 × 직급 히트맵 | Heatmap | 본부별 직급 분포 |
| 입사 추이 | Line | 월별 입사자 수 |

### E-2-8. 6탭 Admin UI (v3.5)
| 탭 (Tier 4: SYS_ADMIN) | 탭 (Tier 3: TEAM_LEAD) | 콘텐츠 |
|---|---|---|
| **사용자** | ✓ | 사용자 검색·필터·인라인 편집 7항목 |
| **생성** | - | 신규 사용자 3단계 위저드 |
| **보안** (v3.5 이력 통합) | ✓ | 감사 카드 + 상세 이력 + CSV 다운로드 |
| **분석** | ✓ | AI 활용 분석 + ROI |
| **인사 통계** | ✓ | 7종 Plotly 차트 |
| **도구** | - | 백업·복원·DB 관리 |

### E-2-9. 로그인 이력 다운로드 (v3.5 신규)
| 항목 | 사양 |
|---|---|
| **컬럼** | 타임스탬프 / 사번 / 사용자명 / 부서 / 직위 / 액션 / 성공여부 / IP / User-Agent |
| **필터** | 날짜 범위 + 최대 건수 (100~10000) |
| **CSV** | UTF-8 BOM (`utf-8-sig`) |
| **XLSX** | openpyxl, 시트명 "로그인이력" |

위치: `_render_login_history_with_export()` ([ui/page_admin.py:625](../../ui/page_admin.py))

### E-2-10. 부서 매핑 확장 (v3.3)
- 부서 접두어 매핑 17개 → **30개** (전체 독립부서 커버)
- **사원번호 자동 갱신**: 부서 selectbox 변경 시 `{접두어}-{순번}` 자동 생성
- 예: 품질보증팀 → `QA-0001`, 생산기술팀 → `PE-0023`

### E-2-11. 인라인 편집 7항목 (v2.7)
- 이름 / 부서 / 직급 / 본부 / 사업장 / 이메일 / 전화
- 더블 클릭으로 편집 → Enter로 저장
- 변경 시 audit log 자동 기록

### E-2-12. 3단계 사용자 생성 위저드 (v2.7)
1. **기본 정보**: 사번 / 이름 / 부서 / 직급
2. **권한 설정**: RBAC 레벨 + 세부 권한 체크
3. **인증**: 임시 비밀번호 발급 + `must_change_pw=True` 플래그

### E-2-13. 감사 로그 (audit.db)
모든 API 호출 기록:
- 엔드포인트 + 메소드 + 시각 + 사용자 + 상세 + 상태 코드
- 위치: [data/audit.db](../../data/), [backend/auth_middleware.py](../../backend/) `log_api_access()`

### E-2-14. 테스트 계정 33명
| 본부 | 계정 수 |
|---|---|
| 시스템 관리자 | 2 |
| 인사본부 | 3 |
| 품질본부 | 6 |
| 생산기술본부 | 5 |
| 영업본부 | 4 |
| 환경안전팀 | 3 |
| 법무팀 | 2 |
| 기타 | 8 |

> **V3.4 점검 노트**: 문서상 33명 vs 실제 시딩 12명 → 데모 전 21명 추가 시딩 필요.

## E-3. 사용자 흐름

```
[로그인 (HR_ADMIN)]
    ↓
[사이드바: 인사 관리] (RBAC L5+ 확인)
    ↓
[6탭 노출]
    ↓
[보안 탭]
    ├─ 감사 카드 3종 (무차별/야간/비활성)
    └─ 상세 이력 (Expander)
       ├─ 날짜 필터 + 건수
       └─ CSV/XLSX 다운로드
    ↓
[분석 탭]
    ├─ 부서 × 기능 히트맵
    ├─ DAU 추이
    └─ ROI 추정 (절감 시간 × 인건비)
    ↓
[인사 통계 탭]
    └─ 7종 Plotly 차트
```

## E-4. 데이터 자산

| 항목 | 위치 | 규모 |
|---|---|---|
| 사용자 DB | [data/auth.db](../../data/) | 33명 (테스트), bcrypt 해시 |
| 감사 로그 DB | [data/audit.db](../../data/) | 모든 API 호출 |
| 세션 저장소 | [data/.sessions/](../../data/) | 서버사이드 JWT |
| 비밀번호 이력 | `password_history` 테이블 | 사용자당 최근 3개 |
| JWT secret | [data/.jwt_secret](../../data/) | 서버 시작 시 자동 생성 |

## E-5. 백엔드 API

| Method | Endpoint | 인증 | 응답 |
|:--:|---|:--:|---|
| `POST` | `/api/auth/login` | - | access + refresh token |
| `POST` | `/api/auth/change-password` | 사번 검증 | 비밀번호 변경 |
| `POST` | `/api/auth/refresh` | refresh token | 새 access token |

(Admin 페이지의 인사 관리는 현재 직접 import 호출 — React 마이그레이션 시 REST API 추가 필요)

## E-6. 화면 구성

```
┌──────────────────────────────────────────────────┐
│ 인사 관리 (HR ADMIN)                             │
├──────────────────────────────────────────────────┤
│ [사용자] [생성] [보안] [분석] [인사 통계] [도구] │
├──────────────────────────────────────────────────┤
│ ── 보안 ─────────                                  │
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐  │
│ │ 무차별 대입 │ │ 야간 접근   │ │ 비활성 계정 │  │
│ │ 1건 감지    │ │ 3건 감지    │ │ 5건 감지    │  │
│ │ ●  CRITICAL │ │ ●  WARNING  │ │ ●  INFO     │  │
│ └─────────────┘ └─────────────┘ └─────────────┘  │
│                                                  │
│ ▼ 상세 로그인 이력 및 다운로드                    │
│ 날짜: [2026-04-01] ~ [2026-04-26]                │
│ 건수: [1000 ▼]                                   │
│ [CSV 다운로드] [XLSX 다운로드]                   │
│                                                  │
│ [테이블: 타임스탬프 | 사번 | 부서 | IP | UA ...] │
│                                                  │
│ ── 분석 ─────────                                  │
│ [Plotly 부서×기능 히트맵]                        │
│ [Plotly DAU 추이 라인]                           │
│ ROI: 절감 시간 4시간/일/인 × 33명 × 30,000원/h   │
│      = 월 약 950만 원 절감 추정                   │
└──────────────────────────────────────────────────┘
```

---

# 기능 F: 설비/공정 AI 어시스턴트

> **영문 라벨**: `EQUIPMENT & PROCESS AI`
> **페이지 파일**: [ui/page_equipment.py](../../ui/page_equipment.py) (1,628줄)
> **기능 모듈**: [features/equipment/](../../features/equipment/) (22 파일)
> **SILLI 부합성**: 품질 개선 + 안전성 향상 (제조업 AI의 핵심)

## F-1. 비즈니스 가치

### 문제 정의
- "관리 한계 안에 있어 사람 눈으로는 정상이지만, AI가 패턴을 잡는다" — SILLI 취지의 핵심
- 에러코드 201건 → 신입은 외울 수 없음
- SPC 차트 → Nelson Rule 8가지를 사람이 일일이 검사하기 어려움
- 금형 수명 = 경험치 의존 → 객관 데이터 부족
- 설비 매뉴얼 = 종이/PDF 산재

### 솔루션
- **실제 동작 ML 모델 4종** (TF-IDF + Isolation Forest + XGBoost + Markov Chain) — "PPT AI"가 아닌 실동작
- **Nelson 8 Rules SPC**: 사람이 못 보는 통계적 이상 자동 감지
- **에러코드 자연어 검색**: "프레스에서 이상한 소리" → 유사 에러 + 이력 + 연쇄 경고
- **MTBF 예측 정비**: 15대 기계, 240건 수리이력으로 다음 정비 예측

## F-2. 핵심 기능 목록

### F-2-1. 에러코드 DB (v3.0)
| 항목 | 사양 |
|---|---|
| **총 건수** | **201건** |
| **장비 유형** | 7종 (프레스, 용접, CNC, 사출, 도장, 검사, 컨베이어) |
| **필드** | 코드 / 설명 / 원인 / 조치 / 부품 / 심각도 / 평균 복구시간 |
| **저장** | SQLite [data/equipment/error_codes.db](../../data/equipment/) |
| **위치** | [features/equipment/error_code_db.py](../../features/equipment/) |

### F-2-2. ML 에러 검색 (v3.1 + v3.4 강화)
| 항목 | 사양 |
|---|---|
| **알고리즘** | TF-IDF + 코사인 유사도 |
| **동의어 사전** | **79개** (한국어, "이상한 소리" → "이음" 등) |
| **장비 가중치** | 사용자 선택 장비 → +0.3 boost |
| **이력 DB** | **685건** (`error_history.db`) — 발생 빈도 가중치 |
| **응답 시간** | **<50ms** |
| **피드백** | 👍/👎 → `search_feedback.db` |
| **위치** | [features/equipment/ml_error_search.py](../../features/equipment/) (24KB) |

### F-2-3. 에러 인과 규칙 (v3.1 신규)
- **카테고리**: **25개** (균열, 마모, 누수, 과열, 진동, 전기, 유압 등)
- **인과 규칙**: 70+ (예: "유압 누수 → 압력 저하 → 성형 불량")
- **위치**: [features/equipment/error_causality.py](../../features/equipment/) (10KB)

### F-2-4. Markov 연쇄 고장 예측 (v3.1 신규)
- **모델**: Markov Chain (25 상태 × 25 상태 전이 행렬)
- **DFS 깊이**: 3단계 (즉각 → 1차 → 2차 영향)
- **출력**: 후속 발생 예상 에러 + 확률 + 권장 사전 조치
- **응답**: <30ms
- **위치**: [features/equipment/markov_predictor.py](../../features/equipment/) (15KB)

### F-2-5. SPC Nelson 8 Rules (v3.1 + v3.4)
**관리도 이상 패턴 8가지 자동 감지**:
| Rule | 패턴 |
|:--:|---|
| 1 | 1점이 ±3σ 초과 |
| 2 | 9점 연속 같은 측 (평균 이동) |
| 3 | 6점 연속 증가 또는 감소 |
| 4 | 14점 교대 증감 |
| 5 | 3점 중 2점이 ±2σ 초과 |
| 6 | 5점 중 4점이 ±1σ 초과 |
| 7 | 15점 연속 ±1σ 이내 (분산 감소) |
| 8 | 8점 연속 ±1σ 외부 |

**v3.4 강화**:
- 가이드 딕셔너리 — 각 위반에 대한 한국어 설명
- 차트 Annotation — 위반 위치에 풍선·음영 자동 표시
- 5공정 건강 대시보드 (CCH/OBC/범퍼빔/도어/볼시트) — 신호등 + Cpk + 위반 수

위치: [features/equipment/spc_realtime.py](../../features/equipment/) (20KB)

### F-2-6. ML SPC 이상 탐지 (v3.1 신규)
- **모델**: Isolation Forest (sklearn)
- **학습 데이터**: 합성 시계열 **10,000건** (5공정)
- **이동 윈도우 Cpk 예측**: 50샘플 윈도우 → Cpk 추세 → 다음 100샘플 예측
- **위치**: [features/equipment/spc_ml_predictor.py](../../features/equipment/) (22KB)

### F-2-7. SPC 데이터 생성기 (v3.5 신규)
| 시나리오 | 효과 |
|---|---|
| 트렌드 주입 | 선형 드리프트 (CCH 자동) |
| 평균 이동 | Nelson Rule 2 (범퍼빔 자동) |
| 이상치 주입 | 단발 outlier (OBC 자동) |
| 층화 | 두 모집단 혼합 |
| 진동 패턴 | 주기적 변동 |

CSV 업로드 인터페이스 + 샘플 재생성 (50~2000샘플).
위치: [features/equipment/spc_data_generator.py](../../features/equipment/) (7KB)

### F-2-8. XGBoost 금형 수명 예측 (v3.1 신규)
| 항목 | 사양 |
|---|---|
| **모델** | XGBoost Regressor |
| **특성 (10종)** | 누적 타수, 평균 사이클 시간, 재질, 부품 사이즈, 마지막 정비 후 일수, 결함률 등 |
| **학습 데이터** | **500건** (배스터브 곡선 시뮬) |
| **출력** | 잔여 수명(타) + 교체 예상일 + 리스크 레벨(LOW/MED/HIGH) |
| **응답** | <50ms |
| **금형 DB** | **25건** ([data/equipment/mold_lifecycle.db](../../data/equipment/)) |
| **위치** | [features/equipment/mold_ml_predictor.py](../../features/equipment/) (20KB) |

### F-2-9. MTBF 예측 정비 엔진 (v3.3 신규)
- **MTBF**: Mean Time Between Failures
- **데이터**: 15대 기계 × 240건 수리 이력
- **분석**:
  - 계절별 패턴 (여름/겨울 고장률 차이)
  - 다음 정비 예상일
  - 위험도 분류 (LOW/MED/HIGH)
  - 비용 TOP 5 (수리 비용 누적 상위)
- **위치**: [features/equipment/maintenance_predictor.py](../../features/equipment/) (12KB)

### F-2-10. 에러 발생 이력 DB (v3.4 신규)
| 항목 | 사양 |
|---|---|
| **건수** | **685건** |
| **심각도** | LOW (10분) / MEDIUM (30분) / HIGH (2시간) / CRITICAL (8시간) |
| **복구 시간** | 심각도별 차등 |
| **빈도 가중치** | 자주 발생한 에러 → 검색 결과 상위 |
| **위치** | [features/equipment/error_history_db.py](../../features/equipment/) |

### F-2-11. 점검 체크리스트 (v3.0)
| 장비 | 주기 | 템플릿 수 |
|---|---|:--:|
| 프레스 | 일/주/월 | 3 |
| 용접 | 일/주/월 | 3 |
| CNC | 일/주/월 | 3 |
| **합계** | | **9** |

체크 결과는 `inspection_logs` 테이블에 저장 + 미달 시 알림.
위치: [features/equipment/inspection_db.py](../../features/equipment/)

### F-2-12. OVERVIEW 통합 대시보드 (v3.1)
**5하위탭** (v3.4):
| 탭 | 콘텐츠 |
|---|---|
| **설비 개요** | 핵심 메트릭 5종 + 7장비 카드 |
| **긴급 조치** | 진행 중 알람 + 우선순위 |
| **장비 유형** | 7장비별 상태 + ML 경고 |
| **예측 정비** | MTBF + 다음 정비 예측 + 비용 TOP 5 |
| **ML 엔진** | 7종 ML 모델 상태 |

### F-2-13. 매뉴얼 RAG (v3.0)
- **데이터**: [data/equipment/manuals/](../../data/equipment/) (PDF 인덱싱)
- **3하위탭**:
  - 에러코드 (검색 + 필터)
  - 증상 가이드 (39 동의어 + 카테고리)
  - AI 질의 (LLM + RAG)
- **위치**: [features/equipment/manual_rag.py](../../features/equipment/)

### F-2-14. 부서 기반 접근 제어 (v3.3)
**허용 14개 부서**:
- 생산기술팀, 품질보증팀, 정비팀, 금형팀, 프레스팀, 용접팀, 도장팀, 검사팀, 환경안전팀, 사출팀, CNC팀, 컨베이어팀, 자재팀, 시스템 관리자

위 외 부서는 메뉴 숨김 + 페이지 진입 방어 코드.

### F-2-15. 증상 카테고리 드롭박스 (v3.4)
- 7장비 × 약 6 카테고리 = **40 카테고리**
- 예: 프레스 → 이음 / 진동 / 압력 저하 / 성형 불량 / 누유 / 전기 등
- 사용자가 카테고리 선택 → ML 검색 자동 필터

## F-3. 사용자 흐름

```
[로그인 (생산기술팀)]
    ↓
[사이드바: 설비/공정 AI] (부서 권한 통과)
    ↓
[3탭: OVERVIEW / 매뉴얼 검색 / 점검 이력]
    ↓
[OVERVIEW → 5하위탭]
    ↓
[설비 개요 탭]
  ├─ 핵심 메트릭: 가동률 92% / Cpk 평균 1.42 / 알람 3건 / MTBF 720h / 정비 임박 2대
  ├─ 7장비 카드: 프레스 ●정상 / 용접 ●경고 / CNC ●정상 ...
  └─ ML 엔진 7종 상태
    ↓
[ML 엔진 탭]
  ├─ TF-IDF Error Search ●ON
  ├─ Isolation Forest SPC ●ON
  ├─ XGBoost Mold ●ON
  ├─ Markov Failure ●ON
  ├─ Doc Quality ●ON
  ├─ Reg Risk ●ON
  └─ Intent Classifier ●ON
    ↓
[SPC 분석 탭 (서브)]
  ├─ 5공정 건강 대시보드
  ├─ Plotly 관리도 — Nelson 위반 음영 + 풍선
  ├─ Cpk 1.38 → 1.24 하락 예측 (Isolation Forest)
  └─ [데이터 관리 expander → CSV 업로드 / 샘플 재생성]
    ↓
[에러 검색 탭 (서브)]
  ├─ 입력: "프레스에서 이상한 소리"
  ├─ 카테고리 드롭박스: 진동 ▼
  ├─ ML TF-IDF + 동의어 79개 → 5건 매칭
  ├─ Top 결과: E-101 베어링 마모 (코사인 0.87)
  ├─ 이력 DB: 지난 12개월 24건 발생, 평균 복구 35분
  ├─ Markov 후속 예측: → E-205 윤활 부족 (0.62) → E-310 모터 과열 (0.31)
  └─ 👍/👎 피드백
    ↓
[금형 탭 (서브)]
  └─ 25개 금형 카드 — 잔여수명 게이지 + 리스크
    ↓
[수리 이력 탭]
  ├─ 240건 이력 + 비용 TOP 5
  └─ 다음 정비 예상일 (MTBF)
```

## F-4. 데이터 자산

| 항목 | 위치 | 규모 |
|---|---|---|
| 에러코드 DB | [data/equipment/error_codes.db](../../data/equipment/) | **201건 / 7장비** |
| 에러 발생 이력 | [data/equipment/error_history.db](../../data/equipment/) | **685건** |
| 금형 DB | [data/equipment/mold_lifecycle.db](../../data/equipment/) | **25건** |
| 점검 템플릿 | [data/equipment/inspection.db](../../data/equipment/) | **9 (3장비×3주기)** |
| 도면 DB | [data/equipment/drawings.db](../../data/equipment/) | 15건 (v3.3 UI 삭제, 코드 잔류) |
| SPC 합성 시계열 | [data/spc_ml/](../../data/) | **10,000건 / 5공정** |
| SPC 샘플 CSV | [data/spc_samples/](../../data/) | 5공정 |
| 금형 학습 데이터 | [data/mold_ml/](../../data/) | **500건** |
| Markov 시퀀스 | [data/markov_ml/](../../data/) | 시퀀스 데이터 |
| 매뉴얼 PDF | [data/equipment/manuals/](../../data/equipment/) | (실제 매뉴얼 인덱싱 필요) |

## F-5. 백엔드 API
현재 Streamlit이 직접 호출하는 구조 — React 마이그레이션 시 다음 API 추가 필요:
- `GET /api/equipment/dashboard` — OVERVIEW 메트릭
- `POST /api/equipment/error-search` — TF-IDF 에러 검색
- `GET /api/equipment/spc/{process}` — Nelson Rule 분석 결과
- `GET /api/equipment/mold/{mold_id}` — XGBoost 잔여수명
- `POST /api/equipment/markov/predict` — 연쇄 고장 예측
- `GET /api/equipment/maintenance/mtbf` — MTBF 분석
- `POST /api/equipment/spc/upload` — CSV 업로드
- `POST /api/equipment/spc/regenerate` — 샘플 재생성

## F-6. 화면 구성

```
┌──────────────────────────────────────────────────┐
│ 설비/공정 AI (EQUIPMENT & PROCESS AI)            │
├──────────────────────────────────────────────────┤
│ [OVERVIEW] [매뉴얼 검색] [점검 이력]             │
├──────────────────────────────────────────────────┤
│ [설비개요][긴급조치][장비유형][예측정비][ML엔진]  │
├──────────────────────────────────────────────────┤
│ ─── 핵심 메트릭 ─────────────                      │
│ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌──┐│
│ │ 92%    │ │ 1.42   │ │ 3 건   │ │ 720h   │ │2 ││
│ │ 가동률 │ │ Cpk평균│ │ 알람   │ │ MTBF   │ │정비││
│ └────────┘ └────────┘ └────────┘ └────────┘ └──┘│
│                                                  │
│ ─── 5공정 건강 ───────────                          │
│ CCH    ● 정상   Cpk 1.51   위반 0                │
│ OBC    ● 경고   Cpk 1.18   위반 2 (Rule 2)       │
│ 범퍼빔 ● 위험   Cpk 0.89   위반 5 (Rule 1,2,5)   │
│ 도어   ● 정상   Cpk 1.62   위반 0                │
│ 볼시트 ● 정상   Cpk 1.55   위반 1 (Rule 6)       │
│                                                  │
│ ─── SPC 관리도 (Plotly) ─────                      │
│ [차트: UCL/CL/LCL + 데이터점 + Nelson 위반 풍선]  │
│                                                  │
│ ─── ML 엔진 상태 ─────────                          │
│ TF-IDF Error      ● ON   p99 38ms                │
│ Isolation Forest  ● ON   p99 87ms                │
│ XGBoost Mold      ● ON   p99 42ms                │
│ Markov Failure    ● ON   p99 24ms                │
│ ...                                              │
│                                                  │
│ ▼ 데이터 관리                                    │
│ [CSV 업로드] [샘플 재생성: 1000샘플 시드 42]     │
└──────────────────────────────────────────────────┘
```

---

# 공통 기반 기능

## G-1. LLM 통합 (Ollama)

### G-1-1. 모델 프로필 5패밀리 11모델 (v3.5 정리)
| 패밀리 | 모델 | 용량 | 용도 |
|---|---|:--:|---|
| **Embedding** | bge-m3:latest | 1.1GB | RAG 임베딩 (필수) |
| **Qwen 3.5** | qwen3.5:9b/latest | 6.1GB | 기본 LLM |
| | qwen3.5:4b | 3.2GB | 경량 |
| **EXAONE** | exaone3.5:latest | 4.4GB | 한국어 특화 |
| | exaone-deep:latest | 4.4GB | 추론 강화 |
| **Gemma 4** | gemma4:latest | 8.9GB | 균형 + 비전 |
| | gemma4:e2b | 6.7GB | 경량 비전 |
| | gemma4:26b | 16.8GB | 대형 비전 |
| **GPT-OSS** | gpt-oss:20b | 12.8GB | 고품질 |
| **Nemotron** | nemotron-cascade-2 | 22.6GB | 향후 서버 대비 |
| **합계** | 11개 모델 | **93.2GB** | (이전 26개에서 68GB 절약) |

### G-1-2. 자동 모델 선택
| 기능 | 우선 모델 | 폴백 |
|---|---|---|
| onboarding (대화) | qwen3.5:9b | exaone3.5 → gemma4 |
| draft (문서) | qwen3.5:9b | exaone3.5 |
| search (요약) | qwen3.5:4b | qwen3.5:9b |
| vision | gemma4:latest | gemma4:e2b |

위치: [core/llm_client.py](../../core/) `auto_select_model()` + `_PREFERRED_FALLBACKS`

## G-2. 벡터 DB (ChromaDB)

| 컬렉션 | 콘텐츠 | 임베딩 |
|---|---|---|
| `ajin_documents` | 사내 문서 (8D, ECN, PPAP 등) | BGE-M3 |
| `employee_profiles` | 사원 시맨틱 프로필 | BGE-M3 |
| `draft_fewshot_samples` | 문서 작성 few-shot 예시 (584건) | BGE-M3 |
| `glossary` | 용어집 297항목 | BGE-M3 |
| `equipment_manuals` | 설비 매뉴얼 (예정) | BGE-M3 |

위치: [vectorstore/](../../vectorstore/) `chroma.sqlite3` 5.4MB + 6 collection

## G-3. 보안 인프라

### G-3-1. 백엔드 미들웨어 (v3.0+)
| 미들웨어 | 기능 |
|---|---|
| **SecurityHeadersMiddleware** | X-Content-Type-Options / X-Frame-Options DENY / X-XSS-Protection / Referrer-Policy / Cache-Control / Permissions-Policy |
| **RateLimitMiddleware** | 일반 60회/분 / 로그인 10회/분 (IP 기반) |
| **CORSMiddleware** | CORS_ORIGINS 화이트리스트 |
| **AuthMiddleware** | JWT 검증 + 부서 컨텍스트 주입 |

### G-3-2. 입력 살균 (sanitize_llm_input)
- LLM 프롬프트 인젝션 방어
- 길이 제한 (5,000자)
- 위험 패턴 제거 (`<script>`, `eval()`, 경로 순회)
- 위치: [core/security.py](../../core/)

### G-3-3. 감사 로그
- 모든 인증·문서 생성·검색 호출 기록
- 위치: [data/audit.db](../../data/), [backend/auth_middleware.py](../../backend/) `log_api_access()`

## G-4. 외부 노출 (현재 ngrok)

### G-4-1. 현재 구조
- **Streamlit**: `localhost:8501` (또는 `8502`)
- **FastAPI**: `localhost:8000` (백엔드)
- **외부 노출**: ngrok 터널링 (별도 실행 — 코드/설정에 통합되지 않음)
- **사이드바 표시**: "ON-PREMISE" 환경

### G-4-2. CORS 화이트리스트
[backend/config.py](../../backend/config.py):
```python
CORS_ORIGINS = [
    "http://localhost:8502",
    "http://localhost:8501",
    "http://127.0.0.1:8502",
    "http://127.0.0.1:8501",
]
```
> Firebase Hosting 배포 시 `https://<project>.web.app` 추가 필수.

---

# 기능 간 교차 네비게이션 (Feature Bridge)

## H-1. 개요
[core/feature_bridge.py](../../core/) — 기능 간 컨텍스트 이동 + 자동 입력.

## H-2. 매핑 표
| 출발 | 도착 | 트리거 | 자동 입력 |
|---|---|---|---|
| A 인원 검색 | B 문서 작성 | 카드 "이메일 작성" | 수신자 = 사원 이메일 |
| A 인원 검색 | B 문서 작성 | 카드 "문서 작성" | 수신자 = 사원 |
| C AI 도우미 | A 인원 검색 | "김민수 부장 어디?" | 검색어 = 이름 |
| C AI 도우미 | F 설비 AI | "에러코드 E001" | 코드 = E001 |
| C AI 도우미 | D 법규 모니터링 | "REACH 규제" | 시나리오 = REACH |
| D 영향 네트워크 | F 설비 AI | 노드 클릭 | 시설 컨텍스트 |
| F 에러 검색 | C AI 도우미 | "이 에러 자세히" | 질의 = 에러 설명 |

## H-3. 권한 체크 (v3.3)
모든 Feature Bridge 호출은 도착 페이지의 RBAC + 부서 권한 사전 검증.
- `is_menu_visible(slug, dept, role)` 호출
- 미통과 시 안내 메시지 + 이동 차단

---

# 부록

## 부록 A. 기능별 라인 수 통계

| 기능 | 페이지 (UI) | 모듈 (features) | 합계 추정 |
|---|---:|---:|---:|
| A. 인원 검색 | 690 | ~3,000 | ~3,690 |
| B. 문서 작성 | 940 + 608 | ~5,500 | ~7,048 |
| C. AI 도우미 | 1,896 | ~3,500 | ~5,396 |
| D. 법규 모니터링 | 2,144 | ~12,000 (9 크롤러 합산) | ~14,144 |
| E. 인사 관리 | 1,314 | ~3,500 (admin + auth) | ~4,814 |
| F. 설비/공정 AI | 1,628 | ~5,500 | ~7,128 |
| **합계** | **9,220** | **~33,000** | **~42,220줄** |

## 부록 B. 6대 기능 핵심 차별 포인트 (대회 어필 자료)

| # | 기능 | 가장 강력한 차별점 |
|:--:|---|---|
| **A** | 인원 검색 | ML 의도 분류 5ms — LLM 없이 즉답 (LLM 폴백 90% 감소) |
| **B** | 문서 작성 | Few-shot RAG 584건 — "아진 톤" 자동 생성 |
| **C** | AI 도우미 | 협업 시나리오 5종 — LLM 없이 즉시 응답하는 맞춤형 가치 |
| **D** | 법규 모니터링 | 관세 시뮬레이터 — "트럼프 25%" 실시간 400억 원 영향 시각화 |
| **E** | 인사 관리 | RBAC 6단계 + 28개 세부 권한 + 부서 기반 메뉴 가시화 |
| **F** | 설비 AI | **실동작 ML 4종** + Nelson 8 Rules — "PPT AI"가 아닌 진짜 분석 시스템 |

## 부록 C. 본선 데모 시나리오 추천 (15분 기준)

| 분 | 기능 | 시나리오 |
|:--:|:--:|---|
| 0~2 | (도입) | "649명 1차 협력사의 5대 도전 과제" |
| 2~4 | A | 자연어 검색 "QA 차장" → 0.3초 응답 + 가시성 마스킹 |
| 4~7 | B | "현대차 SQ팀에 PPAP 제출 안내" → Few-shot 자동 생성 + 품질 87점 평가 + 7포맷 다운로드 |
| 7~10 | C | 신입 시점 "프레스 트라이 SOP" → 8단계 가이드 + 퀴즈 → 오답 재학습 |
| 10~12 | D | 산안법 안전거리 시나리오 시뮬레이션 + 관세 슬라이더 25% → 400억 원 |
| 12~14 | F | SPC Nelson 위반 음영 + 에러 검색 "이상한 소리" → 베어링 마모 + 연쇄 예측 |
| 14~15 | E | 보안 감사 + ROI 산출 (월 950만 원 절감) |

## 부록 D. 우선 보강 항목 (V3.4 점검 기준)

| 우선순위 | 항목 | 작업 |
|:--:|---|---|
| **높음** | 테스트 계정 33명 시딩 | `core/auth/database.py` 추가 21명 |
| **높음** | Few-shot RAG 데이터 검증 | `data/documents/` 인덱싱 동작 확인 |
| **중간** | 매뉴얼 PDF 인덱싱 | `data/equipment/manuals/` 샘플 1~2건 추가 |
| **낮음** | 도면 검색 잔류 코드 정리 | `features/equipment/drawing_search.py` 삭제/주석 |

---

## 변경 이력

| 버전 | 날짜 | 변경 |
|---|---|---|
| **1.0** | 2026-04-26 | 초안 작성 — v3.5 기준 6대 기능 + 공통 기반 + Feature Bridge 전면 문서화 |

---

**문서 작성**: Claude (Anthropic)
**검수 필요**:
- 부록 A의 라인 수 추정치는 실제 grep -r 으로 정확히 확인 필요
- 부록 D의 보강 항목은 본선 데모 전 우선순위에 따라 처리
- React 마이그레이션 시 백엔드 API 갭 분석 필요 ([WEB_DESIGN_SPECIFICATION.md](../design/WEB_DESIGN_SPECIFICATION.md) 참조)

**관련 문서**:
- [WEB_DESIGN_SPECIFICATION.md](../design/WEB_DESIGN_SPECIFICATION.md) — 디자인 시스템 사양
- [README.md](../../README.md) — 전체 프로젝트 개요
- [V3.5_UPDATE_REPORT.md](../reports/V3.5_UPDATE_REPORT.md) — 최신 업데이트
- [V3.4_FEATURE_REVIEW.md](../reports/V3.4_FEATURE_REVIEW.md) — 기능 점검 보고서
