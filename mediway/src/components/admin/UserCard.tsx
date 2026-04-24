import { Link } from 'react-router-dom';
import { UserStatusBadge } from '@/components/admin/UserStatusBadge';
import { UserRowActions } from '@/components/admin/UserRowActions';
import { formatDate, formatRoleLabel } from '@/utils/format';
import type { AdminUserRow } from '@/types/admin';

interface UserCardProps {
  row: AdminUserRow;
  isSelf: boolean;
  onChangeRole: () => void;
  onToggleStatus: () => void;
  onResetPassword: () => void;
  onSoftDelete: () => void;
}

/** 모바일·태블릿(< lg) 카드 레이아웃 — 모든 필드를 한 화면에 */
export function UserCard({
  row,
  isSelf,
  onChangeRole,
  onToggleStatus,
  onResetPassword,
  onSoftDelete,
}: UserCardProps) {
  return (
    <div className="flex flex-col gap-3 rounded-xl bg-surface-container-lowest p-4 shadow-ambient">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <Link
            to={`/admin/users/${row.uid}`}
            className="block truncate text-sm font-semibold text-on-surface no-underline hover:underline"
          >
            {row.displayName ?? '(이름 없음)'}
          </Link>
          <p className="truncate text-xs text-on-surface-variant">{row.email ?? '-'}</p>
        </div>
        <UserStatusBadge status={row.status} />
      </div>

      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-on-surface-variant">
        <span className="rounded-full bg-surface-container-high px-2 py-0.5 font-medium text-on-surface">
          {formatRoleLabel(row.role)}
        </span>
        {row.department && <span>· {row.department}</span>}
        <span>· 가입 {formatDate(row.createdAt)}</span>
      </div>

      <div className="flex justify-end">
        <UserRowActions
          row={row}
          isSelf={isSelf}
          onChangeRole={onChangeRole}
          onToggleStatus={onToggleStatus}
          onResetPassword={onResetPassword}
          onSoftDelete={onSoftDelete}
        />
      </div>
    </div>
  );
}
