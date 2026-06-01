// LoginCalendar — 월 달력 + 일자별 로그인 카운트 히트맵 (v4.9).
//
// SecurityTab 이 사용: 일자 클릭 → 그 일자의 24h 시간대 분포·통계·이력 drill-down.
// URL `?date=YYYY-MM-DD` 와 양방향 동기화.
//
// 자체 구현 (date-fns 미사용) — 외부 의존 0.

import { useMemo } from 'react';
import type { DailyCount } from '@api/admin';

interface Props {
  /** API daily_counts (전체 기간 — 컴포넌트가 month 필터링) */
  dailyCounts: DailyCount[];
  /** 현재 선택된 일자 ('YYYY-MM-DD' 또는 null) */
  selectedDate: string | null;
  onSelect: (date: string) => void;
  year: number;
  month: number; // 1-12
  onYearChange: (y: number) => void;
  onMonthChange: (m: number) => void;
  /** 빠른 버튼 — 부모가 처리 (URL ?date 제거 + days 변경) */
  onQuickRange?: (days: number) => void;
}

const WEEKDAY_LABELS = ['일', '월', '화', '수', '목', '금', '토'];

function daysInMonth(y: number, m: number): number {
  return new Date(y, m, 0).getDate();
}

function firstWeekday(y: number, m: number): number {
  return new Date(y, m - 1, 1).getDay(); // 0=Sun
}

function pad2(n: number): string {
  return String(n).padStart(2, '0');
}

function isFutureDate(y: number, m: number, d: number, today: Date): boolean {
  const cmp = new Date(y, m - 1, d);
  cmp.setHours(0, 0, 0, 0);
  return cmp.getTime() > today.getTime();
}

/** 히트맵 background color — 절대 카운트 기준 5-step gradient. */
function heatColor(count: number, max: number): string {
  if (count === 0) return 'var(--hud-surface, transparent)';
  const ratio = count / max;
  let pct: number;
  if (ratio <= 0.25) pct = 15;
  else if (ratio <= 0.5) pct = 30;
  else if (ratio <= 0.75) pct = 50;
  else pct = 80;
  return `color-mix(in oklab, var(--hud-primary) ${pct}%, transparent)`;
}

export function LoginCalendar({
  dailyCounts,
  selectedDate,
  onSelect,
  year,
  month,
  onYearChange,
  onMonthChange,
  onQuickRange,
}: Props) {
  const today = useMemo(() => {
    const t = new Date();
    t.setHours(0, 0, 0, 0);
    return t;
  }, []);

  // 빠른 일자 카운트 lookup (현 month 전용)
  const monthPrefix = `${year}-${pad2(month)}`;
  const counts: Record<string, { count: number; failed: number }> = useMemo(() => {
    const m: Record<string, { count: number; failed: number }> = {};
    for (const d of dailyCounts) {
      if (d.date.startsWith(monthPrefix)) {
        m[d.date] = { count: d.count, failed: d.failed };
      }
    }
    return m;
  }, [dailyCounts, monthPrefix]);

  const maxCount = useMemo(() => {
    return Math.max(1, ...Object.values(counts).map((c) => c.count));
  }, [counts]);

  const totalDays = daysInMonth(year, month);
  const offset = firstWeekday(year, month);
  const cells: ({ day: number; date: string } | null)[] = [];
  for (let i = 0; i < offset; i++) cells.push(null);
  for (let d = 1; d <= totalDays; d++) {
    cells.push({ day: d, date: `${monthPrefix}-${pad2(d)}` });
  }
  while (cells.length % 7 !== 0) cells.push(null);

  // 연 dropdown 범위: -5년 ~ 현재년
  const currentYear = new Date().getFullYear();
  const yearOptions: number[] = [];
  for (let y = currentYear; y >= currentYear - 5; y--) yearOptions.push(y);

  const months = Array.from({ length: 12 }, (_, i) => i + 1);

  return (
    <div className="lg-card" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div className="lg-card-h" style={{ flexWrap: 'wrap', gap: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <div className="lg-pill">로그인 달력</div>
          <select
            value={year}
            onChange={(e) => onYearChange(Number(e.target.value))}
            style={{ padding: '4px 8px', minHeight: 32, fontFamily: 'var(--hud-font-mono)' }}
          >
            {yearOptions.map((y) => (
              <option key={y} value={y}>{y}</option>
            ))}
          </select>
          <select
            value={month}
            onChange={(e) => onMonthChange(Number(e.target.value))}
            style={{ padding: '4px 8px', minHeight: 32, fontFamily: 'var(--hud-font-mono)' }}
          >
            {months.map((m) => (
              <option key={m} value={m}>{pad2(m)}월</option>
            ))}
          </select>
        </div>
        {onQuickRange && (
          <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
            <button className="lg-btn sm ghost" onClick={() => {
              const t = new Date();
              onYearChange(t.getFullYear());
              onMonthChange(t.getMonth() + 1);
              onSelect(`${t.getFullYear()}-${pad2(t.getMonth() + 1)}-${pad2(t.getDate())}`);
            }}>오늘</button>
            <button className="lg-btn sm ghost" onClick={() => {
              const t = new Date();
              t.setDate(t.getDate() - 1);
              onYearChange(t.getFullYear());
              onMonthChange(t.getMonth() + 1);
              onSelect(`${t.getFullYear()}-${pad2(t.getMonth() + 1)}-${pad2(t.getDate())}`);
            }}>어제</button>
            <button className="lg-btn sm ghost" onClick={() => onQuickRange(7)}>최근 7일</button>
            <button className="lg-btn sm ghost" onClick={() => onQuickRange(30)}>최근 30일</button>
          </div>
        )}
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(7, 1fr)',
          gap: 4,
          fontFamily: 'var(--hud-font-mono)',
        }}
      >
        {WEEKDAY_LABELS.map((w, i) => (
          <div
            key={w}
            style={{
              textAlign: 'center',
              fontSize: 11,
              fontWeight: 700,
              color: i === 0 ? 'var(--hud-red)' : i === 6 ? 'var(--hud-blue)' : 'var(--hud-text-dim)',
              padding: '4px 0',
            }}
          >
            {w}
          </div>
        ))}
        {cells.map((cell, i) => {
          if (!cell) return <div key={`pad-${i}`} />;
          const info = counts[cell.date] ?? { count: 0, failed: 0 };
          const isFuture = isFutureDate(year, month, cell.day, today);
          const isSelected = selectedDate === cell.date;
          const bg = heatColor(info.count, maxCount);
          const dow = (offset + cell.day - 1) % 7;
          const dowColor = dow === 0 ? 'var(--hud-red)' : dow === 6 ? 'var(--hud-blue)' : 'var(--hud-text)';
          return (
            <button
              key={cell.date}
              type="button"
              onClick={() => !isFuture && onSelect(cell.date)}
              disabled={isFuture}
              title={`${cell.date} · ${info.count}건${info.failed > 0 ? ` (실패 ${info.failed})` : ''}`}
              style={{
                minHeight: 56,
                padding: '6px 4px',
                background: bg,
                border: isSelected ? '2px solid var(--hud-primary)' : '1px solid var(--hud-border)',
                borderRadius: 6,
                cursor: isFuture ? 'not-allowed' : 'pointer',
                opacity: isFuture ? 0.3 : 1,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'flex-start',
                justifyContent: 'space-between',
                color: dowColor,
                fontFamily: 'inherit',
              }}
            >
              <span style={{ fontSize: 13, fontWeight: isSelected ? 800 : 500 }}>{cell.day}</span>
              {info.count > 0 && (
                <span style={{ fontSize: 10, fontWeight: 600, alignSelf: 'flex-end' }}>
                  {info.count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 10, color: 'var(--hud-text-dim)' }}>
        <span>적음</span>
        {[15, 30, 50, 80].map((p) => (
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
        <span>많음 · 최대 {maxCount}건/일</span>
      </div>
    </div>
  );
}
