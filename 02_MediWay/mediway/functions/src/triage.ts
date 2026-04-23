import * as admin from 'firebase-admin';
import axios from 'axios';
import { onCall, HttpsError } from 'firebase-functions/v2/https';
import { defineSecret } from 'firebase-functions/params';

/** Secret Manager에서 주입 — Anthropic / OpenAI / Gemini 공통 env slot */
const llmApiKey = defineSecret('LLM_API_KEY');

export interface TriageRecommendation {
  department: string;
  confidence: number;
  reason: string;
}

export interface TriageResponse {
  recommendations: TriageRecommendation[];
  disclaimer: string;
}

export interface TriageDeps {
  callLlm: (symptoms: string) => Promise<TriageRecommendation[]>;
  checkRateLimit: (uid: string) => Promise<void>;
  audit: (uid: string, recommendations: string[]) => Promise<void>;
}

const DISCLAIMER =
  '본 추천은 참고용이며 의학적 진단이 아닙니다. 증상이 심하거나 지속되면 즉시 의료진에게 상담하세요.';
const MIN_SYMPTOM_LEN = 3;
const MAX_SYMPTOM_LEN = 500;
const HOURLY_LIMIT = 10;

/**
 * Triage 비즈니스 로직 — 의존성 주입으로 LLM/RateLimit/Audit을 외부 제공.
 * 트리거와 독립 테스트.
 */
export async function performTriage(
  uid: string,
  symptoms: string,
  deps: TriageDeps,
): Promise<TriageResponse> {
  const trimmed = symptoms.trim();
  if (trimmed.length < MIN_SYMPTOM_LEN || trimmed.length > MAX_SYMPTOM_LEN) {
    throw new HttpsError(
      'invalid-argument',
      `증상은 ${MIN_SYMPTOM_LEN}-${MAX_SYMPTOM_LEN}자로 입력해 주세요`,
    );
  }

  await deps.checkRateLimit(uid);

  const raw = await deps.callLlm(trimmed);
  const recommendations = raw
    .filter(
      (r) =>
        typeof r?.department === 'string' &&
        r.department.length > 0 &&
        typeof r.confidence === 'number' &&
        typeof r.reason === 'string',
    )
    .slice(0, 3);

  if (recommendations.length === 0) {
    throw new HttpsError('internal', 'AI 응답을 분석하지 못했습니다');
  }

  await deps.audit(
    uid,
    recommendations.map((r) => r.department),
  );

  return { recommendations, disclaimer: DISCLAIMER };
}

/** Anthropic Claude Haiku (기본) — JSON 응답 파싱 */
export async function callClaudeHaiku(
  symptoms: string,
  apiKey: string,
): Promise<TriageRecommendation[]> {
  const prompt = `환자 증상: ${symptoms}

위 증상에 대해 적절한 상위 3개 진료과를 JSON으로만 응답하세요.
경고: 본인은 의사가 아니며, 응답은 진단이 아닌 참고용 추천입니다.

응답 형식 (다른 텍스트 없이 JSON만):
{
  "recommendations": [
    {"department": "내과", "confidence": 0.85, "reason": "간단한 이유"}
  ]
}`;

  const resp = await axios.post(
    'https://api.anthropic.com/v1/messages',
    {
      model: 'claude-haiku-4-5-20251001',
      max_tokens: 400,
      messages: [{ role: 'user', content: prompt }],
    },
    {
      headers: {
        'x-api-key': apiKey,
        'anthropic-version': '2023-06-01',
        'content-type': 'application/json',
      },
      timeout: 15000,
    },
  );

  const text = resp.data?.content?.[0]?.text ?? '';
  const match = text.match(/\{[\s\S]*\}/);
  if (!match) return [];
  try {
    const parsed = JSON.parse(match[0]);
    return Array.isArray(parsed.recommendations) ? parsed.recommendations : [];
  } catch {
    return [];
  }
}

/** 기본 rate limit — `/triage_usage/{uid}/{hour}` transaction */
async function defaultCheckRateLimit(uid: string): Promise<void> {
  const hour = Math.floor(Date.now() / 3_600_000);
  const ref = admin.database().ref(`triage_usage/${uid}/${hour}`);
  const tx = await ref.transaction((cur: unknown) =>
    (typeof cur === 'number' ? cur : 0) + 1,
  );
  if (!tx.committed) {
    throw new HttpsError('aborted', '사용량 카운터 업데이트 실패');
  }
  const count = tx.snapshot.val() as number;
  if (count > HOURLY_LIMIT) {
    throw new HttpsError(
      'resource-exhausted',
      `시간당 ${HOURLY_LIMIT}회 제한 초과 — 잠시 후 다시 시도해 주세요`,
    );
  }
}

/** 기본 audit log — 증상 텍스트는 저장 금지, 추천 과만 기록 */
async function defaultAudit(
  uid: string,
  recommendations: string[],
): Promise<void> {
  await admin
    .database()
    .ref('triage_audit')
    .push({
      uid,
      recommendations,
      at: Date.now(),
    });
}

/**
 * 트리거 — Callable Function.
 * 입력: `{ symptoms: string }`
 * 출력: `{ recommendations, disclaimer }`
 */
export const triageSymptoms = onCall(
  {
    region: 'asia-northeast3',
    cors: true,
    secrets: [llmApiKey],
  },
  async (request) => {
    if (!request.auth?.uid) {
      throw new HttpsError('unauthenticated', '로그인이 필요합니다');
    }
    const data = request.data as { symptoms?: string };
    const symptoms = typeof data?.symptoms === 'string' ? data.symptoms : '';
    const apiKey = llmApiKey.value();
    if (!apiKey) {
      throw new HttpsError('failed-precondition', 'LLM_API_KEY 미설정');
    }
    try {
      return await performTriage(request.auth.uid, symptoms, {
        callLlm: (s) => callClaudeHaiku(s, apiKey),
        checkRateLimit: defaultCheckRateLimit,
        audit: defaultAudit,
      });
    } catch (err) {
      if (err instanceof HttpsError) throw err;
      console.error('[triageSymptoms]', err);
      throw new HttpsError('internal', 'AI 추천에 실패했습니다');
    }
  },
);
