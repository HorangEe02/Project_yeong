import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';

// PatientPage는 Firebase·Leaflet 등 의존성이 많아 통째로 mock — wrapper 책임만 확인
vi.mock('@/pages/PatientPage', () => ({
  PatientPage: () => <div data-testid="patient-page">PATIENT_PAGE_ROOT</div>,
}));

import { GuideTab } from '../GuideTab';

describe('GuideTab (wrapper)', () => {
  it('PatientPage를 그대로 렌더 (이관 없이 재사용)', () => {
    render(
      <MemoryRouter initialEntries={['/h/demo/patient/home?tab=guide']}>
        <Routes>
          <Route path="/h/:slug/patient/home" element={<GuideTab />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByTestId('patient-page')).toBeTruthy();
    expect(screen.getByText('PATIENT_PAGE_ROOT')).toBeTruthy();
  });

  it('sessionId 파라미터 있는 deep link에서도 동작', () => {
    render(
      <MemoryRouter initialEntries={['/share/abc']}>
        <Routes>
          <Route path="/share/:sessionId" element={<GuideTab />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByTestId('patient-page')).toBeTruthy();
  });
});
