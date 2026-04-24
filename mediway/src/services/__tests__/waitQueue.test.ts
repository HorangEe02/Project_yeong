import { describe, it, expect, beforeEach, vi } from 'vitest';

const mockOnValue = vi.fn();
const mockRef = vi.fn((_db: unknown, path?: string) =>
  path === undefined ? { __root: true } : { __path: path },
);
const mockGet = vi.fn();
const mockUpdate = vi.fn();

vi.mock('firebase/database', () => ({
  onValue: (...args: unknown[]) => mockOnValue(...args),
  ref: (...args: unknown[]) =>
    args.length <= 1 ? mockRef(args[0]) : mockRef(args[0], args[1] as string),
  get: (...args: unknown[]) => mockGet(...args),
  update: (...args: unknown[]) => mockUpdate(...args),
}));

vi.mock('@/config/firebase', () => ({
  db: { __mocked: true },
  isFirebaseConfigured: () => true,
}));

import {
  callNextWaiting,
  markCompleted,
  markInProgress,
  selectPrimaryActive,
  subscribeDeptQueue,
  subscribeMyWaitQueue,
  todayDateKST,
} from '../waitQueue';
import type { WaitQueueEntry, WaitQueuePatientIndex } from '@/types/waitQueue';

function entry(
  id: string,
  overrides: Partial<WaitQueuePatientIndex> = {},
): WaitQueuePatientIndex {
  return {
    id,
    department: '내과',
    date: '2026-04-24',
    number: 1,
    status: 'waiting',
    ...overrides,
  };
}

function fullEntry(
  id: string,
  overrides: Partial<WaitQueueEntry> = {},
): WaitQueueEntry {
  return {
    id,
    hospitalId: 'demo',
    department: '내과',
    date: '2026-04-24',
    number: 1,
    patientUid: `uid-${id}`,
    status: 'waiting',
    createdAt: 1_700_000_000_000,
    ...overrides,
  };
}

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

describe('selectPrimaryActive', () => {
  const TODAY = '2026-04-24';

  it('오늘이 아닌 엔트리는 제외', () => {
    const result = selectPrimaryActive(
      [entry('a', { date: '2026-04-23', status: 'waiting' })],
      TODAY,
    );
    expect(result).toBeNull();
  });

  it('completed/cancelled 는 제외', () => {
    const result = selectPrimaryActive(
      [
        entry('a', { status: 'completed' }),
        entry('b', { status: 'cancelled' }),
      ],
      TODAY,
    );
    expect(result).toBeNull();
  });

  it('called > in-progress > waiting urgency 순위로 우선', () => {
    const result = selectPrimaryActive(
      [
        entry('wait', { status: 'waiting', number: 1 }),
        entry('prog', { status: 'in-progress', number: 2 }),
        entry('call', { status: 'called', number: 3 }),
      ],
      TODAY,
    );
    expect(result?.id).toBe('call');
  });

  it('같은 urgency 내에서는 number 오름차순', () => {
    const result = selectPrimaryActive(
      [
        entry('c', { status: 'waiting', number: 5 }),
        entry('a', { status: 'waiting', number: 2 }),
        entry('b', { status: 'waiting', number: 3 }),
      ],
      TODAY,
    );
    expect(result?.id).toBe('a');
  });

  it('빈 리스트면 null', () => {
    expect(selectPrimaryActive([], TODAY)).toBeNull();
  });

  it('원본 배열은 변경하지 않음 (non-mutating)', () => {
    const input = [
      entry('b', { status: 'waiting', number: 2 }),
      entry('a', { status: 'called', number: 1 }),
    ];
    const snapshot = JSON.stringify(input);
    selectPrimaryActive(input, TODAY);
    // 실제로는 내부에서 sort() 호출 시 mutation 가능 → filter 체인으로 새 배열 생성됨을 확인
    expect(JSON.stringify(input)).toBe(snapshot);
  });
});

describe('subscribeDeptQueue', () => {
  beforeEach(() => {
    mockOnValue.mockReset();
    mockRef.mockClear();
  });

  function trigger(val: unknown) {
    const cb = mockOnValue.mock.calls[0][1] as (snap: { exists: () => boolean; val: () => unknown }) => void;
    cb({ exists: () => val != null, val: () => val });
  }

  it('경로 hospitals/{hid}/wait_queue/{dept}/{date}', () => {
    subscribeDeptQueue('demo', '내과', '2026-04-24', vi.fn());
    expect(mockRef).toHaveBeenCalledWith(
      expect.anything(),
      'hospitals/demo/wait_queue/내과/2026-04-24',
    );
  });

  it('null snapshot → 빈 배열', () => {
    const onData = vi.fn();
    subscribeDeptQueue('demo', '내과', '2026-04-24', onData);
    trigger(null);
    expect(onData).toHaveBeenCalledWith([]);
  });

  it('기본 필터 — completed/cancelled 제외, number 정렬', () => {
    const onData = vi.fn();
    subscribeDeptQueue('demo', '내과', '2026-04-24', onData);
    trigger({
      a: fullEntry('a', { number: 3, status: 'waiting' }),
      b: fullEntry('b', { number: 1, status: 'called' }),
      c: fullEntry('c', { number: 2, status: 'completed' }),
      d: fullEntry('d', { number: 4, status: 'cancelled' }),
    });
    const passed = onData.mock.calls[0][0] as WaitQueueEntry[];
    expect(passed.map((e) => e.id)).toEqual(['b', 'a']);
  });

  it('includeCompleted=true 면 completed 포함', () => {
    const onData = vi.fn();
    subscribeDeptQueue('demo', '내과', '2026-04-24', onData, undefined, {
      includeCompleted: true,
    });
    trigger({
      a: fullEntry('a', { number: 1, status: 'waiting' }),
      b: fullEntry('b', { number: 2, status: 'completed' }),
    });
    const passed = onData.mock.calls[0][0] as WaitQueueEntry[];
    expect(passed.map((e) => e.id)).toEqual(['a', 'b']);
  });
});

describe('callNextWaiting', () => {
  beforeEach(() => {
    mockGet.mockReset();
    mockUpdate.mockReset();
    mockRef.mockClear();
  });

  it('waiting 없으면 null', async () => {
    mockGet.mockResolvedValue({ exists: () => false, val: () => null });
    const r = await callNextWaiting('demo', '내과', '2026-04-24');
    expect(r).toBeNull();
    expect(mockUpdate).not.toHaveBeenCalled();
  });

  it('가장 낮은 number 의 waiting 을 called 로 전이 + dual-write', async () => {
    mockGet.mockResolvedValue({
      exists: () => true,
      val: () => ({
        a: fullEntry('a', { number: 3, status: 'waiting', patientUid: 'p-a' }),
        b: fullEntry('b', { number: 1, status: 'waiting', patientUid: 'p-b' }),
        c: fullEntry('c', { number: 2, status: 'called', patientUid: 'p-c' }),
      }),
    });
    mockUpdate.mockResolvedValue(undefined);

    const r = await callNextWaiting('demo', '내과', '2026-04-24');
    expect(r?.id).toBe('b');
    expect(r?.status).toBe('called');
    expect(typeof r?.calledAt).toBe('number');

    const payload = mockUpdate.mock.calls[0][1];
    expect(payload['hospitals/demo/wait_queue/내과/2026-04-24/b/status']).toBe('called');
    expect(typeof payload['hospitals/demo/wait_queue/내과/2026-04-24/b/calledAt']).toBe('number');
    expect(payload['hospitals/demo/wait_queue_by_patient/p-b/b/status']).toBe('called');
  });

  it('waiting 이 하나도 없으면 null (모두 called/in-progress)', async () => {
    mockGet.mockResolvedValue({
      exists: () => true,
      val: () => ({
        a: fullEntry('a', { number: 1, status: 'called' }),
        b: fullEntry('b', { number: 2, status: 'in-progress' }),
      }),
    });
    const r = await callNextWaiting('demo', '내과', '2026-04-24');
    expect(r).toBeNull();
    expect(mockUpdate).not.toHaveBeenCalled();
  });
});

describe('markInProgress / markCompleted', () => {
  beforeEach(() => {
    mockUpdate.mockReset();
    mockRef.mockClear();
    mockUpdate.mockResolvedValue(undefined);
  });

  it('markInProgress — dual write status=in-progress + startedAt', async () => {
    await markInProgress('demo', fullEntry('e1', { patientUid: 'p-1' }));
    const payload = mockUpdate.mock.calls[0][1];
    expect(payload['hospitals/demo/wait_queue/내과/2026-04-24/e1/status']).toBe('in-progress');
    expect(typeof payload['hospitals/demo/wait_queue/내과/2026-04-24/e1/startedAt']).toBe('number');
    expect(payload['hospitals/demo/wait_queue_by_patient/p-1/e1/status']).toBe('in-progress');
  });

  it('markCompleted — dual write status=completed + completedAt', async () => {
    await markCompleted('demo', fullEntry('e2', { patientUid: 'p-2' }));
    const payload = mockUpdate.mock.calls[0][1];
    expect(payload['hospitals/demo/wait_queue/내과/2026-04-24/e2/status']).toBe('completed');
    expect(typeof payload['hospitals/demo/wait_queue/내과/2026-04-24/e2/completedAt']).toBe('number');
    expect(payload['hospitals/demo/wait_queue_by_patient/p-2/e2/status']).toBe('completed');
  });
});
