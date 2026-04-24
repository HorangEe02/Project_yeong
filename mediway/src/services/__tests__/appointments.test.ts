import { describe, it, expect, beforeEach, vi } from 'vitest';

const mockOnValue = vi.fn();
const mockPush = vi.fn();
const mockUpdate = vi.fn();
const mockRef = vi.fn((_db: unknown, path?: string) =>
  path === undefined ? { __root: true } : { __path: path },
);

vi.mock('firebase/database', () => ({
  onValue: (...args: unknown[]) => mockOnValue(...args),
  push: (...args: unknown[]) => mockPush(...args),
  ref: (...args: unknown[]) =>
    args.length <= 1 ? mockRef(args[0]) : mockRef(args[0], args[1] as string),
  update: (...args: unknown[]) => mockUpdate(...args),
}));

vi.mock('@/config/firebase', () => ({
  db: { __mocked: true },
  isFirebaseConfigured: () => true,
}));

import {
  cancelAppointment,
  createAppointment,
  subscribeMyAppointments,
} from '../appointments';

describe('subscribeMyAppointments', () => {
  beforeEach(() => {
    mockOnValue.mockReset();
    mockRef.mockClear();
  });

  function trigger(val: unknown) {
    const cb = mockOnValue.mock.calls[0][1] as (snap: { val: () => unknown }) => void;
    cb({ val: () => val });
  }

  it('경로: hospitals/{hid}/appointments_by_patient/{uid}', () => {
    subscribeMyAppointments('demo', 'uid-1', vi.fn());
    expect(mockRef).toHaveBeenCalledWith(
      expect.anything(),
      'hospitals/demo/appointments_by_patient/uid-1',
    );
  });

  it('null snapshot → []', () => {
    const onData = vi.fn();
    subscribeMyAppointments('demo', 'uid-1', onData);
    trigger(null);
    expect(onData).toHaveBeenCalledWith([]);
  });

  it('id 주입 + scheduledAt 오름차순 정렬', () => {
    const onData = vi.fn();
    subscribeMyAppointments('demo', 'uid-1', onData);
    trigger({
      b: { scheduledAt: 2000, status: 'scheduled', department: '내과' },
      a: { scheduledAt: 1000, status: 'scheduled', department: '외과' },
      c: { scheduledAt: 3000, status: 'cancelled', department: '내과' },
    });
    const list = onData.mock.calls[0][0] as Array<{ id: string; scheduledAt: number }>;
    expect(list.map((e) => e.id)).toEqual(['a', 'b', 'c']);
    expect(list[0].scheduledAt).toBe(1000);
  });

  it('에러 콜백 전파', () => {
    const onError = vi.fn();
    subscribeMyAppointments('demo', 'uid-1', vi.fn(), onError);
    const errCb = mockOnValue.mock.calls[0][2] as (err: Error) => void;
    const e = new Error('denied');
    errCb(e);
    expect(onError).toHaveBeenCalledWith(e);
  });
});

describe('createAppointment', () => {
  beforeEach(() => {
    mockPush.mockReset();
    mockUpdate.mockReset();
    mockRef.mockClear();
    mockUpdate.mockResolvedValue(undefined);
    mockPush.mockReturnValue({ key: 'new-appt-id' });
  });

  it('dual-write: full record + patient index subset', async () => {
    const result = await createAppointment('demo', 'uid-1', {
      department: '내과',
      scheduledAt: 1_900_000_000_000,
      durationMin: 30,
    });
    expect(result.id).toBe('new-appt-id');
    expect(result.status).toBe('scheduled');

    const payload = mockUpdate.mock.calls[0][1];
    const fullPath = 'hospitals/demo/appointments/new-appt-id';
    const indexPath = 'hospitals/demo/appointments_by_patient/uid-1/new-appt-id';
    expect(payload[fullPath].department).toBe('내과');
    expect(payload[fullPath].patientUid).toBe('uid-1');
    expect(payload[fullPath].status).toBe('scheduled');
    expect(payload[fullPath].durationMin).toBe(30);

    expect(payload[indexPath]).toEqual({
      scheduledAt: 1_900_000_000_000,
      status: 'scheduled',
      department: '내과',
    });
  });

  it('optional fields (staffUid, notes) 포함 시 record 에 반영', async () => {
    await createAppointment('demo', 'uid-1', {
      department: '외과',
      scheduledAt: 1_900_000_000_000,
      durationMin: 20,
      staffUid: 'staff-1',
      notes: '메모 테스트',
    });
    const payload = mockUpdate.mock.calls[0][1];
    const full = payload['hospitals/demo/appointments/new-appt-id'];
    expect(full.staffUid).toBe('staff-1');
    expect(full.notes).toBe('메모 테스트');
  });

  it('optional 생략 시 undefined 필드 포함 X', async () => {
    await createAppointment('demo', 'uid-1', {
      department: '외과',
      scheduledAt: 1_900_000_000_000,
      durationMin: 20,
    });
    const payload = mockUpdate.mock.calls[0][1];
    const full = payload['hospitals/demo/appointments/new-appt-id'];
    expect('staffUid' in full).toBe(false);
    expect('notes' in full).toBe(false);
  });

  it('department 공백이면 throw', async () => {
    await expect(
      createAppointment('demo', 'uid-1', {
        department: '  ',
        scheduledAt: 1_900_000_000_000,
        durationMin: 30,
      }),
    ).rejects.toThrow('부서명');
  });

  it('durationMin <= 0 이면 throw', async () => {
    await expect(
      createAppointment('demo', 'uid-1', {
        department: '내과',
        scheduledAt: 1_900_000_000_000,
        durationMin: 0,
      }),
    ).rejects.toThrow('진료 시간');
  });
});

describe('cancelAppointment', () => {
  beforeEach(() => {
    mockUpdate.mockReset();
    mockRef.mockClear();
    mockUpdate.mockResolvedValue(undefined);
  });

  it('dual-path status=cancelled + updatedAt', async () => {
    await cancelAppointment('demo', 'uid-1', 'appt-x');
    const payload = mockUpdate.mock.calls[0][1];
    expect(payload['hospitals/demo/appointments/appt-x/status']).toBe('cancelled');
    expect(typeof payload['hospitals/demo/appointments/appt-x/updatedAt']).toBe('number');
    expect(
      payload['hospitals/demo/appointments_by_patient/uid-1/appt-x/status'],
    ).toBe('cancelled');
  });
});
