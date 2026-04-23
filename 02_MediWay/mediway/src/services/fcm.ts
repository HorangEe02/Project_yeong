import { ref, set } from 'firebase/database';
import { getToken } from 'firebase/messaging';
import {
  db,
  getMessagingInstance,
  isFirebaseConfigured,
} from '@/config/firebase';

/** RTDB key-safe token ID (마지막 20자 + 금지 문자 치환). */
export function fcmTokenId(token: string): string {
  return token.slice(-20).replace(/[^a-zA-Z0-9_-]/g, '_');
}

/**
 * FCM 토큰 획득 + `/user_fcm_tokens/{uid}/{tokenId}` 저장.
 *
 * 권한 거부·VAPID key 미설정·브라우저 미지원 모두 null 반환 (조용히 실패).
 * onQueueCall Cloud Function이 이 경로에서 토큰을 fetch해 Push 발송.
 */
export async function registerFcmToken(
  uid: string,
  vapidKeyOverride?: string,
): Promise<string | null> {
  if (!isFirebaseConfigured()) return null;
  if (typeof Notification === 'undefined') return null;

  try {
    const permission = await Notification.requestPermission();
    if (permission !== 'granted') return null;

    const messaging = await getMessagingInstance();
    if (!messaging) return null;

    const vapidKey = vapidKeyOverride ?? import.meta.env.VITE_FIREBASE_VAPID_KEY;
    if (!vapidKey) {
      console.warn('[fcm] VITE_FIREBASE_VAPID_KEY 미설정 — 토큰 발급 생략');
      return null;
    }

    const token = await getToken(messaging, { vapidKey });
    if (!token) return null;

    const tokenId = fcmTokenId(token);
    await set(ref(db, `user_fcm_tokens/${uid}/${tokenId}`), {
      token,
      createdAt: Date.now(),
      userAgent:
        typeof navigator !== 'undefined'
          ? navigator.userAgent.slice(0, 120)
          : '',
    });
    return token;
  } catch (e) {
    console.error('[fcm] registerFcmToken', e);
    return null;
  }
}
