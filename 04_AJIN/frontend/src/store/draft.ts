// Day 8 Phase 2 — Draft (Module B) Zustand store.
// 현재 작성 중인 초안 + 이력 + UI 상태 관리.
// Plan v1.0 — provider/modelId 셀렉터 + stage 진행 상태 추가.

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type {
  CCRecResponse,
  DiffResponse,
  DocCategory,
  DocTypeMeta,
  DraftDocumentMeta,
  DraftToneId,
  QualityResponse,
} from '@/types/draft';

export type LLMProvider = 'ollama' | 'gemini';

export interface StreamStage {
  name: string; // 'classify' | 'rag' | 'security' | 'llm' | 'render'
  status: 'running' | 'ok' | 'warn' | 'error';
  meta?: Record<string, unknown>;
  ts: number; // 수신 시각 (UI 정렬용)
}

interface DraftState {
  // ── 작성 중 (모든 사용자 입력) ─────────────────
  context: DocCategory;
  docTypeId: string;
  toneId: string;
  meta: DraftDocumentMeta;
  userRequest: string; // 자유 형식 요청 (텍스트박스)

  // ── 모델 셀렉터 (Plan v1.0) ────────────────────
  provider: LLMProvider;
  modelId: string;

  // ── 생성 결과 ─────────────────────────────────
  output: string;
  isStreaming: boolean;
  lastSavedContent: string | null; // diff 비교용 (편집 전 LLM 원본)
  hasEdits: boolean; // user 편집 여부
  stages: StreamStage[]; // SSE stage 이벤트 누적

  // ── API 응답 캐시 ──────────────────────────────
  docTypes: DocTypeMeta[];
  quality: QualityResponse | null;
  ccRec: CCRecResponse | null;
  diff: DiffResponse | null;

  // ── 액션 ───────────────────────────────────────
  setContext: (c: DocCategory) => void;
  setDocTypeId: (id: string) => void;
  setToneId: (t: DraftToneId | string) => void;
  setMeta: (patch: Partial<DraftDocumentMeta>) => void;
  setUserRequest: (s: string) => void;
  setProvider: (p: LLMProvider) => void;
  setModelId: (m: string) => void;
  setOutput: (s: string, opts?: { fromUser?: boolean }) => void;
  appendStreamToken: (chunk: string) => void;
  setStreaming: (on: boolean) => void;
  pushStage: (s: Omit<StreamStage, 'ts'>) => void;
  clearStages: () => void;
  resetGeneration: () => void;

  setDocTypes: (items: DocTypeMeta[]) => void;
  setQuality: (q: QualityResponse | null) => void;
  setCCRec: (cc: CCRecResponse | null) => void;
  setDiff: (d: DiffResponse | null) => void;
}

export const useDraftStore = create<DraftState>()(
  persist(
    (set) => ({
      context: 'internal',
      docTypeId: '',
      toneId: 'formal_internal',
      meta: { title: '', recipient: '', cc: [], custom_fields: {} },
      userRequest: '',

      provider: 'ollama',
      modelId: 'qwen3.5:9b',

      output: '',
      isStreaming: false,
      lastSavedContent: null,
      hasEdits: false,
      stages: [],

      docTypes: [],
      quality: null,
      ccRec: null,
      diff: null,

      setContext: (context) => set({ context }),
      setDocTypeId: (docTypeId) => set({ docTypeId }),
      setToneId: (toneId) => set({ toneId }),
      setMeta: (patch) =>
        set((s) => ({ meta: { ...s.meta, ...patch } })),
      setUserRequest: (userRequest) => set({ userRequest }),
      setProvider: (provider) => set({ provider }),
      setModelId: (modelId) => set({ modelId }),

      setOutput: (output, opts) =>
        set({
          output,
          hasEdits: !!opts?.fromUser,
        }),
      appendStreamToken: (chunk) =>
        set((s) => ({ output: s.output + chunk })),
      setStreaming: (isStreaming) =>
        set((s) => ({
          isStreaming,
          // 스트리밍 종료 시 LLM 원본 저장 (이후 편집 비교용)
          lastSavedContent: isStreaming ? s.lastSavedContent : s.output,
          hasEdits: isStreaming ? s.hasEdits : false,
        })),
      pushStage: (s) =>
        set((state) => ({
          stages: [...state.stages, { ...s, ts: Date.now() }].slice(-12),
        })),
      clearStages: () => set({ stages: [] }),
      resetGeneration: () =>
        set({
          output: '',
          isStreaming: false,
          lastSavedContent: null,
          hasEdits: false,
          stages: [],
          quality: null,
          ccRec: null,
          diff: null,
        }),

      setDocTypes: (docTypes) => set({ docTypes }),
      setQuality: (quality) => set({ quality }),
      setCCRec: (ccRec) => set({ ccRec }),
      setDiff: (diff) => set({ diff }),
    }),
    {
      name: 'ajin-draft',
      // P2 — provider/modelId 는 persist 에서 제외.
      // 이유: 사용자가 며칠 뒤 다시 접속하면 그 사이 Ollama 가 모델을 내려뒀거나
      // 백엔드가 재배포돼 해당 모델이 더 이상 _build_llm_options 에 노출되지 않을 수 있다.
      // 매 마운트마다 fetchLlmOptions(default_provider/default_id) 가 안전한 기본값을 갱신한다.
      partialize: (state) => ({
        context: state.context,
        docTypeId: state.docTypeId,
        toneId: state.toneId,
        meta: state.meta,
        userRequest: state.userRequest,
      }),
    },
  ),
);
