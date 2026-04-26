import { describe, it, expect, beforeEach, vi } from 'vitest';

// --- mocks ---

const mockSet = vi.fn();
const mockRunTransaction = vi.fn();
const mockRef = vi.fn((_db: unknown, path?: string) =>
  path === undefined ? { __root: true } : { __path: path },
);

vi.mock('firebase/database', () => ({
  ref: (...args: unknown[]) =>
    args.length <= 1 ? mockRef(args[0]) : mockRef(args[0], args[1] as string),
  set: (...args: unknown[]) => mockSet(...args),
  runTransaction: (...args: unknown[]) => mockRunTransaction(...args),
}));

vi.mock('@/config/firebase', () => ({
  db: { __mocked: true },
  isFirebaseConfigured: () => true,
}));

import {
  issueSelfQRToken,
  QRTokenRateLimitError,
  QR_TOKEN_LIMIT_PER_HOUR,
} from '../qrToken';

beforeEach(() => {
  mockSet.mockReset();
  mockRunTransaction.mockReset();
  mockRef.mockClear();
  mockSet.mockResolvedValue(undefined);
});

/** transaction mock — committed: true / next: number */
function mockTxCommitted(nextValue: number) {
  mockRunTransaction.mockResolvedValueOnce({
    committed: true,
    snapshot: { val: () => nextValue },
  });
}
function mockTxAborted() {
  mockRunTransaction.mockResolvedValueOnce({
    committed: false,
    snapshot: { val: () => null },
  });
}

describe('issueSelfQRToken — 정상 흐름', () => {
  it('rate-limit 통과 + qr_tokens/{token} set 수행', async () => {
    mockTxCommitted(5);
    const now = 1_700_000_000_000; // arbitrary
    await issueSelfQRToken('token-abc', 'uid-1', now);

    // transaction 한 번 호출 (qr_token_usage)
    expect(mockRunTransaction).toHaveBeenCalledTimes(1);
    const txPath = (mockRef.mock.calls[0][1] as string) || '';
    expect(txPath).toMatch(/^qr_token_usage\/uid-1\/\d+$/);

    // qr_tokens/{token} set 호출
    expect(mockSet).toHaveBeenCalledTimes(1);
    const tokenPath = (mockSet.mock.calls[0][0] as { __path?: string }).__path;
    expect(tokenPath).toBe('qr_tokens/token-abc');
    const payload = mockSet.mock.calls[0][1];
    expect(payload).toEqual({
      patientUid: 'uid-1',
      status: 'waiting',
      createdAt: now,
    });
  });

  it('현재 epochHour 사용 — 1시간 경계 정확', async () => {
    mockTxCommitted(1);
    const now = 1_700_003_600_000; // 1 hour later
    await issueSelfQRToken('t', 'u', now);
    const txPath = (mockRef.mock.calls[0][1] as string) || '';
    const expectedHour = Math.floor(now / 3_600_000);
    expect(txPath).toBe(`qr_token_usage/u/${expectedHour}`);
  });
});

describe('issueSelfQRToken — transaction 함수 동작', () => {
  it('transaction 함수가 cur=null 일 때 1 반환', async () => {
    let txFn: (cur: unknown) => unknown = () => undefined;
    mockRunTransaction.mockImplementationOnce((_ref, fn) => {
      txFn = fn;
      return Promise.resolve({
        committed: true,
        snapshot: { val: () => 1 },
      });
    });
    await issueSelfQRToken('t', 'u', 0);
    expect(txFn(null)).toBe(1);
  });

  it('transaction 함수가 cur=29 일 때 30 반환 (cap 도달 직전)', async () => {
    let txFn: (cur: unknown) => unknown = () => undefined;
    mockRunTransaction.mockImplementationOnce((_ref, fn) => {
      txFn = fn;
      return Promise.resolve({
        committed: true,
        snapshot: { val: () => 30 },
      });
    });
    await issueSelfQRToken('t', 'u', 0);
    expect(txFn(29)).toBe(30);
  });

  it('transaction 함수가 cur=30 일 때 undefined 반환 (abort)', async () => {
    let txFn: (cur: unknown) => unknown = () => undefined;
    mockRunTransaction.mockImplementationOnce((_ref, fn) => {
      txFn = fn;
      return Promise.resolve({
        committed: false,
        snapshot: { val: () => null },
      });
    });
    await expect(issueSelfQRToken('t', 'u', 0)).rejects.toThrow(QRTokenRateLimitError);
    expect(txFn(30)).toBeUndefined();
  });
});

describe('issueSelfQRToken — rate limit', () => {
  it('transaction abort → QRTokenRateLimitError + qr_tokens 미작성', async () => {
    mockTxAborted();
    await expect(issueSelfQRToken('t', 'u', 0)).rejects.toBeInstanceOf(
      QRTokenRateLimitError,
    );
    expect(mockSet).not.toHaveBeenCalled();
  });

  it('retryAfterSeconds 가 다음 정시까지 양수', async () => {
    mockTxAborted();
    // now 가 hour 의 30분 시점 → 30분 = 1800초
    const now = 1_700_001_800_000; // 임의: hour boundary 후 1800초
    const err = await issueSelfQRToken('t', 'u', now).catch((e) => e);
    expect(err).toBeInstanceOf(QRTokenRateLimitError);
    expect(err.retryAfterSeconds).toBeGreaterThan(0);
    expect(err.retryAfterSeconds).toBeLessThanOrEqual(3600);
  });
});

describe('issueSelfQRToken — Firebase 미설정', () => {
  it('isFirebaseConfigured()=false → no-op (transaction / set 호출 0)', async () => {
    vi.resetModules();
    vi.doMock('@/config/firebase', () => ({
      db: { __mocked: true },
      isFirebaseConfigured: () => false,
    }));
    const { issueSelfQRToken: fn } = await import('../qrToken');
    await fn('t', 'u', 0);
    expect(mockRunTransaction).not.toHaveBeenCalled();
    expect(mockSet).not.toHaveBeenCalled();
    vi.doUnmock('@/config/firebase');
  });
});

describe('QR_TOKEN_LIMIT_PER_HOUR', () => {
  it('상수 값 = 30', () => {
    expect(QR_TOKEN_LIMIT_PER_HOUR).toBe(30);
  });
});
