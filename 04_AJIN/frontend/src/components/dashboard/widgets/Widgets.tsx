// 5 위젯 variant — 디자인 시스템 v2 컨벤션 준수
//   • EN UPPERCASE + 한글 부제 페어링
//   • 2px 모서리, gold 액센트는 hero metric value 한정
//   • status: ●(채움) / ○(비움) + color
//   • Liquid Glass 미사용 (대시보드는 flat surface)

import type { CSSProperties } from 'react';
import { useNavigate } from 'react-router-dom';
import { MetricCard } from '@components/ui/MetricCard';
import type {
  WidgetSpec,
  WidgetData,
  WidgetStatus,
  WidgetTrafficLight,
} from './types';

const STATUS_COLOR: Record<WidgetStatus, string> = {
  ok: 'var(--hud-primary)',
  warn: '#F59E0B',
  crit: '#EF4444',
  idle: 'var(--hud-text-muted, #888)',
};

interface WidgetProps {
  spec: WidgetSpec;
  data: WidgetData | null;
  loading: boolean;
}

// ────────────────────────────────────────────────────────────
// Metric — 큰 숫자 + EN/KO 라벨
// ────────────────────────────────────────────────────────────
function MetricWidget({ spec, data, loading }: WidgetProps) {
  const navigate = useNavigate();
  const m = data?.metric;
  const rawValue = m?.value ?? 0;
  const numeric = typeof rawValue === 'number' ? rawValue : Number(rawValue);
  const hasTextValue = typeof rawValue === 'string' && !Number.isFinite(numeric);
  return (
    <MetricCard
      value={loading ? 0 : Number.isFinite(numeric) ? numeric : 0}
      labelEn={spec.labelEn}
      labelKo={spec.labelKo}
      secondaryValue={m?.secondary}
      status={m?.status ?? 'ok'}
      onClick={spec.link ? () => navigate(spec.link!) : undefined}
      format={hasTextValue ? () => String(rawValue) : undefined}
    />
  );
}

// ────────────────────────────────────────────────────────────
// List — 짧은 항목 N개 (라벨 + 값)
// ────────────────────────────────────────────────────────────
function ListWidget({ spec, data, loading }: WidgetProps) {
  const navigate = useNavigate();
  const items = data?.list ?? [];
  const interactive = Boolean(spec.link);
  const handle = () => spec.link && navigate(spec.link);
  return (
    <div
      className="metric-card widget-list"
      onClick={interactive ? handle : undefined}
      style={{
        borderLeft: '3px solid var(--hud-primary)',
        cursor: interactive ? 'pointer' : 'default',
        padding: '14px 16px',
        display: 'flex',
        flexDirection: 'column',
        gap: 6,
      }}
    >
      <div className="lg-eyebrow" style={{ fontSize: 10 }}>{spec.labelEn}</div>
      <div className="lg-h2" style={{ fontSize: 14, marginBottom: 4 }}>{spec.labelKo}</div>
      {loading && <div style={{ fontSize: 12, opacity: 0.6 }}>로딩 중…</div>}
      {!loading && items.length === 0 && (
        <div style={{ fontSize: 12, opacity: 0.6 }}>표시할 항목 없음</div>
      )}
      {!loading && items.slice(0, 4).map((it, i) => (
        <div key={i} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            {it.status && (
              <span style={{ color: STATUS_COLOR[it.status] }}>●</span>
            )}
            <span>{it.label}</span>
          </span>
          {it.value !== undefined && (
            <span style={{ fontWeight: 600, color: 'var(--hud-text)' }}>{it.value}</span>
          )}
        </div>
      ))}
    </div>
  );
}

// ────────────────────────────────────────────────────────────
// Gauge — 진행률 바 (Day 8/14 등)
// ────────────────────────────────────────────────────────────
function GaugeWidget({ spec, data, loading }: WidgetProps) {
  const navigate = useNavigate();
  const g = data?.gauge;
  const pct = g && g.total > 0 ? Math.min(100, Math.round((g.current / g.total) * 100)) : 0;
  const interactive = Boolean(spec.link);
  return (
    <div
      className="metric-card widget-gauge"
      onClick={interactive ? () => navigate(spec.link!) : undefined}
      style={{
        borderLeft: '3px solid var(--hud-primary)',
        cursor: interactive ? 'pointer' : 'default',
        padding: '14px 16px',
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
      }}
    >
      <div className="lg-eyebrow" style={{ fontSize: 10 }}>{spec.labelEn}</div>
      <div style={{ fontSize: 14, color: 'var(--hud-text)' }}>{spec.labelKo}</div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
        <span style={{ fontSize: 28, fontWeight: 700, color: 'var(--hud-primary)' }}>
          {loading ? '—' : g?.current ?? '—'}
        </span>
        <span style={{ fontSize: 12, opacity: 0.6 }}>
          / {g?.total ?? '—'} {g?.unit ?? ''}
        </span>
      </div>
      <div style={{
        width: '100%',
        height: 4,
        background: 'var(--hud-surface-2)',
        borderRadius: 2,
        overflow: 'hidden',
      }}>
        <div style={{
          width: `${pct}%`,
          height: '100%',
          background: 'var(--hud-primary)',
          transition: 'width 400ms ease',
        }} />
      </div>
    </div>
  );
}

// ────────────────────────────────────────────────────────────
// TrafficLight — 5공정 신호등 (●●●○●)
// ────────────────────────────────────────────────────────────
function TrafficLightWidget({ spec, data, loading }: WidgetProps) {
  const navigate = useNavigate();
  const lights: WidgetTrafficLight[] = data?.lights ?? [];
  const interactive = Boolean(spec.link);
  return (
    <div
      className="metric-card widget-lights"
      onClick={interactive ? () => navigate(spec.link!) : undefined}
      style={{
        borderLeft: '3px solid var(--hud-primary)',
        cursor: interactive ? 'pointer' : 'default',
        padding: '14px 16px',
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
      }}
    >
      <div className="lg-eyebrow" style={{ fontSize: 10 }}>{spec.labelEn}</div>
      <div style={{ fontSize: 14, color: 'var(--hud-text)' }}>{spec.labelKo}</div>
      <div style={{ display: 'flex', gap: 12, marginTop: 4, flexWrap: 'wrap' }}>
        {loading && <span style={{ fontSize: 12, opacity: 0.6 }}>로딩 중…</span>}
        {!loading && lights.length === 0 && (
          <span style={{ fontSize: 12, opacity: 0.6 }}>데이터 없음</span>
        )}
        {!loading && lights.map((l, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{ color: STATUS_COLOR[l.status], fontSize: 14 }}>●</span>
            <span style={{ fontSize: 11, color: 'var(--hud-text-dim)' }}>{l.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ────────────────────────────────────────────────────────────
// Shortcut — 큰 진입 카드 (챗봇 / 조직도 등)
// ────────────────────────────────────────────────────────────
function ShortcutWidget({ spec }: WidgetProps) {
  const navigate = useNavigate();
  if (!spec.link) return null;
  const style: CSSProperties = {
    borderLeft: '3px solid var(--hud-primary)',
    cursor: 'pointer',
    padding: '20px 16px',
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'center',
    minHeight: 96,
  };
  return (
    <div className="metric-card widget-shortcut" onClick={() => navigate(spec.link!)} style={style}>
      <div className="lg-eyebrow" style={{ fontSize: 10 }}>{spec.labelEn}</div>
      <div style={{
        fontSize: 18,
        fontWeight: 700,
        color: 'var(--hud-primary)',
        marginTop: 6,
      }}>
        {spec.labelKo} →
      </div>
    </div>
  );
}

// ────────────────────────────────────────────────────────────
// Dispatcher
// ────────────────────────────────────────────────────────────
export function WidgetRenderer(props: WidgetProps) {
  switch (props.spec.variant) {
    case 'metric':       return <MetricWidget {...props} />;
    case 'list':         return <ListWidget {...props} />;
    case 'gauge':        return <GaugeWidget {...props} />;
    case 'trafficLight': return <TrafficLightWidget {...props} />;
    case 'shortcut':     return <ShortcutWidget {...props} />;
  }
}
