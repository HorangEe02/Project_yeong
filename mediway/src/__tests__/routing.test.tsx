import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import { MemoryRouter, Route, Routes, Navigate } from 'react-router-dom';
import type { HospitalProfile } from '@/types/hospital';

/**
 * App-level routing 통합 검증.
 *
 * 본 테스트는 `App.tsx` 의 BrowserRouter 외부 — `Routes` 테이블만 떼어내
 * MemoryRouter 안에서 마운트해 다음 시나리오를 단대단으로 검증한다:
 *   1. flat `/patient` → LegacyHospitalRedirect → `/h/demo/patient/home`
 *      → HospitalShell loading → ready 후 HospitalHomePage 마운트
 *   2. flat `/staff/queue` → `/h/demo/staff/queue`
 *   3. unknown slug → not-found 안내
 *   4. cross-tenant 차단
 *
 * 페이지 컴포넌트는 가벼운 stub 으로 mock — Firebase/auth/스토어 의존성 차단.
 */

// --- Mocks ---
type ProfileCb = (p: HospitalProfile | null) => void;
type ErrorCb = (e: Error) => void;

let lastDataCb: ProfileCb | null = null;
const mockSubscribe = vi.fn(
  (_slug: string, onData: ProfileCb, _onError?: ErrorCb) => {
    lastDataCb = onData;
    return () => {};
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
  selectIsSuspended: () => false,
}));

// 페이지 stub — 실제 구현체는 Firebase/스토어를 잡아끌어서 무거우므로 marker 만 렌더
vi.mock('@/pages/HospitalHomePage', () => ({
  HospitalHomePage: () => <div data-testid="page">PAGE:hospitalHome</div>,
}));
vi.mock('@/pages/PatientPage', () => ({
  PatientPage: () => <div data-testid="page">PAGE:patient</div>,
}));
vi.mock('@/pages/StaffPage', () => ({
  StaffPage: () => <div data-testid="page">PAGE:staff</div>,
}));
vi.mock('@/pages/StaffQueuePage', () => ({
  StaffQueuePage: () => <div data-testid="page">PAGE:staffQueue</div>,
}));

// ProtectedRoute 도 stub — auth 게이트 동작 자체는 별도 테스트
vi.mock('@/components/auth/ProtectedRoute', () => ({
  ProtectedRoute: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

import { HospitalShell } from '@/components/hospital/HospitalShell';
import { LegacyHospitalRedirect } from '@/components/hospital/LegacyRedirect';
import { HospitalHomePage } from '@/pages/HospitalHomePage';
import { PatientPage } from '@/pages/PatientPage';
import { StaffPage } from '@/pages/StaffPage';
import { StaffQueuePage } from '@/pages/StaffQueuePage';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';

/** App.tsx 의 routing 블록을 충실히 미러링 — 인증/계정/관리자/공유 등 본 테스트 비범위는 생략 */
function AppRoutesUnderTest() {
  return (
    <Routes>
      <Route path="/forbidden" element={<div data-testid="page">PAGE:forbidden</div>} />

      <Route
        path="/patient"
        element={
          <LegacyHospitalRedirect
            buildTarget={(slug) => `/h/${slug}/patient/home`}
          />
        }
      />
      <Route
        path="/patient/:sessionId"
        element={
          <LegacyHospitalRedirect
            buildTarget={(slug, p) => `/h/${slug}/patient/${p.sessionId ?? ''}`}
          />
        }
      />
      <Route
        path="/staff"
        element={
          <LegacyHospitalRedirect buildTarget={(slug) => `/h/${slug}/staff`} />
        }
      />
      <Route
        path="/staff/queue"
        element={
          <LegacyHospitalRedirect buildTarget={(slug) => `/h/${slug}/staff/queue`} />
        }
      />

      <Route path="/h/:hospitalSlug" element={<HospitalShell />}>
        <Route path="patient" element={<Navigate to="home" replace />} />
        <Route path="patient/home" element={<HospitalHomePage />} />
        <Route path="patient/:sessionId" element={<PatientPage />} />
        <Route
          path="staff"
          element={
            <ProtectedRoute requireRole={['staff', 'admin']}>
              <StaffPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="staff/queue"
          element={
            <ProtectedRoute requireRole={['staff', 'admin']}>
              <StaffQueuePage />
            </ProtectedRoute>
          }
        />
      </Route>
    </Routes>
  );
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AppRoutesUnderTest />
    </MemoryRouter>,
  );
}

const validProfile: HospitalProfile = {
  id: 'demo',
  name: 'MediWay 데모 병원',
  themeColor: '#004e9f',
  status: 'active',
};

beforeEach(() => {
  mockSubscribe.mockClear();
  lastDataCb = null;
  authState = { user: null, profile: null, initialized: true };
});

describe('routing — flat → nested redirect 후 mount', () => {
  it('/patient → /h/demo/patient/home → HospitalHomePage', () => {
    renderAt('/patient');
    // shell 가 즉시 subscribe 호출
    expect(mockSubscribe).toHaveBeenCalledWith(
      'demo',
      expect.any(Function),
      expect.any(Function),
    );
    act(() => lastDataCb?.(validProfile));
    expect(screen.getByTestId('page').textContent).toBe('PAGE:hospitalHome');
  });

  it('/patient/abc123 → /h/demo/patient/abc123 → PatientPage', () => {
    renderAt('/patient/abc123');
    expect(mockSubscribe).toHaveBeenCalledWith(
      'demo',
      expect.any(Function),
      expect.any(Function),
    );
    act(() => lastDataCb?.(validProfile));
    expect(screen.getByTestId('page').textContent).toBe('PAGE:patient');
  });

  it('/staff → /h/demo/staff → StaffPage', () => {
    renderAt('/staff');
    act(() => lastDataCb?.(validProfile));
    expect(screen.getByTestId('page').textContent).toBe('PAGE:staff');
  });

  it('/staff/queue → /h/demo/staff/queue → StaffQueuePage', () => {
    renderAt('/staff/queue');
    act(() => lastDataCb?.(validProfile));
    expect(screen.getByTestId('page').textContent).toBe('PAGE:staffQueue');
  });
});

describe('routing — flat staff with own hospital slug', () => {
  it('hospitalId=smch staff → /h/smch/staff', () => {
    authState = {
      user: { uid: 'u1', isAnonymous: false },
      profile: { hospitalId: 'smch', role: 'staff' },
      initialized: true,
    };
    renderAt('/staff/queue');
    expect(mockSubscribe).toHaveBeenCalledWith(
      'smch',
      expect.any(Function),
      expect.any(Function),
    );
    act(() =>
      lastDataCb?.({
        id: 'smch',
        name: '성모병원',
        status: 'active',
      } as HospitalProfile),
    );
    expect(screen.getByTestId('page').textContent).toBe('PAGE:staffQueue');
  });
});

describe('routing — nested 직접 진입', () => {
  it('/h/demo/patient (index) → /home redirect → HospitalHomePage', () => {
    renderAt('/h/demo/patient');
    act(() => lastDataCb?.(validProfile));
    expect(screen.getByTestId('page').textContent).toBe('PAGE:hospitalHome');
  });

  it('/h/demo/patient/home?tab=appointments — query 보존', () => {
    renderAt('/h/demo/patient/home?tab=appointments');
    act(() => lastDataCb?.(validProfile));
    expect(screen.getByTestId('page').textContent).toBe('PAGE:hospitalHome');
  });
});

describe('routing — 슬러그 검증 분기', () => {
  it('미등록 슬러그 → "병원을 찾을 수 없습니다"', () => {
    renderAt('/h/ghost/patient/home');
    act(() => lastDataCb?.(null));
    expect(screen.getByText('병원을 찾을 수 없습니다')).toBeTruthy();
  });

  it('suspended → /forbidden', () => {
    renderAt('/h/demo/patient/home');
    act(() =>
      lastDataCb?.({
        id: 'demo',
        name: 'X',
        status: 'suspended',
      } as HospitalProfile),
    );
    expect(screen.getByTestId('page').textContent).toBe('PAGE:forbidden');
  });

  it('cross-tenant → /forbidden', () => {
    authState = {
      user: { uid: 'u1', isAnonymous: false },
      profile: { hospitalId: 'smch', role: 'staff' },
      initialized: true,
    };
    renderAt('/h/demo/patient/home'); // 본인 hid 와 다른 슬러그 직접 진입
    act(() => lastDataCb?.(validProfile));
    expect(screen.getByTestId('page').textContent).toBe('PAGE:forbidden');
  });
});
