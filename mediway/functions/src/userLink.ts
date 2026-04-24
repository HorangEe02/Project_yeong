import * as admin from 'firebase-admin';
import type { SocialProvider } from './customToken';
import { injectClaimsForUid } from './setClaims';

/**
 * RTDB `users/{uid}` 레코드가 없으면 최초 생성.
 * 소셜 로그인은 모두 role=patient로 강제.
 * 프로필 반영 직후 Custom Claims도 주입 (로그인 후 RTDB 보안 규칙 즉시 적용 목적).
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

  // 프로필 준비가 끝난 뒤 claim 주입 — 실패는 로깅만 하고 로그인은 성공시킨다.
  await injectClaimsForUid(uid, 'ensureUserRecord');
}
