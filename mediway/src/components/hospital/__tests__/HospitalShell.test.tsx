import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import type { HospitalProfile } from '@/types/hospital';

// --- mocks ---

type ProfileCb = (p: HospitalProfile | null) => void;
type ErrorCb = (e: Error) => void;

let lastDataCb: ProfileCb | null = null;
let lastErrorCb: ErrorCb | null = null;
const mockUnsub = vi.fn();
const mockSubscribe = vi.fn(
  (_slug: string, onData: ProfileCb, onError?: ErrorCb) => {
    lastDataCb = onData;
    lastErrorCb = onError ?? null;
    return mockUnsub;
  },
);

vi.mock('@/services/hospitalProfile', () => ({
  subscribeHospitalProfile: (
    slug: string,
    onData: ProfileCb,
    onError?: ErrorCb,
  ) => mockSubscribe(slug, onData, onError),
  resolveThemeColor: (c: string | null | undefined) => c ?? '#004e9f',
}));

interface FakeAuthState {
  user: { uid: string; isAnonymous: boolean } | null;
  profile: { hospitalId?: string; role?: string } | null;
  initialized: boolean;
}

let authState: FakeAuthState = {
  user: null,
  profile: null,
  initialized: true,
};

vi.mock('@/stores/authStore', () => ({
  useAuthStore: <T,>(selector?: (s: FakeAuthState) => T): T | FakeAuthState =>
    selector ? selector(authState) : authState,
}));

import { HospitalShell } from '../HospitalShell';
import { useHospital } from '@/contexts/HospitalContext';

function renderWithRoute(slug: string, child: React.ReactNode = <ChildProbe />) {
  return render(
    <MemoryRouter initialEntries={[`/h/${slug}/patient/home`]}>
      <Routes>
        <Route path="/h/:hospitalSlug" element={<HospitalShell />}>
          <Route path="patient/home" element={child} />
        </Route>
        <Route path="/forbidden" element={<div>FORBIDDEN_PAGE</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

function ChildProbe() {
  const { slug, profile } = useHospital();
  return (
    <div data-testid="child">
      slug={slug}::name={profile.name}
    </div>
  );
}

beforeEach(() => {
  mockSubscribe.mockClear();
  mockUnsub.mockClear();
  lastDataCb = null;
  lastErrorCb = null;
  authState = { user: null, profile: null, initialized: true };
});

describe('HospitalShell — loading', () => {
  it('첫 마운트 시 로딩 메시지', () => {
    renderWithRoute('demo');
    expect(screen.getByText('병원 정보를 불러오는 중...')).toBeTruthy();
  });

  it('subscribeHospitalProfile 가 slug 로 호출됨', () => {
    renderWithRoute('demo');
    expect(mockSubscribe).toHaveBeenCalledWith(
      'demo',
      expect.any(Function),
      expect.any(Function),
    );
  });
});

describe('HospitalShell — not found', () => {
  it('profile=null → "병원을 찾을 수 없습니다"', () => {
    renderWithRoute('ghost');
    act(() => lastDataCb?.(null));
    expect(screen.getByText('병원을 찾을 수 없습니다')).toBeTruthy();
    // slug 가 보여짐
    expect(screen.getByText('ghost')).toBeTruthy();
  });
});

describe('HospitalShell — error', () => {
  it('에러 콜백 → "병원 정보 로드 실패" + 메시지', () => {
    renderWithRoute('demo');
    act(() => lastErrorCb?.(new Error('PERMISSION_DENIED')));
    expect(screen.getByText('병원 정보 로드 실패')).toBeTruthy();
    expect(screen.getByText('PERMISSION_DENIED')).toBeTruthy();
  });
});

describe('HospitalShell — suspended', () => {
  it('status=suspended → /forbidden?reason=hospital-suspended 로 이동', () => {
    renderWithRoute('demo');
    act(() =>
      lastDataCb?.({
        id: 'demo',
        name: 'X',
        status: 'suspended',
      } as HospitalProfile),
    );
    expect(screen.getByText('FORBIDDEN_PAGE')).toBeTruthy();
  });
});

describe('HospitalShell — cross-tenant', () => {
  it('다른 hospitalId 의 staff → forbidden', () => {
    authState = {
      user: { uid: 'u1', isAnonymous: false },
      profile: { hospitalId: 'smch', role: 'staff' },
      initialized: true,
    };
    renderWithRoute('demo');
    act(() =>
      lastDataCb?.({
        id: 'demo',
        name: 'MediWay 데모',
        status: 'active',
      } as HospitalProfile),
    );
    expect(screen.getByText('FORBIDDEN_PAGE')).toBeTruthy();
  });

  it('hospital admin (role=admin) 도 다른 슬러그면 forbidden', () => {
    authState = {
      user: { uid: 'u1', isAnonymous: false },
      profile: { hospitalId: 'smch', role: 'admin' },
      initialized: true,
    };
    renderWithRoute('demo');
    act(() =>
      lastDataCb?.({
        id: 'demo',
        name: 'MediWay 데모',
        status: 'active',
      } as HospitalProfile),
    );
    expect(screen.getByText('FORBIDDEN_PAGE')).toBeTruthy();
  });

  it('platformAdmin → cross-tenant 통과 (자유 열람)', () => {
    authState = {
      user: { uid: 'u1', isAnonymous: false },
      profile: { hospitalId: 'demo', role: 'platformAdmin' },
      initialized: true,
    };
    renderWithRoute('smch'); // 본인 hospitalId 와 다른 슬러그
    act(() =>
      lastDataCb?.({
        id: 'smch',
        name: '성모병원',
        status: 'active',
      } as HospitalProfile),
    );
    expect(screen.getByTestId('child').textContent).toBe(
      'slug=smch::name=성모병원',
    );
  });

  it('익명 사용자는 cross-tenant 가드 미적용', () => {
    authState = {
      user: { uid: 'anon', isAnonymous: true },
      profile: null,
      initialized: true,
    };
    renderWithRoute('demo');
    act(() =>
      lastDataCb?.({
        id: 'demo',
        name: 'MediWay 데모',
        status: 'active',
      } as HospitalProfile),
    );
    expect(screen.getByTestId('child')).toBeTruthy();
  });

  it('자기 병원 (hospitalId === slug) staff → 통과', () => {
    authState = {
      user: { uid: 'u1', isAnonymous: false },
      profile: { hospitalId: 'demo', role: 'staff' },
      initialized: true,
    };
    renderWithRoute('demo');
    act(() =>
      lastDataCb?.({
        id: 'demo',
        name: 'MediWay 데모',
        status: 'active',
      } as HospitalProfile),
    );
    expect(screen.getByTestId('child').textContent).toBe(
      'slug=demo::name=MediWay 데모',
    );
  });
});

describe('HospitalShell — Outlet/Provider', () => {
  it('ready 상태에서 자식이 useHospital() 으로 slug/profile 접근', () => {
    renderWithRoute('demo');
    act(() =>
      lastDataCb?.({
        id: 'demo',
        name: 'MediWay 데모 병원',
        themeColor: '#004e9f',
        status: 'active',
      } as HospitalProfile),
    );
    const child = screen.getByTestId('child');
    expect(child.textContent).toBe('slug=demo::name=MediWay 데모 병원');
  });
});

describe('HospitalShell — themeColor 주입', () => {
  it('ready 후 documentElement 에 --theme-primary 설정', () => {
    document.documentElement.style.removeProperty('--theme-primary');
    renderWithRoute('demo');
    act(() =>
      lastDataCb?.({
        id: 'demo',
        name: 'X',
        themeColor: '#abcdef',
        status: 'active',
      } as HospitalProfile),
    );
    expect(document.documentElement.style.getPropertyValue('--theme-primary'))
      .toBe('#abcdef');
  });
});

describe('HospitalShell — cleanup', () => {
  it('언마운트 시 unsubscribe 호출', () => {
    const { unmount } = renderWithRoute('demo');
    expect(mockSubscribe).toHaveBeenCalled();
    unmount();
    expect(mockUnsub).toHaveBeenCalled();
  });
});
