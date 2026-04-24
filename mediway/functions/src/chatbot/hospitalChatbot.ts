import * as admin from 'firebase-admin';
import { onCall, HttpsError } from 'firebase-functions/v2/https';
import { z } from 'zod';
import { geminiChat } from './providers/gemini';
import { detectIntent } from './intent';
import {
  checkEmergency,
  emergencyResponse,
  checkPiiRequest,
  PII_REFUSAL_RESPONSE,
  applyDisclaimer,
  sanitizeUserText,
  STANDARD_DISCLAIMER,
} from './safety';
import { loadHospitalContext, renderSystemInstruction } from './context';
import { loadHistory, appendTurn } from './chatSession';
import { checkRateLimit, incrementUsage, LIMITS } from './rateLimit';
import type { ChatbotCallResult, IntentKind } from './providers/shared';

const region = 'asia-northeast3';

const RequestSchema = z.object({
  hospitalId: z.string().min(1).max(64),
  userText: z.string().min(1).max(1000),
  chatId: z.string().max(128).optional(),
});

export const hospitalChatbot = onCall(
  { region, cors: true, timeoutSeconds: 60 },
  async (req) => {
    // 1. Auth check
    if (!req.auth?.uid) {
      throw new HttpsError('unauthenticated', '로그인이 필요합니다');
    }
    const uid = req.auth.uid;

    // 2. Validate
    const parsed = RequestSchema.safeParse(req.data);
    if (!parsed.success) {
      throw new HttpsError(
        'invalid-argument',
        parsed.error.issues.map((i) => i.message).join(', '),
      );
    }
    const { hospitalId, userText: rawText } = parsed.data;
    const userText = sanitizeUserText(rawText);
    if (!userText) {
      throw new HttpsError('invalid-argument', '질문이 비어있습니다');
    }

    // 3. API key
    const apiKey = process.env.GEMINI_API_KEY;
    if (!apiKey) {
      throw new HttpsError(
        'failed-precondition',
        'GEMINI_API_KEY 미설정 — functions/.env 확인',
      );
    }
    const model = process.env.GEMINI_MODEL ?? 'gemini-2.5-flash';

    const db = admin.database();
    const now = Date.now();

    // 4. Safety pre-check: 응급 → LLM 우회 하드코드 응답
    if (checkEmergency(userText)) {
      await db.ref('audit_logs').push({
        actorUid: uid,
        action: 'chatbot.escalate',
        target: hospitalId,
        meta: { userTextSnippet: userText.slice(0, 80) },
        timestamp: now,
      });
      const result: ChatbotCallResult = {
        reply: emergencyResponse(),
        intent: 'escalate',
        disclaimer: STANDARD_DISCLAIMER,
        tokensIn: 0,
        tokensOut: 0,
        model,
      };
      return result;
    }

    // 5. PII 요청 거절
    if (checkPiiRequest(userText)) {
      await db.ref('audit_logs').push({
        actorUid: uid,
        action: 'chatbot.pii_refuse',
        target: hospitalId,
        meta: { userTextSnippet: userText.slice(0, 80) },
        timestamp: now,
      });
      const result: ChatbotCallResult = {
        reply: PII_REFUSAL_RESPONSE,
        intent: 'general',
        disclaimer: STANDARD_DISCLAIMER,
        tokensIn: 0,
        tokensOut: 0,
        model,
      };
      return result;
    }

    // 6. Intent detection
    const intent: IntentKind = detectIntent(userText);

    // 6.5. Rate limit 체크 (escalate/PII 조기 반환은 이미 return한 상태)
    const rc = await checkRateLimit(uid, now);
    if (!rc.allowed) {
      throw new HttpsError(
        'resource-exhausted',
        rc.remainingDay === 0
          ? `오늘 이용 한도(${LIMITS.perDay}회)를 초과했습니다. 내일 다시 시도해 주세요.`
          : `시간당 한도(${LIMITS.perHour}회)를 초과했습니다. 약 ${Math.ceil(rc.retryAfterSeconds / 60)}분 후 다시 시도해 주세요.`,
        { retryAfterSeconds: rc.retryAfterSeconds },
      );
    }

    // 7. Hospital context 로드 (5분 memoize)
    let systemInstruction: string;
    try {
      const ctx = await loadHospitalContext(hospitalId);
      systemInstruction = renderSystemInstruction(ctx);
    } catch (err) {
      console.warn('[hospitalChatbot] context 로드 실패 — generic fallback', err);
      systemInstruction = `당신은 병원 안내 챗봇입니다. 한국어로 친절히 답변하세요. 증상 질문에는 관련 진료과를 추천하고 "진단이 아님" 고지를 포함하세요. 응급 증상은 119 + 응급실 안내.`;
    }

    // 8. 멀티턴 히스토리 로드 (chatId 제공된 경우만)
    const chatIdInput = parsed.data.chatId;
    let history: Awaited<ReturnType<typeof loadHistory>> = [];
    if (chatIdInput) {
      try {
        history = await loadHistory(hospitalId, uid, chatIdInput);
      } catch (err) {
        console.warn(
          `[hospitalChatbot] history 로드 실패 chatId=${chatIdInput} — 빈 히스토리로 진행`,
          err,
        );
      }
    }

    // 9. Gemini call (히스토리 포함)
    let reply: string;
    let tokensIn = 0;
    let tokensOut = 0;
    try {
      const r = await geminiChat({
        apiKey,
        model,
        systemInstruction,
        history,
        userText,
      });
      reply = applyDisclaimer(r.reply || '죄송합니다, 답변을 생성하지 못했습니다.');
      tokensIn = r.tokensIn;
      tokensOut = r.tokensOut;
    } catch (err) {
      console.error('[hospitalChatbot] Gemini 호출 실패', err);
      throw new HttpsError(
        'internal',
        '챗봇 응답 생성에 실패했습니다. 잠시 후 다시 시도해 주세요.',
      );
    }

    // 10. 대화 영속화 (chatId 신규/기존 둘 다 append)
    let sessionChatId = chatIdInput;
    try {
      const turn = await appendTurn({
        hospitalId,
        uid,
        chatId: chatIdInput,
        userText,
        userIntent: intent,
        assistantReply: reply,
        tokensIn,
        tokensOut,
        model,
      });
      sessionChatId = turn.chatId;
    } catch (err) {
      console.warn('[hospitalChatbot] chat_sessions 영속화 실패 (응답은 정상 반환)', err);
    }

    // 11. Usage tracking (chatbot_usage) + audit
    try {
      await Promise.all([
        incrementUsage(uid, now),
        db.ref('audit_logs').push({
          actorUid: uid,
          action: 'chatbot.reply',
          target: hospitalId,
          meta: {
            intent,
            tokensIn,
            tokensOut,
            model,
            userTextLen: userText.length,
            chatId: sessionChatId ?? null,
            historyLen: history.length,
          },
          timestamp: now,
        }),
      ]);
    } catch (err) {
      console.warn('[hospitalChatbot] usage/audit 기록 실패 (응답은 정상 반환)', err);
    }

    const result: ChatbotCallResult = {
      reply,
      intent,
      disclaimer: STANDARD_DISCLAIMER,
      tokensIn,
      tokensOut,
      model,
      chatId: sessionChatId,
      rateLimit: {
        remainingHour: Math.max(0, rc.remainingHour - 1),
        remainingDay: Math.max(0, rc.remainingDay - 1),
      },
    };
    return result;
  },
);
