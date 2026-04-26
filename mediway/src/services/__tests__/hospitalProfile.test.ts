import { describe, it, expect, beforeEach, vi } from 'vitest';

const mockOnValue = vi.fn();
const mockRef = vi.fn((_db: unknown, path?: string) =>
  path === undefined ? { __root: true } : { __path: path },
);

vi.mock('firebase/database', () => ({
  onValue: (...args: unknown[]) => mockOnValue(...args),
  ref: (...args: unknown[]) =>
    args.length <= 1 ? mockRef(args[0]) : mockRef(args[0], args[1] as string),
}));

vi.mock('@/config/firebase', () => ({
  db: { __mocked: true },
  isFirebaseConfigured: () => true,
}));

import {
  subscribeHospitalProfile,
  resolveThemeColor,
} from '../hospitalProfile';

describe('subscribeHospitalProfile', () => {
  beforeEach(() => {
    mockOnValue.mockReset();
    mockRef.mockClear();
  });

  function triggerData(snap: { exists: boolean; val: unknown }) {
    const cb = mockOnValue.mock.calls[0][1] as (s: {
      exists: () => boolean;
      val: () => unknown;
    }) => void;
    cb({ exists: () => snap.exists, val: () => snap.val });
  }

  function triggerError(err: Error) {
    const cb = mockOnValue.mock.calls[0][2] as (e: Error) => void;
    cb(err);
  }

  it('경로: hospitals/{slug}/profile', () => {
    subscribeHospitalProfile('demo', vi.fn());
    expect(mockRef).toHaveBeenCalledWith(expect.anything(), 'hospitals/demo/profile');
  });

  it('snapshot 미존재 → null', () => {
    const onData = vi.fn();
    subscribeHospitalProfile('demo', onData);
    triggerData({ exists: false, val: null });
    expect(onData).toHaveBeenCalledWith(null);
  });

  it('snapshot 존재 → HospitalProfile 그대로 전달', () => {
    const onData = vi.fn();
    subscribeHospitalProfile('demo', onData);
    triggerData({
      exists: true,
      val: {
        id: 'demo',
        name: 'MediWay 데모 병원',
        themeColor: '#004e9f',
        status: 'active',
      },
    });
    expect(onData).toHaveBeenCalledWith({
      id: 'demo',
      name: 'MediWay 데모 병원',
      themeColor: '#004e9f',
      status: 'active',
    });
  });

  it('id/name 누락 시 slug 로 보강', () => {
    const onData = vi.fn();
    subscribeHospitalProfile('legacy', onData);
    triggerData({
      exists: true,
      val: { themeColor: '#004e9f' },
    });
    const arg = onData.mock.calls[0][0];
    expect(arg.id).toBe('legacy');
    expect(arg.name).toBe('legacy');
    expect(arg.themeColor).toBe('#004e9f');
  });

  it('val()이 null 이면 onData(null)', () => {
    const onData = vi.fn();
    subscribeHospitalProfile('demo', onData);
    triggerData({ exists: true, val: null });
    expect(onData).toHaveBeenCalledWith(null);
  });

  it('에러 콜백 전파', () => {
    const onError = vi.fn();
    subscribeHospitalProfile('demo', vi.fn(), onError);
    const err = new Error('PERMISSION_DENIED');
    triggerError(err);
    expect(onError).toHaveBeenCalledWith(err);
  });

  it('빈 slug → 즉시 null + no-op unsubscribe', () => {
    const onData = vi.fn();
    const unsub = subscribeHospitalProfile('', onData);
    expect(onData).toHaveBeenCalledWith(null);
    expect(mockOnValue).not.toHaveBeenCalled();
    expect(typeof unsub).toBe('function');
    // 호출해도 throw 없음
    unsub();
  });

  it('suspended 상태도 그대로 전달 (분기는 컨슈머 책임)', () => {
    const onData = vi.fn();
    subscribeHospitalProfile('demo', onData);
    triggerData({
      exists: true,
      val: { id: 'demo', name: 'X', status: 'suspended' },
    });
    const arg = onData.mock.calls[0][0];
    expect(arg.status).toBe('suspended');
  });
});

describe('resolveThemeColor', () => {
  it('정상 #RRGGBB → 그대로', () => {
    expect(resolveThemeColor('#004e9f')).toBe('#004e9f');
    expect(resolveThemeColor('#A1B2C3')).toBe('#A1B2C3');
  });

  it('null/undefined → fallback', () => {
    expect(resolveThemeColor(null)).toBe('#004e9f');
    expect(resolveThemeColor(undefined)).toBe('#004e9f');
  });

  it('빈 문자열 → fallback', () => {
    expect(resolveThemeColor('')).toBe('#004e9f');
  });

  it('잘못된 형식 → fallback', () => {
    expect(resolveThemeColor('blue')).toBe('#004e9f');
    expect(resolveThemeColor('#deadbe')).toBe('#deadbe'); // 6자리 hex 라 통과
    expect(resolveThemeColor('#abc')).toBe('#004e9f'); // 3자리는 거절
    expect(resolveThemeColor('rgb(0,0,0)')).toBe('#004e9f');
    expect(resolveThemeColor('#1234567')).toBe('#004e9f'); // 7자리 거절
  });
});
