/**
 * 프론트엔드 측 Chatbot 타입 — 서버 `hospitalChatbot` callable 과 1:1 미러.
 * 서버 원본: mediway/functions/src/chatbot/providers/shared.ts + hospitalChatbot.ts
 */

export type ChatIntent =
  | 'triage'
  | 'hospital_info'
  | 'department_info'
  | 'appointment_help'
  | 'direction'
  | 'general'
  | 'escalate';

export interface ChatbotRequest {
  hospitalId: string;
  userText: string;
  /** 기존 대화 이어쓸 때 지난 호출에서 받은 chatId 재전송 — 첫 호출엔 undefined */
  chatId?: string | null;
}

export interface ChatbotResponse {
  reply: string;
  intent: ChatIntent;
  disclaimer: string;
  /** 서버가 발급/유지하는 session id — 다음 호출 때 재전송하면 히스토리 이어짐 */
  chatId?: string;
  /** rateLimit 은 서버가 내려주지만 UI 에는 노출하지 않음 (policy) */
  rateLimit?: { remainingHour: number; remainingDay: number };
  recommendedDepartments?: string[];
}

/**
 * 프론트 서비스 계층이 Firebase HttpsError 를 normalize 해서 던지는 커스텀 에러.
 * UI 는 `code` 로 분기, `message` 는 그대로 사용자에게 표시 가능 수준.
 */
export type ChatbotErrorCode =
  | 'unauthenticated'
  | 'rate_limited'
  | 'invalid_argument'
  | 'network'
  | 'internal'
  | 'unknown';

export interface ChatbotError {
  code: ChatbotErrorCode;
  message: string;
  retryAfterSeconds?: number;
}

// ---- UI-local (서버 비전송) ----

/** 말풍선 thread 에 표시할 메시지 단위 */
export interface UIChatMessage {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  createdAt: number;
  /** welcome 등 서버 왕복 없이 클라이언트가 렌더하는 메시지 플래그 */
  isWelcome?: boolean;
}
