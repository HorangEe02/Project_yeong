export type ChatRole = 'user' | 'model';

export type IntentKind =
  | 'triage'
  | 'hospital_info'
  | 'department_info'
  | 'appointment_help'
  | 'direction'
  | 'general'
  | 'escalate';

export interface ChatMessage {
  role: ChatRole;
  text: string;
}

export interface ChatbotCallResult {
  reply: string;
  intent: IntentKind;
  recommendedDepartments?: string[];
  disclaimer: string;
  tokensIn: number;
  tokensOut: number;
  model: string;
  /** 대화 식별자 — 기존 대화 이어쓸 땐 클라이언트가 재전송 */
  chatId?: string;
  /** Rate limit 잔여량 — 클라이언트 UI 배너 노출용 */
  rateLimit?: {
    remainingHour: number;
    remainingDay: number;
  };
}
