import { ref, get, set, update, remove, runTransaction } from 'firebase/database';
import { auth, db, isFirebaseConfigured } from '@/config/firebase';
import { appendAudit } from '@/services/auditLog';
import { setUserRole, updateUserProfile } from '@/services/userProfile';
import type {
  StaffInvitation,
  StaffInvitationResult,
} from '@/types/staff-invitation';
import { INVITE_TTL_MS } from '@/types/staff-invitation';

const TOKEN_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789';
const TOKEN_LENGTH = 32;

export function generateInviteToken(): string {
  const buf = new Uint32Array(TOKEN_LENGTH);
  crypto.getRandomValues(buf);
  let out = '';
  for (let i = 0; i < TOKEN_LENGTH; i++) {
    out += TOKEN_ALPHABET[buf[i] % TOKEN_ALPHABET.length];
  }
  return out;
}

export interface CreateInvitationInput {
  email: string;
  displayName?: string;
  department: string;
  hospitalId: string;
  ttlMs?: number;
}

/** admin 전용 초대 생성 */
export async function createStaffInvitation(
  input: CreateInvitationInput,
): Promise<StaffInvitation> {
  if (!isFirebaseConfigured()) throw new Error('Firebase 미설정');
  const actor = auth.currentUser;
  if (!actor) throw new Error('로그인이 필요합니다');

  const now = Date.now();
  const ttl = input.ttlMs ?? INVITE_TTL_MS;
  for (let attempt = 0; attempt < 3; attempt++) {
    const token = generateInviteToken();
    const invitation: StaffInvitation = {
      token,
      email: input.email.trim().toLowerCase(),
      displayName: input.displayName?.trim() || null,
      department: input.department.trim(),
      hospitalId: input.hospitalId.trim(),
      invitedBy: actor.uid,
      invitedByEmail: actor.email,
      invitedAt: now,
      expiresAt: now + ttl,
      status: 'pending',
    };
    const snap = await get(ref(db, `staff_invitations/${token}`));
    if (snap.exists()) continue;
    await set(ref(db, `staff_invitations/${token}`), invitation);
    await appendAudit('user.invite.create', invitation.email, {
      token,
      department: invitation.department,
      hospitalId: invitation.hospitalId,
    });
    return invitation;
  }
  throw new Error('초대 토큰 생성 실패 — 다시 시도하세요');
}

/** 초대 조회 (토큰 보유자 누구나) */
export async function getStaffInvitation(
  token: string,
): Promise<StaffInvitationResult> {
  if (!isFirebaseConfigured()) return { valid: false, reason: 'not_found' };
  const snap = await get(ref(db, `staff_invitations/${token}`));
  if (!snap.exists()) return { valid: false, reason: 'not_found' };
  const data = snap.val() as StaffInvitation;
  if (data.status === 'revoked') return { valid: false, reason: 'revoked' };
  if (data.status === 'accepted') return { valid: false, reason: 'accepted' };
  if (data.expiresAt < Date.now()) return { valid: false, reason: 'expired' };
  return { valid: true, invitation: data };
}

/** 초대 수락 — 현재 로그인 사용자의 이메일이 초대 이메일과 일치해야 함 */
export async function acceptStaffInvitation(token: string): Promise<StaffInvitation> {
  if (!isFirebaseConfigured()) throw new Error('Firebase 미설정');
  const user = auth.currentUser;
  if (!user || user.isAnonymous) {
    throw new Error('로그인 후 수락할 수 있습니다');
  }
  if (!user.email) throw new Error('이메일 정보가 없습니다');

  const invitePath = `staff_invitations/${token}`;
  const userEmail = user.email.toLowerCase();
  const now = Date.now();

  const tx = await runTransaction(ref(db, invitePath), (current: StaffInvitation | null) => {
    if (!current) return current;
    if (current.status !== 'pending') return; // abort
    if (current.expiresAt < now) return;
    if (current.email.toLowerCase() !== userEmail) return;
    return {
      ...current,
      status: 'accepted' as const,
      claimedBy: user.uid,
      claimedAt: now,
    };
  });

  if (!tx.committed || !tx.snapshot.exists()) {
    throw new Error('초대 수락 실패 — 만료되었거나 다른 이메일로 로그인했습니다');
  }
  const invitation = tx.snapshot.val() as StaffInvitation;

  // 사용자 프로필 승격
  await updateUserProfile(user.uid, {
    hospitalId: invitation.hospitalId,
    department: invitation.department,
    displayName: invitation.displayName ?? user.displayName ?? undefined,
  });
  await setUserRole(user.uid, 'staff');

  await appendAudit('user.invite.accept', user.uid, {
    token,
    hospitalId: invitation.hospitalId,
    department: invitation.department,
  });
  return invitation;
}

/** 초대 폐기 (admin) */
export async function revokeStaffInvitation(token: string): Promise<void> {
  if (!isFirebaseConfigured()) return;
  await update(ref(db, `staff_invitations/${token}`), { status: 'revoked' });
  await appendAudit('user.invite.revoke', token);
}

/** 초대 삭제 (admin, 완전 정리용) */
export async function deleteStaffInvitation(token: string): Promise<void> {
  if (!isFirebaseConfigured()) return;
  await remove(ref(db, `staff_invitations/${token}`));
}

/** 초대 전체 목록 조회 (admin) */
export async function listStaffInvitations(): Promise<StaffInvitation[]> {
  if (!isFirebaseConfigured()) return [];
  const snap = await get(ref(db, 'staff_invitations'));
  if (!snap.exists()) return [];
  const rows: StaffInvitation[] = [];
  snap.forEach((child) => {
    rows.push(child.val() as StaffInvitation);
  });
  return rows.sort((a, b) => b.invitedAt - a.invitedAt);
}

export function buildInviteUrl(token: string): string {
  const origin =
    typeof window !== 'undefined'
      ? window.location.origin
      : 'https://mediway-demo.web.app';
  return `${origin}/invite/${token}`;
}

/** 대량 초대 — 순차 처리(Firebase write 간격) + 진행률 콜백 */
export async function bulkCreateInvitations(
  inputs: CreateInvitationInput[],
  onProgress?: (done: number, total: number) => void,
): Promise<{
  successes: StaffInvitation[];
  failures: Array<{ input: CreateInvitationInput; error: string }>;
}> {
  const successes: StaffInvitation[] = [];
  const failures: Array<{ input: CreateInvitationInput; error: string }> = [];
  for (let i = 0; i < inputs.length; i++) {
    const input = inputs[i];
    try {
      const res = await createStaffInvitation(input);
      successes.push(res);
    } catch (err) {
      failures.push({
        input,
        error: err instanceof Error ? err.message : String(err),
      });
    }
    onProgress?.(i + 1, inputs.length);
  }
  return { successes, failures };
}
