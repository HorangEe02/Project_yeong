import { describe, it, expect, beforeEach, vi } from 'vitest';

const mockGet = vi.fn();
const mockRemove = vi.fn();
const mockPush = vi.fn();
const mockSend = vi.fn();

vi.mock('firebase-admin', () => {
  const refFactory = (path: string) => ({
    get: () => mockGet(path),
    remove: () => mockRemove(path),
    push: (value: unknown) => mockPush(path, value),
  });
  return {
    default: {
      database: () => ({ ref: refFactory }),
      messaging: () => ({ send: mockSend }),
    },
    database: () => ({ ref: refFactory }),
    messaging: () => ({ send: mockSend }),
  };
});

// onValueUpdated을 식별 함수로 변환 (event handler만 추출)
vi.mock('firebase-functions/v2/database', async () => {
  return {
    onValueUpdated: (_opts: unknown, handler: unknown) => handler,
  };
});

import { onQueueCall } from '../wait_queue/onQueueCall';

type Handler = (event: {
  data: {
    before: { val: () => unknown };
    after: { val: () => unknown };
  };
  params: Record<string, string>;
}) => Promise<void>;

function makeEvent(before: unknown, after: unknown, params?: Record<string, string>) {
  return {
    data: {
      before: { val: () => before },
      after: { val: () => after },
    },
    params: {
      hospitalId: 'demo',
      department: '내과',
      date: '2026-04-24',
      queueNumber: '3',
      ...params,
    },
  };
}

describe('onQueueCall — status 전이 처리', () => {
  const handler = onQueueCall as unknown as Handler;

  beforeEach(() => {
    mockGet.mockReset();
    mockRemove.mockReset();
    mockPush.mockReset();
    mockSend.mockReset();
  });

  it('status waiting → called 전이 시 FCM push 발송 + audit 기록', async () => {
    mockGet.mockResolvedValueOnce({
      val: () => ({
        tokenA: { token: 'fcm-token-a' },
        tokenB: { token: 'fcm-token-b' },
      }),
    });
    mockSend.mockResolvedValue({ messageId: 'ok' });
    mockPush.mockResolvedValue(undefined);

    await handler(
      makeEvent(
        { status: 'waiting', patientUid: 'p1', queueNumber: 3 },
        { status: 'called', patientUid: 'p1', queueNumber: 3 },
      ),
    );

    expect(mockSend).toHaveBeenCalledTimes(2);
    expect(mockSend.mock.calls[0][0]).toMatchObject({
      token: 'fcm-token-a',
      notification: { title: '호출되었습니다' },
      data: expect.objectContaining({
        type: 'queue_call',
        hospitalId: 'demo',
        department: '내과',
      }),
    });
    const auditCall = mockPush.mock.calls.find(([p]) =>
      typeof p === 'string' && p.startsWith('audit_logs_v2/'),
    );
    expect(auditCall?.[1]).toMatchObject({
      action: 'wait_queue.call.push',
      target: 'p1',
      meta: { sent: 2, failed: 0 },
    });
  });

  it('이미 called 상태면 중복 발송 방지', async () => {
    await handler(
      makeEvent(
        { status: 'called', patientUid: 'p1' },
        { status: 'called', patientUid: 'p1' },
      ),
    );
    expect(mockSend).not.toHaveBeenCalled();
    expect(mockPush).not.toHaveBeenCalled();
  });

  it('called 외 다른 status 전이(in_progress 등)는 무시', async () => {
    await handler(
      makeEvent(
        { status: 'called', patientUid: 'p1' },
        { status: 'in_progress', patientUid: 'p1' },
      ),
    );
    expect(mockSend).not.toHaveBeenCalled();
  });

  it('patientUid 누락 시 skip', async () => {
    await handler(
      makeEvent(
        { status: 'waiting' },
        { status: 'called' },
      ),
    );
    expect(mockSend).not.toHaveBeenCalled();
  });

  it('FCM 토큰이 없으면 skip — 로그만', async () => {
    mockGet.mockResolvedValueOnce({ val: () => null });
    await handler(
      makeEvent(
        { status: 'waiting', patientUid: 'p1' },
        { status: 'called', patientUid: 'p1' },
      ),
    );
    expect(mockSend).not.toHaveBeenCalled();
  });

  it('무효 토큰은 발송 실패 시 자동 제거', async () => {
    mockGet.mockResolvedValueOnce({
      val: () => ({
        stale: { token: 'dead-token' },
        valid: { token: 'good-token' },
      }),
    });
    mockSend
      .mockRejectedValueOnce(
        Object.assign(new Error('stale'), {
          code: 'messaging/registration-token-not-registered',
        }),
      )
      .mockResolvedValueOnce({ messageId: 'ok' });
    mockRemove.mockResolvedValue(undefined);
    mockPush.mockResolvedValue(undefined);

    await handler(
      makeEvent(
        { status: 'waiting', patientUid: 'p1' },
        { status: 'called', patientUid: 'p1', queueNumber: 3 },
      ),
    );

    expect(mockSend).toHaveBeenCalledTimes(2);
    expect(mockRemove).toHaveBeenCalledTimes(1);
    expect(mockRemove.mock.calls[0][0]).toBe('user_fcm_tokens/p1/stale');
    const auditCall = mockPush.mock.calls.find(([p]) =>
      typeof p === 'string' && p.startsWith('audit_logs_v2/'),
    );
    expect(auditCall?.[1]).toMatchObject({
      meta: { sent: 1, failed: 1 },
    });
  });

  it('after 데이터 자체가 null이면 skip', async () => {
    await handler(makeEvent({ status: 'waiting' }, null));
    expect(mockSend).not.toHaveBeenCalled();
  });
});
