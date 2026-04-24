import { httpsCallable } from 'firebase/functions';
import { functions, isFirebaseConfigured } from '@/config/firebase';
import type {
  ChatbotError,
  ChatbotErrorCode,
  ChatbotRequest,
  ChatbotResponse,
} from '@/types/chatbot';

/**
 * `hospitalChatbot` (asia-northeast3) callable 래퍼.
 *
 * 서버 원본: mediway/functions/src/chatbot/hospitalChatbot.ts
 * 서버 스키마: `{ hospitalId, userText, chatId? }` → `ChatbotCallResult`
 *
 * 이 래퍼는:
 *  1) `chatId` 가 falsy 면 payload 에서 아예 누락 (Firebase callable 이 undefined→null
 *     로 직렬화하는 문제는 서버가 `.nullish()` 로 흡수하지만, 네트워크 낭비 방지)
 *  2) 빈 문자열은 즉시 로컬 거절 (서버 왕복 없이 invalid_argument)
 *  3) Firebase HttpsError 를 `ChatbotError` 로 normalize — UI 가 code 분기로 사용
 */
export async function sendChatbotMessage(
  input: ChatbotRequest,
): Promise<ChatbotResponse> {
  const userText = input.userText.trim();
  if (!userText) {
    throw asChatbotError('invalid_argument', '질문이 비어있습니다');
  }
  if (!isFirebaseConfigured()) {
    throw asChatbotError('internal', 'Firebase 미설정');
  }

  const payload: ChatbotRequest = {
    hospitalId: input.hospitalId,
    userText,
  };
  if (input.chatId) payload.chatId = input.chatId;

  const callable = httpsCallable<ChatbotRequest, ChatbotResponse>(
    functions,
    'hospitalChatbot',
  );
  try {
    const result = await callable(payload);
    return result.data;
  } catch (err) {
    throw normalizeError(err);
  }
}

function normalizeError(err: unknown): ChatbotError {
  const anyErr = err as {
    code?: string;
    message?: string;
    details?: { retryAfterSeconds?: number };
  } | null;
  const codeRaw = anyErr?.code ?? 'unknown';
  const message = anyErr?.message ?? '알 수 없는 오류';

  // Firebase callable returns code like 'functions/resource-exhausted'
  // 일부 환경은 'resource-exhausted' 단독. substring 매칭으로 모두 커버.
  if (codeRaw.includes('unauthenticated')) {
    return asChatbotError('unauthenticated', '로그인이 필요합니다');
  }
  if (codeRaw.includes('resource-exhausted')) {
    return {
      code: 'rate_limited',
      message,
      retryAfterSeconds: anyErr?.details?.retryAfterSeconds,
    };
  }
  if (codeRaw.includes('invalid-argument')) {
    return asChatbotError('invalid_argument', message);
  }
  if (codeRaw.includes('unavailable') || codeRaw.includes('deadline-exceeded')) {
    return asChatbotError('network', '네트워크 오류 — 잠시 후 다시 시도해 주세요');
  }
  if (codeRaw.includes('internal') || codeRaw.includes('failed-precondition')) {
    return asChatbotError('internal', message);
  }
  return asChatbotError('unknown', message);
}

function asChatbotError(code: ChatbotErrorCode, message: string): ChatbotError {
  return { code, message };
}
