// PermissionViolationTable — K4=0 검증 UI + 권한 위반 표 (PR-E5).
// 입력: AuditDashboardResponse.permission_violations

import type { PermissionViolationRow } from '@api/admin';

interface Props {
  rows: PermissionViolationRow[];
  loading?: boolean;
  onViewAuditLog?: () => void;
}

export function PermissionViolationTable({ rows, loading, onViewAuditLog }: Props) {
  return (
    <div className="lg-card">
      <div className="lg-card-h">
        <div>
          <div className="lg-pill">PERMISSION VIOLATIONS · K4=0</div>
          <div style={{ marginTop: 6, fontSize: 12, color: 'var(--hud-text-dim)' }}>
            {loading
              ? '로딩 중…'
              : rows.length === 0
                ? '권한 위반 이벤트 없음'
                : `${rows.length}건 권한 위반 감지됨`}
          </div>
        </div>
        {onViewAuditLog && (
          <button
            type="button"
            className="lg-btn sm ghost"
            onClick={onViewAuditLog}
          >
            감사 로그 보기
          </button>
        )}
      </div>

      {/* K4=0 검증 배너 */}
      {!loading && rows.length === 0 && (
        <div
          style={{
            padding: '14px 16px',
            borderRadius: 6,
            background: 'rgba(0, 200, 120, 0.08)',
            border: '1px solid var(--hud-green)',
            display: 'flex',
            alignItems: 'center',
            gap: 10,
          }}
        >
          <span style={{ fontSize: 18 }}>✓</span>
          <div>
            <div style={{ fontWeight: 600, color: 'var(--hud-green)', fontSize: 14 }}>
              권한 위반 0건 — 양호
            </div>
            <div style={{ fontSize: 12, color: 'var(--hud-text-dim)', marginTop: 2 }}>
              조회 기간 내 인가되지 않은 엔드포인트 접근이 없습니다.
            </div>
          </div>
        </div>
      )}

      {!loading && rows.length > 0 && (
        <>
          <div
            style={{
              padding: '10px 14px',
              borderRadius: 6,
              background: 'rgba(220, 60, 60, 0.08)',
              border: '1px solid #d33',
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              marginBottom: 12,
            }}
          >
            <span style={{ fontSize: 18 }}>⚠</span>
            <div style={{ fontWeight: 600, color: '#d33', fontSize: 14 }}>
              {rows.length}건의 권한 위반이 감지되었습니다 — 즉시 검토 필요
            </div>
          </div>

          <div className="lg-table-wrap">
            <table className="lg-table">
              <thead>
                <tr>
                  <th>타임스탬프</th>
                  <th>사번</th>
                  <th>이름</th>
                  <th>부서</th>
                  <th>역할</th>
                  <th>엔드포인트</th>
                  <th>메서드</th>
                  <th>상태</th>
                  <th>상세</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={`${r.timestamp}-${r.employee_id}-${i}`}>
                    <td className="mono" style={{ whiteSpace: 'nowrap' }}>
                      {r.timestamp.slice(0, 19).replace('T', ' ')}
                    </td>
                    <td className="mono">{r.employee_id}</td>
                    <td>{r.name || '—'}</td>
                    <td>{r.department || <span className="dim">—</span>}</td>
                    <td>
                      <span
                        style={{
                          fontSize: 11,
                          padding: '2px 7px',
                          borderRadius: 4,
                          border: '1px solid var(--hud-line)',
                          fontFamily: 'var(--hud-font-mono)',
                        }}
                      >
                        {r.role || '—'}
                      </span>
                    </td>
                    <td className="mono" style={{ fontSize: 11, maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {r.endpoint}
                    </td>
                    <td>
                      <span
                        className="lg-state-pill"
                        style={{
                          background: r.method === 'DELETE' ? '#d33' : r.method === 'POST' || r.method === 'PUT' ? '#e9c244' : undefined,
                          color: r.method === 'DELETE' || r.method === 'POST' || r.method === 'PUT' ? '#fff' : undefined,
                        }}
                      >
                        {r.method}
                      </span>
                    </td>
                    <td>
                      <span className={`lg-state-pill ${r.status_code >= 500 ? 'crit' : 'warn'}`}>
                        {r.status_code}
                      </span>
                    </td>
                    <td style={{ fontSize: 11, color: 'var(--hud-text-dim)', maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {r.detail || '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
