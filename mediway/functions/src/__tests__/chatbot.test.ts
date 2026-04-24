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
    mockPush.mockResolvedValue(undefined);
    mockTransaction.mockResolvedValue(undefined);
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
});
