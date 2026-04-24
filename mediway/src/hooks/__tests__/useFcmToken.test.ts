import { describe, it, expect, beforeEach, vi } from 'vitest';

const mockSet = vi.fn();
const mockRef = vi.fn((_db: unknown, path: string) => ({ __path: path }));
const mockServerTimestamp = vi.fn(() => ({ '.sv': 'timestamp' }));

vi.mock('firebase/database', () => ({
  ref: (...args: unknown[]) => mockRef(args[0], args[1] as string),
  serverTimestamp: () => mockServerTimestamp(),
  set: (...args: unknown[]) => mockSet(...args),
}));

vi.mock('@/config/firebase', () => ({
  db: { __mocked: true },
  isFirebaseConfigured: () => true,
}));

vi.mock('@/services/notification', () => ({
  requestNotificationPermission: vi.fn(),
}));

vi.mock('@/stores/authStore', () => ({
  useAuthStore: () => null,
}));

import { hashTokenKey, persistFcmToken, __resetFcmTokenCache } from '../useFcmToken';

describe('hashTokenKey', () => {
  it('deterministic — 같은 입력 → 같은 출력', () => {
    const a = hashTokenKey('abc123:APA91bF');
    const b = hashTokenKey('abc123:APA91bF');
    expect(a).toBe(b);
  });

  it('정확히 8자 lowercase hex', () => {
    const h = hashTokenKey('some-fcm-token-string');
    expect(h).toMatch(/^[0-9a-f]{8}$/);
  });

  it('다른 토큰은 다른 key 생성 (충돌 확률 무시)', () => {
    const a = hashTokenKey('token-one');
    const b = hashTokenKey('token-two');
    expect(a).not.toBe(b);
  });

  it('빈 문자열도 안전하게 처리', () => {
    const h = hashTokenKey('');
    expect(h).toMatch(/^[0-9a-f]{8}$/);
  });
});

describe('persistFcmToken', () => {
  beforeEach(() => {
    mockSet.mockReset();
    mockRef.mockClear();
    mockServerTimestamp.mockClear();
    __resetFcmTokenCache();
    mockSet.mockResolvedValue(undefined);
  });

  it('/user_fcm_tokens/{uid}/{hash} 경로에 { token, createdAt } 저장', async () => {
    const uid = 'uid-xyz';
    const token = 'fcm-token-value-123';
    const expectedKey = hashTokenKey(token);

    const returnedKey = await persistFcmToken(uid, token);

    expect(returnedKey).toBe(expectedKey);
    expect(mockRef).toHaveBeenCalledWith(
      expect.anything(),
      `user_fcm_tokens/${uid}/${expectedKey}`,
    );
    expect(mockSet).toHaveBeenCalledTimes(1);
    const payload = mockSet.mock.calls[0][1];
    expect(payload.token).toBe(token);
    expect(payload.createdAt).toEqual({ '.sv': 'timestamp' });
  });

  it('동일 (uid, token) 재호출 시 network 호출 skip', async () => {
    const uid = 'uid-1';
    const token = 'same-token';

    await persistFcmToken(uid, token);
    await persistFcmToken(uid, token);

    expect(mockSet).toHaveBeenCalledTimes(1);
  });

  it('다른 uid 또는 다른 token이면 별도 저장', async () => {
    await persistFcmToken('uid-a', 'tok-1');
    await persistFcmToken('uid-a', 'tok-2');
    await persistFcmToken('uid-b', 'tok-1');

    expect(mockSet).toHaveBeenCalledTimes(3);
  });
});
