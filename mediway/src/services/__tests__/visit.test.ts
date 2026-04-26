import { describe, it, expect, beforeEach, vi } from 'vitest';
import type { Visit, VisitStatus } from '@/types/visit';

// --- mocks ---

const mockSet = vi.fn();
const mockUpdate = vi.fn();
const mockGet = vi.fn();
const mockRemove = vi.fn();
const mockOnValue = vi.fn();
const mockUnsubscribe = vi.fn();

let nextPushKey = 'pk-001';
const mockPush = vi.fn(() => ({ key: nextPushKey }));

const mockRef = vi.fn((_db: unknown, path?: string) =>
  path === undefined ? { __root: true } : { __path: path },
);

const mockQuery = vi.fn((r: unknown) => ({ __query: r }));
const mockOrderByChild = vi.fn((field: string) => ({ __orderByChild: field }));
const mockEqualTo = vi.fn((v: unknown) => ({ __equalTo: v }));
const mockLimitToLast = vi.fn((n: number) => ({ __limitToLast: n }));

vi.mock('firebase/database', () => ({
  ref: (...args: unknown[]) =>
    args.length <= 1 ? mockRef(args[0]) : mockRef(args[0], args[1] as string),
  push: (...args: unknown[]) => mockPush(...args),
  set: (...args: unknown[]) => mockSet(...args),
  update: (...args: unknown[]) => mockUpdate(...args),
  get: (...args: unknown[]) => mockGet(...args),
  remove: (...args: unknown[]) => mockRemove(...args),
  onValue: (...args: unknown[]) => {
    mockOnValue(...args);
    return mockUnsubscribe;
  },
  query: (...args: unknown[]) => mockQuery(args[0]),
  orderByChild: (...args: unknown[]) => mockOrderByChild(args[0] as string),
  equalTo: (...args: unknown[]) => mockEqualTo(args[0]),
  limitToLast: (...args: unknown[]) => mockLimitToLast(args[0] as number),
}));

vi.mock('@/config/firebase', () => ({
  db: { __mocked: true },
  isFirebaseConfigured: () => true,
  auth: { currentUser: { uid: 'admin-1', email: 'admin@demo.test' } },
}));

const mockAppendAudit = vi.fn();
vi.mock('../auditLog', () => ({
  appendAudit: (...args: unknown[]) => mockAppendAudit(...args),
}));

import {
  createVisit,
  updateVisit,
  updateVisitStatus,
  deleteVisit,
  subscribeActiveVisit,
  subscribeActiveVisitsByDepartment,
  subscribeRecentVisits,
  listVisitsByPatient,
  listVisitsByDepartment,
} from '../visit';

beforeEach(() => {
  mockSet.mockReset();
  mockUpdate.mockReset();
  mockGet.mockReset();
  mockRemove.mockReset();
  mockOnValue.mockReset();
  mockUnsubscribe.mockReset();
  mockPush.mockReset();
  mockRef.mockClear();
  mockAppendAudit.mockReset();

  mockSet.mockResolvedValue(undefined);
  mockUpdate.mockResolvedValue(undefined);
  mockRemove.mockResolvedValue(undefined);
  mockAppendAudit.mockResolvedValue(undefined);
  nextPushKey = 'pk-001';
  mockPush.mockImplementation(() => ({ key: nextPushKey }));
});

function baseInput(overrides: Partial<Visit> = {}) {
  return {
    patientUid: 'uid-1',
    type: 'outpatient' as const,
    status: 'scheduled' as VisitStatus,
    zone: 'Zone A-1',
    department: 'IM',
    createdBy: 'admin-1',
    ...overrides,
  };
}

// =====================================================================
// createVisit
// =====================================================================

describe('createVisit', () => {
  it('push key 반환 + set + audit visit.create 호출', async () => {
    nextPushKey = 'visit-abc';
    const id = await createVisit('demo', baseInput());

    expect(id).toBe('visit-abc');
    expect(mockSet).toHaveBeenCalledTimes(1);
    expect(mockAppendAudit).toHaveBeenCalledWith(
      'visit.create',
      'visit-abc',
      expect.objectContaining({ type: 'outpatient', status: 'scheduled', patientUid: 'uid-1' }),
      'demo',
    );
  });

  it('hospitalId 가 slug 로 자동 주입됨 + createdAt/updatedAt 자동', async () => {
    nextPushKey = 'visit-xyz';
    await createVisit('demo', baseInput());

    const setArg = mockSet.mock.calls[0][1] as Visit;
    expect(setArg.hospitalId).toBe('demo');
    expect(setArg.visitId).toBe('visit-xyz');
    expect(typeof setArg.createdAt).toBe('number');
    expect(setArg.createdAt).toBe(setArg.updatedAt);
  });

  it('push key 없음 → throw', async () => {
    mockPush.mockImplementationOnce(() => ({ key: null as unknown as string }));
    await expect(createVisit('demo', baseInput())).rejects.toThrow('Failed to allocate visitId');
  });
});

// =====================================================================
// updateVisit
// =====================================================================

describe('updateVisit', () => {
  it('partial merge + updatedAt 자동 + audit visit.update', async () => {
    await updateVisit('demo', 'v1', { zone: 'Zone B-2', notes: 'updated' });

    expect(mockUpdate).toHaveBeenCalledTimes(1);
    const patch = mockUpdate.mock.calls[0][1] as Record<string, unknown>;
    expect(patch.zone).toBe('Zone B-2');
    expect(patch.notes).toBe('updated');
    expect(typeof patch.updatedAt).toBe('number');

    expect(mockAppendAudit).toHaveBeenCalledWith(
      'visit.update',
      'v1',
      { fields: ['zone', 'notes'] },
      'demo',
    );
  });
});

// =====================================================================
// updateVisitStatus
// =====================================================================

describe('updateVisitStatus', () => {
  it('checked-in → checkedInAt 자동 stamp + audit', async () => {
    await updateVisitStatus('demo', 'v1', 'checked-in');

    const patch = mockUpdate.mock.calls[0][1] as Record<string, unknown>;
    expect(patch.status).toBe('checked-in');
    expect(typeof patch.checkedInAt).toBe('number');
    expect(patch.completedAt).toBeUndefined();

    expect(mockAppendAudit).toHaveBeenCalledWith(
      'visit.status.change',
      'v1',
      { status: 'checked-in' },
      'demo',
    );
  });

  it('completed → completedAt 자동 stamp', async () => {
    await updateVisitStatus('demo', 'v1', 'completed');

    const patch = mockUpdate.mock.calls[0][1] as Record<string, unknown>;
    expect(patch.status).toBe('completed');
    expect(typeof patch.completedAt).toBe('number');
  });

  it('in-progress → checkedInAt/completedAt stamp 안 함', async () => {
    await updateVisitStatus('demo', 'v1', 'in-progress');

    const patch = mockUpdate.mock.calls[0][1] as Record<string, unknown>;
    expect(patch.status).toBe('in-progress');
    expect(patch.checkedInAt).toBeUndefined();
    expect(patch.completedAt).toBeUndefined();
  });
});

// =====================================================================
// deleteVisit
// =====================================================================

describe('deleteVisit', () => {
  it('remove + audit visit.delete', async () => {
    await deleteVisit('demo', 'v1');
    expect(mockRemove).toHaveBeenCalledTimes(1);
    expect(mockAppendAudit).toHaveBeenCalledWith('visit.delete', 'v1', null, 'demo');
  });
});

// =====================================================================
// subscribeActiveVisit
// =====================================================================

describe('subscribeActiveVisit', () => {
  function fakeSnap(visits: Visit[]) {
    return {
      exists: () => visits.length > 0,
      forEach: (cb: (child: { val: () => Visit }) => void) => {
        for (const v of visits) cb({ val: () => v });
      },
    };
  }

  it('snapshot 빔 → null emit', () => {
    const cb = vi.fn();
    subscribeActiveVisit('demo', 'uid-1', cb);
    const onValueCb = mockOnValue.mock.calls[0][1] as (s: ReturnType<typeof fakeSnap>) => void;
    onValueCb(fakeSnap([]));
    expect(cb).toHaveBeenCalledWith(null);
  });

  it('active(checked-in) 1건만 → 그대로 emit', () => {
    const cb = vi.fn();
    subscribeActiveVisit('demo', 'uid-1', cb);
    const onValueCb = mockOnValue.mock.calls[0][1] as (s: ReturnType<typeof fakeSnap>) => void;
    const v: Visit = {
      visitId: 'v1', patientUid: 'uid-1', hospitalId: 'demo',
      type: 'outpatient', status: 'checked-in', zone: 'Zone A-1', department: 'IM',
      createdAt: 100, updatedAt: 100, createdBy: 'admin-1',
    };
    onValueCb(fakeSnap([v]));
    expect(cb).toHaveBeenCalledWith(v);
  });

  it('active 0건 + scheduled/completed 만 → null', () => {
    const cb = vi.fn();
    subscribeActiveVisit('demo', 'uid-1', cb);
    const onValueCb = mockOnValue.mock.calls[0][1] as (s: ReturnType<typeof fakeSnap>) => void;
    onValueCb(
      fakeSnap([
        {
          visitId: 'v1', patientUid: 'uid-1', hospitalId: 'demo',
          type: 'outpatient', status: 'scheduled', zone: 'Zone A-1', department: 'IM',
          createdAt: 100, updatedAt: 100, createdBy: 'admin-1',
        },
        {
          visitId: 'v2', patientUid: 'uid-1', hospitalId: 'demo',
          type: 'outpatient', status: 'completed', zone: 'Zone A-1', department: 'IM',
          createdAt: 200, updatedAt: 200, createdBy: 'admin-1',
        },
      ]),
    );
    expect(cb).toHaveBeenCalledWith(null);
  });

  it('active 다건 → 가장 최근 createdAt 1건', () => {
    const cb = vi.fn();
    subscribeActiveVisit('demo', 'uid-1', cb);
    const onValueCb = mockOnValue.mock.calls[0][1] as (s: ReturnType<typeof fakeSnap>) => void;
    const v1: Visit = {
      visitId: 'v1', patientUid: 'uid-1', hospitalId: 'demo',
      type: 'outpatient', status: 'in-progress', zone: 'Zone A-1', department: 'IM',
      createdAt: 100, updatedAt: 100, createdBy: 'admin-1',
    };
    const v2: Visit = { ...v1, visitId: 'v2', createdAt: 300, status: 'checked-in' };
    onValueCb(fakeSnap([v1, v2]));
    expect(cb).toHaveBeenCalledWith(v2);
  });
});

// =====================================================================
// subscribeActiveVisitsByDepartment (I.2.2)
// =====================================================================

describe('subscribeActiveVisitsByDepartment', () => {
  function fakeSnap(visits: Visit[]) {
    return {
      exists: () => visits.length > 0,
      forEach: (cb: (child: { val: () => Visit }) => void) => {
        for (const v of visits) cb({ val: () => v });
      },
    };
  }

  function v(overrides: Partial<Visit>): Visit {
    return {
      visitId: 'x',
      patientUid: 'u',
      hospitalId: 'demo',
      type: 'outpatient',
      status: 'checked-in',
      zone: 'Z',
      department: 'IM',
      createdAt: 0,
      updatedAt: 0,
      createdBy: 'admin-1',
      ...overrides,
    };
  }

  const today = new Date('2026-04-26T12:00:00').getTime();
  const yesterday = new Date('2026-04-25T12:00:00').getTime();

  it('snapshot 빔 → [] emit', () => {
    const cb = vi.fn();
    subscribeActiveVisitsByDepartment('demo', 'IM', today, cb);
    const onValueCb = mockOnValue.mock.calls[0][1] as (s: ReturnType<typeof fakeSnap>) => void;
    onValueCb(fakeSnap([]));
    expect(cb).toHaveBeenCalledWith([]);
  });

  it('department 일치 + active + 같은 날 → 포함', () => {
    const cb = vi.fn();
    subscribeActiveVisitsByDepartment('demo', 'IM', today, cb);
    const onValueCb = mockOnValue.mock.calls[0][1] as (s: ReturnType<typeof fakeSnap>) => void;
    const visit = v({ visitId: 'a', department: 'IM', status: 'checked-in', createdAt: today });
    onValueCb(fakeSnap([visit]));
    expect(cb).toHaveBeenCalledWith([visit]);
  });

  it('department 불일치 → 제외', () => {
    const cb = vi.fn();
    subscribeActiveVisitsByDepartment('demo', 'IM', today, cb);
    const onValueCb = mockOnValue.mock.calls[0][1] as (s: ReturnType<typeof fakeSnap>) => void;
    onValueCb(fakeSnap([v({ visitId: 'a', department: 'GS', createdAt: today })]));
    expect(cb).toHaveBeenCalledWith([]);
  });

  it('status=completed → 제외 (active 만)', () => {
    const cb = vi.fn();
    subscribeActiveVisitsByDepartment('demo', 'IM', today, cb);
    const onValueCb = mockOnValue.mock.calls[0][1] as (s: ReturnType<typeof fakeSnap>) => void;
    onValueCb(fakeSnap([v({ visitId: 'a', status: 'completed', createdAt: today })]));
    expect(cb).toHaveBeenCalledWith([]);
  });

  it('status=scheduled → 제외 (active 만)', () => {
    const cb = vi.fn();
    subscribeActiveVisitsByDepartment('demo', 'IM', today, cb);
    const onValueCb = mockOnValue.mock.calls[0][1] as (s: ReturnType<typeof fakeSnap>) => void;
    onValueCb(fakeSnap([v({ visitId: 'a', status: 'scheduled', createdAt: today })]));
    expect(cb).toHaveBeenCalledWith([]);
  });

  it('다른 날 visit → 제외', () => {
    const cb = vi.fn();
    subscribeActiveVisitsByDepartment('demo', 'IM', today, cb);
    const onValueCb = mockOnValue.mock.calls[0][1] as (s: ReturnType<typeof fakeSnap>) => void;
    onValueCb(fakeSnap([v({ visitId: 'a', createdAt: yesterday })]));
    expect(cb).toHaveBeenCalledWith([]);
  });

  it('다건 → createdAt asc 정렬 (대기 순서)', () => {
    const cb = vi.fn();
    subscribeActiveVisitsByDepartment('demo', 'IM', today, cb);
    const onValueCb = mockOnValue.mock.calls[0][1] as (s: ReturnType<typeof fakeSnap>) => void;
    const earlyMs = new Date('2026-04-26T09:00:00').getTime();
    const lateMs = new Date('2026-04-26T15:00:00').getTime();
    onValueCb(
      fakeSnap([
        v({ visitId: 'late', createdAt: lateMs }),
        v({ visitId: 'early', createdAt: earlyMs }),
      ]),
    );
    const emitted = (cb.mock.calls[0][0] as Visit[]).map((x) => x.visitId);
    expect(emitted).toEqual(['early', 'late']);
  });

  it('unsubscribe 함수 반환', () => {
    const unsub = subscribeActiveVisitsByDepartment('demo', 'IM', today, vi.fn());
    expect(typeof unsub).toBe('function');
    unsub();
    expect(mockUnsubscribe).toHaveBeenCalledTimes(1);
  });
});

// =====================================================================
// subscribeRecentVisits
// =====================================================================

describe('subscribeRecentVisits', () => {
  function fakeSnap(visits: Visit[]) {
    return {
      exists: () => visits.length > 0,
      forEach: (cb: (child: { val: () => Visit }) => void) => {
        for (const v of visits) cb({ val: () => v });
      },
    };
  }

  it('snapshot 빔 → empty array emit', () => {
    const cb = vi.fn();
    subscribeRecentVisits('demo', 20, cb);
    const onValueCb = mockOnValue.mock.calls[0][1] as (s: ReturnType<typeof fakeSnap>) => void;
    onValueCb(fakeSnap([]));
    expect(cb).toHaveBeenCalledWith([]);
  });

  it('visits 다건 → createdAt desc 정렬', () => {
    const cb = vi.fn();
    subscribeRecentVisits('demo', 20, cb);
    const onValueCb = mockOnValue.mock.calls[0][1] as (s: ReturnType<typeof fakeSnap>) => void;
    const visits: Visit[] = [
      { visitId: 'a', patientUid: 'u1', hospitalId: 'demo', type: 'outpatient', status: 'scheduled', zone: 'Z', createdAt: 100, updatedAt: 100, createdBy: 'admin-1' },
      { visitId: 'b', patientUid: 'u1', hospitalId: 'demo', type: 'outpatient', status: 'scheduled', zone: 'Z', createdAt: 300, updatedAt: 300, createdBy: 'admin-1' },
      { visitId: 'c', patientUid: 'u1', hospitalId: 'demo', type: 'outpatient', status: 'scheduled', zone: 'Z', createdAt: 200, updatedAt: 200, createdBy: 'admin-1' },
    ];
    onValueCb(fakeSnap(visits));
    const emitted = (cb.mock.calls[0][0] as Visit[]).map((v) => v.visitId);
    expect(emitted).toEqual(['b', 'c', 'a']); // 300, 200, 100
  });

  it('limitToLast(N) 호출 검증', () => {
    subscribeRecentVisits('demo', 5, vi.fn());
    expect(mockLimitToLast).toHaveBeenCalledWith(5);
  });

  it('orderByChild("createdAt") 호출 검증', () => {
    subscribeRecentVisits('demo', 10, vi.fn());
    expect(mockOrderByChild).toHaveBeenCalledWith('createdAt');
  });

  it('unsubscribe 함수 반환 (onValue 의 cleanup)', () => {
    const unsub = subscribeRecentVisits('demo', 20, vi.fn());
    expect(typeof unsub).toBe('function');
    unsub();
    expect(mockUnsubscribe).toHaveBeenCalledTimes(1);
  });
});

// =====================================================================
// listVisitsByPatient
// =====================================================================

describe('listVisitsByPatient', () => {
  it('최신순 sort + limit 적용', async () => {
    const visits: Visit[] = [
      { visitId: 'a', patientUid: 'uid-1', hospitalId: 'demo', type: 'outpatient', status: 'scheduled', zone: 'A', createdAt: 100, updatedAt: 100, createdBy: 'admin-1' },
      { visitId: 'b', patientUid: 'uid-1', hospitalId: 'demo', type: 'outpatient', status: 'completed', zone: 'A', createdAt: 300, updatedAt: 300, createdBy: 'admin-1' },
      { visitId: 'c', patientUid: 'uid-1', hospitalId: 'demo', type: 'outpatient', status: 'completed', zone: 'A', createdAt: 200, updatedAt: 200, createdBy: 'admin-1' },
    ];
    mockGet.mockResolvedValueOnce({
      exists: () => true,
      forEach: (cb: (child: { val: () => Visit }) => void) => {
        for (const v of visits) cb({ val: () => v });
      },
    });

    const out = await listVisitsByPatient('demo', 'uid-1', { limit: 2 });
    expect(out.map((v) => v.visitId)).toEqual(['b', 'c']); // 300, 200 (limit=2, 100 제외)
  });
});

// =====================================================================
// listVisitsByDepartment
// =====================================================================

describe('listVisitsByDepartment', () => {
  it('department 일치 + 같은 날짜 visit 만 반환 (최신순)', async () => {
    const today = new Date('2026-04-26T12:00:00').getTime();
    const yesterday = new Date('2026-04-25T12:00:00').getTime();
    const visits: Visit[] = [
      { visitId: 'a', patientUid: 'uid-1', hospitalId: 'demo', type: 'outpatient', status: 'scheduled', zone: 'A', department: 'IM', createdAt: today, updatedAt: today, createdBy: 'admin-1' },
      { visitId: 'b', patientUid: 'uid-2', hospitalId: 'demo', type: 'outpatient', status: 'scheduled', zone: 'A', department: 'IM', createdAt: yesterday, updatedAt: yesterday, createdBy: 'admin-1' },
      { visitId: 'c', patientUid: 'uid-3', hospitalId: 'demo', type: 'outpatient', status: 'scheduled', zone: 'A', department: 'GS', createdAt: today, updatedAt: today, createdBy: 'admin-1' },
    ];
    mockGet.mockResolvedValueOnce({
      exists: () => true,
      forEach: (cb: (child: { val: () => Visit }) => void) => {
        for (const v of visits) cb({ val: () => v });
      },
    });

    const out = await listVisitsByDepartment('demo', 'IM', today);
    expect(out.map((v) => v.visitId)).toEqual(['a']); // IM + today only
  });
});
