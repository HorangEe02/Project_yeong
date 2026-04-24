import { getToken, onMessage, type MessagePayload } from 'firebase/messaging';
import { getMessagingInstance, isFirebaseConfigured } from '@/config/firebase';

/** FCM 토큰 획득 (알림 권한 요청 포함) */
export async function requestNotificationPermission(): Promise<string | null> {
  if (!isFirebaseConfigured()) return null;

  try {
    const permission = await Notification.requestPermission();
    if (permission !== 'granted') {
      console.warn('[MediWay] 알림 권한이 거부되었습니다.');
      return null;
    }

    const messaging = await getMessagingInstance();
    if (!messaging) return null;

    const vapidKey = import.meta.env.VITE_FIREBASE_VAPID_KEY;
    const token = await getToken(messaging, { vapidKey });
    return token;
  } catch (error) {
    console.error('[MediWay] FCM 토큰 획득 실패:', error);
    return null;
  }
}

/** 포그라운드 메시지 수신 리스너 */
export async function onForegroundMessage(
  callback: (payload: MessagePayload) => void,
): Promise<(() => void) | null> {
  if (!isFirebaseConfigured()) return null;

  const messaging = await getMessagingInstance();
  if (!messaging) return null;

  const unsubscribe = onMessage(messaging, callback);
  return unsubscribe;
}

/** 인앱 토스트 알림 표시 (FCM 대체용 로컬 알림) */
export function showLocalNotification(title: string, body: string): void {
  // 브라우저 네이티브 알림 (포그라운드에서도 동작)
  if ('Notification' in window && Notification.permission === 'granted') {
    new Notification(title, {
      body,
      icon: '/favicon.svg',
      badge: '/favicon.svg',
    });
  }
}

/**
 * 동선 관련 알림 발송 헬퍼
 * Phase 1에서는 클라이언트 사이드 로컬 알림으로 구현
 * (프로덕션에서는 Cloud Functions 서버 사이드 FCM 발송 권장)
 */
export const NotificationMessages = {
  routeReceived: () =>
    showLocalNotification(
      'MediWay',
      '다음 목적지가 등록되었습니다. 안내를 확인해주세요.',
    ),
  nextDestination: (name: string) =>
    showLocalNotification(
      'MediWay',
      `다음 목적지 — ${name}`,
    ),
  allCompleted: () =>
    showLocalNotification(
      'MediWay',
      '오늘 진료가 모두 끝났습니다. 귀가하셔도 됩니다.',
    ),
};
