import * as admin from 'firebase-admin';
import type { SocialProvider } from './customToken';
import { applyClaimsFromProfile } from './setClaims';

/**
 * RTDB `users/{uid}` 레코드가 없으면 최초 생성.
 * 소셜 로그인은 모두 role=patient로 강제.
 *
 * P1: 레코드 작성 후 자동으로 Custom Claims 주입 —
 * 클라이언트의 첫 `getIdToken(true)` 호출 시점에 page-level 인증이 완전 작동.
 */
export async function ensureUserRecord(
  uid: string,
  provider: SocialProvider,
  email: string | null,
  displayName: string | null,
): Promise<void> {
  const ref = admin.database().ref(`users/${uid}`);
  const snap = await ref.get();
  if (snap.exists()) {
    // 최신 메타만 반영
    await ref.update({
      email: email ?? snap.child('email').val() ?? null,
      displayName: displayName ?? snap.child('displayName').val() ?? null,
      updatedAt: Date.now(),
    });
  } else {
    const now = Date.now();
    await ref.set({
      uid,
      email,
      displayName,
      role: 'patient',
      status: 'active',
      providers: [provider],
      createdAt: now,
      updatedAt: now,
    });
  }

  // 프로필 작성·갱신 직후 Claim 동기화 — 실패해도 레코드 생성 자체는 유지
  try {
    await applyClaimsFromProfile(uid);
  } catch (err) {
    console.warn('[ensureUserRecord] claim 동기화 실패 (non-fatal)', uid, err);
  }
}
