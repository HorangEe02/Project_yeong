/**
 * CLI 검증 러너 — Admin SDK로 모든 활성 유저의 customClaims.role 존재 여부 점검.
 * cli-migrate-claims.ts 실행 후 `ready: true` 달성 여부 확인용.
 *
 * 사용법:
 *   npx ts-node scripts/cli-verify-claims.ts
 */

import * as admin from 'firebase-admin';

const PAGE_SIZE = 500;

interface VerifyResult {
  totalActive: number;
  withRoleClaim: number;
  missingRoleClaim: number;
  sampleMissingUids: string[];
  mismatchUids: Array<{ uid: string; rtdbRole: string; claimRole: string | null }>;
  ready: boolean;
}

async function main() {
  admin.initializeApp({
    credential: admin.credential.applicationDefault(),
    databaseURL:
      process.env.FIREBASE_DATABASE_URL ??
      'https://mediway-demo-default-rtdb.firebaseio.com',
    projectId: process.env.GOOGLE_CLOUD_PROJECT ?? 'mediway-demo',
  });

  const db = admin.database();
  const usersRoot = db.ref('users');

  const result: VerifyResult = {
    totalActive: 0,
    withRoleClaim: 0,
    missingRoleClaim: 0,
    sampleMissingUids: [],
    mismatchUids: [],
    ready: false,
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
        const claimRole = (user.customClaims?.role as string | undefined) ?? null;
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
        result.missingRoleClaim += 1;
        if (result.sampleMissingUids.length < 50) {
          result.sampleMissingUids.push(
            `${uid} (auth lookup failed: ${err instanceof Error ? err.message : String(err)})`,
          );
        }
      }
    }

    if (entries.length < PAGE_SIZE) keepGoing = false;
  }

  result.ready = result.missingRoleClaim === 0;

  console.log('=== Claims Verification ===');
  console.log(`totalActive        : ${result.totalActive}`);
  console.log(`withRoleClaim      : ${result.withRoleClaim}`);
  console.log(`missingRoleClaim   : ${result.missingRoleClaim}`);
  console.log(`mismatches         : ${result.mismatchUids.length}`);
  console.log(`READY (Commit 8)   : ${result.ready ? '✅ YES' : '❌ NO'}`);

  if (result.sampleMissingUids.length > 0) {
    console.log('\n--- Missing UIDs (sample) ---');
    result.sampleMissingUids.forEach((u) => console.log(`  ${u}`));
  }
  if (result.mismatchUids.length > 0) {
    console.log('\n--- Claim vs RTDB role 불일치 (sample) ---');
    result.mismatchUids.forEach((m) =>
      console.log(`  ${m.uid}: rtdb=${m.rtdbRole} claim=${m.claimRole}`),
    );
  }

  process.exit(result.ready ? 0 : 2);
}

main().catch((err) => {
  console.error('[cli-verify] 치명적 오류:', err);
  process.exit(10);
});
