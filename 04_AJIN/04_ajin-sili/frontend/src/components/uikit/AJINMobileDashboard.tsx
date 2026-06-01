// AJINMobileDashboard — uiux/.../mobile/MobScreens.jsx :: MobDashboard React/TS 변환.
//
// 디자인 시스템 v3.5 의 App Store-style 모바일 dashboard 패턴 적용:
//   - .aj-mobile wrapper + .aj-screen + .aj-bg-grad
//   - MobShellTop (greeting + name + timestamp)
//   - .aj-as-hero (Story of the day) — 최우선 알람 또는 KPI 강조
//   - .aj-grid-2 + .aj-glass.aj-kpi (2-col KPI strip)
//   - .aj-glass.aj-toast (실시간 알람 토스트)
//   - .aj-as-sect (App Store section header)
//   - .aj-glass.aj-divlist (모듈 list with ModRow)
//   - 최근 활동 list
//
// dashboard.tsx 에서 isMobile && data-neural="on" 시 본 컴포넌트 렌더.

import { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AlertTriangle,
  ChevronRight,
  Cpu,
  FileText,
  MessageSquare,
  Search,
  Shield,
} from 'lucide-react';

import { useAuthStore } from '@store/auth';
import { useEquipmentRTDB } from '@hooks/useEquipmentRTDB';

export interface AJINMobileDashboardProps {
  /** 알람 합 + topAlarm + 사용자 데이터 — dashboard.tsx 가 prop 으로 전달 */
  activeAlarmsCount?: number;
  topAlarm?: {
    id: string;
    severity: string;
    title: string;
    detail: string;
    module: 'F' | 'D';
  } | null;
}

function formatGreetingDate(): string {
  const days = ['일', '월', '화', '수', '목', '금', '토'];
  const now = new Date();
  const dow = days[now.getDay()];
  const m = now.getMonth() + 1;
  const d = now.getDate();
  return `${dow}요일, ${m}월 ${d}일`;
}

function formatTimestamp(): string {
  const now = new Date();
  return now.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', hour12: false });
}

export function AJINMobileDashboard({
  activeAlarmsCount = 0,
  topAlarm = null,
}: AJINMobileDashboardProps) {
  const user = useAuthStore((s) => s.user);
  const navigate = useNavigate();
  const equipmentViolations = useEquipmentRTDB();

  const greeting = useMemo(() => formatGreetingDate(), []);
  const ts = useMemo(() => formatTimestamp(), []);
  const userName = user?.username || '익명';
  const userRole = (user as { position?: string })?.position || '책임';

  const equipmentOk = equipmentViolations.length;
  const heroSeverity = topAlarm?.severity || 'CRITICAL';
  const heroTitle = topAlarm?.title || '오늘의 인사이트';
  const heroDetail = topAlarm?.detail || 'SPC 정상 가동 — 알람 0건';
  const heroAccent =
    heroSeverity === 'CRITICAL' ? 'var(--hud-red, #C0392B)' :
    heroSeverity === 'HIGH' ? 'var(--hud-orange, #E8A317)' :
    'var(--hud-primary, #FCB132)';

  const handleNavigate = (path: string) => () => navigate(path);

  return (
    <div className="aj-mobile" style={{ minHeight: '100vh' }}>
      <div className="aj-screen dark" style={{ position: 'relative' }}>
        <div className="aj-bg-grad dark" />

        {/* MobShellTop — aj-brand mark + greeting + name (reference MobScreens.jsx L28-51) */}
        <div
          style={{
            position: 'relative',
            zIndex: 3,
            padding: '12px 20px 4px',
          }}
        >
          {/* Brand mark + timestamp row */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <div className="aj-brand">
              <div className="mark">A</div>
              <div>
                <div className="word">
                  AJ<i>·</i>IN
                </div>
                <div className="ko">아진산업</div>
              </div>
            </div>
            <div className="aj-mono" style={{ fontSize: 10, opacity: 0.65, textAlign: 'right' }}>
              {ts} KST
            </div>
          </div>

          {/* Greeting + name hero */}
          <div style={{ marginTop: 14 }}>
            <div className="aj-mono" style={{ fontSize: 10, opacity: 0.6, letterSpacing: '0.1em' }}>
              {greeting}
            </div>
            <h1
              style={{
                margin: '6px 0 4px',
                fontSize: 26,
                fontWeight: 700,
                lineHeight: 1.18,
                letterSpacing: '-0.012em',
              }}
            >
              안녕하세요,<br />
              <span style={{ color: 'var(--hud-primary, #FCB132)' }}>{userName}</span> {userRole}님
            </h1>
          </div>
        </div>

        <div className="aj-scroll" style={{ position: 'relative', zIndex: 3, marginTop: 14 }}>
          {/* App-Store-style HERO of the day — 최우선 알람 */}
          <div style={{ padding: '4px 12px 16px' }}>
            <div
              className="aj-as-hero"
              role="button"
              onClick={topAlarm ? handleNavigate(topAlarm.module === 'F' ? '/equipment' : '/compliance') : undefined}
              style={{
                cursor: topAlarm ? 'pointer' : 'default',
                position: 'relative',
                borderRadius: 'var(--aj-radius, 22px)',
                overflow: 'hidden',
                background: 'linear-gradient(135deg, color-mix(in oklab, ' + heroAccent + ' 30%, var(--hud-surface)) 0%, var(--hud-surface) 70%)',
                border: `1px solid color-mix(in oklab, ${heroAccent} 30%, transparent)`,
                padding: '20px 22px',
                minHeight: 160,
              }}
            >
              <div
                className="overline"
                style={{
                  fontSize: 10,
                  letterSpacing: '0.18em',
                  fontWeight: 600,
                  color: heroAccent,
                  marginBottom: 8,
                  textTransform: 'uppercase',
                }}
              >
                {heroSeverity === 'CRITICAL' ? '긴급 · STORY OF THE DAY' : '오늘의 인사이트 · STORY'}
              </div>
              <div
                className="ttl"
                style={{ fontSize: 20, fontWeight: 700, lineHeight: 1.22, marginBottom: 6 }}
              >
                {heroTitle}
              </div>
              <div className="sub" style={{ fontSize: 12, opacity: 0.78, marginBottom: 14 }}>
                {heroDetail}
              </div>
              <div
                className="cta"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 12,
                  padding: '10px 12px',
                  borderRadius: 14,
                  background: 'rgba(255, 255, 255, 0.06)',
                  border: '1px solid rgba(255, 255, 255, 0.08)',
                }}
              >
                <div
                  className="ico-tile"
                  style={{
                    width: 36,
                    height: 36,
                    borderRadius: 10,
                    background: `color-mix(in oklab, ${heroAccent} 25%, transparent)`,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: heroAccent,
                  }}
                >
                  {topAlarm?.module === 'D' ? <Shield size={20} /> : <AlertTriangle size={20} />}
                </div>
                <div className="meta" style={{ flex: 1 }}>
                  <div className="t" style={{ fontSize: 13, fontWeight: 600 }}>
                    {topAlarm?.module === 'D' ? '법규 모니터 · Compliance' : '설비 AI · Equipment'}
                  </div>
                  <div className="s" style={{ fontSize: 11, opacity: 0.6 }}>
                    {activeAlarmsCount}건 진행 중 · 실시간 분석
                  </div>
                </div>
                <button
                  type="button"
                  className="get"
                  style={{
                    padding: '6px 14px',
                    borderRadius: 999,
                    background: heroAccent,
                    border: 'none',
                    color: '#0E1218',
                    fontSize: 12,
                    fontWeight: 700,
                    cursor: 'pointer',
                  }}
                >
                  열기
                </button>
              </div>
            </div>
          </div>

          {/* KPI strip — 2 columns */}
          <div
            className="aj-grid-2"
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr',
              gap: 10,
              padding: '0 12px 6px',
            }}
          >
            <div
              className="aj-glass aj-kpi"
              style={{
                padding: '14px 16px',
                borderRadius: 'var(--aj-radius, 22px)',
                background: 'rgba(255, 255, 255, 0.05)',
                border: '1px solid rgba(255, 255, 255, 0.08)',
                backdropFilter: 'blur(var(--lg-blur, 36px)) saturate(var(--lg-sat, 1.8))',
                WebkitBackdropFilter: 'blur(var(--lg-blur, 36px)) saturate(var(--lg-sat, 1.8))',
              }}
            >
              <div
                className="k"
                style={{ fontSize: 10, letterSpacing: '0.14em', opacity: 0.6, textTransform: 'uppercase' }}
              >
                ALARMS TODAY
              </div>
              <div className="v" style={{ fontSize: 28, fontWeight: 700, marginTop: 4 }}>
                {activeAlarmsCount}
                <i style={{ fontSize: 12, opacity: 0.5, marginLeft: 4, fontStyle: 'normal' }}>건</i>
              </div>
              <div
                className="delta"
                style={{ fontSize: 11, color: 'var(--hud-orange, #E8A317)', marginTop: 4 }}
              >
                실시간 알람 합
              </div>
            </div>
            <div
              className="aj-glass aj-kpi"
              style={{
                padding: '14px 16px',
                borderRadius: 'var(--aj-radius, 22px)',
                background: 'rgba(255, 255, 255, 0.05)',
                border: '1px solid rgba(255, 255, 255, 0.08)',
                backdropFilter: 'blur(var(--lg-blur, 36px)) saturate(var(--lg-sat, 1.8))',
                WebkitBackdropFilter: 'blur(var(--lg-blur, 36px)) saturate(var(--lg-sat, 1.8))',
              }}
            >
              <div
                className="k"
                style={{ fontSize: 10, letterSpacing: '0.14em', opacity: 0.6, textTransform: 'uppercase' }}
              >
                EQUIPMENT SPC
              </div>
              <div className="v" style={{ fontSize: 28, fontWeight: 700, marginTop: 4 }}>
                {equipmentOk === 0 ? 'OK' : equipmentOk}
                {equipmentOk > 0 && (
                  <i style={{ fontSize: 12, opacity: 0.5, marginLeft: 4, fontStyle: 'normal' }}>위반</i>
                )}
              </div>
              <div
                className="delta"
                style={{
                  fontSize: 11,
                  color: equipmentOk === 0 ? 'var(--hud-green, #2D8A4E)' : 'var(--hud-red, #C0392B)',
                  marginTop: 4,
                }}
              >
                {equipmentOk === 0 ? '정상 가동 중' : `${equipmentOk}건 위반`}
              </div>
            </div>
          </div>

          {/* Modules section header (App Store style) */}
          <div
            className="aj-as-sect"
            style={{
              display: 'flex',
              alignItems: 'flex-end',
              justifyContent: 'space-between',
              padding: '24px 20px 12px',
            }}
          >
            <div>
              <div
                className="label"
                style={{
                  fontSize: 10,
                  letterSpacing: '0.14em',
                  color: 'var(--hud-primary, #FCB132)',
                  fontWeight: 600,
                  marginBottom: 4,
                  textTransform: 'uppercase',
                }}
              >
                MODULES · 모듈
              </div>
              <h2 style={{ fontSize: 22, fontWeight: 700, margin: 0, letterSpacing: '-0.012em' }}>
                업무에 필요한 모든 것
              </h2>
            </div>
            <span
              className="more"
              style={{ fontSize: 12, color: 'var(--hud-primary, #FCB132)', cursor: 'pointer' }}
              onClick={handleNavigate('/profile')}
            >
              전체
            </span>
          </div>

          {/* Module list — App Store divlist */}
          <div
            className="aj-glass aj-divlist"
            style={{
              margin: '0 12px',
              borderRadius: 'var(--aj-radius, 22px)',
              background: 'rgba(255, 255, 255, 0.04)',
              border: '1px solid rgba(255, 255, 255, 0.06)',
              backdropFilter: 'blur(var(--lg-blur, 36px)) saturate(var(--lg-sat, 1.8))',
              WebkitBackdropFilter: 'blur(var(--lg-blur, 36px)) saturate(var(--lg-sat, 1.8))',
              overflow: 'hidden',
            }}
          >
            <ModRow icon={<MessageSquare size={20} />} ko="AI 채팅"   en="CHAT · NLU"       meta="Streaming"   onClick={handleNavigate('/chat')} />
            <ModRow icon={<Search size={20} />}         ko="문서 검색" en="SEARCH · HYBRID"  meta="bge-m3"      onClick={handleNavigate('/search')} />
            <ModRow icon={<FileText size={20} />}       ko="문서 작성" en="DRAFT · GEN-AI"   meta="few-shot"    onClick={handleNavigate('/draft')} />
            <ModRow icon={<Shield size={20} />}         ko="규제 모니터" en="COMPLIANCE"     meta={`${activeAlarmsCount}건`} onClick={handleNavigate('/compliance')} />
            <ModRow icon={<Cpu size={20} />}            ko="설비 AI"   en="EQUIPMENT"        meta={equipmentOk === 0 ? 'OK' : `${equipmentOk} 위반`} onClick={handleNavigate('/equipment')} last />
          </div>

          {/* Bottom spacer for BottomTabBar */}
          <div style={{ height: 120 }} />
        </div>
      </div>
    </div>
  );
}

function ModRow({
  icon,
  ko,
  en,
  meta,
  onClick,
  last,
}: {
  icon: React.ReactNode;
  ko: string;
  en: string;
  meta: string;
  onClick?: () => void;
  last?: boolean;
}) {
  return (
    <div
      className="aj-row"
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') onClick?.(); }}
      style={{
        display: 'grid',
        gridTemplateColumns: '44px 1fr auto',
        gap: 12,
        alignItems: 'center',
        padding: '14px 16px',
        cursor: 'pointer',
        borderBottom: last ? 'none' : '0.5px solid rgba(255, 255, 255, 0.07)',
        transition: 'background 200ms ease-out',
      }}
    >
      <div
        className="ico"
        style={{
          width: 36,
          height: 36,
          borderRadius: 10,
          background: 'rgba(252, 177, 50, 0.12)',
          color: 'var(--hud-primary, #FCB132)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        {icon}
      </div>
      <div>
        <div className="ko" style={{ fontSize: 14, fontWeight: 600 }}>{ko}</div>
        <div
          className="en aj-mono"
          style={{
            fontSize: 10,
            opacity: 0.55,
            letterSpacing: '0.08em',
            marginTop: 1,
            textTransform: 'uppercase',
          }}
        >
          {en}
        </div>
      </div>
      <div
        className="meta"
        style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, opacity: 0.7 }}
      >
        {meta}
        <ChevronRight size={14} aria-hidden />
      </div>
    </div>
  );
}
