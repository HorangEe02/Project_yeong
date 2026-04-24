import { describe, it, expect, beforeEach, vi } from 'vitest';

// admin.database().ref(path).get() / push() 흐름을 모킹한다.
const mockGet = vi.fn();
const mockPush = vi.fn();
const mockSetCustomUserClaims = vi.fn();
const mockGetUser = vi.fn();

vi.mock('firebase-admin', () => {
  const refFactory = (path: string) => ({
    get: () => mockGet(path),
    push: (value: unknown) => mockPush(path, value),
  });
  return {
    default: {
      database: () => ({ ref: refFactory }),
      auth: () => ({
        setCustomUserClaims: mockSetCustomUserClaims,
        getUser: mockGetUser,
      }),
    },
    database: () => ({ ref: refFactory }),
    auth: () => ({
      setCustomUserClaims: mockSetCustomUserClaims,
      getUser: mockGetUser,
    }),
  };
});

// onCall을 걷어내 핸들러를 순수 함수처럼 테스트한다.
// 실제 런타임에서는 CallableFunction 객체를 만들어 리턴하지만, 테스트에선 핸들러만 직접 호출한다.
vi.mock('firebase-functions/v2/https', async () => {
  const actual = await vi.importActual<typeof import('firebase-functions/v2/https')>(
    'firebase-functions/v2/https',
  );
  return {
    ...actual,
    onCall: (_opts: unknown, handler: unknown) => handler,
  };
});

import {
  buildClaimsFromProfile,
  injectClaimsForUid,
  refreshMyClaims,
  setUserClaims,
} from '../setClaims';

type CallableHandler = (req: {
  auth?: { uid: string; token: Record<string, unknown> };
  data: unknown;
}) => Promise<unknown>;

describe('buildClaimsFromProfile', () => {
  beforeEach(() => {
    mockGet.mockReset();
    mockPush.mockReset();
    mockSetCustomUserClaims.mockReset();
  });

  it('staff 프로필 → role·hospitalId 주입', async () => {
    mockGet.mockResolvedValueOnce({
      exists: () => true,
      val: () => ({ role: 'staff', hospitalId: 'smch', department: 'ER' }),
    });
    const claims = await buildClaimsFromProfile('uid-1');
    expect(claims.role).toBe('staff');
    expect(claims.hospitalId).toBe('smch');
    expect(claims.hospitalIds).toEqual([]);
    expect(typeof claims.claimsSetAt).toBe('number');
  });

  it('primaryHospitalId 우선 적용, 없으면 hospitalId로 fallback', async () => {
    mockGet.mockResolvedValueOnce({
      exists: () => true,
      val: () => ({
        role: 'patient',
        primaryHospitalId: 'smch',
        hospitalId: 'fallback',
      }),
    });
    const claims = await buildClaimsFromProfile('uid-2');
    expect(claims.hospitalId).toBe('smch');
  });

  it('hospitalIds 배열이 있으면 전달, 아니면 []로 정규화', async () => {
    mockGet.mockResolvedValueOnce({
      exists: () => true,
      val: () => ({ role: 'patient', hospitalIds: ['smch', 'snuh'] }),
    });
    const a = await buildClaimsFromProfile('uid-3a');
    expect(a.hospitalIds).toEqual(['smch', 'snuh']);

    mockGet.mockResolvedValueOnce({
      exists: () => true,
      val: () => ({ role: 'patient' }),
    });
    const b = await buildClaimsFromProfile('uid-3b');
    expect(b.hospitalIds).toEqual([]);
  });

  it('role 누락 시 patient로 기본값 주입', async () => {
    mockGet.mockResolvedValueOnce({
      exists: () => true,
      val: () => ({ hospitalId: 'smch' }),
    });
    const claims = await buildClaimsFromProfile('uid-4');
    expect(claims.role).toBe('patient');
  });

  it('프로필 미존재 → not-found HttpsError', async () => {
    mockGet.mockResolvedValueOnce({ exists: () => false, val: () => null });
    await expect(buildClaimsFromProfile('missing-uid')).rejects.toMatchObject({
      code: 'not-found',
    });
  });
});

describe('injectClaimsForUid', () => {
  beforeEach(() => {
    mockGet.mockReset();
    mockPush.mockReset();
    mockSetCustomUserClaims.mockReset();
  });

  it('프로필 존재 시 setCustomUserClaims + audit_logs 기록', async () => {
    mockGet.mockResolvedValueOnce({
      exists: () => true,
      val: () => ({ role: 'staff', hospitalId: 'smch' }),
    });
    mockPush.mockResolvedValueOnce(undefined);
    mockSetCustomUserClaims.mockResolvedValueOnce(undefined);

    await injectClaimsForUid('uid-10', 'ensureUserRecord');

    expect(mockSetCustomUserClaims).toHaveBeenCalledTimes(1);
    const [uidArg, claimsArg] = mockSetCustomUserClaims.mock.calls[0];
    expect(uidArg).toBe('uid-10');
    expect(claimsArg.role).toBe('staff');

    // T1-1c cutover: v2-only (legacy write 제거됨)
    expect(mockPush).toHaveBeenCalledTimes(1);
    const [path, value] = mockPush.mock.calls[0];
    expect(path).toBe('audit_logs_v2/smch');
    expect((value as { action: string }).action).toBe('user.claims.autoInject');
    expect((value as { meta: { origin: string } }).meta.origin).toBe('ensureUserRecord');
  });

  it('프로필 미존재 + throwOnError=false이면 silently 로깅만', async () => {
    mockGet.mockResolvedValueOnce({ exists: () => false, val: () => null });
    await expect(
      injectClaimsForUid('missing-uid', 'ensureUserRecord'),
    ).resolves.toBeUndefined();
    expect(mockSetCustomUserClaims).not.toHaveBeenCalled();
  });

  it('프로필 미존재 + throwOnError=true이면 호출자에게 throw', async () => {
    mockGet.mockResolvedValueOnce({ exists: () => false, val: () => null });
    await expect(
      injectClaimsForUid('missing-uid', 'adminCreateStaff', true),
    ).rejects.toMatchObject({ code: 'not-found' });
    expect(mockSetCustomUserClaims).not.toHaveBeenCalled();
  });
});

describe('refreshMyClaims 핸들러', () => {
  const handler = refreshMyClaims as unknown as CallableHandler;

  beforeEach(() => {
    mockGet.mockReset();
    mockPush.mockReset();
    mockSetCustomUserClaims.mockReset();
  });

  it('미인증 요청은 unauthenticated 에러', async () => {
    await expect(handler({ data: undefined })).rejects.toMatchObject({
      code: 'unauthenticated',
    });
  });

  it('본인 프로필 기반 claim 설정 + audit 로그 + forceRefresh 플래그 반환', async () => {
    mockGet.mockResolvedValueOnce({
      exists: () => true,
      val: () => ({ role: 'staff', hospitalId: 'smch' }),
    });
    mockSetCustomUserClaims.mockResolvedValueOnce(undefined);
    mockPush.mockResolvedValueOnce(undefined);

    const result = (await handler({
      auth: { uid: 'uid-1', token: {} },
      data: undefined,
    })) as { claims: { role: string }; forceRefresh: boolean };

    expect(result.forceRefresh).toBe(true);
    expect(result.claims.role).toBe('staff');
    expect(mockSetCustomUserClaims).toHaveBeenCalledWith(
      'uid-1',
      expect.objectContaining({ role: 'staff', hospitalId: 'smch' }),
    );
    const [auditPath, auditValue] = mockPush.mock.calls[0];
    expect(auditPath).toBe('audit_logs_v2/smch');
    expect((auditValue as { action: string }).action).toBe('user.claims.refresh');
  });
});

describe('setUserClaims 핸들러 — 권한·검증·에스컬레이션 방어', () => {
  const handler = setUserClaims as unknown as CallableHandler;

  beforeEach(() => {
    mockGet.mockReset();
    mockPush.mockReset();
    mockSetCustomUserClaims.mockReset();
    mockGetUser.mockReset();
  });

  it('미인증 요청은 unauthenticated', async () => {
    await expect(
      handler({ data: { uid: 'target', role: 'staff' } }),
    ).rejects.toMatchObject({ code: 'unauthenticated' });
  });

  it('patient 호출자는 permission-denied', async () => {
    await expect(
      handler({
        auth: { uid: 'caller', token: { role: 'patient' } },
        data: { uid: 'target', role: 'staff' },
      }),
    ).rejects.toMatchObject({ code: 'permission-denied' });
  });

  it('staff 호출자도 permission-denied', async () => {
    await expect(
      handler({
        auth: { uid: 'caller', token: { role: 'staff' } },
        data: { uid: 'target', role: 'staff' },
      }),
    ).rejects.toMatchObject({ code: 'permission-denied' });
  });

  it('잘못된 role 값은 invalid-argument (Zod)', async () => {
    await expect(
      handler({
        auth: { uid: 'caller', token: { role: 'admin' } },
        data: { uid: 'target', role: 'superuser' },
      }),
    ).rejects.toMatchObject({ code: 'invalid-argument' });
  });

  it('uid 누락은 invalid-argument (Zod)', async () => {
    await expect(
      handler({
        auth: { uid: 'caller', token: { role: 'admin' } },
        data: { role: 'staff' },
      }),
    ).rejects.toMatchObject({ code: 'invalid-argument' });
  });

  it('🔒 admin은 다른 유저를 platformAdmin으로 승격시킬 수 없다 (에스컬레이션 방어)', async () => {
    await expect(
      handler({
        auth: { uid: 'some-admin', token: { role: 'admin' } },
        data: { uid: 'target', role: 'platformAdmin' },
      }),
    ).rejects.toMatchObject({ code: 'permission-denied' });
    expect(mockSetCustomUserClaims).not.toHaveBeenCalled();
  });

  it('platformAdmin은 platformAdmin 부여 가능', async () => {
    mockGetUser.mockResolvedValueOnce({ customClaims: null });
    mockSetCustomUserClaims.mockResolvedValueOnce(undefined);
    mockPush.mockResolvedValueOnce(undefined);
    const result = (await handler({
      auth: { uid: 'platform-admin', token: { role: 'platformAdmin' } },
      data: { uid: 'target', role: 'platformAdmin' },
    })) as { claims: { role: string } };
    expect(result.claims.role).toBe('platformAdmin');
    expect(mockSetCustomUserClaims).toHaveBeenCalledTimes(1);
  });

  it('admin이 staff 부여 시 before/after 기록된 audit 로그 작성', async () => {
    mockGetUser.mockResolvedValueOnce({
      customClaims: { role: 'patient', hospitalId: null, hospitalIds: [], claimsSetAt: 1 },
    });
    mockSetCustomUserClaims.mockResolvedValueOnce(undefined);
    mockPush.mockResolvedValueOnce(undefined);

    await handler({
      auth: { uid: 'some-admin', token: { role: 'admin', email: 'a@x' } },
      data: { uid: 'target', role: 'staff', hospitalId: 'smch', reason: '승격 요청' },
    });

    const [path, value] = mockPush.mock.calls[0];
    expect(path).toBe('audit_logs_v2/smch');
    const log = value as {
      action: string;
      actorUid: string;
      actorEmail: string;
      target: string;
      meta: {
        before: { role: string } | null;
        after: { role: string };
        reason: string | null;
      };
    };
    expect(log.action).toBe('user.claims.setByAdmin');
    expect(log.actorUid).toBe('some-admin');
    expect(log.actorEmail).toBe('a@x');
    expect(log.target).toBe('target');
    expect(log.meta.before?.role).toBe('patient');
    expect(log.meta.after.role).toBe('staff');
    expect(log.meta.reason).toBe('승격 요청');
  });
});
