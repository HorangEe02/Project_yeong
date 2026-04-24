import * as admin from 'firebase-admin';
import { onCall, HttpsError } from 'firebase-functions/v2/https';

const region = 'asia-northeast3';
const PAGE_SIZE = 500;

interface VerifyResult {
  totalActive: number;
  withRoleClaim: number;
  missingRoleClaim: number;
  sampleMissingUids: string[];
  mismatchUids: Array<{ uid: string; rtdbRole: string; claimRole: string | null }>;
}

/**
 * 모든 활성 유저에 대해 `customClaims.role` 존재 여부 및 RTDB role과의 일치 여부를 점검.
 * Commit 9 마이그레이션 후 Commit 8 RTDB rules 배포 전 호출해 0 missing 확인.
 *
 * 호출 권한: `platformAdmin` 전용.
 * 반환: 전체 활성 유저 수 · claim 보유 수 · 누락 수 · 누락 sample 최대 50 · 불일치 최대 50.
 */
export const verifyMigration = onCall(
  { region, cors: true, timeoutSeconds: 540 },
  async (req) => {
    if (!req.auth?.uid) {
      throw new HttpsError('unauthenticated', '로그인이 필요합니다');
    }
    if (req.auth.token.role !== 'platformAdmin') {
      throw new HttpsError('permission-denied', 'platformAdmin 권한이 필요합니다');
    }

    const db = admin.database();
    const usersRoot = db.ref('users');

    const result: VerifyResult = {
      totalActive: 0,
      withRoleClaim: 0,
      missingRoleClaim: 0,
      sampleMissingUids: [],
      mismatchUids: [],
    };

    let lastKey: string | null = null;
    let keepGoing = true;

    while (keepGoing) {
      const q = lastKey
        ? usersRoot.orderByKey().startAfter(lastKey).limitToFirst(PAGE_SIZE)
        : usersRoot.orderByKey().limitToFirst(PAGE_SIZE);
      const pageSnap = await q.get();
      const page = pageSnap.val() as
        | Record<string, { status?: string; role?: string }>
        | null;
      if (!page) break;
      const entries = Object.entries(page);
      if (entries.length === 0) break;

      for (const [uid, profile] of entries) {
        lastKey = uid;
        if (profile?.status && profile.status !== 'active') continue;
        result.totalActive += 1;

        try {
          const user = await admin.auth().getUser(uid);
          const claimRole =
            (user.customClaims?.role as string | undefined) ?? null;
          if (claimRole) {
            result.withRoleClaim += 1;
            const rtdbRole = profile?.role ?? 'patient';
            if (claimRole !== rtdbRole && result.mismatchUids.length < 50) {
              result.mismatchUids.push({ uid, rtdbRole, claimRole });
            }
          } else {
            result.missingRoleClaim += 1;
            if (result.sampleMissingUids.length < 50) {
              result.sampleMissingUids.push(uid);
            }
          }
        } catch (err) {
          // Auth 계정 자체가 없는 orphan 프로필 — 누락으로 카운트
          result.missingRoleClaim += 1;
          if (result.sampleMissingUids.length < 50) {
            result.sampleMissingUids.push(`${uid} (auth lookup failed: ${err instanceof Error ? err.message : String(err)})`);
          }
        }
      }

      if (entries.length < PAGE_SIZE) keepGoing = false;
    }

    return {
      ...result,
      ready: result.missingRoleClaim === 0,
    };
  },
);
