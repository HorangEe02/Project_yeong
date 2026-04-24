import { describe, it, expect, beforeEach, vi } from 'vitest';

const mockHttpsCallable = vi.fn();
const mockGetIdToken = vi.fn();
const mockGetIdTokenResult = vi.fn();

vi.mock('@/config/firebase', () => ({
  isFirebaseConfigured: () => true,
  auth: {
    get currentUser() {
      return {
        uid: 'uid-1',
        isAnonymous: false,
        getIdToken: mockGetIdToken,
        getIdTokenResult: mockGetIdTokenResult,
      };
    },
  },
  functions: { __mocked: true },
}));

vi.mock('firebase/functions', () => ({
  httpsCallable: (...args: unknown[]) => mockHttpsCallable(...args),
}));

import { refreshMyClaims, hasRoleClaim } from '../useRefreshToken';

describe('refreshMyClaims', () => {
  beforeEach(() => {
    mockHttpsCallable.mockReset();
    mockGetIdToken.mockReset();
    mockGetIdTokenResult.mockReset();
  });

  it('callable 호출 후 getIdToken(true)로 강제 갱신', async () => {
    const callable = vi.fn().mockResolvedValue({
      data: {
        claims: {
          role: 'patient',
          hospitalId: 'smch',
          hospitalIds: [],
          claimsSetAt: 1,
        },
        forceRefresh: true,
      },
    });
    mockHttpsCallable.mockReturnValue(callable);
    mockGetIdToken.mockResolvedValue('new-token');

    const result = await refreshMyClaims();

    expect(mockHttpsCallable).toHaveBeenCalledWith(
      expect.anything(),
      'refreshMyClaims',
    );
    expect(callable).toHaveBeenCalledTimes(1);
    expect(mockGetIdToken).toHaveBeenCalledWith(true);
    expect(result?.claims.role).toBe('patient');
    expect(result?.forceRefresh).toBe(true);
  });
});

describe('hasRoleClaim', () => {
  beforeEach(() => {
    mockGetIdTokenResult.mockReset();
  });

  it('role claim 있으면 true', async () => {
    mockGetIdTokenResult.mockResolvedValue({ claims: { role: 'patient' } });
    await expect(hasRoleClaim()).resolves.toBe(true);
  });

  it('role claim 없으면 false', async () => {
    mockGetIdTokenResult.mockResolvedValue({ claims: {} });
    await expect(hasRoleClaim()).resolves.toBe(false);
  });
});
