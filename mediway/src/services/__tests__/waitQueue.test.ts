import { describe, it, expect, beforeEach, vi } from 'vitest';

const mockOnValue = vi.fn();
const mockRef = vi.fn((_db: unknown, path: string) => ({ __path: path }));

vi.mock('firebase/database', () => ({
  onValue: (...args: unknown[]) => mockOnValue(...args),
  ref: (...args: unknown[]) => mockRef(args[0], args[1] as string),
}));

vi.mock('@/config/firebase', () => ({
  db: { __mocked: true },
  isFirebaseConfigured: () => true,
}));

import { subscribeMyWaitQueue, todayDateKST } from '../waitQueue';

describe('todayDateKST', () => {
  it('UTC 자정은 KST 오전 9시 → 같은 날짜', () => {
    // 2026-04-24T00:00:00Z == 2026-04-24T09:00:00+09:00
    const now = new Date('2026-04-24T00:00:00Z');
    expect(todayDateKST(now)).toBe('2026-04-24');
  });

  it('UTC 늦은 저녁은 KST 익일 새벽 → 다음 날짜', () => {
    // 2026-04-23T20:00:00Z == 2026-04-24T05:00:00+09:00
    const now = new Date('2026-04-23T20:00:00Z');
    expect(todayDateKST(now)).toBe('2026-04-24');
  });

  it('KST 자정 직전은 아직 그 날짜', () => {
    // 2026-04-24T14:59:00Z == 2026-04-24T23:59:00+09:00
    const now = new Date('2026-04-24T14:59:00Z');
    expect(todayDateKST(now)).toBe('2026-04-24');
  });

  it('KST 자정 직후는 다음 날짜', () => {
    // 2026-04-24T15:00:00Z == 2026-04-25T00:00:00+09:00
    const now = new Date('2026-04-24T15:00:00Z');
    expect(todayDateKST(now)).toBe('2026-04-25');
  });

  it('기본 인자(now)는 현재 시각', () => {
    const result = todayDateKST();
    expect(result).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });
});

describe('subscribeMyWaitQueue', () => {
  beforeEach(() => {
    mockOnValue.mockReset();
    mockRef.mockClear();
  });

  function triggerSnapshot(val: unknown) {
    // mockOnValue.mock.calls[0] = [refObj, onValueCb, onErrorCb]
    const onValueCb = mockOnValue.mock.calls[0][1] as (snap: {
      val: () => unknown;
    }) => void;
    onValueCb({ val: () => val });
  }

  it('올바른 path 로 구독 — hospitals/{hid}/wait_queue_by_patient/{uid}', () => {
    const onData = vi.fn();
    subscribeMyWaitQueue('demo', 'uid-1', onData);
    expect(mockRef).toHaveBeenCalledWith(
      expect.anything(),
      'hospitals/demo/wait_queue_by_patient/uid-1',
    );
  });

  it('데이터 없으면 빈 배열 전달', () => {
    const onData = vi.fn();
    subscribeMyWaitQueue('demo', 'uid-1', onData);
    triggerSnapshot(null);
    expect(onData).toHaveBeenCalledWith([]);
  });

  it('엔트리 → { id, ...value } 매핑 + number 오름차순 정렬', () => {
    const onData = vi.fn();
    subscribeMyWaitQueue('demo', 'uid-1', onData);
    triggerSnapshot({
      'entry-b': { department: '내과', date: '2026-04-24', number: 5, status: 'waiting' },
      'entry-a': { department: '내과', date: '2026-04-24', number: 2, status: 'waiting' },
      'entry-c': { department: '정형외과', date: '2026-04-24', number: 1, status: 'called' },
    });
    expect(onData).toHaveBeenCalledWith([
      { id: 'entry-c', department: '정형외과', date: '2026-04-24', number: 1, status: 'called' },
      { id: 'entry-a', department: '내과', date: '2026-04-24', number: 2, status: 'waiting' },
      { id: 'entry-b', department: '내과', date: '2026-04-24', number: 5, status: 'waiting' },
    ]);
  });

  it('onError 는 subscription 에러 시 호출됨', () => {
    const onData = vi.fn();
    const onError = vi.fn();
    subscribeMyWaitQueue('demo', 'uid-1', onData, onError);
    const onErrorCb = mockOnValue.mock.calls[0][2] as (err: Error) => void;
    const err = new Error('permission_denied');
    onErrorCb(err);
    expect(onError).toHaveBeenCalledWith(err);
  });

  it('unsubscribe 함수 반환 — 호출 시 구독 정리', () => {
    const mockUnsub = vi.fn();
    mockOnValue.mockReturnValue(mockUnsub);
    const unsubscribe = subscribeMyWaitQueue('demo', 'uid-1', vi.fn());
    unsubscribe();
    expect(mockUnsub).toHaveBeenCalled();
  });
});
