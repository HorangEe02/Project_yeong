import { describe, it, expect, beforeEach, vi } from 'vitest';

const mockGet = vi.fn();
const mockRemove = vi.fn();
const mockPush = vi.fn();
const mockSend = vi.fn();
const mockSet = vi.fn();
const mockUpdate = vi.fn();

/**
 * dispatcher 가 쓰는 orderByChild/startAt/get 체인 / push().set / update 모두 지원.
 * notification_logs 와 users/{uid}/notifications 경로는 기본 empty snapshot 반환.
 */
function makeSnapshot(value: unknown) {
  return {
    val: () => (value === undefined ? null : value),
    exists: () => value !== undefined && value !== null,
    forEach: (cb: (c: { key: string; val: () => unknown }) => boolean | void) => {
      if (value && typeof value === 'object') {
        for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
          const stop = cb({ key: k, val: () => v });
          if (stop === true) break;
        }
      }
    },
  };
}

vi.mock('firebase-admin', () => {
  let pushSeq = 0;
  const refFactory = (path: string) => ({
    get: () => mockGet(path),
    remove: () => mockRemove(path),
    push: (value?: unknown) => {
      pushSeq += 1;
      const key = `-pushed${pushSeq}`;
      const childPath = `${path}/${key}`;
      if (value !== undefined) mockPush(path, value);
      return {
        key,
        set: (v: unknown) => {
          mockPush(path, v);
          return mockSet(childPath, v);
        },
        update: (p: unknown) => mockUpdate(childPath, p),
      };
    },
    set: (v: unknown) => {
      mockPush(path, v);
      return mockSet(path, v);
    },
    update: (p: unknown) => mockUpdate(path, p),
    orderByChild: (_c: string) => ({
      startAt: (_s: unknown) => ({
        async get() {
          // dispatcher findByIdempotencyKey — 기본 empty
          return makeSnapshot(null);
        },
      }),
    }),
  });
  return {
    default: {
      database: Object.assign(() => ({ ref: refFactory }), {
        ServerValue: { increment: (n: number) => ({ __inc: n }) },
      }),
      messaging: () => ({ send: mockSend }),
    },
    database: Object.assign(() => ({ ref: refFactory }), {
      ServerValue: { increment: (n: number) => ({ __inc: n }) },
    }),
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

describe('onQueueCall — status 전이 처리 (dispatcher 경유)', () => {
  const handler = onQueueCall as unknown as Handler;

  /** path → snapshot value 매핑 기반 기본 mock */
  function setPathGets(map: Record<string, unknown>) {
    mockGet.mockImplementation((path: string) => {
      const v = Object.prototype.hasOwnProperty.call(map, path) ? map[path] : null;
      return Promise.resolve(makeSnapshot(v));
    });
  }

  beforeEach(() => {
    mockGet.mockReset();
    mockRemove.mockReset();
    mockPush.mockReset();
    mockSend.mockReset();
    mockSet.mockReset();
    mockUpdate.mockReset();
    // default: 모든 경로 empty snapshot
    mockGet.mockResolvedValue(makeSnapshot(null));
  });

  it('status waiting → called 전이 시 Dispatcher 경유 FCM push + audit 기록', async () => {
    setPathGets({
      'user_fcm_tokens/p1': {
        tokenA: { token: 'fcm-token-a' },
        tokenB: { token: 'fcm-token-b' },
      },
      // users/p1/notifications → null (기본) = prefs 없음, 모두 허용
    });
    mockSend.mockResolvedValue('providerMsgId');
    mockPush.mockResolvedValue(undefined);
    mockSet.mockResolvedValue(undefined);
    mockUpdate.mockResolvedValue(undefined);

    await handler(
      makeEvent(
        { status: 'waiting', patientUid: 'p1', queueNumber: 3 },
        { status: 'called', patientUid: 'p1', queueNumber: 3 },
      ),
    );

    // FCM 2개 토큰 모두 발송
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
    // Audit 기록 — dispatcher outcome 포함
    const auditCall = mockPush.mock.calls.find(([p]) =>
      typeof p === 'string' && p.startsWith('audit_logs_v2/'),
    );
    expect(auditCall?.[1]).toMatchObject({
      action: 'wait_queue.call.push',
      target: 'p1',
      meta: expect.objectContaining({
        deliveredChannel: 'fcm',
      }),
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

  it('FCM 토큰이 없으면 FcmAdapter throw → dispatcher 는 deliveredChannel=null 로 finalize', async () => {
    // 모든 path empty snapshot (default beforeEach)
    mockPush.mockResolvedValue(undefined);
    mockSet.mockResolvedValue(undefined);
    mockUpdate.mockResolvedValue(undefined);

    await handler(
      makeEvent(
        { status: 'waiting', patientUid: 'p1' },
        { status: 'called', patientUid: 'p1' },
      ),
    );
    expect(mockSend).not.toHaveBeenCalled();
    const auditCall = mockPush.mock.calls.find(([p]) =>
      typeof p === 'string' && p.startsWith('audit_logs_v2/'),
    );
    expect(auditCall?.[1]).toMatchObject({
      meta: expect.objectContaining({ deliveredChannel: null }),
    });
  });

  it('무효 토큰은 발송 실패 시 자동 제거 + dispatcher 가 fcm 으로 deliver', async () => {
    setPathGets({
      'user_fcm_tokens/p1': {
        stale: { token: 'dead-token' },
        valid: { token: 'good-token' },
      },
    });
    mockSend
      .mockRejectedValueOnce(
        Object.assign(new Error('stale'), {
          code: 'messaging/registration-token-not-registered',
        }),
      )
      .mockResolvedValueOnce('good-msgid');
    mockRemove.mockResolvedValue(undefined);
    mockPush.mockResolvedValue(undefined);
    mockSet.mockResolvedValue(undefined);
    mockUpdate.mockResolvedValue(undefined);

    await handler(
      makeEvent(
        { status: 'waiting', patientUid: 'p1' },
        { status: 'called', patientUid: 'p1', queueNumber: 3 },
      ),
    );

    expect(mockSend).toHaveBeenCalledTimes(2);
    expect(mockRemove).toHaveBeenCalledTimes(1);
    expect(mockRemove.mock.calls[0][0]).toBe('user_fcm_tokens/p1/stale');
    // 적어도 한 토큰은 성공 → FcmAdapter 'sent' → dispatcher deliveredChannel='fcm'
    const auditCall = mockPush.mock.calls.find(([p]) =>
      typeof p === 'string' && p.startsWith('audit_logs_v2/'),
    );
    expect(auditCall?.[1]).toMatchObject({
      meta: expect.objectContaining({ deliveredChannel: 'fcm' }),
    });
  });

  it('after 데이터 자체가 null이면 skip', async () => {
    await handler(makeEvent({ status: 'waiting' }, null));
    expect(mockSend).not.toHaveBeenCalled();
  });
});
