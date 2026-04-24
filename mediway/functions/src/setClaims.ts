import * as admin from 'firebase-admin';
import { onCall, HttpsError } from 'firebase-functions/v2/https';
import { z } from 'zod';

const region = 'asia-northeast3';

export interface MediwayClaims {
  role: string;
  hospitalId: string | null;
  hospitalIds: string[];
  claimsSetAt: number;
}

/**
 * RTDB `/users/{uid}` 프로필을 읽어 Firebase Custom Claims로 변환.
 * `primaryHospitalId`가 아직 스키마에 없으므로 `hospitalId` 단일 필드로 fallback.
 */
export async function buildClaimsFromProfile(uid: string): Promise<MediwayClaims> {
  const snap = await admin.database().ref(`users/${uid}`).get();
  if (!snap.exists()) {
    throw new HttpsError('not-found', '유저 프로필이 없습니다');
  }
  const profile = snap.val() as {
    role?: string;
    primaryHospitalId?: string;
    hospitalId?: string;
    hospitalIds?: string[];
  };
  return {
    role: profile.role ?? 'patient',
    hospitalId: profile.primaryHospitalId ?? profile.hospitalId ?? null,
    hospitalIds: Array.isArray(profile.hospitalIds) ? profile.hospitalIds : [],
    claimsSetAt: Date.now(),
  };
}

/**
 * 본인 RTDB 프로필 기반으로 Custom Claims 최신화.
 * 클라이언트에서 가입 직후, 병원 전환 직후 호출.
 */
export const refreshMyClaims = onCall({ region, cors: true }, async (req) => {
  if (!req.auth?.uid) {
    throw new HttpsError('unauthenticated', '로그인이 필요합니다');
  }
  const uid = req.auth.uid;
  const claims = await buildClaimsFromProfile(uid);
  await admin.auth().setCustomUserClaims(uid, claims);

  await admin.database().ref('audit_logs').push({
    actorUid: uid,
    action: 'user.claims.refresh',
    target: uid,
    meta: { claims },
    timestamp: claims.claimsSetAt,
  });

  return { claims, forceRefresh: true };
});

const SetUserClaimsInput = z.object({
  uid: z.string().min(1),
  role: z.enum(['patient', 'staff', 'admin', 'platformAdmin']),
  hospitalId: z.string().nullable().optional(),
  hospitalIds: z.array(z.string()).optional(),
  reason: z.string().max(500).optional(),
});

/**
 * 관리자(또는 platformAdmin)가 임의 유저의 claim을 직접 조작.
 * Commit 7 범위에서는 `role === 'admin'`도 허용 (plusultra_v2 §P1 Commit 7 리스크 1).
 * Commit 10+ 에서 `platformAdmin` 전용으로 좁힐 예정.
 */
export const setUserClaims = onCall({ region, cors: true }, async (req) => {
  if (!req.auth?.uid) {
    throw new HttpsError('unauthenticated', '로그인이 필요합니다');
  }
  const callerRole = req.auth.token.role as string | undefined;
  if (callerRole !== 'admin' && callerRole !== 'platformAdmin') {
    throw new HttpsError('permission-denied', '관리자 권한이 필요합니다');
  }

  const parsed = SetUserClaimsInput.safeParse(req.data);
  if (!parsed.success) {
    throw new HttpsError('invalid-argument', '요청 파라미터가 올바르지 않습니다');
  }
  const { uid, role, hospitalId, hospitalIds, reason } = parsed.data;

  // 권한 에스컬레이션 차단 — admin은 platformAdmin으로 승격시킬 수 없다.
  // platformAdmin은 오직 platformAdmin만 부여 가능 (Commit 10+에서 전용 경로로 분리 예정).
  if (role === 'platformAdmin' && callerRole !== 'platformAdmin') {
    throw new HttpsError(
      'permission-denied',
      'platformAdmin 권한은 platformAdmin만 부여할 수 있습니다',
    );
  }

  const beforeUser = await admin.auth().getUser(uid);
  const beforeClaims = (beforeUser.customClaims ?? null) as MediwayClaims | null;

  const nextClaims: MediwayClaims = {
    role,
    hospitalId: hospitalId ?? null,
    hospitalIds: hospitalIds ?? [],
    claimsSetAt: Date.now(),
  };
  await admin.auth().setCustomUserClaims(uid, nextClaims);

  await admin.database().ref('audit_logs').push({
    actorUid: req.auth.uid,
    actorEmail: req.auth.token.email ?? null,
    action: 'user.claims.setByAdmin',
    target: uid,
    meta: { before: beforeClaims, after: nextClaims, reason: reason ?? null },
    timestamp: nextClaims.claimsSetAt,
  });

  return { claims: nextClaims };
});

/**
 * 서버 측에서 직접 claim을 주입할 때 호출 (ensureUserRecord·adminCreateStaff 등).
 *
 * @param throwOnError 실패를 호출자에게 전파할지 여부.
 *   - `false` (기본): 로그인·가입 플로우(ensureUserRecord)처럼 즉시 재시도 경로가 있는 경우.
 *     클라이언트가 authStore init에서 `refreshMyClaims`로 자동 복구한다.
 *   - `true`: adminCreateStaff처럼 실패 시 호출자가 트랜잭션을 중단해야 하는 경우.
 *     claim 없이 계정이 남으면 staff 첫 로그인 시 RTDB 401이 확정되므로 반드시 throw.
 */
export async function injectClaimsForUid(
  uid: string,
  origin: 'ensureUserRecord' | 'adminCreateStaff',
  throwOnError: boolean = false,
): Promise<void> {
  try {
    const claims = await buildClaimsFromProfile(uid);
    await admin.auth().setCustomUserClaims(uid, claims);
    await admin.database().ref('audit_logs').push({
      actorUid: uid,
      action: 'user.claims.autoInject',
      target: uid,
      meta: { claims, origin },
      timestamp: claims.claimsSetAt,
    });
  } catch (err) {
    console.error(`[injectClaimsForUid:${origin}]`, err);
    if (throwOnError) throw err;
  }
}
