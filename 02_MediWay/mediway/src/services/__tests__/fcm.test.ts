import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

const requestPermissionMock = vi.fn();
const getMessagingInstanceMock = vi.fn();
const getTokenMock = vi.fn();
const setMock = vi.fn();

vi.mock('@/config/firebase', () => ({
  db: {},
  isFirebaseConfigured: () => true,
  getMessagingInstance: () => getMessagingInstanceMock(),
}));

vi.mock('firebase/database', () => ({
  ref: (_db: unknown, path: string) => ({ path }),
  set: (r: { path: string }, value: unknown) => setMock(r.path, value),
}));

vi.mock('firebase/messaging', () => ({
  getToken: (_m: unknown, opts: { vapidKey: string }) => getTokenMock(opts),
}));

import { fcmTokenId, registerFcmToken } from '../fcm';

const originalNotification = (globalThis as Record<string, unknown>).Notification;

beforeEach(() => {
  requestPermissionMock.mockReset();
  getMessagingInstanceMock.mockReset();
  getTokenMock.mockReset();
  setMock.mockReset();

  (globalThis as Record<string, unknown>).Notification = {
    requestPermission: requestPermissionMock,
  };
});

afterEach(() => {
  (globalThis as Record<string, unknown>).Notification = originalNotification;
});

describe('fcmTokenId', () => {
  it('마지막 20자 + 비허용 문자 _ 치환', () => {
    const token = 'aa/bb+cc=dd-ee_ff.gg:hh?ii jj';
    const id = fcmTokenId(token);
    expect(id.length).toBe(20);
    expect(id).not.toMatch(/[^a-zA-Z0-9_-]/);
  });

  it('짧은 토큰은 전체 사용 (sanitize)', () => {
    expect(fcmTokenId('abc/def')).toBe('abc_def');
  });
});

describe('registerFcmToken', () => {
  it('Notification 미지원 브라우저 → null', async () => {
    delete (globalThis as Record<string, unknown>).Notification;
    const r = await registerFcmToken('uid-a', 'vapid-x');
    expect(r).toBeNull();
  });

  it('권한 거부 → null + getToken 미호출', async () => {
    requestPermissionMock.mockResolvedValueOnce('denied');
    const r = await registerFcmToken('uid-a', 'vapid-x');
    expect(r).toBeNull();
    expect(getTokenMock).not.toHaveBeenCalled();
  });

  it('messaging 미지원(null) → null', async () => {
    requestPermissionMock.mockResolvedValueOnce('granted');
    getMessagingInstanceMock.mockResolvedValueOnce(null);
    const r = await registerFcmToken('uid-a', 'vapid-x');
    expect(r).toBeNull();
    expect(getTokenMock).not.toHaveBeenCalled();
  });

  it('VAPID key 미설정 → null', async () => {
    requestPermissionMock.mockResolvedValueOnce('granted');
    getMessagingInstanceMock.mockResolvedValueOnce({});
    const r = await registerFcmToken('uid-a', '');
    expect(r).toBeNull();
    expect(getTokenMock).not.toHaveBeenCalled();
  });

  it('정상 — getToken 호출 + set 호출 + 토큰 반환', async () => {
    requestPermissionMock.mockResolvedValueOnce('granted');
    getMessagingInstanceMock.mockResolvedValueOnce({});
    const fake = 'abcdefghijklmnopqrstuvwxyz0123456789abcdefghij';
    getTokenMock.mockResolvedValueOnce(fake);
    setMock.mockResolvedValueOnce(undefined);

    const r = await registerFcmToken('uid-a', 'vapid-real');
    expect(r).toBe(fake);
    expect(getTokenMock).toHaveBeenCalledWith({ vapidKey: 'vapid-real' });
    const [path, value] = setMock.mock.calls[0] as [string, Record<string, unknown>];
    expect(path).toBe(`user_fcm_tokens/uid-a/${fcmTokenId(fake)}`);
    expect(value.token).toBe(fake);
    expect(value.createdAt).toBeTypeOf('number');
  });

  it('getToken null → null', async () => {
    requestPermissionMock.mockResolvedValueOnce('granted');
    getMessagingInstanceMock.mockResolvedValueOnce({});
    getTokenMock.mockResolvedValueOnce(null);
    const r = await registerFcmToken('uid-a', 'vapid-real');
    expect(r).toBeNull();
    expect(setMock).not.toHaveBeenCalled();
  });

  it('getToken throw → null (swallow)', async () => {
    requestPermissionMock.mockResolvedValueOnce('granted');
    getMessagingInstanceMock.mockResolvedValueOnce({});
    getTokenMock.mockRejectedValueOnce(new Error('boom'));
    const errSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    const r = await registerFcmToken('uid-a', 'vapid-real');
    expect(r).toBeNull();
    errSpy.mockRestore();
  });
});
