import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import type { Visit } from '@/types/visit';

// --- Mocks ---

// Stub QRCodeSVG (jsdom + svg 부담 회피)
vi.mock('qrcode.react', () => ({
  QRCodeSVG: () => <div data-testid="qr-svg-stub" />,
}));

// useActiveVisit 결과 주입
let mockUseActiveVisitState: { visit: Visit | null; loading: boolean } = {
  visit: null,
  loading: false,
};
vi.mock('@/hooks/useActiveVisit', () => ({
  useActiveVisit: () => mockUseActiveVisitState,
}));

vi.mock('@/contexts/HospitalContext', () => ({
  useHospital: () => ({ slug: 'demo', profile: { id: 'demo', name: 'demo', status: 'active' } }),
}));

vi.mock('@/services/auth', () => ({
  getCurrentUid: () => 'uid-1',
}));

// authStore — selector 패턴 지원
let mockProfile: { displayName: string | null } | null = { displayName: '홍길동' };
vi.mock('@/stores/authStore', () => ({
  useAuthStore: <T,>(selector?: (s: { profile: typeof mockProfile }) => T): T | { profile: typeof mockProfile } =>
    selector ? selector({ profile: mockProfile }) : { profile: mockProfile },
}));

import { QRDisplay } from '../QRDisplay';

beforeEach(() => {
  mockUseActiveVisitState = { visit: null, loading: false };
  mockProfile = { displayName: '홍길동' };
});

function makeVisit(overrides: Partial<Visit> = {}): Visit {
  return {
    visitId: 'v1',
    patientUid: 'uid-1',
    hospitalId: 'demo',
    type: 'outpatient',
    status: 'checked-in',
    zone: 'Zone A-1',
    department: 'IM',
    createdAt: 100,
    updatedAt: 100,
    createdBy: 'admin-1',
    ...overrides,
  };
}

describe('QRDisplay — visit 정보 카드', () => {
  it('loading=true → "불러오는 중..." 표시', () => {
    mockUseActiveVisitState = { visit: null, loading: true };
    render(<QRDisplay onTokenGenerated={vi.fn()} />);
    expect(screen.getByTestId('visit-loading')).toBeTruthy();
    expect(screen.getByText('불러오는 중...')).toBeTruthy();
  });

  it('visit null + !loading → "진료 정보 없음" + profile.displayName 표시', () => {
    mockUseActiveVisitState = { visit: null, loading: false };
    render(<QRDisplay onTokenGenerated={vi.fn()} />);
    expect(screen.getByTestId('visit-empty')).toBeTruthy();
    expect(screen.getByText('홍길동')).toBeTruthy();
    expect(screen.getByText(/진료 정보 없음/)).toBeTruthy();
  });

  it('outpatient visit → "외래 · {department} / {zone}" 표시', () => {
    mockUseActiveVisitState = {
      visit: makeVisit({ type: 'outpatient', department: '내과', zone: 'Zone B-2' }),
      loading: false,
    };
    render(<QRDisplay onTokenGenerated={vi.fn()} />);
    expect(screen.getByTestId('visit-loaded')).toBeTruthy();
    expect(screen.getByText('외래 · 내과 / Zone B-2')).toBeTruthy();
  });

  it('inpatient visit → "입원 · {ward}-{room}-{bed}" 표시 + zone 무시', () => {
    mockUseActiveVisitState = {
      visit: makeVisit({
        type: 'inpatient',
        ward: '3W',
        room: '302',
        bed: 'A',
        department: undefined,
        zone: 'IGNORED',
      }),
      loading: false,
    };
    render(<QRDisplay onTokenGenerated={vi.fn()} />);
    expect(screen.getByText('입원 · 3W-302-A')).toBeTruthy();
  });

  it('inpatient visit (bed 없음) → "입원 · {ward}-{room}"', () => {
    mockUseActiveVisitState = {
      visit: makeVisit({
        type: 'inpatient',
        ward: '5W',
        room: '501',
        bed: undefined,
        department: undefined,
      }),
      loading: false,
    };
    render(<QRDisplay onTokenGenerated={vi.fn()} />);
    expect(screen.getByText('입원 · 5W-501')).toBeTruthy();
  });

  it('checkup visit → "검진 · {zone}"', () => {
    mockUseActiveVisitState = {
      visit: makeVisit({ type: 'checkup', zone: '검진실 1F', department: undefined }),
      loading: false,
    };
    render(<QRDisplay onTokenGenerated={vi.fn()} />);
    expect(screen.getByText('검진 · 검진실 1F')).toBeTruthy();
  });

  it('emergency visit → "응급 · ER / {zone}"', () => {
    mockUseActiveVisitState = {
      visit: makeVisit({ type: 'emergency', department: 'ER', zone: 'ER 분류실' }),
      loading: false,
    };
    render(<QRDisplay onTokenGenerated={vi.fn()} />);
    expect(screen.getByText('응급 · ER / ER 분류실')).toBeTruthy();
  });

  it('visit.displayName 우선 — RTDB cache 사용', () => {
    mockUseActiveVisitState = {
      visit: makeVisit({ displayName: '김환자' }),
      loading: false,
    };
    render(<QRDisplay onTokenGenerated={vi.fn()} />);
    expect(screen.getByText(/김환자/)).toBeTruthy();
  });

  it('visit.displayName 없고 profile.displayName 도 없음 → "환자" fallback', () => {
    mockProfile = { displayName: null };
    mockUseActiveVisitState = { visit: null, loading: false };
    render(<QRDisplay onTokenGenerated={vi.fn()} />);
    expect(screen.getByText('환자')).toBeTruthy();
  });
});
