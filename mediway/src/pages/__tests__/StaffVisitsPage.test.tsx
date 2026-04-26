import { describe, it, expect, beforeEach, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { HospitalProvider } from '@/contexts/HospitalContext';
import type { HospitalProfile } from '@/types/hospital';
import type { Visit } from '@/types/visit';

// --- Mocks ---

const mockUpdateVisitStatus = vi.fn();
vi.mock('@/services/visit', () => ({
  updateVisitStatus: (...args: unknown[]) => mockUpdateVisitStatus(...args),
  // 본 페이지는 useStaffActiveVisits 통해 호출 — subscribeActiveVisitsByDepartment 직접 mock 안 함
}));

let mockHookState: { visits: Visit[]; loading: boolean } = { visits: [], loading: false };
vi.mock('@/hooks/useStaffActiveVisits', () => ({
  useStaffActiveVisits: () => mockHookState,
}));

let mockProfile: { department?: string | null; displayName?: string | null } | null = {
  department: 'IM',
  displayName: '담당 의료진',
};
vi.mock('@/stores/authStore', () => ({
  useAuthStore: <T,>(selector?: (s: { profile: typeof mockProfile }) => T): T | { profile: typeof mockProfile } =>
    selector ? selector({ profile: mockProfile }) : { profile: mockProfile },
}));

import { StaffVisitsPage } from '../StaffVisitsPage';

beforeEach(() => {
  mockUpdateVisitStatus.mockReset();
  mockUpdateVisitStatus.mockResolvedValue(undefined);
  mockHookState = { visits: [], loading: false };
  mockProfile = { department: 'IM', displayName: '담당 의료진' };
});

function makeProfile(): HospitalProfile {
  return { id: 'demo', name: 'MediWay 데모', status: 'active' };
}

function makeVisit(overrides: Partial<Visit> = {}): Visit {
  return {
    visitId: 'v1',
    patientUid: 'uid-pat',
    hospitalId: 'demo',
    type: 'outpatient',
    status: 'checked-in',
    zone: 'Zone A-1',
    department: 'IM',
    createdAt: new Date('2026-04-26T10:00:00').getTime(),
    updatedAt: 0,
    createdBy: 'admin-1',
    ...overrides,
  };
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/h/demo/staff/visits']}>
      <Routes>
        <Route
          path="/h/:hospitalSlug/staff/visits"
          element={
            <HospitalProvider value={{ slug: 'demo', profile: makeProfile() }}>
              <StaffVisitsPage />
            </HospitalProvider>
          }
        />
      </Routes>
    </MemoryRouter>,
  );
}

describe('StaffVisitsPage — 부서 정보', () => {
  it('profile.department 없음 → "담당 부서가 설정되지 않았습니다" alert', () => {
    mockProfile = { department: null };
    renderPage();
    expect(screen.getByTestId('staff-visits-no-dept')).toBeTruthy();
  });

  it('profile.department 존재 → 부서명 + 환자 수 헤드라인', () => {
    mockHookState = { visits: [makeVisit()], loading: false };
    renderPage();
    expect(screen.getByText(/IM 부서/)).toBeTruthy();
    expect(screen.getByText(/active 환자 1명/)).toBeTruthy();
  });
});

describe('StaffVisitsPage — 리스트 표시', () => {
  it('loading=true → "불러오는 중..."', () => {
    mockHookState = { visits: [], loading: true };
    renderPage();
    expect(screen.getByTestId('staff-visits-loading')).toBeTruthy();
  });

  it('visits 빔 + !loading → "현재 active 환자 없음"', () => {
    mockHookState = { visits: [], loading: false };
    renderPage();
    expect(screen.getByTestId('staff-visits-empty')).toBeTruthy();
  });

  it('visits 다건 → 카드 리스트', () => {
    mockHookState = {
      visits: [makeVisit({ visitId: 'a' }), makeVisit({ visitId: 'b' })],
      loading: false,
    };
    renderPage();
    expect(screen.getByTestId('staff-visit-a')).toBeTruthy();
    expect(screen.getByTestId('staff-visit-b')).toBeTruthy();
  });

  it('inpatient → ward-room-bed 위치', () => {
    mockHookState = {
      visits: [
        makeVisit({
          visitId: 'a',
          type: 'inpatient',
          ward: '5W',
          room: '501',
          bed: 'A',
          department: 'IM',
        }),
      ],
      loading: false,
    };
    renderPage();
    expect(screen.getByTestId('staff-visit-a').textContent).toContain('5W-501-A');
  });
});

describe('StaffVisitsPage — status 변경', () => {
  it('select 변경 → updateVisitStatus 호출', async () => {
    mockHookState = { visits: [makeVisit({ visitId: 'a', status: 'checked-in' })], loading: false };
    renderPage();
    fireEvent.change(screen.getByTestId('staff-visit-status-select-a'), {
      target: { value: 'in-progress' },
    });
    await waitFor(() => {
      expect(mockUpdateVisitStatus).toHaveBeenCalledWith('demo', 'a', 'in-progress');
    });
  });

  it('updateVisitStatus reject → error 표시', async () => {
    mockUpdateVisitStatus.mockRejectedValueOnce(new Error('PERMISSION_DENIED'));
    mockHookState = { visits: [makeVisit({ visitId: 'a' })], loading: false };
    renderPage();
    fireEvent.change(screen.getByTestId('staff-visit-status-select-a'), {
      target: { value: 'completed' },
    });
    await waitFor(() => {
      expect(screen.getByTestId('staff-visits-error').textContent).toMatch(/PERMISSION_DENIED/);
    });
  });
});

describe('StaffVisitsPage — sub-nav', () => {
  it('StaffSubNav active="visits" 마운트 (환자 진료 탭 aria-current=page)', () => {
    renderPage();
    expect(
      screen.getByRole('link', { name: '환자 진료' }).getAttribute('aria-current'),
    ).toBe('page');
  });
});
