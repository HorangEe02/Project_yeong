import { Outlet, useLocation } from 'react-router-dom';
import { TopBar } from '@components/shell/TopBar';
import { LeftSidebar } from '@components/shell/LeftSidebar';
import { RightPanel, type RightPanelMode } from '@components/shell/RightPanel';
import { ErrorBoundary } from '@components/ErrorBoundary';
import { useUIStore } from '@store/ui';

/** 라우트별 RightPanel mode 결정 — chat 만 analytics, 나머지는 default. */
function resolveRightPanelMode(pathname: string): RightPanelMode {
  if (pathname.startsWith('/chat')) return 'analytics';
  return 'default';
}

export function Shell() {
  const rightOpen = useUIStore((s) => s.rightPanelOpen);
  const location = useLocation();
  const rightMode = resolveRightPanelMode(location.pathname);

  return (
    <div className="app-shell">
      <TopBar />
      <div className={`app-body ${rightOpen ? '' : 'no-right'}`}>
        <LeftSidebar />
        <main style={{ minWidth: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
          {/* 페이지 단위 ErrorBoundary — 라우트 변경 시 자동 reset */}
          <ErrorBoundary key={location.pathname}>
            <Outlet />
          </ErrorBoundary>
        </main>
        {rightOpen && <RightPanel mode={rightMode} />}
      </div>
    </div>
  );
}
