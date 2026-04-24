import { ref, get, push, query, limitToLast, orderByChild } from 'firebase/database';
import { auth, db, isFirebaseConfigured } from '@/config/firebase';
import type { AuditAction, AuditLogEntry } from '@/types/admin';

/** 감사 로그 기록 (append-only) */
export async function appendAudit(
  action: AuditAction,
  target: string,
  meta?: AuditLogEntry['meta'],
): Promise<void> {
  if (!isFirebaseConfigured()) return;
  const user = auth.currentUser;
  if (!user) return;
  const entry: Omit<AuditLogEntry, 'id'> = {
    actorUid: user.uid,
    actorEmail: user.email,
    action,
    target,
    meta,
    timestamp: Date.now(),
  };
  await push(ref(db, 'audit_logs'), entry);
}

/** 최근 감사 로그 조회 (admin 전용) */
export async function listAudit(limit = 50): Promise<AuditLogEntry[]> {
  if (!isFirebaseConfigured()) return [];
  const q = query(ref(db, 'audit_logs'), orderByChild('timestamp'), limitToLast(limit));
  const snapshot = await get(q);
  if (!snapshot.exists()) return [];
  const rows: AuditLogEntry[] = [];
  snapshot.forEach((child) => {
    rows.push({ id: child.key ?? '', ...(child.val() as Omit<AuditLogEntry, 'id'>) });
  });
  return rows.reverse();
}
