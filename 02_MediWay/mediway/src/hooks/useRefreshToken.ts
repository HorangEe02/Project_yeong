import { useCallback } from 'react';
import { getAuth } from 'firebase/auth';
import { httpsCallable } from 'firebase/functions';
import { functions } from '@/config/firebase';
import type { MediwayClaims } from '@/types/auth-claims';

/**
 * 서버에서 본인 Custom Claim을 최신화하고, 클라이언트 ID 토큰을 즉시 강제 갱신.
 *
 * 호출 시점:
 * - 가입 직후 (primaryHospitalId가 프로필에 세팅된 직후)
 * - 병원 선택·전환 직후
 * - 역할 변경 직후 (admin/staff 승격)
 *
 * 구현:
 * 1. `refreshMyClaims` Cloud Function 호출 → Admin SDK가 프로필 기반 claim 주입
 * 2. `currentUser.getIdToken(true)`로 토큰 강제 재발급 — claim 즉시 반영
 */
export function useRefreshToken() {
  return useCallback(async (): Promise<MediwayClaims | null> => {
    const auth = getAuth();
    const user = auth.currentUser;
    if (!user) {
      throw new Error('로그인이 필요합니다');
    }
    const callable = httpsCallable<
      void,
      { claims: MediwayClaims; forceRefresh: boolean }
    >(functions, 'refreshMyClaims');
    const result = await callable();
    await user.getIdToken(true);
    return result.data.claims;
  }, []);
}
