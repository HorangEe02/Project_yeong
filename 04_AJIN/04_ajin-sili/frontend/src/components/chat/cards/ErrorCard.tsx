// v3.3 Phase F — ErrorCard: 설비 에러 + Markov 후속 + SPC 통합 (Module F).

import type { ErrorCardPayload } from './types';

interface Props {
  payload: ErrorCardPayload;
  onOpen?: (url: string) => void;
}

function severityColor(sev: string): string {
  switch (sev.toUpperCase()) {
    case 'HIGH':     return 'var(--hud-red)';
    case 'MEDIUM':   return 'var(--hud-orange)';
    case 'LOW':      return 'var(--hud-green)';
    case 'INFO':     return 'var(--hud-blue)';
    default:         return 'var(--hud-text-dim)';
  }
}

export function ErrorCard({ payload, onOpen }: Props) {
  const handleOpen = () => {
    if (!payload.full_view_url) return;
    if (onOpen) {
      onOpen(payload.full_view_url);
    } else {
      window.location.assign(payload.full_view_url);
    }
  };

  const sevColor = severityColor(payload.severity);
  const hasCode = !!payload.code;
  const hasNextLikely = (payload.next_likely?.length ?? 0) > 0;

  return (
    <div className="lg-action-card" data-kind="error">
      <div className="lg-eyebrow">
        EQUIPMENT
        {hasCode && <span className="lg-meta">{payload.code}</span>}
      </div>

      {hasCode && (
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
          <strong style={{ fontSize: 14, color: 'var(--hud-text)', fontFamily: 'var(--hud-font-mono)' }}>
            {payload.code}
          </strong>
          {payload.error_name && (
            <span style={{ fontSize: 13, color: 'var(--hud-text)' }}>{payload.error_name}</span>
          )}
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
        </div>
      )}

      {(payload.cause || payload.action) && (
        <div
          style={{
            padding: '10px 12px',
            borderRadius: 8,
            background: 'color-mix(in oklab, var(--hud-text) 4%, transparent)',
            border: '1px solid color-mix(in oklab, var(--hud-text) 8%, transparent)',
            fontSize: 12,
            lineHeight: 1.7,
            color: 'var(--hud-text-dim)',
          }}
        >
          {payload.cause && (
            <div>
              <span style={{ fontWeight: 600, color: 'var(--hud-text)' }}>원인</span> · {payload.cause}
            </div>
          )}
          {payload.action && (
            <div>
              <span style={{ fontWeight: 600, color: 'var(--hud-text)' }}>조치</span> · {payload.action}
            </div>
          )}
        </div>
      )}

      {(payload.avg_recovery_min !== null || payload.history_count !== null) && (
        <div style={{ display: 'flex', gap: 12, fontSize: 11, color: 'var(--hud-text-dim)' }}>
          {payload.avg_recovery_min !== null && (
            <span>평균 복구 <b style={{ color: 'var(--hud-text)' }}>{payload.avg_recovery_min}분</b></span>
          )}
          {payload.history_count !== null && (
            <span>이력 <b style={{ color: 'var(--hud-text)' }}>{payload.history_count}건</b></span>
          )}
        </div>
      )}

      {hasNextLikely && (
        <div>
          <div className="lg-eyebrow" style={{ marginBottom: 6 }}>
            ⚠ 연쇄 고장 예측 (Markov)
          </div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {payload.next_likely.map((p) => {
              const pct = (p.probability * 100).toFixed(0);
              return (
                <span
                  key={p.code}
                  className="lg-chip"
                  style={{ fontSize: 10, padding: '4px 10px' }}
                  title={p.description}
                >
                  <b style={{ fontFamily: 'var(--hud-font-mono)' }}>{p.code}</b>
                  <span style={{ marginLeft: 6, opacity: 0.7 }}>{pct}%</span>
                </span>
              );
            })}
          </div>
        </div>
      )}

      <div>
        <button
          type="button"
          className="lg-btn sm"
          onClick={handleOpen}
          disabled={!payload.full_view_url}
        >
          Module F 에서 자세히 →
        </button>
      </div>
    </div>
  );
}
