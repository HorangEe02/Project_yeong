import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

const useSeniorModeMock = vi.fn();
vi.mock('@/hooks/useSeniorMode', () => ({
  useSeniorMode: () => useSeniorModeMock(),
}));

const useHospitalMock = vi.fn();
vi.mock('@/hooks/useHospital', () => ({
  useHospital: () => useHospitalMock(),
}));

vi.mock('@/stores/authStore', () => ({
  useAuthStore: <T,>(
    sel: (s: {
      user: { uid: string; email: string; displayName: string };
      profile: { displayName: string };
    }) => T,
  ) =>
    sel({
      user: { uid: 'uid-a', email: 'a@example.com', displayName: '테스트' },
      profile: { displayName: '테스트' },
    }),
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

function renderWithRouter(ui: React.ReactElement) {
  return render(<MemoryRouter initialEntries={['/h/demo/patient/home']}>{ui}</MemoryRouter>);
}

beforeEach(() => {
  useSeniorModeMock.mockReset();
  useHospitalMock.mockReset();
});

describe('HomeTab 분기', () => {
  it('senior OFF + aiTriage OFF → 표준 홈 (Greeting + 3개 위젯 + QuickActions)', () => {
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
    renderWithRouter(<HomeTab />);
    // Greeting 섹션 (시간대 + 이름)
    expect(screen.getByText(/좋은 (아침|오후|저녁)입니다/)).toBeTruthy();
    expect(screen.getByText('테스트')).toBeTruthy();
    // 위젯 3개
    expect(screen.getByText('오늘 일정')).toBeTruthy();
    expect(screen.getByText('진료 대기')).toBeTruthy();
    expect(screen.getByText('응급실 바로가기')).toBeTruthy();
    expect(screen.queryByText('AI 진료과 추천')).toBeNull();
    // SeniorGreeting (고령자 모드 전용) 없음
    expect(screen.queryByLabelText('오늘 날짜 인사')).toBeNull();
    // Recent Results stub + Quick Actions
    expect(screen.getByText('최근 검사 결과')).toBeTruthy();
    expect(screen.getByRole('group', { name: '빠른 작업' })).toBeTruthy();
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
    renderWithRouter(<HomeTab />);
    expect(screen.getByText('AI 진료과 추천')).toBeTruthy();
  });

  it('senior ON → SeniorHome (AI 위젯 숨김 + 인사 섹션 노출, Greeting/QuickActions 없음)', () => {
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
    renderWithRouter(<HomeTab />);
    expect(screen.getByLabelText('오늘 날짜 인사')).toBeTruthy();
    expect(screen.getByText('오늘 일정')).toBeTruthy();
    expect(screen.queryByText('AI 진료과 추천')).toBeNull();
    // StandardHome 전용 요소는 없음
    expect(screen.queryByRole('group', { name: '빠른 작업' })).toBeNull();
    expect(screen.queryByText('최근 검사 결과')).toBeNull();
  });
});
