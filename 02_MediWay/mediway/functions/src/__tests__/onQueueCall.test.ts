import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  dispatchCallNotification,
  type QueueCallDeps,
} from '../onQueueCall';

const getTokensMock = vi.fn();
const sendMock = vi.fn();

const deps: QueueCallDeps = {
  getTokens: (uid) => getTokensMock(uid),
  send: (msg) => sendMock(msg),
};

const params = { hospitalId: 'demo', entryId: 'entry-1' };

beforeEach(() => {
  getTokensMock.mockReset();
  sendMock.mockReset();
});

describe('dispatchCallNotification', () => {
  it('after null → skipped:after-null', async () => {
    const r = await dispatchCallNotification(params, null, null, deps);
    expect(r).toEqual({ skipped: true, reason: 'after-null' });
    expect(getTokensMock).not.toHaveBeenCalled();
  });

  it('status !== called → skipped:not-called', async () => {
    const r = await dispatchCallNotification(
      params,
      { status: 'waiting' },
      { status: 'waiting', patientUid: 'u' },
      deps,
    );
    expect(r).toEqual({ skipped: true, reason: 'not-called' });
  });

  it('이미 called였던 상태 → skipped:already-called', async () => {
    const r = await dispatchCallNotification(
      params,
      { status: 'called' },
      { status: 'called', patientUid: 'u', department: '내과', number: 1 },
      deps,
    );
    expect(r).toEqual({ skipped: true, reason: 'already-called' });
  });

  it('patientUid 없음 → skipped:no-patient-uid', async () => {
    const r = await dispatchCallNotification(
      params,
      { status: 'waiting' },
      { status: 'called', department: '내과', number: 1 },
      deps,
    );
    expect(r).toEqual({ skipped: true, reason: 'no-patient-uid' });
  });

  it('토큰 비어있음 → skipped:no-tokens', async () => {
    getTokensMock.mockResolvedValueOnce([]);
    const r = await dispatchCallNotification(
      params,
      { status: 'waiting' },
      { status: 'called', patientUid: 'u', department: '내과', number: 1 },
      deps,
    );
    expect(r).toEqual({ skipped: true, reason: 'no-tokens' });
    expect(sendMock).not.toHaveBeenCalled();
  });

  it('정상 발송 — FCM send 호출 + 응답 전파', async () => {
    getTokensMock.mockResolvedValueOnce(['tok-A', 'tok-B']);
    sendMock.mockResolvedValueOnce({ successCount: 2, failureCount: 0 });

    const r = await dispatchCallNotification(
      params,
      { status: 'waiting' },
      {
        status: 'called',
        patientUid: 'u',
        department: '내과',
        number: 7,
      },
      deps,
    );

    expect(r).toEqual({ skipped: false, successCount: 2, failureCount: 0 });
    expect(getTokensMock).toHaveBeenCalledWith('u');
    expect(sendMock).toHaveBeenCalledOnce();
    const msg = sendMock.mock.calls[0][0];
    expect(msg.tokens).toEqual(['tok-A', 'tok-B']);
    expect(msg.notification.title).toBe('진료 호출 알림');
    expect(msg.notification.body).toContain('내과');
    expect(msg.notification.body).toContain('7번');
    expect(msg.data).toEqual({
      type: 'queue-call',
      hospitalId: 'demo',
      entryId: 'entry-1',
      department: '내과',
      number: '7',
    });
  });

  it('부분 실패 응답도 그대로 전파', async () => {
    getTokensMock.mockResolvedValueOnce(['tok-X']);
    sendMock.mockResolvedValueOnce({ successCount: 0, failureCount: 1 });
    const r = await dispatchCallNotification(
      params,
      { status: 'waiting' },
      { status: 'called', patientUid: 'u', department: '외과', number: 3 },
      deps,
    );
    expect(r).toEqual({ skipped: false, successCount: 0, failureCount: 1 });
  });
});
