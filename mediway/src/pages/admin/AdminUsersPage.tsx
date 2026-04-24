import { useCallback, useEffect, useMemo, useState } from 'react';
import { Search, UserPlus, UserCog } from 'lucide-react';
import { Link } from 'react-router-dom';
import { AdminLayout } from '@/pages/admin/AdminLayout';
import { DataTable, type Column } from '@/components/admin/DataTable';
import { UserStatusBadge } from '@/components/admin/UserStatusBadge';
import { InviteStaffDialog } from '@/components/admin/InviteStaffDialog';
import { ChangeRoleDialog } from '@/components/admin/ChangeRoleDialog';
import { ConfirmDialog } from '@/components/admin/ConfirmDialog';
import { UserRowActions } from '@/components/admin/UserRowActions';
import { UserCard } from '@/components/admin/UserCard';
import { CreateStaffAccountDialog } from '@/components/admin/CreateStaffAccountDialog';
import {
  changeUserStatus,
  listUsers,
  sendPasswordResetFor,
  softDeleteUser,
} from '@/services/adminUsers';
import { useAuthStore } from '@/stores/authStore';
import type { AdminUserRow } from '@/types/admin';
import type { UserRole, UserStatus } from '@/types/auth';
import { formatDate, formatRoleLabel } from '@/utils/format';

const ROLE_TABS: { value: UserRole | 'all'; label: string }[] = [
  { value: 'all', label: '전체' },
  { value: 'staff', label: '의료진' },
  { value: 'patient', label: '환자' },
  { value: 'admin', label: '관리자' },
];

const STATUS_OPTIONS: { value: UserStatus | 'all'; label: string }[] = [
  { value: 'all', label: '모든 상태' },
  { value: 'active', label: '활성' },
  { value: 'suspended', label: '비활성' },
  { value: 'deleted', label: '삭제됨' },
];

export function AdminUsersPage() {
  const actorUid = useAuthStore((s) => s.user?.uid);
  const [rows, setRows] = useState<AdminUserRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [inviteOpen, setInviteOpen] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [roleTarget, setRoleTarget] = useState<AdminUserRow | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<AdminUserRow | null>(null);
  const [resetTarget, setResetTarget] = useState<AdminUserRow | null>(null);
  const [tab, setTab] = useState<UserRole | 'all'>('all');
  const [status, setStatus] = useState<UserStatus | 'all'>('all');
  const [q, setQ] = useState('');
  const [toast, setToast] = useState<{ tone: 'ok' | 'err'; text: string } | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      setRows(await listUsers());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (!toast) return;
    const id = setTimeout(() => setToast(null), 3000);
    return () => clearTimeout(id);
  }, [toast]);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return rows.filter((r) => {
      if (tab !== 'all' && r.role !== tab) return false;
      if (status !== 'all' && r.status !== status) return false;
      if (needle) {
        const hay = `${r.displayName ?? ''} ${r.email ?? ''} ${r.department ?? ''}`.toLowerCase();
        if (!hay.includes(needle)) return false;
      }
      return true;
    });
  }, [rows, tab, status, q]);

  const act = async (fn: () => Promise<void>, ok: string) => {
    try {
      await fn();
      setToast({ tone: 'ok', text: ok });
      await refresh();
    } catch (err) {
      setToast({
        tone: 'err',
        text: err instanceof Error ? err.message : String(err),
      });
    }
  };

  const onToggleStatus = (r: AdminUserRow) => {
    const next: UserStatus = r.status === 'active' ? 'suspended' : 'active';
    void act(
      () => changeUserStatus(r.uid, next),
      next === 'active' ? '계정을 활성화했습니다' : '계정을 비활성화했습니다',
    );
  };

  // 데스크톱(lg+) 테이블 컬럼 정의
  const columns: Column<AdminUserRow>[] = [
    {
      key: 'user',
      header: '사용자',
      cell: (r) => (
        <div className="min-w-0">
          <Link
            to={`/admin/users/${r.uid}`}
            className="block truncate font-medium text-on-surface no-underline hover:underline"
          >
            {r.displayName ?? '(이름 없음)'}
          </Link>
          <p className="truncate text-[11px] text-on-surface-variant">
            {r.email ?? '-'}
          </p>
        </div>
      ),
    },
    {
      key: 'role',
      header: '역할',
      cell: (r) => formatRoleLabel(r.role),
      width: '90px',
    },
    {
      key: 'dept',
      header: '소속',
      cell: (r) => <span className="text-on-surface-variant">{r.department ?? '-'}</span>,
      className: 'hidden xl:table-cell',
    },
    {
      key: 'status',
      header: '상태',
      cell: (r) => <UserStatusBadge status={r.status} />,
      width: '80px',
    },
    {
      key: 'created',
      header: '가입일',
      cell: (r) => (
        <span className="text-xs text-on-surface-variant">
          {formatDate(r.createdAt)}
        </span>
      ),
      width: '110px',
      className: 'hidden xl:table-cell',
    },
    {
      key: 'actions',
      header: '액션',
      cell: (r) => (
        <UserRowActions
          row={r}
          isSelf={actorUid === r.uid}
          onChangeRole={() => setRoleTarget(r)}
          onToggleStatus={() => onToggleStatus(r)}
          onResetPassword={() => setResetTarget(r)}
          onSoftDelete={() => setDeleteTarget(r)}
        />
      ),
      width: '64px',
    },
  ];

  return (
    <AdminLayout
      title="사용자 관리"
      description="의료진·환자·관리자 계정을 조회하고 상태를 변경합니다"
      actions={
        <>
          <button
            type="button"
            onClick={() => setCreateOpen(true)}
            className="flex items-center gap-1 rounded-lg border border-primary bg-surface px-3 py-1.5 text-xs font-medium text-primary"
            title="Functions 배포 필요 (Blaze 플랜)"
          >
            <UserCog className="h-3.5 w-3.5" />
            계정 생성
          </button>
          <button
            type="button"
            onClick={() => setInviteOpen(true)}
            className="flex items-center gap-1 rounded-lg bg-primary px-3 py-1.5 text-xs font-medium text-on-primary"
          >
            <UserPlus className="h-3.5 w-3.5" />
            의료진 초대
          </button>
        </>
      }
    >
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="flex overflow-hidden rounded-lg border border-surface-container-high">
          {ROLE_TABS.map((t) => (
            <button
              key={t.value}
              type="button"
              onClick={() => setTab(t.value)}
              className={`px-3 py-1.5 text-xs font-medium ${
                tab === t.value
                  ? 'bg-primary text-on-primary'
                  : 'bg-surface text-on-surface'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        <select
          value={status}
          onChange={(e) => setStatus(e.target.value as UserStatus | 'all')}
          className="rounded-lg border border-surface-container-high bg-surface px-3 py-1.5 text-xs"
        >
          {STATUS_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>

        <div className="relative ml-auto">
          <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-on-surface-variant" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="이름·이메일·부서 검색"
            className="w-full rounded-lg border border-surface-container-high bg-surface py-1.5 pl-8 pr-3 text-xs outline-none focus:border-primary sm:w-64"
          />
        </div>
      </div>

      <p className="mb-2 text-xs text-on-surface-variant">
        {loading ? '...' : `${filtered.length}명`}
      </p>

      {toast && (
        <p
          className={`mb-2 rounded-lg px-3 py-2 text-xs ${
            toast.tone === 'ok' ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-600'
          }`}
        >
          {toast.text}
        </p>
      )}

      {/* 데스크톱 (lg+): 테이블 */}
      <div className="hidden lg:block">
        <DataTable
          columns={columns}
          rows={filtered}
          rowKey={(r) => r.uid}
          loading={loading}
          disableMobileCard
        />
      </div>

      {/* 태블릿/모바일 (< lg): 카드 */}
      <div className="flex flex-col gap-2 lg:hidden">
        {loading ? (
          <p className="rounded-xl bg-surface-container-lowest p-6 text-center text-sm text-on-surface-variant shadow-ambient">
            불러오는 중...
          </p>
        ) : filtered.length === 0 ? (
          <p className="rounded-xl bg-surface-container-lowest p-6 text-center text-sm text-on-surface-variant shadow-ambient">
            표시할 사용자가 없습니다
          </p>
        ) : (
          filtered.map((r) => (
            <UserCard
              key={r.uid}
              row={r}
              isSelf={actorUid === r.uid}
              onChangeRole={() => setRoleTarget(r)}
              onToggleStatus={() => onToggleStatus(r)}
              onResetPassword={() => setResetTarget(r)}
              onSoftDelete={() => setDeleteTarget(r)}
            />
          ))
        )}
      </div>

      <InviteStaffDialog
        open={inviteOpen}
        onClose={() => setInviteOpen(false)}
        onIssued={() => {
          /* 목록 재조회 불필요 — 초대는 staff_invitations에 저장 */
        }}
      />

      <CreateStaffAccountDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={() => {
          setToast({ tone: 'ok', text: '의료진 계정이 생성되었습니다' });
          void refresh();
        }}
      />

      <ChangeRoleDialog
        open={!!roleTarget}
        row={roleTarget}
        onClose={() => setRoleTarget(null)}
        onChanged={() => {
          setToast({ tone: 'ok', text: '역할이 변경되었습니다' });
          void refresh();
        }}
      />

      <ConfirmDialog
        open={!!resetTarget}
        title="비밀번호 재설정 메일을 보낼까요?"
        description={
          resetTarget?.email
            ? `${resetTarget.email} 로 재설정 링크를 발송합니다.`
            : '이메일이 없습니다'
        }
        confirmLabel="발송"
        onClose={() => setResetTarget(null)}
        onConfirm={async () => {
          if (!resetTarget?.email) return;
          await act(
            () => sendPasswordResetFor(resetTarget.uid, resetTarget.email!),
            '비밀번호 재설정 메일을 발송했습니다',
          );
        }}
      />

      <ConfirmDialog
        open={!!deleteTarget}
        title="계정을 삭제하시겠습니까?"
        description="프로필이 익명화되고 상태가 '삭제됨'으로 변경됩니다. 연관된 방문 계획도 함께 삭제됩니다."
        requireText="DELETE"
        danger
        confirmLabel="삭제"
        onClose={() => setDeleteTarget(null)}
        onConfirm={async () => {
          if (!deleteTarget) return;
          await act(() => softDeleteUser(deleteTarget.uid), '계정이 삭제되었습니다');
        }}
      />
    </AdminLayout>
  );
}
