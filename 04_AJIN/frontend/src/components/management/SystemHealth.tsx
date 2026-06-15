// SystemHealth.tsx — v4.8 F-System.
// Runtime cards for scheduler, database, vector, storage, and external posture.

import { useEffect, useState } from 'react';
import { fetchSystemHealthExtended, type SystemHealthExtended } from '@api/management';

const POLL_MS = 30_000;

function ledColor(status: string | undefined): string {
  switch ((status || '').toLowerCase()) {
    case 'ok': return '#3a3';
    case 'warn': return '#e9c244';
    case 'error': return '#d33';
    case 'disabled': return '#888';
    case 'empty': return '#aaa';
    case 'unknown': return '#aaa';
    default: return '#666';
  }
}

interface SectionCardProps {
  title: string;
  subtitle?: string;
  section: Record<string, unknown> | undefined;
  metrics: string[];
}

function formatMetricValue(value: unknown): string {
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  if (typeof value === 'object' && value !== null) return JSON.stringify(value);
  return String(value);
}

function metricLabel(key: string): string {
  const labels: Record<string, string> = {
    backend: 'backend',
    connected: 'connected',
    alembic_current: 'alembic',
    data_api_locked_down: 'data api',
    default_admin_risk: 'admin risk',
    project_ref_configured: 'project ref',
    url_matches_project_ref: 'url match',
    storage_configured: 'storage cfg',
    storage_buckets_present: 'buckets',
    realtime_enabled: 'realtime',
    write_mode: 'write',
    read_mode: 'read',
    primary: 'primary',
    postgres_ready: 'postgres',
    chroma_ready: 'chroma',
    chroma_collections: 'collections',
    files: 'files',
    collections: 'collections',
    free_gb: 'free GB',
    used_gb: 'used GB',
    total_gb: 'total GB',
    supabase_status: 'supabase',
  };
  return labels[key] || key;
}

function SectionCard({ title, subtitle, section, metrics }: SectionCardProps) {
  const status = (section?.status as string) || 'unknown';
  return (
    <div className="lg-card" style={{ padding: 14, minHeight: 120 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <div>
          <strong style={{ fontSize: 13 }}>{title}</strong>
          {subtitle && <div style={{ fontSize: 10, opacity: 0.58, marginTop: 2 }}>{subtitle}</div>}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span
            style={{
              display: 'inline-block',
              width: 10,
              height: 10,
              borderRadius: '50%',
              background: ledColor(status),
            }}
          />
          <span style={{ fontSize: 11, opacity: 0.7 }}>{status}</span>
        </div>
      </div>
      <div style={{ fontSize: 12 }}>
        {metrics.map((k) => {
          if (!section || section[k] === undefined) return null;
          const v = section[k];
          const render = formatMetricValue(v);
          return (
            <div key={k} style={{ display: 'grid', gridTemplateColumns: 'minmax(82px, 0.9fr) minmax(0, 1.4fr)', gap: 10, padding: '2px 0' }}>
              <span style={{ opacity: 0.7 }}>{metricLabel(k)}</span>
              <span style={{ fontFamily: 'monospace', overflowWrap: 'anywhere', textAlign: 'right' }}>{render}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function SystemHealth() {
  const [data, setData] = useState<SystemHealthExtended | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      try {
        const r = await fetchSystemHealthExtended();
        if (!cancelled) {
          setData(r);
          setError(null);
        }
      } catch (e) {
        if (!cancelled) {
          setError((e as Error)?.message || '시스템 헬스 로드 실패');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    tick();
    const id = window.setInterval(tick, POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  if (loading && !data) {
    return <div className="lg-card" style={{ padding: 16, fontSize: 12 }}>로딩 중…</div>;
  }

  if (error && !data) {
    return (
      <div className="lg-card" style={{ padding: 16 }}>
        <div className="lg-state-pill crit">{error}</div>
      </div>
    );
  }

  const s = data?.sections ?? {};

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
        <strong>시스템 헬스</strong>
        <span style={{ fontSize: 11, opacity: 0.6 }}>
          마지막 갱신: {data?.timestamp?.slice(0, 19) || '—'} · 30s polling
        </span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 12 }}>
        <SectionCard
          title="PostgreSQL"
          subtitle="운영 application DB"
          section={s.postgresql as Record<string, unknown> | undefined}
          metrics={['backend', 'connected', 'alembic_current', 'data_api_locked_down', 'default_admin_risk']}
        />
        <SectionCard
          title="Supabase"
          subtitle="DB · Storage · Realtime"
          section={s.supabase as Record<string, unknown> | undefined}
          metrics={['project_ref_configured', 'url_matches_project_ref', 'storage_configured', 'storage_buckets_present', 'realtime_enabled']}
        />
        <SectionCard
          title="Vector Store"
          subtitle="Chroma / Supabase pgvector routing"
          section={s.vector_store as Record<string, unknown> | undefined}
          metrics={['write_mode', 'read_mode', 'primary', 'postgres_ready', 'chroma_ready', 'chroma_collections']}
        />
        <SectionCard
          title="Celery Beat"
          subtitle="scheduler heartbeat"
          section={s.celery_beat as Record<string, unknown> | undefined}
          metrics={['last_heartbeat', 'schedule_lag_seconds']}
        />
        <SectionCard
          title="Redis"
          subtitle="cache / stream"
          section={s.redis as Record<string, unknown> | undefined}
          metrics={['ping_ms', 'used_memory_mb', 'connected_clients']}
        />
        <SectionCard
          title="SQLite Mirror"
          subtitle="legacy/local mirror files"
          section={s.sqlite as Record<string, unknown> | undefined}
          metrics={['files']}
        />
        <SectionCard
          title="ChromaDB"
          subtitle="legacy/local vector index"
          section={s.chromadb as Record<string, unknown> | undefined}
          metrics={['collections']}
        />
        <SectionCard
          title="Disk"
          subtitle="container writable layer"
          section={s.disk as Record<string, unknown> | undefined}
          metrics={['free_gb', 'used_gb', 'total_gb']}
        />
        <SectionCard
          title="External"
          subtitle="third-party flags"
          section={s.external as Record<string, unknown> | undefined}
          metrics={[
            'slack_signing',
            'firebase_admin',
            'firebase_write_enabled',
            'firebase_read_fallback_enabled',
            'gemini_api_key_set',
            'firestore_audit_enabled',
            'supabase_status',
          ]}
        />
      </div>
    </div>
  );
}

export default SystemHealth;
