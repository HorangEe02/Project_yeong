import type { AuditAction } from '@/types/admin';
import type { UserRole, UserStatus } from '@/types/auth';

export function formatDate(ts: number | undefined | null): string {
  if (!ts) return '-';
  const d = new Date(ts);
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

export function formatDateTime(ts: number | undefined | null): string {
  if (!ts) return '-';
  const d = new Date(ts);
  return `${formatDate(ts)} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function formatRelativeTime(ts: number): string {
  const diff = Date.now() - ts;
  if (diff < 60_000) return '방금 전';
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}분 전`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}시간 전`;
  if (diff < 30 * 86_400_000) return `${Math.floor(diff / 86_400_000)}일 전`;
  return formatDate(ts);
}

export function formatRoleLabel(role: UserRole | undefined): string {
  switch (role) {
    case 'staff':
      return '의료진';
    case 'admin':
      return '관리자';
    case 'patient':
      return '환자';
    default:
      return '-';
  }
}

export function formatStatusLabel(status: UserStatus | undefined): string {
  switch (status) {
    case 'active':
      return '활성';
    case 'suspended':
      return '비활성';
    case 'deleted':
      return '삭제됨';
    default:
      return '-';
  }
}

export function formatActionLabel(action: AuditAction): string {
  switch (action) {
    case 'user.status.change':
      return '계정 상태 변경';
    case 'user.role.change':
      return '역할 변경';
    case 'user.password.reset':
      return '비밀번호 재설정 발송';
    case 'user.soft_delete':
      return '계정 삭제';
    case 'staff_code.issue':
      return '의료진 코드 발급';
    case 'staff_code.revoke':
      return '의료진 코드 회수';
    case 'session.force_expire':
      return '세션 강제 만료';
    case 'visit_plan.set':
      return '방문 계획 설정';
    case 'visit_plan.clear':
      return '방문 계획 삭제';
    case 'visit_plan.auto_send':
      return '방문 계획 자동 전송';
    case 'user.invite.create':
      return '의료진 초대 발급';
    case 'user.invite.accept':
      return '의료진 초대 수락';
    case 'user.invite.revoke':
      return '의료진 초대 폐기';
    case 'user.role.request':
      return '역할 전환 신청';
    case 'user.role.approve':
      return '역할 전환 승인';
    case 'user.role.reject':
      return '역할 전환 거절';
    case 'user.account.create':
      return '의료진 계정 직접 생성';
    default:
      return action;
  }
}

function pad(n: number): string {
  return String(n).padStart(2, '0');
}
