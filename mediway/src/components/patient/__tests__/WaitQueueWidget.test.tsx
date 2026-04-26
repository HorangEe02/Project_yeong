import { describe, it, expect, beforeEach, vi } from 'vitest';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useSearchParams } from 'react-router-dom';
import type { HospitalProfile } from '@/types/hospital';
import type { WaitQueuePatientIndex } from '@/types/waitQueue';

// --- Mocks ---

type Cb = (rows: WaitQueuePatientIndex[]) => void;
type ErrCb = (err: Error) => void;

let lastCb: Cb | null = null;
let lastErrCb: ErrCb | null = null;
const mockUnsub = vi.fn();
const mockSubscribe = vi.fn(
  (_slug: string, _uid: string, onData: Cb, onError?: ErrCb) => {
    lastCb = onData;
    lastErrCb = onError ?? null;
    return mockUnsub;
  },
);

vi.mock('@/services/waitQueue', () => ({
  subscribeMyWaitQueue: (
    slug: string,
    uid: string,
    onData: Cb,
    onError?: ErrCb,
  ) => mockSubscribe(slug, uid, onData, onError),
  selectPrimaryActive: (
    rows: WaitQueuePatientIndex[],
    today: string,
  ): WaitQueuePatientIndex | null => {
    const URGENCY: Record<string, number> = {
      called: 0,
      'in-progress': 1,
      waiting: 2,
      completed: 99,
      cancelled: 99,
    };
    const f = rows
      .filter(
        (e) => e.date === today && e.status !== 'completed' && e.status !== 'cancelled',
      )
      .sort((a, b) => {
        const d = (URGENCY[a.status] ?? 99) - (URGENCY[b.status] ?? 99);
        return d !== 0 ? d : a.number - b.number;
      });
    return f[0] ?? null;
  },
  // 결정적 today — 모든 entry 의 date 와 일치
  todayDateKST: () => '2026-04-26',
}));

interface FakeAuthState {
  user: { uid: string; isAnonymous: boolean } | null;
  profile: { hospitalId?: string } | null;
}
let authState: FakeAuthState = {
  user: { uid: 'u-patient', isAnonymous: false },
  profile: { hospitalId: 'demo' },
};
vi.mock('@/stores/authStore', () => ({
  useAuthStore: <T,>(selector?: (s: FakeAuthState) => T): T | FakeAuthState =>
    selector ? selector(authState) : authState,
}));

import { WaitQueueWidget } from '../WaitQueueWidget';
import { HospitalProvider, FEATURE_DEFAULTS } from '@/contexts/HospitalContext';

function makeProfile(features?: Record<string, boolean>): HospitalProfile {
  return {
    id: 'demo',
    name: 'MediWay 데모',
    status: 'active',
    ...(features ? { features } : {}),
  };
}

function renderWidget(opts?: {
  features?: Record<string, boolean>;
  initialPath?: string;
}) {
  return render(
    <MemoryRouter initialEntries={[opts?.initialPath ?? '/h/demo/patient/home']}>
      <Routes>
        <Route
          path="/h/:hospitalSlug/patient/home"
          element={
            <HospitalProvider value={{ slug: 'demo', profile: makeProfile(opts?.features) }}>
              <WaitQueueWidget />
              <PathProbe />
            </HospitalProvider>
          }
        />
      </Routes>
    </MemoryRouter>,
  );
}

function PathProbe() {
  const [params] = useSearchParams();
  return <div data-testid="search">{params.toString()}</div>;
}

beforeEach(() => {
  mockSubscribe.mockClear();
  mockUnsub.mockClear();
  lastCb = null;
  lastErrCb = null;
  authState = {
    user: { uid: 'u-patient', isAnonymous: false },
    profile: { hospitalId: 'demo' },
  };
});

describe('WaitQueueWidget — 가시성 가드', () => {
  it('미로그인 사용자 → 미렌더 (subscribe 미호출 + 위젯 마커 없음)', () => {
    authState = { user: null, profile: null };
    renderWidget();
    expect(mockSubscribe).not.toHaveBeenCalled();
    expect(screen.queryByLabelText('대기 정보 불러오는 중')).toBeNull();
    expect(screen.queryByTestId('waitqueue-empty')).toBeNull();
    expect(screen.queryByTestId('waitqueue-error')).toBeNull();
  });

  it('익명 사용자 → 미렌더 (auth 있어도 isAnonymous=true)', () => {
    authState = {
      user: { uid: 'anon', isAnonymous: true },
      profile: null,
    };
    renderWidget();
    expect(mockSubscribe).not.toHaveBeenCalled();
    expect(screen.queryByLabelText('대기 정보 불러오는 중')).toBeNull();
  });

  it('features.appointments=false → 미렌더 (subscribe 미호출)', () => {
    renderWidget({ features: { appointments: false } });
    expect(mockSubscribe).not.toHaveBeenCalled();
    expect(screen.queryByLabelText('대기 정보 불러오는 중')).toBeNull();
  });

  it('default features (appointments=true) → subscribe 호출 + slug 사용', () => {
    renderWidget();
    expect(mockSubscribe).toHaveBeenCalledTimes(1);
    expect(mockSubscribe.mock.calls[0][0]).toBe('demo');
    expect(mockSubscribe.mock.calls[0][1]).toBe('u-patient');
  });
});

describe('WaitQueueWidget — slug 소스 (F1.1c)', () => {
  it('useHospital().slug 가 profile.hospitalId 와 다른 슬러그면 slug 가 우선', () => {
    // profile.hospitalId='demo' 이지만 URL 로는 다른 hospital — 사용자가 다른 병원 방문
    // (HospitalShell 가드가 cross-tenant 면 차단하므로 여기 진입 시점엔 정합)
    authState = {
      user: { uid: 'u-patient', isAnonymous: false },
      profile: { hospitalId: 'home-hospital' },
    };
    render(
      <MemoryRouter initialEntries={['/h/visiting-hospital/patient/home']}>
        <Routes>
          <Route
            path="/h/:hospitalSlug/patient/home"
            element={
              <HospitalProvider
                value={{
                  slug: 'visiting-hospital',
                  profile: makeProfile(),
                }}
              >
                <WaitQueueWidget />
              </HospitalProvider>
            }
          />
        </Routes>
      </MemoryRouter>,
    );
    expect(mockSubscribe.mock.calls[0][0]).toBe('visiting-hospital');
  });
});

describe('WaitQueueWidget — 데이터 상태', () => {
  it('초기 마운트 시 skeleton (loading) 표시', () => {
    renderWidget();
    expect(
      screen.getByLabelText('대기 정보 불러오는 중'),
    ).toBeTruthy();
  });

  it('데이터 0건 → empty CTA 표시', () => {
    renderWidget();
    act(() => lastCb?.([]));
    expect(screen.getByTestId('waitqueue-empty')).toBeTruthy();
    expect(screen.getByText('외래 탭으로 이동')).toBeTruthy();
  });

  it('CTA 클릭 → ?tab=appointments 로 이동', () => {
    renderWidget();
    act(() => lastCb?.([]));
    fireEvent.click(screen.getByText('외래 탭으로 이동'));
    expect(screen.getByTestId('search').textContent).toBe('tab=appointments');
  });

  it('waiting 엔트리 → 순번 카드 + "대기 중" 뱃지', () => {
    renderWidget();
    act(() =>
      lastCb?.([
        {
          id: 'e1',
          department: '내과',
          date: '2026-04-26',
          number: 5,
          status: 'waiting',
        },
      ]),
    );
    expect(screen.getByText('5')).toBeTruthy();
    expect(screen.getByText('대기 중')).toBeTruthy();
    expect(screen.getByText(/내과/)).toBeTruthy();
  });

  it('called 엔트리 → 링 강조 + "진료실로 이동해 주세요" 안내', () => {
    renderWidget();
    act(() =>
      lastCb?.([
        {
          id: 'e1',
          department: '내과',
          date: '2026-04-26',
          number: 5,
          status: 'called',
        },
      ]),
    );
    expect(screen.getByText('호출됨')).toBeTruthy();
    expect(screen.getByText('진료실로 이동해 주세요')).toBeTruthy();
  });

  it('completed 엔트리만 → empty (정렬에서 제외)', () => {
    renderWidget();
    act(() =>
      lastCb?.([
        {
          id: 'e1',
          department: '내과',
          date: '2026-04-26',
          number: 5,
          status: 'completed',
        },
      ]),
    );
    expect(screen.getByTestId('waitqueue-empty')).toBeTruthy();
  });

  it('called + waiting 동시 → urgency 우선 (called 표시)', () => {
    renderWidget();
    act(() =>
      lastCb?.([
        { id: 'e1', department: '내과', date: '2026-04-26', number: 1, status: 'waiting' },
        { id: 'e2', department: '외과', date: '2026-04-26', number: 7, status: 'called' },
      ]),
    );
    expect(screen.getByText('7')).toBeTruthy();
    expect(screen.getByText('호출됨')).toBeTruthy();
  });

  it('subscription error → 폴백 문구', () => {
    renderWidget();
    act(() => lastErrCb?.(new Error('PERMISSION_DENIED')));
    expect(
      screen.getByText('대기 정보를 불러올 수 없습니다. 잠시 후 다시 시도해 주세요.'),
    ).toBeTruthy();
  });
});

describe('WaitQueueWidget — 정리', () => {
  it('언마운트 시 unsubscribe 호출', () => {
    const { unmount } = renderWidget();
    expect(mockSubscribe).toHaveBeenCalled();
    unmount();
    expect(mockUnsub).toHaveBeenCalled();
  });
});

describe('FEATURE_DEFAULTS 회귀 보호', () => {
  it('appointments default true 가 widget mount 보장', () => {
    expect(FEATURE_DEFAULTS.appointments).toBe(true);
  });
});
