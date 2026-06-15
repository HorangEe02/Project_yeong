// AJINMobileAdmin — iPhone 모바일 관리자 콘솔.
// reference: AJINMobileCompliance.tsx 의 .aj-screen / .aj-bg-grad / .aj-scroll 패턴.
//
// 2026-05-28 신규 — 기존 admin.tsx 가 desktop 2-column 그대로 모바일에 노출되어
// USERS 탭 (조직 트리 + 전체 사용자) 우측 컬럼 잘림 / AUDIT 탭 (필터 + 타임라인)
// 우측 잘림 incident. 모바일은 단일 column read-only 요약 + "데스크탑에서 자세히"
// 안내로 단순화.
//
// 구조:
//   .aj-screen.dark > .aj-bg-grad.dark > .aj-scroll
//   ├─ Header (aj-mono FEATURE G · ADMIN + h1 관리자 콘솔 + role pill)
//   ├─ Tab strip (USERS / AUDIT / SYSTEM)
//   └─ Tab content (현재 active 만):
//      ├─ USERS  : 총 사용자 수 + 부서 카운트 top 5 + 최근 권한 변경 안내
//      ├─ AUDIT  : 최근 감사 이벤트 5건
//      └─ SYSTEM : DB / LLM / 디스크 / 감사 sink 헬스 카드

import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertTriangle, Database, ShieldCheck, Users } from 'lucide-react';

import { useAuthStore } from '@store/auth';

type TabKey = 'users' | 'audit' | 'system';

interface TabDef {
  key: TabKey;
  ko: string;
  en: string;
  minLevel: number;
  icon: typeof Users;
}

const TABS: TabDef[] = [
  { key: 'users',  ko: '사용자',     en: 'USERS',  minLevel: 4, icon: Users },
  { key: 'audit',  ko: '감사 로그',  en: 'AUDIT',  minLevel: 4, icon: ShieldCheck },
  { key: 'system', ko: '시스템',     en: 'SYSTEM', minLevel: 5, icon: Database },
];

interface AdminUserItem {
  employee_id: string;
  username?: string;
  department?: string;
  role_name?: string;
}

interface SecurityAlertItem {
  id: string | number;
  kind?: string;
  message?: string;
  created_at?: string;
}

interface SystemHealthState {
  // 백엔드 SystemHealthResponse (schemas/admin.py) 와 필드명 일치.
  auth_db_ok?: boolean;
  employees_db_ok?: boolean;
  audit_db_ok?: boolean;
  seed_users?: number;
  active_sessions?: number;
}

export function AJINMobileAdmin() {
  const navigate = useNavigate();
  const auth = useAuthStore((s) => s.user);
  const myLevel = auth?.role_level ?? 1;
  const accessible = TABS.filter((t) => myLevel >= t.minLevel);
  const [active, setActive] = useState<TabKey>(accessible[0]?.key ?? 'users');

  const [users, setUsers] = useState<AdminUserItem[]>([]);
  const [alerts, setAlerts] = useState<SecurityAlertItem[]>([]);
  const [health, setHealth] = useState<SystemHealthState | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    (async () => {
      try {
        const headers = { 'X-Requested-With': 'XMLHttpRequest' };
        const [u, a, h] = await Promise.allSettled([
          fetch('/api/admin/users?status=active&limit=200', { credentials: 'include', headers }).then((r) => r.json()),
          fetch('/api/admin/security/alerts?limit=5', { credentials: 'include', headers }).then((r) => r.json()),
          fetch('/api/admin/system/health', { credentials: 'include', headers }).then((r) => r.json()),
        ]);
        if (!alive) return;
        if (u.status === 'fulfilled' && Array.isArray(u.value?.users)) {
          setUsers(u.value.users);
        }
        if (a.status === 'fulfilled' && Array.isArray(a.value?.alerts)) {
          setAlerts(a.value.alerts);
        }
        if (h.status === 'fulfilled' && h.value && typeof h.value === 'object') {
          setHealth(h.value);
        }
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  const totalUsers = users.length;
  const deptCounts = aggregateDept(users).slice(0, 5);

  return (
    <div className="aj-mobile" style={{ minHeight: '100vh' }}>
      <div className="aj-screen dark" style={{ position: 'relative', minHeight: '100vh' }}>
        <div className="aj-bg-grad dark" />

        <div
          className="aj-scroll"
          style={{
            paddingTop: 18,
            paddingBottom: 120,
            position: 'relative',
            zIndex: 3,
            minHeight: '100vh',
          }}
        >
          {/* Header */}
          <div style={{ padding: '12px 20px 4px' }}>
            <div className="aj-mono" style={{ color: 'var(--aj-gold, #FCB132)' }}>
              FEATURE G · ADMIN CONSOLE
            </div>
            <h1
              style={{
                margin: '6px 0 4px',
                fontSize: 28,
                fontWeight: 700,
                letterSpacing: '-0.018em',
              }}
            >
              관리자 콘솔
            </h1>
            <div style={{ fontSize: 13, opacity: 0.65 }}>
              계정 위임 · 감사 로그 · 시스템 헬스
            </div>
            <div style={{ marginTop: 10 }}>
              <span className="aj-chip gold" style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                {auth?.role_name ?? 'GUEST'} · L{myLevel}
              </span>
            </div>
          </div>

          {/* Tab strip */}
          <div
            style={{
              display: 'flex',
              gap: 6,
              padding: '14px 16px 4px',
              overflowX: 'auto',
              scrollbarWidth: 'none',
            }}
          >
            {accessible.map((t) => {
              const isActive = t.key === active;
              const Icon = t.icon;
              return (
                <button
                  key={t.key}
                  type="button"
                  onClick={() => setActive(t.key)}
                  className={'aj-chip' + (isActive ? ' gold' : '')}
                  style={{
                    border: 0,
                    cursor: 'pointer',
                    whiteSpace: 'nowrap',
                    fontFamily: 'inherit',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 6,
                  }}
                  aria-pressed={isActive}
                >
                  <Icon size={14} aria-hidden />
                  <span>{t.en} · {t.ko}</span>
                </button>
              );
            })}
          </div>

          {accessible.length === 0 && (
            <div className="aj-glass" style={{ margin: '16px 16px 0', padding: 18, fontSize: 13, opacity: 0.75 }}>
              <AlertTriangle size={14} style={{ marginRight: 6, verticalAlign: 'middle' }} />
              관리자 콘솔 접근 권한이 없습니다. L4 이상 + 화이트리스트 부서가 필요합니다.
            </div>
          )}

          {/* USERS tab */}
          {active === 'users' && (
            <>
              <div className="aj-grid-2" style={{ paddingTop: 12 }}>
                <div className="aj-glass aj-kpi">
                  <div className="k">총 사용자</div>
                  <div className="v">{loading ? '—' : totalUsers}</div>
                  <div className="delta">active only</div>
                </div>
                <div className="aj-glass aj-kpi">
                  <div className="k">부서</div>
                  <div className="v">{loading ? '—' : deptCounts.length}</div>
                  <div className="delta">상위 {deptCounts.length}</div>
                </div>
              </div>
              <div className="aj-sect-h">
                <h3>부서별 사용자 (상위 5)</h3>
              </div>
              <div className="aj-glass aj-divlist" style={{ margin: '0 12px' }}>
                {loading && (
                  <div style={{ padding: 18, textAlign: 'center', opacity: 0.6, fontSize: 13 }}>불러오는 중…</div>
                )}
                {!loading && deptCounts.length === 0 && (
                  <div style={{ padding: 18, textAlign: 'center', opacity: 0.6, fontSize: 13 }}>표시할 데이터가 없습니다.</div>
                )}
                {!loading && deptCounts.map((d) => (
                  <div
                    key={d.dept}
                    style={{
                      display: 'grid',
                      gridTemplateColumns: '1fr auto',
                      padding: '12px 14px',
                      alignItems: 'center',
                    }}
                  >
                    <span style={{ fontSize: 14 }}>{d.dept}</span>
                    <span style={{ fontVariantNumeric: 'tabular-nums', opacity: 0.75 }}>{d.count}명</span>
                  </div>
                ))}
              </div>
              <DesktopHint label="부서 트리 / 사용자 권한 위임 / IdP 매핑은 데스크탑에서" />
            </>
          )}

          {/* AUDIT tab */}
          {active === 'audit' && (
            <>
              <div className="aj-sect-h">
                <h3>최근 보안 알림</h3>
              </div>
              <div className="aj-glass aj-divlist" style={{ margin: '0 12px' }}>
                {loading && (
                  <div style={{ padding: 18, textAlign: 'center', opacity: 0.6, fontSize: 13 }}>불러오는 중…</div>
                )}
                {!loading && alerts.length === 0 && (
                  <div style={{ padding: 18, textAlign: 'center', opacity: 0.6, fontSize: 13 }}>
                    <ShieldCheck size={14} style={{ marginRight: 6, verticalAlign: 'middle' }} />
                    최근 보안 알림 없음
                  </div>
                )}
                {!loading && alerts.slice(0, 5).map((a) => (
                  <div
                    key={a.id}
                    style={{
                      display: 'grid',
                      gridTemplateColumns: '1fr auto',
                      gap: 8,
                      padding: '12px 14px',
                    }}
                  >
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 2 }}>
                        {a.kind ?? 'security_event'}
                      </div>
                      <div style={{ fontSize: 12, opacity: 0.7, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {a.message ?? '—'}
                      </div>
                    </div>
                    <div style={{ fontSize: 11, opacity: 0.55, whiteSpace: 'nowrap' }}>
                      {formatTime(a.created_at)}
                    </div>
                  </div>
                ))}
              </div>
              <DesktopHint label="필터 / 타임라인 / SIEM export 는 데스크탑에서" />
            </>
          )}

          {/* SYSTEM tab */}
          {active === 'system' && (
            <>
              <div className="aj-grid-2" style={{ paddingTop: 12 }}>
                <HealthCard label="인증 DB"   state={health?.auth_db_ok} />
                <HealthCard label="직원 DB"   state={health?.employees_db_ok} />
                <HealthCard label="감사 DB"   state={health?.audit_db_ok} />
                <div className="aj-glass aj-kpi">
                  <div className="k">계정 · 세션</div>
                  <div className="v" style={{ fontSize: 22 }}>{loading ? '—' : (health?.seed_users ?? 0)}</div>
                  <div className="delta">활성 세션 {loading ? '—' : (health?.active_sessions ?? 0)}</div>
                </div>
              </div>
              <DesktopHint label="백업 트리거 / 감사 로그 검색 / IdP 헬스 상세는 데스크탑에서" />
            </>
          )}

          <div style={{ padding: '20px 16px 0' }}>
            <button
              type="button"
              onClick={() => navigate('/')}
              className="aj-chip"
              style={{ border: 0, cursor: 'pointer', fontFamily: 'inherit' }}
            >
              ← 대시보드로
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function aggregateDept(users: AdminUserItem[]): { dept: string; count: number }[] {
  const map = new Map<string, number>();
  for (const u of users) {
    const dept = u.department || '(미지정)';
    map.set(dept, (map.get(dept) ?? 0) + 1);
  }
  return [...map.entries()]
    .map(([dept, count]) => ({ dept, count }))
    .sort((a, b) => b.count - a.count);
}

function formatTime(iso?: string): string {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return '';
    return d.toLocaleString('ko-KR', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
  } catch {
    return '';
  }
}

function HealthCard({ label, state, hint }: { label: string; state: boolean | undefined; hint?: string }) {
  const color =
    state === true ? '#4FB774' :
    state === false ? '#FF7565' :
    'rgba(255,255,255,0.55)';
  const text =
    state === true ? 'OK' :
    state === false ? 'FAIL' :
    '—';
  return (
    <div className="aj-glass aj-kpi">
      <div className="k">{label}</div>
      <div className="v" style={{ color, fontSize: 22 }}>{text}</div>
      {hint && <div className="delta">{hint}</div>}
    </div>
  );
}

function DesktopHint({ label }: { label: string }) {
  return (
    <div
      className="aj-glass"
      style={{
        margin: '16px 16px 0',
        padding: '12px 14px',
        fontSize: 12,
        opacity: 0.7,
        textAlign: 'center',
      }}
    >
      💡 {label}
    </div>
  );
}
