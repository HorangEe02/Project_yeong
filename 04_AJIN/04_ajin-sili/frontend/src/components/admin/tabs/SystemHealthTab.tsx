// SystemHealthTab — 시스템 헬스 (6 카드 LED + DB 백업 / Audit Log / 기본 Health).
// PR-E4 (6→3 탭 통합) — 기존 SystemToolsTab 에서 rename + 6 카드 LED 보강.
// SYS_ADMIN(L5) 전용.

import { useEffect, useState } from 'react';
import {
  downloadSystemBackup,
  fetchAuditLog,
  fetchSystemHealth,
  type AuditLogResponse,
  type SystemHealthResponse,
} from '@api/admin';
import {
  fetchSystemHealthExtended,
  type SystemHealthExtended,
  type SystemHealthSection,
} from '@api/management';
import { fetchIdPCapabilities } from '@api/auth';
import { useAuthStore } from '@store/auth';

// ─────────────────────────────────────────────────────────────
// 6 카드 LED — Beat / Queue / Cache / Storage / External / IdP.
// 데이터: 트랙 B fetchSystemHealthExtended (재사용) + fetchIdPCapabilities.
// ─────────────────────────────────────────────────────────────
function ledColor(status: string | undefined): string {
  switch ((status || '').toLowerCase()) {
    case 'ok': return '#3a3';
    case 'warn': return '#e9c244';
    case 'error': return '#d33';
    case 'disabled': return '#888';
    case 'empty':
    case 'unknown':
      return '#aaa';
    default: return '#666';
  }
}

interface LedCardProps {
  title: string;
  status: string;
  metrics: { k: string; v: string }[];
}

function LedCard({ title, status, metrics }: LedCardProps) {
  return (
    <div className="lg-card" style={{ padding: 14, minHeight: 130 }}>
      <div style={{
        display: 'flex', justifyContent: 'space-between',
        alignItems: 'center', marginBottom: 8,
      }}>
        <strong style={{ fontSize: 13 }}>{title}</strong>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{
            display: 'inline-block', width: 10, height: 10,
            borderRadius: '50%', background: ledColor(status),
          }} />
          <span style={{ fontSize: 11, opacity: 0.7 }}>{status || '—'}</span>
        </div>
      </div>
      <div style={{ fontSize: 12 }}>
        {metrics.map(({ k, v }) => (
          <div key={k} style={{
            display: 'flex', justifyContent: 'space-between',
            padding: '2px 0',
          }}>
            <span style={{ opacity: 0.7 }}>{k}</span>
            <span style={{ fontFamily: 'monospace' }}>{v}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function pickString(section: SystemHealthSection | undefined, key: string): string {
  const v = section?.[key];
  if (v === undefined || v === null) return '—';
  if (typeof v === 'object') return JSON.stringify(v);
  return String(v);
}

export function SystemHealthTab() {
  const myLevel = useAuthStore((s) => s.user?.role_level ?? 1);
  const [health, setHealth] = useState<SystemHealthResponse | null>(null);
  const [extended, setExtended] = useState<SystemHealthExtended | null>(null);
  const [idp, setIdp] = useState<{ providers: string[] } | null>(null);
  const [audit, setAudit] = useState<AuditLogResponse | null>(null);
  const [filterEndpoint, setFilterEndpoint] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (myLevel < 5) return;
    fetchSystemHealth().then(setHealth).catch((e) => setError((e as Error).message));
    fetchSystemHealthExtended()
      .then(setExtended)
      .catch((e) => setError((e as Error).message));
    fetchIdPCapabilities().then(setIdp).catch(() => setIdp({ providers: [] }));
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
        <p style={{ marginTop: 12 }}>시스템 헬스는 SYS_ADMIN(L5) 전용입니다.</p>
      </div>
    );
  }

  const s = extended?.sections ?? {};
  const idpActive = (idp?.providers?.length ?? 0) > 0;
  const idpStatus = idp === null ? 'unknown' : idpActive ? 'ok' : 'disabled';
  const idpProvider = idpActive ? idp!.providers.join(' · ').toUpperCase() : 'DISABLED';

  return (
    <>
      {error && (
        <div className="lg-card">
          <div className="lg-state-pill crit">{error}</div>
        </div>
      )}

      {/* 6 카드 LED — Beat · Queue · Cache · Storage · External · IdP */}
      <div className="lg-card">
        <div className="lg-card-h">
          <div>
            <div className="lg-pill">SYSTEM HEALTH · 6 SUBSYSTEMS</div>
            <div style={{ marginTop: 6, fontSize: 13, color: 'var(--hud-text-dim)' }}>
              {extended?.timestamp
                ? `마지막 갱신: ${extended.timestamp.slice(0, 19)}`
                : '로딩 중…'}
            </div>
          </div>
        </div>
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
          gap: 12,
        }}>
          <LedCard
            title="Beat (Celery)"
            status={pickString(s.celery_beat, 'status')}
            metrics={[
              { k: 'last_heartbeat', v: pickString(s.celery_beat, 'last_heartbeat') },
              { k: 'schedule_lag_s', v: pickString(s.celery_beat, 'schedule_lag_seconds') },
              { k: 'scheduled_24h', v: pickString(s.celery_beat, 'scheduled_tasks_24h') },
            ]}
          />
          <LedCard
            title="Queue (Redis)"
            status={pickString(s.redis, 'status')}
            metrics={[
              { k: 'ping_ms', v: pickString(s.redis, 'ping_ms') },
              { k: 'connected_clients', v: pickString(s.redis, 'connected_clients') },
              { k: 'used_memory_mb', v: pickString(s.redis, 'used_memory_mb') },
            ]}
          />
          <LedCard
            title="Cache (user_cache)"
            status={pickString(s.sqlite, 'status')}
            metrics={[
              { k: 'hit_rate', v: pickString(s.sqlite, 'user_cache_hit_rate') },
              { k: 'last_reconcile', v: pickString(s.sqlite, 'user_cache_last_reconcile') },
              { k: 'files', v: pickString(s.sqlite, 'files') },
            ]}
          />
          <LedCard
            title="Storage (data/)"
            status={pickString(s.disk, 'status')}
            metrics={[
              { k: 'used_gb', v: pickString(s.disk, 'used_gb') },
              { k: 'free_gb', v: pickString(s.disk, 'free_gb') },
              { k: 'total_gb', v: pickString(s.disk, 'total_gb') },
            ]}
          />
          <LedCard
            title="External (APIs)"
            status={pickString(s.external, 'status')}
            metrics={[
              { k: 'gemini_api_key', v: pickString(s.external, 'gemini_api_key_set') },
              { k: 'slack_signing', v: pickString(s.external, 'slack_signing') },
              { k: 'firebase_admin', v: pickString(s.external, 'firebase_admin') },
              { k: 'firebase_write', v: pickString(s.external, 'firebase_write_enabled') },
              {
                k: 'firebase_read_fallback',
                v: pickString(s.external, 'firebase_read_fallback_enabled'),
              },
            ]}
          />
          <LedCard
            title="IdP (Identity Provider)"
            status={idpStatus}
            metrics={[
              { k: 'provider', v: idpProvider },
              { k: 'providers_count', v: String(idp?.providers?.length ?? 0) },
              { k: 'idp_managed', v: idpActive ? 'true' : 'false' },
            ]}
          />
        </div>
      </div>

      {/* 기존 4 metric — auth/employees/audit db + 시드 사용자 */}
      <div className="lg-card">
        <div className="lg-card-h">
          <div>
            <div className="lg-pill">CORE DB STATUS</div>
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

export default SystemHealthTab;
