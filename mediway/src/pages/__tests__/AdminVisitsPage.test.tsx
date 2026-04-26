import { describe, it, expect, beforeEach, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { HospitalProvider } from '@/contexts/HospitalContext';
import type { HospitalProfile } from '@/types/hospital';
import type { Visit } from '@/types/visit';

// --- Mocks ---

const mockCreateVisit = vi.fn();
const mockUpdateVisitStatus = vi.fn();
const mockUnsubscribeRecent = vi.fn();
const mockSubscribeRecentVisits = vi.fn();
vi.mock('@/services/visit', () => ({
  createVisit: (...args: unknown[]) => mockCreateVisit(...args),
  updateVisitStatus: (...args: unknown[]) => mockUpdateVisitStatus(...args),
  subscribeRecentVisits: (
    slug: string,
    limit: number,
    cb: (vs: unknown[]) => void,
  ) => {
    mockSubscribeRecentVisits(slug, limit, cb);
    return mockUnsubscribeRecent;
  },
}));

vi.mock('@/services/auth', () => ({
  getCurrentUid: () => 'admin-1',
}));

import { AdminVisitsPage } from '../AdminVisitsPage';

beforeEach(() => {
  mockCreateVisit.mockReset();
  mockUpdateVisitStatus.mockReset();
  mockSubscribeRecentVisits.mockReset();
  mockUnsubscribeRecent.mockReset();
  mockCreateVisit.mockResolvedValue('visit-new-1');
  mockUpdateVisitStatus.mockResolvedValue(undefined);
});

function makeVisit(overrides: Partial<Visit> = {}): Visit {
  return {
    visitId: 'v1',
    patientUid: 'uid-1',
    hospitalId: 'demo',
    type: 'outpatient',
    status: 'scheduled',
    zone: 'Zone A-1',
    department: 'IM',
    createdAt: 1700000000000,
    updatedAt: 1700000000000,
    createdBy: 'admin-1',
    ...overrides,
  };
}

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

// =====================================================================
// I.1.2 — RecentVisitsList + status 변경 dropdown
// =====================================================================

describe('AdminVisitsPage — 최근 visit 리스트 (I.1.2)', () => {
  it('마운트 시 subscribeRecentVisits(slug, 20) 호출', () => {
    renderPage();
    expect(mockSubscribeRecentVisits).toHaveBeenCalledTimes(1);
    expect(mockSubscribeRecentVisits.mock.calls[0][0]).toBe('demo');
    expect(mockSubscribeRecentVisits.mock.calls[0][1]).toBe(20);
  });

  it('visits 빔 → "등록된 visit 없음" 표시', () => {
    renderPage();
    const cb = mockSubscribeRecentVisits.mock.calls[0][2] as (vs: Visit[]) => void;
    act(() => cb([]));
    expect(screen.getByTestId('recent-visits-empty')).toBeTruthy();
    expect(screen.getByText('등록된 visit 없음')).toBeTruthy();
  });

  it('visits 다건 → 카드 리스트 표시', () => {
    renderPage();
    const cb = mockSubscribeRecentVisits.mock.calls[0][2] as (vs: Visit[]) => void;
    const v1 = makeVisit({ visitId: 'v1' });
    const v2 = makeVisit({
      visitId: 'v2',
      type: 'inpatient',
      ward: '3W',
      room: '302',
      department: undefined,
    });
    act(() => cb([v1, v2]));
    expect(screen.getByTestId('visit-card-v1')).toBeTruthy();
    expect(screen.getByTestId('visit-card-v2')).toBeTruthy();
  });

  it('status select 변경 → updateVisitStatus(slug, visitId, newStatus) 호출', async () => {
    renderPage();
    const cb = mockSubscribeRecentVisits.mock.calls[0][2] as (vs: Visit[]) => void;
    act(() => cb([makeVisit({ visitId: 'v1', status: 'scheduled' })]));

    fireEvent.change(screen.getByTestId('visit-status-select-v1'), {
      target: { value: 'checked-in' },
    });

    await waitFor(() => {
      expect(mockUpdateVisitStatus).toHaveBeenCalledWith('demo', 'v1', 'checked-in');
    });
  });

  it('updateVisitStatus reject → error 표시', async () => {
    mockUpdateVisitStatus.mockRejectedValueOnce(new Error('PERMISSION_DENIED'));
    renderPage();
    const cb = mockSubscribeRecentVisits.mock.calls[0][2] as (vs: Visit[]) => void;
    act(() => cb([makeVisit({ visitId: 'v1' })]));

    fireEvent.change(screen.getByTestId('visit-status-select-v1'), {
      target: { value: 'completed' },
    });

    await waitFor(() => {
      expect(screen.getByTestId('visit-status-update-error').textContent).toMatch(
        /PERMISSION_DENIED/,
      );
    });
  });

  it('inpatient visit → 카드에 ward-room-bed 위치 표시', () => {
    renderPage();
    const cb = mockSubscribeRecentVisits.mock.calls[0][2] as (vs: Visit[]) => void;
    act(() =>
      cb([
        makeVisit({
          visitId: 'v1',
          type: 'inpatient',
          ward: '5W',
          room: '501',
          bed: 'A',
          department: undefined,
        }),
      ]),
    );
    expect(screen.getByTestId('visit-card-v1').textContent).toContain('5W-501-A');
  });

  it('unmount 시 unsubscribe 호출', () => {
    const { unmount } = renderPage();
    expect(mockUnsubscribeRecent).not.toHaveBeenCalled();
    unmount();
    expect(mockUnsubscribeRecent).toHaveBeenCalledTimes(1);
  });
});
