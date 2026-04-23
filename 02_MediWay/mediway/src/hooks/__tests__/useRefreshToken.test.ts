import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook } from '@testing-library/react';

const getIdTokenMock = vi.fn();
const currentUser = { getIdToken: getIdTokenMock, uid: 'uid-1' };
type MockAuthReturn = { currentUser: typeof currentUser | null };
const getAuthMock = vi.fn<[], MockAuthReturn>(() => ({ currentUser }));

vi.mock('firebase/auth', () => ({
  getAuth: () => getAuthMock(),
}));

const callableMock = vi.fn();
const httpsCallableMock = vi.fn<unknown[], typeof callableMock>(
  () => callableMock,
);

vi.mock('firebase/functions', () => ({
  httpsCallable: (...args: unknown[]) => httpsCallableMock(...args),
}));

vi.mock('@/config/firebase', () => ({
  functions: {},
}));

import { useRefreshToken } from '../useRefreshToken';

beforeEach(() => {
  getIdTokenMock.mockReset();
  callableMock.mockReset();
  httpsCallableMock.mockClear();
});

describe('useRefreshToken', () => {
  it('refreshMyClaims 호출 + getIdToken(true) 강제 갱신', async () => {
    callableMock.mockResolvedValueOnce({
      data: {
        claims: {
          role: 'patient',
          hospitalId: 'demo',
          hospitalIds: ['demo'],
          claimsSetAt: 123,
        },
        forceRefresh: true,
      },
    });
    getIdTokenMock.mockResolvedValueOnce('new-token');

    const { result } = renderHook(() => useRefreshToken());
    const claims = await result.current();

    expect(claims?.role).toBe('patient');
    expect(claims?.hospitalId).toBe('demo');
    expect(callableMock).toHaveBeenCalled();
    expect(getIdTokenMock).toHaveBeenCalledWith(true);
    // httpsCallable 이름이 'refreshMyClaims'
    expect(httpsCallableMock.mock.calls[0][1]).toBe('refreshMyClaims');
  });

  it('로그인 안 된 상태 → throw', async () => {
    getAuthMock.mockImplementationOnce(() => ({ currentUser: null }));
    const { result } = renderHook(() => useRefreshToken());
    await expect(result.current()).rejects.toThrow(/로그인/);
    expect(callableMock).not.toHaveBeenCalled();
  });

  it('callable 에러는 hook 밖으로 전파', async () => {
    callableMock.mockRejectedValueOnce(new Error('permission-denied'));
    const { result } = renderHook(() => useRefreshToken());
    await expect(result.current()).rejects.toThrow(/permission-denied/);
    expect(getIdTokenMock).not.toHaveBeenCalled();
  });
});
