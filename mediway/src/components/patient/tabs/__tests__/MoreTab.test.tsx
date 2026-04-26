import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { HospitalProvider } from '@/contexts/HospitalContext';
import type { HospitalProfile } from '@/types/hospital';

// 본 테스트는 history link 만 검증 — 다른 카드(고령자/알림) 는 별도 sprint 에서.

vi.mock('@/stores/authStore', () => ({
  useAuthStore: () => null,
}));

vi.mock('@/stores/preferencesStore', () => ({
  usePreferencesStore: <T,>(selector?: (s: { uiSenior: boolean; setUiSenior: () => void }) => T) =>
    selector ? selector({ uiSenior: false, setUiSenior: () => {} }) : null,
}));

vi.mock('@/stores/notificationPrefsStore', () => ({
  useNotificationPrefsStore: <T,>(
    selector?: (s: {
      prefs: Record<string, unknown>;
      initialized: boolean;
      error: null;
      init: () => void;
      cleanup: () => void;
      setChannel: () => void;
      setScenario: () => void;
      revokeAll: () => void;
      restore: () => void;
    }) => T,
  ) =>
    selector
      ? selector({
          prefs: {},
          initialized: true,
          error: null,
          init: () => {},
          cleanup: () => {},
          setChannel: () => {},
          setScenario: () => {},
          revokeAll: () => {},
          restore: () => {},
        })
      : null,
}));

import { MoreTab } from '../MoreTab';

function makeProfile(): HospitalProfile {
  return { id: 'demo', name: 'MediWay 데모', status: 'active' };
}

function renderTab(slug = 'demo') {
  return render(
    <MemoryRouter initialEntries={[`/h/${slug}/patient/home`]}>
      <Routes>
        <Route
          path="/h/:hospitalSlug/patient/home"
          element={
            <HospitalProvider value={{ slug, profile: makeProfile() }}>
              <MoreTab />
            </HospitalProvider>
          }
        />
      </Routes>
    </MemoryRouter>,
  );
}

describe('MoreTab — 방문 이력 카드 (I.4.3)', () => {
  it('"방문 이력" 카드 + 링크 표시', () => {
    renderTab();
    expect(screen.getByTestId('more-history-link')).toBeTruthy();
    expect(screen.getByText('방문 이력')).toBeTruthy();
    expect(screen.getByText('지난 방문 기록을 확인합니다.')).toBeTruthy();
  });

  it('href = /h/{slug}/patient/history (default slug)', () => {
    renderTab();
    expect(screen.getByTestId('more-history-link').getAttribute('href')).toBe(
      '/h/demo/patient/history',
    );
  });

  it('다른 slug → href 도 따라 변경', () => {
    renderTab('smch');
    expect(screen.getByTestId('more-history-link').getAttribute('href')).toBe(
      '/h/smch/patient/history',
    );
  });
});
