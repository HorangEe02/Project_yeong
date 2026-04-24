import { useCallback, useEffect, useState } from 'react';
import { Plus, Download, Trash2 } from 'lucide-react';
import { AdminLayout } from '@/pages/admin/AdminLayout';
import { DataTable, type Column } from '@/components/admin/DataTable';
import { ConfirmDialog } from '@/components/admin/ConfirmDialog';
import { IconButton } from '@/components/admin/IconButton';
import { IssueCodeDialog } from '@/components/admin/IssueCodeDialog';
import { listStaffCodes, revokeStaffCode } from '@/services/adminStaffCodes';
import { downloadCsv, toCsv } from '@/utils/csv';
import { formatDate } from '@/utils/format';
import type { StaffCode } from '@/types/staff-code';

export function AdminStaffCodesPage() {
  const [rows, setRows] = useState<StaffCode[]>([]);
  const [loading, setLoading] = useState(true);
  const [issueOpen, setIssueOpen] = useState(false);
  const [revokeTarget, setRevokeTarget] = useState<StaffCode | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      setRows(await listStaffCodes());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const onExport = () => {
    const csv = toCsv(rows, [
      { key: 'code', label: 'code' },
      { key: 'hospitalId', label: 'hospital' },
      { key: 'department', label: 'department' },
      { key: 'usedBy', label: 'usedBy' },
      { key: 'expiresAt', label: 'expiresAt' },
      { key: 'createdAt', label: 'createdAt' },
    ]);
    downloadCsv(`staff-codes-${new Date().toISOString().slice(0, 10)}.csv`, csv);
  };

  const columns: Column<StaffCode>[] = [
    {
      key: 'code',
      header: '코드',
      cell: (r) => <span className="font-mono text-xs">{r.code}</span>,
    },
    {
      key: 'hospital',
      header: '병원',
      cell: (r) => <span className="text-xs text-on-surface-variant">{r.hospitalId}</span>,
    },
    {
      key: 'dept',
      header: '부서',
      cell: (r) => r.department,
    },
    {
      key: 'status',
      header: '상태',
      cell: (r) => <CodeStatusBadge code={r} />,
      width: '100px',
    },
    {
      key: 'expires',
      header: '만료일',
      cell: (r) => (
        <span className="text-xs text-on-surface-variant">{formatDate(r.expiresAt)}</span>
      ),
      width: '120px',
    },
    {
      key: 'actions',
      header: '',
      cell: (r) => (
        <IconButton
          label="회수"
          tone="danger"
          onClick={() => setRevokeTarget(r)}
        >
          <Trash2 className="h-3.5 w-3.5" />
        </IconButton>
      ),
      width: '64px',
    },
  ];

  return (
    <AdminLayout
      title="의료진 코드"
      description="발급된 코드를 관리하고 신규 코드를 발급합니다"
      actions={
        <>
          <button
            type="button"
            onClick={onExport}
            disabled={rows.length === 0}
            className="flex items-center gap-1 rounded-lg border border-surface-container-high bg-surface px-3 py-1.5 text-xs disabled:opacity-50"
          >
            <Download className="h-3.5 w-3.5" />
            CSV
          </button>
          <button
            type="button"
            onClick={() => setIssueOpen(true)}
            className="flex items-center gap-1 rounded-lg bg-primary px-3 py-1.5 text-xs font-medium text-on-primary"
          >
            <Plus className="h-3.5 w-3.5" />
            발급
          </button>
        </>
      }
    >
      <p className="mb-2 text-xs text-on-surface-variant">
        {loading ? '...' : `${rows.length}개`}
      </p>
      <DataTable
        columns={columns}
        rows={rows}
        rowKey={(r) => r.code}
        loading={loading}
      />

      <IssueCodeDialog
        open={issueOpen}
        onClose={() => setIssueOpen(false)}
        onIssued={refresh}
      />

      <ConfirmDialog
        open={!!revokeTarget}
        title="코드를 회수하시겠습니까?"
        description={`${revokeTarget?.code} 코드를 DB에서 삭제합니다. 이미 사용된 코드의 경우 연결된 의료진 계정은 유지됩니다.`}
        danger
        confirmLabel="회수"
        onClose={() => setRevokeTarget(null)}
        onConfirm={async () => {
          if (revokeTarget) {
            await revokeStaffCode(revokeTarget.code);
            await refresh();
          }
        }}
      />
    </AdminLayout>
  );
}

function CodeStatusBadge({ code }: { code: StaffCode }) {
  const expired = code.expiresAt && code.expiresAt < Date.now();
  const used = !!code.usedBy;
  const label = used ? '사용됨' : expired ? '만료' : '미사용';
  const cls = used
    ? 'bg-primary/10 text-primary'
    : expired
      ? 'bg-red-50 text-red-600'
      : 'bg-green-50 text-green-700';
  return (
    <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${cls}`}>
      {label}
    </span>
  );
}
