// Firebase Auth 자동 부트스트랩 — admin SDK 미사용 (옵션 B 유지)
// 첫 로그인: createUser → signIn / 두 번째부터: signIn 만
//
// 이메일 매핑: {employee_id.toLowerCase()}@ajin.local
// 비밀번호: 사용자 입력 그대로 사용
// 백엔드 JWT 와 병행 — Firebase Auth 실패 시 graceful degrade.

import {
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signOut,
  onAuthStateChanged,
  updatePassword,
  type User,
} from 'firebase/auth';
import { auth } from '@lib/firebase';

export function buildEmail(employeeId: string): string {
  return `${employeeId.toLowerCase()}@ajin.local`;
}

export interface FirebaseAuthResult {
  uid: string;
  isNewlyCreated: boolean;
}

/**
 * Firebase Auth 자동 부트스트랩.
 * - 1차: signInWithEmailAndPassword 시도
 * - 실패 (auth/user-not-found 또는 auth/invalid-credential) 시 createUser + 자동 로그인
 * - 다른 에러는 throw
 */
export async function ensureFirebaseUser(
  employeeId: string,
  password: string,
): Promise<FirebaseAuthResult> {
  if (!auth) {
    throw new Error('Firebase Auth not configured');
  }
  const email = buildEmail(employeeId);
  try {
    const cred = await signInWithEmailAndPassword(auth, email, password);
    return { uid: cred.user.uid, isNewlyCreated: false };
  } catch (e) {
    const code = (e as { code?: string })?.code;
    const isFirstLogin =
      code === 'auth/user-not-found' ||
      code === 'auth/invalid-credential' ||
      code === 'auth/invalid-login-credentials';
    if (isFirstLogin) {
      try {
        const cred = await createUserWithEmailAndPassword(auth, email, password);
        return { uid: cred.user.uid, isNewlyCreated: true };
      } catch (createErr) {
        // race: 다른 기기에서 이미 등록 → signIn 재시도
        const createCode = (createErr as { code?: string })?.code;
        if (createCode === 'auth/email-already-in-use') {
          const cred = await signInWithEmailAndPassword(auth, email, password);
          return { uid: cred.user.uid, isNewlyCreated: false };
        }
        throw createErr;
      }
    }
    throw e;
  }
}

/**
 * 비밀번호 변경 후 Firebase 비밀번호 동기화.
 * - 현재 로그인된 user 가 있으면 updatePassword 호출
 * - 미로그인 상태이면 ensureFirebaseUser 로 새 비밀번호로 부트스트랩
 */
export async function syncFirebasePassword(
  employeeId: string,
  newPassword: string,
): Promise<FirebaseAuthResult> {
  if (!auth) {
    throw new Error('Firebase Auth not configured');
  }
  const current = auth.currentUser;
  if (current) {
    try {
      await updatePassword(current, newPassword);
      return { uid: current.uid, isNewlyCreated: false };
    } catch (e) {
      // requires-recent-login 등 — fallthrough 후 ensureFirebaseUser 로 재처리
      if (import.meta.env.DEV) {
        console.warn('[Firebase Auth] updatePassword 실패, 재부트스트랩 시도:', e);
      }
    }
  }
  return ensureFirebaseUser(employeeId, newPassword);
}

export async function signOutFirebase(): Promise<void> {
  if (!auth) return;
  try {
    await signOut(auth);
  } catch (e) {
    if (import.meta.env.DEV) {
      console.warn('[Firebase Auth] signOut 실패:', e);
    }
  }
}

export function watchFirebaseUser(callback: (user: User | null) => void): () => void {
  if (!auth) return () => {};
  return onAuthStateChanged(auth, callback);
}

/**
 * 현재 Firebase 사용자의 ID Token 을 반환한다.
 * - 미로그인 또는 Firebase 미초기화 시 null
 * - 401 자동 복구 시 axios interceptor 가 호출하며 forceRefresh=true 권장
 */
export async function getFirebaseIdToken(forceRefresh = false): Promise<string | null> {
  if (!auth?.currentUser) return null;
  try {
    return await auth.currentUser.getIdToken(forceRefresh);
  } catch (e) {
    if (import.meta.env.DEV) {
      console.warn('[Firebase Auth] getIdToken 실패:', e);
    }
    return null;
  }
}

/** Firebase Auth 가 로그인 상태인지 동기 확인 (RequireAuth 가드용). */
export function hasFirebaseUser(): boolean {
  return Boolean(auth?.currentUser);
}
