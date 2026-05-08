// v3.3 Phase F — ComplianceCard: 규제·컴플라이언스 조회 결과 (Module D).

import type { ComplianceCardPayload } from './types';

interface Props {
  payload: ComplianceCardPayload;
  onOpen?: (url: string) => void;
}

function severityColor(sev: string): string {
  switch (sev.toUpperCase()) {
    case 'CRITICAL': return 'var(--hud-red)';
    case 'HIGH':     return 'var(--hud-orange)';
    case 'MEDIUM':   return 'var(--hud-yellow, var(--hud-primary))';
    default:         return 'var(--hud-text-dim)';
  }
}

export function ComplianceCard({ payload, onOpen }: Props) {
  const handleOpen = () => {
    if (!payload.full_view_url) return;
    if (onOpen) {
      onOpen(payload.full_view_url);
    } else {
      window.location.assign(payload.full_view_url);
    }
  };

  const sevColor = severityColor(payload.severity);
  const dday = payload.days_until_effective;

  return (
    <div className="lg-action-card" data-kind="compliance">
      <div className="lg-eyebrow">
        COMPLIANCE
        {payload.regulation_id && <span className="lg-meta">{payload.regulation_id}</span>}
      </div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
        <strong style={{ fontSize: 14, color: 'var(--hud-text)' }}>{payload.title}</strong>
        {payload.severity && (
          <span
            style={{
              padding: '2px 8px',
              borderRadius: 999,
              fontFamily: 'var(--hud-font-mono)',
              fontSize: 10,
              fontWeight: 600,
              letterSpacing: '0.08em',
              color: sevColor,
              background: `color-mix(in oklab, ${sevColor} 14%, transparent)`,
              border: `1px solid color-mix(in oklab, ${sevColor} 35%, transparent)`,
            }}
          >
            {payload.severity}
          </span>
        )}
        {dday !== null && dday !== undefined && (
          <span className="lg-meta">
            {dday >= 0 ? `D-${dday}` : `D+${Math.abs(dday)}`}
            {payload.effective_date && ` · ${payload.effective_date}`}
          </span>
        )}
      </div>
      {payload.excerpt && (
        <p
          style={{
            margin: 0,
            padding: '10px 12px',
            borderRadius: 8,
            background: 'color-mix(in oklab, var(--hud-text) 4%, transparent)',
            border: '1px solid color-mix(in oklab, var(--hud-text) 8%, transparent)',
            fontSize: 12,
            lineHeight: 1.65,
            color: 'var(--hud-text-dim)',
          }}
        >
          {payload.excerpt}
        </p>
      )}
      {payload.affected_departments?.length > 0 && (
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
          <span className="lg-meta">영향 부서:</span>
          {payload.affected_departments.map((d) => (
            <span key={d} className="lg-chip" style={{ fontSize: 10, padding: '3px 8px' }}>
              {d}
            </span>
          ))}
        </div>
      )}
      <div>
        <button
          type="button"
          className="lg-btn sm"
          onClick={handleOpen}
          disabled={!payload.full_view_url}
        >
          Module D 에서 자세히 →
        </button>
      </div>
    </div>
  );
}
