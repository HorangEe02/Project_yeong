// WeeklyHeatmap — 7일 × 24시간 grid heatmap (v4.9.2).
//
// SecurityTab의 '주간' 모드에서 사용. 각 cell = 일자·시간대별 로그인 카운트.
// 셀 클릭 시 SecurityTab의 일별 모드로 전환 + 해당 일자 선택.

import { useMemo } from 'react';
import type { LoginHistoryEntry } from '@api/admin';

interface Props {
  history: LoginHistoryEntry[];
  /** 그리드 마지막 일자 (default 오늘) — 7일 grid 의 우측 끝 */
  endDate?: string;       // YYYY-MM-DD
  /** 셀 클릭 시 호출 (date, hour) */
  onCellClick?: (date: string, hour: number) => void;
}

const HOURS = Array.from({ length: 24 }, (_, h) => h);

function pad2(n: number): string {
  return String(n).padStart(2, '0');
}

function dateKey(d: Date): string {
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
}

function weekdayLabel(d: Date): string {
  return ['일', '월', '화', '수', '목', '금', '토'][d.getDay()];
}

function heatColor(count: number, max: number): string {
  if (count === 0) return 'var(--hud-surface, transparent)';
  const ratio = count / max;
  let pct: number;
  if (ratio <= 0.2) pct = 15;
  else if (ratio <= 0.4) pct = 30;
  else if (ratio <= 0.6) pct = 50;
  else if (ratio <= 0.8) pct = 70;
  else pct = 90;
  return `color-mix(in oklab, var(--hud-primary) ${pct}%, transparent)`;
}

export function WeeklyHeatmap({ history, endDate, onCellClick }: Props) {
  // 7일 범위 계산 (endDate 우측 끝)
  const days = useMemo(() => {
    const end = endDate ? new Date(`${endDate}T00:00:00`) : new Date();
    end.setHours(0, 0, 0, 0);
    const result: Date[] = [];
    for (let i = 6; i >= 0; i--) {
      const d = new Date(end);
      d.setDate(end.getDate() - i);
      result.push(d);
    }
    return result;
  }, [endDate]);

  // grid: {dateKey: {hour: {count, failed}}}
  const grid = useMemo(() => {
    const dayKeys = new Set(days.map(dateKey));
    const m: Record<string, Record<number, { count: number; failed: number }>> = {};
    for (const d of days) {
      m[dateKey(d)] = {};
      for (const h of HOURS) m[dateKey(d)][h] = { count: 0, failed: 0 };
    }
    for (const row of history) {
      const dk = row.timestamp.slice(0, 10);
      if (!dayKeys.has(dk)) continue;
      const hr = Number(row.timestamp.slice(11, 13));
      if (!Number.isFinite(hr) || hr < 0 || hr > 23) continue;
      m[dk][hr].count += 1;
      if (!row.success) m[dk][hr].failed += 1;
    }
    return m;
  }, [days, history]);

  const maxCount = useMemo(() => {
    let max = 1;
    for (const day of Object.values(grid)) {
      for (const cell of Object.values(day)) {
        if (cell.count > max) max = cell.count;
      }
    }
    return max;
  }, [grid]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      {/* 시간 라벨 (상단) */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '52px repeat(24, 1fr)',
          gap: 2,
          fontFamily: 'var(--hud-font-mono)',
          fontSize: 9,
          color: 'var(--hud-text-dim)',
        }}
      >
        <div />
        {HOURS.map((h) => (
          <div key={h} style={{ textAlign: 'center' }}>
            {h % 3 === 0 ? pad2(h) : ''}
          </div>
        ))}
      </div>

      {/* 7행 grid */}
      {days.map((d) => {
        const dk = dateKey(d);
        const wd = weekdayLabel(d);
        const wdColor = d.getDay() === 0 ? 'var(--hud-red)' : d.getDay() === 6 ? 'var(--hud-blue)' : 'var(--hud-text)';
        return (
          <div
            key={dk}
            style={{
              display: 'grid',
              gridTemplateColumns: '52px repeat(24, 1fr)',
              gap: 2,
            }}
          >
            <div
              style={{
                fontFamily: 'var(--hud-font-mono)',
                fontSize: 10,
                color: wdColor,
                display: 'flex',
                alignItems: 'center',
                gap: 4,
                paddingRight: 6,
                justifyContent: 'flex-end',
              }}
              title={dk}
            >
              <span>{wd}</span>
              <span style={{ color: 'var(--hud-text-dim)' }}>{pad2(d.getMonth() + 1)}-{pad2(d.getDate())}</span>
            </div>
            {HOURS.map((h) => {
              const cell = grid[dk]?.[h] ?? { count: 0, failed: 0 };
              const bg = heatColor(cell.count, maxCount);
              return (
                <button
                  key={h}
                  type="button"
                  onClick={() => onCellClick?.(dk, h)}
                  title={`${dk} ${pad2(h)}시 — ${cell.count}건${cell.failed > 0 ? ` (실패 ${cell.failed})` : ''}`}
                  style={{
                    height: 22,
                    background: bg,
                    border: '1px solid var(--hud-border)',
                    borderRadius: 2,
                    cursor: onCellClick ? 'pointer' : 'default',
                    padding: 0,
                  }}
                />
              );
            })}
          </div>
        );
      })}

      {/* 범례 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 10, color: 'var(--hud-text-dim)', marginTop: 6 }}>
        <span>적음</span>
        {[15, 30, 50, 70, 90].map((p) => (
          <span
            key={p}
            style={{
              width: 16,
              height: 12,
              background: `color-mix(in oklab, var(--hud-primary) ${p}%, transparent)`,
              borderRadius: 2,
              border: '1px solid var(--hud-border)',
            }}
          />
        ))}
        <span>많음 · 최대 {maxCount}건/셀</span>
      </div>
    </div>
  );
}
