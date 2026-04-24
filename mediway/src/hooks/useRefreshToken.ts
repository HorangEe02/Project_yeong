import { useCallback } from 'react';
import { httpsCallable } from 'firebase/functions';
import { auth, functions, isFirebaseConfigured } from '@/config/firebase';

export interface MediwayClaimsPayload {
  role: string;
  hospitalId: string | null;
  hospitalIds: string[];
  claimsSetAt: number;
}

export interface RefreshClaimsResult {
  claims: MediwayClaimsPayload;
  forceRefresh: boolean;
}

/**
 * 현재 로그인 유저의 Custom Claims를 서버 프로필 기준으로 재동기화하고
 * ID 토큰을 즉시 강제 갱신한다. hook 외부(Store·Service)에서도 재사용 가능.
 */
export async function refreshMyClaims(): Promise<RefreshClaimsResult | null> {
  if (!isFirebaseConfigured()) return null;
  const user = auth.currentUser;
  if (!user) throw new Error('로그인이 필요합니다');

  const callable = httpsCallable<void, RefreshClaimsResult>(
    functions,
    'refreshMyClaims',
  );
  const result = await callable();
  await user.getIdToken(true);
  return result.data;
}

/**
 * React 컴포넌트에서 쓰는 hook 버전.
 * 동작은 `refreshMyClaims`와 동일하고 렌더 간 함수 참조만 안정적으로 유지한다.
 */
export function useRefreshToken(): () => Promise<RefreshClaimsResult | null> {
  return useCallback(() => refreshMyClaims(), []);
}

/** 현재 ID 토큰에 role claim이 실려 있는지 (AuthStore init에서 자동 갱신 판별용) */
export async function hasRoleClaim(): Promise<boolean> {
  if (!isFirebaseConfigured()) return true;
  const user = auth.currentUser;
  if (!user) return false;
  const tokenResult = await user.getIdTokenResult();
  return typeof tokenResult.claims.role === 'string';
}
