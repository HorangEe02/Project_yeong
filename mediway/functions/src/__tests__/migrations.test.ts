import { describe, it, expect, beforeEach, vi } from 'vitest';

// admin 모킹 — 페이지네이션 체이닝 (orderByKey, startAfter, limitToFirst, get) + push + set + getUser
const mockGet = vi.fn();
const mockSet = vi.fn();
const mockPush = vi.fn();
const mockSetCustomUserClaims = vi.fn();
const mockGetUser = vi.fn();

function chainedQuery() {
  const ctx: { startAfterKey: string | null } = { startAfterKey: null };
  const builder = {
    orderByKey: () => builder,
    startAfter: (key: string) => {
      ctx.startAfterKey = key;
      return builder;
    },
    limitToFirst: () => builder,
    get: () => mockGet(ctx.startAfterKey),
  };
  return builder;
}

vi.mock('firebase-admin', () => {
  const refFactory = (path: string) => ({
    get: () => mockGet(path),
    set: (value: unknown) => mockSet(path, value),
    push: (value: unknown) => mockPush(path, value),
    orderByKey: () => chainedQuery(),
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

vi.mock('firebase-functions/v2/https', async () => {
  const actual = await vi.importActual<typeof import('firebase-functions/v2/https')>(
    'firebase-functions/v2/https',
  );
  return {
    ...actual,
    onCall: (_opts: unknown, handler: unknown) => handler,
  };
});

import { migrateAllClaims } from '../migrations/migrateAllClaims';
import { verifyMigration } from '../migrations/verifyMigration';

type Handler = (req: {
  auth?: { uid: string; token: Record<string, unknown> };
  data: unknown;
}) => Promise<unknown>;

describe('migrateAllClaims — 권한·검증', () => {
  const handler = migrateAllClaims as unknown as Handler;

  beforeEach(() => {
    mockGet.mockReset();
    mockSet.mockReset();
    mockPush.mockReset();
    mockSetCustomUserClaims.mockReset();
    mockGetUser.mockReset();
  });

  it('미인증 요청은 unauthenticated', async () => {
    await expect(handler({ data: {} })).rejects.toMatchObject({
      code: 'unauthenticated',
    });
  });

  it('admin 호출자도 permission-denied (platformAdmin 전용)', async () => {
    await expect(
      handler({
        auth: { uid: 'some-admin', token: { role: 'admin' } },
        data: {},
      }),
    ).rejects.toMatchObject({ code: 'permission-denied' });
  });

  it('patient·staff 호출자도 permission-denied', async () => {
    await expect(
      handler({
        auth: { uid: 'p', token: { role: 'patient' } },
        data: {},
      }),
    ).rejects.toMatchObject({ code: 'permission-denied' });
    await expect(
      handler({
        auth: { uid: 's', token: { role: 'staff' } },
        data: {},
      }),
    ).rejects.toMatchObject({ code: 'permission-denied' });
  });
});

describe('migrateAllClaims — 실행', () => {
  const handler = migrateAllClaims as unknown as Handler;
  const platformAdmin = { auth: { uid: 'pa', token: { role: 'platformAdmin' } } };

  beforeEach(() => {
    mockGet.mockReset();
    mockSet.mockReset();
    mockPush.mockReset();
    mockSetCustomUserClaims.mockReset();
  });

  it('활성 유저 3명 claim 주입 + audit + progress 저장', async () => {
    // progress 조회 — 첫 실행이므로 미존재
    mockGet
      .mockResolvedValueOnce({ exists: () => false, val: () => null }) // progress ref
      // 첫 페이지: 3명 모두 active
      .mockResolvedValueOnce({
        val: () => ({
          u1: { role: 'patient', status: 'active' },
          u2: { role: 'staff', hospitalId: 'smch', status: 'active' },
          u3: { role: 'admin', hospitalId: 'snuh', status: 'active' },
        }),
      })
      // 각 유저 프로필 재조회 (buildClaimsFromProfile 내부)
      .mockResolvedValueOnce({ exists: () => true, val: () => ({ role: 'patient', status: 'active' }) })
      .mockResolvedValueOnce({ exists: () => true, val: () => ({ role: 'staff', hospitalId: 'smch', status: 'active' }) })
      .mockResolvedValueOnce({ exists: () => true, val: () => ({ role: 'admin', hospitalId: 'snuh', status: 'active' }) });

    mockSetCustomUserClaims.mockResolvedValue(undefined);
    mockPush.mockResolvedValue(undefined);
    mockSet.mockResolvedValue(undefined);

    const result = (await handler({ ...platformAdmin, data: {} })) as {
      migrationId: string;
      progress: { migrated: number; failed: number; skipped: number; processed: number; finishedAt: number };
    };

    expect(mockSetCustomUserClaims).toHaveBeenCalledTimes(3);
    expect(mockSetCustomUserClaims).toHaveBeenCalledWith('u1', expect.objectContaining({ role: 'patient' }));
    expect(mockSetCustomUserClaims).toHaveBeenCalledWith('u2', expect.objectContaining({ role: 'staff', hospitalId: 'smch' }));
    expect(mockSetCustomUserClaims).toHaveBeenCalledWith('u3', expect.objectContaining({ role: 'admin', hospitalId: 'snuh' }));

    // audit_logs push는 각 유저마다 1회
    const auditCalls = mockPush.mock.calls.filter(([p]) => p === 'audit_logs');
    expect(auditCalls).toHaveLength(3);
    expect((auditCalls[0][1] as { action: string }).action).toBe('user.claims.migration.v1');

    expect(result.progress.migrated).toBe(3);
    expect(result.progress.failed).toBe(0);
    expect(result.progress.skipped).toBe(0);
    expect(result.progress.finishedAt).toBeGreaterThan(0);
  });

  it('비활성(suspended/deleted) 유저는 skip', async () => {
    mockGet
      .mockResolvedValueOnce({ exists: () => false, val: () => null })
      .mockResolvedValueOnce({
        val: () => ({
          u1: { role: 'patient', status: 'active' },
          u2: { role: 'patient', status: 'suspended' },
          u3: { role: 'patient', status: 'deleted' },
        }),
      })
      .mockResolvedValueOnce({ exists: () => true, val: () => ({ role: 'patient', status: 'active' }) });

    mockSetCustomUserClaims.mockResolvedValue(undefined);
    mockPush.mockResolvedValue(undefined);
    mockSet.mockResolvedValue(undefined);

    const result = (await handler({ ...platformAdmin, data: {} })) as {
      progress: { migrated: number; skipped: number };
    };

    expect(result.progress.migrated).toBe(1);
    expect(result.progress.skipped).toBe(2);
    expect(mockSetCustomUserClaims).toHaveBeenCalledTimes(1);
  });

  it('dryRun 모드는 setCustomUserClaims·audit push 호출 없이 count만 반환', async () => {
    mockGet
      .mockResolvedValueOnce({ exists: () => false, val: () => null })
      .mockResolvedValueOnce({
        val: () => ({ u1: { role: 'patient', status: 'active' } }),
      })
      .mockResolvedValueOnce({ exists: () => true, val: () => ({ role: 'patient', status: 'active' }) });

    mockSet.mockResolvedValue(undefined);

    const result = (await handler({ ...platformAdmin, data: { dryRun: true } })) as {
      progress: { migrated: number };
      dryRun: boolean;
    };

    expect(result.dryRun).toBe(true);
    expect(result.progress.migrated).toBe(1);
    expect(mockSetCustomUserClaims).not.toHaveBeenCalled();
    const auditCalls = mockPush.mock.calls.filter(([p]) => p === 'audit_logs');
    expect(auditCalls).toHaveLength(0);
  });

  it('이미 완료된 migration은 재실행 시 alreadyCompleted=true 반환', async () => {
    mockGet.mockResolvedValueOnce({
      exists: () => true,
      val: () => ({
        startedAt: 1,
        lastKey: 'u10',
        processed: 10,
        migrated: 10,
        skipped: 0,
        failed: 0,
        errors: [],
        finishedAt: 2,
      }),
    });

    const result = (await handler({
      ...platformAdmin,
      data: { migrationId: 'prev-run' },
    })) as { alreadyCompleted: boolean };

    expect(result.alreadyCompleted).toBe(true);
    expect(mockSetCustomUserClaims).not.toHaveBeenCalled();
  });
});

describe('verifyMigration', () => {
  const handler = verifyMigration as unknown as Handler;
  const platformAdmin = { auth: { uid: 'pa', token: { role: 'platformAdmin' } } };

  beforeEach(() => {
    mockGet.mockReset();
    mockGetUser.mockReset();
  });

  it('미인증 요청은 unauthenticated', async () => {
    await expect(handler({ data: {} })).rejects.toMatchObject({
      code: 'unauthenticated',
    });
  });

  it('non-platformAdmin 호출자는 permission-denied', async () => {
    await expect(
      handler({ auth: { uid: 'a', token: { role: 'admin' } }, data: {} }),
    ).rejects.toMatchObject({ code: 'permission-denied' });
  });

  it('모든 활성 유저가 role claim 보유 시 ready=true', async () => {
    mockGet.mockResolvedValueOnce({
      val: () => ({
        u1: { role: 'patient', status: 'active' },
        u2: { role: 'staff', hospitalId: 'smch', status: 'active' },
      }),
    });
    mockGetUser
      .mockResolvedValueOnce({ customClaims: { role: 'patient' } })
      .mockResolvedValueOnce({ customClaims: { role: 'staff' } });

    const result = (await handler({ ...platformAdmin, data: {} })) as {
      totalActive: number;
      withRoleClaim: number;
      missingRoleClaim: number;
      ready: boolean;
    };
    expect(result.totalActive).toBe(2);
    expect(result.withRoleClaim).toBe(2);
    expect(result.missingRoleClaim).toBe(0);
    expect(result.ready).toBe(true);
  });

  it('claim 누락 유저 있으면 ready=false + sample uid 반환', async () => {
    mockGet.mockResolvedValueOnce({
      val: () => ({
        u1: { role: 'patient', status: 'active' },
        u2: { role: 'staff', status: 'active' },
      }),
    });
    mockGetUser
      .mockResolvedValueOnce({ customClaims: { role: 'patient' } })
      .mockResolvedValueOnce({ customClaims: null });

    const result = (await handler({ ...platformAdmin, data: {} })) as {
      missingRoleClaim: number;
      sampleMissingUids: string[];
      ready: boolean;
    };
    expect(result.missingRoleClaim).toBe(1);
    expect(result.sampleMissingUids).toEqual(['u2']);
    expect(result.ready).toBe(false);
  });

  it('claim.role과 RTDB.role 불일치 감지', async () => {
    mockGet.mockResolvedValueOnce({
      val: () => ({ u1: { role: 'staff', status: 'active' } }),
    });
    mockGetUser.mockResolvedValueOnce({ customClaims: { role: 'patient' } });

    const result = (await handler({ ...platformAdmin, data: {} })) as {
      mismatchUids: Array<{ uid: string; rtdbRole: string; claimRole: string }>;
      ready: boolean;
    };
    expect(result.mismatchUids).toEqual([
      { uid: 'u1', rtdbRole: 'staff', claimRole: 'patient' },
    ]);
    expect(result.ready).toBe(true); // claim은 있으므로 ready=true, 불일치는 별도 수동 조치
  });

  it('비활성 유저는 카운트·조회 모두 skip', async () => {
    mockGet.mockResolvedValueOnce({
      val: () => ({
        u1: { role: 'patient', status: 'deleted' },
        u2: { role: 'staff', status: 'active' },
      }),
    });
    mockGetUser.mockResolvedValueOnce({ customClaims: { role: 'staff' } });

    const result = (await handler({ ...platformAdmin, data: {} })) as {
      totalActive: number;
      withRoleClaim: number;
    };
    expect(result.totalActive).toBe(1);
    expect(result.withRoleClaim).toBe(1);
    expect(mockGetUser).toHaveBeenCalledTimes(1);
  });
});
