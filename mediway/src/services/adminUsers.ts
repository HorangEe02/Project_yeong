import { ref, get } from 'firebase/database';
import { db, isFirebaseConfigured } from '@/config/firebase';
import { sendPasswordReset } from '@/services/auth';
import { appendAudit } from '@/services/auditLog';
import { setUserRole, setUserStatus, updateUserProfile } from '@/services/userProfile';
import { clearVisitPlan } from '@/services/visitPlan';
import type { AdminUserFilter, AdminUserRow, AdminStats } from '@/types/admin';
import type { UserRole, UserStatus } from '@/types/auth';

/** 모든 사용자 조회 + 클라이언트 측 필터링 (소규모 데모 전제) */
export async function listUsers(
  filter: AdminUserFilter = {},
): Promise<AdminUserRow[]> {
  if (!isFirebaseConfigured()) return [];
  const snapshot = await get(ref(db, 'users'));
  if (!snapshot.exists()) return [];
  const rows: AdminUserRow[] = [];
  snapshot.forEach((child) => {
    rows.push(child.val() as AdminUserRow);
  });
  return applyFilter(rows, filter).sort((a, b) => b.createdAt - a.createdAt);
}

export function applyFilter(
  rows: AdminUserRow[],
  filter: AdminUserFilter,
): AdminUserRow[] {
  const q = filter.q?.trim().toLowerCase();
  return rows.filter((r) => {
    if (filter.role && r.role !== filter.role) return false;
    if (filter.status && r.status !== filter.status) return false;
    if (q) {
      const hay = `${r.displayName ?? ''} ${r.email ?? ''} ${r.department ?? ''}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
}

export async function getUserDetail(uid: string): Promise<AdminUserRow | null> {
  if (!isFirebaseConfigured()) return null;
  const snapshot = await get(ref(db, `users/${uid}`));
  if (!snapshot.exists()) return null;
  return snapshot.val() as AdminUserRow;
}

export async function changeUserStatus(uid: string, status: UserStatus): Promise<void> {
  await setUserStatus(uid, status);
  await appendAudit('user.status.change', uid, { status });
}

export async function changeUserRole(uid: string, role: UserRole): Promise<void> {
  await setUserRole(uid, role);
  await appendAudit('user.role.change', uid, { role });
}

export async function softDeleteUser(uid: string): Promise<void> {
  await updateUserProfile(uid, {
    status: 'deleted',
    displayName: '(탈퇴한 사용자)',
  });
  // 연관 개인 데이터 정리 — visit_plan은 어차피 24h TTL이지만 즉시 제거해 프라이버시 보장
  try {
    await clearVisitPlan(uid);
  } catch (err) {
    console.warn('[MediWay] visit_plan 정리 실패(무시):', err);
  }
  await appendAudit('user.soft_delete', uid);
}

export async function sendPasswordResetFor(
  uid: string,
  email: string,
): Promise<void> {
  await sendPasswordReset(email);
  await appendAudit('user.password.reset', uid);
}

export function computeStats(rows: AdminUserRow[], activeSessions = 0): AdminStats {
  return {
    totalUsers: rows.length,
    staffCount: rows.filter((r) => r.role === 'staff').length,
    patientCount: rows.filter((r) => r.role === 'patient').length,
    adminCount: rows.filter((r) => r.role === 'admin').length,
    activeCount: rows.filter((r) => r.status === 'active').length,
    suspendedCount: rows.filter((r) => r.status === 'suspended').length,
    activeSessions,
  };
}
