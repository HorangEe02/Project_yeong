# Day 8 — B 문서 검색/작성 (Document Drafting · Module B)

> **작성일**: 2026-04-27 (Day 5++.4 채팅 폴리싱 완료 직후)
> **선행**: Day 4 채팅 + Day 5 SOP/시나리오/다운로드 + Day 5+ Firebase Auth + Day 5++ HUD 폴리싱 / 백엔드 LLM 라우터 30 unit test PASS / `features/draft/*` 9 모듈 (~3,500줄) 보존
> **대상**: `B-2-1 ~ B-2-11` 사양 (FEATURE L278~363) — Few-shot RAG, 13 문서 유형, 7포맷 다운로드, 품질 평가, CC 추천, 버전 diff, 3탭(내부/외부/이력)
> **목표 시간**: 2.5~3시간 (분할 가능)
> **본선까지**: 13 작업일 남음

---

## 목차

1. [목적 + 요구사항](#1-목적--요구사항)
2. [기존 자산 인벤토리](#2-기존-자산-인벤토리)
3. [아키텍처](#3-아키텍처)
4. [3탭 UI — 내부/외부/이력](#4-3탭-ui--내부외부이력)
5. [13 문서 유형 + 어조 selector](#5-13-문서-유형--어조-selector)
6. [Few-shot RAG + SSE 스트리밍 생성](#6-few-shot-rag--sse-스트리밍-생성)
7. [품질 평가 5기준 카드 (B-2-4)](#7-품질-평가-5기준-카드-b-2-4)
8. [CC 자동 추천 칩 (B-2-6)](#8-cc-자동-추천-칩-b-2-6)
9. [버전 비교 diff (B-2-5)](#9-버전-비교-diff-b-2-5)
10. [7포맷 다운로드 (B-2-8)](#10-7포맷-다운로드-b-2-8)
11. [Firestore `documents` + Storage 통합](#11-firestore-documents--storage-통합)
12. [파일 구조](#12-파일-구조)
13. [단계 분할 — Phase 1~4](#13-단계-분할--phase-14)
14. [검증 체크리스트](#14-검증-체크리스트)
15. [위험 + 완화](#15-위험--완화)
16. [Day 8 비스코프](#16-day-8-비스코프)
17. [시간 분배표](#17-시간-분배표)
18. [사용자 결정 대기](#18-사용자-결정-대기)

---

## 1. 목적 + 요구사항

### 1-1. 목표
백엔드 `features/draft/*` 9 모듈을 React UI로 노출 + Firebase 풀스택 통합. 본선 평가 #3 (Firebase 풀스택) 강화 + #1 (LLM 활용) 보강.

### 1-2. 비즈니스 요구사항

| # | 요구사항 | 근거 |
|:--:|---|---|
| 1 | 3탭 (내부 / 외부 / 이력) | B-2-10, Day 8 일정 |
| 2 | 13 문서 유형 selector | B-2-2 |
| 3 | 어조 selector (formal/standard/friendly 등) | B 사양 |
| 4 | Few-shot RAG → SSE 토큰 단위 스트리밍 | B-2-1 + Day 4 useSSE |
| 5 | 품질 평가 5기준 카드 | B-2-4 |
| 6 | CC 자동 추천 칩 | B-2-6 |
| 7 | 버전 diff (생성 결과 vs 사용자 편집) | B-2-5 |
| 8 | 7포맷 다운로드 (DOCX/ODT/PDF/XLSX/CSV/TXT/클립보드) | B-2-8, Day 8 |
| 9 | Firestore `documents/{user_id}/{doc_id}` 영구화 | Day 8 |
| 10 | Storage `/pdfs/drafts/{user_id}/{doc_id}.{ext}` 백업 | Day 8 |
| 11 | 이력 탭 — 최근 N개 문서 + Firestore 로드 | Day 8 |

### 1-3. 비기능 요구사항

| 항목 | 목표 |
|---|---|
| 첫 토큰 (TTFT) | <800ms (LLM 라우터 `draft` 모드 — Ollama qwen3.5:9b 1순위 사내 보안) |
| 품질 평가 응답 | <500ms (백엔드 doc_quality_scorer 호출, mock 가능) |
| CC 추천 응답 | <300ms (백엔드 cc_recommender 호출) |
| 7포맷 변환 | <2s (DOCX/PDF 가장 느림) |
| Firestore 쓰기 | <500ms (fire-and-forget) |
| Storage 업로드 | <3s (PDF 200KB 기준) |
| TS strict | 0 오류 |

### 1-4. 비범위 (Day 8)
- ❌ 양식 카탈로그 11종 자동 다운로드 화면 (B-2-7 → **Day 12 폴리싱**)
- ❌ 마크다운 → CSV/XLSX 깊은 변환 (B-2-9 → 단순 변환만, 깊은 로직은 백엔드 `docx_exporter.py` 활용)
- ❌ Jinja2 매핑 수정 UI (B-2-11 → 비범위 또는 Day 13)
- ❌ 가중치 BM25 검색 UI (B-2-3 → 백엔드 자동 사용만, UI X)
- ❌ 양식 미리보기 모달 (선택 — Day 12)
- ❌ 협업 코멘트/리뷰 (비범위)

---

## 2. 기존 자산 인벤토리

### 2-1. `features/draft/*` (~3,500줄 추정)

| 모듈 | 역할 | Day 8 활용 |
|---|---|---|
| `fewshot_rag.py` | Few-shot 검색 + RAG 컨텍스트 | ⭐ 백엔드 그대로 사용 |
| `classifier.py` | 문서 유형 분류 | ⭐ 백엔드 (auto-detect) |
| `doc_type_config.py` | 13 문서 유형 메타 (이름/설명/필수 필드) | ⭐ 신규 GET 엔드포인트로 노출 |
| `cc_recommender.py` | CC 자동 추천 (수신자/부서 → 자동 CC 후보) | ⭐ 신규 POST `/cc/recommend` |
| `doc_quality_scorer.py` | 품질 평가 5기준 점수화 | ⭐ 신규 POST `/quality/score` |
| `doc_diff.py` | 버전 diff (texthash + line-based) | ⭐ 신규 POST `/diff` |
| `docx_exporter.py` | DOCX/PDF/XLSX 변환 | ⭐ 기존 `/export` 엔드포인트 활용 |
| `draft_session.py` | 세션 관리 (conversation history) | ⭐ frontend useChatStore 같이 활용 |

### 2-2. `backend/routers/draft.py` 기존 엔드포인트

| 메서드 | 경로 | 역할 |
|---|---|---|
| POST | `/api/draft/generate` | LLM 호출 (단일 응답) |
| POST | `/api/draft/generate-pipeline` | Few-shot RAG → 분류 → 생성 → 품질 → diff 파이프라인 |
| POST | `/api/draft/export` | 7포맷 변환 (DOCX/PDF/XLSX/...) |
| GET | `/api/draft/templates` | 양식 11종 목록 |

### 2-3. Day 8 신규 엔드포인트 (Phase 1)

| 메서드 | 경로 | 역할 |
|---|---|---|
| GET | `/api/draft/doc-types` | 13 문서 유형 메타 |
| POST | `/api/draft/cc/recommend` | CC 자동 추천 |
| POST | `/api/draft/quality/score` | 품질 평가 5기준 |
| POST | `/api/draft/diff` | 버전 diff |
| POST | `/api/draft/stream` | SSE 스트리밍 (Day 4 패턴) |

기존 `/generate`, `/generate-pipeline`은 비스트리밍 → 신규 `/stream` 으로 SSE 통합 (LLM 라우터 `draft` 모드).

---

## 3. 아키텍처

```
┌──────────────────────────────────────────────────────────────────┐
│  React /draft 페이지 (HUD Command Center 패턴)                   │
│                                                                   │
│  TopBar + LeftSidebar + ChatHeader (모듈 표시)                   │
│                                                                   │
│  메인 영역:                                                       │
│   ├── DraftHeader: SESSION + LLM/Firebase 상태 + 모델 selectbox  │
│   ├── DraftPageTabs: [내부 · INTERNAL] [외부 · EXTERNAL] [이력]  │
│   │                                                                │
│   │  내부/외부 탭:                                                 │
│   │   ├── 좌 패널 (300px):                                         │
│   │   │   - DocTypeSelector (13 종)                               │
│   │   │   - ToneSelector (4~5 톤)                                 │
│   │   │   - 메타 입력 폼 (수신자/제목/내용 요청)                  │
│   │   │   - CC 추천 칩                                            │
│   │   │   - [생성 ▶] CTA                                          │
│   │   ├── 중앙 (flex):                                             │
│   │   │   - DraftPreview (생성 결과 마크다운)                     │
│   │   │   - SSE 스트리밍 인디케이터                               │
│   │   │   - DownloadActions (7포맷)                               │
│   │   ├── 우 (280px) RightPanel mode='analytics' (재사용)         │
│   │   ├── DiffViewer (모달) — 버전 비교                           │
│   │   └── QualityCard — 품질 평가 5기준                           │
│   │                                                                │
│   │  이력 탭:                                                      │
│   │   - DraftHistoryList (Firestore documents/{uid}/...)          │
│   │   - 클릭 시 미리보기 + 다운로드 + 재편집                       │
└────────────┬─────────────────────────────────────────────────────┘
             │
             │ POST /api/draft/{stream,cc/recommend,quality/score,diff,export,doc-types}
             ▼
┌──────────────────────────────────────────────────────────────────┐
│  FastAPI :8000  backend/routers/draft.py (갱신)                  │
│   ├── /stream — LLMRouter.stream(mode=DRAFT) + Few-shot RAG      │
│   ├── /cc/recommend — cc_recommender.py 호출                     │
│   ├── /quality/score — doc_quality_scorer.py 호출                │
│   ├── /diff — doc_diff.py 호출                                   │
│   ├── /export — docx_exporter.py (7포맷)                         │
│   ├── /doc-types — doc_type_config.py 메타                       │
│   └── /generate-pipeline (기존 — 단일 응답 fallback)              │
└────────────┬─────────────────────────────────────────────────────┘
             │
             ▼
┌──────────────────────────────────────────────────────────────────┐
│  Firebase                                                         │
│  ├── Firestore: documents/{user_uid}/{doc_id}                    │
│  │   { meta, content, quality_score, version_history, status }   │
│  ├── Storage:   /pdfs/drafts/{user_uid}/{doc_id}.{ext}           │
│  └── Firestore의 meta.storageUrls 에 Storage URL 저장             │
└──────────────────────────────────────────────────────────────────┘
```

---

## 4. 3탭 UI — 내부/외부/이력

### 4-1. 탭 정의

| 탭 | id | 콘텐츠 | 사용처 |
|---|---|---|---|
| **내부 · INTERNAL** | `internal` | 사내 보고서/품의서/회의록 등 (사내 어조, RAG=사내 SOP+용어집) | 사원 일상 |
| **외부 · EXTERNAL** | `external` | 고객사 공문 / 클레임 답변 / PPAP 제출서 (외부 격식 어조) | 협력사·완성차 대응 |
| **이력 · HISTORY** | `history` | Firestore 영구화된 최근 N개 문서 | 재편집/재다운로드 |

### 4-2. 디폴트 탭 + 영구화

- 디폴트: `internal` (사용자 결정 #2)
- `useUIStore.draftPageTab: 'internal' | 'external' | 'history'` + persist

### 4-3. 내부 vs 외부 차이

| 항목 | 내부 | 외부 |
|---|---|---|
| 어조 selector 디폴트 | `formal_internal` | `formal_external` |
| RAG 컨텍스트 | SOP + 용어집 + 사내 부서 가이드 | 표준 양식 + 고객사 클레임 사례 |
| 13 doc-types 필터 | 보고서/품의서/회의록/공지 등 7종 | 클레임 답변/PPAP/CC/제안서 등 6종 |

doc_type_config.py 의 `category` 필드로 자동 필터.

---

## 5. 13 문서 유형 + 어조 selector

### 5-1. 13 문서 유형 (B-2-2)

`doc_type_config.py` 에 정의된 메타 (이름/설명/필수 필드/카테고리). 정확한 13종은 백엔드 모듈 직접 호출로 노출:

```python
# /api/draft/doc-types 응답
[
  { id: "report",        category: "internal", name_ko: "보고서",        required_fields: ["title", "summary", "details"] },
  { id: "approval",      category: "internal", name_ko: "품의서",        required_fields: [...] },
  { id: "meeting_min",   category: "internal", name_ko: "회의록",        required_fields: [...] },
  { id: "notice",        category: "internal", name_ko: "공지",          required_fields: [...] },
  ...
  { id: "claim_reply",   category: "external", name_ko: "클레임 답변",   required_fields: [...] },
  { id: "ppap_submit",   category: "external", name_ko: "PPAP 제출서",   required_fields: [...] },
  ...
]
```

frontend `<DocTypeSelector category="internal" />` 가 카테고리별 7~6종 chip 표시.

### 5-2. 어조 selector (4~5 톤)

| id | 한 | 영 |
|---|---|---|
| `formal_internal` | 격식 (사내) | Formal (Internal) |
| `formal_external` | 격식 (외부) | Formal (External) |
| `standard` | 표준 | Standard |
| `friendly` | 친근 | Friendly |
| `concise` | 간결 | Concise |

selectbox 또는 segmented control. LLM 프롬프트에 `tone={tone_id}` 주입.

---

## 6. Few-shot RAG + SSE 스트리밍 생성

### 6-1. 흐름

```
1. 사용자 입력: doc_type, tone, meta(수신자/제목/내용 요청)
2. 백엔드 /api/draft/stream POST → SSE 응답
   a. fewshot_rag.py 가 ChromaDB 에서 Top-K 사례 retrieve
   b. classifier.py 가 doc_type 검증 (mismatch 시 보정 제안)
   c. LLMRouter.stream(mode=DRAFT, prompt=...) 토큰 스트리밍
3. Frontend useSSE 훅 (Day 4) 재사용 → DraftPreview 업데이트
```

### 6-2. 백엔드 신규 엔드포인트 — `POST /api/draft/stream`

```python
@router.post("/stream")
async def draft_stream(req: DraftStreamRequest, user=Depends(get_current_user)):
    # 1) Few-shot RAG
    examples = fewshot_rag.retrieve(req.doc_type, req.meta, top_k=3)
    
    # 2) classifier (선택)
    classified = classifier.classify(req.meta)
    
    # 3) prompt 합성
    prompt = build_draft_prompt(req.doc_type, req.tone, req.meta, examples)
    
    # 4) LLM stream
    async def event_stream():
        async for ev in _llm_router.stream(
            prompt=prompt,
            mode=LLMMode.DRAFT,  # qwen3.5:9b 1순위 (사내 보안)
            history=[],
            force_provider=None,
        ):
            yield {"data": json.dumps(ev, ensure_ascii=False)}
    
    return EventSourceResponse(event_stream())
```

### 6-3. Frontend SSE 처리

```typescript
const sse = useSSE({
  onToken: (chunk) => setDraftContent((prev) => prev + chunk),
  onMetadata: (meta) => setDraftMeta(meta),
  onDone: (final) => {
    runQualityScore();         // 품질 평가 자동 호출
    runCcRecommend();          // CC 추천 자동 호출
    saveDraftToFirestore();    // Firestore 영구화
  },
  onError: (msg) => addToast({ type: 'error', message: msg }),
});

const startDraft = () => sse.start({
  url: '/api/draft/stream',
  body: { doc_type, tone, meta, language: 'ko' },
});
```

---

## 7. 품질 평가 5기준 카드 (B-2-4)

### 7-1. 5기준 (FEATURE_SPEC L304~)

| # | 기준 | 평가 방식 |
|:--:|---|---|
| 1 | **명확성** | 문장 모호 표현 비율 |
| 2 | **완결성** | 필수 섹션 충족 |
| 3 | **격식** | 어조 일관성 + 한자/외래어 비율 |
| 4 | **정확성** | 수치/날짜/명사 일관성 |
| 5 | **간결성** | 중복 표현 + 단어 평균 길이 |

각 0~100점, 평균 종합 점수 + 색상 (90+ 녹색 / 70-89 노랑 / <70 빨강).

### 7-2. 백엔드 — `POST /api/draft/quality/score`

```python
@router.post("/quality/score")
async def quality_score(req: QualityRequest, user=Depends(get_current_user)):
    scores = doc_quality_scorer.score(req.text, doc_type=req.doc_type)
    return {
        "scores": scores,  # {"clarity": 87, "completeness": 92, ...}
        "average": round(sum(scores.values()) / 5, 1),
        "issues": doc_quality_scorer.find_issues(req.text),  # [{section, severity, message}, ...]
    }
```

### 7-3. Frontend `<QualityCard />`

```
┌─ 품질 평가 · QUALITY ─────────┐
│ 종합 87.4 / 100   [● 양호]    │
│ ─                              │
│ 명확성   ████████░░  87        │
│ 완결성   █████████░  92        │
│ 격식     ███████░░░  73        │
│ 정확성   ████████░░  85        │
│ 간결성   ████████░░  88        │
│                                │
│ 이슈 2건:                      │
│  • [경고] 3절: "약간" 모호     │
│  • [정보] 5절: 중복 표현       │
└────────────────────────────────┘
```

신규: `components/draft/QualityCard.tsx` (~120줄), `api/draft.ts` 의 `scoreQuality()`.

---

## 8. CC 자동 추천 칩 (B-2-6)

### 8-1. 추천 로직

`cc_recommender.py` — 수신자 + 부서 + 문서유형 → CC 후보 (사번 + 직책).

### 8-2. 백엔드 — `POST /api/draft/cc/recommend`

```python
@router.post("/cc/recommend")
async def cc_recommend(req: CCRecRequest, user=Depends(get_current_user)):
    candidates = cc_recommender.recommend(
        recipient=req.recipient,
        doc_type=req.doc_type,
        department=user.department,
    )
    return {"candidates": candidates}  # [{employee_id, name, position, score}, ...]
```

### 8-3. Frontend `<CcChips />`

- 수신자 입력 시 자동 호출 (debounce 500ms)
- chip 5개 추천 (점수 순)
- 클릭 시 `selected[]` 추가 → 메타 폼에 반영

신규: `components/draft/CcChips.tsx` (~70줄)

---

## 9. 버전 비교 diff (B-2-5)

### 9-1. 흐름

생성 결과 (v1) → 사용자 편집 (v2) → diff 비교 모달 (v1 vs v2 라인 단위).

### 9-2. 백엔드 — `POST /api/draft/diff`

```python
@router.post("/diff")
async def doc_diff(req: DiffRequest, user=Depends(get_current_user)):
    result = doc_diff.compute(req.old, req.new)
    return {
        "additions": result.additions,
        "deletions": result.deletions,
        "modifications": result.modifications,
        "similarity": result.similarity,
    }
```

### 9-3. Frontend `<DiffViewer />`

- Modal 컴포넌트 (Day 3 자산)
- 두 컬럼: 좌 v1 (편집 전), 우 v2 (편집 후)
- 추가는 녹색, 삭제는 빨강 줄긋기, 수정은 노랑

신규: `components/draft/DiffViewer.tsx` (~120줄)

---

## 10. 7포맷 다운로드 (B-2-8)

### 10-1. 7 포맷

| # | 포맷 | 라이브러리 (백엔드) |
|:--:|---|---|
| 1 | **DOCX** | python-docx |
| 2 | **ODT** | (DOCX → ODT 변환 또는 직접 생성) |
| 3 | **PDF** | fpdf2 또는 reportlab |
| 4 | **XLSX** | openpyxl (마크다운 표 → 시트) |
| 5 | **CSV** | utf-8-sig BOM (Excel 한글) |
| 6 | **TXT** | utf-8 |
| 7 | **클립보드 복사** | Frontend `navigator.clipboard.writeText()` |

### 10-2. 백엔드 `/api/draft/export` (기존)

이미 존재 — Day 8 에서는 ODT/PDF 추가 검증.

### 10-3. Frontend — Day 5 `DownloadActions` 확장

기존 4 포맷 (DOCX/XLSX/CSV/TXT) + ODT/PDF/클립보드 추가 = 7 포맷.

`components/chat/DownloadActions.tsx` 갱신 또는 `components/draft/DraftDownloadActions.tsx` 신규.

권장: **신규** — Day 8 의 7포맷은 chat 의 4포맷보다 풍부, 별도 컴포넌트가 깔끔.

---

## 11. Firestore `documents` + Storage 통합

### 11-1. 데이터 모델

```typescript
// Firestore: documents/{user_uid}/items/{doc_id}
interface DraftDocument {
  id: string;
  user_uid: string;
  doc_type: string;       // 'report' | 'approval' | ...
  tone: string;
  meta: {
    title: string;
    recipient: string;
    cc: string[];
    custom_fields: Record<string, string>;
  };
  content: string;        // 마크다운 본문
  quality?: { scores, average, issues };
  cc_recommended?: { employee_id, name }[];
  versions: { content, _at, source: 'llm' | 'user' }[];
  storage_urls?: {
    docx?: string;
    pdf?: string;
    xlsx?: string;
    // ...
  };
  status: 'draft' | 'completed' | 'archived';
  _at: Timestamp;
}
```

### 11-2. 보안 규칙 (firestore.rules 갱신)

```
match /documents/{userId}/items/{docId} {
  allow read, write: if request.auth.uid == userId;
}
```

이미 deploy 됐다면 (Day 2): `match /documents/{userId}/{docId}` — items 서브컬렉션 변경 시 갱신 필요. 검증.

### 11-3. Storage 경로

```
/pdfs/drafts/{user_uid}/{doc_id}.docx
/pdfs/drafts/{user_uid}/{doc_id}.pdf
/pdfs/drafts/{user_uid}/{doc_id}.xlsx
```

Frontend `api/upload.ts` (Day 5++) 패턴 확장 — 다운로드 응답 받은 후 별도 업로드 또는 백엔드 직접 (옵션 B 유지).

권장 흐름:
1. 사용자 다운로드 클릭 → 백엔드 `/export` 호출
2. 백엔드 → 파일 bytes 반환 + (선택) Storage 업로드 + URL 응답
3. Frontend → 파일 다운로드 (browser blob) + Firestore meta 갱신 (storageUrls)

또는 옵션 B 그대로:
1. 백엔드 `/export` 는 bytes 만 반환
2. Frontend 가 bytes 받아서 → Storage Web SDK 직접 업로드 → URL 받음
3. Frontend 가 다운로드 + Firestore 갱신

옵션 B 권장 (firebase-admin 미도입 정책).

---

## 12. 파일 구조

### 12-1. 신규/갱신 파일

```
ajin-ai-assistant-react/
├── backend/
│   ├── routers/
│   │   └── draft.py                     ⭐ 갱신 (+~200줄: 5 신규 엔드포인트)
│   └── schemas/
│       └── draft.py                     갱신 (+~60줄)
└── frontend/src/
    ├── routes/
    │   └── draft.tsx                    ⭐ 갱신 (19 → ~280)
    ├── components/
    │   └── draft/                       ⭐ 신규 디렉토리
    │       ├── DraftPageTabs.tsx        ⭐ ~80 (3탭 메인)
    │       ├── InternalTab.tsx          ⭐ ~150
    │       ├── ExternalTab.tsx          ⭐ ~120 (InternalTab 재사용)
    │       ├── HistoryTab.tsx           ⭐ ~100
    │       ├── DocTypeSelector.tsx      ⭐ ~80
    │       ├── ToneSelector.tsx         ⭐ ~50
    │       ├── DraftMetaForm.tsx        ⭐ ~100 (수신자/제목/내용)
    │       ├── DraftPreview.tsx         ⭐ ~80 (마크다운 + 편집)
    │       ├── QualityCard.tsx          ⭐ ~120 (5기준 점수)
    │       ├── CcChips.tsx              ⭐ ~70
    │       ├── DiffViewer.tsx           ⭐ ~120 (Modal)
    │       └── DraftDownloadActions.tsx ⭐ ~80 (7포맷)
    ├── api/
    │   ├── draft.ts                     ⭐ 신규 (~150)
    │   └── (기존 onboarding.ts, sop.ts 등)
    ├── store/
    │   ├── draft.ts                     ⭐ 신규 (~120, Zustand)
    │   └── ui.ts                        갱신 (+10, draftPageTab persist)
    ├── lib/
    │   └── firestore-draft.ts           ⭐ 신규 (~80)
    ├── types/
    │   └── draft.ts                     ⭐ 신규 (~60)
    ├── styles/
    │   └── components.css               갱신 (+~200, .draft-* 클래스)
    └── i18n/
        ├── ko/common.json               갱신 (+~40 키)
        └── en/common.json               갱신 (+~40 키)
```

### 12-2. 줄 수 합계

| 카테고리 | 신규 | 갱신 |
|---|---:|---:|
| 백엔드 | — | ~260 |
| Frontend draft 컴포넌트 12개 | ~1,150 | — |
| Frontend api/store/lib/types | ~410 | +10 |
| draft.tsx | — | +260 (placeholder 폐기) |
| styles | — | +200 |
| i18n | — | +80 |
| **합계** | **~1,560** | **~810** |

총 **~2,370줄** (분량 큼 → Phase 분할).

---

## 13. 단계 분할 — Phase 1~4

### Phase 1 — 백엔드 5 신규 엔드포인트 + 검증 (~45분)
- [ ] `backend/schemas/draft.py` 갱신 — 신규 요청/응답 (`DraftStreamRequest`, `CCRecRequest`, `QualityRequest`, `DiffRequest`, `DocTypeListResponse`)
- [ ] `backend/routers/draft.py` 갱신 — 5 신규 엔드포인트:
  - `POST /stream` (SSE 스트리밍)
  - `POST /cc/recommend`
  - `POST /quality/score`
  - `POST /diff`
  - `GET /doc-types`
- [ ] `features/draft/*` import 호환성 검증 (Day 5 의 onboarding 패턴 따름)
- [ ] 기존 `/generate-pipeline` 보존 (fallback)

검증: 5 엔드포인트 OpenAPI 등록 + 직접 curl 테스트

### Phase 2 — Frontend 기본 UI (3탭 + selector + SSE) (~60분)
- [ ] `frontend/src/types/draft.ts` (DraftDocument, DocType, Tone)
- [ ] `frontend/src/store/draft.ts` Zustand (draftPageTab, currentDoc, history)
- [ ] `frontend/src/store/ui.ts` 갱신 — `draftPageTab` persist
- [ ] `frontend/src/api/draft.ts` (5 함수)
- [ ] `frontend/src/components/draft/DraftPageTabs.tsx`
- [ ] `frontend/src/components/draft/InternalTab.tsx` + `ExternalTab.tsx`
- [ ] `frontend/src/components/draft/{DocTypeSelector,ToneSelector,DraftMetaForm,DraftPreview}.tsx`
- [ ] `frontend/src/routes/draft.tsx` 본격 구현 (placeholder 폐기)

검증: TS strict + `/draft` 200 + 3탭 동작 + 생성 클릭 → SSE 토큰 스트리밍

### Phase 3 — 품질/CC/diff/7포맷 (~60분)
- [ ] `frontend/src/components/draft/QualityCard.tsx`
- [ ] `frontend/src/components/draft/CcChips.tsx`
- [ ] `frontend/src/components/draft/DiffViewer.tsx` (Modal)
- [ ] `frontend/src/components/draft/DraftDownloadActions.tsx` (7포맷)
- [ ] 자동 호출 wiring (생성 done 후 quality/cc 자동 호출)

검증: 생성 후 품질 카드 자동 표시 + CC 추천 chip + 다운로드 7포맷

### Phase 4 — Firestore + Storage + 이력 탭 (~30분)
- [ ] `frontend/src/lib/firestore-draft.ts` (saveDraft, loadHistory, deleteDraft)
- [ ] `frontend/src/components/draft/HistoryTab.tsx`
- [ ] 자동 영구화 — 생성 done 시 Firestore 쓰기 + Storage 업로드
- [ ] i18n 한·영 키 40개 추가

검증: Firestore 콘솔에서 `documents/{uid}/items/...` 확인 + Storage `/pdfs/drafts/...` 확인 + 이력 탭에 표시

---

## 14. 검증 체크리스트

### 14-1. 코드
- [ ] TS strict 0 오류 (`tsc -b`)
- [ ] ESLint 0 경고 (신규 파일)
- [ ] pytest `test_llm_router.py` 30/30 PASS 유지
- [ ] 외부 npm 추가 0 (백엔드 `python-docx`, `openpyxl`, `fpdf2` 모두 기존)
- [ ] Day 1~5++ 다른 라우트 손상 0

### 14-2. 기능
- [ ] 13 문서 유형 GET 정상 (카테고리별 필터)
- [ ] 어조 5종 selector 동작
- [ ] 생성 클릭 → SSE 토큰 단위 스트리밍 (LLM 라우터 `draft` 모드)
- [ ] 품질 평가 5기준 카드 자동 표시
- [ ] CC 추천 chips 5개 (수신자 입력 시 debounce)
- [ ] 버전 diff Modal (편집 후 비교)
- [ ] 7포맷 다운로드 모두 동작 (DOCX/ODT/PDF/XLSX/CSV/TXT/클립보드)
- [ ] 클립보드 복사 → `navigator.clipboard.writeText`
- [ ] 이력 탭 → Firestore 최근 N개 로드 + 클릭 시 상세
- [ ] Storage `/pdfs/drafts/{uid}/{doc_id}.{ext}` 업로드

### 14-3. UX
- [ ] HUD Command Center 패턴 일관 (좌·중·우 3-Column)
- [ ] Liquid Glass + 골드 CTA
- [ ] No-emoji 정책 (글리프 ●/○ 사용)
- [ ] 라이트/다크/AUTO 테마
- [ ] 모바일 768/1024 반응형

### 14-4. 본선 시연 추가 가능
- 시연 7: 내부 탭 → "보고서" 선택 → 입력 → SSE 생성 → 품질 87점 + CC 추천 + DOCX 다운로드
- 시연 8: 이력 탭 → 어제 작성 문서 → 재편집 → diff 비교 → PDF 다운로드

---

## 15. 위험 + 완화

| # | 위험 | 영향 | 완화 |
|:--:|---|:--:|---|
| 1 | `features/draft/*` Streamlit st.* 의존 | 🔴 | Day 5 onboarding 패턴 — 먼저 import 시도 + 데이터 함수만 분리 |
| 2 | ODT 변환 라이브러리 부재 | 🟡 | `python-docx` → ODT 변환 또는 비스코프 (DOCX 만) |
| 3 | PDF 한글 폰트 (fpdf2 default) | 🟡 | `fpdf2` 한글 폰트 추가 또는 reportlab 사용 |
| 4 | Few-shot RAG 컨텍스트 토큰 초과 | 🟡 | top_k=3 제한 + LLM 라우터 자동 폴백 |
| 5 | 품질 평가 mock vs 실 점수 | 🟢 | doc_quality_scorer.py 그대로 사용 |
| 6 | CC 추천 정확도 | 🟢 | cc_recommender.py 기존 로직 그대로 |
| 7 | Firestore 쓰기 quota | 🟢 | fire-and-forget |
| 8 | Storage 업로드 5MB 초과 | 🟢 | 압축 또는 split |
| 9 | 7포맷 변환 시간 | 🟡 | UI 로딩 인디케이터 + 병렬 처리 (Promise.all) |
| 10 | 다른 라우트 손상 | 🟡 | tokens.css/components.css 추가만, 기존 클래스 변경 X |

---

## 16. Day 8 비스코프 (Day 9~12)

| # | 항목 | 일정 |
|:--:|---|---|
| 1 | 양식 카탈로그 11종 자동 다운로드 화면 (B-2-7) | Day 12 |
| 2 | 마크다운 → CSV/XLSX 깊은 변환 (B-2-9) | Day 12 |
| 3 | Jinja2 매핑 수정 UI (B-2-11) | 비범위 |
| 4 | 가중치 BM25 검색 UI (B-2-3) | Day 12 |
| 5 | 양식 미리보기 모달 | Day 12 |
| 6 | 협업 코멘트/리뷰 | 비범위 |
| 7 | 자동 저장 (autosave 30초) | Day 12 |
| 8 | 커서 위치 보존 (편집 중 reload) | Day 12 |
| 9 | Cloud Functions — 생성 통계 집계 | Day 14 |
| 10 | 사용자 별 즐겨찾기 양식 | Day 11 |

---

## 17. 시간 분배표 (총 2.5~3h)

| 시간대 | 작업 |
|:--:|---|
| 00:00 ~ 00:10 | features/draft/* 호환성 검증 + 백엔드 `/generate-pipeline` 동작 확인 |
| 00:10 ~ 00:55 | Phase 1 — 백엔드 5 신규 엔드포인트 |
| 00:55 ~ 01:00 | Phase 1 검증 (curl) |
| 01:00 ~ 02:00 | Phase 2 — Frontend 기본 UI (3탭 + selector + SSE) |
| 02:00 ~ 03:00 | Phase 3 — 품질/CC/diff/7포맷 |
| 03:00 ~ 03:30 | Phase 4 — Firestore + Storage + 이력 + i18n |
| 03:30 ~ 03:45 | 통합 검증 + 시연 시나리오 |

---

## 18. 사용자 결정 대기 (실행 직전)

| # | 결정 | 권장 |
|:--:|---|---|
| 1 | **위임 방식** | `executor` (opus) — 분할 (Phase 1~2 + Phase 3~4) 권장 |
| 2 | **디폴트 탭** | `internal` (사내 사용 빈도 ↑) |
| 3 | **ODT 포맷** | DOCX 만 → ODT 비스코프 (시간 절약) 또는 7포맷 모두 |
| 4 | **PDF 한글 폰트** | `Pretendard` 또는 시스템 폰트 (fpdf2 한계 시 reportlab) |
| 5 | **자동 영구화 시점** | 생성 done 직후 fire-and-forget |
| 6 | **이력 탭 N개** | 최근 30개 (Firestore limit) |
| 7 | **품질 카드 자동 호출** | 생성 done 즉시 (또는 사용자 클릭 시) |

권장 디폴트로 가도 무방하면 즉시 위임 가능.

---

## 변경 이력

| 버전 | 날짜 | 변경 |
|---|---|---|
| **1.0** | 2026-04-27 | 초안 — 18 섹션 / 신규 ~1,560 + 갱신 ~810 / Phase 4분할 |

---

**관련 문서**:
- [DAY5_PLAN.md](DAY5_PLAN.md) — Day 5 Phase 1~5 (완료, 패턴 참조)
- [LLM_ROUTER_PLAN.md](LLM_ROUTER_PLAN.md) — 백엔드 라우터 (LLMMode.DRAFT 1순위 ollama qwen3.5:9b)
- [FINAL_17DAY_PLAN.md](FINAL_17DAY_PLAN.md) — Day 8 위치 (L363)
- [FEATURE_SPECIFICATION.md](../features/FEATURE_SPECIFICATION.md) — B-2-1 ~ B-2-11 사양 (L278~363)
- `uiux/AJIN AI Assistant Design System_v2/README.md` — HUD Command Center 패턴
