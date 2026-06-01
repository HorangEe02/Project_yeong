// admin.tsx — 기능 G · 관리자 콘솔 (PR-E4: 6→3 탭 통합).
// 3 탭: account_delegation · security_alerts · system_health
// 디자인: AJIN AI Assistant Design System v2 (.lg-* 클래스만 사용).
//
// Legacy ?tab=* 쿼리는 redirect 처리:
//   ?tab=users           → AccountDelegationTab (계정 위임)
//   ?tab=create_user     → AccountDelegationTab + IdP 위임 안내 자동 노출
//   ?tab=search_analytics → /search/analytics
//   ?tab=analytics       → /equipment?cat=stats
//   ?tab=security        → SecurityAlertsTab
//   ?tab=tools           → SystemHealthTab

import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuthStore } from '@store/auth';
import { useIsMobile } from '@hooks/useBreakpoint';
import { getLockReason } from '@lib/rbac';
import { AccountDelegationTab } from '@components/admin/tabs/AccountDelegationTab';
import { SecurityAlertsTab } from '@components/admin/tabs/SecurityAlertsTab';
import { SystemHealthTab } from '@components/admin/tabs/SystemHealthTab';
import { Tab6to3Notice } from '@components/admin/Tab6to3Notice';
import { AJINMobileAdmin } from '@components/uikit/AJINMobileAdmin';

type TabKey = 'account_delegation' | 'security_alerts' | 'system_health';

interface TabDef {
  key: TabKey;
  ko: string;
  en: string;
  minLevel: number;
}

const TABS: TabDef[] = [
  { key: 'account_delegation', ko: '계정 위임', en: 'ACCOUNT DELEGATION', minLevel: 4 },
  { key: 'security_alerts',    ko: '보안 알림', en: 'SECURITY ALERTS',    minLevel: 4 },
  { key: 'system_health',      ko: '시스템 헬스', en: 'SYSTEM HEALTH',     minLevel: 5 },
];

// Legacy 6-탭 → 3-탭 redirect 매핑.
// 외부 경로(/search/analytics 등) 로 빠지는 case 는 별도 처리.
const LEGACY_TAB_TO_NEW: Record<string, TabKey> = {
  users: 'account_delegation',
  create_user: 'account_delegation',
  create: 'account_delegation',
  security: 'security_alerts',
  tools: 'system_health',
};

const LEGACY_TAB_TO_EXTERNAL: Record<string, string> = {
  search_analytics: '/search/analytics',
  search: '/search/analytics',
  analytics: '/equipment?cat=stats',
  // PR-E8 — HRMS 폐기 + KPI 대시보드 이관 (Q3 잠정 가정 적용)
  hr_stats_legacy: '/equipment?cat=stats',
  hr: '/equipment?cat=stats',
  hr_stats: '/equipment?cat=stats',
};

export function Admin() {
  const auth = useAuthStore((s) => s.user);
  const isMobile = useIsMobile();
  const myLevel = auth?.role_level ?? 1;
  const accessible = TABS.filter((t) => myLevel >= t.minLevel);
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();

  const legacyTab = params.get('tab');
  const initialFromQuery: TabKey | null =
    legacyTab && LEGACY_TAB_TO_NEW[legacyTab] ? LEGACY_TAB_TO_NEW[legacyTab] : null;
  const initial: TabKey =
    initialFromQuery ?? accessible[0]?.key ?? 'account_delegation';
  const [active, setActive] = useState<TabKey>(initial);

  // Legacy ?tab=* 처리:
  //   1) 외부 경로로 빠지는 경우 즉시 navigate (PR-E4 redirect 정책).
  //   2) 내부 매핑 가능한 경우 새 enum 으로 교체 후 ?tab 쿼리 제거.
  useEffect(() => {
    if (!legacyTab) return;
    const external = LEGACY_TAB_TO_EXTERNAL[legacyTab];
    if (external) {
      // PR-E8 — HRMS 이관 안내 (legacy hr_stats_legacy/hr/hr_stats → KPI 대시보드)
      if (legacyTab.startsWith('hr')) {
        // 3초 후 자동 redirect — 사용자가 안내 확인 가능
        const t = setTimeout(() => navigate(external, { replace: true }), 3000);
        return () => clearTimeout(t);
      }
      navigate(external, { replace: true });
      return;
    }
    if (LEGACY_TAB_TO_NEW[legacyTab]) {
      const next = new URLSearchParams(params);
      next.delete('tab');
      setParams(next, { replace: true });
    }
    // 알 수 없는 ?tab 값은 무시 (default 탭 노출).
  }, [legacyTab, navigate, params, setParams]);

  // PR-E8 — HRMS 이관 안내 페이지
  const isHrmsLegacy = legacyTab !== null && legacyTab.startsWith('hr')
    && LEGACY_TAB_TO_EXTERNAL[legacyTab] !== undefined;
  if (isHrmsLegacy) {
    const target = LEGACY_TAB_TO_EXTERNAL[legacyTab!];
    return (
      <div style={{ padding: 24 }}>
        <div className="lg-card">
          <div className="lg-pill">HRMS 이관 안내</div>
          <h2 style={{ marginTop: 12, fontSize: 20, fontWeight: 700 }}>
            HRMS 페이지는 v4.9 부터 KPI 대시보드로 이관되었습니다
          </h2>
          <p style={{ marginTop: 12, color: 'var(--hud-text-dim)', lineHeight: 1.6 }}>
            인사 통계 / 헤드카운트 / 본부-직급 매트릭스는 설비/공정 AI 의
            <b> 통계 카테고리</b> 로 통합되었습니다.<br />
            3초 후 자동으로 이동합니다.
          </p>
          <div style={{ marginTop: 16, display: 'flex', gap: 8 }}>
            <button
              type="button"
              className="lg-btn primary"
              onClick={() => navigate(target, { replace: true })}
            >
              지금 이동 → {target}
            </button>
            <button
              type="button"
              className="lg-btn ghost"
              onClick={() => {
                const next = new URLSearchParams(params);
                next.delete('tab');
                setParams(next, { replace: true });
              }}
            >
              관리자 콘솔 유지
            </button>
          </div>
        </div>
      </div>
    );
  }

  // 권한 가드: rbac.ts MODULE_PERMISSIONS['admin'] 의 minRoleLevel(L4) + allowedDepartments
  // 5개 부서 화이트리스트 모두 통과해야 진입 가능. URL 직접 접근도 차단.
  const lockReason = getLockReason('admin', auth ?? null);
  if (lockReason) {
    return (
      <div style={{ padding: 24 }}>
        <div className="lg-card">
          <div className="lg-state-pill crit">권한 부족</div>
          <p style={{ marginTop: 12 }}>
            관리자 콘솔은 <b>L4(HR_ADMIN) 이상</b>이며 다음 부서 소속만 접근 가능합니다:
            <br />IT전략팀 · 총무인사팀 · 품질경영팀 · 내부감사팀 · 경영기획팀
            <br /><br />
            <small style={{ opacity: 0.7 }}>사유: {lockReason}</small>
            <br /><br />필요 시 시스템 관리자에게 문의하세요.
          </p>
        </div>
      </div>
    );
  }

  // 2026-05-28 — 모바일 viewport 분기. admin.tsx 데스크탑 2-column 이 모바일에서
  // 우측 컬럼 잘림 incident fix. lockReason / isHrmsLegacy 같은 early return 은
  // 데스크탑·모바일 공통이므로 그 뒤에 isMobile 분기 위치.
  if (isMobile) {
    return <AJINMobileAdmin />;
  }

  return (
    <div className="page lg-page" data-screen-label="G · Admin Console">
      <Tab6to3Notice />

      <div className="lg-card-h" style={{ marginBottom: 18 }}>
        <div>
          <div className="lg-pill">FEATURE G · ADMIN CONSOLE</div>
          <h1 style={{ marginTop: 6, fontSize: 24, fontWeight: 700, letterSpacing: '-0.01em' }}>
            관리자 콘솔
          </h1>
          <div style={{ fontSize: 13, color: 'var(--hud-text-dim)', marginTop: 4 }}>
            계정 위임 (IdP) · 보안 알림 · 시스템 헬스 — v4.9 부터 3 탭으로 단순화
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

      {active === 'account_delegation' && <AccountDelegationTab />}
      {active === 'security_alerts' && <SecurityAlertsTab />}
      {active === 'system_health' && <SystemHealthTab />}
    </div>
  );
}
