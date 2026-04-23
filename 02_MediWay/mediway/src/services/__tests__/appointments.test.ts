import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('@/config/firebase', () => ({
  db: {} as object,
  isFirebaseConfigured: () => true,
}));

const getMock = vi.fn();
const updateMock = vi.fn();
const pushMock = vi.fn();
const onValueMock = vi.fn();

vi.mock('firebase/database', () => ({
  ref: (_db: unknown, path?: string) => ({ path: path ?? '' }),
  get: (r: { path: string }) => getMock(r.path),
  update: (r: { path: string }, fan: unknown) => updateMock(r.path, fan),
  push: (r: { path: string }) => {
    pushMock(r.path);
    return { key: `mock-${pushMock.mock.calls.length}` };
  },
  onValue: (
    r: { path: string },
    cb: (s: unknown) => void,
    err?: (e: Error) => void,
  ) => onValueMock(r.path, cb, err),
}));

import {
  cancelAppointment,
  createAppointment,
  getAppointment,
  isCancellable,
  subscribeMyAppointmentIndex,
} from '../appointments';

beforeEach(() => {
  getMock.mockReset();
  updateMock.mockReset();
  pushMock.mockReset();
  onValueMock.mockReset();
});

describe('createAppointment', () => {
  it('main + 역인덱스 fan-out', async () => {
    updateMock.mockResolvedValueOnce(undefined);
    const future = Date.now() + 86_400_000;
    const result = await createAppointment('demo', 'uid-a', {
      department: '내과',
      scheduledAt: future,
      durationMin: 30,
    });
    expect(result.id).toBe('mock-1');
    expect(result.status).toBe('scheduled');
    const [, fan] = updateMock.mock.calls[0] as [unknown, Record<string, unknown>];
    expect(fan).toHaveProperty(`hospitals/demo/appointments/${result.id}`);
    expect(fan).toHaveProperty(
      `hospitals/demo/appointments_by_patient/uid-a/${result.id}`,
    );
  });

  it('역인덱스 entry에 scheduledAt + status + department만 포함', async () => {
    updateMock.mockResolvedValueOnce(undefined);
    await createAppointment('demo', 'uid-a', {
      department: '내과',
      scheduledAt: Date.now() + 86_400_000,
      durationMin: 30,
      notes: 'should not leak to index',
    });
    const [, fan] = updateMock.mock.calls[0] as [unknown, Record<string, unknown>];
    const indexKey = Object.keys(fan).find((k) =>
      k.includes('appointments_by_patient'),
    )!;
    const entry = fan[indexKey] as Record<string, unknown>;
    expect(Object.keys(entry).sort()).toEqual(
      ['department', 'scheduledAt', 'status'].sort(),
    );
  });
});

describe('cancelAppointment', () => {
  it('main.status + index.status 모두 cancelled로 set', async () => {
    updateMock.mockResolvedValueOnce(undefined);
    await cancelAppointment('demo', 'uid-a', 'appt-1');
    const [, fan] = updateMock.mock.calls[0] as [unknown, Record<string, unknown>];
    expect(fan['hospitals/demo/appointments/appt-1/status']).toBe('cancelled');
    expect(
      fan['hospitals/demo/appointments_by_patient/uid-a/appt-1/status'],
    ).toBe('cancelled');
  });
});

describe('getAppointment', () => {
  it('존재 없을 때 null', async () => {
    getMock.mockResolvedValueOnce({ exists: () => false });
    expect(await getAppointment('demo', 'ghost')).toBeNull();
  });

  it('존재 시 값 반환', async () => {
    getMock.mockResolvedValueOnce({
      exists: () => true,
      val: () => ({ id: 'appt-1', department: '내과' }),
    });
    const r = await getAppointment('demo', 'appt-1');
    expect(r?.department).toBe('내과');
  });
});

describe('subscribeMyAppointmentIndex', () => {
  it('index snapshot → scheduledAt 오름차순 정렬', () => {
    let cb: ((s: unknown) => void) | null = null;
    onValueMock.mockImplementationOnce((_p, c) => {
      cb = c;
      return () => {};
    });
    let received: Array<{ id: string; scheduledAt: number }> = [];
    subscribeMyAppointmentIndex(
      'demo',
      'uid-a',
      (list) => {
        received = list;
      },
    );
    cb!({
      exists: () => true,
      val: () => ({
        b: { scheduledAt: 200, status: 'scheduled', department: 'X' },
        a: { scheduledAt: 100, status: 'scheduled', department: 'X' },
        c: { scheduledAt: 300, status: 'scheduled', department: 'X' },
      }),
    });
    expect(received.map((e) => e.id)).toEqual(['a', 'b', 'c']);
  });

  it('empty snapshot → []', () => {
    let cb: ((s: unknown) => void) | null = null;
    onValueMock.mockImplementationOnce((_p, c) => {
      cb = c;
      return () => {};
    });
    let received: unknown[] = [];
    subscribeMyAppointmentIndex(
      'demo',
      'uid-a',
      (list) => {
        received = list;
      },
    );
    cb!({ exists: () => false });
    expect(received).toEqual([]);
  });
});

describe('isCancellable', () => {
  it('scheduled만 true', () => {
    expect(isCancellable('scheduled')).toBe(true);
    expect(isCancellable('cancelled')).toBe(false);
    expect(isCancellable('completed')).toBe(false);
  });
});
