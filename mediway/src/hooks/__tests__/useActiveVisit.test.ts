import { describe, it, expect, beforeEach, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import type { Visit } from '@/types/visit';

// --- mocks ---

const mockUnsubscribe = vi.fn();
const mockSubscribe = vi.fn();

vi.mock('@/services/visit', () => ({
  subscribeActiveVisit: (
    slug: string,
    uid: string,
    cb: (v: Visit | null) => void,
  ) => {
    mockSubscribe(slug, uid, cb);
    return mockUnsubscribe;
  },
}));

import { useActiveVisit } from '../useActiveVisit';

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

describe('useActiveVisit', () => {
  it('slug null → idle (subscribe 안 호출)', () => {
    const { result } = renderHook(() => useActiveVisit(null, 'uid-1'));
    expect(result.current.loading).toBe(false);
    expect(result.current.visit).toBeNull();
    expect(mockSubscribe).not.toHaveBeenCalled();
  });

  it('patientUid null → idle', () => {
    const { result } = renderHook(() => useActiveVisit('demo', null));
    expect(result.current.loading).toBe(false);
    expect(result.current.visit).toBeNull();
    expect(mockSubscribe).not.toHaveBeenCalled();
  });

  it('slug + uid → 첫 emit 전 loading=true + subscribe 호출', () => {
    const { result } = renderHook(() => useActiveVisit('demo', 'uid-1'));
    expect(result.current.loading).toBe(true);
    expect(result.current.visit).toBeNull();
    expect(mockSubscribe).toHaveBeenCalledTimes(1);
    expect(mockSubscribe).toHaveBeenCalledWith('demo', 'uid-1', expect.any(Function));
  });

  it('emit 후 visit 갱신 + loading=false', () => {
    const { result } = renderHook(() => useActiveVisit('demo', 'uid-1'));
    const cb = mockSubscribe.mock.calls[0][2] as (v: Visit | null) => void;
    const v = makeVisit();
    act(() => cb(v));
    expect(result.current.visit).toEqual(v);
    expect(result.current.loading).toBe(false);
  });

  it('emit null → visit=null, loading=false (active 없음 의미)', () => {
    const { result } = renderHook(() => useActiveVisit('demo', 'uid-1'));
    const cb = mockSubscribe.mock.calls[0][2] as (v: Visit | null) => void;
    act(() => cb(null));
    expect(result.current.visit).toBeNull();
    expect(result.current.loading).toBe(false);
  });

  it('patientUid 변경 → 이전 unsubscribe + 새 subscribe', () => {
    const { rerender } = renderHook(
      ({ uid }) => useActiveVisit('demo', uid),
      { initialProps: { uid: 'uid-1' } },
    );
    expect(mockSubscribe).toHaveBeenCalledTimes(1);
    rerender({ uid: 'uid-2' });
    expect(mockUnsubscribe).toHaveBeenCalledTimes(1);
    expect(mockSubscribe).toHaveBeenCalledTimes(2);
    expect(mockSubscribe.mock.calls[1][1]).toBe('uid-2');
  });

  it('unmount 시 unsubscribe', () => {
    const { unmount } = renderHook(() => useActiveVisit('demo', 'uid-1'));
    expect(mockUnsubscribe).not.toHaveBeenCalled();
    unmount();
    expect(mockUnsubscribe).toHaveBeenCalledTimes(1);
  });
});
