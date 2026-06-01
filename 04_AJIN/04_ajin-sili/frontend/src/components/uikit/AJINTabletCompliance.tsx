// AJINTabletCompliance — iPad (641-1024px) 전용 규제 모니터.
// reference: PadDashboard 패턴 (aj-pad split, 280px rail / work area).
//
// 좌 rail: 9 crawler list + 마지막 실행 + 상태 dot
// 우 work: KPI 4-tile + 변경 알림 큰 feed + grade filter chips

import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronRight, RefreshCw, Shield } from 'lucide-react';

import {
  fetchChangeFeed,
  fetchChangeKpi,
  type ChangeFeedItem,
  type ChangeKpiResponse,
} from '@api/compliance';

const CRAWLERS = [
  { k: 'iso', ko: 'ISO 14001 / 45001' },
  { k: 'msds', ko: '화학물질 MSDS' },
  { k: 'eu_regulation', ko: 'EU REACH · RoHS' },
  { k: 'domestic_law', ko: '산안법 · 화관법' },
  { k: 'oem_quality', ko: 'IATF 16949 · PPAP' },
  { k: 'apqp', ko: 'APQP 단계' },
  { k: 'carbon_esg', ko: 'Carbon · ESG' },
  { k: 'ev_battery', ko: 'EV Battery UN R100' },
  { k: 'global_trade', ko: '관세 · FTA' },
] as const;

const GRADES = ['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'] as const;

const GRADE_COLOR: Record<string, string> = {
  CRITICAL: '#FF7565',
  HIGH: '#E8A317',
  MEDIUM: '#4FB774',
  LOW: 'rgba(255,255,255,0.55)',
};

export function AJINTabletCompliance() {
  const navigate = useNavigate();
  const [kpi, setKpi] = useState<ChangeKpiResponse | null>(null);
  const [feed, setFeed] = useState<ChangeFeedItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeGrade, setActiveGrade] = useState<(typeof GRADES)[number]>('ALL');

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const [k, f] = await Promise.all([
          fetchChangeKpi(),
          fetchChangeFeed({ limit: 30 }),
        ]);
        if (!alive) return;
        setKpi(k);
        setFeed(f.items);
      } catch {
        // ignore
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  const filteredFeed = useMemo(() => {
    if (activeGrade === 'ALL') return feed;
    return feed.filter((f) => (f.grade || '').toUpperCase() === activeGrade);
  }, [feed, activeGrade]);

  const pending = kpi?.open_count ?? 0;
  const today = kpi?.today_new ?? 0;
  const critical = feed.filter((f) => (f.grade || '').toUpperCase() === 'CRITICAL').length;
  const high = feed.filter((f) => (f.grade || '').toUpperCase() === 'HIGH').length;

  return (
    <div className="aj-mobile" style={{ minHeight: '100vh' }}>
      <div className="aj-screen dark" style={{ position: 'relative', minHeight: '100vh' }}>
        <div className="aj-bg-grad dark" />

        <div className="aj-pad dark" style={{ position: 'relative', zIndex: 3, minHeight: '100vh' }}>
          {/* ===== Rail ===== */}
          <div className="rail">
            <div style={{ padding: '4px 8px 12px' }}>
              <div className="aj-mono" style={{ color: 'var(--aj-gold, #FCB132)', fontSize: 10 }}>
                CRAWLERS · 9
              </div>
              <div style={{ fontSize: 13, marginTop: 4, opacity: 0.65 }}>
                자동 02:00-02:40 KST
              </div>
            </div>

            {CRAWLERS.map((c) => (
              <div key={c.k} className="rail-row" style={{ cursor: 'default' }}>
                <div className="icn">
                  <Shield size={14} aria-hidden />
                </div>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontWeight: 600, fontSize: 13, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {c.ko}
                  </div>
                  <div className="aj-mono" style={{ fontSize: 9, opacity: 0.6, marginTop: 1 }}>
                    {c.k.toUpperCase()}
                  </div>
                </div>
              </div>
            ))}

            <div style={{ flex: 1 }} />

            <div className="aj-glass" style={{ padding: 12, borderRadius: 14 }}>
              <div className="aj-mono" style={{ fontSize: 9, opacity: 0.55 }}>
                NEXT RUN
              </div>
              <div style={{ fontSize: 13, marginTop: 2, fontFamily: '"JetBrains Mono", ui-monospace, monospace' }}>
                02:00 KST 평일
              </div>
            </div>
          </div>

          {/* ===== Work ===== */}
          <div className="work">
            <div style={{ marginBottom: 18 }}>
              <div className="aj-mono" style={{ fontSize: 10, color: 'var(--aj-gold, #FCB132)' }}>
                COMPLIANCE · D1
              </div>
              <h1 style={{ margin: '4px 0 0', fontSize: 32, fontWeight: 700, letterSpacing: '-0.02em' }}>
                규제 모니터
              </h1>
            </div>

            {/* KPI 4-col */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(4, 1fr)',
                gap: 12,
                marginBottom: 18,
              }}
            >
              <Kpi k="미처리" v={loading ? '—' : String(pending)} sub={pending > 0 ? '검토 필요' : 'clear'} down={pending > 0} />
              <Kpi k="오늘 신규" v={loading ? '—' : String(today)} sub={today > 0 ? '+신규' : '변경 없음'} up={today > 0} />
              <Kpi k="CRITICAL" v={String(critical)} sub="긴급" down={critical > 0} />
              <Kpi k="HIGH" v={String(high)} sub="높음" />
            </div>

            {/* Grade filter chips */}
            <div style={{ display: 'flex', gap: 8, marginBottom: 14, flexWrap: 'wrap' }}>
              {GRADES.map((g) => {
                const active = g === activeGrade;
                return (
                  <button
                    key={g}
                    type="button"
                    onClick={() => setActiveGrade(g)}
                    className={'aj-chip' + (active ? ' gold dot' : '')}
                    style={{
                      border: 0,
                      cursor: 'pointer',
                      fontFamily: 'inherit',
                    }}
                    aria-pressed={active}
                  >
                    {g}
                  </button>
                );
              })}
            </div>

            {/* Feed */}
            <div className="aj-glass" style={{ padding: 0, borderRadius: 18, overflow: 'hidden' }}>
              {loading && (
                <div style={{ padding: 32, textAlign: 'center', opacity: 0.6, fontSize: 14 }}>
                  <RefreshCw size={16} style={{ marginRight: 8, verticalAlign: 'middle' }} />
                  불러오는 중…
                </div>
              )}
              {!loading && filteredFeed.length === 0 && (
                <div style={{ padding: 32, textAlign: 'center', opacity: 0.6, fontSize: 14 }}>
                  <Shield size={16} style={{ marginRight: 8, verticalAlign: 'middle' }} />
                  변경 없음
                </div>
              )}
              {!loading &&
                filteredFeed.slice(0, 14).map((item) => {
                  const grade = (item.grade || 'LOW').toUpperCase();
                  const color = GRADE_COLOR[grade] ?? GRADE_COLOR.LOW;
                  return (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => navigate(`/compliance?change_id=${item.id}`)}
                      style={{
                        display: 'grid',
                        gridTemplateColumns: '80px 1fr 120px 24px',
                        gap: 14,
                        padding: '14px 18px',
                        alignItems: 'center',
                        background: 'transparent',
                        border: 0,
                        borderTop: '0.5px solid rgba(255,255,255,0.06)',
                        cursor: 'pointer',
                        color: 'inherit',
                        fontFamily: 'inherit',
                        textAlign: 'left',
                        width: '100%',
                      }}
                    >
                      <span
                        className="aj-mono"
                        style={{ fontSize: 11, color, fontWeight: 600 }}
                      >
                        {grade}
                      </span>
                      <div style={{ minWidth: 0 }}>
                        <div
                          style={{
                            fontSize: 14,
                            fontWeight: 500,
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                          }}
                        >
                          {item.item_title || '제목 없음'}
                        </div>
                        <div
                          style={{
                            fontSize: 11,
                            opacity: 0.6,
                            marginTop: 2,
                            fontFamily: '"JetBrains Mono", ui-monospace, monospace',
                          }}
                        >
                          {item.regulation_type}
                        </div>
                      </div>
                      <div
                        className="aj-mono"
                        style={{ fontSize: 10, opacity: 0.65, textAlign: 'right' }}
                      >
                        {(item.detected_at || '').slice(0, 16).replace('T', ' ')}
                      </div>
                      <ChevronRight size={14} aria-hidden style={{ opacity: 0.5 }} />
                    </button>
                  );
                })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function Kpi({
  k,
  v,
  sub,
  up,
  down,
}: {
  k: string;
  v: string;
  sub: string;
  up?: boolean;
  down?: boolean;
}) {
  return (
    <div className="aj-glass aj-kpi" style={{ padding: '14px 16px' }}>
      <div className="k">{k}</div>
      <div className="v">{v}</div>
      <div className={'delta ' + (up ? 'up' : down ? 'down' : '')}>{sub}</div>
    </div>
  );
}
