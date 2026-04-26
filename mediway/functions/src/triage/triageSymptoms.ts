import * as admin from 'firebase-admin';
import { onCall, HttpsError } from 'firebase-functions/v2/https';
import { geminiChat } from '../chatbot/providers/gemini';
import {
  checkEmergency,
  checkPiiRequest,
  PII_REFUSAL_RESPONSE,
  sanitizeUserText,
  STANDARD_DISCLAIMER,
} from '../chatbot/safety';
import { appendAuditLog } from '../util/auditLog';
import { TriageRequestSchema, type TriageResult, type TriageOutcome, type TriageAuditEntry, type TriageRecommendation } from './types';
import {
  buildTriageSystemInstruction,
  emergencyFallback,
  genericFallback,
  parseTriageJson,
} from './prompt';
import {
  checkTriageRateLimit,
  incrementTriageUsage,
  TRIAGE_LIMIT_PER_HOUR,
} from './rateLimit';

const region = 'asia-northeast3';

/**
 * `triageSymptoms` callable — 환자 증상 텍스트 → 진료과 3개 추천 + 신뢰도 + disclaimer.
 *
 * Pipeline:
 *  1. Auth 확인 (uid 필수)
 *  2. Zod validate (symptomText 10..500)
 *  3. sanitizeUserText 정규화
 *  4. Hospital features.aiTriage=true 검증 (false → failed-precondition)
 *  5. Emergency 키워드 → LLM 우회 + emergencyFallback (응급의학과 1건 + 119 안내)
 *  6. PII 키워드 → LLM 우회 + 빈 recommendations + 거절 사유
 *  7. Rate limit 체크 (시간당 10회)
 *  8. Gemini 호출 + structured JSON output
 *  9. JSON parse 검증 — 실패 시 genericFallback
 *  10. usage +1 (transaction)
 *  11. /triage_audit/{pushId} append + audit_logs_v2 dual-write
 *  12. 응답 반환
 *
 * 권한 모델: Admin SDK 로 실행 → RTDB rules 우회. 호출자(uid) 검증은 onCall 자체.
 */
export const triageSymptoms = onCall(
  { region, cors: true, timeoutSeconds: 30 },
  async (req) => {
    // 1. Auth
    if (!req.auth?.uid) {
      throw new HttpsError('unauthenticated', '로그인이 필요합니다');
    }
    const uid = req.auth.uid;

    // 2. Validate
    const parsed = TriageRequestSchema.safeParse(req.data);
    if (!parsed.success) {
      throw new HttpsError(
        'invalid-argument',
        parsed.error.issues.map((i) => i.message).join(', '),
      );
    }
    const { hospitalId, symptomText: rawText } = parsed.data;
    const symptomText = sanitizeUserText(rawText);
    if (!symptomText || symptomText.length < 10) {
      throw new HttpsError('invalid-argument', '증상 설명은 10자 이상 입력해 주세요');
    }

    const db = admin.database();
    const now = Date.now();
    const symptomLen = symptomText.length;
    const symptomSnippet = symptomText.slice(0, 80);
    const model = process.env.GEMINI_MODEL ?? 'gemini-2.5-flash';

    // 4. Hospital features.aiTriage 검증
    const aiTriageOn = await isAiTriageEnabled(db, hospitalId);
    if (!aiTriageOn) {
      await writeAudit(db, {
        actorUid: uid,
        hospitalId,
        symptomLen,
        symptomSnippet,
        recommendations: [],
        model,
        tokensIn: 0,
        tokensOut: 0,
        outcome: 'feature_disabled',
        timestamp: now,
      });
      throw new HttpsError(
        'failed-precondition',
        '이 병원에서는 AI 진료과 추천 기능이 활성화되어 있지 않습니다',
      );
    }

    // 5. Emergency 분기 (LLM 우회)
    if (checkEmergency(symptomText)) {
      const recs = emergencyFallback();
      await writeAudit(db, {
        actorUid: uid,
        hospitalId,
        symptomLen,
        symptomSnippet,
        recommendations: recs.map((r) => ({
          department: r.department,
          confidence: r.confidence,
        })),
        model,
        tokensIn: 0,
        tokensOut: 0,
        outcome: 'emergency',
        timestamp: now,
      });
      const result: TriageResult = {
        recommendations: recs,
        disclaimer: STANDARD_DISCLAIMER,
        emergencyNotice: '🚨 응급 가능성이 있습니다. 119 또는 가까운 응급실로 즉시 이동하세요.',
        model,
        tokensIn: 0,
        tokensOut: 0,
        rateLimit: { remainingHour: TRIAGE_LIMIT_PER_HOUR },
      };
      return result;
    }

    // 6. PII 분기
    if (checkPiiRequest(symptomText)) {
      await writeAudit(db, {
        actorUid: uid,
        hospitalId,
        symptomLen,
        symptomSnippet,
        recommendations: [],
        model,
        tokensIn: 0,
        tokensOut: 0,
        outcome: 'pii_refuse',
        timestamp: now,
      });
      throw new HttpsError(
        'invalid-argument',
        PII_REFUSAL_RESPONSE.split('\n')[0], // 첫 줄만 — 사용자 친절 안내
      );
    }

    // 7. Rate limit
    const rc = await checkTriageRateLimit(uid, now);
    if (!rc.allowed) {
      await writeAudit(db, {
        actorUid: uid,
        hospitalId,
        symptomLen,
        symptomSnippet,
        recommendations: [],
        model,
        tokensIn: 0,
        tokensOut: 0,
        outcome: 'rate_limited',
        timestamp: now,
      });
      const minutesLeft = Math.ceil(rc.retryAfterSeconds / 60);
      throw new HttpsError(
        'resource-exhausted',
        `시간당 ${TRIAGE_LIMIT_PER_HOUR}회 한도를 초과했습니다. 약 ${minutesLeft}분 후 다시 시도해 주세요.`,
        { retryAfterSeconds: rc.retryAfterSeconds },
      );
    }

    // 3.5. Gemini API key
    const apiKey = process.env.GEMINI_API_KEY;
    if (!apiKey) {
      throw new HttpsError(
        'failed-precondition',
        'GEMINI_API_KEY 미설정 — functions/.env 확인',
      );
    }

    // 8. Gemini 호출
    let recommendations: TriageRecommendation[];
    let tokensIn = 0;
    let tokensOut = 0;
    let outcome: TriageOutcome = 'ok';
    try {
      const r = await geminiChat({
        apiKey,
        model,
        systemInstruction: buildTriageSystemInstruction(),
        history: [],
        userText: symptomText,
        temperature: 0.2, // 결정적 출력
        maxOutputTokens: 768,
      });
      tokensIn = r.tokensIn;
      tokensOut = r.tokensOut;

      // 9. JSON parse + 검증
      const parsedJson = parseTriageJson(r.reply);
      if (!parsedJson || parsedJson.recommendations.length === 0) {
        console.warn('[triageSymptoms] JSON parse 실패 또는 빈 결과 — fallback', {
          uid,
          hospitalId,
          rawSnippet: r.reply.slice(0, 200),
        });
        recommendations = genericFallback();
      } else {
        // 정확히 3개 보장 — 부족하면 그대로, 초과하면 자르기, 0 이면 fallback
        recommendations = parsedJson.recommendations
          .slice(0, 3)
          .sort((a, b) => b.confidence - a.confidence);
      }
    } catch (err) {
      console.error('[triageSymptoms] Gemini 호출 실패', err);
      outcome = 'internal';
      // 사용자에게는 internal 로 알리되 audit 는 기록
      await writeAudit(db, {
        actorUid: uid,
        hospitalId,
        symptomLen,
        symptomSnippet,
        recommendations: [],
        model,
        tokensIn,
        tokensOut,
        outcome,
        timestamp: now,
      });
      throw new HttpsError(
        'internal',
        'AI 추천 응답 생성에 실패했습니다. 잠시 후 다시 시도해 주세요.',
      );
    }

    // 10. usage +1
    try {
      await incrementTriageUsage(uid, now);
    } catch (err) {
      console.warn('[triageSymptoms] usage 증분 실패 (응답은 정상 반환)', err);
    }

    // 11. audit dual-write
    try {
      await Promise.all([
        writeAudit(db, {
          actorUid: uid,
          hospitalId,
          symptomLen,
          symptomSnippet,
          recommendations: recommendations.map((r) => ({
            department: r.department,
            confidence: r.confidence,
          })),
          model,
          tokensIn,
          tokensOut,
          outcome,
          timestamp: now,
        }),
        appendAuditLog(db, hospitalId, {
          actorUid: uid,
          action: 'triage.recommend',
          target: hospitalId,
          meta: {
            departmentTop: recommendations[0]?.department ?? null,
            confidenceTop: recommendations[0]?.confidence ?? null,
            count: recommendations.length,
            tokensIn,
            tokensOut,
            model,
            symptomLen,
          },
          timestamp: now,
        }),
      ]);
    } catch (err) {
      console.warn('[triageSymptoms] audit 기록 실패 (응답은 정상 반환)', err);
    }

    // 12. Response
    const result: TriageResult = {
      recommendations,
      disclaimer: STANDARD_DISCLAIMER,
      model,
      tokensIn,
      tokensOut,
      rateLimit: { remainingHour: Math.max(0, rc.remainingHour - 1) },
    };
    return result;
  },
);

/** RTDB `hospitals/{hid}/profile/features/aiTriage` 가 true 인지 확인. */
async function isAiTriageEnabled(
  db: admin.database.Database,
  hospitalId: string,
): Promise<boolean> {
  try {
    const snap = await db
      .ref(`hospitals/${hospitalId}/profile/features/aiTriage`)
      .get();
    return snap.val() === true;
  } catch (err) {
    console.warn('[triageSymptoms] features.aiTriage 조회 실패 — disabled 처리', err);
    return false;
  }
}

/** `/triage_audit/{pushId}` 에 self-append 형태의 entry 기록 (Admin SDK). */
async function writeAudit(
  db: admin.database.Database,
  entry: TriageAuditEntry,
): Promise<void> {
  try {
    await db.ref('triage_audit').push(entry);
  } catch (err) {
    console.warn('[triageSymptoms] /triage_audit push 실패', err);
  }
}
