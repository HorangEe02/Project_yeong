import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';

const useHospitalMock = vi.fn();
vi.mock('@/hooks/useHospital', () => ({
  useHospital: () => useHospitalMock(),
}));

import { HospitalHomePage } from '../HospitalHomePage';
import { DEFAULT_HOSPITAL_FEATURES } from '@/types/hospital';

function renderAt(url: string) {
  return render(
    <MemoryRouter initialEntries={[url]}>
      <Routes>
        <Route path="/h/:slug/patient/home" element={<HospitalHomePage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('HospitalHomePage', () => {
  it('모든 탭이 mount됨 (hidden으로 visibility 제어)', () => {
    useHospitalMock.mockReturnValue({
      hospital: {
        name: 'Demo',
        slug: 'demo',
        themeColor: '#004e9f',
        contractStatus: 'active',
        features: { ...DEFAULT_HOSPITAL_FEATURES, appointments: true },
        createdAt: 1,
        updatedAt: 1,
      },
      loading: false,
      error: null,
      notFound: false,
      slug: 'demo',
    });
    renderAt('/h/demo/patient/home');

    // 모든 tabpanel이 DOM에 존재 (feature flag 기반 visible tabs만)
    expect(document.getElementById('tabpanel-home')).toBeTruthy();
    expect(document.getElementById('tabpanel-appointments')).toBeTruthy();
    expect(document.getElementById('tabpanel-guide')).toBeTruthy();
    expect(document.getElementById('tabpanel-more')).toBeTruthy();

    // home이 기본 활성 — hidden 속성 확인
    expect(
      document.getElementById('tabpanel-home')?.hasAttribute('hidden'),
    ).toBe(false);
    expect(
      document.getElementById('tabpanel-appointments')?.hasAttribute('hidden'),
    ).toBe(true);
  });

  it('탭 클릭 시 hidden 상태 전환', () => {
    useHospitalMock.mockReturnValue({
      hospital: {
        name: 'Demo',
        slug: 'demo',
        themeColor: '#004e9f',
        contractStatus: 'active',
        features: DEFAULT_HOSPITAL_FEATURES,
        createdAt: 1,
        updatedAt: 1,
      },
      loading: false,
      error: null,
      notFound: false,
      slug: 'demo',
    });
    renderAt('/h/demo/patient/home');

    fireEvent.click(screen.getByRole('tab', { name: '안내' }));

    expect(
      document.getElementById('tabpanel-home')?.hasAttribute('hidden'),
    ).toBe(true);
    expect(
      document.getElementById('tabpanel-guide')?.hasAttribute('hidden'),
    ).toBe(false);
  });

  it('features flag off 시 해당 탭은 렌더되지 않음', () => {
    useHospitalMock.mockReturnValue({
      hospital: {
        name: 'Demo',
        slug: 'demo',
        themeColor: '#004e9f',
        contractStatus: 'active',
        features: DEFAULT_HOSPITAL_FEATURES, // 모두 off
        createdAt: 1,
        updatedAt: 1,
      },
      loading: false,
      error: null,
      notFound: false,
      slug: 'demo',
    });
    renderAt('/h/demo/patient/home');

    // 외래 탭 버튼 자체가 없어야 함
    expect(screen.queryByRole('tab', { name: '외래' })).toBeNull();
    // 하지만 tabpanel은 여전히 mount됨 (feature off인 탭도 placeholder로 유지 —
    //  v2에서 필요 시 조건부 unmount 가능. P2 C2는 상시 mount)
    expect(document.getElementById('tabpanel-appointments')).toBeTruthy();
  });

  it('URL ?tab=guide 진입 시 guide가 active', () => {
    useHospitalMock.mockReturnValue({
      hospital: {
        name: 'Demo',
        slug: 'demo',
        themeColor: '#004e9f',
        contractStatus: 'active',
        features: DEFAULT_HOSPITAL_FEATURES,
        createdAt: 1,
        updatedAt: 1,
      },
      loading: false,
      error: null,
      notFound: false,
      slug: 'demo',
    });
    renderAt('/h/demo/patient/home?tab=guide');
    expect(
      document.getElementById('tabpanel-guide')?.hasAttribute('hidden'),
    ).toBe(false);
  });
});
