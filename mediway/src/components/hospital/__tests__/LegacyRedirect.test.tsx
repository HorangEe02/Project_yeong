import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

// --- mocks ---
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

import { LegacyHospitalRedirect } from '../LegacyRedirect';

beforeEach(() => {
  authState = { user: null, profile: null, initialized: true };
});

describe('LegacyHospitalRedirect — auth 초기화 전', () => {
  it('initialized=false → 로딩 표시', () => {
    authState = { user: null, profile: null, initialized: false };
    render(
      <MemoryRouter initialEntries={['/patient']}>
        <Routes>
          <Route
            path="/patient"
            element={
              <LegacyHospitalRedirect buildTarget={(slug) => `/h/${slug}/patient/home`} />
            }
          />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText('이동할 병원을 확인 중...')).toBeTruthy();
  });
});

describe('LegacyHospitalRedirect — fallback 슬러그', () => {
  it('로그아웃 사용자 → /h/demo/patient/home', () => {
    render(
      <MemoryRouter initialEntries={['/patient']}>
        <Routes>
          <Route
            path="/patient"
            element={
              <LegacyHospitalRedirect buildTarget={(slug) => `/h/${slug}/patient/home`} />
            }
          />
          <Route path="/h/:slug/patient/home" element={<PathProbe />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByTestId('probe').textContent).toBe('/h/demo/patient/home');
  });

  it('익명 사용자도 demo 폴백', () => {
    authState = {
      user: { uid: 'anon', isAnonymous: true },
      profile: null,
      initialized: true,
    };
    render(
      <MemoryRouter initialEntries={['/staff']}>
        <Routes>
          <Route
            path="/staff"
            element={<LegacyHospitalRedirect buildTarget={(slug) => `/h/${slug}/staff`} />}
          />
          <Route path="/h/:slug/staff" element={<PathProbe />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByTestId('probe').textContent).toBe('/h/demo/staff');
  });
});

describe('LegacyHospitalRedirect — 로그인 사용자', () => {
  it('staff (hospitalId=smch) → /h/smch/staff/queue', () => {
    authState = {
      user: { uid: 'u1', isAnonymous: false },
      profile: { hospitalId: 'smch', role: 'staff' },
      initialized: true,
    };
    render(
      <MemoryRouter initialEntries={['/staff/queue']}>
        <Routes>
          <Route
            path="/staff/queue"
            element={
              <LegacyHospitalRedirect buildTarget={(slug) => `/h/${slug}/staff/queue`} />
            }
          />
          <Route path="/h/:slug/staff/queue" element={<PathProbe />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByTestId('probe').textContent).toBe('/h/smch/staff/queue');
  });

  it('hospitalId 없는 patient role → demo 폴백', () => {
    authState = {
      user: { uid: 'u2', isAnonymous: false },
      profile: { role: 'patient' },
      initialized: true,
    };
    render(
      <MemoryRouter initialEntries={['/patient']}>
        <Routes>
          <Route
            path="/patient"
            element={
              <LegacyHospitalRedirect buildTarget={(slug) => `/h/${slug}/patient/home`} />
            }
          />
          <Route path="/h/:slug/patient/home" element={<PathProbe />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByTestId('probe').textContent).toBe('/h/demo/patient/home');
  });
});

describe('LegacyHospitalRedirect — 동적 파라미터', () => {
  it(':sessionId 보존', () => {
    render(
      <MemoryRouter initialEntries={['/patient/abc123']}>
        <Routes>
          <Route
            path="/patient/:sessionId"
            element={
              <LegacyHospitalRedirect
                buildTarget={(slug, p) => `/h/${slug}/patient/${p.sessionId}`}
              />
            }
          />
          <Route path="/h/:slug/patient/:sessionId" element={<PathProbe />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByTestId('probe').textContent).toBe('/h/demo/patient/abc123');
  });
});

describe('LegacyHospitalRedirect — search/hash 보존', () => {
  it('?tab=appointments → 보존', () => {
    render(
      <MemoryRouter initialEntries={['/patient?tab=appointments']}>
        <Routes>
          <Route
            path="/patient"
            element={
              <LegacyHospitalRedirect buildTarget={(slug) => `/h/${slug}/patient/home`} />
            }
          />
          <Route path="/h/:slug/patient/home" element={<PathProbeWithSearch />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByTestId('probe').textContent).toBe(
      '/h/demo/patient/home?tab=appointments',
    );
  });

  it('#anchor → 보존', () => {
    render(
      <MemoryRouter initialEntries={['/staff#section']}>
        <Routes>
          <Route
            path="/staff"
            element={<LegacyHospitalRedirect buildTarget={(slug) => `/h/${slug}/staff`} />}
          />
          <Route path="/h/:slug/staff" element={<PathProbeWithHash />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByTestId('probe').textContent).toBe('/h/demo/staff#section');
  });
});

// --- helpers ---

import { useLocation } from 'react-router-dom';

function PathProbe() {
  const loc = useLocation();
  return <div data-testid="probe">{loc.pathname}</div>;
}

function PathProbeWithSearch() {
  const loc = useLocation();
  return <div data-testid="probe">{loc.pathname}{loc.search}</div>;
}

function PathProbeWithHash() {
  const loc = useLocation();
  return <div data-testid="probe">{loc.pathname}{loc.hash}</div>;
}
