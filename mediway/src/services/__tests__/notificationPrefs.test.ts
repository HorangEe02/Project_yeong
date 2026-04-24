import { describe, it, expect, beforeEach, vi } from 'vitest';

const mockOnValue = vi.fn();
const mockUpdate = vi.fn();
const mockRef = vi.fn((_db: unknown, path?: string) =>
  path === undefined ? { __root: true } : { __path: path },
);

vi.mock('firebase/database', () => ({
  onValue: (...args: unknown[]) => mockOnValue(...args),
  ref: (...args: unknown[]) =>
    args.length <= 1 ? mockRef(args[0]) : mockRef(args[0], args[1] as string),
  update: (...args: unknown[]) => mockUpdate(...args),
}));

vi.mock('@/config/firebase', () => ({
  db: { __mocked: true },
  isFirebaseConfigured: () => true,
}));

import {
  restoreNotifications,
  revokeAllNotifications,
  setNotificationChannel,
  setNotificationScenario,
  subscribeNotificationPrefs,
} from '../notificationPrefs';
import { isChannelEnabled } from '@/types/notificationPrefs';

describe('subscribeNotificationPrefs', () => {
  beforeEach(() => {
    mockOnValue.mockReset();
    mockRef.mockClear();
  });

  function trigger(val: unknown) {
    const cb = mockOnValue.mock.calls[0][1] as (snap: { val: () => unknown }) => void;
    cb({ val: () => val });
  }

  it('경로: users/{uid}/notifications', () => {
    subscribeNotificationPrefs('uid-1', vi.fn());
    expect(mockRef).toHaveBeenCalledWith(expect.anything(), 'users/uid-1/notifications');
  });

  it('null snapshot → 빈 객체', () => {
    const onData = vi.fn();
    subscribeNotificationPrefs('uid-1', onData);
    trigger(null);
    expect(onData).toHaveBeenCalledWith({});
  });

  it('값 통과', () => {
    const onData = vi.fn();
    subscribeNotificationPrefs('uid-1', onData);
    const prefs = { channels: { fcm: false }, updatedAt: 100 };
    trigger(prefs);
    expect(onData).toHaveBeenCalledWith(prefs);
  });

  it('에러 전파', () => {
    const onError = vi.fn();
    subscribeNotificationPrefs('uid-1', vi.fn(), onError);
    const errCb = mockOnValue.mock.calls[0][2] as (err: Error) => void;
    const e = new Error('denied');
    errCb(e);
    expect(onError).toHaveBeenCalledWith(e);
  });
});

describe('setNotificationChannel', () => {
  beforeEach(() => {
    mockUpdate.mockReset();
    mockRef.mockClear();
    mockUpdate.mockResolvedValue(undefined);
  });

  it('users/{uid}/notifications 에 channels/{ch} + updatedAt 부분 업데이트', async () => {
    await setNotificationChannel('uid-1', 'fcm', false);
    expect(mockRef).toHaveBeenCalledWith(expect.anything(), 'users/uid-1/notifications');
    const payload = mockUpdate.mock.calls[0][1];
    expect(payload['channels/fcm']).toBe(false);
    expect(typeof payload.updatedAt).toBe('number');
  });
});

describe('setNotificationScenario', () => {
  beforeEach(() => {
    mockUpdate.mockReset();
    mockUpdate.mockResolvedValue(undefined);
  });

  it('scenarios/{eventType} + updatedAt', async () => {
    await setNotificationScenario('uid-1', 'queue.call', true);
    const payload = mockUpdate.mock.calls[0][1];
    expect(payload['scenarios/queue.call']).toBe(true);
    expect(typeof payload.updatedAt).toBe('number');
  });
});

describe('revokeAllNotifications / restore', () => {
  beforeEach(() => {
    mockUpdate.mockReset();
    mockUpdate.mockResolvedValue(undefined);
  });

  it('revoke → revokedAt=number + updatedAt', async () => {
    await revokeAllNotifications('uid-1');
    const payload = mockUpdate.mock.calls[0][1];
    expect(typeof payload.revokedAt).toBe('number');
    expect(typeof payload.updatedAt).toBe('number');
  });

  it('restore → revokedAt=null + updatedAt', async () => {
    await restoreNotifications('uid-1');
    const payload = mockUpdate.mock.calls[0][1];
    expect(payload.revokedAt).toBeNull();
    expect(typeof payload.updatedAt).toBe('number');
  });
});

describe('isChannelEnabled (client-side pref 해석)', () => {
  it('비어있으면 모두 허용', () => {
    expect(isChannelEnabled({}, 'fcm', 'queue.call')).toBe(true);
  });
  it('revokedAt 설정 시 전체 block', () => {
    expect(isChannelEnabled({ revokedAt: 1 }, 'fcm', 'queue.call')).toBe(false);
  });
  it('channels.fcm=false 만 block', () => {
    expect(isChannelEnabled({ channels: { fcm: false } }, 'fcm', 'queue.call')).toBe(false);
    expect(isChannelEnabled({ channels: { fcm: false } }, 'sms', 'queue.call')).toBe(true);
  });
  it('scenarios 만 block 시 해당 시나리오 전 channel 차단', () => {
    expect(
      isChannelEnabled({ scenarios: { 'queue.call': false } }, 'fcm', 'queue.call'),
    ).toBe(false);
    expect(
      isChannelEnabled({ scenarios: { 'queue.call': false } }, 'fcm', 'appointment.confirmed'),
    ).toBe(true);
  });
});
