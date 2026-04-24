import { onValue, ref, update } from 'firebase/database';
import { db, isFirebaseConfigured } from '@/config/firebase';
import type { UserPreferences } from '@/types/preferences';

/**
 * `/users/{uid}/preferences` 실시간 구독.
 * 값 없음 / 일부 필드만 존재 → `{}` 또는 부분 객체로 콜백.
 *
 * 권한: 본인 read/write 허용 (`/users/{uid}` 기본 rule 상속).
 */
export function subscribeUserPreferences(
  uid: string,
  onData: (prefs: UserPreferences) => void,
  onError?: (err: Error) => void,
): () => void {
  if (!isFirebaseConfigured()) {
    onData({});
    return () => {};
  }
  const path = `users/${uid}/preferences`;
  const unsubscribe = onValue(
    ref(db, path),
    (snap) => {
      const val = (snap.val() ?? {}) as UserPreferences;
      onData(val);
    },
    (err) => {
      console.error('[preferences] subscription error:', err);
      onError?.(err as Error);
    },
  );
  return unsubscribe;
}

/**
 * 고령자 모드 on/off 를 RTDB 에 기록.
 * 부분 업데이트 — `preferences/uiSenior` 필드만 갱신, 다른 preferences 유지.
 */
export async function setUiSenior(uid: string, value: boolean): Promise<void> {
  if (!isFirebaseConfigured()) throw new Error('Firebase 미설정');
  await update(ref(db, `users/${uid}`), {
    'preferences/uiSenior': value,
  });
}
