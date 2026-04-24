import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('@/config/firebase', () => ({
  db: {} as object,
  isFirebaseConfigured: () => true,
}));

const getMock = vi.fn();
const runTransactionMock = vi.fn();
vi.mock('firebase/database', () => ({
  ref: (_db: unknown, path: string) => ({ path }),
  get: (r: { path: string }) => getMock(r.path),
  runTransaction: (r: { path: string }, updater: (v: unknown) => unknown) =>
    runTransactionMock(r.path, updater),
}));

import { validateStaffCode, consumeStaffCode } from '../staffCode';
import type { StaffCode } from '@/types/staff-code';

const baseCode: StaffCode = {
  code: 'DEMO01',
  hospitalId: 'h1',
  department: '내과',
  expiresAt: Date.now() + 86_400_000,
  usedBy: null,
  createdAt: Date.now(),
};

beforeEach(() => {
  getMock.mockReset();
  runTransactionMock.mockReset();
});

describe('validateStaffCode', () => {
  it('존재하지 않는 코드', async () => {
    getMock.mockResolvedValueOnce({ exists: () => false });
    const res = await validateStaffCode('NOPE');
    expect(res).toEqual({ valid: false, reason: 'not_found' });
  });

  it('이미 사용된 코드', async () => {
    getMock.mockResolvedValueOnce({
      exists: () => true,
      val: () => ({ ...baseCode, usedBy: 'uid-xyz' }),
    });
    const res = await validateStaffCode('DEMO01');
    expect(res).toEqual({ valid: false, reason: 'already_used' });
  });

  it('만료된 코드', async () => {
    getMock.mockResolvedValueOnce({
      exists: () => true,
      val: () => ({ ...baseCode, expiresAt: Date.now() - 1 }),
    });
    const res = await validateStaffCode('DEMO01');
    expect(res).toEqual({ valid: false, reason: 'expired' });
  });

  it('유효한 코드는 valid:true 반환', async () => {
    getMock.mockResolvedValueOnce({
      exists: () => true,
      val: () => baseCode,
    });
    const res = await validateStaffCode('demo01');
    expect(res.valid).toBe(true);
    if (res.valid) expect(res.code.department).toBe('내과');
  });

  it('코드 입력은 대문자로 정규화된다', async () => {
    getMock.mockResolvedValueOnce({ exists: () => false });
    await validateStaffCode(' demo01 ');
    expect(getMock).toHaveBeenCalledWith('staff_codes/DEMO01');
  });
});

describe('consumeStaffCode', () => {
  it('유효 코드를 사용 처리하면 usedBy·usedAt이 설정된다', async () => {
    runTransactionMock.mockImplementationOnce(async (_path, updater) => {
      const updated = updater(baseCode);
      return {
        committed: true,
        snapshot: { exists: () => true, val: () => updated },
      };
    });
    const result = await consumeStaffCode('DEMO01', 'uid-abc');
    expect(result.usedBy).toBe('uid-abc');
    expect(result.usedAt).toBeTypeOf('number');
  });

  it('이미 사용된 코드는 트랜잭션 abort → throw', async () => {
    runTransactionMock.mockImplementationOnce(async (_path, updater) => {
      const abort = updater({ ...baseCode, usedBy: 'someone' });
      return {
        committed: abort !== undefined,
        snapshot: { exists: () => true, val: () => baseCode },
      };
    });
    await expect(consumeStaffCode('DEMO01', 'u')).rejects.toThrow();
  });
});
