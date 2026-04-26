import { describe, it, expect, beforeEach, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { HospitalProvider } from '@/contexts/HospitalContext';
import type { HospitalProfile } from '@/types/hospital';

// --- Mocks ---

const mockCreateVisit = vi.fn();
vi.mock('@/services/visit', () => ({
  createVisit: (...args: unknown[]) => mockCreateVisit(...args),
}));

vi.mock('@/services/auth', () => ({
  getCurrentUid: () => 'admin-1',
}));

import { AdminVisitsPage } from '../AdminVisitsPage';

beforeEach(() => {
  mockCreateVisit.mockReset();
  mockCreateVisit.mockResolvedValue('visit-new-1');
});

function makeProfile(): HospitalProfile {
  return { id: 'demo', name: 'MediWay 데모', status: 'active' };
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/h/demo/admin/visits']}>
      <Routes>
        <Route
          path="/h/:hospitalSlug/admin/visits"
          element={
            <HospitalProvider value={{ slug: 'demo', profile: makeProfile() }}>
              <AdminVisitsPage />
            </HospitalProvider>
          }
        />
      </Routes>
    </MemoryRouter>,
  );
}

// =====================================================================
// 폼 렌더링
// =====================================================================

describe('AdminVisitsPage — 폼 렌더링', () => {
  it('헤드라인 + 4개 type radio + patientUid + 제출 버튼', () => {
    renderPage();
    expect(screen.getByRole('heading', { name: '환자 visit 등록' })).toBeTruthy();
    expect(screen.getByLabelText(/외래/)).toBeTruthy();
    expect(screen.getByLabelText(/입원/)).toBeTruthy();
    expect(screen.getByLabelText(/검진/)).toBeTruthy();
    expect(screen.getByLabelText(/응급/)).toBeTruthy();
    expect(screen.getByTestId('visit-input-patientUid')).toBeTruthy();
    expect(screen.getByTestId('visit-submit')).toBeTruthy();
  });

  it('default type=outpatient → department + zone 필드 표시', () => {
    renderPage();
    expect(screen.getByTestId('visit-input-department')).toBeTruthy();
    expect(screen.getByTestId('visit-input-zone')).toBeTruthy();
  });
});

// =====================================================================
// type 별 conditional fields
// =====================================================================

describe('AdminVisitsPage — type 분기', () => {
  it('inpatient 선택 → ward + room + bed 필드 표시 (department 숨김)', () => {
    renderPage();
    const radio = screen.getByRole('radio', { name: '입원' }) as HTMLInputElement;
    fireEvent.click(radio);
    expect(screen.getByTestId('visit-input-ward')).toBeTruthy();
    expect(screen.getByTestId('visit-input-room')).toBeTruthy();
    expect(screen.getByTestId('visit-input-bed')).toBeTruthy();
    expect(screen.queryByTestId('visit-input-department')).toBeNull();
  });

  it('checkup 선택 → zone 만 표시 (department/ward/room 숨김)', () => {
    renderPage();
    fireEvent.click(screen.getByRole('radio', { name: '검진' }));
    expect(screen.getByTestId('visit-input-zone')).toBeTruthy();
    expect(screen.queryByTestId('visit-input-department')).toBeNull();
    expect(screen.queryByTestId('visit-input-ward')).toBeNull();
  });

  it('emergency 선택 → department + zone 표시', () => {
    renderPage();
    fireEvent.click(screen.getByRole('radio', { name: '응급' }));
    expect(screen.getByTestId('visit-input-department')).toBeTruthy();
    expect(screen.getByTestId('visit-input-zone')).toBeTruthy();
  });
});

// =====================================================================
// Validation
// =====================================================================

describe('AdminVisitsPage — validation', () => {
  it('patientUid 빈 채로 제출 → error + createVisit 미호출', async () => {
    renderPage();
    fireEvent.click(screen.getByTestId('visit-submit'));
    await waitFor(() => {
      expect(screen.getByTestId('visit-error').textContent).toMatch(/uid/);
    });
    expect(mockCreateVisit).not.toHaveBeenCalled();
  });

  it('outpatient — patientUid 만 입력 + 제출 → zone 필요 error', async () => {
    renderPage();
    fireEvent.change(screen.getByTestId('visit-input-patientUid'), { target: { value: 'uid-x' } });
    fireEvent.click(screen.getByTestId('visit-submit'));
    await waitFor(() => {
      expect(screen.getByTestId('visit-error').textContent).toMatch(/zone/);
    });
  });
});

// =====================================================================
// 정상 제출
// =====================================================================

describe('AdminVisitsPage — 제출 흐름', () => {
  it('outpatient 정상 입력 → createVisit 호출 + success', async () => {
    renderPage();
    fireEvent.change(screen.getByTestId('visit-input-patientUid'), { target: { value: 'uid-pat' } });
    fireEvent.change(screen.getByTestId('visit-input-department'), { target: { value: '내과' } });
    fireEvent.change(screen.getByTestId('visit-input-zone'), { target: { value: 'Zone A-1' } });
    fireEvent.click(screen.getByTestId('visit-submit'));

    await waitFor(() => {
      expect(mockCreateVisit).toHaveBeenCalledTimes(1);
    });
    const [slug, input] = mockCreateVisit.mock.calls[0];
    expect(slug).toBe('demo');
    expect(input).toMatchObject({
      patientUid: 'uid-pat',
      type: 'outpatient',
      department: '내과',
      zone: 'Zone A-1',
      status: 'scheduled',
      createdBy: 'admin-1',
    });

    await waitFor(() => {
      expect(screen.getByTestId('visit-success').textContent).toContain('visit-new-1');
    });
  });

  it('inpatient 정상 입력 → ward/room/bed 전송 + zone 자동 채움', async () => {
    renderPage();
    fireEvent.click(screen.getByRole('radio', { name: '입원' }));
    fireEvent.change(screen.getByTestId('visit-input-patientUid'), { target: { value: 'uid-pat' } });
    fireEvent.change(screen.getByTestId('visit-input-ward'), { target: { value: '3W' } });
    fireEvent.change(screen.getByTestId('visit-input-room'), { target: { value: '302' } });
    fireEvent.change(screen.getByTestId('visit-input-bed'), { target: { value: 'A' } });
    fireEvent.click(screen.getByTestId('visit-submit'));

    await waitFor(() => {
      expect(mockCreateVisit).toHaveBeenCalledTimes(1);
    });
    const [, input] = mockCreateVisit.mock.calls[0];
    expect(input).toMatchObject({
      type: 'inpatient',
      ward: '3W',
      room: '302',
      bed: 'A',
      zone: '3W-302', // ward-room 자동
    });
  });

  it('createVisit reject → error 표시 + success 없음', async () => {
    mockCreateVisit.mockRejectedValueOnce(new Error('PERMISSION_DENIED'));
    renderPage();
    fireEvent.change(screen.getByTestId('visit-input-patientUid'), { target: { value: 'uid-pat' } });
    fireEvent.change(screen.getByTestId('visit-input-department'), { target: { value: 'IM' } });
    fireEvent.change(screen.getByTestId('visit-input-zone'), { target: { value: 'A1' } });
    fireEvent.click(screen.getByTestId('visit-submit'));

    await waitFor(() => {
      expect(screen.getByTestId('visit-error').textContent).toMatch(/등록 실패/);
      expect(screen.getByTestId('visit-error').textContent).toMatch(/PERMISSION_DENIED/);
    });
    expect(screen.queryByTestId('visit-success')).toBeNull();
  });
});
