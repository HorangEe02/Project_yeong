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

import { setUiSenior, subscribeUserPreferences } from '../preferences';

describe('subscribeUserPreferences', () => {
  beforeEach(() => {
    mockOnValue.mockReset();
    mockRef.mockClear();
  });

  function trigger(val: unknown) {
    const cb = mockOnValue.mock.calls[0][1] as (snap: { val: () => unknown }) => void;
    cb({ val: () => val });
  }

  it('경로: users/{uid}/preferences', () => {
    subscribeUserPreferences('uid-1', vi.fn());
    expect(mockRef).toHaveBeenCalledWith(expect.anything(), 'users/uid-1/preferences');
  });

  it('null snapshot → 빈 객체', () => {
    const onData = vi.fn();
    subscribeUserPreferences('uid-1', onData);
    trigger(null);
    expect(onData).toHaveBeenCalledWith({});
  });

  it('값이 있으면 그대로 전달', () => {
    const onData = vi.fn();
    subscribeUserPreferences('uid-1', onData);
    trigger({ uiSenior: true });
    expect(onData).toHaveBeenCalledWith({ uiSenior: true });
  });

  it('에러 전파', () => {
    const onError = vi.fn();
    subscribeUserPreferences('uid-1', vi.fn(), onError);
    const cb = mockOnValue.mock.calls[0][2] as (err: Error) => void;
    cb(new Error('denied'));
    expect(onError).toHaveBeenCalled();
  });
});

describe('setUiSenior', () => {
  beforeEach(() => {
    mockUpdate.mockReset();
    mockRef.mockClear();
    mockUpdate.mockResolvedValue(undefined);
  });

  it('users/{uid} 에 preferences/uiSenior 필드 부분 업데이트', async () => {
    await setUiSenior('uid-42', true);
    expect(mockRef).toHaveBeenCalledWith(expect.anything(), 'users/uid-42');
    const payload = mockUpdate.mock.calls[0][1];
    expect(payload).toEqual({ 'preferences/uiSenior': true });
  });

  it('false 값도 전달', async () => {
    await setUiSenior('uid-42', false);
    const payload = mockUpdate.mock.calls[0][1];
    expect(payload['preferences/uiSenior']).toBe(false);
  });
});
