import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

const listHospitalsMock = vi.fn();
const createHospitalMock = vi.fn();
const setHospitalContractStatusMock = vi.fn();

vi.mock('@/services/hospitals', () => ({
  listHospitals: () => listHospitalsMock(),
  createHospital: (i: unknown) => createHospitalMock(i),
  setHospitalContractStatus: (id: string, s: string) =>
    setHospitalContractStatusMock(id, s),
  isValidSlug: (s: string) => /^[a-z0-9][a-z0-9-]{0,30}[a-z0-9]$/.test(s),
}));

import { AdminHospitalsPage } from '../AdminHospitalsPage';
import type { HospitalSummary } from '@/types/hospital';

const demo: HospitalSummary = {
  id: 'demo',
  slug: 'demo',
  name: 'MediWay Demo',
  themeColor: '#004e9f',
  contractStatus: 'active',
};

beforeEach(() => {
  listHospitalsMock.mockReset();
  createHospitalMock.mockReset();
  setHospitalContractStatusMock.mockReset();
});

function renderPage() {
  return render(
    <MemoryRouter>
      <AdminHospitalsPage />
    </MemoryRouter>,
  );
}

describe('AdminHospitalsPage', () => {
  it('로딩 → 테이블 렌더', async () => {
    listHospitalsMock.mockResolvedValueOnce([demo]);
    renderPage();
    expect(screen.getByText(/로딩 중/)).toBeTruthy();
    await waitFor(() => screen.getByText('MediWay Demo'));
    expect(screen.getByText('demo')).toBeTruthy();
  });

  it('빈 목록 상태', async () => {
    listHospitalsMock.mockResolvedValueOnce([]);
    renderPage();
    await waitFor(() =>
      expect(screen.getByText(/등록된 병원이 없습니다/)).toBeTruthy(),
    );
  });

  it('상태 변경 → setHospitalContractStatus 호출 + 재로드', async () => {
    listHospitalsMock.mockResolvedValue([demo]);
    setHospitalContractStatusMock.mockResolvedValueOnce(undefined);
    renderPage();
    await waitFor(() => screen.getByText('MediWay Demo'));
    const select = screen.getByDisplayValue('운영 중');
    fireEvent.change(select, { target: { value: 'pilot' } });
    await waitFor(() =>
      expect(setHospitalContractStatusMock).toHaveBeenCalledWith('demo', 'pilot'),
    );
    // 재로드 호출
    expect(listHospitalsMock.mock.calls.length).toBeGreaterThanOrEqual(2);
  });

  it('신규 생성 폼 열기 → 제출', async () => {
    listHospitalsMock.mockResolvedValue([]);
    createHospitalMock.mockResolvedValueOnce({ slug: 'smch', name: 'SMC' });
    renderPage();
    await waitFor(() => screen.getByText(/등록된 병원이 없습니다/));

    fireEvent.click(screen.getByText('+ 신규 병원'));
    fireEvent.change(screen.getByLabelText(/이름/), {
      target: { value: 'SMC' },
    });
    fireEvent.change(screen.getByLabelText(/Slug/), {
      target: { value: 'smch' },
    });
    fireEvent.click(screen.getByText('생성'));
    await waitFor(() =>
      expect(createHospitalMock).toHaveBeenCalledWith(
        expect.objectContaining({ slug: 'smch', name: 'SMC' }),
      ),
    );
  });

  it('잘못된 slug는 에러 노출 + 제출 버튼 disable', async () => {
    listHospitalsMock.mockResolvedValue([]);
    renderPage();
    await waitFor(() => screen.getByText(/등록된 병원이 없습니다/));

    fireEvent.click(screen.getByText('+ 신규 병원'));
    fireEvent.change(screen.getByLabelText(/이름/), {
      target: { value: 'Bad' },
    });
    fireEvent.change(screen.getByLabelText(/Slug/), {
      target: { value: 'Bad!' },
    });
    expect(
      screen.getByText(/소문자 영문\/숫자\/하이픈/),
    ).toBeTruthy();
    const submitBtn = screen.getByText('생성') as HTMLButtonElement;
    expect(submitBtn.disabled).toBe(true);
  });

  it('listHospitals 에러 시 에러 배너', async () => {
    listHospitalsMock.mockRejectedValueOnce(new Error('permission denied'));
    renderPage();
    await waitFor(() =>
      expect(screen.getByText(/permission denied/)).toBeTruthy(),
    );
  });
});
