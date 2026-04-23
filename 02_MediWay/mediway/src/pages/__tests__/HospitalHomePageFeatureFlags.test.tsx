import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';

const useHospitalMock = vi.fn();
vi.mock('@/hooks/useHospital', () => ({
  useHospital: () => useHospitalMock(),
}));

import { HospitalHomePage } from '../HospitalHomePage';
import {
  DEFAULT_HOSPITAL_FEATURES,
  type HospitalProfile,
} from '@/types/hospital';

function buildHospital(
  overrides: Partial<HospitalProfile['features']> = {},
): HospitalProfile {
  return {
    name: 'Demo',
    slug: 'demo',
    themeColor: '#004e9f',
    contractStatus: 'active',
    features: { ...DEFAULT_HOSPITAL_FEATURES, ...overrides },
    createdAt: 1,
    updatedAt: 1,
  };
}

function renderAt(url: string) {
  return render(
    <MemoryRouter initialEntries={[url]}>
      <Routes>
        <Route path="/h/:slug/patient/home" element={<HospitalHomePage />} />
      </Routes>
    </MemoryRouter>,
  );
}

/**
 * C8 — Feature-flag driven tab visibility 통합 검증.
 *
 * 검증 대상:
 * - HospitalContext의 features 변경이 HospitalTabs NAV 필터와 useTabState
 *   activeTab fallback에 실시간 반영되는지.
 */
describe('HospitalHomePage feature flag visibility', () => {
  it('features.appointments=false → 외래 탭 버튼 렌더되지 않음', () => {
    useHospitalMock.mockReturnValue({
      hospital: buildHospital({ appointments: false }),
      loading: false,
      error: null,
      notFound: false,
      slug: 'demo',
    });
    renderAt('/h/demo/patient/home');
    expect(screen.queryByRole('tab', { name: '외래' })).toBeNull();
  });

  it('features.appointments=true → 외래 탭 버튼 렌더', () => {
    useHospitalMock.mockReturnValue({
      hospital: buildHospital({ appointments: true }),
      loading: false,
      error: null,
      notFound: false,
      slug: 'demo',
    });
    renderAt('/h/demo/patient/home');
    expect(screen.getByRole('tab', { name: '외래' })).toBeTruthy();
  });

  it('현재 탭이 features flag off → home으로 fallback', () => {
    useHospitalMock.mockReturnValue({
      hospital: buildHospital({ appointments: false }),
      loading: false,
      error: null,
      notFound: false,
      slug: 'demo',
    });
    // URL 자체는 ?tab=appointments — 하지만 flag가 false이므로 home으로 fallback
    renderAt('/h/demo/patient/home?tab=appointments');

    expect(
      document.getElementById('tabpanel-home')?.hasAttribute('hidden'),
    ).toBe(false);
    expect(
      document.getElementById('tabpanel-appointments')?.hasAttribute('hidden'),
    ).toBe(true);
  });

  it('features flag가 동적으로 toggle — re-render 시 tab 가시성 업데이트', () => {
    useHospitalMock.mockReturnValue({
      hospital: buildHospital({ appointments: true, checkup: true }),
      loading: false,
      error: null,
      notFound: false,
      slug: 'demo',
    });
    const { rerender } = renderAt('/h/demo/patient/home');
    expect(screen.getByRole('tab', { name: '외래' })).toBeTruthy();
    expect(screen.getByRole('tab', { name: '건강검진' })).toBeTruthy();

    // 병원 관리자가 checkup을 비활성 — onValue 구독에서 features 업데이트
    useHospitalMock.mockReturnValue({
      hospital: buildHospital({ appointments: true, checkup: false }),
      loading: false,
      error: null,
      notFound: false,
      slug: 'demo',
    });
    rerender(
      <MemoryRouter initialEntries={['/h/demo/patient/home']}>
        <Routes>
          <Route
            path="/h/:slug/patient/home"
            element={<HospitalHomePage />}
          />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByRole('tab', { name: '외래' })).toBeTruthy();
    expect(screen.queryByRole('tab', { name: '건강검진' })).toBeNull();
  });

  it('항상 노출 탭(홈·안내·더보기)은 features와 무관하게 존재', () => {
    useHospitalMock.mockReturnValue({
      hospital: buildHospital(), // 모든 features false
      loading: false,
      error: null,
      notFound: false,
      slug: 'demo',
    });
    renderAt('/h/demo/patient/home');
    expect(screen.getByRole('tab', { name: '홈' })).toBeTruthy();
    expect(screen.getByRole('tab', { name: '안내' })).toBeTruthy();
    expect(screen.getByRole('tab', { name: '더보기' })).toBeTruthy();
  });
});
