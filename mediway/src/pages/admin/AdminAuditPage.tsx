import { useCallback, useEffect, useMemo, useState } from 'react';
import { Download, RefreshCw } from 'lucide-react';
import { AdminLayout } from '@/pages/admin/AdminLayout';
import { DataTable, type Column } from '@/components/admin/DataTable';
import { listAudit } from '@/services/auditLog';
import { downloadCsv, toCsv } from '@/utils/csv';
import { formatActionLabel, formatDateTime } from '@/utils/format';
import type { AuditAction, AuditLogEntry } from '@/types/admin';

const ACTION_OPTIONS: { value: AuditAction | 'all'; label: string }[] = [
  { value: 'all', label: '전체 액션' },
  { value: 'user.status.change', label: '계정 상태 변경' },
  { value: 'user.role.change', label: '역할 변경' },
  { value: 'user.password.reset', label: '비밀번호 재설정' },
  { value: 'user.soft_delete', label: '계정 삭제' },
  { value: 'staff_code.issue', label: '코드 발급' },
  { value: 'staff_code.revoke', label: '코드 회수' },
  { value: 'session.force_expire', label: '세션 강제 만료' },
];

export function AdminAuditPage() {
  const [rows, setRows] = useState<AuditLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [action, setAction] = useState<AuditAction | 'all'>('all');
  const [q, setQ] = useState('');

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      setRows(await listAudit(200));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return rows.filter((r) => {
      if (action !== 'all' && r.action !== action) return false;
      if (needle) {
        const hay = `${r.actorEmail ?? ''} ${r.target}`.toLowerCase();
        if (!hay.includes(needle)) return false;
      }
      return true;
    });
  }, [rows, action, q]);

  const onExport = () => {
    const csv = toCsv(
      filtered.map((r) => ({
        timestamp: formatDateTime(r.timestamp),
        action: r.action,
        actor: r.actorEmail ?? r.actorUid,
        target: r.target,
        meta: r.meta ? JSON.stringify(r.meta) : '',
      })),
      [
        { key: 'timestamp', label: 'timestamp' },
        { key: 'action', label: 'action' },
        { key: 'actor', label: 'actor' },
        { key: 'target', label: 'target' },
        { key: 'meta', label: 'meta' },
      ],
    );
    downloadCsv(`audit-${new Date().toISOString().slice(0, 10)}.csv`, csv);
  };

  const columns: Column<AuditLogEntry>[] = [
    {
      key: 'time',
      header: '시간',
      cell: (r) => (
        <span className="whitespace-nowrap text-xs text-on-surface-variant">
          {formatDateTime(r.timestamp)}
        </span>
      ),
      width: '160px',
    },
    {
      key: 'action',
      header: '액션',
      cell: (r) => formatActionLabel(r.action),
    },
    {
      key: 'actor',
      header: '수행자',
      cell: (r) => (
        <span className="text-xs text-on-surface-variant">
          {r.actorEmail ?? r.actorUid}
        </span>
      ),
    },
    {
      key: 'target',
      header: '대상',
      cell: (r) => <span className="font-mono text-xs">{r.target}</span>,
    },
    {
      key: 'meta',
      header: '메타',
      cell: (r) =>
        r.meta ? (
          <span className="text-xs text-on-surface-variant">
            {Object.entries(r.meta)
              .map(([k, v]) => `${k}=${v}`)
              .join(' · ')}
          </span>
        ) : null,
    },
  ];

  return (
    <AdminLayout
      title="감사 로그"
      description="운영 액션의 이력을 조회합니다"
      actions={
        <>
          <button
            type="button"
            onClick={refresh}
            className="flex items-center gap-1 rounded-lg border border-surface-container-high bg-surface px-3 py-1.5 text-xs"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            새로고침
          </button>
          <button
            type="button"
            onClick={onExport}
            disabled={filtered.length === 0}
            className="flex items-center gap-1 rounded-lg border border-surface-container-high bg-surface px-3 py-1.5 text-xs disabled:opacity-50"
          >
            <Download className="h-3.5 w-3.5" />
            CSV
          </button>
        </>
      }
    >
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <select
          value={action}
          onChange={(e) => setAction(e.target.value as AuditAction | 'all')}
          className="rounded-lg border border-surface-container-high bg-surface px-3 py-1.5 text-xs"
        >
          {ACTION_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="수행자·대상 검색"
          className="rounded-lg border border-surface-container-high bg-surface px-3 py-1.5 text-xs outline-none focus:border-primary"
        />
        <span className="ml-auto text-xs text-on-surface-variant">
          {loading ? '...' : `${filtered.length}건`}
        </span>
      </div>

      <DataTable
        columns={columns}
        rows={filtered}
        rowKey={(r) => r.id}
        loading={loading}
      />
    </AdminLayout>
  );
}
