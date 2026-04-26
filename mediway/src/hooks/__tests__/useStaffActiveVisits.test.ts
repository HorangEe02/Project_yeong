import { describe, it, expect, beforeEach, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import type { Visit } from '@/types/visit';

const mockUnsubscribe = vi.fn();
const mockSubscribe = vi.fn();

vi.mock('@/services/visit', () => ({
  subscribeActiveVisitsByDepartment: (
    slug: string,
    dept: string,
    dateMs: number,
    cb: (vs: Visit[]) => void,
  ) => {
    mockSubscribe(slug, dept, dateMs, cb);
    return mockUnsubscribe;
  },
}));

import { useStaffActiveVisits } from '../useStaffActiveVisits';

beforeEach(() => {
  mockSubscribe.mockReset();
  mockUnsubscribe.mockReset();
});

function makeVisit(overrides: Partial<Visit> = {}): Visit {
  return {
    visitId: 'v1',
    patientUid: 'uid-1',
    hospitalId: 'demo',
    type: 'outpatient',
    status: 'checked-in',
    zone: 'Zone A-1',
    department: 'IM',
    createdAt: 100,
    updatedAt: 100,
    createdBy: 'admin-1',
    ...overrides,
  };
}

describe('useStaffActiveVisits', () => {
  it('slug null → idle', () => {
    const { result } = renderHook(() => useStaffActiveVisits(null, 'IM'));
    expect(result.current.loading).toBe(false);
    expect(result.current.visits).toEqual([]);
    expect(mockSubscribe).not.toHaveBeenCalled();
  });

  it('dept null → idle', () => {
    const { result } = renderHook(() => useStaffActiveVisits('demo', null));
    expect(result.current.loading).toBe(false);
    expect(result.current.visits).toEqual([]);
    expect(mockSubscribe).not.toHaveBeenCalled();
  });

  it('slug + dept → 첫 emit 전 loading=true', () => {
    const { result } = renderHook(() => useStaffActiveVisits('demo', 'IM'));
    expect(result.current.loading).toBe(true);
    expect(result.current.visits).toEqual([]);
    expect(mockSubscribe).toHaveBeenCalledTimes(1);
    expect(mockSubscribe.mock.calls[0][0]).toBe('demo');
    expect(mockSubscribe.mock.calls[0][1]).toBe('IM');
  });

  it('emit 후 visits 갱신 + loading=false', () => {
    const { result } = renderHook(() => useStaffActiveVisits('demo', 'IM'));
    const cb = mockSubscribe.mock.calls[0][3] as (vs: Visit[]) => void;
    const list = [makeVisit({ visitId: 'a' }), makeVisit({ visitId: 'b' })];
    act(() => cb(list));
    expect(result.current.visits).toEqual(list);
    expect(result.current.loading).toBe(false);
  });

  it('dept 변경 → unsubscribe + 재구독', () => {
    const { rerender } = renderHook(
      ({ d }) => useStaffActiveVisits('demo', d),
      { initialProps: { d: 'IM' } },
    );
    expect(mockSubscribe).toHaveBeenCalledTimes(1);
    rerender({ d: 'GS' });
    expect(mockUnsubscribe).toHaveBeenCalledTimes(1);
    expect(mockSubscribe).toHaveBeenCalledTimes(2);
    expect(mockSubscribe.mock.calls[1][1]).toBe('GS');
  });

  it('unmount → unsubscribe', () => {
    const { unmount } = renderHook(() => useStaffActiveVisits('demo', 'IM'));
    expect(mockUnsubscribe).not.toHaveBeenCalled();
    unmount();
    expect(mockUnsubscribe).toHaveBeenCalledTimes(1);
  });
});
