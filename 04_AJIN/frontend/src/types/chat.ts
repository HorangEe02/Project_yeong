// Day 4 — C AI 도우미 채팅 데이터 모델
// 백엔드 스키마 OnboardingChatRequest 와 1:1 정합 (backend/schemas/onboarding.py)
// Day 5 — 시나리오/액션 메타 + source 필드 추가 (LLM 호출 0회 분기)

import type { ScenarioCard } from '@api/scenarios';
import type { ActionResultPayload } from '@api/actions';

export type MessageRole = 'user' | 'assistant' | 'system';

export type MessageStatus = 'pending' | 'streaming' | 'done' | 'error';

/** 메시지의 출처 — LLM 호출 0회 응답을 식별하기 위한 메타. */
export type MessageSource = 'llm' | 'scenario' | 'action';

/** Day 5++ — AI 응답 카테고리 (헤더 [SOP_GUIDE] / [SCENARIO] / [ACTION] / [CHAT] / [VISION]). */
export type MessageCategory = 'sop' | 'scenario' | 'action' | 'chat' | 'vision';

export interface ChatMessageMeta {
  provider?: string; // "gemini" | "ollama" | "lm_studio"
  model?: string; // "gemini-2.5-pro" | "qwen3.5:9b" | "gemma4:e4b" ...
  fallbackFrom?: string | null;
  finalProvider?: string;
  finalModel?: string;
  ttftMs?: number;
  latencyMs?: number;
  error?: string;
  /** 시나리오 매칭 카드 — source='scenario' 일 때만 채워짐. */
  scenarioCard?: ScenarioCard;
  /** 업무 액션 결과 — source='action' 일 때만 채워짐. */
  actionResult?: ActionResultPayload;
  /** Phase 4 — 비전 첨부 (Storage public URL). */
  imageUrl?: string;
  /** Phase 4 — 문서 첨부 (Storage URL + 추출 텍스트). */
  fileUrl?: string;
  fileName?: string;
  extractedText?: string;
  /** Phase 5 — 사용자가 강제 선택한 (provider, model). */
  forcedProvider?: string;
  forcedModel?: string;
  /** Day 5++ — AI 응답 카테고리. 헤더 배지 [SOP_GUIDE] 등에 사용. */
  category?: MessageCategory;
  /** Day 5++ — 누적 토큰 (Gemini SDK usage_metadata.total_token_count 또는 mock). */
  totalTokens?: number;
}

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  createdAt: number;
  status: MessageStatus;
  meta?: ChatMessageMeta;
  /** 메시지 출처 — Day 5: 'scenario' / 'action' 은 LLM 호출 없이 즉시 응답. */
  source?: MessageSource;
}

export type ChatMode = 'education' | 'work';

export type LLMMode = 'chat' | 'chat_korean' | 'draft' | 'summary' | 'intent';

// 백엔드로 보내는 history 항목. 백엔드 ChatMessage(role="user"|"assistant", content)
export interface HistoryTurn {
  role: 'user' | 'assistant';
  content: string;
}

export interface ChatRequestBody {
  query: string;
  mode: LLMMode;
  history: HistoryTurn[];
  language: 'ko' | 'en';
  department?: string;
  /** Phase 4-B — 첨부 파일에서 추출된 텍스트 (백엔드 file_context 로 매핑). */
  file_context?: string;
  /** Phase 5 — 단일 (provider, model) 강제. 백엔드 ChatRequest.force_provider 로 매핑. */
  force_provider?: [string, string];
}

/** Phase 4-B — 비전/파일 첨부 슬롯 (단일). 한 번에 하나만 첨부. */
export type AttachmentKind = 'image' | 'file';

export interface AttachmentSlot {
  kind: AttachmentKind;
  file: File;
}

/** Phase 5 — 강제 모델 선택 (자동이면 null). */
export interface ForceProvider {
  provider: string; // "gemini" | "ollama"
  model: string; // "gemini-2.5-pro" | "qwen3.5:9b" | "gemma4:e4b"
}

/** Day 5++ — 좌측 컬럼 하단 QuickPrompts chip (DAY5_PLUS_HUD_PLAN Section 5-bis). */
export type QuickPromptCategory = 'scenario' | 'action' | 'sop' | 'general';

export interface QuickPrompt {
  id: string;
  /** chip 본문 (한글 짧은 라벨) */
  label: string;
  category: QuickPromptCategory;
  /** 입력창에 채워질 실제 텍스트 — 시나리오/액션 매처가 트리거되도록 작성. */
  promptText: string;
  /** true 면 chip 클릭 시 즉시 전송. 기본 true (시연 가속). */
  autoSend?: boolean;
}

export const DEFAULT_QUICK_PROMPTS: QuickPrompt[] = [
  {
    id: 'qp-8d',
    label: '8D Report 양식 어디?',
    category: 'scenario',
    promptText: '품질팀에서 8D 올려달라는데?',
  },
  {
    id: 'qp-ecn',
    label: 'ECN 발행 절차',
    category: 'scenario',
    promptText: '설계 변경 요청 왔어',
  },
  {
    id: 'qp-cpk',
    label: 'SPC Cpk 떨어짐 시정',
    category: 'scenario',
    promptText: 'Cpk 1.0 떨어졌어',
  },
  {
    id: 'qp-ppap',
    label: '신차 PPAP 절차',
    category: 'scenario',
    promptText: '현대 신차 양산 시작',
  },
  {
    id: 'qp-safety',
    label: '안전 점검 체크리스트',
    category: 'scenario',
    promptText: '안전 점검 어떻게 해?',
  },
  {
    id: 'qp-reach',
    label: 'REACH 규제 현황',
    category: 'action',
    promptText: 'REACH 규제 현황?',
  },
  {
    id: 'qp-error',
    label: '에러코드 E001',
    category: 'action',
    promptText: '에러코드 E001',
  },
];
