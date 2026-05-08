# Day 5 — C 도우미 보강 (SOP / 시나리오 / 비전 / 파일 / Firebase 통합)

> **작성일**: 2026-04-27 (Day 4 마감 직후)
> **선행**: Day 4 채팅 UI + SSE 동작 + 듀얼 모드 / 백엔드 LLM 라우터 Phase 1~3 / Streamlit v3.5 features/onboarding/* 12 모듈 (~3,460줄) 자산 보존
> **목표 시간**: 3~4시간 (분할 가능)
> **본선까지**: 13 작업일 남음

---

## 목차

1. [목적 + 요구사항](#1-목적--요구사항)
2. [기존 자산 인벤토리 (재사용 우선)](#2-기존-자산-인벤토리-재사용-우선)
3. [아키텍처 — Day 4 위에 보강](#3-아키텍처--day-4-위에-보강)
4. [SOP 8종 시스템](#4-sop-8종-시스템)
5. [협업 시나리오 5종](#5-협업-시나리오-5종)
6. [업무 모드 액션 라우터 (C-2-7)](#6-업무-모드-액션-라우터-c-2-7)
7. [다운로드 영구화](#7-다운로드-영구화)
8. [피드백 이모지 + RTDB](#8-피드백-이모지--rtdb)
9. [Firestore `chat_history` 영구화](#9-firestore-chat_history-영구화)
10. [비전 이미지 업로드](#10-비전-이미지-업로드)
11. [파일 업로드 + 텍스트 추출](#11-파일-업로드--텍스트-추출)
12. [Firebase Storage 통합](#12-firebase-storage-통합)
13. [모델 비교 selectbox (Day 4 보강)](#13-모델-비교-selectbox-day-4-보강)
14. [파일 구조](#14-파일-구조)
15. [단계 분할 — Phase 1~5](#15-단계-분할--phase-15)
16. [검증 체크리스트](#16-검증-체크리스트)
17. [위험 + 완화](#17-위험--완화)
18. [Day 5 비스코프 (Day 11~13 이후)](#18-day-5-비스코프-day-1113-이후)
19. [시간 분배표](#19-시간-분배표)

---

## 1. 목적 + 요구사항

### 1-1. 목표
Day 4 의 기본 채팅 UI 위에 본선 시연 차별점을 얹기:
- **본선 평가 핵심 #2** (실동작 ML 7종 — 부분) — SOP/시나리오 즉시 응답 (LLM 호출 0회)
- **본선 평가 핵심 #3** (Firebase 풀스택) — Firestore + RTDB + Storage 모두 사용
- C-2-3, 4, 5, 7 사양 (FEATURE_SPECIFICATION.md L498~550) 구현

### 1-2. 비즈니스 요구사항

| # | 요구사항 | 근거 |
|:--:|---|---|
| 1 | SOP 8종 단계별 가이드 (체크리스트 + 진행률 + 퀴즈) | C-2-3 |
| 2 | 협업 시나리오 5종 트리거 (LLM 호출 없이 즉시) | C-2-4 |
| 3 | 업무 모드 액션 라우터 (에러코드/인원/8D/SPC/REACH) | C-2-7 |
| 4 | 다운로드 영구화 (DOCX/XLSX/CSV/TXT) | Day 5 일정 |
| 5 | 피드백 이모지 (👍/👎) → RTDB 푸시 | Day 5 일정 |
| 6 | 메시지 종료 시 Firestore 영구화 | Day 5 일정 |
| 7 | 비전 이미지 업로드 (`/chat/vision`) | C-2-1 + Day 5 |
| 8 | 파일 업로드 20+ 확장자 (`/upload`) | Day 5 일정 |
| 9 | Firebase Storage 업로드 | Day 5 일정 |
| 10 | 모델 비교 selectbox (Day 4 보강) | 사용자 정책 — "오픈 LLM 다양성 시연" |

### 1-3. 비기능 요구사항

| 항목 | 목표 |
|---|---|
| SOP/시나리오 응답 시간 | <50ms (LLM 호출 0회) |
| 비전 이미지 업로드 | <2MB, JPEG/PNG, 자동 리사이즈 |
| 파일 업로드 | <10MB, 20+ 확장자 (PDF/DOCX/XLSX/PPTX/HWPX/TXT/CSV/JSON 등) |
| Firestore 쓰기 latency | <500ms (메시지 종료 후 비동기) |
| Storage 업로드 | <3s (2MB 이미지) |
| TS strict 컴파일 | 0 오류 |

### 1-4. 비범위 (Day 5)
- ❌ 부서 라우터 31종 UI (백엔드 통합만, **Day 11 인사 관리** 또는 **Day 12 폴리싱**)
- ❌ 용어집 매처 297항목 UI 하이라이트 (백엔드 자동 주입만, **Day 12**)
- ❌ 대화 요약 메모리 UI 노출 (백엔드 자동만, **Day 13**)
- ❌ 퀴즈 자동 생성 단독 화면 (SOP 학습 종료 시 inline 만, 단독 라우트 X)
- ❌ TF-IDF intent 분류기 (**Day 13**)
- ❌ 능동 엔진 (proactive_engine.py — Day 13 또는 비범위)

---

## 2. 기존 자산 인벤토리 (재사용 우선)

### 2-1. `features/onboarding/` (Streamlit v3.5, ~3,460줄)

| 모듈 | 줄 수 | 역할 | Day 5 활용 |
|---|---:|---|---|
| **`sop_guide.py`** | 334 | SOP 8종 데이터 + 단계별 + 체크리스트 | ⭐ FastAPI 엔드포인트로 노출 |
| **`collaboration_guide.py`** | 199 | 협업 시나리오 5종 + 트리거 매칭 | ⭐ FastAPI 엔드포인트 |
| **`work_actions.py`** | 305 | 업무 모드 액션 라우터 (에러/인원/8D/SPC) | ⭐ FastAPI 엔드포인트 |
| **`glossary_matcher.py`** | 390 | 용어집 매처 (297 용어) | ⭐ 백엔드 자동 프롬프트 주입 |
| `department_router.py` | 537 | 31 부서 프로필 + 자동 선택 | △ 백엔드만 (UI는 Day 11) |
| `curriculum.py` | 256 | 부서별 커리큘럼 | ❌ Day 5 비범위 |
| `context_optimizer.py` | 204 | 컨텍스트 최적화 (3000자/2000자) | ⭐ Day 4 듀얼 모드와 통합 |
| `quiz_engine.py` | 151 | 4지선다 퀴즈 자동 생성 | △ SOP 학습 inline 만 |
| **`feedback_db.py`** | 161 | 피드백 DB | ⭐ Firestore + RTDB로 마이그레이션 |
| `proactive_engine.py` | 160 | 능동 엔진 | ❌ 비범위 |
| `conversation_memory.py` | 173 | 대화 요약 | △ 백엔드 자동만 |
| `conversation_manager.py` | 89 | 대화 컨트롤러 | ❌ Day 4 useChatStore 가 대체 |
| `onboarding_bot.py` | 189 | 봇 통합 | ❌ Day 4 LLMRouter 가 대체 |
| `stream_response.py` | 117 | SSE | ❌ Day 4 backend/routers/onboarding.py 가 대체 |

### 2-2. `data/knowledge_base/`

| 디렉토리 | 내용 | Day 5 활용 |
|---|---|---|
| `sop/` | SOP 8종 JSON 정의 | ⭐ sop_guide.py 가 로드, Day 5 엔드포인트로 노출 |
| `collaboration/` | 시나리오 5종 데이터 | ⭐ collaboration_guide.py |
| `glossary/` (21 파일) | 297 용어 4종 JSON | ⭐ glossary_matcher.py 자동 주입 |
| `department_guides/` | 31 부서 가이드 | △ Day 11 |
| `templates/` | 양식 (8D / ECN / PPAP 등) | ⭐ 다운로드 영구화 |
| `company_info/` | 회사 정보 | ❌ 비범위 |

### 2-3. Frontend Day 1~4 자산

| 자산 | Day 5 재사용 |
|---|---|
| `useSSE` (백엔드 표준) | 비전 모드 SSE (Day 4 stream 그대로) |
| `useChatStore` (Zustand) | 메시지 + 메타 + 피드백 액션 추가 |
| `MessageBubble` / `MessageList` | 다운로드 버튼 + 피드백 버튼 추가 |
| `Modal` / `Drawer` | SOP 단계 모달, 비전 미리보기 |
| `Toast` (Zustand) | 시나리오 매칭, 업로드 완료 알림 |
| `MarkdownRenderer` | SOP 단계 본문 렌더 |
| `lib/firebase.ts` | Firestore + RTDB + Storage 클라이언트 (Day 2 통합 완료) |

---

## 3. 아키텍처 — Day 4 위에 보강

```
┌──────────────────────────────────────────────────────────────────┐
│  React /chat 페이지 (Day 4 기반)                                 │
│                                                                   │
│  ChatHeader [교육][업무] + 모델 selectbox (Day 5 추가)           │
│  ├─ MessageList                                                   │
│  │   ├─ MessageBubble + DownloadActions (Day 5)                  │
│  │   └─ MessageBubble + FeedbackActions (👍/👎) (Day 5)          │
│  ├─ SOPSidePanel (Day 5) — 8종 카드                              │
│  ├─ ScenarioTriggers (Day 5) — 5종 chip                          │
│  ├─ StreamStatus + ProviderBadge                                  │
│  └─ InputComposer + AttachmentTray (Day 5) — 비전/파일           │
│                                                                   │
│  스토어 확장:                                                     │
│   useChatStore — addFeedback, persistMessage, attachVision        │
│   useSOPStore (Day 5 신규) — 진행률 + 단계 추적                   │
└────────────┬─────────────────────────────────────────────────────┘
             │
             │ POST /api/onboarding/{chat,sop,scenarios,actions,vision,upload,feedback}
             │ Authorization: Bearer <Firebase ID Token>
             ▼
┌──────────────────────────────────────────────────────────────────┐
│  FastAPI :8000                                                    │
│  backend/routers/onboarding.py 갱신                              │
│   ├─ POST /chat                       (Day 4)                    │
│   ├─ POST /chat/vision                (이미 존재 — 갱신)         │
│   ├─ POST /upload                     (이미 존재 — 갱신)         │
│   ├─ GET  /sop/list                   ⭐ 신규                    │
│   ├─ GET  /sop/{sop_id}               ⭐ 신규                    │
│   ├─ POST /scenarios/match            ⭐ 신규                    │
│   ├─ POST /actions/match              ⭐ 신규                    │
│   ├─ POST /feedback                   ⭐ 신규                    │
│   └─ POST /download                   ⭐ 신규 (DOCX/XLSX/CSV/TXT)│
│                                                                   │
│  features/onboarding/* 12 모듈 직접 import 사용                  │
└────────────┬─────────────────────────────────────────────────────┘
             │
             ▼
┌──────────────────────────────────────────────────────────────────┐
│  Firebase                                                         │
│  ├─ Firestore: chat_history/{user_id}/{message_id}               │
│  ├─ RTDB:      /feedback/{message_id} (👍/👎 카운트)             │
│  └─ Storage:   /images/{user_id}/{ts}.png + /files/{user_id}/... │
└──────────────────────────────────────────────────────────────────┘
```

---

## 4. SOP 8종 시스템

### 4-1. SOP 8종 목록 (FEATURE C-2-3)

| # | SOP | 카테고리 | 단계 수 (예상) |
|:--:|---|---|---:|
| 1 | 금형 교체 | 설비 | 7 |
| 2 | 용접 검사 | 설비 | 5 |
| 3 | CNC 가공 | 설비 | 6 |
| 4 | 8D Report 작성 | 업무 프로세스 | 8 |
| 5 | ECN 발행 | 업무 프로세스 | 5 |
| 6 | SPC 분석 | 업무 프로세스 | 6 |
| 7 | PPAP 제출 | 업무 프로세스 | 7 |
| 8 | 안전 점검 | 업무 프로세스 | 5 |

### 4-2. 백엔드 — `sop_guide.py` 노출

```python
# backend/routers/onboarding.py 추가
from features.onboarding import sop_guide

@router.get("/sop/list")
async def list_sops(user=Depends(get_current_user)):
    return sop_guide.get_all_sops()  # [{id, title, category, steps_count, ...}]

@router.get("/sop/{sop_id}")
async def get_sop_detail(sop_id: str, user=Depends(get_current_user)):
    detail = sop_guide.get_sop_detail(sop_id)
    if not detail:
        raise HTTPException(404, f"SOP not found: {sop_id}")
    return detail  # {id, title, category, steps: [{n, title, content, checklist, warnings}]}
```

### 4-3. Frontend — SOPSidePanel + Stepper

```
chat 페이지 우측 또는 Drawer 로:
┌──────────────────────────────┐
│ SOP 가이드                    │
│ ─────────────                 │
│ 📋 1. 금형 교체    [50%]      │
│ 📋 2. 용접 검사    [-]        │
│ 📋 3. CNC 가공    [-]         │
│ 📋 4. 8D Report   [100%] ✓    │
│ ...                           │
└──────────────────────────────┘

클릭 → Drawer 또는 Modal 로 단계별 카드:
- Step 1 / 7
- 체크리스트 (Day 3 components/form/Checkbox 재사용)
- 주의사항 (warning 색)
- "다음 단계" / "퀴즈 풀기"
```

신규 컴포넌트:
- `components/sop/SOPSidePanel.tsx` (~80줄) — 8 카드 + 진행률 바
- `components/sop/SOPStepDrawer.tsx` (~120줄) — 단계별 카드 + Stepper(Day 3)
- `components/sop/SOPProgressBar.tsx` (~30줄)

신규 스토어:
- `store/sop.ts` (~80줄) — `progress: Record<sop_id, {currentStep, completed[]}>`, localStorage 영구화

신규 API:
- `api/sop.ts` (~40줄) — `listSops()`, `getSopDetail(id)`, `completeStep(sop_id, step_n)`

### 4-4. SOP 진행률 영구화

LocalStorage 우선 — Firestore 영구화는 Day 5 비스코프 (사용자 디바이스 분리 시 Day 11):
```typescript
const STORAGE_KEY = 'ajin.sop.progress';
useSOPStore.persist({ name: STORAGE_KEY });
```

---

## 5. 협업 시나리오 5종

### 5-1. 시나리오 5종 (FEATURE C-2-4)

| # | 시나리오 | 트리거 (한국어) | 응답 |
|:--:|---|---|---|
| 1 | 품질팀 → 8D Report 요청 | "품질팀에서 8D 올려달라는데?" | 협업 단계 + 담당 부서 + 양식 위치 + 마감 기한 |
| 2 | 설계 변경 → ECN 발행 | "설계 변경 요청 왔어" | (동일 구조) |
| 3 | SPC 이상 → 시정 조치 | "Cpk 1.0 떨어졌어" | (동일 구조) |
| 4 | 신차 양산 → PPAP | "현대 신차 양산 시작" | (동일 구조) |
| 5 | 안전 사고 위험 → 점검 | "안전 점검 어떻게 해?" | (동일 구조) |

LLM 호출 0회 — 즉시 응답.

### 5-2. 백엔드 — `collaboration_guide.py` 노출

```python
@router.post("/scenarios/match")
async def match_scenario(req: ScenarioMatchRequest, user=Depends(get_current_user)):
    """입력 텍스트에서 5종 시나리오 트리거를 매칭."""
    match = collaboration_guide.match_trigger(req.query)
    if not match:
        return {"matched": False}
    return {
        "matched": True,
        "scenario_id": match.id,
        "title": match.title,
        "steps": match.collaboration_steps,
        "departments": match.departments,
        "form_location": match.form_location,
        "deadline": match.deadline,
    }
```

### 5-3. Frontend — 자동 매칭 + Chip

`InputComposer.tsx` 의 `onSend()` 흐름:
1. 입력 텍스트 → `POST /scenarios/match` 호출 (LLM 호출 전)
2. `matched: true` 면 시나리오 카드 메시지 즉시 추가 (LLM 호출 X)
3. `matched: false` 면 기존 LLM 흐름 (Day 4)

신규 컴포넌트:
- `components/chat/ScenarioCard.tsx` (~80줄) — 협업 단계 + 부서 + 양식 + 기한
- `components/chat/ScenarioTriggers.tsx` (~50줄) — chat 빈 상태에서 5 chip 노출, 클릭 시 자동 입력

---

## 6. 업무 모드 액션 라우터 (C-2-7)

### 6-1. 액션 매칭 (FEATURE 540~550)

| 트리거 | 액션 | 응답 |
|---|---|---|
| "에러코드 E001" | error_code_db 조회 | 에러 상세 + 조치 |
| "김민수 부장 어디?" | 인원 검색 호출 | 사원 정보 + 연락처 |
| "8D 양식 어디?" | feature_bridge | 양식 다운로드 링크 |
| "SPC 상태?" | spc_dashboard | 5공정 Cpk |
| "REACH 규제 현황?" | compliance scenario | 시나리오 카드 |

### 6-2. 백엔드 — `work_actions.py` 노출

```python
@router.post("/actions/match")
async def match_action(req: ActionMatchRequest, user=Depends(get_current_user)):
    if useChatStore.mode != "work":  # 업무 모드일 때만
        return {"matched": False}
    action = work_actions.match(req.query)
    if not action:
        return {"matched": False}
    return {
        "matched": True,
        "action_type": action.type,  # "error_code" | "person_search" | ...
        "payload": action.payload,
        "navigate_to": action.navigate_to,  # 다른 모듈로 이동 링크
    }
```

### 6-3. Frontend 흐름

업무 모드 + LLM 호출 전:
1. `POST /scenarios/match` (협업 시나리오)
2. `POST /actions/match` (업무 액션)
3. 둘 다 unmatched → LLM 호출 (Day 4 흐름)

useChatStore 의 `sendMessage()` 갱신:
```typescript
async sendMessage(text, sseStart, language) {
  // 업무 모드 + 한국어일 때만 즉시 응답 시도
  if (get().mode === 'work' && language === 'ko') {
    const action = await matchAction(text);
    if (action.matched) {
      get().pushActionResponse(action);
      return; // LLM 호출 안 함
    }
  }
  
  // 협업 시나리오 매칭 (모드 무관)
  const scenario = await matchScenario(text);
  if (scenario.matched) {
    get().pushScenarioCard(scenario);
    return;
  }
  
  // LLM 호출 (Day 4 흐름)
  await sseStart({ url: buildChatUrl(), body: ... });
}
```

---

## 7. 다운로드 영구화

### 7-1. 백엔드 — `/api/onboarding/download` (신규)

```python
@router.post("/download")
async def generate_download(req: DownloadRequest, user=Depends(get_current_user)):
    """
    req.format: 'docx' | 'xlsx' | 'csv' | 'txt'
    req.content: str (마크다운 또는 plain)
    req.filename: str
    """
    if req.format == "docx":
        bytes_data = generate_docx(req.content)  # python-docx 사용
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif req.format == "xlsx":
        bytes_data = generate_xlsx(req.content)  # openpyxl
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif req.format == "csv":
        bytes_data = req.content.encode("utf-8-sig")  # BOM for Excel 한글
        media_type = "text/csv"
    elif req.format == "txt":
        bytes_data = req.content.encode("utf-8")
        media_type = "text/plain"
    else:
        raise HTTPException(400, "Unsupported format")
    
    return Response(
        content=bytes_data,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{req.filename}.{req.format}"'},
    )
```

`requirements.txt` 의 `python-docx`, `openpyxl` (이미 있음 — DAY3 시점 추가됨).

### 7-2. Frontend — 메시지 풍선 다운로드 버튼

`MessageBubble.tsx` 갱신:
```tsx
{role === 'assistant' && status === 'done' && (
  <DownloadActions
    formats={['md', 'docx', 'xlsx', 'csv', 'txt']}
    onDownload={(format) => downloadMessage(message, format)}
  />
)}
```

신규 컴포넌트:
- `components/chat/DownloadActions.tsx` (~70줄) — 5 버튼 + Tooltip
- `api/download.ts` (~50줄) — Blob 응답 + `URL.createObjectURL` + `<a download>`

---

## 8. 피드백 이모지 + RTDB

### 8-1. UI

`MessageBubble.tsx` (assistant 풍선만):
```tsx
<FeedbackActions
  messageId={message.id}
  onFeedback={(rating) => recordFeedback(message.id, rating)}  // 'thumbs_up' | 'thumbs_down'
/>
```

### 8-2. 백엔드 — RTDB 푸시 (Firestore 동시 쓰기)

```python
@router.post("/feedback")
async def submit_feedback(req: FeedbackRequest, user=Depends(get_current_user)):
    """
    req.message_id, req.rating ('thumbs_up' | 'thumbs_down'), req.user_id
    """
    feedback_db.record(
        user_id=user.uid,
        message_id=req.message_id,
        rating=req.rating,
        ts=time.time(),
    )
    # RTDB push (실시간 카운터)
    rtdb.push(f"/feedback/{req.message_id}", {
        "user_id": user.uid,
        "rating": req.rating,
        "ts": int(time.time()),
    })
    return {"ok": True}
```

### 8-3. Frontend — RTDB 직접 사용 (Day 3 useRTDBValue 활용)

```tsx
const feedback = useRTDBValue(`/feedback/${message.id}`);
// 카운트 표시:
<small>{feedback.up} 👍 / {feedback.down} 👎</small>
```

신규:
- `components/chat/FeedbackActions.tsx` (~60줄)
- `api/feedback.ts` (~40줄)

---

## 9. Firestore `chat_history` 영구화

### 9-1. 메시지 종료 시 쓰기

`useChatStore.finalizeActive()` 갱신:
```typescript
finalizeActive: (final) => {
  const msg = get().messages.find(m => m.id === get().activeMessageId);
  if (msg) {
    // Firestore 쓰기 (비동기, fire-and-forget)
    firestore.doc(`chat_history/${user.uid}/messages/${msg.id}`).set({
      ...msg,
      meta: { ...msg.meta, ...final },
      _at: serverTimestamp(),
    }).catch(console.warn);  // 실패해도 UI 영향 X
  }
  set((s) => ({ ... }));
},
```

### 9-2. 사용자 입장 시 최근 N개 로드

`chat.tsx` 진입 시:
```tsx
useEffect(() => {
  loadRecentMessages(user.uid, 20).then((msgs) => {
    useChatStore.getState().setHistory(msgs);
  });
}, [user.uid]);
```

신규:
- `lib/firestore-chat.ts` (~80줄) — `saveMessage`, `loadRecentMessages`, `clearHistory`

### 9-3. 보안 규칙 (Day 2 deploy 됨, 갱신 0)

`firestore.rules`:
```
match /chat_history/{userId}/messages/{msgId} {
  allow read, write: if request.auth.uid == userId;
}
```

이미 deploy 되어 있어야 함 — 검증 시 `firebase firestore:rules:list` 또는 콘솔 확인.

---

## 10. 비전 이미지 업로드

### 10-1. 백엔드 (이미 존재 — `/chat/vision`)

```python
@router.post("/chat/vision")  # Phase 2 보너스로 이미 존재
async def chat_with_vision(
    file: UploadFile = File(...),
    query: str = Form(...),
    user=Depends(get_current_user),
):
    image_bytes = await file.read()
    if len(image_bytes) > 5 * 1024 * 1024:
        raise HTTPException(413, "Image > 5MB")
    
    async def event_stream():
        async for ev in _llm_router.stream(
            prompt=query,
            mode=LLMMode.VISION,
            image_bytes=image_bytes,
        ):
            yield {"data": json.dumps(ev, ensure_ascii=False)}
    return EventSourceResponse(event_stream())
```

Day 5 갱신 — Storage 백업 + image_url 메타 추가:
```python
# 업로드 후 Storage 에 백업
url = storage.upload(f"images/{user.uid}/{int(time.time())}.png", image_bytes)
# (스트리밍 시작 전 metadata 이벤트로 image_url 노출)
```

### 10-2. Frontend — 이미지 첨부

`InputComposer.tsx` 갱신 — `<AttachmentTray>` 추가:
```tsx
<AttachmentTray
  onImageSelect={(file) => setAttachedImage(file)}
  onFileSelect={(file) => setAttachedFile(file)}
/>
{attachedImage && <ImagePreview file={attachedImage} onRemove={...} />}

// 전송 시:
if (attachedImage) {
  await sendVisionMessage(text, attachedImage);  // POST multipart
} else {
  await sendMessage(text, sseStart, language);  // Day 4 흐름
}
```

신규:
- `components/chat/AttachmentTray.tsx` (~80줄) — 클립 아이콘 + 파일 picker
- `components/chat/ImagePreview.tsx` (~50줄) — 썸네일 + 삭제
- `hooks/useVisionStream.ts` (~100줄) — multipart SSE

`useVisionStream` 은 useSSE 와 다른 흐름 (multipart) — `fetchEventSource` 의 `body` 에 `FormData` 직접 전달.

---

## 11. 파일 업로드 + 텍스트 추출

### 11-1. 백엔드 (이미 존재 — `/upload`)

`backend/routers/onboarding.py` 의 `/upload` 가 Phase 2 보너스로 만들어졌지만 Day 5에서 사용 흐름 정의:

```python
@router.post("/upload")
async def upload_file(file: UploadFile = File(...), user=Depends(get_current_user)):
    file_bytes = await file.read()
    if len(file_bytes) > 10 * 1024 * 1024:
        raise HTTPException(413, "File > 10MB")
    
    # 텍스트 추출 (기존 core/llm_client.py 의 extract_text_from_file 재사용)
    text = extract_text_from_file(file_bytes, file.filename)
    
    # Storage 백업
    url = storage.upload(f"files/{user.uid}/{int(time.time())}_{file.filename}", file_bytes)
    
    return {"text": text, "filename": file.filename, "url": url, "size": len(file_bytes)}
```

지원 확장자 (기존 `extract_text_from_file` 가 처리): TXT/MD/CSV/PY/JS/HTML/CSS/XML/YAML/JSON/PDF/DOCX/XLSX/PPTX/HWPX/DOC/XLS/RTF (~20+).

### 11-2. Frontend 흐름

1. 사용자가 파일 첨부
2. `POST /upload` 호출 → text + url 반환
3. text 를 LLM chat 의 `query` 에 prepend (예: `"파일 내용:\n{text}\n\n질문:\n{user_input}"`)
4. Day 4 정상 SSE 흐름

`useChatStore.attachFile(file)` 액션 추가.

---

## 12. Firebase Storage 통합

### 12-1. 사용처

| 경로 | 용도 |
|---|---|
| `/images/{user_id}/{ts}.png` | 비전 모드 첨부 이미지 (영구화) |
| `/files/{user_id}/{ts}_{filename}` | 파일 업로드 (영구화) |
| `/exports/{user_id}/{message_id}.{format}` | 다운로드 영구화 (선택, Day 5+ 또는 Day 12) |

### 12-2. 보안 규칙 (Day 2 deploy 됨)

`storage.rules`:
```
match /images/{userId}/{file=**} {
  allow read, write: if request.auth.uid == userId;
}
match /files/{userId}/{file=**} {
  allow read, write: if request.auth.uid == userId;
}
```

검증: `firebase storage:rules:list` 또는 콘솔.

### 12-3. 백엔드 vs Frontend 직접 업로드

**옵션 A** — 백엔드 경유 (Storage Admin SDK)
- 장점: 보안 검증 1곳, 파일 변환 가능
- 단점: 대용량 시 백엔드 부하

**옵션 B** — Frontend 직접 (Storage Web SDK)
- 장점: 백엔드 부하 0
- 단점: 보안 규칙 의존

**Day 5 권장: 하이브리드**
- 비전 이미지 (5MB 이하) — 백엔드 경유 (LLM 호출과 함께 처리)
- 파일 업로드 (10MB 이하) — 백엔드 경유 (텍스트 추출 필요)
- 향후 대용량 첨부 — Frontend 직접 (Day 5+ 또는 Day 11)

---

## 13. 모델 비교 selectbox (Day 4 보강)

### 13-1. UI

`ChatHeader` 갱신:
```
[교육][업무]   |   모델: [자동 ▾]
                       └ 자동 (라우팅 매트릭스)
                       └ Gemini 2.5 Pro
                       └ Ollama qwen3.5:9b
                       └ Ollama gemma4:e4b
```

### 13-2. 백엔드 — `force_provider` 파라미터

`POST /api/onboarding/chat` 의 `ChatRequest` 갱신:
```python
class ChatRequest(BaseModel):
    query: str
    mode: str = "chat"
    history: list[dict] | None = None
    language: str = "ko"
    force_provider: str | None = None  # "gemini" | "ollama:qwen3.5:9b" | "ollama:gemma4:e4b"
```

`LLMRouter.stream()` 에 `force_provider` 옵션 추가 (Phase 1~3 갱신은 최소화):
- 라우터 본체는 손대지 말고, FastAPI 라우터에서 force_provider 가 있으면 직접 provider 호출.
- 또는 `LLMRouter.stream(prompt, force=("gemini", "gemini-2.5-pro"))` 형태.

### 13-3. 시연 가치
"같은 질문을 Gemini 와 qwen3.5:9b 와 gemma4:e4b 에 각각 보내서 응답 비교" — 본선 평가 #1 + 사용자 정책 시연 차별점.

신규/갱신:
- `components/chat/ModelSelect.tsx` (~50줄)
- `useChatStore.forceProvider` 필드 + setter
- `core/llm_router.py` 의 `stream()` `force` 파라미터 추가 (~10줄)
- `backend/routers/onboarding.py` 의 `/chat` 엔드포인트 — `force_provider` 처리

---

## 14. 파일 구조

### 14-1. 신규/갱신 파일

```
ajin-ai-assistant-react/
├── backend/routers/
│   └── onboarding.py                  ⭐ 갱신 (+~250줄: 6 신규 엔드포인트)
├── backend/services/
│   ├── download_service.py            ⭐ 신규 (~150줄: DOCX/XLSX/CSV 생성)
│   └── storage_service.py             ⭐ 신규 (~80줄: Firebase Admin Storage)
├── backend/schemas/
│   └── onboarding.py                  갱신 (+~60줄: 신규 요청/응답 스키마)
├── core/
│   └── llm_router.py                  갱신 (+10줄: force_provider 옵션)
└── frontend/src/
    ├── routes/
    │   └── chat.tsx                   갱신 (+~80줄: SOP/시나리오/첨부 통합)
    ├── components/
    │   ├── chat/                      Day 4 + Day 5
    │   │   ├── DownloadActions.tsx    ⭐ ~70
    │   │   ├── FeedbackActions.tsx    ⭐ ~60
    │   │   ├── AttachmentTray.tsx     ⭐ ~80
    │   │   ├── ImagePreview.tsx       ⭐ ~50
    │   │   ├── ScenarioCard.tsx       ⭐ ~80
    │   │   ├── ScenarioTriggers.tsx   ⭐ ~50
    │   │   ├── ModelSelect.tsx        ⭐ ~50
    │   │   └── (Day 4 6개 그대로)
    │   └── sop/                       ⭐ 신규 디렉토리
    │       ├── SOPSidePanel.tsx       ⭐ ~80
    │       ├── SOPStepDrawer.tsx      ⭐ ~120
    │       └── SOPProgressBar.tsx     ⭐ ~30
    ├── hooks/
    │   └── useVisionStream.ts         ⭐ ~100
    ├── api/
    │   ├── sop.ts                     ⭐ ~40
    │   ├── scenarios.ts               ⭐ ~30
    │   ├── actions.ts                 ⭐ ~30
    │   ├── feedback.ts                ⭐ ~40
    │   ├── download.ts                ⭐ ~50
    │   ├── upload.ts                  ⭐ ~40
    │   └── onboarding.ts              갱신 (+~30: force_provider)
    ├── store/
    │   ├── chat.ts                    갱신 (+~80: 첨부/피드백/액션)
    │   └── sop.ts                     ⭐ ~80
    ├── lib/
    │   ├── firestore-chat.ts          ⭐ ~80
    │   └── firebase.ts                갱신 (+~20: storage helper)
    └── i18n/
        ├── ko/common.json             갱신 (+~50 키)
        └── en/common.json             갱신 (+~50 키)
```

### 14-2. 줄 수 합계

| 카테고리 | 신규 | 갱신 |
|---|---:|---:|
| 백엔드 | ~290 | ~330 |
| Frontend 컴포넌트 | ~770 | +80 |
| Frontend hooks/api/store/lib | ~580 | +130 |
| i18n | — | +100 |
| **합계** | **~1,640** | **~640** |

총 ~2,280줄 (분량 큼 → Phase 분할 필수).

---

## 15. 단계 분할 — Phase 1~5

### Phase 1 — 백엔드 엔드포인트 + 스키마 (~45분)
- [ ] `backend/schemas/onboarding.py` 갱신 (신규 요청/응답)
- [ ] `backend/routers/onboarding.py` 갱신 — 6 신규 엔드포인트 (sop/list, sop/{id}, scenarios/match, actions/match, feedback, download)
- [ ] `backend/services/download_service.py` (DOCX/XLSX/CSV)
- [ ] `backend/services/storage_service.py` (Firebase Admin)
- [ ] `core/llm_router.py` force_provider 추가
- [ ] `requirements.txt` — `firebase-admin` 추가 (없으면)

검증: `pytest tests/test_llm_router.py` 30/30 유지 + 신규 엔드포인트 swagger /docs 노출

### Phase 2 — SOP + 시나리오 (~45분)
- [ ] `frontend/src/api/sop.ts`, `scenarios.ts`, `actions.ts`
- [ ] `frontend/src/store/sop.ts` (localStorage persist)
- [ ] `frontend/src/components/sop/*` 3 컴포넌트
- [ ] `frontend/src/components/chat/ScenarioCard.tsx`, `ScenarioTriggers.tsx`
- [ ] `frontend/src/store/chat.ts` 갱신 — pushScenarioCard, pushActionResponse
- [ ] `frontend/src/routes/chat.tsx` 갱신 — SOP Drawer + Scenario Triggers 통합

검증: `npm run build` + `/chat` 에서 시나리오 5종 즉시 응답 확인

### Phase 3 — 다운로드 + 피드백 + Firestore (~45분)
- [ ] `frontend/src/api/download.ts`, `feedback.ts`
- [ ] `frontend/src/components/chat/DownloadActions.tsx`, `FeedbackActions.tsx`
- [ ] `frontend/src/lib/firestore-chat.ts`
- [ ] `frontend/src/store/chat.ts` 갱신 — finalizeActive 에 Firestore 쓰기 + setHistory
- [ ] `frontend/src/routes/chat.tsx` 진입 시 loadRecentMessages

검증: 메시지 송신 → Firestore 콘솔에서 확인 + 피드백 → RTDB 노드 확인

### Phase 4 — 비전 + 파일 + Storage (~45분)
- [ ] `frontend/src/api/upload.ts`
- [ ] `frontend/src/hooks/useVisionStream.ts`
- [ ] `frontend/src/components/chat/AttachmentTray.tsx`, `ImagePreview.tsx`
- [ ] `frontend/src/store/chat.ts` 갱신 — attachVision, attachFile
- [ ] `backend/routers/onboarding.py` /chat/vision + /upload 의 Storage 백업 추가

검증: 이미지 첨부 → /chat/vision SSE 응답 + Storage 콘솔 확인

### Phase 5 — 모델 비교 + i18n + 통합 검증 (~30분)
- [ ] `frontend/src/components/chat/ModelSelect.tsx`
- [ ] `frontend/src/store/chat.ts` 갱신 — forceProvider 필드
- [ ] `frontend/src/components/chat/ChatHeader.tsx` 또는 chat.tsx 직접 통합
- [ ] i18n 한·영 키 ~50개 추가
- [ ] 본선 시연 시나리오 5건 완주

검증: DAY5_PLAN Section 16 체크리스트 모두 ✓

---

## 16. 검증 체크리스트

### 16-1. 코드 품질
- [ ] `npm run build` (TS strict) 0 오류
- [ ] `npm run lint` 0 경고
- [ ] `pytest tests/test_llm_router.py` 30/30 PASS 유지
- [ ] 신규 컴포넌트 ErrorBoundary 보호
- [ ] 외부 의존성 추가: `firebase-admin` (백엔드만)

### 16-2. 기능
- [ ] SOP 8종 모두 노출 + 단계별 카드 정상 표시
- [ ] SOP 진행률 — localStorage 영구화 (페이지 새로고침 후 유지)
- [ ] 협업 시나리오 5종 — 트리거 입력 시 LLM 호출 0회 (즉시 응답)
- [ ] 업무 모드 액션 라우터 5종 매칭
- [ ] 다운로드 — DOCX/XLSX/CSV/TXT 4 형식 생성 + 한글 정상
- [ ] 피드백 (👍/👎) → Firestore + RTDB 동시 쓰기
- [ ] Firestore `chat_history` 영구화 + 페이지 재진입 시 최근 20개 로드
- [ ] 비전 이미지 첨부 → `/chat/vision` SSE 응답
- [ ] 파일 첨부 (PDF/DOCX/XLSX/HWPX) → 텍스트 추출 + LLM 컨텍스트 주입
- [ ] Firebase Storage `/images/`, `/files/` 업로드 확인
- [ ] 모델 selectbox — Gemini/qwen3.5:9b/gemma4:e4b 강제 선택 동작

### 16-3. UX
- [ ] SOP Drawer 모바일 반응형
- [ ] 첨부 이미지 미리보기 + 삭제
- [ ] 시나리오 카드 시각 차별화 (LLM 응답과 다른 색)
- [ ] Toast — 다운로드 완료, 업로드 완료, 피드백 등록
- [ ] 모델 비교 — 강제 모델 사용 시 ProviderBadge 명시 변경

### 16-4. 본선 시연 시나리오
- [ ] **시연 1**: "8D Report 양식 어디?" → 협업 시나리오 카드 즉시 (LLM 0회)
- [ ] **시연 2**: SOP 사이드 패널 → "금형 교체" 클릭 → Step 1~7 따라가기 + 체크리스트
- [ ] **시연 3**: 부품 사진 첨부 → "이 부품 결함이 뭐야?" → Gemini Vision 응답
- [ ] **시연 4**: 모델 selectbox → Gemini → 응답 → qwen3.5:9b → 동일 질문 → 응답 비교
- [ ] **시연 5**: 다운로드 — 응답을 DOCX 로 다운로드
- [ ] **시연 6**: 피드백 👍 → RTDB Live 카운터 갱신

---

## 17. 위험 + 완화

| # | 위험 | 영향 | 완화 |
|:--:|---|:--:|---|
| 1 | **`features/onboarding/*` 모듈 import 충돌** (Streamlit st.* 호출) | 🔴 | sop_guide.py / collaboration_guide.py 가 st.session_state 의존하면 데이터 함수만 분리 — 의심 시 backend wrapper 에서 상태 격리 |
| 2 | **Firestore 쓰기 quota** | 🟡 | fire-and-forget + 실패 시 콘솔 경고만 (UI 영향 X) |
| 3 | **RTDB 동시 카운터 race** | 🟡 | `serverTimestamp` + transaction 사용 또는 카운터 대신 push (유저별 row) |
| 4 | **Storage 비용** | 🟢 | 본선 데모 30명 × 5MB = 150MB — 무시 가능 수준 |
| 5 | **비전 이미지 5MB 초과** | 🟡 | 프론트 sharp/canvas 자동 리사이즈 (1280px 이하) — Day 5 또는 Day 12 |
| 6 | **`firebase-admin` 백엔드 인증** | 🟡 | 서비스 계정 JSON 필요 — `.env` `FIREBASE_SERVICE_ACCOUNT_KEY_PATH` 또는 emulator 사용 |
| 7 | **모델 비교 — Ollama 지연** | 🟡 | 강제 Ollama 시 TTFT 800~1500ms — 시연 시 안내 메시지 또는 워밍업 |
| 8 | **`/upload` 텍스트 추출 — HWPX 파싱 오류** | 🟢 | 기존 core/llm_client.py 의 _extract_hwpx 사용 — fallback 메시지로 처리 |
| 9 | **TS strict — Firestore Timestamp 타입** | 🟡 | `firebase` 9+ modular SDK 의 `Timestamp` import 명시 |
| 10 | **번들 크기 증가** | 🟢 | code splitting — Day 12 모바일 폴리싱에서 lazy import |

---

## 18. Day 5 비스코프 (Day 11~13 이후)

| # | 항목 | 일정 | 사유 |
|:--:|---|---|---|
| 1 | 부서 라우터 31종 UI | Day 11 인사 또는 Day 12 | E 인사와 통합 |
| 2 | 용어집 매처 297항목 UI 하이라이트 | Day 12 폴리싱 | 백엔드 자동 주입은 Day 5 |
| 3 | 대화 요약 메모리 UI | Day 13 또는 비범위 | 백엔드 자동만 |
| 4 | 퀴즈 자동 생성 단독 화면 | Day 5+ 또는 비범위 | SOP inline 만 |
| 5 | 능동 엔진 (proactive_engine) | 비범위 | 시연 가치 낮음 |
| 6 | TF-IDF intent 분류기 (백엔드) | Day 13 | 라우터 보강 |
| 7 | Firestore 영구화 사용자 디바이스 분리 | Day 11 | 멀티 디바이스 동기화 |
| 8 | Frontend 직접 Storage 업로드 | Day 12 | 대용량 첨부 |
| 9 | Cloud Functions 트리거 (Firestore → 통계) | Day 14 | Firebase 통합 보강 |

---

## 19. 시간 분배표 (총 3~3.5h)

| 시간대 | 작업 |
|:--:|---|
| 00:00 ~ 00:10 | features/onboarding/* 모듈 검증 (st.* 의존 없는지) + 백엔드 시작 |
| 00:10 ~ 00:55 | Phase 1 — 백엔드 6 엔드포인트 + 다운로드/Storage 서비스 |
| 00:55 ~ 01:00 | 휴식 + Phase 1 검증 |
| 01:00 ~ 01:45 | Phase 2 — SOP + 시나리오 + 액션 라우터 |
| 01:45 ~ 02:30 | Phase 3 — 다운로드 + 피드백 + Firestore |
| 02:30 ~ 02:35 | 휴식 + Phase 3 검증 |
| 02:35 ~ 03:20 | Phase 4 — 비전 + 파일 + Storage |
| 03:20 ~ 03:50 | Phase 5 — 모델 비교 + i18n + 본선 시연 시나리오 6건 완주 |

---

## 20. 분할 진행 옵션

분량이 ~2,280줄로 크므로 Day 5 를 두 단위로 나눌 수도:

| 옵션 | 분할 |
|---|---|
| **(A) Day 5 통째로 위임** | 1 executor — 3~3.5h, 검증 단위 큼 |
| **(B) Day 5A (Phase 1~3) + Day 5B (Phase 4~5)** ⭐ | 2 executor 순차 — Phase 1~3 검증 후 Phase 4~5 |
| **(C) Day 5A 만 진행, Phase 4~5 는 Day 6 일부** | 가장 안전, 일정 +0.5일 |

권장: **(B)** — Phase 1~3 (시연 핵심 7종) 먼저 검증 후 Phase 4~5 (비전/파일/모델 selectbox) 위임.

---

## 21. 사용자 결정 대기 사항 (실행 직전)

| # | 결정 | 권장 |
|:--:|---|---|
| 1 | **분할 진행 옵션** | **(B) — Phase 1~3 먼저** |
| 2 | **Firebase Admin SDK 인증** | 서비스 계정 JSON 경로 `.env` 의 `FIREBASE_SERVICE_ACCOUNT_KEY_PATH` (사용자 작업 — Phase 1 시작 전) |
| 3 | **모델 selectbox 위치** | `chat.tsx` 의 ChatHeader 우측 (UI 결정 — 권장안 그대로) |
| 4 | **다운로드 파일명 규칙** | `chat-{timestamp}-{first-10-chars}.{format}` |
| 5 | **`features/onboarding/*` 모듈 호환성** | st.* 호출 제거 또는 wrapper 추가 — Phase 1 시작 시 검증, 비호환이면 데이터 함수만 분리 |

---

## 변경 이력

| 버전 | 날짜 | 변경 |
|---|---|---|
| **1.0** | 2026-04-27 | 초안 — 21 섹션 / 신규 ~1,640줄 + 갱신 ~640줄 / Phase 5분할 |

---

**관련 문서**:
- [DAY4_PLAN.md](DAY4_PLAN.md) — Day 4 채팅 UI (완료)
- [LLM_ROUTER_PLAN.md](LLM_ROUTER_PLAN.md) — 백엔드 LLM 라우터 (완료)
- [FINAL_17DAY_PLAN.md](FINAL_17DAY_PLAN.md) — Day 5 위치 (L323)
- [WEB_DESIGN_SPECIFICATION.md](WEB_DESIGN_SPECIFICATION.md) — Liquid Glass 토큰
- [FIREBASE_DB_ARCHITECTURE.md](FIREBASE_DB_ARCHITECTURE.md) — Firebase 통합 아키텍처
- [FEATURE_SPECIFICATION.md](../features/FEATURE_SPECIFICATION.md) — C-2-1 ~ C-2-10 사양
