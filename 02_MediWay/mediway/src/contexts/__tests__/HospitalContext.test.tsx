import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, render, act } from '@testing-library/react';
import { type ReactNode } from 'react';

// 구독 함수는 컨텍스트가 의존하는 외부 경계 — mock
const subscribeMock = vi.fn();
vi.mock('@/services/hospitals', () => ({
  subscribeHospitalProfile: (
    slug: string,
    onChange: (p: unknown) => void,
    onError?: (e: Error) => void,
  ) => subscribeMock(slug, onChange, onError),
}));

import {
  HospitalProvider,
  useHospital,
  useHospitalFeature,
} from '../HospitalContext';
import {
  DEFAULT_HOSPITAL_FEATURES,
  type HospitalProfile,
} from '@/types/hospital';

const demoProfile: HospitalProfile = {
  name: 'Demo',
  slug: 'demo',
  themeColor: '#004e9f',
  contractStatus: 'active',
  features: { ...DEFAULT_HOSPITAL_FEATURES, appointments: true },
  createdAt: 1,
  updatedAt: 1,
};

beforeEach(() => {
  subscribeMock.mockReset();
});

function wrap(slug: string | null) {
  return ({ children }: { children: ReactNode }) => (
    <HospitalProvider slug={slug}>{children}</HospitalProvider>
  );
}

describe('HospitalProvider + useHospital', () => {
  it('slug null이면 로딩·에러 없이 빈 상태', () => {
    const { result } = renderHook(() => useHospital(), { wrapper: wrap(null) });
    expect(result.current.slug).toBeNull();
    expect(result.current.hospital).toBeNull();
    expect(result.current.loading).toBe(false);
  });

  it('slug 주입 시 구독 호출 + 초기 loading=true', () => {
    subscribeMock.mockImplementation(() => () => {});
    const { result } = renderHook(() => useHospital(), {
      wrapper: wrap('demo'),
    });
    expect(subscribeMock).toHaveBeenCalledWith(
      'demo',
      expect.any(Function),
      expect.any(Function),
    );
    expect(result.current.loading).toBe(true);
    expect(result.current.slug).toBe('demo');
  });

  it('구독 콜백 profile 반영 + loading 종료', () => {
    let capturedCb: ((p: HospitalProfile | null) => void) | null = null;
    subscribeMock.mockImplementation((_slug, cb) => {
      capturedCb = cb;
      return () => {};
    });
    const { result } = renderHook(() => useHospital(), {
      wrapper: wrap('demo'),
    });
    act(() => {
      capturedCb!(demoProfile);
    });
    expect(result.current.hospital).toEqual(demoProfile);
    expect(result.current.loading).toBe(false);
    expect(result.current.notFound).toBe(false);
  });

  it('프로필 null이면 notFound=true', () => {
    let capturedCb: ((p: HospitalProfile | null) => void) | null = null;
    subscribeMock.mockImplementation((_slug, cb) => {
      capturedCb = cb;
      return () => {};
    });
    const { result } = renderHook(() => useHospital(), {
      wrapper: wrap('ghost'),
    });
    act(() => capturedCb!(null));
    expect(result.current.notFound).toBe(true);
    expect(result.current.hospital).toBeNull();
  });

  it('unmount 시 구독 해제', () => {
    const unsubMock = vi.fn();
    subscribeMock.mockImplementation(() => unsubMock);
    const { unmount } = renderHook(() => useHospital(), {
      wrapper: wrap('demo'),
    });
    unmount();
    expect(unsubMock).toHaveBeenCalled();
  });

  it('slug 변경 시 이전 구독 해제 + 새 구독 발생', () => {
    const unsubscribes: string[] = [];
    let callIndex = 0;
    subscribeMock.mockImplementation((slug: string) => {
      const myIndex = callIndex++;
      return () => unsubscribes.push(`unsub-${myIndex}-${slug}`);
    });

    function HookReader() {
      useHospital();
      return null;
    }

    const { rerender } = render(
      <HospitalProvider slug="demo">
        <HookReader />
      </HospitalProvider>,
    );
    rerender(
      <HospitalProvider slug="smch">
        <HookReader />
      </HospitalProvider>,
    );
    expect(unsubscribes).toContain('unsub-0-demo');
    expect(subscribeMock).toHaveBeenLastCalledWith(
      'smch',
      expect.any(Function),
      expect.any(Function),
    );
  });

  it('구독 에러 콜백 시 error 상태 설정', () => {
    let capturedErr: ((e: Error) => void) | null = null;
    subscribeMock.mockImplementation((_slug, _cb, err) => {
      capturedErr = err;
      return () => {};
    });
    const { result } = renderHook(() => useHospital(), {
      wrapper: wrap('demo'),
    });
    const e = new Error('permission denied');
    act(() => capturedErr!(e));
    expect(result.current.error).toBe(e);
    expect(result.current.loading).toBe(false);
  });
});

describe('useHospitalFeature', () => {
  it('feature 활성 상태 반영', () => {
    let capturedCb: ((p: HospitalProfile | null) => void) | null = null;
    subscribeMock.mockImplementation((_slug, cb) => {
      capturedCb = cb;
      return () => {};
    });
    const { result } = renderHook(
      () => ({
        appointments: useHospitalFeature('appointments'),
        payment: useHospitalFeature('payment'),
      }),
      { wrapper: wrap('demo') },
    );
    act(() => capturedCb!(demoProfile));
    expect(result.current.appointments).toBe(true);
    expect(result.current.payment).toBe(false);
  });

  it('병원 미선택 시 모두 false', () => {
    const { result } = renderHook(() => useHospitalFeature('appointments'), {
      wrapper: wrap(null),
    });
    expect(result.current).toBe(false);
  });
});
