import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { HospitalTabs } from '../HospitalTabs';
import { TAB_DEFS } from '@/types/tabs';

/**
 * C10 WAI-ARIA Tabs pattern 키보드 내비게이션 검증.
 * https://www.w3.org/WAI/ARIA/apg/patterns/tabs/
 */
describe('HospitalTabs keyboard navigation', () => {
  it('ArrowRight → 다음 탭', () => {
    const onChange = vi.fn();
    render(
      <HospitalTabs tabs={TAB_DEFS} activeTab="home" onChange={onChange} />,
    );
    fireEvent.keyDown(screen.getByRole('tablist'), { key: 'ArrowRight' });
    expect(onChange).toHaveBeenCalledWith('appointments');
  });

  it('ArrowLeft → 이전 탭', () => {
    const onChange = vi.fn();
    render(
      <HospitalTabs
        tabs={TAB_DEFS}
        activeTab="appointments"
        onChange={onChange}
      />,
    );
    fireEvent.keyDown(screen.getByRole('tablist'), { key: 'ArrowLeft' });
    expect(onChange).toHaveBeenCalledWith('home');
  });

  it('ArrowRight wrap-around (마지막 → 첫번째)', () => {
    const onChange = vi.fn();
    render(
      <HospitalTabs tabs={TAB_DEFS} activeTab="more" onChange={onChange} />,
    );
    fireEvent.keyDown(screen.getByRole('tablist'), { key: 'ArrowRight' });
    expect(onChange).toHaveBeenCalledWith('home');
  });

  it('Home → 첫번째 탭', () => {
    const onChange = vi.fn();
    render(
      <HospitalTabs tabs={TAB_DEFS} activeTab="guide" onChange={onChange} />,
    );
    fireEvent.keyDown(screen.getByRole('tablist'), { key: 'Home' });
    expect(onChange).toHaveBeenCalledWith('home');
  });

  it('End → 마지막 탭', () => {
    const onChange = vi.fn();
    render(
      <HospitalTabs tabs={TAB_DEFS} activeTab="home" onChange={onChange} />,
    );
    fireEvent.keyDown(screen.getByRole('tablist'), { key: 'End' });
    expect(onChange).toHaveBeenCalledWith('more');
  });

  it('active 탭만 tabIndex=0 (roving tabindex)', () => {
    render(
      <HospitalTabs
        tabs={TAB_DEFS}
        activeTab="guide"
        onChange={() => {}}
      />,
    );
    const guideTab = screen.getByRole('tab', { name: '안내' });
    const homeTab = screen.getByRole('tab', { name: '홈' });
    expect(guideTab.getAttribute('tabindex')).toBe('0');
    expect(homeTab.getAttribute('tabindex')).toBe('-1');
  });
});
