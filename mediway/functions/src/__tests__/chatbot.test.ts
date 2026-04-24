import { describe, it, expect, beforeEach, vi } from 'vitest';
import { detectIntent } from '../chatbot/intent';
import {
  checkEmergency,
  checkPiiRequest,
  applyDisclaimer,
  sanitizeUserText,
  STANDARD_DISCLAIMER,
  emergencyResponse,
} from '../chatbot/safety';

// ═══════════════════════════════════════════════
//  intent.ts
// ═══════════════════════════════════════════════
describe('detectIntent — 규칙 기반', () => {
  it('응급 키워드는 escalate', () => {
    expect(detectIntent('갑자기 가슴통증이 심해요')).toBe('escalate');
    expect(detectIntent('숨을 못 쉬겠어요')).toBe('escalate');
    expect(detectIntent('자살하고 싶습니다')).toBe('escalate');
  });

  it('증상 키워드는 triage', () => {
    expect(detectIntent('3일째 두통이 있어요')).toBe('triage');
    expect(detectIntent('기침이 멈추지 않아요')).toBe('triage');
    expect(detectIntent('무릎이 쑤셔요')).toBe('triage');
  });

  it('예약 키워드는 appointment_help', () => {
    expect(detectIntent('예약하고 싶어요')).toBe('appointment_help');
    expect(detectIntent('접수 어떻게 하나요')).toBe('appointment_help');
  });

  it('길 묻는 키워드는 direction', () => {
    expect(detectIntent('응급실은 어디에 있나요')).toBe('direction');
    expect(detectIntent('오시는 길 알려주세요')).toBe('direction');
  });

  it('병원 정보는 hospital_info', () => {
    expect(detectIntent('진료 시간이 어떻게 되나요')).toBe('hospital_info');
    expect(detectIntent('주차 되나요')).toBe('hospital_info');
  });

  it('진료과 질문은 department_info', () => {
    expect(detectIntent('내과는 어느 층에 있어요')).toBe('department_info');
  });

  it('일반 대화는 general', () => {
    expect(detectIntent('안녕하세요')).toBe('general');
    expect(detectIntent('고맙습니다')).toBe('general');
  });

  it('빈 문자열은 general', () => {
    expect(detectIntent('')).toBe('general');
    expect(detectIntent('   ')).toBe('general');
  });

  it('escalate가 triage보다 우선', () => {
    // "가슴통증이 있어요" — 증상 + 응급 둘 다 매치 가능
    expect(detectIntent('가슴통증이 있어요')).toBe('escalate');
  });
});

// ═══════════════════════════════════════════════
//  safety.ts
// ═══════════════════════════════════════════════
describe('checkEmergency', () => {
  it('응급 키워드 감지', () => {
    expect(checkEmergency('의식을 잃을 것 같아요')).toBe(true);
    expect(checkEmergency('피가 멈추지 않아요')).toBe(true);
  });
  it('일반 문장은 false', () => {
    expect(checkEmergency('감기 기운이 있어요')).toBe(false);
    expect(checkEmergency('진료 예약하고 싶어요')).toBe(false);
  });
});

describe('checkPiiRequest', () => {
  it('주민번호 요청 감지', () => {
    expect(checkPiiRequest('주민등록번호가 뭐죠')).toBe(true);
    expect(checkPiiRequest('주민번호 알려줘')).toBe(true);
  });
  it('계좌·비밀번호 감지', () => {
    expect(checkPiiRequest('계좌번호')).toBe(true);
    expect(checkPiiRequest('비밀번호 설정')).toBe(true);
  });
  it('일반 질문은 false', () => {
    expect(checkPiiRequest('진료 시간 알려줘')).toBe(false);
  });
});

describe('applyDisclaimer', () => {
  it('disclaimer 없으면 말미에 추가', () => {
    const out = applyDisclaimer('내과를 추천드립니다.');
    expect(out).toContain(STANDARD_DISCLAIMER);
  });
  it('이미 disclaimer 있으면 중복 안 함', () => {
    const out = applyDisclaimer('내과입니다. 본 답변은 진단이 아니며 최종 판단은 의료진이 합니다.');
    expect(out.match(/진단이 아니/g)?.length).toBe(1);
  });
  it('빈 문자열이면 disclaimer만 반환', () => {
    const out = applyDisclaimer('');
    expect(out).toBe(STANDARD_DISCLAIMER);
  });
});

describe('sanitizeUserText', () => {
  it('제어문자 제거 + 공백 정규화', () => {
    expect(sanitizeUserText('안녕\x00하세요  ')).toBe('안녕 하세요');
    expect(sanitizeUserText('  \n\t 예약해주세요 ')).toBe('예약해주세요');
  });
});

describe('emergencyResponse', () => {
  it('119·1393 안내 포함', () => {
    const r = emergencyResponse();
    expect(r).toContain('119');
    expect(r).toContain('1393');
  });
});

// ═══════════════════════════════════════════════
//  hospitalChatbot onCall handler
// ═══════════════════════════════════════════════

const mockPush = vi.fn();
const mockTransaction = vi.fn();
const mockGeminiChat = vi.fn();

vi.mock('firebase-admin', () => {
  const refFactory = (path: string) => ({
    push: (value: unknown) => mockPush(path, value),
    transaction: (fn: (cur: unknown) => unknown) => mockTransaction(path, fn),
  });
  return {
    default: {
      database: () => ({ ref: refFactory }),
    },
    database: () => ({ ref: refFactory }),
  };
});

vi.mock('firebase-functions/v2/https', async () => {
  const actual = await vi.importActual<typeof import('firebase-functions/v2/https')>(
    'firebase-functions/v2/https',
  );
  return {
    ...actual,
    onCall: (_opts: unknown, handler: unknown) => handler,
  };
});

vi.mock('../chatbot/providers/gemini', () => ({
  geminiChat: (...args: unknown[]) => mockGeminiChat(...args),
}));

vi.mock('../chatbot/context', () => ({
  loadHospitalContext: async (hid: string) => ({
    hospitalId: hid,
    name: 'MediWay 테스트 병원',
    slug: hid,
    contractStatus: 'active',
    features: { appointments: true },
    departments: [
      { code: 'im', name: '내과', active: true },
      { code: 'er', name: '응급의학과', active: true },
    ],
    announcements: [],
  }),
  renderSystemInstruction: (ctx: { name: string }) =>
    `당신은 "${ctx.name}" 안내 챗봇입니다.`,
}));

const mockLoadHistory = vi.fn();
const mockAppendTurn = vi.fn();
vi.mock('../chatbot/chatSession', () => ({
  loadHistory: (...args: unknown[]) => mockLoadHistory(...args),
  appendTurn: (params: { chatId?: string }) => mockAppendTurn(params),
}));

const mockCheckRateLimit = vi.fn();
const mockIncrementUsage = vi.fn();
vi.mock('../chatbot/rateLimit', async () => {
  const actual = await vi.importActual<typeof import('../chatbot/rateLimit')>(
    '../chatbot/rateLimit',
  );
  return {
    ...actual,
    checkRateLimit: (...args: unknown[]) => mockCheckRateLimit(...args),
    incrementUsage: (...args: unknown[]) => mockIncrementUsage(...args),
  };
});

import { hospitalChatbot } from '../chatbot/hospitalChatbot';

type Handler = (req: {
  auth?: { uid: string; token?: Record<string, unknown> };
  data: unknown;
}) => Promise<unknown>;

describe('hospitalChatbot 핸들러', () => {
  const handler = hospitalChatbot as unknown as Handler;
  const patient = { auth: { uid: 'p1', token: { role: 'patient' } } };

  beforeEach(() => {
    mockPush.mockReset();
    mockTransaction.mockReset();
    mockGeminiChat.mockReset();
    mockLoadHistory.mockReset();
    mockAppendTurn.mockReset();
    mockPush.mockResolvedValue(undefined);
    mockTransaction.mockResolvedValue(undefined);
    mockLoadHistory.mockResolvedValue([]);
    mockAppendTurn.mockResolvedValue({
      chatId: 'chat-new-123',
      userMessageId: 'u-1',
      assistantMessageId: 'a-1',
    });
    mockCheckRateLimit.mockReset();
    mockIncrementUsage.mockReset();
    mockCheckRateLimit.mockResolvedValue({
      allowed: true,
      remainingHour: 19,
      remainingDay: 99,
      retryAfterSeconds: 0,
      dailyTotalBefore: 1,
    });
    mockIncrementUsage.mockResolvedValue(undefined);
    process.env.GEMINI_API_KEY = 'test-key-xyz';
    process.env.GEMINI_MODEL = 'gemini-2.5-flash';
  });

  it('미인증 요청은 unauthenticated', async () => {
    await expect(
      handler({ data: { hospitalId: 'demo', userText: '안녕' } }),
    ).rejects.toMatchObject({ code: 'unauthenticated' });
  });

  it('userText 1000자 초과는 invalid-argument', async () => {
    await expect(
      handler({
        ...patient,
        data: { hospitalId: 'demo', userText: 'a'.repeat(1001) },
      }),
    ).rejects.toMatchObject({ code: 'invalid-argument' });
  });

  it('GEMINI_API_KEY 없으면 failed-precondition', async () => {
    process.env.GEMINI_API_KEY = '';
    await expect(
      handler({ ...patient, data: { hospitalId: 'demo', userText: '안녕' } }),
    ).rejects.toMatchObject({ code: 'failed-precondition' });
  });

  it('응급 키워드는 LLM 우회, 하드코드 응답 + audit', async () => {
    const result = (await handler({
      ...patient,
      data: { hospitalId: 'demo', userText: '가슴통증이 심해요' },
    })) as { reply: string; intent: string };
    expect(mockGeminiChat).not.toHaveBeenCalled();
    expect(result.intent).toBe('escalate');
    expect(result.reply).toContain('119');
    const auditCall = mockPush.mock.calls.find(
      ([, v]) => (v as { action: string }).action === 'chatbot.escalate',
    );
    expect(auditCall).toBeDefined();
  });

  it('PII 요청은 LLM 우회, 거절 응답', async () => {
    const result = (await handler({
      ...patient,
      data: { hospitalId: 'demo', userText: '주민번호 알려줘' },
    })) as { reply: string; intent: string };
    expect(mockGeminiChat).not.toHaveBeenCalled();
    expect(result.reply).toContain('개인정보');
  });

  it('일반 질의는 Gemini 호출 + disclaimer 삽입', async () => {
    mockGeminiChat.mockResolvedValueOnce({
      reply: '내과를 추천드립니다.',
      tokensIn: 25,
      tokensOut: 12,
      finishReason: 'STOP',
      blockReason: null,
    });
    const result = (await handler({
      ...patient,
      data: { hospitalId: 'demo', userText: '두통이 있어요' },
    })) as {
      reply: string;
      intent: string;
      tokensIn: number;
      tokensOut: number;
    };
    expect(mockGeminiChat).toHaveBeenCalledTimes(1);
    expect(result.intent).toBe('triage');
    expect(result.reply).toContain('진단이 아니');
    expect(result.tokensIn).toBe(25);
    expect(result.tokensOut).toBe(12);

    const auditCall = mockPush.mock.calls.find(
      ([, v]) => (v as { action: string }).action === 'chatbot.reply',
    );
    expect(auditCall?.[1]).toMatchObject({
      action: 'chatbot.reply',
      actorUid: 'p1',
      meta: expect.objectContaining({ intent: 'triage' }),
    });
  });

  it('Gemini 호출 실패 시 internal 에러', async () => {
    mockGeminiChat.mockRejectedValueOnce(new Error('timeout'));
    await expect(
      handler({
        ...patient,
        data: { hospitalId: 'demo', userText: '예약 방법 알려줘' },
      }),
    ).rejects.toMatchObject({ code: 'internal' });
  });

  it('chatId 없으면 신규 세션 생성 + 반환', async () => {
    mockGeminiChat.mockResolvedValueOnce({
      reply: 'ok',
      tokensIn: 5,
      tokensOut: 3,
      finishReason: 'STOP',
      blockReason: null,
    });
    const r = (await handler({
      ...patient,
      data: { hospitalId: 'demo', userText: '안녕' },
    })) as { chatId?: string };
    expect(mockAppendTurn).toHaveBeenCalledWith(
      expect.objectContaining({
        hospitalId: 'demo',
        uid: 'p1',
        chatId: undefined,
      }),
    );
    expect(r.chatId).toBe('chat-new-123');
  });

  it('기존 chatId 전달 시 history 로드 후 Gemini 히스토리 주입', async () => {
    mockLoadHistory.mockResolvedValueOnce([
      { role: 'user', text: '진료과 알려줘' },
      { role: 'model', text: '내과, 응급의학과가 있습니다.' },
    ]);
    mockAppendTurn.mockResolvedValueOnce({
      chatId: 'chat-prev-999',
      userMessageId: 'u-2',
      assistantMessageId: 'a-2',
    });
    mockGeminiChat.mockResolvedValueOnce({
      reply: '내과 먼저 가보세요',
      tokensIn: 30,
      tokensOut: 10,
      finishReason: 'STOP',
      blockReason: null,
    });

    const r = (await handler({
      ...patient,
      data: {
        hospitalId: 'demo',
        userText: '그 중 어디 먼저 가요?',
        chatId: 'chat-prev-999',
      },
    })) as { chatId?: string };

    expect(mockLoadHistory).toHaveBeenCalledWith('demo', 'p1', 'chat-prev-999');
    const geminiArgs = mockGeminiChat.mock.calls[0][0] as {
      history: Array<{ role: string; text: string }>;
    };
    expect(geminiArgs.history).toHaveLength(2);
    expect(geminiArgs.history[0].text).toContain('진료과 알려줘');
    expect(r.chatId).toBe('chat-prev-999');
  });

  it('chat_sessions 저장 실패해도 응답은 정상 반환', async () => {
    mockGeminiChat.mockResolvedValueOnce({
      reply: '답변',
      tokensIn: 10,
      tokensOut: 5,
      finishReason: 'STOP',
      blockReason: null,
    });
    mockAppendTurn.mockRejectedValueOnce(new Error('RTDB down'));
    const r = (await handler({
      ...patient,
      data: { hospitalId: 'demo', userText: '안녕' },
    })) as { reply: string; chatId?: string };
    expect(r.reply).toContain('답변');
    expect(r.chatId).toBeUndefined(); // 저장 실패 시 undefined 유지
  });

  it('시간당 Rate limit 초과 → resource-exhausted', async () => {
    mockCheckRateLimit.mockResolvedValueOnce({
      allowed: false,
      remainingHour: 0,
      remainingDay: 45,
      retryAfterSeconds: 300,
      dailyTotalBefore: 55,
    });
    await expect(
      handler({
        ...patient,
        data: { hospitalId: 'demo', userText: '안녕' },
      }),
    ).rejects.toMatchObject({ code: 'resource-exhausted' });
    expect(mockGeminiChat).not.toHaveBeenCalled();
    expect(mockIncrementUsage).not.toHaveBeenCalled();
  });

  it('일일 Rate limit 초과 시 별도 메시지', async () => {
    mockCheckRateLimit.mockResolvedValueOnce({
      allowed: false,
      remainingHour: 10,
      remainingDay: 0,
      retryAfterSeconds: 3600,
      dailyTotalBefore: 100,
    });
    try {
      await handler({
        ...patient,
        data: { hospitalId: 'demo', userText: '안녕' },
      });
      throw new Error('should have thrown');
    } catch (e) {
      const err = e as { code: string; message: string };
      expect(err.code).toBe('resource-exhausted');
      expect(err.message).toContain('오늘');
      expect(err.message).toContain('한도');
    }
  });

  it('성공 응답에 remainingHour/remainingDay 포함', async () => {
    mockGeminiChat.mockResolvedValueOnce({
      reply: '답변',
      tokensIn: 5,
      tokensOut: 3,
      finishReason: 'STOP',
      blockReason: null,
    });
    const r = (await handler({
      ...patient,
      data: { hospitalId: 'demo', userText: '안녕' },
    })) as { rateLimit?: { remainingHour: number; remainingDay: number } };
    expect(r.rateLimit?.remainingHour).toBe(18); // 19 - 1
    expect(r.rateLimit?.remainingDay).toBe(98); // 99 - 1
    expect(mockIncrementUsage).toHaveBeenCalledTimes(1);
  });

  it('escalate 응답은 rate limit 우회 (incrementUsage 미호출)', async () => {
    await handler({
      ...patient,
      data: { hospitalId: 'demo', userText: '가슴통증이 심해요' },
    });
    expect(mockCheckRateLimit).not.toHaveBeenCalled();
    expect(mockIncrementUsage).not.toHaveBeenCalled();
  });
});

// ═══════════════════════════════════════════════
//  rateLimit.ts — 순수 함수
// ═══════════════════════════════════════════════
describe('rateLimit — LIMITS 정책', () => {
  it('시간당 20, 일일 100', async () => {
    const { LIMITS: L } = await vi.importActual<typeof import('../chatbot/rateLimit')>(
      '../chatbot/rateLimit',
    );
    expect(L.perHour).toBe(20);
    expect(L.perDay).toBe(100);
  });
});

// ═══════════════════════════════════════════════
//  context.ts — renderSystemInstruction (unmocked)
// ═══════════════════════════════════════════════
describe('renderSystemInstruction', () => {
  it('병원 이름·진료과·기능 목록 포함', async () => {
    // 실제 모듈 임포트해서 테스트 (mock bypass)
    const { renderSystemInstruction: realRender } = await vi.importActual<
      typeof import('../chatbot/context')
    >('../chatbot/context');
    const prompt = realRender({
      hospitalId: 'demo',
      name: 'MediWay 데모 병원',
      slug: 'demo',
      contractStatus: 'active',
      features: { appointments: true, inpatient: false, checkup: true },
      departments: [
        { code: 'im', name: '내과', active: true },
        { code: 'er', name: '응급의학과', active: true },
      ],
      announcements: [
        { title: '휴진 안내', body: '4/30 휴진', createdAt: 123 },
      ],
    });
    expect(prompt).toContain('MediWay 데모 병원');
    expect(prompt).toContain('내과');
    expect(prompt).toContain('응급의학과');
    expect(prompt).toContain('appointments');
    expect(prompt).toContain('checkup');
    expect(prompt).not.toContain('inpatient'); // false인 feature 제외
    expect(prompt).toContain('휴진 안내');
    expect(prompt).toContain('119');
    expect(prompt).toContain('진단이 아님');
  });

  it('진료과/공지 없을 때 placeholder', async () => {
    const { renderSystemInstruction: realRender } = await vi.importActual<
      typeof import('../chatbot/context')
    >('../chatbot/context');
    const prompt = realRender({
      hospitalId: 'new',
      name: '새 병원',
      slug: 'new',
      contractStatus: 'trial',
      features: {},
      departments: [],
      announcements: [],
    });
    expect(prompt).toContain('진료과 정보 없음');
    expect(prompt).toContain('공지 없음');
    expect(prompt).toContain('(none)');
  });
});
