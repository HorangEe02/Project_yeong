import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';

const useSeniorModeMock = vi.fn();
vi.mock('@/hooks/useSeniorMode', () => ({
  useSeniorMode: () => useSeniorModeMock(),
}));

const useHospitalMock = vi.fn();
vi.mock('@/hooks/useHospital', () => ({
  useHospital: () => useHospitalMock(),
}));

vi.mock('@/stores/authStore', () => ({
  useAuthStore: <T,>(sel: (s: { user: { uid: string } }) => T) =>
    sel({ user: { uid: 'uid-a' } }),
}));

vi.mock('@/services/waitQueue', () => ({
  subscribeMyEntries: (
    _h: string,
    _u: string,
    cb: (list: unknown[]) => void,
  ) => {
    cb([]);
    return () => {};
  },
}));

import { HomeTab } from '../HomeTab';

beforeEach(() => {
  useSeniorModeMock.mockReset();
  useHospitalMock.mockReset();
});

describe('HomeTab 분기', () => {
  it('senior OFF + aiTriage OFF → 표준 홈 (3개 위젯, triage 없음)', () => {
    useSeniorModeMock.mockReturnValue({
      enabled: false,
      pending: false,
      toggle: vi.fn(),
      setEnabled: vi.fn(),
    });
    useHospitalMock.mockReturnValue({
      slug: 'demo',
      hospital: { features: { aiTriage: false } },
    });
    render(<HomeTab />);
    expect(screen.getByText('오늘 일정')).toBeTruthy();
    expect(screen.getByText('진료 대기')).toBeTruthy();
    expect(screen.getByText('응급실 바로가기')).toBeTruthy();
    expect(screen.queryByText('AI 진료과 추천')).toBeNull();
    // SeniorGreeting 섹션이 없음
    expect(screen.queryByLabelText('오늘 날짜 인사')).toBeNull();
  });

  it('senior OFF + aiTriage ON → 표준 홈에 AI 위젯 포함', () => {
    useSeniorModeMock.mockReturnValue({
      enabled: false,
      pending: false,
      toggle: vi.fn(),
      setEnabled: vi.fn(),
    });
    useHospitalMock.mockReturnValue({
      slug: 'demo',
      hospital: { features: { aiTriage: true } },
    });
    render(<HomeTab />);
    expect(screen.getByText('AI 진료과 추천')).toBeTruthy();
  });

  it('senior ON → SeniorHome (AI 위젯 숨김 + 인사 섹션 노출)', () => {
    useSeniorModeMock.mockReturnValue({
      enabled: true,
      pending: false,
      toggle: vi.fn(),
      setEnabled: vi.fn(),
    });
    useHospitalMock.mockReturnValue({
      slug: 'demo',
      hospital: { features: { aiTriage: true } },
    });
    render(<HomeTab />);
    expect(screen.getByLabelText('오늘 날짜 인사')).toBeTruthy();
    expect(screen.getByText('오늘 일정')).toBeTruthy();
    expect(screen.queryByText('AI 진료과 추천')).toBeNull();
  });
});
