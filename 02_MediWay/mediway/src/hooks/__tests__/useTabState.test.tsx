import { describe, it, expect } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { type ReactNode } from 'react';
import { useTabState } from '../useTabState';
import { DEFAULT_HOSPITAL_FEATURES } from '@/types/hospital';

function wrapper(initial: string) {
  return ({ children }: { children: ReactNode }) => (
    <MemoryRouter initialEntries={[initial]}>
      <Routes>
        <Route path="*" element={<>{children}</>} />
      </Routes>
    </MemoryRouter>
  );
}

describe('useTabState', () => {
  it('URL에 tab 없으면 home으로 fallback', () => {
    const { result } = renderHook(
      () => useTabState({ ...DEFAULT_HOSPITAL_FEATURES, appointments: true }),
      { wrapper: wrapper('/h/demo/patient/home') },
    );
    expect(result.current.activeTab).toBe('home');
  });

  it('URL에 tab=appointments & features.appointments=true 이면 반영', () => {
    const { result } = renderHook(
      () => useTabState({ ...DEFAULT_HOSPITAL_FEATURES, appointments: true }),
      {
        wrapper: wrapper('/h/demo/patient/home?tab=appointments'),
      },
    );
    expect(result.current.activeTab).toBe('appointments');
  });

  it('features flag off이면 해당 탭이 visibleTabs에서 제외 + home fallback', () => {
    const { result } = renderHook(
      () => useTabState({ ...DEFAULT_HOSPITAL_FEATURES, appointments: false }),
      {
        wrapper: wrapper('/h/demo/patient/home?tab=appointments'),
      },
    );
    expect(result.current.activeTab).toBe('home');
    expect(result.current.visibleTabs.map((t) => t.id)).not.toContain(
      'appointments',
    );
  });

  it('존재하지 않는 tab 값이면 home으로 fallback', () => {
    const { result } = renderHook(
      () => useTabState(DEFAULT_HOSPITAL_FEATURES),
      { wrapper: wrapper('/h/demo/patient/home?tab=invalid') },
    );
    expect(result.current.activeTab).toBe('home');
  });

  it('visibleTabs에는 항상 home·guide·more 포함 (always-visible 3개)', () => {
    const { result } = renderHook(
      () => useTabState(DEFAULT_HOSPITAL_FEATURES),
      { wrapper: wrapper('/h/demo/patient/home') },
    );
    const ids = result.current.visibleTabs.map((t) => t.id);
    expect(ids).toEqual(expect.arrayContaining(['home', 'guide', 'more']));
    // 모든 features false — 외래·입원·검진은 빠짐
    expect(ids).not.toContain('appointments');
    expect(ids).not.toContain('inpatient');
    expect(ids).not.toContain('checkup');
  });

  it('setTab으로 URL이 업데이트되어 activeTab 변경', () => {
    const { result } = renderHook(
      () => useTabState({ ...DEFAULT_HOSPITAL_FEATURES, appointments: true }),
      { wrapper: wrapper('/h/demo/patient/home') },
    );
    expect(result.current.activeTab).toBe('home');
    act(() => result.current.setTab('appointments'));
    expect(result.current.activeTab).toBe('appointments');
  });

  it('visibleIds에 없는 탭은 setTab으로도 변경 안 됨', () => {
    const { result } = renderHook(
      () => useTabState({ ...DEFAULT_HOSPITAL_FEATURES, appointments: false }),
      { wrapper: wrapper('/h/demo/patient/home') },
    );
    act(() => result.current.setTab('appointments'));
    expect(result.current.activeTab).toBe('home');
  });
});
