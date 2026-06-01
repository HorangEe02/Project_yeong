// AJINMobileCompliance — iPhone 모바일 규제 모니터 화면.
// reference: uiux/.../mobile-theme.css (aj-screen / aj-bg-grad / aj-glass / aj-grid-2 / aj-divlist).
//
// 2026-05-28 사용자 모바일 피드백 (5건 fix):
//   A1 KPI minHeight 통일 — 두 카드 시각적 길이 불일치 해소
//   A2 paddingBottom 증가 — BottomTabBar 가림 방지 (safe-area 포함)
//   A3 "지금 9 크롤러 일괄 실행" RUN ALL CTA 추가 — runAllCrawlers API
//   A4 9 크롤러 실제 status fetch — hardcoded "OK" 제거, fetchCrawlResultsList
//      + 카드 onClick → runCrawler(name) 개별 retry
//   A5 "전체 →" → /m/compliance/feed 신규 라우트 (무한 스크롤 + 필터 + ack)

import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertTriangle, ChevronRight, Play, RefreshCw, Shield } from 'lucide-react';

import {
  fetchChangeFeed,
  fetchChangeKpi,
  fetchCrawlResultsList,
  runAllCrawlers,
  runCrawler,
  type ChangeFeedItem,
  type ChangeKpiResponse,
  type CrawlResultMeta,
  type CrawlerName,
} from '@api/compliance';

const CRAWLERS: { k: CrawlerName; ko: string }[] = [
  { k: 'iso',           ko: 'ISO' },
  { k: 'msds',          ko: 'MSDS' },
  { k: 'eu_regulation', ko: 'EU REG' },
  { k: 'domestic_law',  ko: '국내법' },
  { k: 'oem_quality',   ko: 'OEM Q' },
  { k: 'apqp',          ko: 'APQP' },
  { k: 'carbon_esg',    ko: 'ESG' },
  { k: 'ev_battery',    ko: 'EV Batt' },
  { k: 'global_trade',  ko: 'Trade' },
];

const GRADE_COLOR: Record<string, string> = {
  CRITICAL: '#FF7565',
  HIGH:     '#E8A317',
  MEDIUM:   '#4FB774',
  LOW:      'rgba(127,127,127,0.6)',
};

function statusBadge(status?: string): { label: string; cls: string } {
  const s = (status || '').toLowerCase();
  if (s === 'success' || s === 'ok') return { label: 'OK', cls: 'ok' };
  if (s === 'partial')               return { label: 'PART', cls: 'warn' };
  if (s === 'failed' || s === 'error') return { label: 'FAIL', cls: 'crit' };
  if (s === 'running')               return { label: '…', cls: 'warn' };
  return { label: '—', cls: '' };
}

export function AJINMobileCompliance() {
  const navigate = useNavigate();
  const [kpi, setKpi] = useState<ChangeKpiResponse | null>(null);
  const [feed, setFeed] = useState<ChangeFeedItem[]>([]);
  const [crawlerByName, setCrawlerByName] = useState<Record<string, CrawlResultMeta>>({});
  const [loading, setLoading] = useState(true);
  const [runAllBusy, setRunAllBusy] = useState(false);
  const [perBusy, setPerBusy] = useState<Record<string, boolean>>({});
  const [err, setErr] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setErr(null);
    const settled = await Promise.allSettled([
      fetchChangeKpi(),
      fetchChangeFeed({ limit: 6 }),
      fetchCrawlResultsList(),
    ]);
    const [k, f, c] = settled;
    if (k.status === 'fulfilled') setKpi(k.value);
    if (f.status === 'fulfilled') setFeed(f.value.items);
    if (c.status === 'fulfilled') {
      const map: Record<string, CrawlResultMeta> = {};
      for (const item of c.value.crawlers) map[item.name] = item;
      setCrawlerByName(map);
    }
    const allFailed = settled.every((s) => s.status === 'rejected');
    if (allFailed) setErr('백엔드 연결 실패 — 잠시 후 다시 시도');
  }, []);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        await reload();
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => { alive = false; };
  }, [reload]);

  const handleRunAll = async () => {
    if (runAllBusy) return;
    setRunAllBusy(true);
    setErr(null);
    try {
      await runAllCrawlers();
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setRunAllBusy(false);
    }
  };

  const handleRetry = async (name: CrawlerName) => {
    if (perBusy[name]) return;
    setPerBusy((p) => ({ ...p, [name]: true }));
    try {
      await runCrawler(name);
      const c = await fetchCrawlResultsList();
      const map: Record<string, CrawlResultMeta> = {};
      for (const item of c.crawlers) map[item.name] = item;
      setCrawlerByName(map);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setPerBusy((p) => ({ ...p, [name]: false }));
    }
  };

  const pendingCount = kpi?.open_count ?? 0;
  const todayCount = kpi?.today_new ?? feed.length;

  return (
    <div className="aj-mobile" style={{ minHeight: '100vh' }}>
      <div className="aj-screen dark" style={{ position: 'relative', minHeight: '100vh' }}>
        <div className="aj-bg-grad dark" />

        <div
          className="aj-scroll"
          style={{
            paddingTop: 18,
            paddingBottom: 'calc(env(safe-area-inset-bottom, 0px) + 140px)',
            position: 'relative',
            zIndex: 3,
            minHeight: '100vh',
          }}
        >
          {/* Header */}
          <div style={{ padding: '12px 20px 4px' }}>
            <div className="aj-mono" style={{ color: 'var(--aj-gold, #FCB132)' }}>
              COMPLIANCE · D1
            </div>
            <h1 style={{ margin: '6px 0 4px', fontSize: 28, fontWeight: 700, letterSpacing: '-0.018em' }}>
              규제 모니터
            </h1>
            <div style={{ fontSize: 13, opacity: 0.65 }}>
              9개 크롤러 · 변경 알림 · 영향도 평가
            </div>
          </div>

          {/* A1 KPI strip 2-col — minHeight 통일 + space-between 정렬 */}
          <div className="aj-grid-2" style={{ paddingTop: 12, alignItems: 'stretch' }}>
            <div className="aj-glass aj-kpi" style={{ minHeight: 124, display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
              <div className="k">미처리 변경</div>
              <div className="v">{loading ? '—' : pendingCount}</div>
              <div className={'delta ' + (pendingCount > 0 ? 'down' : '')}>
                {pendingCount > 0 ? '검토 필요' : 'all clear'}
              </div>
            </div>
            <div className="aj-glass aj-kpi" style={{ minHeight: 124, display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
              <div className="k">오늘 신규</div>
              <div className="v">{loading ? '—' : todayCount}</div>
              <div className={'delta ' + (todayCount > 0 ? 'up' : '')}>
                {todayCount > 0 ? '+신규' : '변경 없음'}
              </div>
            </div>
          </div>

          {/* A3 RUN ALL CTA */}
          <div style={{ padding: '14px 12px 0' }}>
            <button
              type="button"
              onClick={handleRunAll}
              disabled={runAllBusy}
              style={{
                width: '100%',
                minHeight: 48,
                borderRadius: 14,
                border: '1px solid rgba(252,177,50,0.45)',
                background: runAllBusy ? 'rgba(252,177,50,0.18)' : 'var(--aj-gold, #FCB132)',
                color: runAllBusy ? 'inherit' : '#1A1004',
                fontFamily: 'inherit',
                fontSize: 14,
                fontWeight: 700,
                letterSpacing: '0.02em',
                cursor: runAllBusy ? 'wait' : 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 8,
              }}
            >
              {runAllBusy ? <RefreshCw size={16} /> : <Play size={16} />}
              {runAllBusy ? '크롤링 진행 중…' : '지금 9 크롤러 일괄 실행'}
            </button>
          </div>

          {err && (
            <div className="aj-glass" style={{ margin: '12px 16px 0', padding: 12, fontSize: 12, color: '#FF7565' }}>
              <AlertTriangle size={14} style={{ marginRight: 6, verticalAlign: 'middle' }} />
              {err}
            </div>
          )}

          {/* 변경 알림 feed */}
          <div className="aj-sect-h">
            <h3>변경 알림 · Feed</h3>
            <button
              type="button"
              className="more"
              onClick={() => navigate('/m/compliance/feed')}
              style={{
                background: 'transparent',
                border: 0,
                cursor: 'pointer',
                color: 'inherit',
                fontFamily: 'inherit',
              }}
            >
              전체 →
            </button>
          </div>
          <div className="aj-glass aj-divlist" style={{ margin: '0 12px' }}>
            {loading && (
              <div style={{ padding: 18, textAlign: 'center', opacity: 0.6, fontSize: 13 }}>
                <RefreshCw size={14} style={{ marginRight: 6, verticalAlign: 'middle' }} />
                불러오는 중…
              </div>
            )}
            {!loading && feed.length === 0 && (
              <div style={{ padding: 18, textAlign: 'center', opacity: 0.6, fontSize: 13 }}>
                <Shield size={14} style={{ marginRight: 6, verticalAlign: 'middle' }} />
                새로운 규제 변경 없음
              </div>
            )}
            {!loading && feed.slice(0, 5).map((item) => {
              const grade = (item.grade || 'LOW').toUpperCase();
              const color = GRADE_COLOR[grade] ?? GRADE_COLOR.LOW;
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => navigate(`/compliance?change_id=${item.id}`)}
                  style={{
                    display: 'grid',
                    gridTemplateColumns: '52px 1fr auto',
                    gap: 10,
                    padding: '12px 14px',
                    alignItems: 'center',
                    background: 'transparent',
                    border: 0,
                    cursor: 'pointer',
                    color: 'inherit',
                    fontFamily: 'inherit',
                    textAlign: 'left',
                    width: '100%',
                  }}
                >
                  <span className="aj-mono" style={{ fontSize: 10, color, fontWeight: 600 }}>
                    {grade}
                  </span>
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontSize: 14, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {item.item_title || '제목 없음'}
                    </div>
                    <div style={{ fontSize: 11, opacity: 0.6, marginTop: 1, fontFamily: '"JetBrains Mono", ui-monospace, monospace' }}>
                      {item.regulation_type} · {(item.detected_at || '').slice(0, 16).replace('T', ' ')}
                    </div>
                  </div>
                  <ChevronRight size={14} aria-hidden style={{ opacity: 0.5 }} />
                </button>
              );
            })}
          </div>

          {/* A4 9 crawlers 실제 status + 개별 retry */}
          <div className="aj-sect-h">
            <h3>크롤러 · 9</h3>
            <span className="more">자동 02:00-02:40 KST · 탭하여 재실행</span>
          </div>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(3, 1fr)',
              gap: 8,
              padding: '0 12px',
            }}
          >
            {CRAWLERS.map((c) => {
              const item = crawlerByName[c.k];
              const derivedStatus = item ? (item.errors && item.errors.length > 0 ? 'failed' : 'success') : undefined;
              const badge = statusBadge(perBusy[c.k] ? 'running' : derivedStatus);
              return (
                <button
                  key={c.k}
                  type="button"
                  onClick={() => handleRetry(c.k)}
                  disabled={perBusy[c.k] || runAllBusy}
                  className="aj-glass"
                  title={item?.crawled_at ? `최종: ${item.crawled_at.slice(0, 16).replace('T', ' ')}` : '미실행 — 탭하여 실행'}
                  style={{
                    padding: '10px 8px',
                    borderRadius: 14,
                    textAlign: 'center',
                    fontSize: 12,
                    fontWeight: 500,
                    border: 0,
                    cursor: perBusy[c.k] || runAllBusy ? 'wait' : 'pointer',
                    color: 'inherit',
                    fontFamily: 'inherit',
                  }}
                >
                  <div className="aj-mono" style={{ fontSize: 9, opacity: 0.55 }}>
                    {c.k.toUpperCase()}
                  </div>
                  <div style={{ marginTop: 2 }}>{c.ko}</div>
                  <span
                    className={'aj-status ' + badge.cls}
                    style={{ marginTop: 6, display: 'inline-block' }}
                  >
                    {badge.label}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* FAB → desktop full view */}
        <button
          type="button"
          onClick={() => navigate('/compliance')}
          aria-label="데스크탑 전체 보기"
          title="데스크탑 전체 보기"
          style={{
            position: 'fixed',
            right: 16,
            bottom: 'calc(env(safe-area-inset-bottom, 0px) + 80px)',
            width: 52,
            height: 52,
            borderRadius: 999,
            background: 'var(--aj-gold, #FCB132)',
            color: '#1A1004',
            border: 0,
            cursor: 'pointer',
            boxShadow: '0 12px 28px -10px rgba(252,177,50,0.55)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 20,
          }}
        >
          <AlertTriangle size={20} aria-hidden />
        </button>
      </div>
    </div>
  );
}

export default AJINMobileCompliance;
