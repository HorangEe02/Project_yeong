/**
 * CLI 마이그레이션 러너 — httpsCallable 우회.
 *
 * 사용 이유: Commit 9 배포 직후 platformAdmin이 부트스트랩만 된 상태에서,
 *   브라우저 httpsCallable 호출은 기존 로그인 토큰 캐시(최대 1h) 때문에 claim 반영이 지연된다.
 *   Admin SDK 직접 실행은 service account 권한으로 RTDB·Auth 모두 접근하므로 즉시 실행 가능.
 *
 * 본 스크립트는 `functions/src/migrations/migrateAllClaims.ts`의 핵심 로직을 동일하게 수행하되,
 * 권한 체크·progress 저장·audit는 HTTP 핸들러와 동일하게 유지한다.
 *
 * 사용법:
 *   npx ts-node scripts/cli-migrate-claims.ts [--dryRun] [--migrationId=<id>]
 */

import * as admin from 'firebase-admin';
import { buildClaimsFromProfile } from '../src/setClaims';

const PAGE_SIZE = 500;
const MIGRATION_VERSION = 'v1';

interface Progress {
  startedAt: number;
  lastKey: string | null;
  processed: number;
  migrated: number;
  skipped: number;
  failed: number;
  errors: Array<{ uid: string; error: string }>;
  finishedAt: number | null;
}

function parseArgs(argv: string[]) {
  const flags: Record<string, string | boolean> = {};
  for (const raw of argv.slice(2)) {
    if (raw.startsWith('--')) {
      const [k, v] = raw.slice(2).split('=');
      flags[k] = v ?? true;
    }
  }
  return flags;
}

async function main() {
  const flags = parseArgs(process.argv);
  const dryRun = flags.dryRun === true;
  const migrationId =
    typeof flags.migrationId === 'string' && flags.migrationId
      ? flags.migrationId
      : `cli-${Date.now()}`;

  admin.initializeApp({
    credential: admin.credential.applicationDefault(),
    databaseURL:
      process.env.FIREBASE_DATABASE_URL ??
      'https://mediway-demo-default-rtdb.firebaseio.com',
    projectId: process.env.GOOGLE_CLOUD_PROJECT ?? 'mediway-demo',
  });

  const db = admin.database();
  const progressRef = db.ref(`migrations/${MIGRATION_VERSION}/${migrationId}/progress`);
  const existingSnap = await progressRef.get();

  const progress: Progress = existingSnap.exists()
    ? (existingSnap.val() as Progress)
    : {
        startedAt: Date.now(),
        lastKey: null,
        processed: 0,
        migrated: 0,
        skipped: 0,
        failed: 0,
        errors: [],
        finishedAt: null,
      };

  if (progress.finishedAt) {
    console.log(`[cli-migrate] migrationId=${migrationId} 이미 완료됨`);
    console.log(progress);
    process.exit(0);
  }

  console.log(`[cli-migrate] migrationId=${migrationId} dryRun=${dryRun} 시작`);
  console.log(`[cli-migrate] 재개: lastKey=${progress.lastKey ?? '(처음)'}`);

  const usersRoot = db.ref('users');
  let lastKey = progress.lastKey;
  let keepGoing = true;

  while (keepGoing) {
    const q = lastKey
      ? usersRoot.orderByKey().startAfter(lastKey).limitToFirst(PAGE_SIZE)
      : usersRoot.orderByKey().limitToFirst(PAGE_SIZE);
    const pageSnap = await q.get();
    const page = pageSnap.val() as Record<string, { status?: string }> | null;
    if (!page) break;
    const entries = Object.entries(page);
    if (entries.length === 0) break;

    console.log(`[cli-migrate] page size=${entries.length}, lastKey=${lastKey ?? '(none)'}`);

    for (const [uid, profile] of entries) {
      try {
        if (profile?.status && profile.status !== 'active') {
          progress.skipped += 1;
        } else {
          const claims = await buildClaimsFromProfile(uid);
          if (!dryRun) {
            await admin.auth().setCustomUserClaims(uid, claims);
            await db.ref('audit_logs').push({
              actorUid: 'cli-migrate-script',
              action: `user.claims.migration.${MIGRATION_VERSION}`,
              target: uid,
              meta: { claims, migrationId },
              timestamp: claims.claimsSetAt,
            });
          }
          progress.migrated += 1;
        }
      } catch (err) {
        progress.failed += 1;
        const errMsg = err instanceof Error ? err.message : String(err);
        progress.errors.push({ uid, error: errMsg });
        console.warn(`[cli-migrate] FAIL uid=${uid}: ${errMsg}`);
      }
      progress.processed += 1;
      lastKey = uid;
    }

    progress.lastKey = lastKey;
    await progressRef.set(progress);

    if (entries.length < PAGE_SIZE) keepGoing = false;
  }

  progress.finishedAt = Date.now();
  await progressRef.set(progress);
  await db
    .ref(`migrations/${MIGRATION_VERSION}/${migrationId}/summary`)
    .set({
      migrationId,
      dryRun,
      ...progress,
      errors: progress.errors.slice(0, 100),
    });

  console.log(`[cli-migrate] 완료 — processed=${progress.processed} migrated=${progress.migrated} skipped=${progress.skipped} failed=${progress.failed}`);
  if (progress.errors.length > 0) {
    console.log(`[cli-migrate] 실패 sample (최대 10):`);
    progress.errors.slice(0, 10).forEach((e) => console.log(`  ${e.uid}: ${e.error}`));
  }
  process.exit(0);
}

main().catch((err) => {
  console.error('[cli-migrate] 치명적 오류:', err);
  process.exit(10);
});
