import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { HospitalTabs } from '../HospitalTabs';
import { TAB_DEFS } from '@/types/tabs';

describe('HospitalTabs', () => {
  it('전체 탭 렌더 + 현재 탭 aria-selected', () => {
    render(
      <HospitalTabs tabs={TAB_DEFS} activeTab="guide" onChange={() => {}} />,
    );
    const guideTab = screen.getByRole('tab', { name: '안내' });
    expect(guideTab.getAttribute('aria-selected')).toBe('true');

    const homeTab = screen.getByRole('tab', { name: '홈' });
    expect(homeTab.getAttribute('aria-selected')).toBe('false');
  });

  it('클릭 시 onChange(id) 호출', () => {
    const onChange = vi.fn();
    render(
      <HospitalTabs tabs={TAB_DEFS} activeTab="home" onChange={onChange} />,
    );
    fireEvent.click(screen.getByRole('tab', { name: '더보기' }));
    expect(onChange).toHaveBeenCalledWith('more');
  });

  it('빈 tabs 배열 → 아무 것도 렌더 안 됨', () => {
    const { container } = render(
      <HospitalTabs tabs={[]} activeTab="home" onChange={() => {}} />,
    );
    expect(container.querySelectorAll('[role="tab"]')).toHaveLength(0);
  });

  it('tablist 접근성 — role=tablist + aria-label', () => {
    render(
      <HospitalTabs
        tabs={TAB_DEFS}
        activeTab="home"
        onChange={() => {}}
      />,
    );
    const tablist = screen.getByRole('tablist');
    expect(tablist.getAttribute('aria-label')).toContain('탭');
  });
});
