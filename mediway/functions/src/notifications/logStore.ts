import type * as admin from 'firebase-admin';
import type {
  NotificationEvent,
  NotificationLogEntry,
  SendResult,
  Channel,
  UserNotificationPrefs,
} from './types';

/**
 * `/notification_logs/{uid}/{pushId}` — 알림 발송 기록.
 *
 * Dispatcher 흐름:
 *  1) createLogEntry(): event 초기 저장 (attempts 비어있음)
 *  2) 각 채널 시도 후 attempts 축적
 *  3) finalizeLog(): attempts 전체 + finalStatus + deliveredChannel 업데이트
 *
 * 멱등성 보장: findByIdempotencyKey() 로 동일 key 이미 존재하면 중복 skip.
 */

export async function createLogEntry(
  db: admin.database.Database,
  event: NotificationEvent,
): Promise<{ logId: string }> {
  const ref = db.ref(`notification_logs/${event.targetUid}`).push();
  const now = Date.now();
  const entry: NotificationLogEntry = {
    event,
    attempts: [],
    finalStatus: 'failed', // 초기값, finalize 시 갱신
    createdAt: now,
    updatedAt: now,
  };
  await ref.set(entry);
  return { logId: ref.key as string };
}

export async function finalizeLog(
  db: admin.database.Database,
  targetUid: string,
  logId: string,
  attempts: SendResult[],
  deliveredChannel: Channel | null,
): Promise<void> {
  const now = Date.now();
  const update: Partial<NotificationLogEntry> = {
    attempts,
    finalStatus: deliveredChannel ? 'delivered' : 'failed',
    updatedAt: now,
  };
  if (deliveredChannel) update.deliveredChannel = deliveredChannel;
  await db.ref(`notification_logs/${targetUid}/${logId}`).update(update);
}

/**
 * 동일 uid + idempotencyKey 조합의 기존 로그 검색.
 * 최근 24시간 내에서만 탐색 (정책).
 */
export async function findByIdempotencyKey(
  db: admin.database.Database,
  targetUid: string,
  idempotencyKey: string,
): Promise<{ logId: string; entry: NotificationLogEntry } | null> {
  const since = Date.now() - 24 * 60 * 60 * 1000;
  const snap = await db
    .ref(`notification_logs/${targetUid}`)
    .orderByChild('createdAt')
    .startAt(since)
    .get();
  if (!snap.exists()) return null;
  let found: { logId: string; entry: NotificationLogEntry } | null = null;
  snap.forEach((child) => {
    const entry = child.val() as NotificationLogEntry;
    if (entry?.event?.idempotencyKey === idempotencyKey) {
      found = { logId: child.key as string, entry };
      return true; // 탐색 종료
    }
    return false;
  });
  return found;
}

/** 사용자 preferences 로드 — 없으면 빈 객체 반환 */
export async function loadUserPrefs(
  db: admin.database.Database,
  targetUid: string,
): Promise<UserNotificationPrefs> {
  const snap = await db.ref(`users/${targetUid}/notifications`).get();
  return snap.exists() ? (snap.val() as UserNotificationPrefs) : {};
}
