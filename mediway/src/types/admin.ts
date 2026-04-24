import type { UserProfile, UserRole, UserStatus } from '@/types/auth';

export interface AdminUserFilter {
  role?: UserRole;
  status?: UserStatus;
  q?: string;
}

export interface AdminStats {
  totalUsers: number;
  staffCount: number;
  patientCount: number;
  adminCount: number;
  activeCount: number;
  suspendedCount: number;
  activeSessions: number;
}

export type AuditAction =
  | 'user.status.change'
  | 'user.role.change'
  | 'user.password.reset'
  | 'user.soft_delete'
  | 'staff_code.issue'
  | 'staff_code.revoke'
  | 'session.force_expire'
  | 'visit_plan.set'
  | 'visit_plan.clear'
  | 'visit_plan.auto_send'
  | 'user.invite.create'
  | 'user.invite.accept'
  | 'user.invite.revoke'
  | 'user.role.request'
  | 'user.role.approve'
  | 'user.role.reject'
  | 'user.account.create';

export interface AuditLogEntry {
  id: string;
  actorUid: string;
  actorEmail: string | null;
  action: AuditAction;
  target: string; // uid, code, sessionId
  meta?: Record<string, string | number | boolean | null>;
  timestamp: number;
}

export type AdminUserRow = UserProfile;
