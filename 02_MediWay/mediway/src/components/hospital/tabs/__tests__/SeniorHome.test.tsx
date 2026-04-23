import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

// 위젯 내부 훅 의존성 무력화 (렌더 smoke만 검증)
vi.mock('@/hooks/useHospital', () => ({
  useHospital: () => ({ slug: 'demo', hospital: { features: {} } }),
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

import { SeniorHome } from '../SeniorHome';

describe('SeniorHome', () => {
  it('오늘 날짜 인사 섹션 + 3개 위젯 렌더', () => {
    render(<SeniorHome />);
    expect(screen.getByLabelText('오늘 날짜 인사')).toBeTruthy();
    expect(screen.getByText('오늘도 건강하세요')).toBeTruthy();
    expect(screen.getByText('오늘 일정')).toBeTruthy();
    expect(screen.getByText('진료 대기')).toBeTruthy();
    expect(screen.getByText('응급실 바로가기')).toBeTruthy();
  });

  it('오늘 날짜가 ko-KR long 포맷으로 표시', () => {
    render(<SeniorHome />);
    const greeting = screen.getByLabelText('오늘 날짜 인사');
    // "2026년 4월 23일 목요일" 같은 패턴 — 년/월/일 모두 포함
    expect(greeting.textContent).toMatch(/\d{4}년/);
    expect(greeting.textContent).toMatch(/월/);
    expect(greeting.textContent).toMatch(/일/);
  });

  it('AI triage 위젯은 렌더되지 않음 (인지부하 제외)', () => {
    render(<SeniorHome />);
    expect(screen.queryByText('AI 진료과 추천')).toBeNull();
  });
});
