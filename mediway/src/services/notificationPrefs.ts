import { onValue, ref, update } from 'firebase/database';
import { db, isFirebaseConfigured } from '@/config/firebase';
import type {
  NotificationChannel,
  NotificationEventType,
  UserNotificationPrefs,
} from '@/types/notificationPrefs';

/**
 * `/users/{uid}/notifications` 실시간 구독.
 * 값 없으면 `{}` 로 콜백 (= 모든 알림 기본 허용).
 *
 * 권한: `/users/{uid}` 기본 rule 상 본인 read/write 허용. 서브 path `notifications`
 * 는 field 별 rule 없으므로 상속 — 본인 자유 read/write.
 */
export function subscribeNotificationPrefs(
  uid: string,
  onData: (prefs: UserNotificationPrefs) => void,
  onError?: (err: Error) => void,
): () => void {
  if (!isFirebaseConfigured()) {
    onData({});
    return () => {};
  }
  const path = `users/${uid}/notifications`;
  const unsubscribe = onValue(
    ref(db, path),
    (snap) => {
      const val = (snap.val() ?? {}) as UserNotificationPrefs;
      onData(val);
    },
    (err) => {
      console.error('[notificationPrefs] subscription error:', err);
      onError?.(err as Error);
    },
  );
  return unsubscribe;
}

/** 채널 on/off — 부분 업데이트 */
export async function setNotificationChannel(
  uid: string,
  channel: NotificationChannel,
  enabled: boolean,
): Promise<void> {
  if (!isFirebaseConfigured()) throw new Error('Firebase 미설정');
  await update(ref(db, `users/${uid}/notifications`), {
    [`channels/${channel}`]: enabled,
    updatedAt: Date.now(),
  });
}

/** 시나리오 on/off — 부분 업데이트 */
export async function setNotificationScenario(
  uid: string,
  scenario: NotificationEventType,
  enabled: boolean,
): Promise<void> {
  if (!isFirebaseConfigured()) throw new Error('Firebase 미설정');
  await update(ref(db, `users/${uid}/notifications`), {
    [`scenarios/${scenario}`]: enabled,
    updatedAt: Date.now(),
  });
}

/** 전체 수신 거부 — revokedAt = now (PIPA). */
export async function revokeAllNotifications(uid: string): Promise<void> {
  if (!isFirebaseConfigured()) throw new Error('Firebase 미설정');
  const now = Date.now();
  await update(ref(db, `users/${uid}/notifications`), {
    revokedAt: now,
    updatedAt: now,
  });
}

/** 전체 거부 해제 — revokedAt null 로 클리어. */
export async function restoreNotifications(uid: string): Promise<void> {
  if (!isFirebaseConfigured()) throw new Error('Firebase 미설정');
  await update(ref(db, `users/${uid}/notifications`), {
    revokedAt: null,
    updatedAt: Date.now(),
  });
}
