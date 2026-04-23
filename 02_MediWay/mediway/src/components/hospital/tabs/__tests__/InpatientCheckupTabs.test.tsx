import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

const useHospitalMock = vi.fn();
vi.mock('@/hooks/useHospital', () => ({
  useHospital: () => useHospitalMock(),
}));

import { InpatientTab } from '../InpatientTab';
import { CheckupTab } from '../CheckupTab';
import { DEFAULT_HOSPITAL_FEATURES } from '@/types/hospital';

const baseHospital = {
  name: 'Demo',
  slug: 'demo',
  themeColor: '#004e9f',
  contractStatus: 'active' as const,
  features: DEFAULT_HOSPITAL_FEATURES,
  createdAt: 1,
  updatedAt: 1,
};

describe('InpatientTab', () => {
  it('feature off 시 비활성 안내', () => {
    useHospitalMock.mockReturnValue({
      hospital: baseHospital,
      loading: false,
      error: null,
      notFound: false,
      slug: 'demo',
    });
    render(<InpatientTab />);
    expect(screen.getByText(/아직 활성화하지 않았습니다/)).toBeTruthy();
  });

  it('feature on 시 현황 + 준비 중 기능 3개 렌더', () => {
    useHospitalMock.mockReturnValue({
      hospital: { ...baseHospital, features: { ...DEFAULT_HOSPITAL_FEATURES, inpatient: true } },
      loading: false,
      error: null,
      notFound: false,
      slug: 'demo',
    });
    render(<InpatientTab />);
    expect(screen.getByText('입원 현황')).toBeTruthy();
    expect(screen.getByText('담당 의료진 조회')).toBeTruthy();
    expect(screen.getByText('면회 예약')).toBeTruthy();
    expect(screen.getByText('퇴원 수속 안내')).toBeTruthy();
    expect(screen.getAllByText('준비 중').length).toBe(3);
  });
});

describe('CheckupTab', () => {
  it('feature off 시 비활성 안내', () => {
    useHospitalMock.mockReturnValue({
      hospital: baseHospital,
      loading: false,
      error: null,
      notFound: false,
      slug: 'demo',
    });
    render(<CheckupTab />);
    expect(screen.getByText(/아직 활성화하지 않았습니다/)).toBeTruthy();
  });

  it('feature on 시 기록 섹션 + 준비 중 기능 3개 렌더', () => {
    useHospitalMock.mockReturnValue({
      hospital: { ...baseHospital, features: { ...DEFAULT_HOSPITAL_FEATURES, checkup: true } },
      loading: false,
      error: null,
      notFound: false,
      slug: 'demo',
    });
    render(<CheckupTab />);
    expect(screen.getByText('건강검진 기록')).toBeTruthy();
    expect(screen.getByText('검진 예약')).toBeTruthy();
    expect(screen.getByText(/검진 결과.*무기한 보관/)).toBeTruthy();
    expect(screen.getAllByText('준비 중').length).toBe(3);
  });
});
