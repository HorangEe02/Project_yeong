// MobileComplianceFeed — /m/compliance/feed.
//
// 2026-05-28 사용자 모바일 피드백: AJINMobileCompliance 의 "전체 →" 버튼이
// navigate('/compliance') 로 같은 모바일 페이지 재진입 → 작동 안 보임. 본 신규
// 라우트가 진짜 "전체 변경 알림" 화면 — 무한 스크롤 + grade 필터 + ack 버튼.
//
// 데스크탑 사용자가 직접 접근 시 /compliance 로 리다이렉트.

import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronLeft, RefreshCw, Shield, Check } from 'lucide-react';

import {
  acknowledgeChange,
  fetchChangeFeed,
  type ChangeFeedItem,
  type ChangeGrade,
} from '@api/compliance';
import { useIsMobile } from '@hooks/useBreakpoint';
import { useThemeStore } from '@store/theme';

const GRADE_COLOR: Record<string, string> = {
  CRITICAL: '#FF7565',
  HIGH:     '#E8A317',
  MEDIUM:   '#4FB774',
  LOW:      'rgba(127,127,127,0.6)',
};

const FILTERS: { id: 'ALL' | ChangeGrade; label: string }[] = [
  { id: 'ALL',      label: '전체' },
  { id: 'CRITICAL', label: 'CRITICAL' },
  { id: 'HIGH',     label: 'HIGH' },
  { id: 'MEDIUM',   label: 'MEDIUM' },
  { id: 'LOW',      label: 'LOW' },
];

const PAGE_SIZE = 20;

export function MobileComplianceFeed() {
  const navigate = useNavigate();
  const isMobile = useIsMobile();
  const resolved = useThemeStore((s) => s.resolved());

  // 데스크탑에서 직접 접근 시 /compliance 로 리다이렉트.
  useEffect(() => {
    if (!isMobile) navigate('/compliance', { replace: true });
  }, [isMobile, navigate]);

  const [items, setItems] = useState<ChangeFeedItem[]>([]);
  const [filter, setFilter] = useState<'ALL' | ChangeGrade>('ALL');
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const offsetRef = useRef(0);
  const sentinelRef = useRef<HTMLDivElement | null>(null);

  const load = async (reset = false) => {
    if (loading) return;
    setLoading(true);
    setError(null);
    try {
      const offset = reset ? 0 : offsetRef.current;
      const res = await fetchChangeFeed({ limit: PAGE_SIZE, offset, includeFiltered: false });
      const newItems = res.items;
      setItems((prev) => (reset ? newItems : [...prev, ...newItems]));
      offsetRef.current = (reset ? 0 : offsetRef.current) + newItems.length;
      if (newItems.length < PAGE_SIZE) setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  // 첫 로드 + 필터 변경 시 reset
  useEffect(() => {
    setItems([]);
    setDone(false);
    offsetRef.current = 0;
    load(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filter]);

  // 무한 스크롤
  useEffect(() => {
    const el = sentinelRef.current;
    if (!el || done) return;
    const io = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting && !loading && !done) {
          load(false);
        }
      },
      { rootMargin: '200px' },
    );
    io.observe(el);
    return () => io.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading, done]);

  const handleAck = async (id: number) => {
    try {
      await acknowledgeChange(id);
      setItems((prev) => prev.map((it) => (it.id === id ? { ...it, acknowledged: true } : it)));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const filtered = filter === 'ALL' ? items : items.filter((it) => (it.grade || 'LOW').toUpperCase() === filter);

  return (
    <div className="aj-mobile" style={{ minHeight: '100vh' }}>
      <div className={`aj-screen ${resolved === 'light' ? 'light' : 'dark'}`} style={{ position: 'relative', minHeight: '100vh' }}>
        <div className={`aj-bg-grad ${resolved === 'light' ? 'light' : 'dark'}`} />

        <div
          className="aj-scroll"
          style={{
            paddingTop: 18,
            paddingBottom: 'calc(env(safe-area-inset-bottom, 0px) + 120px)',
            position: 'relative',
            zIndex: 3,
            minHeight: '100vh',
          }}
        >
          {/* Header with back */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '12px 16px 6px' }}>
            <button
              type="button"
              onClick={() => navigate(-1)}
              aria-label="뒤로"
              style={{
                width: 36, height: 36, borderRadius: 999,
                background: 'transparent', border: '1px solid rgba(127,127,127,0.25)',
                color: 'currentColor', cursor: 'pointer',
                display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
              }}
            >
              <ChevronLeft size={18} aria-hidden />
            </button>
            <div>
              <div className="aj-mono" style={{ color: 'var(--aj-gold, #FCB132)' }}>
                COMPLIANCE · FEED
              </div>
              <h1 style={{ margin: '4px 0 0', fontSize: 24, fontWeight: 700, letterSpacing: '-0.018em' }}>
                변경 알림 전체
              </h1>
            </div>
          </div>

          {/* Filter chips */}
          <div
            style={{
              display: 'flex', flexWrap: 'wrap', gap: 6,
              padding: '10px 16px 14px',
            }}
          >
            {FILTERS.map((f) => {
              const active = filter === f.id;
              return (
                <button
                  key={f.id}
                  type="button"
                  onClick={() => setFilter(f.id)}
                  aria-pressed={active}
                  className={'aj-chip' + (active ? ' gold' : '')}
                  style={{
                    border: 0, cursor: 'pointer', fontFamily: 'inherit',
                    fontSize: 11, fontWeight: 600, letterSpacing: '0.04em',
                  }}
                >
                  {f.label}
                </button>
              );
            })}
          </div>

          {error && (
            <div className="aj-glass" style={{ margin: '0 16px 12px', padding: 12, fontSize: 12, color: '#FF7565' }}>
              불러오기 실패: {error}
            </div>
          )}

          <div className="aj-glass aj-divlist" style={{ margin: '0 12px' }}>
            {filtered.length === 0 && !loading && (
              <div style={{ padding: 24, textAlign: 'center', opacity: 0.6, fontSize: 13 }}>
                <Shield size={16} style={{ marginRight: 6, verticalAlign: 'middle' }} />
                해당 등급의 변경 알림 없음
              </div>
            )}
            {filtered.map((item) => {
              const grade = (item.grade || 'LOW').toUpperCase();
              const color = GRADE_COLOR[grade] ?? GRADE_COLOR.LOW;
              return (
                <div
                  key={item.id}
                  style={{
                    display: 'grid',
                    gridTemplateColumns: '52px 1fr auto',
                    gap: 10,
                    padding: '12px 14px',
                    alignItems: 'center',
                    opacity: item.acknowledged ? 0.55 : 1,
                  }}
                >
                  <span className="aj-mono" style={{ fontSize: 10, color, fontWeight: 600 }}>
                    {grade}
                  </span>
                  <button
                    type="button"
                    onClick={() => navigate(`/compliance?change_id=${item.id}`)}
                    style={{
                      background: 'transparent', border: 0, padding: 0, textAlign: 'left',
                      color: 'inherit', fontFamily: 'inherit', cursor: 'pointer', minWidth: 0,
                    }}
                  >
                    <div style={{ fontSize: 14, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {item.item_title || '제목 없음'}
                    </div>
                    <div style={{ fontSize: 11, opacity: 0.6, marginTop: 1, fontFamily: '"JetBrains Mono", ui-monospace, monospace' }}>
                      {item.regulation_type} · {(item.detected_at || '').slice(0, 16).replace('T', ' ')}
                    </div>
                  </button>
                  {item.acknowledged ? (
                    <span style={{ fontSize: 10, opacity: 0.55, padding: '4px 8px' }}>확인됨</span>
                  ) : (
                    <button
                      type="button"
                      onClick={() => handleAck(item.id)}
                      aria-label="확인"
                      title="확인"
                      style={{
                        width: 32, height: 32, borderRadius: 999,
                        background: 'rgba(252,177,50,0.18)', border: '1px solid rgba(252,177,50,0.4)',
                        color: 'inherit', cursor: 'pointer',
                        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                      }}
                    >
                      <Check size={14} aria-hidden />
                    </button>
                  )}
                </div>
              );
            })}
            {loading && (
              <div style={{ padding: 18, textAlign: 'center', opacity: 0.6, fontSize: 13 }}>
                <RefreshCw size={14} style={{ marginRight: 6, verticalAlign: 'middle' }} />
                불러오는 중…
              </div>
            )}
            {done && filtered.length > 0 && (
              <div style={{ padding: 14, textAlign: 'center', opacity: 0.5, fontSize: 11, fontFamily: '"JetBrains Mono", ui-monospace, monospace' }}>
                — END · {filtered.length}건 —
              </div>
            )}
          </div>

          <div ref={sentinelRef} style={{ height: 1 }} aria-hidden />
        </div>
      </div>
    </div>
  );
}

export default MobileComplianceFeed;
