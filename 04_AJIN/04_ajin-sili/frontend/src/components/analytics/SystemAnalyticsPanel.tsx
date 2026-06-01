// Day 5++ — RightPanel 의 'analytics' 모드 본체.
// SYSTEM ANALYTICS · 시스템 분석 · REALTIME ●
// + GPU Gauge + LATENCY/QPS + DATA INGESTION 5종.

import { useTranslation } from 'react-i18next';
import { useSystemAnalytics } from '@hooks/useSystemAnalytics';
import { GPUGauge } from './GPUGauge';
import { MetricCard } from './MetricCard';
import { DataIngestionList } from './DataIngestionList';

function formatQps(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(n);
}

export function SystemAnalyticsPanel() {
  const { t } = useTranslation();
  const { data, loading, error } = useSystemAnalytics(5000);

  return (
    <div className="analytics-panel" role="region" aria-label="System Analytics">
      <header className="analytics-panel__header">
        <div className="analytics-panel__title">
          <span className="label-en">{t('analytics.title')}</span>
          <span className="label-ko">· {t('analytics.subtitle')}</span>
        </div>
        <span
          className="analytics-panel__realtime"
          data-active={data !== null || undefined}
        >
          <span className="dot dot-pulse" aria-hidden="true" />
          <span className="label-en">{t('analytics.realtime')}</span>
        </span>
      </header>

      {error && (
        <div className="analytics-panel__error" role="alert">
          {error}
        </div>
      )}

      <div className="analytics-panel__gauge">
        <GPUGauge value={data?.gpu_pct ?? 0} />
      </div>

      <div className="analytics-panel__metrics">
        <MetricCard
          labelEn={t('analytics.latency')}
          labelKo={t('analytics.latency_ko')}
          value={data ? `${data.latency_ms}ms` : '—'}
          emphasized
        />
        <MetricCard
          labelEn={t('analytics.qps')}
          labelKo={t('analytics.qps_ko')}
          value={data ? formatQps(data.qps) : '—'}
        />
      </div>

      <section className="analytics-panel__section">
        <header className="analytics-panel__section-h">
          <span className="label-en">{t('analytics.ingestion.title')}</span>
          <span className="label-ko">· {t('analytics.ingestion.subtitle')}</span>
        </header>
        {data ? (
          <DataIngestionList items={data.ingestion} />
        ) : loading ? (
          <div className="analytics-panel__loading">{t('common.loading')}</div>
        ) : null}
      </section>
    </div>
  );
}
