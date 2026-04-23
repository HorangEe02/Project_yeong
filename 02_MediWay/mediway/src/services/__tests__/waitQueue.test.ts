import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('@/config/firebase', () => ({
  db: {} as object,
  isFirebaseConfigured: () => true,
}));

const getMock = vi.fn();
const updateMock = vi.fn();
const pushMock = vi.fn();
const onValueMock = vi.fn();
const runTransactionMock = vi.fn();

vi.mock('firebase/database', () => ({
  ref: (_db: unknown, path?: string) => ({ path: path ?? '' }),
  get: (r: { path: string }) => getMock(r.path),
  update: (r: { path: string }, fan: unknown) => updateMock(r.path, fan),
  push: (r: { path: string }) => {
    pushMock(r.path);
    return { key: `entry-${pushMock.mock.calls.length}` };
  },
  onValue: (
    r: { path: string },
    cb: (s: unknown) => void,
    err?: (e: Error) => void,
  ) => onValueMock(r.path, cb, err),
  runTransaction: (r: { path: string }, updater: (cur: unknown) => unknown) =>
    runTransactionMock(r.path, updater),
}));

import {
  callNext,
  cancelMyEntry,
  completeEntry,
  enqueue,
  getEntry,
  getTodayDateKst,
  isCancellableByPatient,
  startConsultation,
  subscribeDeptQueue,
  subscribeMyEntries,
} from '../waitQueue';

beforeEach(() => {
  getMock.mockReset();
  updateMock.mockReset();
  pushMock.mockReset();
  onValueMock.mockReset();
  runTransactionMock.mockReset();
});

describe('getTodayDateKst', () => {
  it('UTC 2026-04-22 15:00 → KST 2026-04-23', () => {
    expect(getTodayDateKst(new Date('2026-04-22T15:00:00Z'))).toBe('2026-04-23');
  });

  it('UTC 2026-04-23 14:00 → KST 2026-04-23 (아직 자정 전)', () => {
    expect(getTodayDateKst(new Date('2026-04-23T14:00:00Z'))).toBe('2026-04-23');
  });
});

describe('enqueue', () => {
  it('counter transaction +1 후 main + 역인덱스 fan-out', async () => {
    runTransactionMock.mockResolvedValueOnce({
      committed: true,
      snapshot: { val: () => 3 },
    });
    updateMock.mockResolvedValueOnce(undefined);

    const result = await enqueue('demo', 'uid-a', {
      department: '내과',
      date: '2026-04-23',
    });

    expect(result.number).toBe(3);
    expect(result.status).toBe('waiting');
    expect(result.id).toBe('entry-1');
    expect(runTransactionMock).toHaveBeenCalledTimes(1);
    const [, fan] = updateMock.mock.calls[0] as [unknown, Record<string, unknown>];
    expect(fan).toHaveProperty(
      `hospitals/demo/wait_queue/내과/2026-04-23/${result.id}`,
    );
    expect(fan).toHaveProperty(
      `hospitals/demo/wait_queue_by_patient/uid-a/${result.id}`,
    );
  });

  it('counter 초기값 없을 때 1부터', async () => {
    let seenCurrent: unknown;
    runTransactionMock.mockImplementationOnce(async (_p, updater) => {
      seenCurrent = updater(null);
      return {
        committed: true,
        snapshot: { val: () => seenCurrent as number },
      };
    });
    updateMock.mockResolvedValueOnce(undefined);

    const result = await enqueue('demo', 'uid-a', {
      department: '외과',
      date: '2026-04-23',
    });
    expect(seenCurrent).toBe(1);
    expect(result.number).toBe(1);
  });

  it('transaction 미커밋 시 에러', async () => {
    runTransactionMock.mockResolvedValueOnce({
      committed: false,
      snapshot: { val: () => null },
    });
    await expect(
      enqueue('demo', 'uid-a', { department: '내과', date: '2026-04-23' }),
    ).rejects.toThrow('순번 할당 실패');
  });

  it('appointmentId가 전달되면 entry에 포함', async () => {
    runTransactionMock.mockResolvedValueOnce({
      committed: true,
      snapshot: { val: () => 1 },
    });
    updateMock.mockResolvedValueOnce(undefined);
    const r = await enqueue('demo', 'uid-a', {
      department: '내과',
      date: '2026-04-23',
      appointmentId: 'appt-xyz',
    });
    expect(r.appointmentId).toBe('appt-xyz');
  });

  it('빈 부서명은 거부', async () => {
    await expect(
      enqueue('demo', 'uid-a', { department: '   ', date: '2026-04-23' }),
    ).rejects.toThrow('부서명 필수');
  });

  it('역인덱스 entry는 department/date/number/status만', async () => {
    runTransactionMock.mockResolvedValueOnce({
      committed: true,
      snapshot: { val: () => 5 },
    });
    updateMock.mockResolvedValueOnce(undefined);
    await enqueue('demo', 'uid-a', {
      department: '내과',
      date: '2026-04-23',
      appointmentId: 'should-not-leak',
    });
    const [, fan] = updateMock.mock.calls[0] as [unknown, Record<string, unknown>];
    const indexKey = Object.keys(fan).find((k) =>
      k.includes('wait_queue_by_patient'),
    )!;
    const entry = fan[indexKey] as Record<string, unknown>;
    expect(Object.keys(entry).sort()).toEqual(
      ['date', 'department', 'number', 'status'].sort(),
    );
  });
});

describe('cancelMyEntry', () => {
  it('main.status + main.completedAt + index.status 3개 동기 set', async () => {
    updateMock.mockResolvedValueOnce(undefined);
    await cancelMyEntry('demo', 'uid-a', {
      id: 'entry-1',
      department: '내과',
      date: '2026-04-23',
    });
    const [, fan] = updateMock.mock.calls[0] as [unknown, Record<string, unknown>];
    expect(fan['hospitals/demo/wait_queue/내과/2026-04-23/entry-1/status']).toBe(
      'cancelled',
    );
    expect(
      fan['hospitals/demo/wait_queue_by_patient/uid-a/entry-1/status'],
    ).toBe('cancelled');
    expect(
      fan['hospitals/demo/wait_queue/내과/2026-04-23/entry-1/completedAt'],
    ).toBeTypeOf('number');
  });
});

describe('callNext', () => {
  it('대기 없음 → null', async () => {
    getMock.mockResolvedValueOnce({ exists: () => false });
    const r = await callNext('demo', '내과', '2026-04-23');
    expect(r).toBeNull();
    expect(updateMock).not.toHaveBeenCalled();
  });

  it('waiting 중 최소 number를 called로 전환', async () => {
    getMock.mockResolvedValueOnce({
      exists: () => true,
      val: () => ({
        'e-2': {
          id: 'e-2',
          number: 2,
          status: 'waiting',
          department: '내과',
          date: '2026-04-23',
          patientUid: 'uid-b',
        },
        'e-1': {
          id: 'e-1',
          number: 1,
          status: 'called',
          department: '내과',
          date: '2026-04-23',
          patientUid: 'uid-a',
        },
        'e-3': {
          id: 'e-3',
          number: 3,
          status: 'waiting',
          department: '내과',
          date: '2026-04-23',
          patientUid: 'uid-c',
        },
      }),
    });
    updateMock.mockResolvedValueOnce(undefined);
    const r = await callNext('demo', '내과', '2026-04-23');
    expect(r?.id).toBe('e-2');
    expect(r?.status).toBe('called');
    const [, fan] = updateMock.mock.calls[0] as [unknown, Record<string, unknown>];
    expect(fan['hospitals/demo/wait_queue/내과/2026-04-23/e-2/status']).toBe(
      'called',
    );
    expect(
      fan['hospitals/demo/wait_queue_by_patient/uid-b/e-2/status'],
    ).toBe('called');
  });

  it('모두 완료/취소면 null', async () => {
    getMock.mockResolvedValueOnce({
      exists: () => true,
      val: () => ({
        'e-1': { id: 'e-1', number: 1, status: 'completed', patientUid: 'x' },
        'e-2': { id: 'e-2', number: 2, status: 'cancelled', patientUid: 'y' },
      }),
    });
    const r = await callNext('demo', '내과', '2026-04-23');
    expect(r).toBeNull();
  });
});

describe('startConsultation', () => {
  it('status=in-progress + startedAt 기록 + index 동기화', async () => {
    updateMock.mockResolvedValueOnce(undefined);
    await startConsultation('demo', {
      id: 'entry-9',
      department: '내과',
      date: '2026-04-23',
      patientUid: 'uid-a',
    });
    const [, fan] = updateMock.mock.calls[0] as [unknown, Record<string, unknown>];
    expect(fan['hospitals/demo/wait_queue/내과/2026-04-23/entry-9/status']).toBe(
      'in-progress',
    );
    expect(
      fan['hospitals/demo/wait_queue/내과/2026-04-23/entry-9/startedAt'],
    ).toBeTypeOf('number');
    expect(
      fan['hospitals/demo/wait_queue_by_patient/uid-a/entry-9/status'],
    ).toBe('in-progress');
  });
});

describe('completeEntry', () => {
  it('status=completed + completedAt + index 동기화', async () => {
    updateMock.mockResolvedValueOnce(undefined);
    await completeEntry('demo', {
      id: 'entry-9',
      department: '내과',
      date: '2026-04-23',
      patientUid: 'uid-a',
    });
    const [, fan] = updateMock.mock.calls[0] as [unknown, Record<string, unknown>];
    expect(fan['hospitals/demo/wait_queue/내과/2026-04-23/entry-9/status']).toBe(
      'completed',
    );
  });
});

describe('getEntry', () => {
  it('없음 → null', async () => {
    getMock.mockResolvedValueOnce({ exists: () => false });
    expect(await getEntry('demo', '내과', '2026-04-23', 'x')).toBeNull();
  });

  it('존재 → WaitEntry', async () => {
    getMock.mockResolvedValueOnce({
      exists: () => true,
      val: () => ({ id: 'e-1', number: 1, status: 'waiting' }),
    });
    const r = await getEntry('demo', '내과', '2026-04-23', 'e-1');
    expect(r?.number).toBe(1);
  });
});

describe('subscribeMyEntries', () => {
  it('역인덱스 snapshot → number 오름차순', () => {
    let cb: ((s: unknown) => void) | null = null;
    onValueMock.mockImplementationOnce((_p, c) => {
      cb = c;
      return () => {};
    });
    let got: Array<{ id: string; number: number }> = [];
    subscribeMyEntries('demo', 'uid-a', (list) => {
      got = list;
    });
    cb!({
      exists: () => true,
      val: () => ({
        x: { department: '내과', date: '2026-04-23', number: 7, status: 'waiting' },
        y: { department: '내과', date: '2026-04-23', number: 2, status: 'called' },
        z: { department: '내과', date: '2026-04-23', number: 4, status: 'waiting' },
      }),
    });
    expect(got.map((e) => e.number)).toEqual([2, 4, 7]);
  });

  it('빈 snapshot → []', () => {
    let cb: ((s: unknown) => void) | null = null;
    onValueMock.mockImplementationOnce((_p, c) => {
      cb = c;
      return () => {};
    });
    let got: unknown[] = [];
    subscribeMyEntries('demo', 'uid-a', (list) => {
      got = list;
    });
    cb!({ exists: () => false });
    expect(got).toEqual([]);
  });
});

describe('subscribeDeptQueue', () => {
  it('기본 — 완료/취소 제외, number 오름차순', () => {
    let cb: ((s: unknown) => void) | null = null;
    onValueMock.mockImplementationOnce((_p, c) => {
      cb = c;
      return () => {};
    });
    let got: Array<{ number: number; status: string }> = [];
    subscribeDeptQueue('demo', '내과', '2026-04-23', (list) => {
      got = list;
    });
    cb!({
      exists: () => true,
      val: () => ({
        a: { id: 'a', number: 3, status: 'waiting' },
        b: { id: 'b', number: 1, status: 'called' },
        c: { id: 'c', number: 2, status: 'completed' },
        d: { id: 'd', number: 4, status: 'cancelled' },
      }),
    });
    expect(got.map((e) => e.number)).toEqual([1, 3]);
  });

  it('includeCompleted=true — 전부 반환', () => {
    let cb: ((s: unknown) => void) | null = null;
    onValueMock.mockImplementationOnce((_p, c) => {
      cb = c;
      return () => {};
    });
    let got: Array<{ number: number }> = [];
    subscribeDeptQueue(
      'demo',
      '내과',
      '2026-04-23',
      (list) => {
        got = list;
      },
      undefined,
      { includeCompleted: true },
    );
    cb!({
      exists: () => true,
      val: () => ({
        a: { id: 'a', number: 2, status: 'completed' },
        b: { id: 'b', number: 1, status: 'waiting' },
      }),
    });
    expect(got.map((e) => e.number)).toEqual([1, 2]);
  });
});

describe('isCancellableByPatient', () => {
  it('waiting만 true', () => {
    expect(isCancellableByPatient('waiting')).toBe(true);
    expect(isCancellableByPatient('called')).toBe(false);
    expect(isCancellableByPatient('in-progress')).toBe(false);
    expect(isCancellableByPatient('completed')).toBe(false);
    expect(isCancellableByPatient('cancelled')).toBe(false);
  });
});
