// RightPanel — canonical uiux/web_app/RightPanel.jsx 스타일 (TS port)
// SVG GPU gauge 42% + LATENCY/QPS metric-mini + DATA INGESTION 5 ingest-row.

import { SystemAnalyticsPanel } from '@components/analytics/SystemAnalyticsPanel';

export type RightPanelMode = 'default' | 'analytics';

interface Props {
  mode?: RightPanelMode;
}

const INGESTION = [
  { k: 'ERROR_CODES', v: '201/201', p: 1 },
  { k: 'MOLD_ASSETS', v: '25/25', p: 1 },
  { k: 'SPC_PROCESS', v: '5/5', p: 1 },
  { k: 'DRAWINGS', v: '418/418', p: 1 },
  { k: 'INSPECTIONS', v: '64/72', p: 0.89 },
] as const;

function GpuGauge({ utilization = 0.42 }: { utilization?: number }) {
  const r = 36;
  const c = 2 * Math.PI * r;
  return (
    <div className="gauge">
      <svg viewBox="0 0 96 96">
        <circle cx="48" cy="48" r={r} fill="none" stroke="var(--hud-border)" strokeWidth="6" />
        <circle
          cx="48"
          cy="48"
          r={r}
          fill="none"
          stroke="var(--hud-primary)"
          strokeWidth="6"
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - utilization)}
          transform="rotate(-90 48 48)"
          style={{ filter: 'drop-shadow(0 0 6px var(--hud-primary))' }}
        />
        <text
          x="48"
          y="50"
          textAnchor="middle"
          dominantBaseline="middle"
          fontSize="20"
          fontWeight="700"
          fill="var(--hud-primary)"
          fontFamily="var(--hud-font)"
        >
          {Math.round(utilization * 100)}%
        </text>
      </svg>
      <span className="lbl">GPU · UTILIZATION</span>
    </div>
  );
}

export function RightPanel({ mode = 'default' }: Props = {}) {
  if (mode === 'analytics') {
    return (
      <aside className="right-panel">
        <SystemAnalyticsPanel />
      </aside>
    );
  }

  return (
    <aside className="right-panel">
      <div className="sb-h">
        <span>
          SYSTEM ANALYTICS <span className="ko">시스템 분석</span>
        </span>
        <span className="pill" style={{ color: '#7FD89E' }}>
          REALTIME ●
        </span>
      </div>

      <GpuGauge utilization={0.42} />

      <div className="metric-row">
        <div className="metric-mini">
          <span className="k">LATENCY</span>
          <span className="v">
            124
            <small style={{ fontSize: 11, color: 'var(--hud-text-dim)' }}>ms</small>
          </span>
        </div>
        <div className="metric-mini">
          <span className="k">QPS</span>
          <span className="v">
            8.4
            <small style={{ fontSize: 11, color: 'var(--hud-text-dim)' }}>k</small>
          </span>
        </div>
      </div>

      <div className="sb-section">
        <div className="sb-h">
          <span>
            DATA INGESTION <span className="ko">데이터 수집</span>
          </span>
        </div>
        {INGESTION.map((row) => (
          <div className="ingest-row" key={row.k}>
            <div className="top">
              <span>{row.k}</span>
              <b>{row.v}</b>
            </div>
            <div className="bar">
              <span style={{ width: `${row.p * 100}%` }} />
            </div>
          </div>
        ))}
      </div>
    </aside>
  );
}
