import { describe, it, expect, beforeEach, vi } from 'vitest';

// --- mocks ---

// onCall 래퍼를 우회 — handler 함수를 그대로 노출해 직접 호출 가능
vi.mock('firebase-functions/v2/https', async () => {
  const actual = await vi.importActual<typeof import('firebase-functions/v2/https')>(
    'firebase-functions/v2/https',
  );
  return {
    ...actual,
    onCall: (_opts: unknown, handler: unknown) => handler,
  };
});

const mockGeminiChat = vi.fn();
vi.mock('../chatbot/providers/gemini', () => ({
  geminiChat: (...args: unknown[]) => mockGeminiChat(...args),
}));

// audit_logs_v2 dual-write 는 본 테스트 비범위 — no-op
const mockAppendAuditLog = vi.fn();
vi.mock('../util/auditLog', () => ({
  appendAuditLog: (...args: unknown[]) => mockAppendAuditLog(...args),
}));

// rateLimit & feature 검증을 위한 RTDB mock
let mockUsageCount = 0;
let mockAiTriageOn = true;

const mockTransaction = vi.fn();
const mockGet = vi.fn();
const mockPush = vi.fn();

function makeSnapshot(value: unknown) {
  return {
    val: () => (value === undefined ? null : value),
    exists: () => value !== undefined && value !== null,
  };
}

vi.mock('firebase-admin', () => ({
  database: () => ({
    ref: (path: string) => ({
      get: () => {
        if (path.endsWith('/aiTriage')) {
          return Promise.resolve(makeSnapshot(mockAiTriageOn));
        }
        if (path.startsWith('triage_usage/')) {
          return Promise.resolve(makeSnapshot(mockUsageCount || null));
        }
        return Promise.resolve(makeSnapshot(null));
      },
      transaction: (fn: (cur: unknown) => unknown) => {
        const next = fn(mockUsageCount);
        mockUsageCount = (typeof next === 'number' ? next : 0);
        mockTransaction(path, next);
        return Promise.resolve();
      },
      push: (value: unknown) => {
        mockPush(path, value);
        return Promise.resolve();
      },
    }),
  }),
}));

// 테스트 환경 — Gemini API key 가 있어야 통과 (없으면 failed-precondition)
process.env.GEMINI_API_KEY = 'test-key-fake';

import { triageSymptoms } from '../triage/triageSymptoms';

type Handler = (req: {
  auth?: { uid: string; token?: Record<string, unknown> };
  data: unknown;
}) => Promise<unknown>;

const handler = triageSymptoms as unknown as Handler;

const validRequest = {
  hospitalId: 'demo',
  symptomText: '2일째 기침과 미열이 있어요',
};
const patient = { auth: { uid: 'p1', token: { role: 'patient' } } };

beforeEach(() => {
  mockGeminiChat.mockReset();
  mockTransaction.mockReset();
  mockGet.mockReset();
  mockPush.mockReset();
  mockAppendAuditLog.mockReset();
  mockAppendAuditLog.mockResolvedValue(undefined);
  mockUsageCount = 0;
  mockAiTriageOn = true;
});

// =====================================================================
// Auth + validation
// =====================================================================

describe('triageSymptoms — auth/validation', () => {
  it('미로그인 → unauthenticated', async () => {
    await expect(handler({ data: validRequest })).rejects.toMatchObject({
      code: 'unauthenticated',
    });
  });

  it('symptomText < 10자 → invalid-argument', async () => {
    await expect(
      handler({ ...patient, data: { hospitalId: 'demo', symptomText: '아파' } }),
    ).rejects.toMatchObject({ code: 'invalid-argument' });
  });

  it('symptomText > 500자 → invalid-argument', async () => {
    await expect(
      handler({
        ...patient,
        data: { hospitalId: 'demo', symptomText: '아'.repeat(501) },
      }),
    ).rejects.toMatchObject({ code: 'invalid-argument' });
  });

  it('hospitalId 누락 → invalid-argument', async () => {
    await expect(
      handler({ ...patient, data: { symptomText: validRequest.symptomText } }),
    ).rejects.toMatchObject({ code: 'invalid-argument' });
  });
});

// =====================================================================
// features.aiTriage 게이트
// =====================================================================

describe('triageSymptoms — features.aiTriage', () => {
  it('aiTriage=false → failed-precondition (LLM 미호출)', async () => {
    mockAiTriageOn = false;
    await expect(
      handler({ ...patient, data: validRequest }),
    ).rejects.toMatchObject({ code: 'failed-precondition' });
    expect(mockGeminiChat).not.toHaveBeenCalled();
  });

  it('aiTriage=false 일 때 outcome=feature_disabled 로 audit', async () => {
    mockAiTriageOn = false;
    await expect(
      handler({ ...patient, data: validRequest }),
    ).rejects.toBeDefined();
    const auditCalls = mockPush.mock.calls.filter(
      ([p]) => p === 'triage_audit',
    );
    expect(auditCalls).toHaveLength(1);
    expect((auditCalls[0][1] as { outcome: string }).outcome).toBe(
      'feature_disabled',
    );
  });
});

// =====================================================================
// Emergency 분기
// =====================================================================

describe('triageSymptoms — emergency', () => {
  it('응급 키워드 → LLM 우회 + 응급의학과 1건 + emergencyNotice', async () => {
    const result = (await handler({
      ...patient,
      data: {
        hospitalId: 'demo',
        symptomText: '갑자기 가슴이 너무 아파서 숨을 못 쉬겠어요',
      },
    })) as {
      recommendations: Array<{ department: string }>;
      emergencyNotice?: string;
    };
    expect(mockGeminiChat).not.toHaveBeenCalled();
    expect(result.recommendations).toHaveLength(1);
    expect(result.recommendations[0].department).toBe('응급의학과');
    expect(result.emergencyNotice).toMatch(/119|응급실/);
  });

  it('응급 분기 시 audit outcome=emergency', async () => {
    await handler({
      ...patient,
      data: {
        hospitalId: 'demo',
        symptomText: '갑자기 가슴이 너무 아파서 숨을 못 쉬겠어요',
      },
    });
    const auditCall = mockPush.mock.calls.find(
      ([p]) => p === 'triage_audit',
    );
    expect((auditCall![1] as { outcome: string }).outcome).toBe('emergency');
  });
});

// =====================================================================
// PII 분기
// =====================================================================

describe('triageSymptoms — PII refusal', () => {
  it('PII 키워드 → invalid-argument + LLM 우회', async () => {
    await expect(
      handler({
        ...patient,
        data: {
          hospitalId: 'demo',
          symptomText: '내 주민등록번호 알려줄게 진료과 추천해줘',
        },
      }),
    ).rejects.toMatchObject({ code: 'invalid-argument' });
    expect(mockGeminiChat).not.toHaveBeenCalled();
  });

  it('PII 거절 시 audit outcome=pii_refuse', async () => {
    await expect(
      handler({
        ...patient,
        data: {
          hospitalId: 'demo',
          symptomText: '내 주민등록번호 알려줄게 진료과 추천해줘',
        },
      }),
    ).rejects.toBeDefined();
    const auditCall = mockPush.mock.calls.find(
      ([p]) => p === 'triage_audit',
    );
    expect((auditCall![1] as { outcome: string }).outcome).toBe('pii_refuse');
  });
});

// =====================================================================
// Rate limit
// =====================================================================

describe('triageSymptoms — rate limit', () => {
  it('카운트 10 도달 → resource-exhausted', async () => {
    mockUsageCount = 10;
    await expect(
      handler({ ...patient, data: validRequest }),
    ).rejects.toMatchObject({ code: 'resource-exhausted' });
    expect(mockGeminiChat).not.toHaveBeenCalled();
  });

  it('rate-limit 시 audit outcome=rate_limited', async () => {
    mockUsageCount = 10;
    await expect(
      handler({ ...patient, data: validRequest }),
    ).rejects.toBeDefined();
    const auditCall = mockPush.mock.calls.find(
      ([p]) => p === 'triage_audit',
    );
    expect((auditCall![1] as { outcome: string }).outcome).toBe('rate_limited');
  });

  it('카운트 9 → 통과 + 응답 후 +1 (transaction)', async () => {
    mockUsageCount = 9;
    mockGeminiChat.mockResolvedValue({
      reply: JSON.stringify({
        recommendations: [
          { department: '내과', confidence: 0.85, reason: '기침과 발열로 호흡기 감염 가능성.' },
          { department: '가정의학과', confidence: 0.6, reason: '종합 평가 적합.' },
          { department: '이비인후과', confidence: 0.45, reason: '인후 자극 가능성.' },
        ],
      }),
      tokensIn: 120,
      tokensOut: 80,
    });

    const result = (await handler({ ...patient, data: validRequest })) as {
      recommendations: unknown[];
      rateLimit: { remainingHour: number };
    };
    expect(result.recommendations).toHaveLength(3);
    // 호출 후 incrementUsage transaction 실행
    expect(mockTransaction).toHaveBeenCalled();
    expect(result.rateLimit.remainingHour).toBe(0); // 9 + 1 = 10, remaining = 0
  });
});

// =====================================================================
// OK 경로 — Gemini 응답 처리
// =====================================================================

describe('triageSymptoms — OK 경로', () => {
  beforeEach(() => {
    mockGeminiChat.mockResolvedValue({
      reply: JSON.stringify({
        recommendations: [
          { department: '내과', confidence: 0.85, reason: '기침과 발열로 호흡기 감염 가능성이 높습니다.' },
          { department: '가정의학과', confidence: 0.55, reason: '종합 평가에 적합합니다.' },
          { department: '이비인후과', confidence: 0.4, reason: '인후·기관지 자극 가능성.' },
        ],
      }),
      tokensIn: 120,
      tokensOut: 80,
    });
  });

  it('정상 JSON 응답 → 3개 추천 반환', async () => {
    const result = (await handler({ ...patient, data: validRequest })) as {
      recommendations: Array<{ department: string; confidence: number; reason: string }>;
      disclaimer: string;
      tokensIn: number;
      tokensOut: number;
    };
    expect(result.recommendations).toHaveLength(3);
    expect(result.recommendations[0].department).toBe('내과');
    expect(result.disclaimer).toMatch(/진단/);
    expect(result.tokensIn).toBe(120);
    expect(result.tokensOut).toBe(80);
  });

  it('confidence 내림차순 정렬', async () => {
    mockGeminiChat.mockResolvedValueOnce({
      reply: JSON.stringify({
        recommendations: [
          { department: '내과', confidence: 0.4, reason: 'r1' },
          { department: '가정의학과', confidence: 0.85, reason: 'r2' },
          { department: '이비인후과', confidence: 0.6, reason: 'r3' },
        ],
      }),
      tokensIn: 100,
      tokensOut: 60,
    });
    const result = (await handler({ ...patient, data: validRequest })) as {
      recommendations: Array<{ department: string; confidence: number }>;
    };
    expect(result.recommendations.map((r) => r.confidence)).toEqual([0.85, 0.6, 0.4]);
  });

  it('JSON 파싱 실패 → genericFallback 1건', async () => {
    mockGeminiChat.mockResolvedValueOnce({
      reply: 'not a json at all',
      tokensIn: 50,
      tokensOut: 20,
    });
    const result = (await handler({ ...patient, data: validRequest })) as {
      recommendations: Array<{ department: string }>;
    };
    expect(result.recommendations).toHaveLength(1);
    expect(result.recommendations[0].department).toBe('가정의학과');
  });

  it('audit + audit_logs_v2 두 곳에 기록 (dual-write)', async () => {
    await handler({ ...patient, data: validRequest });
    expect(mockPush.mock.calls.find(([p]) => p === 'triage_audit')).toBeDefined();
    expect(mockAppendAuditLog).toHaveBeenCalled();
    const auditAction = (mockAppendAuditLog.mock.calls[0][2] as { action: string })
      .action;
    expect(auditAction).toBe('triage.recommend');
  });

  it('Gemini 호출 실패 → internal + outcome=internal audit', async () => {
    mockGeminiChat.mockRejectedValueOnce(new Error('upstream timeout'));
    await expect(
      handler({ ...patient, data: validRequest }),
    ).rejects.toMatchObject({ code: 'internal' });
    const auditCall = mockPush.mock.calls.find(
      ([p]) => p === 'triage_audit',
    );
    expect((auditCall![1] as { outcome: string }).outcome).toBe('internal');
  });

  it('허용 목록 외 진료과는 필터링됨 (ALLOWED_DEPARTMENTS)', async () => {
    mockGeminiChat.mockResolvedValueOnce({
      reply: JSON.stringify({
        recommendations: [
          { department: '비공식과', confidence: 0.9, reason: 'r' },
          { department: '내과', confidence: 0.7, reason: 'r' },
          { department: '가정의학과', confidence: 0.5, reason: 'r' },
        ],
      }),
      tokensIn: 100,
      tokensOut: 50,
    });
    const result = (await handler({ ...patient, data: validRequest })) as {
      recommendations: Array<{ department: string }>;
    };
    expect(result.recommendations.find((r) => r.department === '비공식과')).toBeUndefined();
    expect(result.recommendations.length).toBeGreaterThanOrEqual(1);
  });
});
