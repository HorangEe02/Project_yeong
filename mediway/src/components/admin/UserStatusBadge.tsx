import type { UserStatus } from '@/types/auth';
import { formatStatusLabel } from '@/utils/format';

export function UserStatusBadge({ status }: { status: UserStatus }) {
  const cls =
    status === 'active'
      ? 'bg-green-50 text-green-700'
      : status === 'suspended'
        ? 'bg-amber-50 text-amber-700'
        : 'bg-red-50 text-red-600';
  return (
    <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${cls}`}>
      {formatStatusLabel(status)}
    </span>
  );
}
