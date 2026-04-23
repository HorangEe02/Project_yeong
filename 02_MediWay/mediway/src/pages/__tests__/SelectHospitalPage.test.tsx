import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';

const listActiveHospitalsMock = vi.fn();
vi.mock('@/services/hospitals', () => ({
  listActiveHospitals: () => listActiveHospitalsMock(),
}));

import { SelectHospitalPage } from '../SelectHospitalPage';
import type { HospitalSummary } from '@/types/hospital';

const demo: HospitalSummary = {
  id: 'demo',
  slug: 'demo',
  name: 'MediWay 데모 병원',
  themeColor: '#004e9f',
  contractStatus: 'active',
};

const smch: HospitalSummary = {
  id: 'smch',
  slug: 'smch',
  name: 'Samsung Medical',
  themeColor: '#009688',
  contractStatus: 'pilot',
};

function renderAt(url: string) {
  return render(
    <MemoryRouter initialEntries={[url]}>
      <Routes>
        <Route path="/hospitals/select" element={<SelectHospitalPage />} />
        <Route
          path="/h/:slug/patient/home"
          element={<div>REDIRECTED patient</div>}
        />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  listActiveHospitalsMock.mockReset();
});

describe('SelectHospitalPage', () => {
  it('로딩 중 메시지 → 로드 후 카드 렌더', async () => {
    let resolve: (list: HospitalSummary[]) => void;
    listActiveHospitalsMock.mockImplementation(
      () => new Promise<HospitalSummary[]>((r) => (resolve = r)),
    );
    renderAt('/hospitals/select');
    expect(screen.getByText(/불러오는 중/)).toBeTruthy();

    resolve!([demo, smch]);
    await waitFor(() =>
      expect(screen.getByText('MediWay 데모 병원')).toBeTruthy(),
    );
    expect(screen.getByText('Samsung Medical')).toBeTruthy();
  });

  it('빈 목록 → 빈 상태 메시지', async () => {
    listActiveHospitalsMock.mockResolvedValueOnce([]);
    renderAt('/hospitals/select');
    await waitFor(() =>
      expect(
        screen.getByText(/가입 가능한 병원이 없습니다/),
      ).toBeTruthy(),
    );
  });

  it('검색 필터링', async () => {
    listActiveHospitalsMock.mockResolvedValueOnce([demo, smch]);
    renderAt('/hospitals/select');
    await waitFor(() => screen.getByText('Samsung Medical'));

    fireEvent.change(screen.getByRole('searchbox'), {
      target: { value: 'samsung' },
    });

    expect(screen.queryByText('MediWay 데모 병원')).toBeNull();
    expect(screen.getByText('Samsung Medical')).toBeTruthy();
  });

  it('검색 결과 0건 → "검색 결과가 없습니다"', async () => {
    listActiveHospitalsMock.mockResolvedValueOnce([demo]);
    renderAt('/hospitals/select');
    await waitFor(() => screen.getByText('MediWay 데모 병원'));

    fireEvent.change(screen.getByRole('searchbox'), {
      target: { value: 'zzzzz' },
    });
    expect(screen.getByText(/검색 결과가 없습니다/)).toBeTruthy();
  });

  it('?hospital=demo URL 부트스트랩 → 환자 홈으로 즉시 이동', async () => {
    listActiveHospitalsMock.mockResolvedValueOnce([demo, smch]);
    renderAt('/hospitals/select?hospital=demo');
    await waitFor(() =>
      expect(screen.getByText('REDIRECTED patient')).toBeTruthy(),
    );
  });

  it('존재하지 않는 slug는 bootstrap 무시하고 목록 표시', async () => {
    listActiveHospitalsMock.mockResolvedValueOnce([demo]);
    renderAt('/hospitals/select?hospital=ghost');
    await waitFor(() => screen.getByText('MediWay 데모 병원'));
    expect(screen.queryByText('REDIRECTED patient')).toBeNull();
  });

  it('서비스 에러 시 에러 메시지 + 빈 리스트', async () => {
    listActiveHospitalsMock.mockRejectedValueOnce(new Error('permission'));
    renderAt('/hospitals/select');
    await waitFor(() =>
      expect(screen.getByText(/permission/)).toBeTruthy(),
    );
  });
});
