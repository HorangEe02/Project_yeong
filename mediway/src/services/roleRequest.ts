import { ref, get, remove } from 'firebase/database';
import { auth, db, isFirebaseConfigured } from '@/config/firebase';
import { appendAudit } from '@/services/auditLog';
import { setUserRole, updateUserProfile } from '@/services/userProfile';
import type { AdminUserRow } from '@/types/admin';
import type { PendingRoleRequest, UserProfile } from '@/types/auth';

export interface SubmitRoleRequestInput {
  hospitalId: string;
  department: string;
  reason?: string;
}

/** 환자 본인이 의료진 전환 신청 */
export async function submitRoleRequest(
  input: SubmitRoleRequestInput,
): Promise<PendingRoleRequest> {
  if (!isFirebaseConfigured()) throw new Error('Firebase 미설정');
  const user = auth.currentUser;
  if (!user || user.isAnonymous) throw new Error('로그인이 필요합니다');

  if (!input.hospitalId.trim() || !input.department.trim()) {
    throw new Error('소속과 부서를 모두 입력하세요');
  }

  const request: PendingRoleRequest = {
    requestedRole: 'staff',
    hospitalId: input.hospitalId.trim(),
    department: input.department.trim(),
    reason: input.reason?.trim() || undefined,
    requestedAt: Date.now(),
    status: 'pending',
  };
  await updateUserProfile(user.uid, { pendingRoleRequest: request });
  await appendAudit('user.role.request', user.uid, {
    department: request.department,
    hospitalId: request.hospitalId,
  });
  return request;
}

/** 신청 본인 취소 */
export async function cancelRoleRequest(): Promise<void> {
  if (!isFirebaseConfigured()) return;
  const user = auth.currentUser;
  if (!user) throw new Error('로그인이 필요합니다');
  await remove(ref(db, `users/${user.uid}/pendingRoleRequest`));
}

/** 승인 대기 목록 조회 (admin) */
export async function listPendingRequests(): Promise<AdminUserRow[]> {
  if (!isFirebaseConfigured()) return [];
  const snap = await get(ref(db, 'users'));
  if (!snap.exists()) return [];
  const rows: AdminUserRow[] = [];
  snap.forEach((child) => {
    const row = child.val() as UserProfile;
    if (row.pendingRoleRequest?.status === 'pending') {
      rows.push(row);
    }
  });
  return rows.sort(
    (a, b) =>
      (b.pendingRoleRequest?.requestedAt ?? 0) -
      (a.pendingRoleRequest?.requestedAt ?? 0),
  );
}

/** 관리자가 신청을 승인 → role=staff 로 승격 */
export async function approveRoleRequest(uid: string): Promise<void> {
  if (!isFirebaseConfigured()) throw new Error('Firebase 미설정');
  const snap = await get(ref(db, `users/${uid}`));
  if (!snap.exists()) throw new Error('사용자를 찾을 수 없습니다');
  const profile = snap.val() as UserProfile;
  if (profile.pendingRoleRequest?.status !== 'pending') {
    throw new Error('대기 중인 신청이 없습니다');
  }
  const req = profile.pendingRoleRequest;

  await updateUserProfile(uid, {
    hospitalId: req.hospitalId,
    department: req.department,
  });
  await setUserRole(uid, 'staff');
  // 요청 제거
  await remove(ref(db, `users/${uid}/pendingRoleRequest`));

  await appendAudit('user.role.approve', uid, {
    hospitalId: req.hospitalId,
    department: req.department,
  });
}

/** 관리자가 신청을 거절 */
export async function rejectRoleRequest(
  uid: string,
  reason?: string,
): Promise<void> {
  if (!isFirebaseConfigured()) return;
  const snap = await get(ref(db, `users/${uid}/pendingRoleRequest`));
  if (!snap.exists()) throw new Error('대기 중인 신청이 없습니다');
  const req = snap.val() as PendingRoleRequest;
  await updateUserProfile(uid, {
    pendingRoleRequest: {
      ...req,
      status: 'rejected',
      rejectReason: reason?.trim() || undefined,
      rejectedAt: Date.now(),
    },
  });
  await appendAudit('user.role.reject', uid, {
    reason: reason ?? null,
  });
}
