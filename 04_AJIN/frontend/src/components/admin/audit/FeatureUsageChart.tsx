// FeatureUsageChart — Feature 별 사용량 SVG 막대 + 만족도 점선 overlay (PR-E5).
// Plotly 의존 없음. 자체 SVG 렌더링.
// 입력: AuditDashboardResponse.feature_usage

import { useMemo, useState } from 'react';
import type { FeatureUsageSummaryRow } from '@api/admin';

interface Props {
  rows: FeatureUsageSummaryRow[];
  loading?: boolean;
  onPeriodChange?: (period: 'day' | 'week' | 'month') => void;
  period?: 'day' | 'week' | 'month';
}

const FEATURE_COLORS: Record<string, string> = {
  A: '#3b9eee',
  B: '#5ec97c',
  C: '#e9c244',
  D: '#e97c3b',
  F: '#b06ee9',
};

function featureColor(feature: string): string {
  const key = feature.toUpperCase().replace(/^feature_?/i, '').trim();
  return FEATURE_COLORS[key] ?? '#888';
}

const PAD_LEFT = 48;
const PAD_RIGHT = 20;
const PAD_TOP = 16;
const PAD_BOTTOM = 56;
const CHART_H = 220;

export function FeatureUsageChart({ rows, loading, onPeriodChange, period = 'week' }: Props) {
  const [localPeriod, setLocalPeriod] = useState<'day' | 'week' | 'month'>(period);

  function handlePeriod(p: 'day' | 'week' | 'month') {
    setLocalPeriod(p);
    onPeriodChange?.(p);
  }

  const { bars, ratingLine, svgW } = useMemo(() => {
    if (!rows.length) return { bars: [], ratingLine: [], svgW: 0 };

    const maxCount = Math.max(1, ...rows.map((r) => r.count));
    const n = rows.length;
    const minW = 560;
    const totalW = Math.max(minW, n * 96 + PAD_LEFT + PAD_RIGHT);
    const barW = Math.min(56, (totalW - PAD_LEFT - PAD_RIGHT) / n - 8);
    const innerH = CHART_H - PAD_TOP - PAD_BOTTOM;

    const b = rows.map((r, i) => {
      const slotW = (totalW - PAD_LEFT - PAD_RIGHT) / n;
      const cx = PAD_LEFT + slotW * i + slotW / 2;
      const barH = Math.max(2, (r.count / maxCount) * innerH);
      return {
        x: cx - barW / 2,
        y: PAD_TOP + innerH - barH,
        w: barW,
        h: barH,
        cx,
        color: featureColor(r.feature),
        count: r.count,
        name: r.name || r.feature,
        feature: r.feature,
        rating: r.avg_rating,
        feedbacks: r.feedback_count,
      };
    });

    // 만족도 점선: y = PAD_TOP + innerH * (1 - rating)
    const rl = b.map((bar) => ({
      cx: bar.cx,
      cy: PAD_TOP + innerH * (1 - Math.min(1, Math.max(0, bar.rating))),
      rating: bar.rating,
    }));

    return { bars: b, ratingLine: rl, svgW: totalW };
  }, [rows]);

  const innerH = CHART_H - PAD_TOP - PAD_BOTTOM;
  // Y axis ticks (count)
  const maxCount = rows.length ? Math.max(1, ...rows.map((r) => r.count)) : 10;
  const yTicks = [0, 0.25, 0.5, 0.75, 1].map((f) => ({
    v: Math.round(maxCount * f),
    y: PAD_TOP + innerH * (1 - f),
  }));

  // 만족도 점선 path
  const ratingPathD = ratingLine.length > 1
    ? ratingLine.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.cx.toFixed(1)},${p.cy.toFixed(1)}`).join(' ')
    : '';

  return (
    <div className="lg-card">
      <div className="lg-card-h">
        <div>
          <div className="lg-pill">FEATURE USAGE · 사용량 &amp; 만족도</div>
          <div style={{ marginTop: 6, fontSize: 12, color: 'var(--hud-text-dim)' }}>
            {loading
              ? '로딩 중…'
              : rows.length === 0
                ? '데이터 없음'
                : `Feature ${rows.length}종 · 막대=사용량, 점선=만족도(0-1)`}
          </div>
        </div>
        {/* Period 토글 */}
        <div style={{ display: 'flex', gap: 4 }}>
          {(['day', 'week', 'month'] as const).map((p) => (
            <button
              key={p}
              type="button"
              className={`lg-btn sm${localPeriod === p ? '' : ' ghost'}`}
              onClick={() => handlePeriod(p)}
            >
              {p === 'day' ? '1일' : p === 'week' ? '7일' : '30일'}
            </button>
          ))}
        </div>
      </div>

      {rows.length === 0 && !loading && (
        <div style={{ padding: 24, textAlign: 'center', color: 'var(--hud-text-dim)', fontSize: 13 }}>
          해당 기간 사용 데이터가 없습니다.
        </div>
      )}

      {rows.length > 0 && (
        <div style={{ overflowX: 'auto' }}>
          <svg
            width={svgW}
            height={CHART_H}
            style={{ display: 'block', minWidth: svgW }}
          >
            {/* Y grid lines + labels */}
            {yTicks.map((t) => (
              <g key={`yt-${t.v}`}>
                <line
                  x1={PAD_LEFT}
                  y1={t.y}
                  x2={svgW - PAD_RIGHT}
                  y2={t.y}
                  stroke="var(--hud-line)"
                  strokeWidth={0.5}
                  strokeDasharray="4,3"
                />
                <text
                  x={PAD_LEFT - 6}
                  y={t.y + 4}
                  fontSize={9}
                  fill="var(--hud-text-dim)"
                  textAnchor="end"
                >
                  {t.v}
                </text>
              </g>
            ))}

            {/* Bars */}
            {bars.map((b) => (
              <g key={b.feature}>
                <rect
                  x={b.x}
                  y={b.y}
                  width={b.w}
                  height={b.h}
                  fill={b.color}
                  opacity={0.82}
                  rx={2}
                >
                  <title>{`${b.name}: ${b.count}건 | 만족도 ${(b.rating * 100).toFixed(0)}% (피드백 ${b.feedbacks}건)`}</title>
                </rect>
                {/* Count label on top of bar */}
                {b.count > 0 && (
                  <text
                    x={b.cx}
                    y={b.y - 4}
                    fontSize={10}
                    fill="var(--hud-text)"
                    textAnchor="middle"
                    fontWeight="600"
                  >
                    {b.count}
                  </text>
                )}
                {/* X axis: feature label */}
                <text
                  x={b.cx}
                  y={PAD_TOP + innerH + 16}
                  fontSize={11}
                  fill="var(--hud-text-dim)"
                  textAnchor="middle"
                  fontWeight="600"
                >
                  {b.feature}
                </text>
                {/* Feature name (wrap on second line) */}
                <text
                  x={b.cx}
                  y={PAD_TOP + innerH + 30}
                  fontSize={9}
                  fill="var(--hud-text-dim)"
                  textAnchor="middle"
                >
                  {b.name.length > 8 ? `${b.name.slice(0, 8)}…` : b.name}
                </text>
              </g>
            ))}

            {/* 만족도 점선 overlay */}
            {ratingPathD && (
              <path
                d={ratingPathD}
                fill="none"
                stroke="#5ec97c"
                strokeWidth={1.5}
                strokeDasharray="5,3"
              />
            )}
            {/* 만족도 점 */}
            {ratingLine.map((p, i) => (
              <circle
                key={`rl-${i}`}
                cx={p.cx}
                cy={p.cy}
                r={3.5}
                fill="#5ec97c"
                stroke="var(--hud-bg)"
                strokeWidth={1}
              >
                <title>{`만족도: ${(p.rating * 100).toFixed(0)}%`}</title>
              </circle>
            ))}

            {/* 범례 */}
            <g transform={`translate(${PAD_LEFT}, ${CHART_H - 8})`}>
              <rect x={0} y={-8} width={10} height={10} fill="#3b9eee" rx={2} opacity={0.82} />
              <text x={14} y={0} fontSize={9} fill="var(--hud-text-dim)">사용량</text>
              <line x1={60} y1={-3} x2={78} y2={-3} stroke="#5ec97c" strokeWidth={1.5} strokeDasharray="4,2" />
              <circle cx={69} cy={-3} r={2.5} fill="#5ec97c" />
              <text x={82} y={0} fontSize={9} fill="var(--hud-text-dim)">만족도</text>
            </g>
          </svg>
        </div>
      )}
    </div>
  );
}
