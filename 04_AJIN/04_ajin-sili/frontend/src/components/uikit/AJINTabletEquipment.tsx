// AJINTabletEquipment — iPad 전용 설비 AI.
// reference PadDashboard 패턴 (aj-pad split rail/work).
//
// 좌 rail: 8 sub-tab nav (Overview/Alerts/Equipment Type/Predictive/SPC/ML/Manual/Inspection)
// 우 work: 첫 탭 (Overview) KPI 4-tile + SparkChart + 최근 알람 list

import { useNavigate } from 'react-router-dom';
import {
  AlertTriangle,
  ChevronRight,
  ClipboardList,
  Cpu,
  FileSearch,
  Gauge,
  LayoutDashboard,
  TrendingUp,
  Wrench,
  Zap,
} from 'lucide-react';

import { useEquipmentRTDB } from '@hooks/useEquipmentRTDB';

const EQUIPMENT_TOTAL = 97;

const SUB_TABS = [
  { k: 'overview', I: LayoutDashboard, ko: '설비 개요', en: 'OVERVIEW', path: '/equipment?tab=overview&sub=overview' },
  { k: 'alerts', I: AlertTriangle, ko: '긴급 조치', en: 'ALERTS', path: '/equipment?tab=overview&sub=alerts' },
  { k: 'equipment', I: Wrench, ko: '장비 유형', en: 'EQUIPMENT', path: '/equipment?tab=overview&sub=equipment' },
  { k: 'predictive', I: TrendingUp, ko: '예측 정비', en: 'PREDICTIVE', path: '/equipment?tab=overview&sub=predictive' },
  { k: 'spc', I: Cpu, ko: 'SPC · Nelson 8', en: 'SPC', path: '/equipment?tab=overview&sub=spc' },
  { k: 'ml', I: Zap, ko: 'ML 엔진', en: 'ML', path: '/equipment?tab=overview&sub=ml' },
  { k: 'manual', I: FileSearch, ko: '매뉴얼/에러', en: 'MANUAL', path: '/equipment?tab=manual_error' },
  { k: 'inspection', I: ClipboardList, ko: '점검 이력', en: 'INSPECTION', path: '/equipment?tab=inspection' },
] as const;

export function AJINTabletEquipment() {
  const navigate = useNavigate();
  const violations = useEquipmentRTDB();
  const ok = Math.max(0, EQUIPMENT_TOTAL - violations.length);
  const alarms = violations.length;

  return (
    <div className="aj-mobile" style={{ minHeight: '100vh' }}>
      <div className="aj-screen dark" style={{ position: 'relative', minHeight: '100vh' }}>
        <div className="aj-bg-grad dark" />

        <div className="aj-pad dark" style={{ position: 'relative', zIndex: 3, minHeight: '100vh' }}>
          {/* ===== Rail ===== */}
          <div className="rail">
            <div style={{ padding: '4px 8px 12px' }}>
              <div className="aj-mono" style={{ color: 'var(--aj-gold, #FCB132)', fontSize: 10 }}>
                EQUIPMENT · F · 8 TABS
              </div>
              <div style={{ fontSize: 13, marginTop: 4, opacity: 0.65 }}>
                실시간 SPC · RAG · 점검
              </div>
            </div>

            {SUB_TABS.map((t) => (
              <div
                key={t.k}
                className={'rail-row' + (t.k === 'overview' ? ' on' : '')}
                role="button"
                tabIndex={0}
                onClick={() => navigate(t.path)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    navigate(t.path);
                  }
                }}
                aria-label={`${t.ko} · ${t.en}`}
              >
                <div className="icn">
                  <t.I size={14} aria-hidden />
                </div>
                <div>
                  <div style={{ fontWeight: 600, fontSize: 14 }}>{t.ko}</div>
                  <div className="aj-mono" style={{ fontSize: 9, opacity: 0.7, marginTop: 1 }}>
                    {t.en}
                  </div>
                </div>
              </div>
            ))}

            <div style={{ flex: 1 }} />
          </div>

          {/* ===== Work ===== */}
          <div className="work">
            <div style={{ marginBottom: 18 }}>
              <div className="aj-mono" style={{ fontSize: 10, color: 'var(--aj-gold, #FCB132)' }}>
                EQUIPMENT · OVERVIEW
              </div>
              <h1 style={{ margin: '4px 0 0', fontSize: 32, fontWeight: 700, letterSpacing: '-0.02em' }}>
                설비 AI · 라이브
              </h1>
            </div>

            {/* KPI 4-col */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(4, 1fr)',
                gap: 12,
                marginBottom: 18,
              }}
            >
              <Kpi
                k="EQUIPMENT OK"
                v={`${ok}/${EQUIPMENT_TOTAL}`}
                sub={alarms > 0 ? `${alarms} alerts` : 'all clear'}
                down={alarms > 0}
              />
              <Kpi k="MTBF" v="312h" sub="베어링 평균" up />
              <Kpi k="OEE" v="84.6%" sub="+1.2% wk" up />
              <Kpi k="DOWN TIME" v="4.2h" sub="이번주" />
            </div>

            {/* SPC chart + alarms 2-up */}
            <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: 12 }}>
              <div className="aj-glass" style={{ padding: 18 }}>
                <div className="aj-sect-h" style={{ padding: '0 0 12px' }}>
                  <h3 style={{ fontSize: 11 }}>SPC · 사출 라인 #03</h3>
                  <span className="aj-mono" style={{ fontSize: 10, color: '#E8A317' }}>
                    NELSON R2 · WARN
                  </span>
                </div>
                <SparkChart />
                <div style={{ display: 'flex', gap: 18, marginTop: 12, fontSize: 12, opacity: 0.75 }}>
                  <span>
                    <b style={{ fontFamily: '"JetBrains Mono"', fontSize: 14, color: '#fff' }}>0.92</b> Cpk
                  </span>
                  <span>
                    <b style={{ fontFamily: '"JetBrains Mono"', fontSize: 14, color: '#fff' }}>62.4°C</b> setpt
                  </span>
                  <span>
                    <b style={{ fontFamily: '"JetBrains Mono"', fontSize: 14, color: '#FF7565' }}>+4.2°C</b> drift
                  </span>
                </div>
              </div>

              <div className="aj-glass" style={{ padding: 18 }}>
                <div className="aj-sect-h" style={{ padding: '0 0 12px' }}>
                  <h3 style={{ fontSize: 11 }}>실시간 알람 · LIVE</h3>
                  <span className="aj-mono" style={{ fontSize: 10, color: alarms > 0 ? '#FF7565' : '#4FB774' }}>
                    {alarms > 0 ? `${alarms} 알람` : 'NORMAL'}
                  </span>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 4 }}>
                  {alarms === 0 && (
                    <div style={{ padding: 14, textAlign: 'center', opacity: 0.55, fontSize: 13 }}>
                      <Gauge size={16} style={{ marginRight: 6, verticalAlign: 'middle' }} />
                      전 라인 정상
                    </div>
                  )}
                  {violations.slice(0, 4).map((v, i) => (
                    <div
                      key={String(v.id ?? i)}
                      style={{
                        display: 'grid',
                        gridTemplateColumns: 'auto 1fr',
                        gap: 10,
                        padding: '8px 0',
                        borderBottom: '0.5px solid rgba(255,255,255,0.06)',
                        alignItems: 'center',
                      }}
                    >
                      <span className="aj-status crit">
                        {String(v.severity || 'warning').toUpperCase()}
                      </span>
                      <div style={{ minWidth: 0 }}>
                        <div style={{ fontSize: 13, fontWeight: 500 }}>{v.message}</div>
                        <div style={{ fontSize: 10, opacity: 0.55, marginTop: 1 }}>{v.process_name}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* 빠른 입구 row */}
            <div className="aj-glass" style={{ marginTop: 12, padding: 14 }}>
              <div className="aj-sect-h" style={{ padding: '0 0 8px' }}>
                <h3 style={{ fontSize: 11 }}>빠른 입구 · Quick</h3>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
                {SUB_TABS.slice(0, 4).map((q) => (
                  <button
                    key={q.k}
                    type="button"
                    onClick={() => navigate(q.path)}
                    className="aj-chip"
                    style={{
                      border: 0,
                      cursor: 'pointer',
                      fontFamily: 'inherit',
                      justifyContent: 'flex-start',
                      gap: 8,
                      height: 38,
                    }}
                  >
                    <q.I size={14} aria-hidden />
                    {q.ko}
                    <ChevronRight size={12} aria-hidden style={{ marginLeft: 'auto', opacity: 0.5 }} />
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function Kpi({
  k,
  v,
  sub,
  up,
  down,
}: {
  k: string;
  v: string;
  sub: string;
  up?: boolean;
  down?: boolean;
}) {
  return (
    <div className="aj-glass aj-kpi" style={{ padding: '14px 16px' }}>
      <div className="k">{k}</div>
      <div className="v">{v}</div>
      <div className={'delta ' + (up ? 'up' : down ? 'down' : '')}>{sub}</div>
    </div>
  );
}

function SparkChart() {
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
        <linearGradient id="ajin-tablet-eq-spark" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="#FCB132" stopOpacity="0.45" />
          <stop offset="100%" stopColor="#FCB132" stopOpacity="0" />
        </linearGradient>
      </defs>
      <line x1="8" x2={w - 8} y1={y(66.0)} y2={y(66.0)} stroke="#FF7565" strokeWidth="0.7" strokeDasharray="3 4" />
      <line x1="8" x2={w - 8} y1={y(60.0)} y2={y(60.0)} stroke="#FF7565" strokeWidth="0.7" strokeDasharray="3 4" />
      <line x1="8" x2={w - 8} y1={y(63.0)} y2={y(63.0)} stroke="rgba(255,255,255,0.18)" strokeWidth="0.6" />
      <path d={`${path} L ${x(pts.length - 1)},${h - 16} L ${x(0)},${h - 16} Z`} fill="url(#ajin-tablet-eq-spark)" />
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
