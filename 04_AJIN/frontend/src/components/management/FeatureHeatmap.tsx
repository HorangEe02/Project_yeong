// FeatureHeatmap.tsx — v4.8 F-Stats.
// feature × bucket 자체 SVG 히트맵 (Plotly 의존 회피). 7/30/90일 토글.

import { useEffect, useMemo, useState } from 'react';
import { fetchFeatureHeatmap, type FeatureHeatmapResponse } from '@api/management';

const FEATURE_LABEL: Record<string, string> = {
  A: 'A · 인원검색',
  B: 'B · 문서작성',
  C: 'C · AI도우미',
  D: 'D · 규정준수',
  E: 'E · 인사관리',
  F: 'F · 설비/공정',
};

const PERIOD_PRESETS: { period: 'day' | 'week' | 'month'; days: number; label: string }[] = [
  { period: 'day', days: 7, label: '7일' },
  { period: 'day', days: 30, label: '30일' },
  { period: 'day', days: 90, label: '90일' },
  { period: 'week', days: 84, label: '12주' },
  { period: 'month', days: 365, label: '12개월' },
];

function colorFor(value: number, max: number): string {
  if (max <= 0 || value <= 0) return 'rgba(120,120,120,0.08)';
  const ratio = Math.min(1, value / max);
  // 청록 → 보라 그라데이션 (작은값=옅은 청록, 큰값=짙은 보라)
  const r = Math.round(60 + 120 * ratio);
  const g = Math.round(160 - 80 * ratio);
  const b = Math.round(220);
  return `rgb(${r},${g},${b})`;
}

export function FeatureHeatmap() {
  const [preset, setPreset] = useState(0);
  const [data, setData] = useState<FeatureHeatmapResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const cur = PERIOD_PRESETS[preset];
    setLoading(true);
    setError(null);
    fetchFeatureHeatmap(cur.period, cur.days)
      .then((r) => setData(r))
      .catch((e) => setError((e as Error)?.message || '히트맵 로드 실패'))
      .finally(() => setLoading(false));
  }, [preset]);

  const maxValue = useMemo(() => {
    if (!data) return 0;
    let m = 0;
    for (const f of data.features) {
      for (const b of data.buckets) {
        const v = data.matrix[f]?.[b.key] ?? 0;
        if (v > m) m = v;
      }
    }
    return m;
  }, [data]);

  return (
    <div>
      <div className="lg-card-h" style={{ marginBottom: 12 }}>
        <div>
          <strong>기능별 사용 히트맵</strong>
          <span style={{ fontSize: 11, opacity: 0.6, marginLeft: 8 }}>
            audit.db api_audit_log 기반 · max={maxValue}
          </span>
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          {PERIOD_PRESETS.map((p, i) => (
            <button
              key={p.label}
              type="button"
              className={`lg-btn ${preset === i ? 'lg-btn-primary' : ''}`}
              onClick={() => setPreset(i)}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="lg-state-pill crit" style={{ marginBottom: 8 }}>{error}</div>
      )}

      <div className="lg-card" style={{ padding: 12, overflowX: 'auto' }}>
        {loading && !data ? (
          <div style={{ fontSize: 12 }}>로딩 중…</div>
        ) : !data ? (
          <div style={{ fontSize: 12 }}>데이터 없음</div>
        ) : (
          <table style={{ borderCollapse: 'separate', borderSpacing: 2, fontSize: 11 }}>
            <thead>
              <tr>
                <th style={{ padding: 4, fontWeight: 600, opacity: 0.7 }} />
                {data.buckets.map((b) => (
                  <th
                    key={b.key}
                    style={{
                      padding: 4,
                      fontWeight: 500,
                      opacity: 0.6,
                      writingMode: 'vertical-rl',
                      transform: 'rotate(180deg)',
                      whiteSpace: 'nowrap',
                    }}
                    title={b.label}
                  >
                    {b.label.slice(-5)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.features.map((f) => (
                <tr key={f}>
                  <th style={{ padding: '4px 8px', fontWeight: 600, textAlign: 'left', whiteSpace: 'nowrap' }}>
                    {FEATURE_LABEL[f] ?? f}
                  </th>
                  {data.buckets.map((b) => {
                    const v = data.matrix[f]?.[b.key] ?? 0;
                    return (
                      <td
                        key={b.key}
                        title={`${FEATURE_LABEL[f] ?? f} · ${b.label} → ${v}`}
                        style={{
                          width: 28,
                          height: 28,
                          textAlign: 'center',
                          background: colorFor(v, maxValue),
                          color: v > maxValue * 0.5 ? '#fff' : 'inherit',
                          borderRadius: 3,
                          fontSize: 10,
                          fontWeight: 500,
                        }}
                      >
                        {v > 0 ? v : ''}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

export default FeatureHeatmap;
