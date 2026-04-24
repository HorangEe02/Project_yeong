import * as admin from 'firebase-admin';
import type { ChatMessage, IntentKind } from './providers/shared';

const HISTORY_TURN_LIMIT = 10; // 최근 10 turn만 context로 주입
const SESSION_VERSION = 'v1';

export interface ChatSessionMeta {
  startedAt: number;
  lastActivityAt: number;
  messageCount: number;
  hospitalId: string;
  uid: string;
  resolved?: boolean;
}

export interface ChatSessionMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: number;
  intent?: IntentKind;
  meta?: {
    tokensIn?: number;
    tokensOut?: number;
    model?: string;
  };
}

function sessionRoot(hospitalId: string, uid: string, chatId: string) {
  return admin
    .database()
    .ref(`chat_sessions/${hospitalId}/${uid}/${chatId}`);
}

/**
 * 기존 chat 세션의 히스토리를 Gemini format으로 변환.
 * 최근 HISTORY_TURN_LIMIT 개만 반환 (token budget 제한).
 * 'system' role 메시지는 제외 (systemInstruction은 renderSystemInstruction에서 별도 생성).
 */
export async function loadHistory(
  hospitalId: string,
  uid: string,
  chatId: string,
): Promise<ChatMessage[]> {
  const snap = await sessionRoot(hospitalId, uid, chatId)
    .child('messages')
    .orderByChild('timestamp')
    .limitToLast(HISTORY_TURN_LIMIT)
    .get();

  const raw = (snap.val() ?? {}) as Record<string, ChatSessionMessage>;
  const sorted = Object.values(raw).sort((a, b) => a.timestamp - b.timestamp);

  return sorted
    .filter((m) => m.role === 'user' || m.role === 'assistant')
    .map((m) => ({
      role: m.role === 'assistant' ? ('model' as const) : ('user' as const),
      text: m.content,
    }));
}

/**
 * 유저 + assistant 메시지 pair를 세션에 저장.
 * chatId가 없으면 신규 생성.
 * 반환: 실제 사용 chatId + 두 메시지 ID
 */
export async function appendTurn(params: {
  hospitalId: string;
  uid: string;
  chatId?: string;
  userText: string;
  userIntent: IntentKind;
  assistantReply: string;
  tokensIn: number;
  tokensOut: number;
  model: string;
}): Promise<{ chatId: string; userMessageId: string; assistantMessageId: string }> {
  const db = admin.database();
  const hospitalId = params.hospitalId;
  const uid = params.uid;

  let chatId = params.chatId;
  if (!chatId) {
    const newRef = db.ref(`chat_sessions/${hospitalId}/${uid}`).push();
    chatId = newRef.key!;
    await newRef.set({
      startedAt: Date.now(),
      lastActivityAt: Date.now(),
      messageCount: 0,
      hospitalId,
      uid,
      version: SESSION_VERSION,
    });
  }

  const root = sessionRoot(hospitalId, uid, chatId);
  const messagesRef = root.child('messages');

  const now = Date.now();
  const userRef = messagesRef.push();
  const assistantRef = messagesRef.push();

  const userMessage: ChatSessionMessage = {
    role: 'user',
    content: params.userText,
    timestamp: now,
    intent: params.userIntent,
  };
  const assistantMessage: ChatSessionMessage = {
    role: 'assistant',
    content: params.assistantReply,
    timestamp: now + 1, // 순서 보장용 +1ms
    intent: params.userIntent,
    meta: {
      tokensIn: params.tokensIn,
      tokensOut: params.tokensOut,
      model: params.model,
    },
  };

  await Promise.all([
    userRef.set(userMessage),
    assistantRef.set(assistantMessage),
    root.update({
      lastActivityAt: now + 1,
      messageCount: admin.database.ServerValue.increment(2),
    }),
  ]);

  return {
    chatId,
    userMessageId: userRef.key!,
    assistantMessageId: assistantRef.key!,
  };
}

/** 테스트용 유틸 */
export const __internal = {
  HISTORY_TURN_LIMIT,
  SESSION_VERSION,
};
