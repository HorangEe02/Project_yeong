import { describe, it, expect, beforeEach, vi } from 'vitest';

const mockCallable = vi.fn();
const mockHttpsCallable = vi.fn(() => mockCallable);

vi.mock('firebase/functions', () => ({
  httpsCallable: (...args: unknown[]) => mockHttpsCallable(...args),
}));

vi.mock('@/config/firebase', () => ({
  functions: { __mocked: true },
  isFirebaseConfigured: () => true,
}));

import { sendChatbotMessage } from '../chatbot';

function hspError(code: string, message: string, details?: unknown): Error {
  const err = new Error(message);
  (err as Error & { code: string; details?: unknown }).code = code;
  if (details !== undefined) (err as Error & { details: unknown }).details = details;
  return err;
}

describe('sendChatbotMessage', () => {
  beforeEach(() => {
    mockCallable.mockReset();
    mockHttpsCallable.mockClear();
  });

  it('정상 응답 passthrough + hospitalChatbot 함수명 전달', async () => {
    mockCallable.mockResolvedValue({
      data: {
        reply: '안녕하세요.',
        intent: 'general',
        disclaimer: '진단이 아닙니다',
        chatId: 'chat-42',
      },
    });
    const r = await sendChatbotMessage({ hospitalId: 'demo', userText: '안녕' });
    expect(r.reply).toBe('안녕하세요.');
    expect(r.chatId).toBe('chat-42');
    expect(mockHttpsCallable).toHaveBeenCalledWith(
      expect.anything(),
      'hospitalChatbot',
    );
  });

  it('userText 공백/빈문자 → 로컬 invalid_argument, 서버 호출 없음', async () => {
    await expect(
      sendChatbotMessage({ hospitalId: 'demo', userText: '   ' }),
    ).rejects.toMatchObject({ code: 'invalid_argument' });
    expect(mockCallable).not.toHaveBeenCalled();
  });

  it('chatId falsy 면 payload 에서 생략 (null/undefined 전송 방지)', async () => {
    mockCallable.mockResolvedValue({ data: { reply: 'ok', intent: 'general', disclaimer: '' } });
    await sendChatbotMessage({ hospitalId: 'demo', userText: 'hello' });
    const payload = mockCallable.mock.calls[0][0];
    expect('chatId' in payload).toBe(false);
  });

  it('chatId truthy 면 그대로 전달', async () => {
    mockCallable.mockResolvedValue({ data: { reply: 'ok', intent: 'general', disclaimer: '' } });
    await sendChatbotMessage({ hospitalId: 'demo', userText: 'hello', chatId: 'chat-7' });
    const payload = mockCallable.mock.calls[0][0];
    expect(payload.chatId).toBe('chat-7');
  });

  it('userText 는 trim 후 전송', async () => {
    mockCallable.mockResolvedValue({ data: { reply: 'ok', intent: 'general', disclaimer: '' } });
    await sendChatbotMessage({ hospitalId: 'demo', userText: '  안녕  ' });
    expect(mockCallable.mock.calls[0][0].userText).toBe('안녕');
  });

  it('unauthenticated 에러 normalize', async () => {
    mockCallable.mockRejectedValue(hspError('functions/unauthenticated', '로그인 필요'));
    await expect(
      sendChatbotMessage({ hospitalId: 'demo', userText: 'hi' }),
    ).rejects.toMatchObject({ code: 'unauthenticated' });
  });

  it('resource-exhausted → rate_limited + retryAfterSeconds 전파', async () => {
    mockCallable.mockRejectedValue(
      hspError(
        'functions/resource-exhausted',
        '시간당 한도를 초과했습니다',
        { retryAfterSeconds: 3600 },
      ),
    );
    await expect(
      sendChatbotMessage({ hospitalId: 'demo', userText: 'hi' }),
    ).rejects.toMatchObject({
      code: 'rate_limited',
      retryAfterSeconds: 3600,
    });
  });

  it('invalid-argument → invalid_argument', async () => {
    mockCallable.mockRejectedValue(hspError('functions/invalid-argument', '질문이 비어있습니다'));
    await expect(
      sendChatbotMessage({ hospitalId: 'demo', userText: 'hi' }),
    ).rejects.toMatchObject({ code: 'invalid_argument' });
  });

  it('unavailable/deadline-exceeded → network', async () => {
    mockCallable.mockRejectedValue(hspError('functions/unavailable', 'timeout'));
    await expect(
      sendChatbotMessage({ hospitalId: 'demo', userText: 'hi' }),
    ).rejects.toMatchObject({ code: 'network' });
  });

  it('internal → internal 유지', async () => {
    mockCallable.mockRejectedValue(hspError('functions/internal', 'Gemini 호출 실패'));
    await expect(
      sendChatbotMessage({ hospitalId: 'demo', userText: 'hi' }),
    ).rejects.toMatchObject({ code: 'internal' });
  });

  it('알 수 없는 code → unknown fallback', async () => {
    mockCallable.mockRejectedValue(hspError('functions/aborted', '???'));
    await expect(
      sendChatbotMessage({ hospitalId: 'demo', userText: 'hi' }),
    ).rejects.toMatchObject({ code: 'unknown' });
  });
});
