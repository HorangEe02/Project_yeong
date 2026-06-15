// ApprovalQueueTable — PR-E8 권한 변경 결재 대기열.
// status='pending' (보안 승인 대기) + status='security_approved' (임원 승인 대기) 두 큐 토글.

import { useCallback, useEffect, useState } from 'react';
import {
  approvePermissionExecutive,
  approvePermissionSecurity,
  fetchPermissionQueue,
  rejectPermissionRequest,
  type PermissionChangeRequestRow,
} from '@api/admin';
import { useAuthStore } from '@store/auth';
import { useToast } from '@store/toast';

// 임원 직급 — backend admin.py _EXECUTIVE_POSITIONS 미러
const EXECUTIVE_POSITIONS = new Set(['이사', '상무', '전무', '부사장', '사장']);

type QueueStatus = 'pending' | 'security_approved';

function statusPill(status: string) {
  const klass =
    status === 'pending' ? 'warn'
      : status === 'security_approved' ? 'ok'
      : status === 'rejected' ? 'crit'
      : '';
  return <span className={`lg-state-pill ${klass}`}>{status}</span>;
}

export function ApprovalQueueTable() {
  const user = useAuthStore((s) => s.user);
  const myLevel = user?.role_level ?? 1;
  const myPosition = user?.position ?? '';
  const isExecutive = myLevel >= 5 && EXECUTIVE_POSITIONS.has(myPosition);
  const isSecurityApprover = myLevel >= 5;
  const { addToast } = useToast();

  const [queueStatus, setQueueStatus] = useState<QueueStatus>('pending');
  const [items, setItems] = useState<PermissionChangeRequestRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  const reload = useCallback(() => {
    setLoading(true);
    setError(null);
    fetchPermissionQueue(queueStatus)
      .then((r) => setItems(r.items))
      .catch((e) => setError(`대기열 로드 실패: ${(e as Error).message}`))
      .finally(() => setLoading(false));
  }, [queueStatus]);

  useEffect(() => { reload(); }, [reload]);

  const handleApprove = useCallback(async (row: PermissionChangeRequestRow) => {
    setBusyId(row.request_id);
    try {
      if (row.status === 'pending') {
        await approvePermissionSecurity(row.request_id);
        addToast({ type: 'success', message: `보안 승인 완료. id=${row.request_id}` });
      } else {
        await approvePermissionExecutive(row.request_id);
        addToast({ type: 'success', message: `임원 승인 완료 (적용). id=${row.request_id}` });
      }
      reload();
    } catch (e) {
      addToast({ type: 'error', message: `승인 실패: ${(e as Error).message}` });
    } finally {
      setBusyId(null);
    }
  }, [reload, addToast]);

  const handleReject = useCallback(async (row: PermissionChangeRequestRow) => {
    const reason = window.prompt(`반려 사유 (필수)\nrequest_id=${row.request_id}`);
    if (!reason || !reason.trim()) return;
    setBusyId(row.request_id);
    try {
      await rejectPermissionRequest(row.request_id, reason.trim());
      addToast({ type: 'success', message: `반려 처리 완료. id=${row.request_id}` });
      reload();
    } catch (e) {
      addToast({ type: 'error', message: `반려 실패: ${(e as Error).message}` });
    } finally {
      setBusyId(null);
    }
  }, [reload, addToast]);

  return (
    <div className="lg-card">
      <div className="lg-card-h">
        <div>
          <div className="lg-pill">APPROVAL QUEUE</div>
          <div style={{ marginTop: 6, fontSize: 13, color: 'var(--hud-text-dim)' }}>
            {loading ? '로딩 중…' : `${items.length}건 대기`} ·
            보안승인자: {isSecurityApprover ? '✓' : '—'} ·
            임원승인자: {isExecutive ? '✓' : '—'}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          <button
            type="button"
            className={`lg-btn ${queueStatus === 'pending' ? 'primary' : 'ghost'} sm`}
            onClick={() => setQueueStatus('pending')}
          >
            보안 승인 대기
          </button>
          <button
            type="button"
            className={`lg-btn ${queueStatus === 'security_approved' ? 'primary' : 'ghost'} sm`}
            onClick={() => setQueueStatus('security_approved')}
          >
            임원 승인 대기
          </button>
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

      <div className="lg-table-wrap">
        <table className="lg-table">
          <thead>
            <tr>
              <th>req_id</th>
              <th>permission_key</th>
              <th>요청자</th>
              <th>요청시각</th>
              <th>상태</th>
              <th>사유</th>
              <th style={{ textAlign: 'right' }}>액션</th>
            </tr>
          </thead>
          <tbody>
            {items.map((row) => {
              const canSecurity = row.status === 'pending' && isSecurityApprover;
              const canExecutive = row.status === 'security_approved' && isExecutive;
              const canReject = isSecurityApprover &&
                (row.status === 'pending' || row.status === 'security_approved');
              return (
                <tr key={row.request_id}>
                  <td className="mono">{row.request_id}</td>
                  <td className="mono">{row.permission_key}</td>
                  <td>{row.requested_by}</td>
                  <td className="dim mono" style={{ fontSize: 11 }}>{row.requested_at}</td>
                  <td>{statusPill(row.status)}</td>
                  <td
                    style={{
                      maxWidth: 240, overflow: 'hidden', textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap', fontSize: 12,
                    }}
                    title={row.reason}
                  >
                    {row.reason}
                  </td>
                  <td style={{ textAlign: 'right' }}>
                    <div style={{ display: 'inline-flex', gap: 4 }}>
                      {canSecurity && (
                        <button
                          type="button"
                          className="lg-btn primary sm"
                          onClick={() => handleApprove(row)}
                          disabled={busyId === row.request_id}
                        >
                          보안 승인
                        </button>
                      )}
                      {canExecutive && (
                        <button
                          type="button"
                          className="lg-btn primary sm"
                          onClick={() => handleApprove(row)}
                          disabled={busyId === row.request_id}
                        >
                          임원 승인
                        </button>
                      )}
                      {canReject && (
                        <button
                          type="button"
                          className="lg-btn ghost sm"
                          onClick={() => handleReject(row)}
                          disabled={busyId === row.request_id}
                        >
                          반려
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
            {!loading && items.length === 0 && (
              <tr>
                <td
                  colSpan={7}
                  style={{ textAlign: 'center', color: 'var(--hud-text-dim)', padding: 24 }}
                >
                  대기 중인 요청 없음
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default ApprovalQueueTable;
