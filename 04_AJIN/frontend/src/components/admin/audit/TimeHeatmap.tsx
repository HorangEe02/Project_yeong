// TimeHeatmap — 시간(0-23) × 요일(월-일) 사용량 SVG heatmap (PR-E5).
// 부서별 색상 layering 은 회피, 총합 카운트만 시각화 (Plotly 의존 없음).
// 입력: AuditDashboardResponse.time_pattern.

import { useMemo } from 'react';
import type { TimePatternBucket } from '@api/admin';

interface Props {
  buckets: TimePatternBucket[];
  height?: number;
}

const WEEKDAYS = ['월', '화', '수', '목', '금', '토', '일'];

/** count 를 0-1 normalized 후 cold(파랑) → hot(빨강) interpolation. */
function colorFor(intensity: number): string {
  if (intensity <= 0) return 'rgba(255, 255, 255, 0.04)';
  // 0 → blue (60, 160, 230), 1 → red (220, 60, 60)
  const r = Math.round(60 + (220 - 60) * intensity);
  const g = Math.round(160 + (60 - 160) * intensity);
  const b = Math.round(230 + (60 - 230) * intensity);
  return `rgb(${r}, ${g}, ${b})`;
}

export function TimeHeatmap({ buckets, height = 220 }: Props) {
  // (hour, weekday) → total count (department 합산)
  const { grid, max } = useMemo(() => {
    const g: number[][] = Array.from({ length: 7 }, () => Array(24).fill(0));
    let m = 0;
    for (const b of buckets) {
      if (b.weekday < 0 || b.weekday > 6 || b.hour < 0 || b.hour > 23) continue;
      g[b.weekday][b.hour] += b.count;
      if (g[b.weekday][b.hour] > m) m = g[b.weekday][b.hour];
    }
    return { grid: g, max: m };
  }, [buckets]);

  const cellW = 32;
  const cellH = 22;
  const padLeft = 36;
  const padTop = 24;
  const width = padLeft + 24 * cellW;
  const totalH = padTop + 7 * cellH;

  return (
    <div className="lg-card">
      <div className="lg-card-h">
        <div>
          <div className="lg-pill">TIME HEATMAP · 시간×요일</div>
          <div style={{ marginTop: 6, fontSize: 12, color: 'var(--hud-text-dim)' }}>
            {buckets.length === 0
              ? '데이터 없음 — audit.db 가 비어있습니다.'
              : `총 ${buckets.length} buckets · max=${max}`}
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11 }}>
          <span style={{ display: 'inline-block', width: 14, height: 14, background: colorFor(0.05), border: '1px solid var(--hud-line)' }} />
          <span>cold</span>
          <span style={{ display: 'inline-block', width: 14, height: 14, background: colorFor(1) }} />
          <span>hot</span>
        </div>
      </div>
      <div style={{ overflowX: 'auto' }}>
        <svg width={width} height={totalH} style={{ display: 'block', minWidth: width, height }}>
          {/* x-axis (hours) */}
          {Array.from({ length: 24 }, (_, h) => (
            <text
              key={`hx-${h}`}
              x={padLeft + h * cellW + cellW / 2}
              y={padTop - 8}
              fontSize={9}
              fill="var(--hud-text-dim)"
              textAnchor="middle"
            >
              {h}
            </text>
          ))}
          {/* y-axis (weekday) */}
          {WEEKDAYS.map((d, w) => (
            <text
              key={`wd-${w}`}
              x={padLeft - 8}
              y={padTop + w * cellH + cellH / 2 + 3}
              fontSize={10}
              fill="var(--hud-text-dim)"
              textAnchor="end"
            >
              {d}
            </text>
          ))}
          {/* cells */}
          {grid.map((row, w) =>
            row.map((c, h) => {
              const intensity = max > 0 ? c / max : 0;
              return (
                <rect
                  key={`c-${w}-${h}`}
                  x={padLeft + h * cellW + 1}
                  y={padTop + w * cellH + 1}
                  width={cellW - 2}
                  height={cellH - 2}
                  fill={colorFor(intensity)}
                  stroke="var(--hud-line)"
                  strokeWidth={0.5}
                >
                  <title>{`${WEEKDAYS[w]} ${h}시 — ${c}건`}</title>
                </rect>
              );
            }),
          )}
        </svg>
      </div>
    </div>
  );
}
