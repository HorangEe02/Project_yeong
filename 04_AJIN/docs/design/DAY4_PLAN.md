# Day 4 — C AI 도우미 Frontend 통합 (백엔드 LLM 라우터 차단 해제)

> **작성일**: 2026-04-27 (Day 3 마감 직후)
> **선행**: 백엔드 LLM 라우터 Phase 1~3 완료 (30 unit test PASS, `/api/onboarding/chat` SSE 동작)
> **목표 시간**: 1.5~2시간
> **본선까지**: 14 작업일 남음

---

## 목차

1. [목적 + 요구사항](#1-목적--요구사항)
2. [사용자 정책 + 백엔드 매칭](#2-사용자-정책--백엔드-매칭)
3. [아키텍처](#3-아키텍처)
4. [SSE 포맷 통일 — Before/After](#4-sse-포맷-통일--beforeafter)
5. [`useSSE` 훅 갱신 사양](#5-usesse-훅-갱신-사양)
6. [메시지 데이터 모델 (Frontend)](#6-메시지-데이터-모델-frontend)
7. [파일 구조 + 컴포넌트 트리](#7-파일-구조--컴포넌트-트리)
8. [`chat.tsx` 페이지 레이아웃](#8-chattsx-페이지-레이아웃)
9. [`onboarding.ts` API 클라이언트](#9-onboardingts-api-클라이언트)
10. [듀얼 모드 (교육/업무) 사양](#10-듀얼-모드-교육업무-사양)
11. [Zustand 채팅 스토어](#11-zustand-채팅-스토어)
12. [i18n 키 신규 (한·영)](#12-i18n-키-신규-한영)
13. [단계 분할 — Phase 1~3](#13-단계-분할--phase-13)
14. [검증 체크리스트](#14-검증-체크리스트)
15. [위험 + 완화](#15-위험--완화)
16. [Day 4 비스코프 (Day 5 이후)](#16-day-4-비스코프-day-5-이후)
17. [시간 분배표](#17-시간-분배표)

---

## 1. 목적 + 요구사항

### 1-1. 목표
Day 1~3 (셸/공통 컴포넌트/Firebase) 와 백엔드 LLM 라우터 Phase 1~3 (Gemini + Ollama + Circuit Breaker + 메트릭 + FastAPI SSE 엔드포인트) 가 모두 완성된 지금, 두 레이어를 잇는 **C AI 도우미 화면** 을 본격 구현.

### 1-2. 비즈니스 요구사항

| # | 요구사항 | 근거 |
|:--:|---|---|
| 1 | SSE 토큰 단위 실시간 응답 | C-2-1 사양 (`docs/features/FEATURE_SPECIFICATION.md:480`) |
| 2 | 듀얼 모드 (교육 3000자 / 업무 2000자) | C-2-6 (FEATURE:532) |
| 3 | 폴백 인디케이터 — "Gemini → Ollama" 표기 | 사용자 정책 — "오픈 LLM 다양성 강조" 시연 |
| 4 | Liquid Glass 스타일 일관성 | Day 1 디자인 토큰 + 테마 |
| 5 | 한·영 i18n | Day 1 부트스트랩에서 결정 |
| 6 | 모바일 반응형 (768/1024) | 본선 모바일 데모 포함 |
| 7 | 인증 — Firebase ID Token Bearer | Day 2 Auth 통합 |
| 8 | 네비게이션 차단 (스트리밍 중) | C-2-1 v3.4 — 의도치 않은 페이지 이탈 방지 |

### 1-3. 비기능 요구사항

| 항목 | 목표 |
|---|---|
| 첫 토큰 표시 (TTFT) | <800ms (백엔드 Gemini TTFT 200~400ms + 네트워크) |
| 메시지 1000자 렌더링 | <50ms (react-markdown lazy) |
| TS strict 컴파일 | 0 오류 |
| 컴포넌트 재사용 | Day 3 라이브러리 ≥80% 활용 |
| ErrorBoundary | 페이지 단위 격리 (Day 3 패턴) |
| AbortController | 사용자 취소 즉시 반영 |

### 1-4. 비범위 (Day 4)
- ❌ SOP 단계별 가이드 (C-2-3, **Day 5**)
- ❌ 협업 시나리오 5종 (C-2-4, **Day 5**)
- ❌ 비전 이미지 업로드 (C-2-5, **Day 5**)
- ❌ 파일 업로드 20+ 확장자 (**Day 5**)
- ❌ 다운로드 영구화 (DOCX/XLSX) (**Day 5**)
- ❌ Firestore 메시지 영구화 (`chat_history/{user}/{msg_id}`) (**Day 5**)
- ❌ 피드백 이모지 (👍/👎) → RTDB 푸시 (**Day 5**)
- ❌ 부서 라우터 31종 (C-2-8, **Day 5**)
- ❌ 용어집 매처 297항목 (C-2-9, **Day 5**)
- ❌ 대화 요약 메모리 (C-2-10, **Day 5**)
- ❌ TF-IDF intent 분류기 (Phase 2의 백엔드 추가 작업)

---

## 2. 사용자 정책 + 백엔드 매칭

### 2-1. 모델 풀 (백엔드 Phase 1~3 확정)
- **Gemini 2.5 Pro** 단일 (외부 1순위)
- **Ollama**: `qwen3.5:9b/4b`, `gemma4:e4b/e2b` (사내 폴백)
- **임베딩**: `bge-m3` 단독
- **EXAONE 사용 금지**

### 2-2. 라우팅 매트릭스 (재확인)

| 모드 | 1순위 | 2순위 | 3순위 |
|---|---|---|---|
| `chat` | Gemini 2.5 Pro | qwen3.5:9b | gemma4:e4b |
| `chat_korean` | Gemini 2.5 Pro | qwen3.5:9b | gemma4:e4b |
| `draft` | qwen3.5:9b | gemma4:e4b | Gemini 2.5 Pro |
| `summary` | Gemini 2.5 Pro | qwen3.5:4b | gemma4:e2b |
| `intent` | Gemini 2.5 Pro | qwen3.5:4b | — |

Day 4 화면에서 사용자 입력 시 **자동 라우팅** — 한국어 입력 감지 시 `chat_korean`, 영어면 `chat`. 듀얼 모드의 "업무" 는 토큰 예산만 줄이고 모드는 동일.

### 2-3. 시연 차별점 (본선 평가 포인트 #1)
- "Gemini 응답 중 → API 키 차단 → Ollama 자동 전환" 플로우 시연
- UI에 **`fallback_from`** 메타데이터 표기 (Toast 또는 ProviderBadge)
- 백엔드의 `metadata.final_provider`, `metadata.final_model` 을 그대로 노출

---

## 3. 아키텍처

```
┌──────────────────────────────────────────────────────────────┐
│  Browser (React 19, Vite 8, TS strict)                       │
│                                                               │
│  src/routes/chat.tsx (page)                                  │
│   ├─ <ChatHeader />     모드 토글 + 모델 정보                │
│   ├─ <MessageList />    auto-scroll, react-markdown          │
│   │   └─ <MessageBubble /> user/assistant role               │
│   │       └─ <ProviderBadge /> "Gemini 2.5 Pro" 표시        │
│   ├─ <StreamStatus />   "스트리밍 중", 폴백 인디케이터        │
│   └─ <InputComposer />  textarea + 전송/중지 버튼             │
│                                                               │
│  Hooks:                                                       │
│   ├─ useSSE (갱신)                                            │
│   └─ useChatStore (Zustand 신규)                             │
│                                                               │
│  API:                                                         │
│   └─ src/api/onboarding.ts (신규)                            │
└────────────────┬─────────────────────────────────────────────┘
                 │ POST /api/onboarding/chat (SSE)
                 │ Authorization: Bearer <Firebase ID Token>
                 ▼
┌──────────────────────────────────────────────────────────────┐
│  FastAPI (uvicorn :8000)                                     │
│  backend/routers/onboarding.py                               │
│   └─ EventSourceResponse + LLMRouter.stream()               │
└────────────────┬─────────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────────┐
│  LLMRouter (Phase 1~3 완성)                                  │
│   └─ chain: Gemini → Ollama qwen3.5:9b → gemma4:e4b          │
│       Circuit Breaker + Metrics + LM Studio 토글             │
└──────────────────────────────────────────────────────────────┘
```

Vite dev proxy 또는 백엔드 CORS 로 `:5173 → :8000` 연결 (위험 #1 참조).

---

## 4. SSE 포맷 통일 — Before/After

### 4-1. 결정
**(C) `useSSE` 갱신 — 백엔드 표준 따름.**
이유:
- 백엔드는 Phase 3 에서 30 unit test 로 검증된 안정 포맷
- `metadata.fallback_from` / `metadata.final_provider` 등 풍부한 정보로 시연 차별점 직결
- useSSE 117줄, 로컬 변경 risk 낮음

### 4-2. Before (현 useSSE)

```typescript
// src/hooks/useSSE.ts (현재)
interface SSEMessage {
  token?: string;
  done?: boolean;
  error?: string;
  meta?: Record<string, unknown>;
}
```

서버 페이로드 가정: `data: {"token":"안녕"}`, `data: {"done":true}`.

### 4-3. After (백엔드 표준 적용)

```typescript
// src/hooks/useSSE.ts (갱신)
export type StreamEventType = 'metadata' | 'token' | 'done' | 'error';

export interface StreamEvent {
  type: StreamEventType;
  content: string | null;
  metadata: Record<string, unknown> | null;
}

// 편의 — 콜백에 정규화된 객체 전달
export interface SSECallbacks {
  onToken?: (chunk: string) => void;          // type === 'token'
  onMetadata?: (meta: Record<string, unknown>) => void;
  onDone?: (finalMeta: Record<string, unknown>) => void;
  onError?: (msg: string, err?: unknown) => void;
}
```

서버 페이로드: `data: {"type":"token","content":"안녕","metadata":null}`.

내부 상태 `text`, `isStreaming` 은 그대로 유지 (chat.tsx 가 구독 가능).

추가 상태 — 폴백/모델 정보 노출:
```typescript
interface UseSSEReturn {
  text: string;
  isStreaming: boolean;
  meta: { provider?: string; model?: string; fallbackFrom?: string | null };
  start: (args: SSEStartArgs) => Promise<void>;
  stop: () => void;
  reset: () => void;
}
```

---

## 5. `useSSE` 훅 갱신 사양

### 5-1. 변경 요약 (현 117줄 → ~135줄, +18 net)

| Before | After |
|---|---|
| `SSEMessage { token?, done?, error?, meta? }` | `StreamEvent { type, content, metadata }` |
| `options.onMessage(msg)` 단일 콜백 | `onToken / onMetadata / onDone / onError` 4개 |
| `text` 만 외부 노출 | `text + meta { provider, model, fallbackFrom }` |
| token 처리 — `if (msg.token)` | type 분기 — `switch (msg.type)` |

### 5-2. 핵심 갱신 코드

```typescript
onmessage(ev) {
  if (!ev.data) return;
  let parsed: StreamEvent;
  try {
    parsed = JSON.parse(ev.data) as StreamEvent;
  } catch {
    return; // heartbeat 등 무시
  }

  switch (parsed.type) {
    case 'metadata': {
      const m = parsed.metadata ?? {};
      setMeta((prev) => ({
        ...prev,
        provider: typeof m.provider === 'string' ? m.provider : prev.provider,
        model: typeof m.model === 'string' ? m.model : prev.model,
        fallbackFrom:
          'fallback_from' in m
            ? (m.fallback_from as string | null)
            : prev.fallbackFrom,
      }));
      callbacks.onMetadata?.(m);
      break;
    }
    case 'token':
      if (parsed.content) {
        setText((prev) => prev + parsed.content);
        callbacks.onToken?.(parsed.content);
      }
      break;
    case 'done':
      setIsStreaming(false);
      callbacks.onDone?.(parsed.metadata ?? {});
      break;
    case 'error':
      setIsStreaming(false);
      callbacks.onError?.(parsed.content ?? 'unknown', parsed.metadata);
      break;
  }
}
```

### 5-3. 호환성 — Day 3 다른 사용처
useSSE 의 사용처: 현재 `chat.tsx` placeholder 만. **Day 4 갱신과 동시 도입 — 호환성 부담 없음.**

---

## 6. 메시지 데이터 모델 (Frontend)

### 6-1. `src/types/chat.ts` (신규, ~40줄)

```typescript
export type MessageRole = 'user' | 'assistant' | 'system';

export interface ChatMessage {
  id: string;                          // crypto.randomUUID()
  role: MessageRole;
  content: string;                     // 누적 텍스트
  createdAt: number;                   // Date.now()
  status: 'pending' | 'streaming' | 'done' | 'error';
  meta?: {
    provider?: string;                 // "gemini" | "ollama" | "lm_studio"
    model?: string;                    // "gemini-2.5-pro" | "qwen3.5:9b" ...
    fallbackFrom?: string | null;
    finalProvider?: string;
    ttftMs?: number;
    latencyMs?: number;
    error?: string;
  };
}

export type ChatMode = 'education' | 'work';  // 듀얼 모드 (교육/업무)

export interface ChatRequest {
  query: string;
  mode: 'chat' | 'chat_korean' | 'draft' | 'summary';
  history?: { role: 'user' | 'model'; content: string }[];
  language: 'ko' | 'en';
  // 듀얼 모드 — 백엔드는 mode 만 받지만 향후 컨텍스트 길이 분기에 사용
  contextBudget?: number;              // 3000 | 2000
}
```

### 6-2. user input → ChatRequest 변환

```typescript
function buildRequest(text: string, mode: ChatMode, language: 'ko' | 'en'): ChatRequest {
  const llmMode = language === 'ko' ? 'chat_korean' : 'chat';
  return {
    query: text,
    mode: llmMode,
    history: takeLastNTurns(history, mode === 'education' ? 6 : 4),
    language,
    contextBudget: mode === 'education' ? 3000 : 2000,
  };
}
```

---

## 7. 파일 구조 + 컴포넌트 트리

### 7-1. 신규/갱신 파일

```
frontend/src/
├── routes/
│   └── chat.tsx                      ⭐ 갱신 (19 → ~280줄)
├── components/
│   └── chat/                         ⭐ 신규 디렉토리
│       ├── MessageBubble.tsx         ⭐ 60줄 — user/assistant 풍선
│       ├── MessageList.tsx           ⭐ 70줄 — auto-scroll + ErrorBoundary
│       ├── InputComposer.tsx         ⭐ 90줄 — textarea + send/stop
│       ├── ModeToggle.tsx            ⭐ 50줄 — 교육/업무 토글
│       ├── ProviderBadge.tsx         ⭐ 40줄 — 모델 표시
│       └── StreamStatus.tsx          ⭐ 50줄 — 스트리밍 인디케이터 + 폴백
├── hooks/
│   └── useSSE.ts                     갱신 (117 → ~135줄)
├── api/
│   └── onboarding.ts                 ⭐ 신규 (~80줄)
├── store/
│   └── chat.ts                       ⭐ 신규 Zustand (~110줄)
├── types/
│   └── chat.ts                       ⭐ 신규 (~40줄)
└── i18n/
    ├── ko/common.json                갱신 (+30 키)
    └── en/common.json                갱신 (+30 키)
```

### 7-2. 줄 수 합계

| 카테고리 | 줄 수 |
|---|---:|
| 신규 컴포넌트 6개 | ~360 |
| 신규 chat.tsx (placeholder 19줄 폐기) | ~280 |
| 신규 onboarding.ts | ~80 |
| 신규 store/chat.ts | ~110 |
| 신규 types/chat.ts | ~40 |
| useSSE.ts 갱신 | +18 |
| i18n 키 추가 | ~60 (한·영 합) |
| **합계** | **~948** |

---

## 8. `chat.tsx` 페이지 레이아웃

### 8-1. 시각 레이아웃

```
┌──────────────────────────────────────────────────────┐
│  C · ONBOARDING                       [교육][업무]  │ ← Header
│  AI WORK ASSISTANT · MODULE C                        │
├──────────────────────────────────────────────────────┤
│                                                      │
│  ╭─────────────╮                                    │
│  │ 안녕하세요  │  ← Assistant bubble                 │
│  │ (gemini)    │                                    │
│  ╰─────────────╯                                    │
│                                                      │
│                          ╭───────────────╮          │
│                          │ 8D 양식 어디? │  ← User  │
│                          ╰───────────────╯          │
│                                                      │
│  ╭───────────────────╮                              │
│  │ 8D Report 양식... │  ← Streaming                 │
│  │ ▎                 │  ← cursor                    │
│  ╰───────────────────╯                              │
│                                                      │
│  ⚡ Gemini → Ollama 폴백 중                         │ ← StreamStatus
├──────────────────────────────────────────────────────┤
│  [textarea ──────────────] [▶ 전송] [⏹ 중지]       │ ← Composer
└──────────────────────────────────────────────────────┘
```

### 8-2. 핵심 코드 골격

```tsx
export function Chat() {
  const { t, i18n } = useTranslation();
  const { messages, mode, sendMessage, abort } = useChatStore();
  const sse = useSSE({
    onToken: (chunk) => useChatStore.getState().appendToActive(chunk),
    onMetadata: (meta) => useChatStore.getState().updateActiveMeta(meta),
    onDone: (final) => useChatStore.getState().finalizeActive(final),
    onError: (msg) => useChatStore.getState().errorActive(msg),
  });

  return (
    <ErrorBoundary fallback={<ChatErrorFallback />}>
      <div className="page chat-page">
        <ChatHeader mode={mode} onModeChange={useChatStore.getState().setMode} />
        <MessageList messages={messages} streamingText={sse.text} streamingMeta={sse.meta} />
        <StreamStatus isStreaming={sse.isStreaming} meta={sse.meta} />
        <InputComposer
          disabled={sse.isStreaming}
          onSend={(text) => sendMessage(text, sse.start, i18n.language as 'ko' | 'en')}
          onStop={() => { sse.stop(); abort(); }}
        />
      </div>
    </ErrorBoundary>
  );
}
```

### 8-3. 네비게이션 차단 (C-2-1 v3.4)
스트리밍 중 LeftSidebar 모듈 버튼 disabled. `useChatStore.isStreaming` 을 `useUIStore.lockNavigation` 에 동기화 — Day 1 LeftSidebar 가 이미 disabled prop 지원하면 그대로, 미지원이면 +5줄 추가.

---

## 9. `onboarding.ts` API 클라이언트

### 9-1. 시그니처

```typescript
// src/api/onboarding.ts (신규)
import { useAuthStore } from '@store/auth';

const BASE = import.meta.env.VITE_API_BASE_URL || '/api';

export function buildChatUrl(): string {
  return `${BASE}/onboarding/chat`;
}

export function authHeaders(): Record<string, string> {
  const token = useAuthStore.getState().accessToken;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export interface ChatBody {
  query: string;
  mode: string;
  history?: { role: string; content: string }[];
  language?: string;
}

// useSSE.start() 가 직접 fetch 하므로 본 파일은 URL/헤더 빌더 위주.
// 비스트리밍 health 체크용 함수 제공:

export async function fetchOnboardingHealth() {
  const res = await fetch(`${BASE}/onboarding/health`, { headers: authHeaders() });
  if (!res.ok) throw new Error(`health ${res.status}`);
  return res.json() as Promise<{ providers: string[]; circuit: Record<string, string> }>;
}
```

### 9-2. Vite proxy (필요 시)

```typescript
// vite.config.ts
server: {
  proxy: {
    '/api': {
      target: 'http://localhost:8000',
      changeOrigin: true,
      // SSE 호환 — keepAlive
      ws: false,
    },
  },
},
```

또는 `VITE_API_BASE_URL=http://localhost:8000/api` 로 직접 호출 + 백엔드 CORS 허용. **Vite proxy 권장** — 동일 origin 으로 보여 인증 쿠키/CORS 부담 0.

---

## 10. 듀얼 모드 (교육/업무) 사양

### 10-1. UI 토글

`<ModeToggle>` — `[교육] [업무]` 두 버튼. 활성 버튼은 GlassPanel `data-active="true"` 스타일. `useChatStore.mode` 와 양방향.

### 10-2. 모드 차이

| 모드 | 컨텍스트 토큰 예산 | History 턴 수 | 시각 큐 |
|---|---:|---:|---|
| **교육** | 3000자 | 6턴 | 푸른 톤 + "📚 학습 모드" |
| **업무** | 2000자 | 4턴 | 주황 톤 + "⚡ 즉답 모드" |

### 10-3. 백엔드 호환성
현재 백엔드는 `LLMMode` enum (chat / chat_korean / draft / ...) 만 받음. 듀얼 모드는 **프론트 측 history 트리밍 + 향후 백엔드 `context_budget` 파라미터 추가** 로 처리. Day 4 에서는 history 길이만 분기, 백엔드 변경은 Day 5 이후.

---

## 11. Zustand 채팅 스토어

### 11-1. `src/store/chat.ts` (신규, ~110줄)

```typescript
import { create } from 'zustand';
import type { ChatMessage, ChatMode } from '@/types/chat';
import type { SSEStartArgs } from '@/hooks/useSSE';
import { buildChatUrl } from '@/api/onboarding';

interface ChatState {
  messages: ChatMessage[];
  mode: ChatMode;
  activeMessageId: string | null;
  
  setMode: (m: ChatMode) => void;
  sendMessage: (
    text: string,
    sseStart: (args: SSEStartArgs) => Promise<void>,
    language: 'ko' | 'en'
  ) => Promise<void>;
  appendToActive: (chunk: string) => void;
  updateActiveMeta: (meta: Record<string, unknown>) => void;
  finalizeActive: (final: Record<string, unknown>) => void;
  errorActive: (errMsg: string) => void;
  abort: () => void;
  reset: () => void;
}

export const useChatStore = create<ChatState>((set, get) => ({
  messages: [],
  mode: 'education',
  activeMessageId: null,

  setMode: (m) => set({ mode: m }),

  sendMessage: async (text, sseStart, language) => {
    const userMsg: ChatMessage = {
      id: crypto.randomUUID(), role: 'user', content: text,
      createdAt: Date.now(), status: 'done',
    };
    const assistantMsg: ChatMessage = {
      id: crypto.randomUUID(), role: 'assistant', content: '',
      createdAt: Date.now(), status: 'streaming',
    };
    set((s) => ({
      messages: [...s.messages, userMsg, assistantMsg],
      activeMessageId: assistantMsg.id,
    }));

    const llmMode = language === 'ko' ? 'chat_korean' : 'chat';
    const turnCount = get().mode === 'education' ? 6 : 4;
    const history = get().messages
      .filter((m) => m.role !== 'system')
      .slice(-turnCount)
      .map((m) => ({ role: m.role === 'user' ? 'user' : 'model', content: m.content }));

    await sseStart({
      url: buildChatUrl(),
      body: { query: text, mode: llmMode, history, language },
    });
  },

  appendToActive: (chunk) => set((s) => ({
    messages: s.messages.map((m) =>
      m.id === s.activeMessageId ? { ...m, content: m.content + chunk } : m
    ),
  })),

  updateActiveMeta: (meta) => set((s) => ({
    messages: s.messages.map((m) =>
      m.id === s.activeMessageId
        ? { ...m, meta: { ...m.meta, ...meta } }
        : m
    ),
  })),

  finalizeActive: (final) => set((s) => ({
    messages: s.messages.map((m) =>
      m.id === s.activeMessageId
        ? { ...m, status: 'done', meta: { ...m.meta, ...final } }
        : m
    ),
    activeMessageId: null,
  })),

  errorActive: (errMsg) => set((s) => ({
    messages: s.messages.map((m) =>
      m.id === s.activeMessageId
        ? { ...m, status: 'error', meta: { ...m.meta, error: errMsg } }
        : m
    ),
    activeMessageId: null,
  })),

  abort: () => set((s) => ({
    messages: s.messages.map((m) =>
      m.id === s.activeMessageId
        ? { ...m, status: 'done', content: m.content + ' [중지됨]' }
        : m
    ),
    activeMessageId: null,
  })),

  reset: () => set({ messages: [], activeMessageId: null }),
}));
```

---

## 12. i18n 키 신규 (한·영)

### 12-1. 추가 키

| Key | 한 | 영 |
|---|---|---|
| `chat.title` | C · 온보딩 | C · Onboarding |
| `chat.subtitle` | AI 업무 보조 | AI Work Assistant |
| `chat.mode.education` | 교육 | Education |
| `chat.mode.work` | 업무 | Work |
| `chat.mode.educationHint` | 신입 학습용 — 상세 설명 | New-hire learning — detailed |
| `chat.mode.workHint` | 즉답 모드 — 간결 | Quick-answer mode — concise |
| `chat.composer.placeholder` | 무엇이든 물어보세요 | Ask anything |
| `chat.composer.send` | 전송 | Send |
| `chat.composer.stop` | 중지 | Stop |
| `chat.empty.title` | 대화를 시작해보세요 | Start a conversation |
| `chat.empty.examples.0` | "8D Report 양식 어디?" | "Where is the 8D Report form?" |
| `chat.empty.examples.1` | "REACH 규제 현황은?" | "What is REACH compliance status?" |
| `chat.empty.examples.2` | "신차 PPAP 절차?" | "PPAP process for new vehicle?" |
| `chat.status.streaming` | 응답 생성 중... | Generating response... |
| `chat.status.fallback` | {{from}} 실패 → {{to}} 사용 중 | {{from}} failed → using {{to}} |
| `chat.status.done` | 완료 ({{model}}) | Done ({{model}}) |
| `chat.status.error` | 응답 실패 | Response failed |
| `chat.provider.gemini` | Gemini 2.5 Pro | Gemini 2.5 Pro |
| `chat.provider.ollama` | Ollama (사내) | Ollama (on-prem) |
| `chat.provider.lm_studio` | LM Studio | LM Studio |

총 ~30 키 × 2 언어 = ~60 줄 JSON 추가.

---

## 13. 단계 분할 — Phase 1~3

### Phase 1 — 데이터 모델 + 훅 + 스토어 (~30분)
- [ ] `src/types/chat.ts` 작성
- [ ] `src/hooks/useSSE.ts` 갱신 (백엔드 표준)
- [ ] `src/api/onboarding.ts` 신규 (URL 빌더 + health)
- [ ] `src/store/chat.ts` 신규 Zustand
- [ ] Vite proxy 설정 (`vite.config.ts` `/api` → `:8000`)

검증: `npm run build` (TS strict 컴파일 0 오류)

### Phase 2 — UI 컴포넌트 (~45분)
- [ ] `src/components/chat/MessageBubble.tsx`
- [ ] `src/components/chat/MessageList.tsx` (auto-scroll)
- [ ] `src/components/chat/InputComposer.tsx`
- [ ] `src/components/chat/ModeToggle.tsx`
- [ ] `src/components/chat/ProviderBadge.tsx`
- [ ] `src/components/chat/StreamStatus.tsx`
- [ ] `src/routes/chat.tsx` 본격 구현 (placeholder 폐기)
- [ ] i18n 한·영 키 30개 추가

검증: `/chat` 라우트 200 + 시각 검수

### Phase 3 — 통합 검증 (~30분)
- [ ] FastAPI 백엔드 시작 (`uvicorn backend.main:app --port 8000`)
- [ ] 브라우저 `/chat` 진입 → 메시지 입력 → SSE 토큰 표시 확인
- [ ] 네비게이션 차단 (스트리밍 중 사이드바 disabled)
- [ ] 듀얼 모드 토글 동작
- [ ] AbortController — 중지 버튼 즉시 반영
- [ ] 폴백 시뮬레이션 — `.env` 의 `GEMINI_API_KEY` 무효화 → Ollama 폴백 → ProviderBadge 변경

검증: 본선 시연 시나리오 1회 완주

---

## 14. 검증 체크리스트

### 14-1. 코드 품질
- [ ] `npm run build` (TS strict) 0 오류
- [ ] `npm run lint` 0 경고
- [ ] 신규 컴포넌트 모두 ErrorBoundary 보호
- [ ] 신규 훅/스토어 jsdoc 또는 타입으로 자동 문서화
- [ ] 외부 의존성 추가 0 (모두 기존 풀에서)

### 14-2. 기능
- [ ] 한국어 입력 → `chat_korean` 모드 → Gemini 2.5 Pro 응답
- [ ] 영어 입력 → `chat` 모드 → Gemini 2.5 Pro 응답
- [ ] Gemini 키 무효 → 자동 Ollama 폴백 → UI 인디케이터 표시
- [ ] 듀얼 모드 토글 — 교육/업무 history 길이 차이
- [ ] 메시지 markdown 렌더링 (코드블록 / 표 / 리스트)
- [ ] 스트리밍 중 사이드바 모듈 disabled
- [ ] 중지 버튼 — AbortController 즉시 반응

### 14-3. UX
- [ ] Liquid Glass 일관성 (Dashboard / Search 와 동일 톤)
- [ ] 모바일 768/1024 반응형 (메시지 풍선 max-width 80%)
- [ ] 라이트/다크/AUTO 테마 모두 정상
- [ ] 빈 상태 — 예시 질문 3개 표시
- [ ] 에러 상태 — 재시도 버튼

### 14-4. 본선 시연 시나리오
- [ ] **시연 1**: "8D Report 양식 어디?" → Gemini 응답
- [ ] **시연 2**: 키 차단 → Ollama qwen3.5:9b 자동 폴백 → ProviderBadge 갱신
- [ ] **시연 3**: 듀얼 모드 토글 → 같은 질문 → 응답 길이 차이

---

## 15. 위험 + 완화

| # | 위험 | 영향 | 완화 |
|:--:|---|:--:|---|
| 1 | **CORS 에러** :5173 ↔ :8000 | 🔴 | Vite proxy 설정 — 동일 origin 으로 보임 |
| 2 | **Firebase ID Token** 미설정 | 🔴 | `useAuthStore.accessToken` 에 ID Token 저장되는지 Phase 1 검증 |
| 3 | **백엔드 미가동** | 🟡 | Phase 3 진입 전 `curl :8000/api/onboarding/health` 확인 절차 |
| 4 | **SSE keepAlive 끊김** | 🟡 | `fetchEventSource` `openWhenHidden:true` (이미 적용) |
| 5 | **react-markdown XSS** | 🟢 | `react-markdown` 기본 sanitizer + remark-gfm 만 사용 |
| 6 | **스트리밍 중 페이지 이탈** | 🟡 | `beforeunload` 경고 + 사이드바 disabled |
| 7 | **컨텍스트 토큰 초과** | 🟡 | history 슬라이스 (교육 6턴 / 업무 4턴) — 백엔드도 Phase 2 에서 mode 별 컨텍스트 길이 제어 |
| 8 | **모델 비교 UI 사용자 결정 미정** | 🟢 | Day 4 에는 자동 라우팅만 — Day 5 보강에서 `[자동/Gemini/qwen3.5/gemma4]` selectbox 추가 |
| 9 | **Plotly 페이지와 동시 렌더 시 메모리** | 🟢 | chat 페이지는 Plotly 미사용 |
| 10 | **AbortController 미지원 브라우저** | 🟢 | 본선 데모는 Chrome 130+ 가정 — `AbortSignal.any?.()` optional chain 으로 폴백 |

---

## 16. Day 4 비스코프 (Day 5 이후)

| # | 항목 | 일정 | 사양 |
|:--:|---|---|---|
| 1 | SOP 8종 가이드 카드 | Day 5 | C-2-3 |
| 2 | 협업 시나리오 5종 트리거 | Day 5 | C-2-4 |
| 3 | 비전 이미지 업로드 (`/chat/vision`) | Day 5 | C-2-5 + 기능 C |
| 4 | 파일 업로드 20+ 확장자 (`/upload`) | Day 5 | 기능 C |
| 5 | 다운로드 영구화 (DOCX/XLSX/CSV) | Day 5 | C 기능 |
| 6 | 피드백 이모지 (👍/👎) → RTDB | Day 5 | Firebase 통합 |
| 7 | Firestore `chat_history` 영구화 | Day 5 | Firebase 통합 |
| 8 | 부서 라우터 31종 | Day 5 | C-2-8 |
| 9 | 용어집 매처 297항목 | Day 5 | C-2-9 |
| 10 | 대화 요약 메모리 | Day 5 | C-2-10 |
| 11 | 모델 비교 selectbox `[자동/Gemini/qwen3.5/gemma4]` | Day 5 또는 Day 12 | 시연 차별점 |
| 12 | TF-IDF intent 분류기 (백엔드) | Day 13 | LLM 라우터 보강 |

---

## 17. 시간 분배표 (총 1.5~2h)

| 시간대 | 작업 |
|:--:|---|
| 00:00 ~ 00:05 | 백엔드 시작 + `/health` 확인 + Vite proxy 설정 |
| 00:05 ~ 00:35 | Phase 1 — types + useSSE 갱신 + onboarding API + chat store |
| 00:35 ~ 00:50 | Phase 1 검증 — TS strict 컴파일 + 단위 import 테스트 |
| 00:50 ~ 01:25 | Phase 2 — 컴포넌트 6개 + chat.tsx 본격 구현 |
| 01:25 ~ 01:35 | Phase 2 — i18n 한·영 키 추가 |
| 01:35 ~ 01:55 | Phase 3 — 브라우저 통합 검증 + 본선 시연 시나리오 3건 |
| 01:55 ~ 02:00 | 마감 — 검증 체크리스트 점검 + 알려진 이슈 보고 |

---

## 18. 사용자 결정 대기 사항 (실행 직전)

| # | 결정 | 권장 |
|:--:|---|---|
| 1 | **위임 방식** — 직접 실행 vs `executor` 위임 vs `designer + executor` 병렬 | `executor` (opus) 백그라운드 |
| 2 | **모델 비교 selectbox** — Day 4 vs Day 5 | **Day 5** (자동 라우팅 안정 후 추가) |
| 3 | **백엔드 자동 시작 스크립트** | 사용자가 별도 터미널에서 `uvicorn` 실행 — 통합 검증 시점에 |
| 4 | **Vite proxy vs CORS** | **Vite proxy** (vite.config.ts 갱신) |

---

## 변경 이력

| 버전 | 날짜 | 변경 |
|---|---|---|
| **1.0** | 2026-04-27 | 초안 — 18 섹션 / 신규 11 파일 / Phase 3분할 / 검증 체크리스트 |

---

**관련 문서**:
- [LLM_ROUTER_PLAN.md](LLM_ROUTER_PLAN.md) — 백엔드 Phase 1~3 (완료)
- [FINAL_17DAY_PLAN.md](FINAL_17DAY_PLAN.md) — Day 4 위치 (L310)
- [DAY3_PLAN.md](DAY3_PLAN.md) — useSSE 훅 + 13 컴포넌트 라이브러리
- [WEB_DESIGN_SPECIFICATION.md](WEB_DESIGN_SPECIFICATION.md) — Liquid Glass 토큰
- [FEATURE_SPECIFICATION.md](../features/FEATURE_SPECIFICATION.md) — C 도우미 사양 C-2-1~C-2-10
