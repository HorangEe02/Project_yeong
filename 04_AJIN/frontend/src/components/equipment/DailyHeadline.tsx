// W8 (P0) — 데일리 헤드라인 카드.
// equipment.tsx 의 OVERVIEW 서브탭 최상단에 마운트.
// '공장장 시점' 1줄 요약 + 세부 위험 신호 칩 N개.

import { useEffect, useState } from 'react';
import { AlertOctagon, AlertTriangle, CheckCircle2 } from 'lucide-react';
import { fetchHeadline } from '@api/equipment';
import type { HeadlineItem, HeadlineResponse } from '@/types/equipment';

interface Props {
  onJump?: (target: HeadlineItem['target_module']) => void;
}

export function DailyHeadline({ onJump }: Props) {
  const [data, setData] = useState<HeadlineResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    fetchHeadline()
      .then((r) => active && setData(r))
      .catch((e: unknown) => active && setError(e instanceof Error ? e.message : String(e)))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, []);

  const top = data?.items?.[0];
  const topSeverity = top?.severity ?? 'normal';
  const headerColor =
    topSeverity === 'critical'
      ? '#dc2626'
      : topSeverity === 'warning'
        ? '#d97706'
        : '#16a34a';
  const Icon = topSeverity === 'critical'
    ? AlertOctagon
    : topSeverity === 'warning'
      ? AlertTriangle
      : CheckCircle2;

  return (
    <section
      className="lg-card"
      style={{
        marginBottom: 16,
        padding: 18,
        borderLeft: `4px solid ${headerColor}`,
        background: `color-mix(in oklab, ${headerColor} 6%, transparent)`,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14 }}>
        <div
          style={{
            width: 40,
            height: 40,
            borderRadius: 10,
            background: `color-mix(in oklab, ${headerColor} 18%, transparent)`,
            color: headerColor,
            display: 'grid',
            placeItems: 'center',
            flexShrink: 0,
          }}
        >
          <Icon size={20} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
            <div>
              <div className="lg-eyebrow" style={{ fontSize: 10, opacity: 0.75 }}>
                DAILY HEADLINE · 오늘의 위험 신호
              </div>
              <div style={{ fontSize: 16, fontWeight: 700, marginTop: 4, lineHeight: 1.4 }}>
                {loading ? '집계 중…' : error ? '집계 실패' : (data?.summary ?? '신호 없음')}
              </div>
            </div>
            {data && (
              <div style={{ fontSize: 11, opacity: 0.65, whiteSpace: 'nowrap' }}>
                활성 알람 {data.active_alarm_count}건
                <br />
                <span style={{ opacity: 0.7 }}>
                  {data.generated_at.slice(11, 19)}
                </span>
              </div>
            )}
          </div>

          {error && (
            <div style={{ marginTop: 10, fontSize: 12, color: '#dc2626' }}>
              ⚠️ {error}
            </div>
          )}

          {data && data.items.length > 0 && (
            <div style={{ marginTop: 10, display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {data.items.map((it, i) => (
                <SignalChip key={i} item={it} onJump={onJump} />
              ))}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

function SignalChip({ item, onJump }: { item: HeadlineItem; onJump?: Props['onJump'] }) {
  const color =
    item.severity === 'critical'
      ? '#dc2626'
      : item.severity === 'warning'
        ? '#d97706'
        : '#16a34a';

  const onClick = () => {
    if (item.target_module && onJump) onJump(item.target_module);
  };

  return (
    <button
      onClick={onClick}
      disabled={!item.target_module}
      style={{
        padding: '6px 10px',
        borderRadius: 999,
        border: `1px solid color-mix(in oklab, ${color} 45%, transparent)`,
        background: `color-mix(in oklab, ${color} 8%, transparent)`,
        color: 'var(--hud-text)',
        fontSize: 11,
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        cursor: item.target_module ? 'pointer' : 'default',
      }}
      title={item.target_module ? `${item.target_module} 탭으로 이동` : ''}
    >
      <span
        style={{
          width: 6,
          height: 6,
          borderRadius: 999,
          background: color,
        }}
      />
      <b>{item.label}</b>
      {item.detail && <span style={{ opacity: 0.7 }}>· {item.detail}</span>}
    </button>
  );
}
