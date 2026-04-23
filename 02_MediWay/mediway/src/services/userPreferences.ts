import { ref, update } from 'firebase/database';
import { db, isFirebaseConfigured } from '@/config/firebase';
import type { UserPreferences } from '@/types/auth';

/**
 * 사용자 환경설정 서비스 — `/users/{uid}/preferences` 부분 업데이트.
 *
 * P2: largeUi (고령자 모드 토글)가 첫 consumer.
 * P3: notificationChannels, P5: language가 이어서 사용.
 */
export async function updatePreferences(
  uid: string,
  patch: Partial<UserPreferences>,
): Promise<void> {
  if (!isFirebaseConfigured()) {
    throw new Error('Firebase 미설정');
  }
  await update(ref(db, `users/${uid}/preferences`), patch);
  await update(ref(db, `users/${uid}`), { updatedAt: Date.now() });
}
