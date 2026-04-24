import { useCallback, useEffect, useState } from 'react';
import { CheckCircle2, XCircle, RefreshCw, UserCheck } from 'lucide-react';
import { AdminLayout } from '@/pages/admin/AdminLayout';
import { DataTable, type Column } from '@/components/admin/DataTable';
import { ConfirmDialog } from '@/components/admin/ConfirmDialog';
import {
  approveRoleRequest,
  listPendingRequests,
  rejectRoleRequest,
} from '@/services/roleRequest';
import { formatRelativeTime } from '@/utils/format';
import type { AdminUserRow } from '@/types/admin';

export function AdminRequestsPage() {
  const [rows, setRows] = useState<AdminUserRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [acting, setActing] = useState<string | null>(null);
  const [rejectTarget, setRejectTarget] = useState<AdminUserRow | null>(null);
  const [rejectReason, setRejectReason] = useState('');
  const [msg, setMsg] = useState<{ tone: 'ok' | 'err'; text: string } | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      setRows(await listPendingRequests());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const onApprove = async (uid: string) => {
    setMsg(null);
    setActing(uid);
    try {
      await approveRoleRequest(uid);
      setMsg({ tone: 'ok', text: '승인되었습니다' });
      await refresh();
    } catch (err) {
      setMsg({ tone: 'err', text: err instanceof Error ? err.message : String(err) });
    } finally {
      setActing(null);
    }
  };

  const onRejectConfirm = async () => {
    if (!rejectTarget) return;
    setActing(rejectTarget.uid);
    try {
      await rejectRoleRequest(rejectTarget.uid, rejectReason);
      setMsg({ tone: 'ok', text: '거절되었습니다' });
      await refresh();
    } catch (err) {
      setMsg({ tone: 'err', text: err instanceof Error ? err.message : String(err) });
    } finally {
      setActing(null);
      setRejectReason('');
    }
  };

  const columns: Column<AdminUserRow>[] = [
    {
      key: 'name',
      header: '신청자',
      cell: (r) => (
        <div>
          <p className="text-sm font-medium text-on-surface">
            {r.displayName ?? '(이름 없음)'}
          </p>
          <p className="text-[11px] text-on-surface-variant">{r.email}</p>
        </div>
      ),
    },
    {
      key: 'dept',
      header: '신청 소속/부서',
      cell: (r) => (
        <div>
          <p className="text-sm">{r.pendingRoleRequest?.department ?? '-'}</p>
          <p className="text-[11px] text-on-surface-variant">
            {r.pendingRoleRequest?.hospitalId ?? '-'}
          </p>
        </div>
      ),
    },
    {
      key: 'reason',
      header: '사유',
      cell: (r) => (
        <span className="text-xs text-on-surface-variant">
          {r.pendingRoleRequest?.reason ?? '-'}
        </span>
      ),
    },
    {
      key: 'when',
      header: '신청',
      cell: (r) =>
        r.pendingRoleRequest ? (
          <span className="whitespace-nowrap text-xs text-on-surface-variant">
            {formatRelativeTime(r.pendingRoleRequest.requestedAt)}
          </span>
        ) : null,
      width: '100px',
    },
    {
      key: 'actions',
      header: '',
      cell: (r) => (
        <div className="flex gap-1">
          <button
            type="button"
            disabled={acting === r.uid}
            onClick={() => onApprove(r.uid)}
            className="flex items-center gap-1 rounded-md border border-green-500 bg-green-50 px-2 py-1 text-[11px] text-green-700 disabled:opacity-50"
          >
            <CheckCircle2 className="h-3 w-3" />
            승인
          </button>
          <button
            type="button"
            disabled={acting === r.uid}
            onClick={() => {
              setRejectTarget(r);
              setRejectReason('');
            }}
            className="flex items-center gap-1 rounded-md border border-red-300 bg-red-50 px-2 py-1 text-[11px] text-red-600 disabled:opacity-50"
          >
            <XCircle className="h-3 w-3" />
            거절
          </button>
        </div>
      ),
      width: '170px',
    },
  ];

  return (
    <AdminLayout
      title="역할 전환 신청"
      description="환자가 의료진으로 전환을 요청한 내역을 검토합니다"
      actions={
        <button
          type="button"
          onClick={refresh}
          className="flex items-center gap-1 rounded-lg border border-surface-container-high bg-surface px-3 py-1.5 text-xs"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          새로고침
        </button>
      }
    >
      <div className="mb-3 flex items-center gap-2 text-xs text-on-surface-variant">
        <UserCheck className="h-3.5 w-3.5" />
        승인 대기 · {loading ? '...' : `${rows.length}건`}
      </div>

      {msg && (
        <p
          className={`mb-3 rounded-lg px-3 py-2 text-xs ${
            msg.tone === 'ok' ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-600'
          }`}
        >
          {msg.text}
        </p>
      )}

      <DataTable
        columns={columns}
        rows={rows}
        rowKey={(r) => r.uid}
        loading={loading}
        emptyLabel="대기 중인 신청이 없습니다"
      />

      <ConfirmDialog
        open={!!rejectTarget}
        title={`${rejectTarget?.displayName ?? '이 신청'}을 거절하시겠습니까?`}
        description="거절 사유는 신청자의 프로필에서 확인할 수 있습니다."
        confirmLabel="거절"
        danger
        onClose={() => setRejectTarget(null)}
        onConfirm={onRejectConfirm}
      >
        <div className="mt-3 flex flex-col gap-1">
          <label className="text-xs text-on-surface-variant">거절 사유 (선택)</label>
          <textarea
            value={rejectReason}
            onChange={(e) => setRejectReason(e.target.value)}
            rows={3}
            maxLength={200}
            className="rounded-lg border border-surface-container-high bg-surface px-3 py-2 text-sm outline-none focus:border-primary"
          />
        </div>
      </ConfirmDialog>
    </AdminLayout>
  );
}
