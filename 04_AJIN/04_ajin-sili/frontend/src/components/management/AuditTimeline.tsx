// AuditTimeline.tsx — v4.8 F-Audit.
// 좌측 필터 + 우측 vertical timeline. CSV 다운로드 버튼.
// 무한 스크롤 — IntersectionObserver. 페이지 50개 단위.

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  fetchAuditTimeline,
  type AuditTimelineRow,
  type AuditTimelineFilters,
} from '@api/management';

const PERIOD_OPTIONS = [
  { value: 7, label: '7일' },
  { value: 30, label: '30일' },
  { value: 90, label: '90일' },
];

function statusColor(code: number): string {
  if (code >= 500) return '#d33';
  if (code >= 400) return '#e88';
  if (code >= 300) return '#cc8';
  return '#5b8';
}

function downloadCsv(rows: AuditTimelineRow[]) {
  const header = ['timestamp', 'employee_id', 'name', 'department', 'role', 'endpoint', 'method', 'status_code', 'detail', 'ip_address'];
  const lines = [header.join(',')];
  for (const r of rows) {
    const cells = header.map((k) => {
      const v = (r as unknown as Record<string, unknown>)[k];
      const s = v == null ? '' : String(v);
      return `"${s.replace(/"/g, '""')}"`;
    });
    lines.push(cells.join(','));
  }
  const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `audit_timeline_${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

export function AuditTimeline() {
  const [filters, setFilters] = useState<AuditTimelineFilters>({
    actor: '',
    action: '',
    target: '',
    result: 'all',
    period_days: 30,
    page: 1,
    page_size: 50,
  });

  const [rows, setRows] = useState<AuditTimelineRow[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const sentinelRef = useRef<HTMLDivElement | null>(null);

  const load = useCallback(
    async (p: number, replace: boolean) => {
      setLoading(true);
      setError(null);
      try {
        const r = await fetchAuditTimeline({ ...filters, page: p, page_size: 50 });
        setTotal(r.total);
        setRows((prev) => (replace ? r.rows : [...prev, ...r.rows]));
      } catch (e) {
        setError((e as Error)?.message || '타임라인 로드 실패');
      } finally {
        setLoading(false);
      }
    },
    [filters],
  );

  // 필터 변경 시 페이지 리셋 + 1페이지 재로드.
  useEffect(() => {
    setPage(1);
    load(1, true);
  }, [filters.actor, filters.action, filters.target, filters.result, filters.period_days, load]);

  // 무한 스크롤
  useEffect(() => {
    const el = sentinelRef.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting && !loading && rows.length < total) {
            const next = page + 1;
            setPage(next);
            load(next, false);
          }
        }
      },
      { rootMargin: '200px' },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [page, loading, total, rows.length, load]);

  const totalKnown = useMemo(() => Math.min(rows.length, total), [rows.length, total]);

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: 16 }}>
      <div className="lg-card" style={{ padding: 12, height: 'fit-content' }}>
        <strong style={{ fontSize: 13 }}>필터</strong>
        <div style={{ marginTop: 10 }}>
          <label style={lbl}>실행자 (사번/이름)</label>
          <input
            value={filters.actor ?? ''}
            onChange={(e) => setFilters((f) => ({ ...f, actor: e.target.value }))}
            style={inp}
            placeholder="예: HR-0001"
          />
        </div>
        <div style={{ marginTop: 8 }}>
          <label style={lbl}>액션 (endpoint/method)</label>
          <input
            value={filters.action ?? ''}
            onChange={(e) => setFilters((f) => ({ ...f, action: e.target.value }))}
            style={inp}
            placeholder="예: /admin/users"
          />
        </div>
        <div style={{ marginTop: 8 }}>
          <label style={lbl}>대상 (detail 부분일치)</label>
          <input
            value={filters.target ?? ''}
            onChange={(e) => setFilters((f) => ({ ...f, target: e.target.value }))}
            style={inp}
          />
        </div>
        <div style={{ marginTop: 8 }}>
          <label style={lbl}>결과</label>
          <select
            value={filters.result ?? 'all'}
            onChange={(e) => setFilters((f) => ({ ...f, result: e.target.value as 'all' | 'success' | 'fail' }))}
            style={inp}
          >
            <option value="all">전체</option>
            <option value="success">성공 (2xx)</option>
            <option value="fail">실패 (4xx/5xx)</option>
          </select>
        </div>
        <div style={{ marginTop: 8 }}>
          <label style={lbl}>기간</label>
          <select
            value={filters.period_days ?? 30}
            onChange={(e) => setFilters((f) => ({ ...f, period_days: parseInt(e.target.value, 10) }))}
            style={inp}
          >
            {PERIOD_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>
        <button
          type="button"
          className="lg-btn"
          style={{ marginTop: 12, width: '100%' }}
          onClick={() => downloadCsv(rows)}
          disabled={rows.length === 0}
        >
          CSV 다운로드 ({rows.length})
        </button>
      </div>

      <div>
        <div className="lg-card-h" style={{ marginBottom: 10 }}>
          <div>
            <strong>타임라인</strong>
            <span style={{ fontSize: 11, opacity: 0.6, marginLeft: 8 }}>
              {totalKnown} / {total}
            </span>
          </div>
        </div>

        {error && (
          <div className="lg-state-pill crit" style={{ marginBottom: 8 }}>{error}</div>
        )}

        <div className="lg-card" style={{ padding: 0 }}>
          {rows.length === 0 && !loading ? (
            <div style={{ padding: 16, fontSize: 12, opacity: 0.7 }}>일치하는 감사 로그가 없습니다.</div>
          ) : (
            <div>
              {rows.map((r) => (
                <div
                  key={`${r.id}-${r.timestamp}`}
                  style={{
                    display: 'flex',
                    gap: 10,
                    padding: '10px 12px',
                    borderBottom: '1px solid var(--lg-border-soft, rgba(0,0,0,0.05))',
                  }}
                >
                  <div style={{ width: 130, fontSize: 11, opacity: 0.8 }}>
                    {(r.timestamp || '').slice(0, 19).replace('T', ' ')}
                  </div>
                  <div style={{ width: 110, fontSize: 11 }}>
                    <div>{r.employee_id || '—'}</div>
                    {r.name && <div style={{ opacity: 0.6 }}>{r.name}</div>}
                  </div>
                  <div style={{ width: 60 }}>
                    <span
                      style={{
                        display: 'inline-block',
                        padding: '2px 6px',
                        fontSize: 10,
                        borderRadius: 3,
                        background: statusColor(r.status_code),
                        color: '#fff',
                        fontWeight: 600,
                      }}
                    >
                      {r.method}
                    </span>
                    <span style={{ fontSize: 10, opacity: 0.7, marginLeft: 4 }}>{r.status_code}</span>
                  </div>
                  <div style={{ flex: 1, fontSize: 12 }}>
                    <div style={{ fontFamily: 'monospace' }}>{r.endpoint}</div>
                    {r.detail && (
                      <div style={{ fontSize: 11, opacity: 0.7, marginTop: 2 }}>{r.detail}</div>
                    )}
                  </div>
                  {r.ip_address && (
                    <div style={{ width: 100, fontSize: 10, opacity: 0.6, fontFamily: 'monospace' }}>{r.ip_address}</div>
                  )}
                </div>
              ))}
              <div ref={sentinelRef} style={{ height: 16 }} />
              {loading && (
                <div style={{ padding: 12, fontSize: 12, textAlign: 'center', opacity: 0.6 }}>로딩 중…</div>
              )}
              {!loading && rows.length >= total && rows.length > 0 && (
                <div style={{ padding: 12, fontSize: 11, textAlign: 'center', opacity: 0.5 }}>
                  · 끝 ·
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

const lbl: React.CSSProperties = {
  display: 'block',
  fontSize: 11,
  opacity: 0.7,
  marginBottom: 3,
};

const inp: React.CSSProperties = {
  width: '100%',
  padding: '6px 8px',
  fontSize: 12,
  border: '1px solid var(--lg-border, rgba(0,0,0,0.1))',
  borderRadius: 4,
  background: 'var(--lg-input-bg, rgba(0,0,0,0.02))',
};

export default AuditTimeline;
