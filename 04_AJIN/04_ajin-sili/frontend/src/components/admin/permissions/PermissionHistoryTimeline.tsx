// PermissionHistoryTimeline — PR-E8 변경 이력 vertical timeline.
// applied + rejected 만 표시. 페이지네이션 = limit 슬라이더.

import { useCallback, useEffect, useState } from 'react';
import {
  fetchPermissionHistory,
  type PermissionChangeRequestRow,
} from '@api/admin';

function actionLabel(status: string): { ko: string; klass: string } {
  if (status === 'applied') return { ko: '적용됨', klass: 'ok' };
  if (status === 'rejected') return { ko: '반려됨', klass: 'crit' };
  return { ko: status, klass: '' };
}

function shortDiff(row: PermissionChangeRequestRow): string {
  const oldR = row.old_value?.min_role ?? '—';
  const newR = (row.new_value as { min_role?: string })?.min_role ?? '—';
  if (oldR !== newR) return `min_role: ${oldR} → ${newR}`;
  const oldD = row.old_value?.departments?.join(',') ?? '—';
  const newDArr = (row.new_value as { departments?: string[] | null })?.departments;
  const newD = Array.isArray(newDArr) ? newDArr.join(',') : '—';
  if (oldD !== newD) return `departments: ${oldD || '—'} → ${newD || '—'}`;
  return row.old_value ? '권한 정의 업데이트' : '권한 신규 생성';
}

export function PermissionHistoryTimeline() {
  const [items, setItems] = useState<PermissionChangeRequestRow[]>([]);
  const [limit, setLimit] = useState(50);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(() => {
    setLoading(true);
    setError(null);
    fetchPermissionHistory(limit)
      .then((r) => setItems(r.items))
      .catch((e) => setError(`이력 로드 실패: ${(e as Error).message}`))
      .finally(() => setLoading(false));
  }, [limit]);

  useEffect(() => { reload(); }, [reload]);

  return (
    <div className="lg-card">
      <div className="lg-card-h">
        <div>
          <div className="lg-pill">CHANGE HISTORY</div>
          <div style={{ marginTop: 6, fontSize: 13, color: 'var(--hud-text-dim)' }}>
            {loading ? '로딩 중…' : `최근 ${items.length}건`} · applied + rejected
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <label style={{ fontSize: 12, color: 'var(--hud-text-dim)' }}>
            표시 개수
          </label>
          <select
            className="lg-input"
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            style={{ width: 90 }}
          >
            {[25, 50, 100, 200, 500].map((n) => (
              <option key={n} value={n}>{n}</option>
            ))}
          </select>
          <button type="button" className="lg-btn ghost sm" onClick={reload} disabled={loading}>
            새로고침
          </button>
        </div>
      </div>

      {error && (
        <div className="lg-state-pill crit" style={{ display: 'inline-block', marginBottom: 10 }}>
          {error}
        </div>
      )}

      <div style={{ display: 'grid', gap: 8 }}>
        {items.map((row) => {
          const label = actionLabel(row.status);
          const ts = row.applied_at ?? row.requested_at;
          const actor = row.executive_approver ?? row.security_approver ?? row.requested_by;
          return (
            <div
              key={row.request_id}
              style={{
                display: 'grid',
                gridTemplateColumns: '180px 90px 1fr',
                gap: 12,
                padding: '10px 12px',
                borderLeft: `3px solid var(--hud-${row.status === 'applied' ? 'primary' : 'text-dim'})`,
                background: 'color-mix(in oklab, var(--hud-text) 4%, transparent)',
                borderRadius: 4,
                alignItems: 'baseline',
              }}
            >
              <div className="dim mono" style={{ fontSize: 11 }}>{ts}</div>
              <div><span className={`lg-state-pill ${label.klass}`}>{label.ko}</span></div>
              <div style={{ display: 'grid', gap: 2 }}>
                <div style={{ fontSize: 13 }}>
                  <span className="mono">{row.permission_key}</span>
                  {' · '}
                  <span style={{ color: 'var(--hud-text-dim)' }}>by</span>{' '}
                  <b>{actor}</b>
                </div>
                <div style={{ fontSize: 12, color: 'var(--hud-text-dim)' }}>
                  {shortDiff(row)}
                </div>
                {row.reason && (
                  <div style={{ fontSize: 11, color: 'var(--hud-text-dim)', fontStyle: 'italic' }}>
                    사유: {row.reason}
                  </div>
                )}
              </div>
            </div>
          );
        })}
        {!loading && items.length === 0 && (
          <div
            style={{ textAlign: 'center', color: 'var(--hud-text-dim)', padding: 24 }}
          >
            변경 이력 없음
          </div>
        )}
      </div>
    </div>
  );
}

export default PermissionHistoryTimeline;
