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
}
