import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { useState } from 'react';

const useHospitalMock = vi.fn();
vi.mock('@/hooks/useHospital', () => ({
  useHospital: () => useHospitalMock(),
}));

// Replace AppointmentsTab with a stateful probe — tests the Mount-all
// guarantee without requiring Firebase/RHF/Zod wiring
vi.mock('@/components/hospital/tabs/AppointmentsTab', () => ({
  AppointmentsTab: () => {
    const [value, setValue] = useState('');
    return (
      <div>
        <input
          aria-label="probe-input"
          value={value}
          onChange={(e) => setValue(e.target.value)}
        />
        <div data-testid="probe-value">{value}</div>
      </div>
    );
  },
}));

// Similarly replace GuideTab with a simpler probe so the test doesn't
// pull in PatientPage's full Firebase stack
vi.mock('@/components/hospital/tabs/GuideTab', () => ({
  GuideTab: () => {
    const [scanned, setScanned] = useState(0);
    return (
      <div>
        <button onClick={() => setScanned((n) => n + 1)}>scan</button>
        <div data-testid="scan-count">{scanned}</div>
      </div>
    );
  },
}));

import { HospitalHomePage } from '../HospitalHomePage';
import { DEFAULT_HOSPITAL_FEATURES } from '@/types/hospital';

function renderPage(url: string) {
  return render(
    <MemoryRouter initialEntries={[url]}>
      <Routes>
        <Route path="/h/:slug/patient/home" element={<HospitalHomePage />} />
      </Routes>
    </MemoryRouter>,
  );
}

/**
 * C9 — Mount-all + hidden 전략이 탭 전환 중 React state를 보존하는지 검증.
 *
 * 실제 QR 스캐너·RTDB 구독의 visibility 타이밍은 실 브라우저에서만
 * 재현 가능하므로 `public/e2e-tab-session.html`로 별도 커버.
 * jsdom 수준에서는 컴포넌트 state가 hidden 전환을 거쳐도 살아있음을 확인한다.
 */
describe('Tab switch session persistence', () => {
  beforeEach(() => {
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
  });

  it('외래 탭 input 값이 다른 탭 방문 후 복귀 시 유지', () => {
    renderPage('/h/demo/patient/home?tab=appointments');

    const input = screen.getByLabelText('probe-input') as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'hello' } });
    expect(
      (screen.getByTestId('probe-value') as HTMLElement).textContent,
    ).toBe('hello');

    // 다른 탭으로 전환
    fireEvent.click(screen.getByRole('tab', { name: '홈' }));
    expect(
      document.getElementById('tabpanel-appointments')?.hasAttribute('hidden'),
    ).toBe(true);
    expect(
      document.getElementById('tabpanel-home')?.hasAttribute('hidden'),
    ).toBe(false);

    // 외래로 복귀
    fireEvent.click(screen.getByRole('tab', { name: '외래' }));
    expect(
      document.getElementById('tabpanel-appointments')?.hasAttribute('hidden'),
    ).toBe(false);

    // input value + probe-value 모두 살아있음
    const inputAfter = screen.getByLabelText('probe-input') as HTMLInputElement;
    expect(inputAfter.value).toBe('hello');
    expect(
      (screen.getByTestId('probe-value') as HTMLElement).textContent,
    ).toBe('hello');
  });

  it('안내 탭의 내부 state가 탭 전환을 거쳐도 유지', () => {
    renderPage('/h/demo/patient/home?tab=guide');

    fireEvent.click(screen.getByText('scan'));
    fireEvent.click(screen.getByText('scan'));
    expect(
      (screen.getByTestId('scan-count') as HTMLElement).textContent,
    ).toBe('2');

    fireEvent.click(screen.getByRole('tab', { name: '더보기' }));
    fireEvent.click(screen.getByRole('tab', { name: '안내' }));

    expect(
      (screen.getByTestId('scan-count') as HTMLElement).textContent,
    ).toBe('2');
  });

  it('tabpanel DOM id 유지 — 세션·핸들러 참조 안전', () => {
    renderPage('/h/demo/patient/home');

    const homePanel1 = document.getElementById('tabpanel-home');
    const guidePanel1 = document.getElementById('tabpanel-guide');

    fireEvent.click(screen.getByRole('tab', { name: '안내' }));
    fireEvent.click(screen.getByRole('tab', { name: '홈' }));

    const homePanel2 = document.getElementById('tabpanel-home');
    const guidePanel2 = document.getElementById('tabpanel-guide');

    // DOM 참조 동일성 (unmount되지 않았음) — React 내부 재사용 기준
    expect(homePanel2).toBe(homePanel1);
    expect(guidePanel2).toBe(guidePanel1);
  });
});
