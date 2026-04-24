import { useCallback, useEffect, useMemo, useState } from 'react';
import { Copy, Trash2, RefreshCw, Mail, FileUp } from 'lucide-react';
import { AdminLayout } from '@/pages/admin/AdminLayout';
import { DataTable, type Column } from '@/components/admin/DataTable';
import { ConfirmDialog } from '@/components/admin/ConfirmDialog';
import { BulkInviteDialog } from '@/components/admin/BulkInviteDialog';
import {
  buildInviteUrl,
  deleteStaffInvitation,
  listStaffInvitations,
  revokeStaffInvitation,
} from '@/services/staffInvitation';
import { formatDate } from '@/utils/format';
import type { StaffInvitation, StaffInvitationStatus } from '@/types/staff-invitation';

const FILTERS: { value: StaffInvitationStatus | 'all'; label: string }[] = [
  { value: 'all', label: '전체' },
  { value: 'pending', label: '대기' },
  { value: 'accepted', label: '수락됨' },
  { value: 'revoked', label: '폐기됨' },
  { value: 'expired', label: '만료' },
];

export function AdminInvitationsPage() {
  const [rows, setRows] = useState<StaffInvitation[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<StaffInvitationStatus | 'all'>('all');
  const [revokeTarget, setRevokeTarget] = useState<StaffInvitation | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<StaffInvitation | null>(null);
  const [copiedToken, setCopiedToken] = useState<string | null>(null);
  const [bulkOpen, setBulkOpen] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      setRows(await listStaffInvitations());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const now = Date.now();
  const effective = useMemo(
    () =>
      rows.map((r) => ({
        ...r,
        effectiveStatus:
          r.status === 'pending' && r.expiresAt < now ? 'expired' : r.status,
      })),
    [rows, now],
  );

  const filtered = effective.filter((r) =>
    filter === 'all' ? true : r.effectiveStatus === filter,
  );

  const copy = async (token: string) => {
    try {
      await navigator.clipboard.writeText(buildInviteUrl(token));
      setCopiedToken(token);
      setTimeout(() => setCopiedToken(null), 1500);
    } catch {}
  };

  const onRevoke = async () => {
    if (!revokeTarget) return;
    await revokeStaffInvitation(revokeTarget.token);
    await refresh();
  };
  const onDelete = async () => {
    if (!deleteTarget) return;
    await deleteStaffInvitation(deleteTarget.token);
    await refresh();
  };

  const columns: Column<(typeof effective)[number]>[] = [
    {
      key: 'email',
      header: '이메일',
      cell: (r) => (
        <div>
          <p className="text-sm font-medium text-on-surface">{r.email}</p>
          {r.displayName && (
            <p className="text-[11px] text-on-surface-variant">{r.displayName}</p>
          )}
        </div>
      ),
    },
    {
      key: 'dept',
      header: '소속/부서',
      cell: (r) => (
        <div className="text-xs">
          <p>{r.department}</p>
          <p className="text-on-surface-variant">{r.hospitalId}</p>
        </div>
      ),
    },
    {
      key: 'status',
      header: '상태',
      cell: (r) => <StatusBadge status={r.effectiveStatus} />,
      width: '100px',
    },
    {
      key: 'expires',
      header: '만료일',
      cell: (r) => (
        <span className="text-xs text-on-surface-variant">{formatDate(r.expiresAt)}</span>
      ),
      width: '100px',
    },
    {
      key: 'claimed',
      header: '수락',
      cell: (r) =>
        r.claimedBy ? (
          <span className="font-mono text-[11px] text-on-surface-variant">
            {r.claimedBy.slice(0, 10)}…
          </span>
        ) : (
          <span className="text-[11px] text-on-surface-variant/60">-</span>
        ),
    },
    {
      key: 'actions',
      header: '',
      cell: (r) => (
        <div className="flex gap-1">
          {r.effectiveStatus === 'pending' && (
            <button
              type="button"
              onClick={() => copy(r.token)}
              className="flex items-center gap-1 rounded-md border border-primary px-2 py-1 text-[11px] text-primary"
            >
              <Copy className="h-3 w-3" />
              {copiedToken === r.token ? '복사됨' : 'URL'}
            </button>
          )}
          {r.effectiveStatus === 'pending' && (
            <button
              type="button"
              onClick={() => setRevokeTarget(r)}
              className="flex items-center gap-1 rounded-md border border-amber-300 bg-amber-50 px-2 py-1 text-[11px] text-amber-700"
            >
              폐기
            </button>
          )}
          <button
            type="button"
            onClick={() => setDeleteTarget(r)}
            className="flex items-center gap-1 rounded-md border border-red-300 bg-red-50 px-2 py-1 text-[11px] text-red-600"
          >
            <Trash2 className="h-3 w-3" />
            삭제
          </button>
        </div>
      ),
      width: '180px',
    },
  ];

  return (
    <AdminLayout
      title="의료진 초대"
      description="발급한 초대 링크의 상태를 확인하고 관리합니다"
      actions={
        <>
          <button
            type="button"
            onClick={() => setBulkOpen(true)}
            className="flex items-center gap-1 rounded-lg bg-primary px-3 py-1.5 text-xs font-medium text-on-primary"
          >
            <FileUp className="h-3.5 w-3.5" />
            CSV 일괄
          </button>
          <button
            type="button"
            onClick={refresh}
            className="flex items-center gap-1 rounded-lg border border-surface-container-high bg-surface px-3 py-1.5 text-xs"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            새로고침
          </button>
        </>
      }
    >
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Mail className="h-3.5 w-3.5 text-on-surface-variant" />
        <div className="flex overflow-hidden rounded-lg border border-surface-container-high">
          {FILTERS.map((f) => (
            <button
              key={f.value}
              type="button"
              onClick={() => setFilter(f.value)}
              className={`px-3 py-1.5 text-xs font-medium ${
                filter === f.value
                  ? 'bg-primary text-on-primary'
                  : 'bg-surface text-on-surface'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
        <span className="ml-auto text-xs text-on-surface-variant">
          {loading ? '...' : `${filtered.length}건`}
        </span>
      </div>

      <DataTable
        columns={columns}
        rows={filtered}
        rowKey={(r) => r.token}
        loading={loading}
        emptyLabel="초대 내역이 없습니다"
      />

      <ConfirmDialog
        open={!!revokeTarget}
        title="초대를 폐기할까요?"
        description="초대 링크를 더 이상 수락할 수 없게 됩니다. (기록은 남음)"
        confirmLabel="폐기"
        danger
        onClose={() => setRevokeTarget(null)}
        onConfirm={onRevoke}
      />

      <ConfirmDialog
        open={!!deleteTarget}
        title="초대 기록을 삭제할까요?"
        description="DB에서 완전히 제거됩니다. 이미 수락된 사용자 계정에는 영향이 없습니다."
        confirmLabel="삭제"
        danger
        onClose={() => setDeleteTarget(null)}
        onConfirm={onDelete}
      />

      <BulkInviteDialog
        open={bulkOpen}
        onClose={() => setBulkOpen(false)}
        onIssued={refresh}
      />
    </AdminLayout>
  );
}

function StatusBadge({ status }: { status: StaffInvitationStatus }) {
  const map: Record<StaffInvitationStatus, { label: string; cls: string }> = {
    pending: { label: '대기', cls: 'bg-amber-50 text-amber-700' },
    accepted: { label: '수락됨', cls: 'bg-green-50 text-green-700' },
    expired: { label: '만료', cls: 'bg-surface-container-high text-on-surface-variant' },
    revoked: { label: '폐기', cls: 'bg-red-50 text-red-600' },
  };
  const m = map[status];
  return (
    <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${m.cls}`}>
      {m.label}
    </span>
  );
}
