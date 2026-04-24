import { ref, onValue, remove, update, type Unsubscribe } from 'firebase/database';
import { db, isFirebaseConfigured } from '@/config/firebase';
import { appendAudit } from '@/services/auditLog';
import type { Session } from '@/types/session';

/** 전체 세션을 실시간 구독 (admin 전용) */
export function subscribeAllSessions(
  callback: (sessions: Session[]) => void,
): Unsubscribe {
  if (!isFirebaseConfigured()) {
    callback([]);
    return () => {};
  }
  return onValue(ref(db, 'sessions'), (snapshot) => {
    if (!snapshot.exists()) {
      callback([]);
      return;
    }
    const rows: Session[] = [];
    snapshot.forEach((child) => {
      rows.push(child.val() as Session);
    });
    callback(rows.sort((a, b) => b.createdAt - a.createdAt));
  });
}

export async function forceExpireSession(sessionId: string): Promise<void> {
  if (!isFirebaseConfigured()) return;
  await update(ref(db, `sessions/${sessionId}`), { status: 'completed' });
  await appendAudit('session.force_expire', sessionId);
}

export async function deleteSession(sessionId: string): Promise<void> {
  if (!isFirebaseConfigured()) return;
  await remove(ref(db, `sessions/${sessionId}`));
}
