import { useEffect } from 'react';
import { useAuthStore } from '@/stores/authStore';
import { registerFcmToken } from '@/services/fcm';

/**
 * 로그인 사용자의 FCM 토큰을 자동 등록한다.
 * 권한/브라우저/VAPID 조건을 못 맞추면 조용히 skip (UX에 영향 없음).
 */
export function useFcmToken(): void {
  const uid = useAuthStore((s) => s.user?.uid);
  useEffect(() => {
    if (!uid) return;
    registerFcmToken(uid).catch((e) => {
      console.error('[useFcmToken]', e);
    });
  }, [uid]);
}
