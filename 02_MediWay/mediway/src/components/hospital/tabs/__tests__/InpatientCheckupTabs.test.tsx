import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

const useHospitalMock = vi.fn();
vi.mock('@/hooks/useHospital', () => ({
  useHospital: () => useHospitalMock(),
}));

vi.mock('@/stores/authStore', () => {
  const state = { user: { uid: 'uid-a' } };
  return {
    useAuthStore: <T,>(selector: (s: typeof state) => T) => selector(state),
  };
});

vi.mock('@/services/appointments', () => ({
  createAppointment: vi.fn(),
  subscribeMyAppointmentIndex: (
    _h: string,
    _u: string,
    cb: (list: unknown[]) => void,
  ) => {
    cb([]);
    return () => {};
  },
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

  it('feature on 시 담당 의료진·면회 예약·퇴원 안내 섹션', () => {
    useHospitalMock.mockReturnValue({
      hospital: {
        ...baseHospital,
        features: { ...DEFAULT_HOSPITAL_FEATURES, inpatient: true },
      },
      loading: false,
      error: null,
      notFound: false,
      slug: 'demo',
    });
    render(<InpatientTab />);
    expect(screen.getByText('담당 의료진')).toBeTruthy();
    expect(screen.getByText('면회 예약')).toBeTruthy();
    expect(screen.getByText('퇴원 수속 안내')).toBeTruthy();
    expect(screen.getByRole('button', { name: '면회 예약 등록' })).toBeTruthy();
  });

  it('면회 예약 폼 — 전체 입력 후 등록하면 목록에 추가', () => {
    useHospitalMock.mockReturnValue({
      hospital: {
        ...baseHospital,
        features: { ...DEFAULT_HOSPITAL_FEATURES, inpatient: true },
      },
      loading: false,
      error: null,
      notFound: false,
      slug: 'demo',
    });
    render(<InpatientTab />);
    fireEvent.change(screen.getByPlaceholderText('방문자 이름'), {
      target: { value: '홍길동' },
    });
    fireEvent.change(screen.getByPlaceholderText(/관계/), {
      target: { value: '배우자' },
    });
    const future = new Date(Date.now() + 86_400_000)
      .toISOString()
      .slice(0, 16);
    fireEvent.change(screen.getByLabelText('방문 일시'), {
      target: { value: future },
    });
    fireEvent.click(screen.getByRole('button', { name: '면회 예약 등록' }));
    expect(screen.getByText('홍길동')).toBeTruthy();
    expect(screen.getByText(/배우자/)).toBeTruthy();
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

  it('feature on 시 검진 예약 폼 + 빈 리스트 메시지', () => {
    useHospitalMock.mockReturnValue({
      hospital: {
        ...baseHospital,
        features: { ...DEFAULT_HOSPITAL_FEATURES, checkup: true },
      },
      loading: false,
      error: null,
      notFound: false,
      slug: 'demo',
    });
    render(<CheckupTab />);
    expect(screen.getByText('검진 예약')).toBeTruthy();
    expect(screen.getByText(/아직 검진 예약이 없습니다/)).toBeTruthy();
    expect(
      screen.getByRole('button', { name: '검진 예약 등록' }),
    ).toBeTruthy();
  });

  it('검진 종류 select에 4개 옵션', () => {
    useHospitalMock.mockReturnValue({
      hospital: {
        ...baseHospital,
        features: { ...DEFAULT_HOSPITAL_FEATURES, checkup: true },
      },
      loading: false,
      error: null,
      notFound: false,
      slug: 'demo',
    });
    render(<CheckupTab />);
    const select = screen.getByLabelText('검진 종류') as HTMLSelectElement;
    expect(select.options).toHaveLength(4);
  });
});
