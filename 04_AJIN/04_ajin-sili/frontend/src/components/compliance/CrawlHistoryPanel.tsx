// F12 frontend — 최근 24h 크롤 실행 통계 + 최근 10건 audit row.
// 페르소나:
//   - 현직자(시니어): incident 추적 — 실패한 크롤 즉시 식별
//   - 신입: "오늘 무슨 일이 있었나" 학습 자료

import { useEffect, useState } from 'react';
import {
  fetchCrawlHistory,
  fetchCrawlHistoryStats,
  type CrawlRunAuditRow,
  type CrawlHistoryStats,
} from '@api/compliance';

export function CrawlHistoryPanel() {
  const [stats, setStats] = useState<CrawlHistoryStats | null>(null);
  const [runs, setRuns] = useState<CrawlRunAuditRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAll, setShowAll] = useState(false);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, h] = await Promise.all([
        fetchCrawlHistoryStats(),
        fetchCrawlHistory({ limit: 20 }),
      ]);
      setStats(s);
      setRuns(h.runs);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const visibleRuns = showAll ? runs : runs.slice(0, 8);
  const slaItems = stats?.sla ? Object.values(stats.sla) : [];
  const staleSlaCount = slaItems.filter((item) => item && item.status !== 'fresh').length;

  return (
    <div>
      <div className="lg-card-h">
        <div>
          <div className="lg-eyebrow">CRAWL AUDIT · 최근 24h</div>
          <h2 className="lg-h2">크롤러 실행 이력</h2>
        </div>
        <div className="lg-actions">
          <button className="lg-btn sm ghost" onClick={() => void load()}>
            새로고침
          </button>
        </div>
      </div>

      {error && <div className="lg-error" style={{ padding: 8 }}>{error}</div>}
      {loading && !stats && <div className="lg-sub" style={{ padding: 8 }}>불러오는 중…</div>}

      {stats && (
        <div className="lg-metric-row" style={{ marginBottom: 12 }}>
          <div className="lg-metric">
            <span className="k">총 실행</span>
            <span className="v">{stats.total_runs}</span>
          </div>
          <div className={'lg-metric ' + (stats.failed_runs > 0 ? 'warn' : '')}>
            <span className="k">실패</span>
            <span className="v">{stats.failed_runs}</span>
          </div>
          <div className="lg-metric">
            <span className="k">크롤러 수</span>
            <span className="v">{stats.per_crawler.length}</span>
          </div>
          <div className="lg-metric">
            <span className="k">윈도우</span>
            <span className="v">{stats.window}</span>
          </div>
          <div className={'lg-metric ' + (staleSlaCount > 0 ? 'warn' : '')}>
            <span className="k">SLA 경고</span>
            <span className="v">{staleSlaCount}</span>
          </div>
        </div>
      )}

      {runs.length === 0 && !loading && (
        <div className="lg-sub" style={{ padding: 12, fontSize: 12 }}>
          최근 24시간 내 실행 이력이 없습니다.
          <code style={{ marginLeft: 6, fontSize: 11 }}>POST /api/compliance/crawl/run-all</code>
          {' '}또는 cron 가동 후 자동 적재됩니다.
        </div>
      )}

      {runs.length > 0 && (
        <div className="lg-table-wrap">
          <table className="lg-table">
            <thead>
              <tr>
                <th>시각</th>
                <th>크롤러</th>
                <th>결과</th>
                <th>변경</th>
                <th>경과(ms)</th>
                <th>HTTP</th>
                <th>트리거</th>
              </tr>
            </thead>
            <tbody>
              {visibleRuns.map((r) => (
                <tr key={r.run_id}>
                  <td className="mono dim" style={{ fontSize: 11 }}>
                    {r.started_at.slice(5, 16).replace('T', ' ')}
                  </td>
                  <td>{r.crawler_name}</td>
                  <td>
                    {r.ok ? (
                      <span className="lg-state-pill ok">● OK</span>
                    ) : (
                      <span
                        className="lg-state-pill crit"
                        title={r.errors || ''}
                      >
                        ● FAIL
                      </span>
                    )}
                  </td>
                  <td className="mono">{r.updates_found || '—'}</td>
                  <td className="mono dim">{r.elapsed_ms}</td>
                  <td className="mono dim">{r.http_status ?? '—'}</td>
                  <td>
                    <span className="lg-pill" style={{ fontSize: 10 }}>
                      {r.trigger_source || '—'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {runs.length > 8 && (
            <div style={{ textAlign: 'center', marginTop: 8 }}>
              <button
                className="lg-btn ghost sm"
                onClick={() => setShowAll(!showAll)}
              >
                {showAll ? '접기' : `+${runs.length - 8}건 더 보기`}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
