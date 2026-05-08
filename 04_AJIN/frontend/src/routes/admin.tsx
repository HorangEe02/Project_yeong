// admin.tsx — 기능 E (인사 관리) 6-탭 라우터.
// 모든 mock 데이터 제거 — 실 API (/admin/*) 연동.
// 디자인: AJIN AI Assistant Design System v2 (.lg-* 클래스만 사용).

import { useState } from 'react';
import { useAuthStore } from '@store/auth';
import { SecurityTab } from '@components/admin/tabs/SecurityTab';
import { UsersTab } from '@components/admin/tabs/UsersTab';
import { CreateUserTab } from '@components/admin/tabs/CreateUserTab';
import { AnalyticsTab } from '@components/admin/tabs/AnalyticsTab';
import { HRStatsTab } from '@components/admin/tabs/HRStatsTab';
import { SystemToolsTab } from '@components/admin/tabs/SystemToolsTab';
import { ScenariosTab } from '@components/admin/tabs/ScenariosTab';

type TabKey = 'security' | 'users' | 'create' | 'analytics' | 'stats' | 'scenarios' | 'tools';

interface TabDef {
  key: TabKey;
  ko: string;
  en: string;
  minLevel: number;
}

const TABS: TabDef[] = [
  { key: 'security',  ko: '보안 감사',     en: 'SECURITY',   minLevel: 4 },
  { key: 'users',     ko: '사용자',        en: 'USERS',      minLevel: 4 },
  { key: 'create',    ko: '계정 생성',     en: 'CREATE',     minLevel: 4 },
  { key: 'analytics', ko: 'AI 활용 분석',  en: 'ANALYTICS',  minLevel: 4 },
  { key: 'stats',     ko: '인사 통계',     en: 'HR STATS',   minLevel: 3 },
  { key: 'scenarios', ko: '협업 시나리오', en: 'SCENARIOS',  minLevel: 4 },
  { key: 'tools',     ko: '시스템 도구',   en: 'TOOLS',      minLevel: 5 },
];

export function Admin() {
  const auth = useAuthStore((s) => s.user);
  const myLevel = auth?.role_level ?? 1;
  const accessible = TABS.filter((t) => myLevel >= t.minLevel);
  const initial: TabKey = accessible[0]?.key ?? 'stats';
  const [active, setActive] = useState<TabKey>(initial);

  if (myLevel < 3) {
    return (
      <div style={{ padding: 24 }}>
        <div className="lg-card">
          <div className="lg-state-pill crit">권한 부족</div>
          <p style={{ marginTop: 12 }}>
            인사 관리 메뉴는 TEAM_LEAD(L3) 이상에게만 접근이 허용됩니다.
            <br />필요 시 시스템 관리자에게 문의하세요.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="page lg-page" data-screen-label="E · Admin & HR">
      <div className="lg-card-h" style={{ marginBottom: 18 }}>
        <div>
          <div className="lg-pill">FEATURE E · ADMIN</div>
          <h1 style={{ marginTop: 6, fontSize: 24, fontWeight: 700, letterSpacing: '-0.01em' }}>
            인사 관리
          </h1>
          <div style={{ fontSize: 13, color: 'var(--hud-text-dim)', marginTop: 4 }}>
            사용자 디렉터리 · 계정 발급 · 보안 감사 · AI 활용 분석 · 인사 통계 · 시스템 도구
          </div>
        </div>
        <div className="lg-role">
          {auth?.role_name ?? 'GUEST'} · L{myLevel}
        </div>
      </div>

      <div className="lg-tabs">
        {TABS.map((t) => {
          const enabled = myLevel >= t.minLevel;
          return (
            <button
              key={t.key}
              className={`lg-tab ${active === t.key ? 'on' : ''}`}
              onClick={() => enabled && setActive(t.key)}
              disabled={!enabled}
              type="button"
              title={enabled ? '' : `이 탭은 L${t.minLevel} 이상만 접근 가능합니다.`}
            >
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 1 }}>
                <span className="en">{t.en}</span>
                <span className="ko">{t.ko}</span>
              </div>
            </button>
          );
        })}
      </div>

      {active === 'security' && <SecurityTab />}
      {active === 'users' && <UsersTab />}
      {active === 'create' && <CreateUserTab />}
      {active === 'analytics' && <AnalyticsTab />}
      {active === 'stats' && <HRStatsTab />}
      {active === 'scenarios' && <ScenariosTab />}
      {active === 'tools' && <SystemToolsTab />}
    </div>
  );
}
