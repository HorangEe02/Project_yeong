import { describe, it, expect, vi, beforeEach } from 'vitest';

// firebase-admin 전체를 mock — admin.auth() / admin.database()
const setCustomUserClaims = vi.fn();
const refGet = vi.fn();
const refs: string[] = [];

vi.mock('firebase-admin', () => {
  const api = {
    auth: () => ({ setCustomUserClaims }),
    database: () => ({
      ref: (path: string) => {
        refs.push(path);
        return { get: refGet };
      },
    }),
  };
  return { default: api, ...api };
});

import { applyClaimsFromProfile } from '../setClaims';

beforeEach(() => {
  setCustomUserClaims.mockReset();
  refGet.mockReset();
  refs.length = 0;
});

describe('applyClaimsFromProfile', () => {
  it('프로필 존재 시 role/hospitalId/hospitalIds로 claim 설정', async () => {
    refGet.mockResolvedValueOnce({
      exists: () => true,
      val: () => ({
        role: 'staff',
        primaryHospitalId: 'demo',
        hospitalIds: ['demo', 'smch'],
      }),
    });
    const claims = await applyClaimsFromProfile('uid-1');
    expect(claims.role).toBe('staff');
    expect(claims.hospitalId).toBe('demo');
    expect(claims.hospitalIds).toEqual(['demo', 'smch']);
    expect(claims.claimsSetAt).toBeTypeOf('number');
    expect(setCustomUserClaims).toHaveBeenCalledWith(
      'uid-1',
      expect.objectContaining({
        role: 'staff',
        hospitalId: 'demo',
        hospitalIds: ['demo', 'smch'],
      }),
    );
    expect(refs).toContain('users/uid-1');
  });

  it('primaryHospitalId 없을 때 레거시 hospitalId 사용', async () => {
    refGet.mockResolvedValueOnce({
      exists: () => true,
      val: () => ({
        role: 'staff',
        hospitalId: 'legacy-h',
      }),
    });
    const claims = await applyClaimsFromProfile('uid-legacy');
    expect(claims.hospitalId).toBe('legacy-h');
  });

  it('role 없으면 patient 기본값', async () => {
    refGet.mockResolvedValueOnce({
      exists: () => true,
      val: () => ({ primaryHospitalId: 'demo' }),
    });
    const claims = await applyClaimsFromProfile('uid-p');
    expect(claims.role).toBe('patient');
  });

  it('hospitalId 전무 시 null', async () => {
    refGet.mockResolvedValueOnce({
      exists: () => true,
      val: () => ({ role: 'patient' }),
    });
    const claims = await applyClaimsFromProfile('uid-no-h');
    expect(claims.hospitalId).toBeNull();
    expect(claims.hospitalIds).toEqual([]);
  });

  it('프로필 없으면 throw', async () => {
    refGet.mockResolvedValueOnce({ exists: () => false });
    await expect(applyClaimsFromProfile('ghost')).rejects.toThrow(
      /유저 프로필 없음/,
    );
    expect(setCustomUserClaims).not.toHaveBeenCalled();
  });
});
