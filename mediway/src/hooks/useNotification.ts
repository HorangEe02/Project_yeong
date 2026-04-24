import { useEffect, useState } from 'react';
import { requestNotificationPermission, onForegroundMessage } from '@/services/notification';
import { isFirebaseConfigured } from '@/config/firebase';

interface UseNotificationReturn {
  /** FCM 토큰 (세션에 저장용) */
  fcmToken: string | null;
  /** 알림 권한 상태 */
  permissionStatus: NotificationPermission | 'unsupported';
  /** 알림 권한 요청 */
  requestPermission: () => Promise<void>;
}

export function useNotification(): UseNotificationReturn {
  const [fcmToken, setFcmToken] = useState<string | null>(null);
  const [permissionStatus, setPermissionStatus] = useState<NotificationPermission | 'unsupported'>(
    typeof Notification !== 'undefined' ? Notification.permission : 'unsupported',
  );

  const requestPermission = async () => {
    const token = await requestNotificationPermission();
    if (token) {
      setFcmToken(token);
      setPermissionStatus('granted');
    } else {
      setPermissionStatus(
        typeof Notification !== 'undefined' ? Notification.permission : 'unsupported',
      );
    }
  };

  // 포그라운드 메시지 리스너 등록
  useEffect(() => {
    if (!isFirebaseConfigured()) return;

    let cleanup: (() => void) | null = null;

    onForegroundMessage((payload) => {
      // 포그라운드에서는 인앱 토스트로 표시
      if (payload.notification) {
        const { title, body } = payload.notification;
        if (title && body && typeof Notification !== 'undefined' && Notification.permission === 'granted') {
          new Notification(title, { body, icon: '/favicon.svg' });
        }
      }
    }).then((unsub) => {
      cleanup = unsub;
    });

    return () => {
      cleanup?.();
    };
  }, []);

  return { fcmToken, permissionStatus, requestPermission };
}
