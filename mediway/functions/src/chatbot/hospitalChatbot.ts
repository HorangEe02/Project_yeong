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
import type { ChatbotCallResult, IntentKind } from './providers/shared';

const region = 'asia-northeast3';

const RequestSchema = z.object({
  hospitalId: z.string().min(1).max(64),
  userText: z.string().min(1).max(1000),
  chatId: z.string().max(128).optional(),
});

/**
 * R3.1 MVP용 기본 system prompt. 병원별 context 동적 주입은 R3.2에서.
 */
const BASE_SYSTEM_INSTRUCTION = `당신은 "MediWay 병원" 안내 챗봇입니다. 병원 이용에 관한 친절한 안내를 제공합니다.

[답변 스타일]
- 한국어, 존댓말, 3~5문장 이내
- 필요 시 이모지 1개 (🏥 💊 🗺️) 허용
- 증상 질문에는 관련 진료과 2~3개를 추천하되 반드시 "진단이 아님" 안내 포함
- 모르는 정보는 "병원에 직접 문의 부탁드립니다"로 답변

[금지]
- 확정 진단·처방·약물 복용법·용량 안내
- 주민번호·계좌·비밀번호 등 개인정보 요청
- 다른 병원 추천
- 원격 진료 행위로 해석될 수 있는 상세 의학 조언

[응급 안내]
- 가슴통증·호흡곤란·의식저하·대량출혈·자살 징후는 즉시 119 + 응급실 + 1393 안내`;

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

    // 7. Gemini call (stateless — history X for MVP; R3.3에서 멀티턴)
    let reply: string;
    let tokensIn = 0;
    let tokensOut = 0;
    try {
      const r = await geminiChat({
        apiKey,
        model,
        systemInstruction: BASE_SYSTEM_INSTRUCTION,
        history: [],
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

    // 8. Usage tracking + audit
    const hourEpoch = Math.floor(now / 3_600_000);
    try {
      await Promise.all([
        db.ref(`triage_usage/${uid}/${hourEpoch}`).transaction((cur) => {
          return typeof cur === 'number' ? cur + 1 : 1;
        }),
        db.ref('audit_logs').push({
          actorUid: uid,
          action: 'chatbot.reply',
          target: hospitalId,
          meta: { intent, tokensIn, tokensOut, model, userTextLen: userText.length },
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
    };
    return result;
  },
);
