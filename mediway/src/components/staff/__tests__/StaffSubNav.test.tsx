import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { HospitalProfile } from '@/types/hospital';
import { HospitalProvider } from '@/contexts/HospitalContext';
import { StaffSubNav } from '../StaffSubNav';

function wrap(slug: string, ui: React.ReactNode, profile?: Partial<HospitalProfile>) {
  return render(
    <MemoryRouter>
      <HospitalProvider
        value={{
          slug,
          profile: { id: slug, name: slug, status: 'active', ...profile },
        }}
      >
        {ui}
      </HospitalProvider>
    </MemoryRouter>,
  );
}

describe('StaffSubNav', () => {
  it('두 탭(동선 전송 / 대기열 콘솔) 라벨 노출', () => {
    wrap('demo', <StaffSubNav active="dashboard" />);
    expect(screen.getByRole('link', { name: '동선 전송' })).toBeTruthy();
    expect(screen.getByRole('link', { name: '대기열 콘솔' })).toBeTruthy();
  });

  it('active="dashboard" 일 때 dashboard 탭 aria-current=page', () => {
    wrap('demo', <StaffSubNav active="dashboard" />);
    const dash = screen.getByRole('link', { name: '동선 전송' });
    const queue = screen.getByRole('link', { name: '대기열 콘솔' });
    expect(dash.getAttribute('aria-current')).toBe('page');
    expect(queue.getAttribute('aria-current')).toBeNull();
  });

  it('active="queue" 일 때 queue 탭 aria-current=page', () => {
    wrap('demo', <StaffSubNav active="queue" />);
    const dash = screen.getByRole('link', { name: '동선 전송' });
    const queue = screen.getByRole('link', { name: '대기열 콘솔' });
    expect(queue.getAttribute('aria-current')).toBe('page');
    expect(dash.getAttribute('aria-current')).toBeNull();
  });

  it('링크 href 가 슬러그를 정확히 사용', () => {
    wrap('demo', <StaffSubNav active="dashboard" />);
    expect(
      screen.getByRole('link', { name: '동선 전송' }).getAttribute('href'),
    ).toBe('/h/demo/staff');
    expect(
      screen.getByRole('link', { name: '대기열 콘솔' }).getAttribute('href'),
    ).toBe('/h/demo/staff/queue');
  });

  it('다른 슬러그 (smch) → href 도 따라 변경', () => {
    wrap('smch', <StaffSubNav active="queue" />);
    expect(
      screen.getByRole('link', { name: '동선 전송' }).getAttribute('href'),
    ).toBe('/h/smch/staff');
    expect(
      screen.getByRole('link', { name: '대기열 콘솔' }).getAttribute('href'),
    ).toBe('/h/smch/staff/queue');
  });

  it('aria-label="의료진 메뉴"', () => {
    wrap('demo', <StaffSubNav active="dashboard" />);
    expect(screen.getByRole('navigation', { name: '의료진 메뉴' })).toBeTruthy();
  });
});
