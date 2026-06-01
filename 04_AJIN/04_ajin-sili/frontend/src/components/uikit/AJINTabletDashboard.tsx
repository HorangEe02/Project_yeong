// AJINTabletDashboard — iPad (641-1024px) 전용 dashboard, reference PadDashboard 패턴.
//
// reference: uiux/AJIN AI Assistant Design System/ui_kits/mobile/PadScreens.jsx::PadDashboard (L35-143)
//
// 구조:
//   .aj-pad (split layout, 280px sidebar rail / minmax(0,1fr) work area, mobile-theme.css L283)
//   ├─ rail (sidebar):
//   │   ├─ aj-brand (mark + word + ko)
//   │   ├─ 7 module nav items (Dashboard/AI Chat/Search/Draft/Compliance/Equipment/Admin)
//   │   └─ user profile card (avatar gradient + name + role)
//   └─ work area:
//       ├─ Header (Dashboard mono + 안녕하세요 + ⌘K 검색)
//       ├─ KPI strip 4-col (QUERIES TODAY / EQUIPMENT OK / SOP COVERAGE / DRAFTS PENDING)
//       ├─ 2-up panels (SPC chart 1.6fr / Compliance Critical 1fr)
//       └─ Activity LIVE list
//
// 동작 data wiring:
//   - useAuthStore → sidebar profile + greeting userName/role
//   - useEquipmentRTDB → EQUIPMENT OK KPI (97 - violations)
//   - useLocation → 현재 pathname 으로 rail-row active 표시
//   - navigate → rail-row 클릭 시 라우팅
//   - topAlarm → Compliance Critical 의 첫 항목 dynamic 표시

import { useMemo } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  Cpu,
  FileText,
  Home,
  MessageSquare,
  Search,
  Settings,
  Shield,
  Sparkles,
} from 'lucide-react';

import { useAuthStore } from '@store/auth';
import { useEquipmentRTDB } from '@hooks/useEquipmentRTDB';

export interface AJINTabletDashboardProps {
  activeAlarmsCount?: number;
  topAlarm?: {
    id: string;
    severity: string;
    title: string;
    detail: string;
    module: 'F' | 'D';
  } | null;
}

// reference PadDashboard L36-44 의 sidebar items
const RAIL_ITEMS = [
  { k: 'home',  I: Home,           ko: '대시보드', l: 'Dashboard',  path: '/' },
  { k: 'chat',  I: MessageSquare,  ko: 'AI 채팅',  l: 'AI Chat',    path: '/chat' },
  { k: 'srch',  I: Search,         ko: '검색',     l: 'Search',     path: '/search' },
  { k: 'drft',  I: FileText,       ko: '문서작성', l: 'Draft',      path: '/draft' },
  { k: 'cmpl',  I: Shield,         ko: '규제',     l: 'Compliance', path: '/compliance' },
  { k: 'eqpt',  I: Cpu,            ko: '설비 AI',  l: 'Equipment',  path: '/equipment' },
  { k: 'admn',  I: Settings,       ko: '관리자',   l: 'Admin',      path: '/admin' },
] as const;

function formatTodayDow(): string {
  const days = ['일', '월', '화', '수', '목', '금', '토'];
  const now = new Date();
  return `${days[now.getDay()]} ${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;
}

function isRouteActive(currentPath: string, itemPath: string): boolean {
  if (itemPath === '/') return currentPath === '/' || currentPath === '/dashboard';
  return currentPath === itemPath || currentPath.startsWith(itemPath + '/');
}

export function AJINTabletDashboard({
  activeAlarmsCount = 0,
  topAlarm = null,
}: AJINTabletDashboardProps) {
  const user = useAuthStore((s) => s.user);
  const navigate = useNavigate();
  const location = useLocation();
  const equipmentViolations = useEquipmentRTDB();

  const ts = useMemo(() => formatTodayDow(), []);
  const userName = user?.username || '익명';
  const userRole = (user as { position?: string })?.position || '책임';
  const userRoleLevel = user?.role_level ?? 2;
  const userAvatarLetter = userName.charAt(0);
  const userDept = user?.department || 'R&D';

  const equipmentTotal = 97;
  const equipmentOk = Math.max(0, equipmentTotal - equipmentViolations.length);
  const equipmentAlerts = equipmentViolations.length;

  // topAlarm 이 있으면 그 데이터로 SPC panel + Compliance critical 첫 줄 dynamic 화
  const spcTitle = topAlarm?.module === 'F' ? topAlarm.title : 'SPC · 사출 라인 #03';
  const spcSeverity = topAlarm?.severity || 'WARN';
  const spcTone =
    spcSeverity === 'CRITICAL' ? '#FF7565' :
    spcSeverity === 'HIGH' ? '#E8A317' :
    '#E8A317';

  const complianceTitle = topAlarm?.module === 'D' ? topAlarm.title : 'EU CBAM 2단계';

  return (
    <div className="aj-mobile" style={{ minHeight: '100vh' }}>
      <div className="aj-screen dark" style={{ position: 'relative', minHeight: '100vh' }}>
        <div className="aj-bg-grad dark" />

        <div
          className="aj-pad dark"
          style={{ position: 'relative', zIndex: 3, minHeight: '100vh' }}
        >
          {/* ===== Sidebar rail ===== */}
          <div className="rail">
            {/* Brand mark cluster */}
            <div className="aj-brand" style={{ padding: '4px 8px 14px' }}>
              <div className="mark" style={{ width: 32, height: 32, fontSize: 16 }}>A</div>
              <div>
                <div className="word" style={{ fontSize: 14 }}>
                  AJ<i>·</i>IN
                </div>
                <div className="ko" style={{ fontSize: 9 }}>
                  아진산업 · v3.5
                </div>
              </div>
            </div>

            {/* Module nav */}
            {RAIL_ITEMS.map((it) => {
              const active = isRouteActive(location.pathname, it.path);
              return (
                <div
                  key={it.k}
                  className={'rail-row' + (active ? ' on' : '')}
                  role="button"
                  tabIndex={0}
                  onClick={() => navigate(it.path)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      navigate(it.path);
                    }
                  }}
                  aria-label={`${it.ko} · ${it.l}`}
                >
                  <div className="icn">
                    <it.I size={16} />
                  </div>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: 14 }}>{it.ko}</div>
                    <div
                      className="aj-mono"
                      style={{ fontSize: 9, opacity: 0.7, marginTop: 1 }}
                    >
                      {it.l}
                    </div>
                  </div>
                </div>
              );
            })}

            <div style={{ flex: 1 }} />

            {/* User profile card */}
            <div className="aj-glass" style={{ padding: 12, borderRadius: 14 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <div
                  style={{
                    width: 36,
                    height: 36,
                    borderRadius: 999,
                    background: 'linear-gradient(135deg, #FCB132, #B57600)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontWeight: 700,
                    color: '#07090C',
                    fontSize: 14,
                  }}
                >
                  {userAvatarLetter}
                </div>
                <div style={{ minWidth: 0, flex: 1 }}>
                  <div
                    style={{
                      fontSize: 13,
                      fontWeight: 600,
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                    }}
                  >
                    {userName}
                  </div>
                  <div className="aj-mono" style={{ fontSize: 9, opacity: 0.6 }}>
                    {userDept} · L{userRoleLevel}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* ===== Work area ===== */}
          <div className="work">
            {/* Header */}
            <div
              style={{
                display: 'flex',
                alignItems: 'baseline',
                justifyContent: 'space-between',
                marginBottom: 18,
                gap: 16,
              }}
            >
              <div>
                <div
                  className="aj-mono"
                  style={{ fontSize: 10, color: 'var(--aj-gold, #FCB132)' }}
                >
                  DASHBOARD · {ts}
                </div>
                <h1
                  style={{
                    margin: '4px 0 0',
                    fontSize: 32,
                    fontWeight: 700,
                    letterSpacing: '-0.02em',
                  }}
                >
                  안녕하세요, {userName} {userRole}
                </h1>
              </div>

              {/* ⌘K search */}
              <button
                type="button"
                className="aj-glass aj-search"
                onClick={() => navigate('/search')}
                style={{
                  width: 280,
                  height: 42,
                  borderRadius: 14,
                  cursor: 'pointer',
                  background: 'rgba(255,255,255,0.06)',
                  border: '0.5px solid rgba(255,255,255,0.12)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '0 12px',
                  color: 'inherit',
                  textAlign: 'left',
                }}
                aria-label="Open search"
              >
                <Search size={16} aria-hidden style={{ opacity: 0.55 }} />
                <span
                  style={{
                    flex: 1,
                    fontSize: 14,
                    opacity: 0.55,
                    fontFamily: 'inherit',
                  }}
                >
                  검색…
                </span>
                <span
                  className="aj-mono"
                  style={{
                    fontSize: 10,
                    opacity: 0.55,
                    padding: '2px 6px',
                    borderRadius: 5,
                    background: 'rgba(255,255,255,0.06)',
                  }}
                >
                  ⌘K
                </span>
              </button>
            </div>

            {/* KPI strip 4-col */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(4, 1fr)',
                gap: 12,
                marginBottom: 14,
              }}
            >
              <Kpi k="QUERIES TODAY" v="2,847" delta="+12.4%" up />
              <Kpi
                k="EQUIPMENT OK"
                v={`${equipmentOk}/${equipmentTotal}`}
                delta={equipmentAlerts > 0 ? `${equipmentAlerts} alerts` : 'all clear'}
                down={equipmentAlerts > 0}
              />
              <Kpi k="SOP COVERAGE" v="98.2%" delta="+0.6%" up />
              <Kpi
                k="ALARMS PENDING"
                v={String(activeAlarmsCount)}
                delta={activeAlarmsCount > 0 ? 'review' : 'all clear'}
                down={activeAlarmsCount > 0}
              />
            </div>

            {/* 2-up panels — SPC chart + Compliance critical */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '1.6fr 1fr',
                gap: 12,
              }}
            >
              <div className="aj-glass" style={{ padding: 18 }}>
                <div
                  className="aj-sect-h"
                  style={{ padding: '0 0 12px' }}
                >
                  <h3 style={{ fontSize: 11 }}>{spcTitle}</h3>
                  <span
                    className="aj-mono"
                    style={{ fontSize: 10, color: spcTone }}
                  >
                    {spcSeverity === 'CRITICAL' ? 'CRITICAL' : 'NELSON R2 · WARN'}
                  </span>
                </div>
                <SparkChart />
                <div
                  style={{
                    display: 'flex',
                    gap: 18,
                    marginTop: 12,
                    fontSize: 12,
                    opacity: 0.75,
                  }}
                >
                  <span>
                    <b
                      style={{
                        fontFamily: '"JetBrains Mono", ui-monospace, monospace',
                        fontSize: 14,
                        color: '#fff',
                      }}
                    >
                      0.92
                    </b>{' '}
                    Cpk
                  </span>
                  <span>
                    <b
                      style={{
                        fontFamily: '"JetBrains Mono", ui-monospace, monospace',
                        fontSize: 14,
                        color: '#fff',
                      }}
                    >
                      62.4°C
                    </b>{' '}
                    setpt
                  </span>
                  <span>
                    <b
                      style={{
                        fontFamily: '"JetBrains Mono", ui-monospace, monospace',
                        fontSize: 14,
                        color: '#FF7565',
                      }}
                    >
                      +4.2°C
                    </b>{' '}
                    drift
                  </span>
                </div>
              </div>

              <div className="aj-glass" style={{ padding: 18 }}>
                <div className="aj-sect-h" style={{ padding: '0 0 12px' }}>
                  <h3 style={{ fontSize: 11 }}>Critical · 컴플라이언스</h3>
                  <span className="aj-mono" style={{ fontSize: 10, color: '#FF7565' }}>
                    3 ITEMS
                  </span>
                </div>
                <ComplItem ko={complianceTitle} en="D-14" tone="red" />
                <ComplItem ko="K-ESG 공시기준" en="D-32" tone="amber" />
                <ComplItem ko="IATF 16949 갱신" en="D-58" tone="amber" />
              </div>
            </div>

            {/* Activity LIVE */}
            <div className="aj-glass" style={{ padding: 18, marginTop: 12 }}>
              <div className="aj-sect-h" style={{ padding: '0 0 8px' }}>
                <h3 style={{ fontSize: 11 }}>Activity · 최근</h3>
                <span
                  className="aj-mono"
                  style={{
                    fontSize: 10,
                    color: 'var(--aj-gold, #FCB132)',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 6,
                  }}
                >
                  <span
                    style={{
                      width: 6,
                      height: 6,
                      borderRadius: 999,
                      background: 'var(--aj-gold, #FCB132)',
                      animation: 'pulse 2s infinite',
                    }}
                    aria-hidden
                  />
                  LIVE
                </span>
              </div>
              <div className="aj-divlist">
                <PadActivity
                  ts="14:18"
                  who="설비 AI"
                  what="사출 #03 SPC Nelson R2 발생"
                  tag="ALERT"
                  tone="red"
                />
                <PadActivity
                  ts="13:42"
                  who="문서 작성"
                  what="ECN-2024-0182 v3 초안 — 품질점수 92"
                  tag="DRAFT"
                />
                <PadActivity
                  ts="13:05"
                  who="컴플라이언스"
                  what="EU CBAM Q3 보고서 자동 갱신"
                  tag="GEN"
                />
                <PadActivity
                  ts="12:48"
                  who="AI 채팅"
                  what="@생산기술 SOP-MOLD-005 step 4 응답"
                  tag="CHAT"
                />
              </div>
            </div>

            {/* Quick action FAB */}
            <button
              type="button"
              onClick={() => navigate('/chat')}
              aria-label="새 AI 대화"
              style={{
                position: 'fixed',
                right: 28,
                bottom: 28,
                width: 56,
                height: 56,
                borderRadius: 999,
                background: 'linear-gradient(135deg, #FCB132, #B57600)',
                color: '#07090C',
                border: 0,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: '0 12px 36px -8px rgba(252,177,50,0.6)',
                zIndex: 20,
              }}
            >
              <Sparkles size={22} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── helpers ───

function Kpi({
  k,
  v,
  delta,
  up,
  down,
}: {
  k: string;
  v: string;
  delta: string;
  up?: boolean;
  down?: boolean;
}) {
  return (
    <div className="aj-glass aj-kpi" style={{ padding: '14px 16px' }}>
      <div className="k">{k}</div>
      <div className="v">{v}</div>
      <div className={'delta ' + (up ? 'up' : down ? 'down' : '')}>{delta}</div>
    </div>
  );
}

function ComplItem({ ko, en, tone }: { ko: string; en: string; tone: 'red' | 'amber' }) {
  const c = tone === 'red' ? '#FF7565' : '#E8A317';
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '1fr auto',
        padding: '10px 0',
        borderBottom: '0.5px solid rgba(255,255,255,0.06)',
      }}
    >
      <div style={{ fontSize: 13, fontWeight: 500 }}>{ko}</div>
      <span className="aj-mono" style={{ fontSize: 11, color: c }}>
        {en}
      </span>
    </div>
  );
}

function PadActivity({
  ts,
  who,
  what,
  tag,
  tone,
}: {
  ts: string;
  who: string;
  what: string;
  tag: string;
  tone?: 'red';
}) {
  const cls = tone === 'red' ? 'crit' : 'gold';
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '56px 1fr auto',
        gap: 10,
        padding: '12px 0',
        alignItems: 'center',
      }}
    >
      <div className="aj-mono" style={{ fontSize: 11, opacity: 0.6 }}>
        {ts}
      </div>
      <div>
        <div style={{ fontSize: 14 }}>{what}</div>
        <div style={{ fontSize: 11, opacity: 0.55, marginTop: 1 }}>{who}</div>
      </div>
      <span className={'aj-status ' + cls}>{tag}</span>
    </div>
  );
}

function SparkChart() {
  // reference PadScreens.jsx::SparkChart (L176-204) — SPC mini chart
  const pts = [62.0, 62.1, 62.2, 61.9, 62.1, 62.3, 62.5, 63.0, 63.5, 64.2, 64.8, 65.6, 66.0, 66.4];
  const min = 60;
  const max = 68;
  const w = 540;
  const h = 140;
  const x = (i: number) => 8 + (i / (pts.length - 1)) * (w - 16);
  const y = (v: number) => h - 16 - ((v - min) / (max - min)) * (h - 24);
  const path = pts.map((p, i) => (i === 0 ? 'M' : 'L') + x(i) + ',' + y(p)).join(' ');

  return (
    <svg viewBox={`0 0 ${w} ${h}`} style={{ width: '100%', height: 140 }} aria-hidden>
      <defs>
        <linearGradient id="ajin-tablet-spark-grad" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="#FCB132" stopOpacity="0.45" />
          <stop offset="100%" stopColor="#FCB132" stopOpacity="0" />
        </linearGradient>
      </defs>
      {/* USL */}
      <line x1="8" x2={w - 8} y1={y(66.0)} y2={y(66.0)} stroke="#FF7565" strokeWidth="0.7" strokeDasharray="3 4" />
      {/* LSL */}
      <line x1="8" x2={w - 8} y1={y(60.0)} y2={y(60.0)} stroke="#FF7565" strokeWidth="0.7" strokeDasharray="3 4" />
      {/* Mean */}
      <line x1="8" x2={w - 8} y1={y(63.0)} y2={y(63.0)} stroke="rgba(255,255,255,0.18)" strokeWidth="0.6" />
      <path d={`${path} L ${x(pts.length - 1)},${h - 16} L ${x(0)},${h - 16} Z`} fill="url(#ajin-tablet-spark-grad)" />
      <path d={path} fill="none" stroke="#FCB132" strokeWidth="2" />
      {pts.map((p, i) => (
        <circle
          key={i}
          cx={x(i)}
          cy={y(p)}
          r={i >= pts.length - 3 ? 4 : 2.4}
          fill={i >= pts.length - 3 ? '#FF7565' : '#FCB132'}
        />
      ))}
    </svg>
  );
}
