// management.tsx — v4.8 F 트랙. 4 카테고리 (Users / Audit / System / Stats) wrap router.
// URL 쿼리 `?cat=users|audit|system|stats` 로 카테고리 전환.
// RBAC: users L1+ / audit L4+ / system L3+ / stats L1+. 비활성 카테고리는 탭 자체 미노출.
// `/hr` → `?cat=users`, `/admin` → `?cat=system` 으로 App.tsx 가 리다이렉트.

import { useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuthStore } from '@store/auth';
import { UsersCategory } from '@components/management/UsersCategory';
import { AuditTimeline } from '@components/management/AuditTimeline';
import { SystemHealth } from '@components/management/SystemHealth';
import { FeatureHeatmap } from '@components/management/FeatureHeatmap';

type CatKey = 'users' | 'audit' | 'system' | 'stats';

interface CatDef {
  key: CatKey;
  ko: string;
  en: string;
  minLevel: number;
}

const CATS: CatDef[] = [
  { key: 'users',  ko: '사용자',     en: 'USERS',  minLevel: 1 },
  { key: 'audit',  ko: '감사 로그',  en: 'AUDIT',  minLevel: 4 },
  { key: 'system', ko: '시스템',     en: 'SYSTEM', minLevel: 3 },
  { key: 'stats',  ko: '사용 통계',  en: 'STATS',  minLevel: 1 },
];

function readCatFromSearch(search: string): CatKey | null {
  const params = new URLSearchParams(search);
  const raw = (params.get('cat') || '').toLowerCase();
  if (raw === 'users' || raw === 'audit' || raw === 'system' || raw === 'stats') {
    return raw;
  }
  return null;
}

export function Management() {
  const auth = useAuthStore((s) => s.user);
  const myLevel = auth?.role_level ?? 1;
  const navigate = useNavigate();
  const location = useLocation();

  const accessible = useMemo(
    () => CATS.filter((c) => myLevel >= c.minLevel),
    [myLevel],
  );

  const requested = readCatFromSearch(location.search);
  const requestedDef = CATS.find((c) => c.key === requested) ?? null;
  const requestedAllowed =
    requestedDef !== null && myLevel >= requestedDef.minLevel;

  // 요청한 cat 이 권한 부족이면 첫 허용 cat 으로 redirect.
  // 요청한 cat 이 없으면 첫 허용 cat 으로 redirect (단, 이미 매치되면 noop).
  useEffect(() => {
    if (!auth) return;
    if (!requested) {
      const first = accessible[0]?.key ?? 'users';
      navigate(`/management?cat=${first}`, { replace: true });
      return;
    }
    if (!requestedAllowed) {
      const first = accessible[0]?.key ?? 'users';
      navigate(`/management?cat=${first}`, { replace: true });
    }
  }, [auth, requested, requestedAllowed, accessible, navigate]);

  const [active, setActive] = useState<CatKey>(
    requestedAllowed && requestedDef ? requestedDef.key : (accessible[0]?.key ?? 'users'),
  );

  // URL ↔ active 동기화 (사용자가 ?cat 직접 변경 시).
  useEffect(() => {
    if (requestedAllowed && requestedDef && requestedDef.key !== active) {
      setActive(requestedDef.key);
    }
  }, [requestedDef, requestedAllowed, active]);

  const handleSelect = (key: CatKey) => {
    setActive(key);
    navigate(`/management?cat=${key}`, { replace: true });
  };

  // 접근 가능한 카테고리가 하나도 없는 경우 (이론상 L1+ 라서 항상 users/stats 는 접근 가능).
  if (accessible.length === 0) {
    return (
      <div style={{ padding: 24 }}>
        <div className="lg-card">
          <div className="lg-state-pill crit">권한 부족</div>
          <p style={{ marginTop: 12 }}>
            관리 콘솔에 접근할 수 있는 카테고리가 없습니다. 시스템 관리자에게 문의하세요.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="page lg-page" data-screen-label="F · Management Console">
      <div className="lg-card-h" style={{ marginBottom: 18 }}>
        <div>
          <div className="lg-pill">FEATURE F · MANAGEMENT CONSOLE</div>
          <h1 style={{ marginTop: 6, fontSize: 24, fontWeight: 700, letterSpacing: '-0.01em' }}>
            시스템 관리
          </h1>
          <div style={{ fontSize: 13, color: 'var(--hud-text-dim)', marginTop: 4 }}>
            사용자 · 감사 로그 · 시스템 상태 · 사용 통계
          </div>
        </div>
        <div className="lg-role">
          {auth?.role_name ?? 'GUEST'} · L{myLevel}
        </div>
      </div>

      <div className="lg-tabs">
        {CATS.map((c) => {
          const enabled = myLevel >= c.minLevel;
          if (!enabled) return null;
          return (
            <button
              key={c.key}
              className={`lg-tab ${active === c.key ? 'on' : ''}`}
              onClick={() => handleSelect(c.key)}
              type="button"
              title={`L${c.minLevel}+ 카테고리`}
            >
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 1 }}>
                <span className="en">{c.en}</span>
                <span className="ko">{c.ko}</span>
              </div>
            </button>
          );
        })}
      </div>

      {active === 'users' && <UsersCategory />}
      {active === 'audit' && myLevel >= 4 && <AuditTimeline />}
      {active === 'system' && myLevel >= 3 && <SystemHealth />}
      {active === 'stats' && <FeatureHeatmap />}
    </div>
  );
}

export default Management;
