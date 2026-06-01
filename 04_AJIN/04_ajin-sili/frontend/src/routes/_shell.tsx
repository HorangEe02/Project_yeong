import { useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { TopBar } from '@components/shell/TopBar';
import { LeftSidebar } from '@components/shell/LeftSidebar';
import { RightPanel, type RightPanelMode } from '@components/shell/RightPanel';
import { ErrorBoundary } from '@components/ErrorBoundary';
import { CommandPalette } from '@components/search/CommandPalette';
import { useUIStore } from '@store/ui';
import { useAuthStore } from '@store/auth';
import { useSearchStore } from '@store/search';
import { useHotkey } from '@hooks/useHotkeys';
import { useOnlineStatus } from '@hooks/useOnlineStatus';
import { useIsMobile } from '@hooks/useBreakpoint';
import { BottomTabBar } from '@components/shell/BottomTabBar';
import { MobileDrawer } from '@components/shell/MobileDrawer';

/** 라우트별 RightPanel mode 결정 — chat 만 analytics, 나머지는 default. */
function resolveRightPanelMode(pathname: string): RightPanelMode {
  if (pathname.startsWith('/chat')) return 'analytics';
  return 'default';
}

export function Shell() {
  const rightOpen = useUIStore((s) => s.rightPanelOpen);
  const user = useAuthStore((s) => s.user);
  const location = useLocation();
  const rightMode = resolveRightPanelMode(location.pathname);

  // SYS 패널 (시스템 분석 / GPU·LATENCY·QPS·INGESTION) 은 관리자 전용.
  // 일반 사용자는 토글 상태와 무관하게 패널 자체를 비노출 → main 컬럼이 전체 폭 사용.
  const isAdmin = (user?.role_level ?? 0) >= 5;
  // v4.4 — 모바일·태블릿(≤1024px)에서 RightPanel 강제 숨김 (가로 폭 부족)
  const isMobile = useIsMobile();
  const rightVisible = isAdmin && rightOpen && !isMobile;

  // W5 — ⌘K / Ctrl+K 글로벌 명령 팔레트.
  // v4.7 Sprint 2 P0 — store.isPaletteOpen 도 함께 반영 (InputComposer "/" 트리거 경로).
  const [paletteOpen, setPaletteOpen] = useState(false);
  const storePaletteOpen = useSearchStore((s) => s.isPaletteOpen);
  const closeStorePalette = useSearchStore((s) => s.closePalette);
  const isPaletteOpen = paletteOpen || storePaletteOpen;
  const handleClosePalette = () => {
    setPaletteOpen(false);
    if (storePaletteOpen) closeStorePalette();
  };
  useHotkey(() => setPaletteOpen((v) => !v), { combo: 'meta+k', allowInInput: true });
  useHotkey(() => setPaletteOpen((v) => !v), { combo: 'ctrl+k', allowInInput: true });

  // 네트워크 오프라인/온라인 토스트 — 앱 전역 1회 마운트
  useOnlineStatus();

  return (
    <div
      className={`app-shell ${isMobile ? 'aj-mobile' : ''}`.trim()}
      data-mobile={isMobile ? 'true' : undefined}
    >
      <TopBar />
      <div className={`app-body ${rightVisible ? '' : 'no-right'}`}>
        <LeftSidebar />
        <main
          style={{
            minWidth: 0,
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column',
            paddingBottom: isMobile ? 'calc(var(--bottom-nav-h, 60px) + env(safe-area-inset-bottom, 0px) + 12px)' : 0,
          }}
        >
          {/* 페이지 단위 ErrorBoundary — 라우트 변경 시 자동 reset */}
          <ErrorBoundary key={location.pathname}>
            <Outlet />
          </ErrorBoundary>
        </main>
        {rightVisible && <RightPanel mode={rightMode} />}
      </div>
      {isMobile && <BottomTabBar />}
      {isMobile && <MobileDrawer />}
      <CommandPalette isOpen={isPaletteOpen} onClose={handleClosePalette} />
    </div>
  );
}
