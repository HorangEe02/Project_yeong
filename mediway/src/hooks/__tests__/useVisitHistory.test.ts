import { describe, it, expect, beforeEach, vi } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import type { Visit } from '@/types/visit';

const mockListVisitsByPatient = vi.fn();
vi.mock('@/services/visit', () => ({
  listVisitsByPatient: (...args: unknown[]) => mockListVisitsByPatient(...args),
}));

import { useVisitHistory } from '../useVisitHistory';

beforeEach(() => {
  mockListVisitsByPatient.mockReset();
});

function makeVisit(overrides: Partial<Visit> = {}): Visit {
  return {
    visitId: 'v1',
    patientUid: 'uid-1',
    hospitalId: 'demo',
    type: 'outpatient',
    status: 'completed',
    zone: 'Z',
    department: 'IM',
    createdAt: 100,
    updatedAt: 100,
    createdBy: 'admin-1',
    ...overrides,
  };
}

describe('useVisitHistory', () => {
  it('slug null → idle (listVisitsByPatient 안 호출)', () => {
    const { result } = renderHook(() => useVisitHistory(null, 'uid-1'));
    expect(result.current.loading).toBe(false);
    expect(result.current.visits).toEqual([]);
    expect(result.current.error).toBeNull();
    expect(mockListVisitsByPatient).not.toHaveBeenCalled();
  });

  it('patientUid null → idle', () => {
    const { result } = renderHook(() => useVisitHistory('demo', null));
    expect(result.current.loading).toBe(false);
    expect(mockListVisitsByPatient).not.toHaveBeenCalled();
  });

  it('마운트 시 loading=true → 성공 시 visits 갱신 + loading=false', async () => {
    const list = [makeVisit({ visitId: 'a' }), makeVisit({ visitId: 'b' })];
    mockListVisitsByPatient.mockResolvedValueOnce(list);

    const { result } = renderHook(() => useVisitHistory('demo', 'uid-1'));
    expect(result.current.loading).toBe(true);

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });
    expect(result.current.visits).toEqual(list);
    expect(result.current.error).toBeNull();
    expect(mockListVisitsByPatient).toHaveBeenCalledWith('demo', 'uid-1', { limit: 50 });
  });

  it('listVisitsByPatient reject → error 설정 + loading=false', async () => {
    mockListVisitsByPatient.mockRejectedValueOnce(new Error('PERMISSION_DENIED'));

    const { result } = renderHook(() => useVisitHistory('demo', 'uid-1'));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });
    expect(result.current.error).toBe('PERMISSION_DENIED');
    expect(result.current.visits).toEqual([]);
  });

  it('refresh() 호출 → listVisitsByPatient 재호출', async () => {
    mockListVisitsByPatient.mockResolvedValue([]);
    const { result } = renderHook(() => useVisitHistory('demo', 'uid-1'));

    await waitFor(() => {
      expect(mockListVisitsByPatient).toHaveBeenCalledTimes(1);
    });

    act(() => result.current.refresh());

    await waitFor(() => {
      expect(mockListVisitsByPatient).toHaveBeenCalledTimes(2);
    });
  });

  it('opts.limit 전달', async () => {
    mockListVisitsByPatient.mockResolvedValue([]);
    renderHook(() => useVisitHistory('demo', 'uid-1', { limit: 10 }));
    await waitFor(() => {
      expect(mockListVisitsByPatient).toHaveBeenCalledWith('demo', 'uid-1', { limit: 10 });
    });
  });
});
