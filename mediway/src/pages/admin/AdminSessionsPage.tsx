import { useEffect, useState } from 'react';
import { Activity, X } from 'lucide-react';
import { AdminLayout } from '@/pages/admin/AdminLayout';
import { DataTable, type Column } from '@/components/admin/DataTable';
import { ConfirmDialog } from '@/components/admin/ConfirmDialog';
import {
  forceExpireSession,
  subscribeAllSessions,
} from '@/services/adminSessions';
import { formatRelativeTime } from '@/utils/format';
import type { Session } from '@/types/session';

export function AdminSessionsPage() {
  const [rows, setRows] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);
  const [expireTarget, setExpireTarget] = useState<Session | null>(null);
  const [filter, setFilter] = useState<'active' | 'completed' | 'all'>('active');

  useEffect(() => {
    const unsub = subscribeAllSessions((sessions) => {
      setRows(sessions);
      setLoading(false);
    });
    return unsub;
  }, []);

  const filtered = rows.filter((s) => {
    if (filter === 'all') return true;
    if (filter === 'active') return s.status !== 'completed';
    return s.status === 'completed';
  });

  const columns: Column<Session>[] = [
    {
      key: 'sid',
      header: '세션 ID',
      cell: (r) => (
        <span className="font-mono text-xs text-on-surface-variant">
          {r.sessionId.slice(0, 10)}
        </span>
      ),
    },
    {
      key: 'status',
      header: '상태',
      cell: (r) => <SessionBadge status={r.status} />,
      width: '110px',
    },
    {
      key: 'progress',
      header: '진행률',
      cell: (r) => (
        <div className="flex items-center gap-2">
          <div className="h-1.5 w-20 rounded-full bg-surface-container-high">
            <div
              className="h-full rounded-full bg-primary"
              style={{
                width: `${Math.round(
                  (r.currentWaypointIndex / Math.max(1, r.waypoints.length)) * 100,
                )}%`,
              }}
            />
          </div>
          <span className="text-xs text-on-surface-variant">
            {r.currentWaypointIndex}/{r.waypoints.length}
          </span>
        </div>
      ),
    },
    {
      key: 'created',
      header: '생성',
      cell: (r) => (
        <span className="text-xs text-on-surface-variant">
          {formatRelativeTime(r.createdAt)}
        </span>
      ),
      width: '120px',
    },
    {
      key: 'actions',
      header: '',
      cell: (r) =>
        r.status === 'completed' ? null : (
          <button
            type="button"
            onClick={() => setExpireTarget(r)}
            className="flex items-center gap-1 rounded-md border border-amber-300 bg-amber-50 px-2 py-1 text-[11px] text-amber-700"
          >
            <X className="h-3 w-3" />
            강제 만료
          </button>
        ),
      width: '110px',
    },
  ];

  return (
    <AdminLayout
      title="세션"
      description="환자-의료진 간 활성 세션을 실시간으로 확인합니다"
      actions={
        <div className="flex overflow-hidden rounded-lg border border-surface-container-high">
          {(['active', 'completed', 'all'] as const).map((f) => (
            <button
              key={f}
              type="button"
              onClick={() => setFilter(f)}
              className={`px-3 py-1.5 text-xs font-medium ${
                filter === f
                  ? 'bg-primary text-on-primary'
                  : 'bg-surface text-on-surface'
              }`}
            >
              {f === 'active' ? '활성' : f === 'completed' ? '완료' : '전체'}
            </button>
          ))}
        </div>
      }
    >
      <div className="mb-3 flex items-center gap-2 text-xs text-on-surface-variant">
        <Activity className="h-3.5 w-3.5" />
        실시간 구독 중 · {filtered.length}건
      </div>

      <DataTable
        columns={columns}
        rows={filtered}
        rowKey={(r) => r.sessionId}
        loading={loading}
        emptyLabel="표시할 세션이 없습니다"
      />

      <ConfirmDialog
        open={!!expireTarget}
        title="세션을 강제로 만료시킬까요?"
        description={`해당 세션의 상태를 'completed'로 전환합니다. 환자 앱에는 안내가 종료된 것으로 표시됩니다.`}
        danger
        confirmLabel="강제 만료"
        onClose={() => setExpireTarget(null)}
        onConfirm={async () => {
          if (expireTarget) await forceExpireSession(expireTarget.sessionId);
        }}
      />
    </AdminLayout>
  );
}

function SessionBadge({ status }: { status: Session['status'] }) {
  const map: Record<Session['status'], { label: string; cls: string }> = {
    waiting: { label: '대기', cls: 'bg-amber-50 text-amber-700' },
    navigating: { label: '안내 중', cls: 'bg-primary/10 text-primary' },
    completed: { label: '완료', cls: 'bg-surface-container-high text-on-surface-variant' },
  };
  const m = map[status];
  return (
    <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${m.cls}`}>
      {m.label}
    </span>
  );
}
