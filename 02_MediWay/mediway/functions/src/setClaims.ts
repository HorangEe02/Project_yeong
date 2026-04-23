import * as admin from 'firebase-admin';
import { onCall, HttpsError } from 'firebase-functions/v2/https';

/**
 * MediWay Custom Claims payload (ID 토큰 페이로드에 주입됨).
 *
 * - RTDB Rules에서 `auth.token.role`, `auth.token.hospitalId`로 평가
 * - Admin SDK `setCustomUserClaims`로만 쓰기 가능
 * - 토큰 최대 1시간 캐시 — 클라이언트는 `getIdToken(true)`로 강제 갱신
 */
export interface MediwayClaims {
  role: string; // 'patient' | 'staff' | 'admin' | 'platformAdmin'
  hospitalId: string | null;
  hospitalIds: string[];
  claimsSetAt: number;
}

const region = 'asia-northeast3';

/**
 * 주어진 uid의 RTDB 프로필을 읽어 Custom Claims를 동기화.
 * - role: profile.role ?? 'patient'
 * - hospitalId: primaryHospitalId 우선, legacy hospitalId 차선
 * - hospitalIds: profile.hospitalIds ?? []
 *
 * ensureUserRecord, handleCreateStaff, refreshMyClaims, setUserClaims
 * 모두 이 헬퍼를 호출하여 일관성을 유지.
 */
export async function applyClaimsFromProfile(uid: string): Promise<MediwayClaims> {
  const snap = await admin.database().ref(`users/${uid}`).get();
  if (!snap.exists()) {
    throw new HttpsError('not-found', `유저 프로필 없음: ${uid}`);
  }
  const profile = snap.val() as {
    role?: string;
    primaryHospitalId?: string;
    hospitalId?: string;
    hospitalIds?: string[];
  };

  const claims: MediwayClaims = {
    role: profile.role ?? 'patient',
    hospitalId: profile.primaryHospitalId ?? profile.hospitalId ?? null,
    hospitalIds: profile.hospitalIds ?? [],
    claimsSetAt: Date.now(),
  };
  await admin.auth().setCustomUserClaims(uid, claims);
  return claims;
}

/**
 * `refreshMyClaims` — 로그인된 유저가 본인 claim을 최신화.
 *
 * 사용 시점:
 * - 가입 직후 (프로필 생성 완료 후)
 * - 병원 선택·전환 직후
 * - 클라이언트가 `getIdTokenResult()` 읽어 프로필과 불일치 감지 시
 */
export const refreshMyClaims = onCall(
  { region, cors: true },
  async (request) => {
    if (!request.auth?.uid) {
      throw new HttpsError('unauthenticated', '로그인이 필요합니다');
    }
    try {
      const claims = await applyClaimsFromProfile(request.auth.uid);
      return { claims, forceRefresh: true };
    } catch (err) {
      if (err instanceof HttpsError) throw err;
      console.error('[refreshMyClaims]', err);
      throw new HttpsError('internal', 'Claim 갱신에 실패했습니다');
    }
  },
);

/**
 * `setUserClaims` — platformAdmin이 임의 유저의 claim을 프로필 기반으로 재동기화.
 *
 * 사용 시점:
 * - 역할 승격·강등 직후 (RTDB 프로필 업데이트 후 claim도 따라가야 할 때)
 * - 긴급 권한 회수 (프로필에서 role 변경 → 이 함수로 claim 즉시 반영)
 *
 * 대상 유저 본인은 다음 `getIdToken(true)` 또는 claim TTL 만료 후 반영됨.
 */
export const setUserClaims = onCall(
  { region, cors: true },
  async (request) => {
    if (!request.auth?.uid) {
      throw new HttpsError('unauthenticated', '로그인이 필요합니다');
    }
    if (request.auth.token.role !== 'platformAdmin') {
      throw new HttpsError(
        'permission-denied',
        '플랫폼 관리자만 사용할 수 있습니다',
      );
    }

    const uid =
      typeof request.data?.uid === 'string' ? request.data.uid.trim() : '';
    if (!uid) {
      throw new HttpsError('invalid-argument', 'uid는 필수입니다');
    }

    try {
      const claims = await applyClaimsFromProfile(uid);
      // 감사 로그
      await admin
        .database()
        .ref('audit_logs')
        .push({
          actorUid: request.auth.uid,
          actorEmail: request.auth.token.email ?? null,
          action: 'user.claims.refresh',
          target: uid,
          meta: {
            role: claims.role,
            hospitalId: claims.hospitalId,
          },
          timestamp: Date.now(),
        });
      return { claims };
    } catch (err) {
      if (err instanceof HttpsError) throw err;
      console.error('[setUserClaims]', err);
      throw new HttpsError('internal', 'Claim 설정에 실패했습니다');
    }
  },
);
