import { ref, get, push, query, limitToLast, orderByChild } from 'firebase/database';
import { auth, db, isFirebaseConfigured } from '@/config/firebase';
import { useAuthStore } from '@/stores/authStore';
import type { AuditAction, AuditLogEntry } from '@/types/admin';

/**
 * T1-1c 이후 — write/read 경로가 `/audit_logs_v2/{hospitalId}/{pushId}` 로 이전됨.
 * 기존 `/audit_logs` 는 platformAdmin read-only, write 금지.
 *
 * `hospitalId` 파라미터가 제공되지 않으면 현재 로그인된 사용자의
 * `profile.hospitalId` 를 사용. platformAdmin 이고 hospitalId 가 없으면 'platform'
 * bucket 으로 기록 (시스템 액션).
 */
function resolveBucket(explicit?: string | null): string {
  if (explicit && explicit.trim()) return explicit.trim();
  const hid = useAuthStore.getState().profile?.hospitalId;
  return hid && hid.trim() ? hid : 'platform';
}

/**
 * 감사 로그 기록 (append-only).
 * @param hospitalId — 필요 시 명시. 생략하면 현재 로그인 사용자의 hospitalId.
 */
export async function appendAudit(
  action: AuditAction,
  target: string,
  meta?: AuditLogEntry['meta'],
  hospitalId?: string | null,
): Promise<void> {
  if (!isFirebaseConfigured()) return;
  const user = auth.currentUser;
  if (!user) return;
  const bucket = resolveBucket(hospitalId);
  const entry: Omit<AuditLogEntry, 'id'> = {
    actorUid: user.uid,
    actorEmail: user.email,
    action,
    target,
    meta,
    timestamp: Date.now(),
  };
  await push(ref(db, `audit_logs_v2/${bucket}`), entry);
}

/**
 * 최근 감사 로그 조회.
 *
 * admin 은 자기 병원 bucket 만 조회. platformAdmin 은 본인 claim 상의 bucket
 * 또는 명시된 `hospitalId` bucket 만 조회한다 (multi-bucket aggregation 은 후속 기능).
 *
 * @param hospitalId — 생략하면 현재 로그인 사용자의 hospitalId.
 */
export async function listAudit(
  limit = 50,
  hospitalId?: string | null,
): Promise<AuditLogEntry[]> {
  if (!isFirebaseConfigured()) return [];
  const bucket = resolveBucket(hospitalId);
  const q = query(
    ref(db, `audit_logs_v2/${bucket}`),
    orderByChild('timestamp'),
    limitToLast(limit),
  );
  const snapshot = await get(q);
  if (!snapshot.exists()) return [];
  const rows: AuditLogEntry[] = [];
  snapshot.forEach((child) => {
    rows.push({ id: child.key ?? '', ...(child.val() as Omit<AuditLogEntry, 'id'>) });
  });
  return rows.reverse();
}
