// SystemToolsTab — 시스템 도구 (DB 백업 / Audit Log / Health).
// SYS_ADMIN(L5) 전용.

import { useEffect, useState } from 'react';
import {
  downloadSystemBackup,
  fetchAuditLog,
  fetchSystemHealth,
  type AuditLogResponse,
  type SystemHealthResponse,
} from '@api/admin';
import { useAuthStore } from '@store/auth';

export function SystemToolsTab() {
  const myLevel = useAuthStore((s) => s.user?.role_level ?? 1);
  const [health, setHealth] = useState<SystemHealthResponse | null>(null);
  const [audit, setAudit] = useState<AuditLogResponse | null>(null);
  const [filterEndpoint, setFilterEndpoint] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (myLevel < 5) return;
    fetchSystemHealth().then(setHealth).catch((e) => setError((e as Error).message));
  }, [myLevel]);

  useEffect(() => {
    if (myLevel < 5) return;
    fetchAuditLog({ endpoint: filterEndpoint || undefined, limit: 50 })
      .then(setAudit)
      .catch((e) => setError((e as Error).message));
  }, [myLevel, filterEndpoint]);

  const handleBackup = async () => {
    setBusy(true);
    setError(null);
    try {
      const blob = await downloadSystemBackup();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `auth_${new Date().toISOString().replace(/[:.]/g, '-')}.db`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(`백업 실패: ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  };

  if (myLevel < 5) {
    return (
      <div className="lg-card">
        <div className="lg-state-pill crit">권한 부족</div>
        <p style={{ marginTop: 12 }}>시스템 도구는 SYS_ADMIN(L5) 전용입니다.</p>
      </div>
    );
  }

  return (
    <>
      {error && (
        <div className="lg-card">
          <div className="lg-state-pill crit">{error}</div>
        </div>
      )}

      <div className="lg-card">
        <div className="lg-card-h">
          <div>
            <div className="lg-pill">SYSTEM HEALTH</div>
          </div>
        </div>
        <div className="lg-metric-row">
          <div className="lg-metric">
            <div className="k">AUTH DB</div>
            <div className="v" style={{ color: health?.auth_db_ok ? 'var(--hud-primary)' : '#C0392B' }}>
              {health?.auth_db_ok ? '● OK' : '○ 미존재'}
            </div>
            <div className="en">data/auth.db</div>
          </div>
          <div className="lg-metric">
            <div className="k">EMPLOYEES DB</div>
            <div className="v" style={{ color: health?.employees_db_ok ? 'var(--hud-primary)' : '#C0392B' }}>
              {health?.employees_db_ok ? '● OK' : '○ 미존재'}
            </div>
            <div className="en">data/employees.db</div>
          </div>
          <div className="lg-metric">
            <div className="k">AUDIT DB</div>
            <div className="v" style={{ color: health?.audit_db_ok ? 'var(--hud-primary)' : '#C0392B' }}>
              {health?.audit_db_ok ? '● OK' : '○ 미존재'}
            </div>
            <div className="en">data/audit.db</div>
          </div>
          <div className="lg-metric">
            <div className="k">시드 사용자</div>
            <div className="v">{health?.seed_users ?? '—'}</div>
            <div className="en">REGISTERED ACCOUNTS</div>
          </div>
        </div>
      </div>

      <div className="lg-card">
        <div className="lg-card-h">
          <div>
            <div className="lg-pill">DB BACKUP</div>
            <div style={{ marginTop: 6, fontSize: 13, color: 'var(--hud-text-dim)' }}>
              auth.db 의 SQLite hot-backup 을 생성하여 다운로드합니다.
            </div>
          </div>
          <button className="lg-btn" disabled={busy} onClick={handleBackup} type="button">
            {busy ? '백업 중…' : 'auth.db 백업 다운로드'}
          </button>
        </div>
      </div>

      <div className="lg-card">
        <div className="lg-card-h">
          <div>
            <div className="lg-pill">API AUDIT LOG</div>
            <div style={{ marginTop: 6, fontSize: 13, color: 'var(--hud-text-dim)' }}>
              {audit ? `${audit.total}건 표시` : '로딩 중…'}
            </div>
          </div>
          <div className="lg-field" style={{ minWidth: 220 }}>
            <label>엔드포인트 필터</label>
            <input
              type="search"
              value={filterEndpoint}
              onChange={(e) => setFilterEndpoint(e.target.value)}
              placeholder="/api/admin"
            />
          </div>
        </div>

        <div className="lg-table-wrap">
          <table className="lg-table">
            <thead>
              <tr>
                <th>타임스탬프</th>
                <th>사번</th>
                <th>이름</th>
                <th>역할</th>
                <th>엔드포인트</th>
                <th>METHOD</th>
                <th>상태</th>
                <th>상세</th>
              </tr>
            </thead>
            <tbody>
              {(audit?.rows ?? []).map((r, i) => (
                <tr key={`${r.timestamp}-${i}`}>
                  <td className="mono">{r.timestamp}</td>
                  <td className="mono">{r.employee_id || '—'}</td>
                  <td>{r.name || '—'}</td>
                  <td><span className="lg-role">{r.role || '—'}</span></td>
                  <td className="mono">{r.endpoint}</td>
                  <td className="mono">{r.method}</td>
                  <td className="mono">
                    {r.status_code < 400
                      ? <span className="lg-state-pill ok">{r.status_code}</span>
                      : <span className="lg-state-pill crit">{r.status_code}</span>}
                  </td>
                  <td className="dim" style={{ maxWidth: 320, whiteSpace: 'normal' }}>{r.detail}</td>
                </tr>
              ))}
              {(!audit || audit.rows.length === 0) && (
                <tr>
                  <td colSpan={8} style={{ textAlign: 'center', color: 'var(--hud-text-dim)', padding: 24 }}>
                    감사 로그가 없습니다.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
