import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

// 훅·서비스 mock
vi.mock('@/hooks/useHospital', () => ({
  useHospital: () => ({ slug: 'demo', hospital: { features: {} } }),
}));

const useSeniorModeMock = vi.fn().mockReturnValue({
  enabled: true,
  pending: false,
  toggle: vi.fn(),
  setEnabled: vi.fn(),
});
vi.mock('@/hooks/useSeniorMode', () => ({
  useSeniorMode: () => useSeniorModeMock(),
}));

vi.mock('@/stores/authStore', () => ({
  useAuthStore: <T,>(
    sel: (s: {
      user: { uid: string; email: string; displayName: string };
      profile: { displayName: string };
    }) => T,
  ) =>
    sel({
      user: { uid: 'uid-a', email: 'a@example.com', displayName: '홍길동' },
      profile: { displayName: '홍길동' },
    }),
}));

let activeEntries: unknown[] = [];
vi.mock('@/services/waitQueue', () => ({
  subscribeMyEntries: (
    _h: string,
    _u: string,
    cb: (list: unknown[]) => void,
  ) => {
    cb(activeEntries);
    return () => {};
  },
}));

vi.mock('@/services/appointments', () => ({
  subscribeMyAppointmentIndex: (
    _h: string,
    _u: string,
    cb: (list: unknown[]) => void,
  ) => {
    cb([]);
    return () => {};
  },
}));

import { SeniorHome } from '../SeniorHome';

function renderWithRouter() {
  return render(
    <MemoryRouter initialEntries={['/h/demo/patient/home']}>
      <SeniorHome />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  activeEntries = [];
});

describe('SeniorHome (U1)', () => {
  it('인사 카드 + 4 타일 + 응급 버튼 렌더', () => {
    renderWithRouter();
    expect(screen.getByLabelText('오늘 인사 + 다음 방문')).toBeTruthy();
    expect(screen.getByText('홍길동')).toBeTruthy();
    expect(screen.getByText('병원 예약하기')).toBeTruthy();
    expect(screen.getByText('길 안내')).toBeTruthy();
    expect(screen.getByText('내 순번 보기')).toBeTruthy();
    expect(screen.getByText('가족 연락')).toBeTruthy();
    expect(screen.getByText('응급 도움 받기')).toBeTruthy();
  });

  it('가족 연락 타일은 disabled (aria-disabled true)', () => {
    renderWithRouter();
    const familyBtn = screen.getByRole('button', { name: /가족 연락/ });
    expect(familyBtn.getAttribute('aria-disabled')).toBe('true');
  });

  it('활성 wait entry가 있으면 내 순번 타일에 뱃지 노출', () => {
    activeEntries = [
      {
        id: 'e-1',
        department: '내과',
        date: '2026-04-23',
        number: 7,
        status: 'waiting',
      },
    ];
    renderWithRouter();
    expect(screen.getByLabelText('알림 7건')).toBeTruthy();
  });

  it('응급 버튼 클릭 → 확인 모달', () => {
    renderWithRouter();
    fireEvent.click(screen.getByText('응급 도움 받기'));
    expect(screen.getByRole('dialog')).toBeTruthy();
    expect(screen.getByText('어떻게 도와드릴까요?')).toBeTruthy();
  });
});
