import { describe, it, expect, beforeEach, vi } from 'vitest';

const mockCallable = vi.fn();
const mockHttpsCallable = vi.fn((..._args: unknown[]) => mockCallable);

vi.mock('firebase/functions', () => ({
  httpsCallable: (...args: unknown[]) => mockHttpsCallable(...args),
}));

vi.mock('@/config/firebase', () => ({
  functions: { __mocked: true },
  isFirebaseConfigured: () => true,
}));

import { requestTriageRecommendation } from '../triage';

function hspError(code: string, message: string, details?: unknown): Error {
  const err = new Error(message);
  (err as Error & { code: string; details?: unknown }).code = code;
  if (details !== undefined) (err as Error & { details: unknown }).details = details;
  return err;
}

const validInput = {
  hospitalId: 'demo',
  symptomText: '2일째 기침과 미열이 있어요',
};

describe('requestTriageRecommendation — payload 정규화', () => {
  beforeEach(() => {
    mockCallable.mockReset();
    mockHttpsCallable.mockClear();
  });

  it('정상 응답 passthrough + triageSymptoms 함수명 전달', async () => {
    mockCallable.mockResolvedValue({
      data: {
        recommendations: [
          { department: '내과', confidence: 0.85, reason: 'r' },
          { department: '가정의학과', confidence: 0.55, reason: 'r' },
          { department: '이비인후과', confidence: 0.4, reason: 'r' },
        ],
        disclaimer: '진단이 아닙니다',
        model: 'gemini-2.5-flash',
        tokensIn: 100,
        tokensOut: 60,
        rateLimit: { remainingHour: 9 },
      },
    });
    const r = await requestTriageRecommendation(validInput);
    expect(r.recommendations).toHaveLength(3);
    expect(r.disclaimer).toBe('진단이 아닙니다');
    expect(mockHttpsCallable).toHaveBeenCalledWith(
      expect.anything(),
      'triageSymptoms',
    );
  });

  it('symptomText trim 처리', async () => {
    mockCallable.mockResolvedValue({ data: { recommendations: [] } });
    await requestTriageRecommendation({
      hospitalId: 'demo',
      symptomText: '   2일째 기침과 미열이 있어요   ',
    });
    expect(mockCallable.mock.calls[0][0].symptomText).toBe('2일째 기침과 미열이 있어요');
  });

  it('빈 문자열 → invalid_argument (네트워크 호출 없음)', async () => {
    await expect(
      requestTriageRecommendation({ hospitalId: 'demo', symptomText: '   ' }),
    ).rejects.toMatchObject({
      code: 'invalid_argument',
      message: '증상 설명을 입력해 주세요',
    });
    expect(mockCallable).not.toHaveBeenCalled();
  });

  it('10자 미만 → invalid_argument (네트워크 호출 없음)', async () => {
    await expect(
      requestTriageRecommendation({ hospitalId: 'demo', symptomText: '아파요' }),
    ).rejects.toMatchObject({
      code: 'invalid_argument',
      message: '증상 설명은 10자 이상 입력해 주세요',
    });
    expect(mockCallable).not.toHaveBeenCalled();
  });

  it('500자 초과 → invalid_argument (네트워크 호출 없음)', async () => {
    await expect(
      requestTriageRecommendation({
        hospitalId: 'demo',
        symptomText: '아'.repeat(501),
      }),
    ).rejects.toMatchObject({ code: 'invalid_argument' });
    expect(mockCallable).not.toHaveBeenCalled();
  });
});

describe('requestTriageRecommendation — error normalize', () => {
  beforeEach(() => {
    mockCallable.mockReset();
  });

  it('unauthenticated → code=unauthenticated', async () => {
    mockCallable.mockRejectedValue(hspError('functions/unauthenticated', '로그인 필요'));
    await expect(requestTriageRecommendation(validInput)).rejects.toMatchObject({
      code: 'unauthenticated',
    });
  });

  it('failed-precondition + aiTriage 키워드 → feature_disabled', async () => {
    mockCallable.mockRejectedValue(
      hspError(
        'functions/failed-precondition',
        '이 병원에서는 AI 진료과 추천 기능이 활성화되어 있지 않습니다',
      ),
    );
    await expect(requestTriageRecommendation(validInput)).rejects.toMatchObject({
      code: 'feature_disabled',
    });
  });

  it('failed-precondition + GEMINI_API_KEY → internal', async () => {
    mockCallable.mockRejectedValue(
      hspError('functions/failed-precondition', 'GEMINI_API_KEY 미설정'),
    );
    await expect(requestTriageRecommendation(validInput)).rejects.toMatchObject({
      code: 'internal',
    });
  });

  it('resource-exhausted → rate_limited + retryAfterSeconds 보존', async () => {
    mockCallable.mockRejectedValue(
      hspError('functions/resource-exhausted', '시간당 한도 초과', {
        retryAfterSeconds: 1234,
      }),
    );
    const err = await requestTriageRecommendation(validInput).catch((e) => e);
    expect(err.code).toBe('rate_limited');
    expect(err.retryAfterSeconds).toBe(1234);
  });

  it('invalid-argument 서버 측 → invalid_argument + 메시지 보존', async () => {
    mockCallable.mockRejectedValue(
      hspError('functions/invalid-argument', '증상 설명은 10자 이상'),
    );
    await expect(requestTriageRecommendation(validInput)).rejects.toMatchObject({
      code: 'invalid_argument',
      message: '증상 설명은 10자 이상',
    });
  });

  it('unavailable → network', async () => {
    mockCallable.mockRejectedValue(hspError('functions/unavailable', '연결 실패'));
    await expect(requestTriageRecommendation(validInput)).rejects.toMatchObject({
      code: 'network',
    });
  });

  it('deadline-exceeded → network', async () => {
    mockCallable.mockRejectedValue(hspError('functions/deadline-exceeded', '시간 초과'));
    await expect(requestTriageRecommendation(validInput)).rejects.toMatchObject({
      code: 'network',
    });
  });

  it('internal → internal', async () => {
    mockCallable.mockRejectedValue(hspError('functions/internal', 'AI 응답 실패'));
    await expect(requestTriageRecommendation(validInput)).rejects.toMatchObject({
      code: 'internal',
      message: 'AI 응답 실패',
    });
  });

  it('알 수 없는 code → unknown', async () => {
    mockCallable.mockRejectedValue(hspError('functions/something-new', '?'));
    await expect(requestTriageRecommendation(validInput)).rejects.toMatchObject({
      code: 'unknown',
    });
  });
});

describe('requestTriageRecommendation — Firebase 미설정', () => {
  beforeEach(() => {
    mockCallable.mockReset();
  });

  it('isFirebaseConfigured()=false → internal (callable 호출 없음)', async () => {
    vi.resetModules();
    vi.doMock('@/config/firebase', () => ({
      functions: { __mocked: true },
      isFirebaseConfigured: () => false,
    }));
    const { requestTriageRecommendation: fn } = await import('../triage');
    await expect(fn(validInput)).rejects.toMatchObject({
      code: 'internal',
      message: 'Firebase 미설정',
    });
    expect(mockCallable).not.toHaveBeenCalled();
    vi.doUnmock('@/config/firebase');
  });
});
