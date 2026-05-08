// Day 4 — C AI 도우미 채팅 스토어 (Zustand)
// useSSE 훅은 따로 두고, store 는 메시지 상태와 history 트리밍만 책임.
// Day 5 — 시나리오/액션 매칭 즉시 응답 + Firestore 영속 (loadHistory) 추가.

import { create } from 'zustand';
import type {
  AttachmentSlot,
  ChatMessage,
  ChatMode,
  ChatMessageMeta,
  ChatRequestBody,
  ForceProvider,
  HistoryTurn,
  LLMMode,
} from '@/types/chat';
import type { ScenarioCard } from '@api/scenarios';
import type { ActionResultPayload } from '@api/actions';
import { saveMessage } from '@lib/firestore-chat';

/** Firestore 영속 — fire-and-forget. saveMessage 내부에서 auth.currentUser?.uid 검사 후 noop. */
function persistMessage(message: ChatMessage): void {
  void saveMessage(message);
}

/** Day 5++ — 세션 ID 생성 (#A47-2026 패턴, DAY5_PLUS_HUD_PLAN Section 7-1). */
function generateSessionId(): string {
  const year = new Date().getFullYear();
  const seq = Math.floor(Math.random() * 999) + 1; // 1~999
  const padded = String(seq).padStart(2, '0');
  return `A${padded}-${year}`;
}

interface ChatState {
  messages: ChatMessage[];
  mode: ChatMode;
  activeMessageId: string | null;
  /** Phase 4-B — 첨부 슬롯 (단일). */
  attachment: AttachmentSlot | null;
  /** Phase 5 — 강제 (provider, model). null 이면 자동 폴백 체인. */
  forceProvider: ForceProvider | null;
  /** Day 5++ — 세션 ID (#A47-2026). 페이지 진입 시 1회 생성. */
  sessionId: string;
  /** Day 5++ — 직전 응답의 의도 분류 시간 (mock). */
  intentMs: number | null;

  setMode: (m: ChatMode) => void;
  setForceProvider: (p: ForceProvider | null) => void;
  /** Day 5++ — 의도 분류 시간(ms) 갱신. */
  setIntentMs: (n: number | null) => void;
  attachVision: (file: File) => void;
  attachFile: (file: File) => void;
  clearAttachment: () => void;

  /** user 메시지 + assistant placeholder 를 한 번에 푸시. SSE 시작용 body 를 반환. */
  beginTurn: (text: string, language: 'ko' | 'en') => ChatRequestBody;

  /** 비전 turn — 사용자 메시지에 imageUrl 메타 부여 + assistant placeholder. */
  beginVisionTurn: (text: string) => void;

  /** 파일 turn — 추출된 텍스트를 file_context 로 주입 + 메시지에 fileName/fileUrl 메타. */
  beginFileTurn: (
    text: string,
    language: 'ko' | 'en',
    file: { fileName: string; extractedText: string; fileUrl?: string },
  ) => ChatRequestBody;

  /** 시나리오 매칭 즉시 응답 — user 메시지 + assistant(card) 둘 다 푸시 (LLM 호출 X). */
  pushScenarioCard: (userText: string, card: ScenarioCard) => void;

  /** 업무 액션 즉시 응답 — user 메시지 + assistant(action) 둘 다 푸시 (LLM 호출 X). */
  pushActionResponse: (userText: string, result: ActionResultPayload) => void;

  /** Firestore 등에서 가져온 메시지 목록을 일괄 주입 (페이지 진입 시). */
  setHistory: (messages: ChatMessage[]) => void;

  appendToActive: (chunk: string) => void;
  updateActiveMeta: (meta: Record<string, unknown>) => void;
  /** 활성 turn 의 직전 user 메시지 meta 를 부분 업데이트 (Storage URL 갱신용). */
  updateActiveUserMeta: (patch: Partial<ChatMessageMeta>) => void;
  finalizeActive: (final: Record<string, unknown>) => void;
  errorActive: (errMsg: string) => void;
  abortActive: () => void;
  reset: () => void;
}

const HISTORY_TURN_LIMIT: Record<ChatMode, number> = {
  education: 6,
  work: 4,
};

const CONTEXT_BUDGET: Record<ChatMode, number> = {
  education: 3000,
  work: 2000,
};

function selectLLMMode(language: 'ko' | 'en'): LLMMode {
  return language === 'ko' ? 'chat_korean' : 'chat';
}

function toHistoryTurn(m: ChatMessage): HistoryTurn | null {
  if (m.role === 'system') return null;
  if (!m.content.trim()) return null;
  return { role: m.role, content: m.content };
}

function mapMetaUpdate(meta: Record<string, unknown>): Partial<ChatMessageMeta> {
  const out: Partial<ChatMessageMeta> = {};
  if (typeof meta.provider === 'string') out.provider = meta.provider;
  if (typeof meta.model === 'string') out.model = meta.model;
  if ('fallback_from' in meta) out.fallbackFrom = meta.fallback_from as string | null;
  if (typeof meta.final_provider === 'string') out.finalProvider = meta.final_provider;
  if (typeof meta.final_model === 'string') out.finalModel = meta.final_model;
  if (typeof meta.ttft_ms === 'number') out.ttftMs = meta.ttft_ms;
  if (typeof meta.latency_ms === 'number') out.latencyMs = meta.latency_ms;
  // Phase 4-B — 백엔드가 image_url 메타를 echo 할 수 있음
  if (typeof meta.image_url === 'string') out.imageUrl = meta.image_url;
  if (typeof meta.imageUrl === 'string') out.imageUrl = meta.imageUrl;
  // Day 5++ — 카테고리/토큰 (백엔드 echo 시 채워짐, 없으면 store 측에서 분기 시 직접 부착).
  if (
    typeof meta.category === 'string' &&
    ['sop', 'scenario', 'action', 'chat', 'vision'].includes(meta.category)
  ) {
    out.category = meta.category as ChatMessageMeta['category'];
  }
  if (typeof meta.total_tokens === 'number') out.totalTokens = meta.total_tokens;
  if (typeof meta.totalTokens === 'number') out.totalTokens = meta.totalTokens;
  return out;
}

export const useChatStore = create<ChatState>((set, get) => ({
  messages: [],
  mode: 'education',
  activeMessageId: null,
  attachment: null,
  forceProvider: null,
  sessionId: generateSessionId(),
  intentMs: null,

  setMode: (m) => set({ mode: m }),
  setForceProvider: (p) => set({ forceProvider: p }),
  setIntentMs: (n: number | null) => set({ intentMs: n }),
  attachVision: (file) => set({ attachment: { kind: 'image', file } }),
  attachFile: (file) => set({ attachment: { kind: 'file', file } }),
  clearAttachment: () => set({ attachment: null }),

  beginVisionTurn: (text) => {
    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: text,
      createdAt: Date.now(),
      status: 'done',
      meta: { imageUrl: 'pending' }, // Storage 업로드 후 useVisionStream 이 실제 URL 로 갱신
    };
    const assistantMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: '',
      createdAt: Date.now(),
      status: 'streaming',
      meta: { category: 'vision' },
    };
    set((s) => ({
      messages: [...s.messages, userMsg, assistantMsg],
      activeMessageId: assistantMsg.id,
    }));
  },

  beginFileTurn: (text, language, file) => {
    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: text,
      createdAt: Date.now(),
      status: 'done',
      meta: { fileName: file.fileName, fileUrl: file.fileUrl, extractedText: file.extractedText },
    };
    const assistantMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: '',
      createdAt: Date.now(),
      status: 'streaming',
      meta: { category: 'chat' },
    };
    const turnCount = HISTORY_TURN_LIMIT[get().mode];
    const trimmed = get()
      .messages.slice(-turnCount * 2)
      .map(toHistoryTurn)
      .filter((m): m is HistoryTurn => m !== null);

    set((s) => ({
      messages: [...s.messages, userMsg, assistantMsg],
      activeMessageId: assistantMsg.id,
    }));

    const body: ChatRequestBody = {
      query: text,
      mode: selectLLMMode(language),
      history: trimmed,
      language,
      file_context: file.extractedText,
    };
    return body;
  },

  beginTurn: (text, language) => {
    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: text,
      createdAt: Date.now(),
      status: 'done',
    };
    const assistantMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: '',
      createdAt: Date.now(),
      status: 'streaming',
      meta: { category: 'chat' },
    };

    const turnCount = HISTORY_TURN_LIMIT[get().mode];
    const trimmed = get()
      .messages.slice(-turnCount * 2)
      .map(toHistoryTurn)
      .filter((m): m is HistoryTurn => m !== null);

    set((s) => ({
      messages: [...s.messages, userMsg, assistantMsg],
      activeMessageId: assistantMsg.id,
    }));

    const body: ChatRequestBody = {
      query: text,
      mode: selectLLMMode(language),
      history: trimmed,
      language,
    };
    void CONTEXT_BUDGET; // 향후 백엔드 context_budget 도입 시 사용 (Day 5+)
    return body;
  },

  pushScenarioCard: (userText, card) => {
    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: userText,
      createdAt: Date.now(),
      status: 'done',
    };
    const assistantMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: card.formatted_text,
      createdAt: Date.now(),
      status: 'done',
      source: 'scenario',
      meta: { scenarioCard: card, category: 'scenario' },
    };
    set((s) => ({
      messages: [...s.messages, userMsg, assistantMsg],
      activeMessageId: null,
    }));
    persistMessage(userMsg);
    persistMessage(assistantMsg);
  },

  pushActionResponse: (userText, result) => {
    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: userText,
      createdAt: Date.now(),
      status: 'done',
    };
    const assistantMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: result.display_text,
      createdAt: Date.now(),
      status: 'done',
      source: 'action',
      meta: { actionResult: result, category: 'action' },
    };
    set((s) => ({
      messages: [...s.messages, userMsg, assistantMsg],
      activeMessageId: null,
    }));
    persistMessage(userMsg);
    persistMessage(assistantMsg);
  },

  setHistory: (messages) => set({ messages, activeMessageId: null }),

  appendToActive: (chunk) =>
    set((s) => ({
      messages: s.messages.map((m) =>
        m.id === s.activeMessageId ? { ...m, content: m.content + chunk } : m,
      ),
    })),

  updateActiveMeta: (meta) =>
    set((s) => ({
      messages: s.messages.map((m) =>
        m.id === s.activeMessageId
          ? { ...m, meta: { ...(m.meta ?? {}), ...mapMetaUpdate(meta) } }
          : m,
      ),
    })),

  updateActiveUserMeta: (patch) =>
    set((s) => {
      if (!s.activeMessageId) return s;
      const idx = s.messages.findIndex((m) => m.id === s.activeMessageId);
      if (idx <= 0) return s;
      const userIdx = idx - 1;
      const prev = s.messages[userIdx];
      if (!prev || prev.role !== 'user') return s;
      const next = { ...prev, meta: { ...(prev.meta ?? {}), ...patch } };
      const messages = [...s.messages];
      messages[userIdx] = next;
      return { messages };
    }),

  finalizeActive: (final) => {
    let finalized: ChatMessage | null = null;
    let userToPersist: ChatMessage | null = null;
    set((s) => {
      const updatedMessages = s.messages.map((m) => {
        if (m.id === s.activeMessageId) {
          const next = {
            ...m,
            status: 'done' as const,
            meta: { ...(m.meta ?? {}), ...mapMetaUpdate(final) },
          };
          finalized = next;
          return next;
        }
        return m;
      });
      // 직전 user 메시지도 한 번 영속 (turn 시작 시 push 됐지만 status='done' 으로 정착)
      if (s.activeMessageId) {
        const idx = updatedMessages.findIndex((m) => m.id === s.activeMessageId);
        if (idx > 0) {
          const prev = updatedMessages[idx - 1];
          if (prev?.role === 'user') userToPersist = prev;
        }
      }
      return { messages: updatedMessages, activeMessageId: null };
    });
    const u: ChatMessage | null = userToPersist;
    const f: ChatMessage | null = finalized;
    if (u !== null) persistMessage(u);
    if (f !== null) persistMessage(f);
  },

  errorActive: (errMsg) =>
    set((s) => ({
      messages: s.messages.map((m) =>
        m.id === s.activeMessageId
          ? { ...m, status: 'error', meta: { ...(m.meta ?? {}), error: errMsg } }
          : m,
      ),
      activeMessageId: null,
    })),

  abortActive: () =>
    set((s) => ({
      messages: s.messages.map((m) =>
        m.id === s.activeMessageId
          ? { ...m, status: 'done', content: m.content + (m.content ? ' ' : '') + '[중지됨]' }
          : m,
      ),
      activeMessageId: null,
    })),

  reset: () => set({ messages: [], activeMessageId: null, attachment: null }),
}));
