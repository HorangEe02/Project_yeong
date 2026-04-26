import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { HospitalProvider } from '@/contexts/HospitalContext';
import type { HospitalProfile } from '@/types/hospital';
import type { Visit } from '@/types/visit';

let mockHookState: { visits: Visit[]; loading: boolean; error: string | null } = {
  visits: [],
  loading: false,
  error: null,
};
vi.mock('@/hooks/useVisitHistory', () => ({
  useVisitHistory: () => ({ ...mockHookState, refresh: vi.fn() }),
}));

let mockProfile: { uid?: string; displayName?: string | null } | null = {
  uid: 'uid-pat',
  displayName: '박환자',
};
vi.mock('@/stores/authStore', () => ({
  useAuthStore: <T,>(selector?: (s: { profile: typeof mockProfile }) => T): T | { profile: typeof mockProfile } =>
    selector ? selector({ profile: mockProfile }) : { profile: mockProfile },
}));

import { PatientHistoryPage } from '../PatientHistoryPage';

beforeEach(() => {
  mockHookState = { visits: [], loading: false, error: null };
  mockProfile = { uid: 'uid-pat', displayName: '박환자' };
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
    status: 'completed',
    zone: 'Zone A-1',
    department: 'IM',
    createdAt: new Date('2026-04-20T10:00:00').getTime(),
    updatedAt: 0,
    createdBy: 'admin-1',
    ...overrides,
  };
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/h/demo/patient/history']}>
      <Routes>
        <Route
          path="/h/:hospitalSlug/patient/history"
          element={
            <HospitalProvider value={{ slug: 'demo', profile: makeProfile() }}>
              <PatientHistoryPage />
            </HospitalProvider>
          }
        />
      </Routes>
    </MemoryRouter>,
  );
}

describe('PatientHistoryPage', () => {
  it('헤드라인 + 홈 링크 표시', () => {
    renderPage();
    expect(screen.getByRole('heading', { name: '방문 이력' })).toBeTruthy();
    const back = screen.getByTestId('history-back-home');
    expect(back.getAttribute('href')).toBe('/h/demo/patient/home');
  });

  it('profile 없음 → "로그인이 필요" alert', () => {
    mockProfile = null;
    renderPage();
    expect(screen.getByTestId('history-no-auth')).toBeTruthy();
  });

  it('loading=true → "불러오는 중..." 표시', () => {
    mockHookState = { visits: [], loading: true, error: null };
    renderPage();
    expect(screen.getByTestId('history-loading')).toBeTruthy();
  });

  it('error → 에러 alert', () => {
    mockHookState = { visits: [], loading: false, error: 'PERMISSION_DENIED' };
    renderPage();
    expect(screen.getByTestId('history-error').textContent).toMatch(/PERMISSION_DENIED/);
  });

  it('visits 빔 + !loading → "방문 이력이 없습니다"', () => {
    renderPage();
    expect(screen.getByTestId('history-empty')).toBeTruthy();
  });

  it('visits 다건 → 카드 리스트 표시 (각 카드 testid)', () => {
    mockHookState = {
      visits: [makeVisit({ visitId: 'a' }), makeVisit({ visitId: 'b' })],
      loading: false,
      error: null,
    };
    renderPage();
    expect(screen.getByTestId('history-card-a')).toBeTruthy();
    expect(screen.getByTestId('history-card-b')).toBeTruthy();
  });

  it('inpatient visit → ward-room-bed 위치 표시', () => {
    mockHookState = {
      visits: [
        makeVisit({
          visitId: 'a',
          type: 'inpatient',
          ward: '5W',
          room: '501',
          bed: 'A',
          department: undefined,
        }),
      ],
      loading: false,
      error: null,
    };
    renderPage();
    expect(screen.getByTestId('history-card-a').textContent).toContain('5W-501-A');
  });

  it('notes 60자 초과 → "..." truncate', () => {
    const longNotes = 'a'.repeat(80);
    mockHookState = {
      visits: [makeVisit({ visitId: 'a', notes: longNotes })],
      loading: false,
      error: null,
    };
    renderPage();
    const card = screen.getByTestId('history-card-a');
    expect(card.textContent).toContain('a'.repeat(60) + '...');
  });
});
