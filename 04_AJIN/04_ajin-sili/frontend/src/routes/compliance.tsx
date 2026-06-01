// compliance.tsx — Module D1 변경감지·알림 MVP 전용 화면.

import { useCallback, useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { DownloadActions } from '@components/common/DownloadActions';
import { CrawlHistoryPanel } from '@components/compliance/CrawlHistoryPanel';
import { CrawlResultsDrawer } from '@components/compliance/CrawlResultsDrawer';
import {
  acknowledgeChange,
  ackComplianceAlarm,
  fetchChangeFeed,
  fetchChangeKpi,
  fetchComplianceAlarms,
  fetchCrawlHistoryStats,
  fetchCrawlResultsList,
  runAllCrawlers,
  runCrawler,
  transitionChangeStatus,
  type ChangeFeedItem,
  type ChangeKpiResponse,
  type ChangeStatus,
  type ComplianceAlarm,
  type CrawlResultMeta,
  type CrawlRunResult,
  type CrawlSlaItem,
  type CrawlerName,
} from '@api/compliance';
import { getComplianceGradeMeta } from '@lib/complianceSeverity';
import { useIsMobile, useIsTablet } from '@hooks/useBreakpoint';
import { AJINMobileCompliance } from '@components/uikit/AJINMobileCompliance';
import { AJINTabletCompliance } from '@components/uikit/AJINTabletCompliance';

interface CrawlerCard {
  id: number;
  key: CrawlerName;
  name: string;
  target: string;
  last: string;
  changes: number;
  status: 'ok' | 'warn' | 'err' | 'idle' | 'busy';
  errors: string[];
  informational: string[];
  mode: 'live' | 'curated' | 'unknown';
  slaStatus: CrawlSlaItem['status'] | 'unknown';
  cadence: string;
  credentialRequired: boolean;
  credentialPresent: boolean;
}

const INFO_PATTERNS = [
  'credentials not configured',
  'live fetch returned 0 items',
  'falling back to curated',
  'robots.txt 가 차단함',
  'live fetch failed: RuntimeError: UNECE',
];

const CRAWLER_META: { key: CrawlerName; id: number; name: string; target: string }[] = [
  { id: 1, key: 'iso', name: 'ISO Crawler', target: 'ISO 14001 / 45001' },
  { id: 2, key: 'msds', name: 'MSDS Crawler', target: '화학물질안전보건자료' },
  { id: 3, key: 'eu_regulation', name: 'EU Regulation', target: 'REACH · RoHS · ELV' },
  { id: 4, key: 'domestic_law', name: 'Domestic Law', target: '산안법 · 화관법 · 환경법' },
  { id: 5, key: 'oem_quality', name: 'OEM Quality', target: 'IATF 16949 · PPAP · FMEA' },
  { id: 6, key: 'apqp', name: 'APQP Crawler', target: 'APQP 단계별 요구사항' },
  { id: 7, key: 'carbon_esg', name: 'Carbon ESG', target: '탄소 배출 / ESG 지표' },
  { id: 8, key: 'ev_battery', name: 'EV Battery', target: 'EV 배터리 (UN R100)' },
  { id: 9, key: 'global_trade', name: 'Global Trade', target: '관세 · FTA · 무역 규제' },
];

function classifyErrors(errs: string[] | undefined): { real: string[]; informational: string[] } {
  const real: string[] = [];
  const informational: string[] = [];
  for (const err of errs ?? []) {
    const lower = err.toLowerCase();
    if (INFO_PATTERNS.some((pattern) => lower.includes(pattern.toLowerCase()))) {
      informational.push(err);
    } else {
      real.push(err);
    }
  }
  return { real, informational };
}

function deriveStatus(
  real: string[],
  informational: string[],
  hasResult: boolean,
  slaStatus: CrawlSlaItem['status'] | 'unknown' = 'unknown',
): CrawlerCard['status'] {
  if (slaStatus === 'fresh') return 'ok';
  if (slaStatus === 'stale' || slaStatus === 'missing_credential') return 'warn';
  if (slaStatus === 'degraded') return 'warn';
  if (!hasResult) return 'idle';
  if (real.length > 0) return 'err';
  if (informational.length > 0) return 'warn';
  return 'ok';
}

function gradeBadgeText(value: string): string {
  const meta = getComplianceGradeMeta(value);
  return `${meta.grade} · ${meta.actionLabel}`;
}

function slaBadgeText(status: CrawlerCard['slaStatus']): string {
  const labels: Record<CrawlerCard['slaStatus'], string> = {
    fresh: 'FRESH',
    stale: 'STALE',
    degraded: 'DEGRADED',
    missing_credential: 'CREDENTIAL',
    unknown: 'UNKNOWN',
  };
  return labels[status];
}

function shortDateTime(value: string | undefined): string {
  if (!value) return '—';
  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) return value.slice(0, 16);
  return new Date(parsed).toISOString().slice(5, 16).replace('T', ' ');
}

function toCrawlerCard(
  meta: typeof CRAWLER_META[number],
  result?: CrawlRunResult,
  sla?: CrawlSlaItem,
): CrawlerCard {
  const { real, informational } = classifyErrors(result?.errors);
  const slaStatus = sla?.status ?? 'unknown';
  return {
    id: meta.id,
    key: meta.key,
    name: meta.name,
    target: meta.target,
    last: shortDateTime(sla?.last_success_at || result?.crawled_at),
    changes: result?.updates_found ?? 0,
    status: deriveStatus(real, informational, Boolean(result), slaStatus),
    errors: real,
    informational,
    mode: sla?.source_type ?? result?.source_type ?? (informational.length > 0 ? 'curated' : 'unknown'),
    slaStatus,
    cadence: sla?.cadence ?? '',
    credentialRequired: Boolean(sla?.credential_required),
    credentialPresent: sla?.credential_present ?? true,
  };
}

function toCrawlerCardFromMeta(
  meta: typeof CRAWLER_META[number],
  item?: CrawlResultMeta,
  sla?: CrawlSlaItem,
): CrawlerCard {
  const { real, informational } = classifyErrors(item?.errors);
  const slaStatus = sla?.status ?? 'unknown';
  return {
    id: meta.id,
    key: meta.key,
    name: meta.name,
    target: meta.target,
    last: shortDateTime(sla?.last_success_at || item?.crawled_at),
    changes: item?.updates_found ?? 0,
    status: deriveStatus(real, informational, Boolean(item), slaStatus),
    errors: real,
    informational,
    mode: sla?.source_type ?? item?.source_type ?? (informational.length > 0 ? 'curated' : 'unknown'),
    slaStatus,
    cadence: sla?.cadence ?? '',
    credentialRequired: Boolean(sla?.credential_required),
    credentialPresent: sla?.credential_present ?? true,
  };
}

function buildChangesMarkdown(items: ChangeFeedItem[], total: number): string {
  const lines = ['# 법규 변경 감지 보고서', '', `총 변경 건수: **${total}건**`, ''];
  lines.push('| 등급 | 상태 | 규제 | 항목 | 감지일 | 영향 부서 |');
  lines.push('|---|---|---|---|---|---|');
  for (const item of items) {
    lines.push([
      item.grade,
      item.status,
      item.regulation_type,
      item.item_title || item.item_id,
      (item.detected_at || '').slice(0, 10),
      item.affected_departments.join(', ') || '—',
    ].join(' | ').replace(/^/, '| ').replace(/$/, ' |'));
  }
  return lines.join('\n');
}

const STATUS_OPTIONS: ChangeStatus[] = ['pending', 'reviewing', 'planning', 'announced', 'done'];

export function Compliance() {
  const [searchParams] = useSearchParams();
  const focusId = searchParams.get('focus');
  const [kpi, setKpi] = useState<ChangeKpiResponse | null>(null);
  const [feed, setFeed] = useState<ChangeFeedItem[]>([]);
  const [feedTotal, setFeedTotal] = useState(0);
  const [alarms, setAlarms] = useState<ComplianceAlarm[]>([]);
  const [crawlers, setCrawlers] = useState<CrawlerCard[]>(
    CRAWLER_META.map((meta) => toCrawlerCard(meta)),
  );
  const [selectedCrawler, setSelectedCrawler] = useState<{ name: string; label?: string } | null>(null);
  const [crawlBusy, setCrawlBusy] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const refreshD1 = useCallback(async () => {
    // Postmortem 2026-05-27 — Promise.allSettled 로 부분 실패 허용.
    // 이전 Promise.all 은 5개 중 1개라도 reject 되면 전체 catch 로 빠져 사용자에게
    // "전체 페이지 깨짐" 으로 보였음. 부분 실패는 해당 위젯만 빈 상태로 두고
    // 나머지는 정상 렌더 + 안내 메시지로 신뢰도 유지.
    const settled = await Promise.allSettled([
      fetchChangeKpi(30),
      fetchChangeFeed({ limit: 30, offset: 0, includeFiltered: false }),
      fetchComplianceAlarms(0, 8),
      fetchCrawlResultsList(),
      fetchCrawlHistoryStats(),
    ]);
    const [kpiRes, feedRes, alarmsRes, crawlerRes, crawlerStatsRes] = settled;
    const failed: string[] = [];

    if (kpiRes.status === 'fulfilled') {
      setKpi(kpiRes.value);
    } else {
      failed.push('KPI');
    }

    if (feedRes.status === 'fulfilled') {
      setFeed(feedRes.value.items);
      setFeedTotal(feedRes.value.total);
    } else {
      failed.push('변경 피드');
    }

    if (alarmsRes.status === 'fulfilled') {
      setAlarms(alarmsRes.value.items);
    } else {
      failed.push('주요 알람');
    }

    const crawlerData = crawlerRes.status === 'fulfilled' ? crawlerRes.value : null;
    const crawlerStats = crawlerStatsRes.status === 'fulfilled' ? crawlerStatsRes.value : null;
    if (!crawlerData) failed.push('크롤러 목록');
    if (!crawlerStats) failed.push('크롤 통계');

    const crawlerByName = new Map(crawlerData?.crawlers.map((item) => [item.name, item]) ?? []);
    setCrawlers(CRAWLER_META.map((meta) => (
      toCrawlerCardFromMeta(meta, crawlerByName.get(meta.key), crawlerStats?.sla?.[meta.key])
    )));

    setLoadError(failed.length > 0
      ? `일부 데이터 로드 실패 (${failed.join(', ')}) — 나머지는 정상 표시됩니다.`
      : null);
  }, []);

  useEffect(() => {
    let cancelled = false;
    refreshD1().catch((err: unknown) => {
      if (!cancelled) setLoadError(err instanceof Error ? err.message : String(err));
    });
    return () => {
      cancelled = true;
    };
  }, [refreshD1]);

  const handleRunAll = useCallback(async () => {
    if (crawlBusy) return;
    setCrawlBusy(true);
    const startedAt = Date.now();
    const pollInterval = window.setInterval(() => {
      fetchCrawlResultsList()
        .then((res) => {
          const crawlerByName = new Map(res.crawlers.map((item) => [item.name, item]));
          setCrawlers((prev) => prev.map((card) => {
            const meta = CRAWLER_META.find((item) => item.key === card.key);
            const item = crawlerByName.get(card.key);
            const updatedAt = item?.crawled_at ? Date.parse(item.crawled_at) : 0;
            if (!meta || updatedAt < startedAt - 1000) return card;
            return toCrawlerCardFromMeta(meta, item);
          }));
        })
        .catch(() => {});
    }, 1500);

    try {
      const result = await runAllCrawlers();
      setCrawlers(CRAWLER_META.map((meta) => toCrawlerCard(meta, result.crawlers[meta.key])));
      await refreshD1();
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : String(err));
    } finally {
      window.clearInterval(pollInterval);
      setCrawlBusy(false);
    }
  }, [crawlBusy, refreshD1]);

  const handleRetryCrawler = useCallback(async (name: CrawlerName) => {
    setCrawlers((prev) => prev.map((card) => (
      card.key === name ? { ...card, status: 'busy' as const } : card
    )));
    try {
      const result = await runCrawler(name);
      const meta = CRAWLER_META.find((item) => item.key === name);
      if (!meta) return;
      setCrawlers((prev) => prev.map((card) => (
        card.key === name ? toCrawlerCard(meta, result) : card
      )));
      await refreshD1();
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setCrawlers((prev) => prev.map((card) => (
        card.key === name ? { ...card, status: 'err' as const, errors: [message] } : card
      )));
    }
  }, [refreshD1]);

  const handleAckChange = useCallback(async (id: number) => {
    await acknowledgeChange(id);
    await refreshD1();
  }, [refreshD1]);

  const handleTransition = useCallback(async (id: number, status: ChangeStatus) => {
    await transitionChangeStatus(id, status);
    await refreshD1();
  }, [refreshD1]);

  const handleAckAlarm = useCallback(async (id: string) => {
    await ackComplianceAlarm(id);
    setAlarms((prev) => prev.map((item) => (
      item.id === id ? { ...item, acknowledged: true } : item
    )));
  }, []);

  // v3.6 — 모바일/태블릿 viewport early return (Design System v3.5 reference 매칭)
  const isMobileCompliance = useIsMobile();
  const isTabletCompliance = useIsTablet();
  if (isMobileCompliance) return <AJINMobileCompliance />;
  if (isTabletCompliance) return <AJINTabletCompliance />;

  return (
    <div className="page lg-page" data-screen-label="D · Compliance">
      <section className="lg-hero">
        <div className="lg-hero-eyebrow">COMPLIANCE MONITORING · D1 MVP</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <div className="ne-orb sm" aria-hidden style={{ flexShrink: 0 }} />
          <h1 className="lg-display" style={{ margin: 0 }}>변경감지 / 알림</h1>
        </div>
        <p className="lg-sub">
          외부 규제 소스 수집 결과를 비교해 신규·개정 항목을 감지하고, 미확인 변경과 알림 큐를 중심으로 대응 상태를 관리합니다.
        </p>
        <div className="lg-actions" style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button className="lg-btn" onClick={handleRunAll} disabled={crawlBusy}>
            {crawlBusy ? '실행 중…' : 'RUN ALL'}
          </button>
          <Link className="lg-btn ghost" to="/profile/notifications">
            알림 설정
          </Link>
        </div>
        {loadError && (
          <p className="lg-sub" style={{ color: 'var(--hud-red, #f33)' }}>
            백엔드 연결 실패: {loadError}
          </p>
        )}
      </section>

      <section className="lg-card">
        <div className="lg-card-h">
          <div>
            <div className="lg-eyebrow">D1 KPI · 최근 30일</div>
            <h2 className="lg-h2">변경 대응 현황</h2>
          </div>
          <span className="lg-pill">미확인 {feed.filter((item) => !item.acknowledged).length}건</span>
        </div>
        <div className="lg-metric-row">
          <div className={`lg-metric ${getComplianceGradeMeta('CRITICAL').className}`}>
            <span className="k">CRITICAL · 즉시</span>
            <span className="v">{kpi?.month_critical ?? 0}</span>
          </div>
          <div className={`lg-metric ${getComplianceGradeMeta('HIGH').className}`}>
            <span className="k">HIGH · 우선</span>
            <span className="v">{kpi?.month_high ?? 0}</span>
          </div>
          <div className={`lg-metric ${getComplianceGradeMeta('MEDIUM').className}`}>
            <span className="k">MEDIUM · 검토</span>
            <span className="v">{kpi?.month_medium ?? 0}</span>
          </div>
          <div className={`lg-metric ${getComplianceGradeMeta('LOW').className}`}>
            <span className="k">LOW · 모니터링</span>
            <span className="v">{kpi?.month_low ?? 0}</span>
          </div>
        </div>
      </section>

      <section className="lg-card">
        <div className="lg-card-h">
          <div>
            <div className="lg-eyebrow">ALARMS · 실시간 알림</div>
            <h2 className="lg-h2">주요 알림</h2>
          </div>
        </div>
        <div className="lg-table-wrap">
          <table className="lg-table">
            <thead>
              <tr><th>등급</th><th>알림</th><th>시간</th><th></th></tr>
            </thead>
            <tbody>
              {alarms.length === 0 && (
                <tr><td colSpan={4} className="dim">표시할 알림이 없습니다.</td></tr>
              )}
              {alarms.map((alarm) => {
                const meta = getComplianceGradeMeta(alarm.severity);
                return (
                <tr key={alarm.id} className={`lg-risk-row ${meta.className}`}>
                  <td>
                    <span
                      className={`lg-tag ${meta.className}`}
                      title={`${meta.grade} · ${meta.labelKo} · ${meta.actionLabel}`}
                    >
                      {gradeBadgeText(alarm.severity)}
                    </span>
                  </td>
                  <td>
                    <strong>{alarm.title}</strong>
                    <div className="dim">{alarm.detail}</div>
                  </td>
                  <td className="mono dim">{shortDateTime(alarm.timestamp)}</td>
                  <td>
                    {alarm.acknowledged ? (
                      <span className="lg-ok">처리됨</span>
                    ) : (
                      <button className="lg-btn ghost sm" onClick={() => void handleAckAlarm(alarm.id)}>
                        확인
                      </button>
                    )}
                  </td>
                </tr>
              );
              })}
            </tbody>
          </table>
        </div>
      </section>

      <section className="lg-card">
        <div className="lg-card-h">
          <div>
            <div className="lg-eyebrow">CHANGE FEED · {feedTotal}건</div>
            <h2 className="lg-h2">변경 피드</h2>
          </div>
          <DownloadActions
            content={() => buildChangesMarkdown(feed, feedTotal)}
            basename={`compliance_changes_${new Date().toISOString().slice(0, 10)}`}
            source="compliance"
            metadata={{ title: '법규 변경 감지 보고서', doc_type: 'compliance_changes' }}
          />
        </div>
        <div className="lg-table-wrap">
          <table className="lg-table">
            <thead>
              <tr>
                <th>등급</th>
                <th>상태</th>
                <th>규제 / 항목</th>
                <th>영향</th>
                <th>감지</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {feed.length === 0 && (
                <tr><td colSpan={6} className="dim">감지된 변경이 없습니다.</td></tr>
              )}
              {feed.map((item) => {
                const meta = getComplianceGradeMeta(item.grade);
                return (
                <tr
                  key={item.id}
                  className={`lg-risk-row ${meta.className}`}
                  style={focusId && String(item.id) === focusId ? { outline: '1px solid var(--hud-primary)' } : undefined}
                >
                  <td>
                    <span
                      className={`lg-tag ${meta.className}`}
                      title={`${meta.grade} · ${meta.labelKo} · ${meta.actionLabel}`}
                    >
                      {gradeBadgeText(item.grade)}
                    </span>
                  </td>
                  <td>
                    <select
                      className="lg-select"
                      value={item.status}
                      onChange={(event) => void handleTransition(item.id, event.target.value as ChangeStatus)}
                    >
                      {STATUS_OPTIONS.map((status) => (
                        <option key={status} value={status}>{status}</option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <strong>{item.regulation_type}</strong>
                    <div>{item.item_title || item.item_id}</div>
                    {item.summary_ko && <div className="dim">{item.summary_ko}</div>}
                  </td>
                  <td className="dim">
                    {(item.affected_departments.length ? item.affected_departments : ['—']).join(', ')}
                  </td>
                  <td className="mono dim">{shortDateTime(item.detected_at)}</td>
                  <td>
                    {item.acknowledged ? (
                      <span className="lg-ok">처리됨</span>
                    ) : (
                      <button className="lg-btn ghost sm" onClick={() => void handleAckChange(item.id)}>
                        확인
                      </button>
                    )}
                  </td>
                </tr>
              );
              })}
            </tbody>
          </table>
        </div>
      </section>

      <section className="lg-card">
        <div className="lg-card-h">
          <div>
            <div className="lg-eyebrow">CRAWLERS · 9개</div>
            <h2 className="lg-h2">크롤러 실행 현황</h2>
          </div>
        </div>
        <div className="lg-crawl-grid">
          {crawlers.map((crawler) => {
            const dotClass =
              crawler.status === 'ok' ? 'ok'
                : crawler.status === 'err' ? 'err'
                  : crawler.status === 'warn' || crawler.status === 'busy' ? 'warn'
                    : '';
            return (
              <div
                key={crawler.key}
                className="lg-crawl"
                onClick={() => setSelectedCrawler({ name: crawler.key, label: crawler.name })}
                style={{ cursor: 'pointer' }}
              >
                <div className="lg-crawl-h" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                    <span className="num">{String(crawler.id).padStart(2, '0')}</span>
                    <span className={'lg-dot ' + dotClass} />
                  </span>
	                  {crawler.mode === 'live' && <span className="lg-state-pill ok">LIVE</span>}
	                  {crawler.mode === 'curated' && <span className="lg-state-pill warn">CURATED</span>}
	                  {crawler.slaStatus !== 'unknown' && (
	                    <span className={'lg-state-pill ' + (crawler.slaStatus === 'fresh' ? 'ok' : 'warn')}>
	                      {slaBadgeText(crawler.slaStatus)}
	                    </span>
	                  )}
	                </div>
	                <div className="lg-crawl-name">{crawler.name}</div>
	                <div className="lg-crawl-target">{crawler.target}</div>
	                <div className="lg-crawl-foot">
	                  <span className="mono dim" title={crawler.cadence || undefined}>{crawler.last}</span>
	                  {crawler.status === 'busy'
	                    ? <span className="dim">실행 중…</span>
	                    : crawler.changes
	                      ? <span className="lg-chg">{crawler.changes}건</span>
	                      : <span className="dim">—</span>}
	                </div>
	                {crawler.credentialRequired && !crawler.credentialPresent && (
	                  <div className="lg-crawl-info">credential missing</div>
	                )}
                {crawler.errors.length > 0 && (
                  <div className="lg-crawl-err" title={crawler.errors.join('\n')}>{crawler.errors[0]}</div>
                )}
                {crawler.errors.length === 0 && crawler.informational.length > 0 && (
                  <div className="lg-crawl-info" title={crawler.informational.join('\n')}>큐레이트 모드</div>
                )}
                <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
                  <button
                    className="lg-btn ghost sm"
                    onClick={(event) => {
                      event.stopPropagation();
                      setSelectedCrawler({ name: crawler.key, label: crawler.name });
                    }}
                    style={{ flex: 1, fontSize: 11, padding: '4px 10px', minWidth: 0 }}
                  >
                    상세
                  </button>
                  <button
                    className="lg-btn ghost sm"
                    onClick={(event) => {
                      event.stopPropagation();
                      void handleRetryCrawler(crawler.key);
                    }}
                    disabled={crawler.status === 'busy'}
                    style={{ flex: 1, fontSize: 11, padding: '4px 10px', minWidth: 0 }}
                  >
                    {crawler.status === 'busy' ? '…' : '재시도'}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      <section className="lg-card">
        <CrawlHistoryPanel />
      </section>

      <CrawlResultsDrawer
        crawlerName={selectedCrawler?.name ?? null}
        displayName={selectedCrawler?.label}
        isOpen={selectedCrawler !== null}
        onClose={() => setSelectedCrawler(null)}
      />
    </div>
  );
}
