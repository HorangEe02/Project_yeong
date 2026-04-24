import { useEffect, useState } from 'react';
import { ref, serverTimestamp, set } from 'firebase/database';
import { db, isFirebaseConfigured } from '@/config/firebase';
import { requestNotificationPermission } from '@/services/notification';
import { useAuthStore } from '@/stores/authStore';

/**
 * HomeTab 등 진료 화면 진입 시 한 번 호출.
 *
 * 1. 알림 권한 요청 (이미 거부 상태면 재요청하지 않고 스킵)
 * 2. FCM 토큰 획득 (`requestNotificationPermission` 내부 처리)
 * 3. `/user_fcm_tokens/{uid}/{tokenKey}` 에 `{ token, createdAt }` 저장
 *    - `tokenKey` = FNV-1a 32-bit hex of token — 같은 브라우저 재방문 시 동일 key로 덮어씀
 *
 * 이미 저장에 성공한 `(uid, token)` 쌍은 모듈 scope의 Set에 기록 →
 * 탭 전환·컴포넌트 재마운트 시 네트워크 호출이 반복되지 않는다.
 *
 * 사용 예:
 * ```tsx
 * function HomeTab() {
 *   useFcmToken();
 *   return <div>...</div>;
 * }
 * ```
 */
interface UseFcmTokenOptions {
  /** false면 권한 요청과 토큰 저장을 모두 스킵. 기본 true. */
  enabled?: boolean;
}

interface UseFcmTokenReturn {
  fcmToken: string | null;
  permissionStatus: NotificationPermission | 'unsupported';
  error: string | null;
}

const persistedTokens = new Set<string>();

/** 테스트에서만 사용 — 모듈 scope dedup Set 초기화 */
export function __resetFcmTokenCache(): void {
  persistedTokens.clear();
}

/**
 * FCM 토큰을 path-safe 16자 이하의 key로 압축한다.
 * FNV-1a 32-bit → 8 hex. 단일 사용자의 N개 디바이스 기준 충돌 확률은 실질 0.
 */
export function hashTokenKey(token: string): string {
  let h = 0x811c9dc5;
  for (let i = 0; i < token.length; i++) {
    h ^= token.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return (h >>> 0).toString(16).padStart(8, '0');
}

/**
 * `/user_fcm_tokens/{uid}/{tokenKey}` 에 `{ token, createdAt }` 를 쓴다.
 * hook 밖(서비스·store)에서도 재사용 가능하도록 분리.
 * 이미 저장된 (uid, token) 쌍이면 네트워크 호출 없이 기존 key만 반환.
 */
export async function persistFcmToken(uid: string, token: string): Promise<string> {
  const tokenKey = hashTokenKey(token);
  const dedupKey = `${uid}:${token}`;
  if (persistedTokens.has(dedupKey)) return tokenKey;

  await set(ref(db, `user_fcm_tokens/${uid}/${tokenKey}`), {
    token,
    createdAt: serverTimestamp(),
  });
  persistedTokens.add(dedupKey);
  return tokenKey;
}

export function useFcmToken(options?: UseFcmTokenOptions): UseFcmTokenReturn {
  const enabled = options?.enabled ?? true;
  const user = useAuthStore((s) => s.user);
  const [fcmToken, setFcmToken] = useState<string | null>(null);
  const [permissionStatus, setPermissionStatus] = useState<NotificationPermission | 'unsupported'>(
    typeof Notification !== 'undefined' ? Notification.permission : 'unsupported',
  );
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!enabled) return;
    if (!user || user.isAnonymous) return;
    if (!isFirebaseConfigured()) return;
    if (typeof Notification === 'undefined') {
      setPermissionStatus('unsupported');
      return;
    }
    if (Notification.permission === 'denied') {
      setPermissionStatus('denied');
      return;
    }

    let cancelled = false;

    void (async () => {
      try {
        const token = await requestNotificationPermission();
        if (cancelled) return;
        setPermissionStatus(
          typeof Notification !== 'undefined' ? Notification.permission : 'unsupported',
        );
        if (!token) return;
        setFcmToken(token);
        await persistFcmToken(user.uid, token);
      } catch (err) {
        if (cancelled) return;
        const message = err instanceof Error ? err.message : 'unknown error';
        console.error('[useFcmToken] 저장 실패', err);
        setError(message);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [user, enabled]);

  return { fcmToken, permissionStatus, error };
}
