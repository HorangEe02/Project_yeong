import * as admin from 'firebase-admin';
import { onCall, HttpsError } from 'firebase-functions/v2/https';
import { buildClaimsFromProfile } from '../setClaims';
import { appendAuditLog } from '../util/auditLog';

const region = 'asia-northeast3';
const PAGE_SIZE = 500;
const MIGRATION_VERSION = 'v1';

interface MigrationProgress {
  startedAt: number;
  lastKey: string | null;
  processed: number;
  migrated: number;
  skipped: number;
  failed: number;
  errors: Array<{ uid: string; error: string }>;
  finishedAt: number | null;
}

/**
 * 모든 활성 유저의 Custom Claims를 RTDB 프로필 기준으로 재주입하는 일괄 마이그레이션.
 * Commit 8 RTDB rules 배포 전 1회 실행 필수.
 *
 * 호출 권한: `platformAdmin` 전용.
 *   admin에게 허용하면 하위 admin이 자기 RTDB role을 platformAdmin으로 set(admin은 whitelist 우회 가능)
 *   한 뒤 migration으로 token을 승격시키는 공격 벡터가 열린다.
 *
 * 재개: 이전 실행이 중단되면 동일 `migrationId` 로 재호출. `/migrations/v1/{id}/progress` 에서 `lastKey` 를 이어 간다.
 * 멱등성: 동일 유저에게 setCustomUserClaims 반복 호출은 동일 결과(안전).
 */
export const migrateAllClaims = onCall(
  { region, cors: true, timeoutSeconds: 540 },
  async (req) => {
    if (!req.auth?.uid) {
      throw new HttpsError('unauthenticated', '로그인이 필요합니다');
    }
    if (req.auth.token.role !== 'platformAdmin') {
      throw new HttpsError('permission-denied', 'platformAdmin 권한이 필요합니다');
    }

    const data = (req.data ?? {}) as { migrationId?: string; dryRun?: boolean };
    const migrationId =
      typeof data.migrationId === 'string' && data.migrationId
        ? data.migrationId
        : String(Date.now());
    const dryRun = data.dryRun === true;

    const db = admin.database();
    const progressRef = db.ref(`migrations/${MIGRATION_VERSION}/${migrationId}/progress`);
    const existingSnap = await progressRef.get();

    const progress: MigrationProgress = existingSnap.exists()
      ? (existingSnap.val() as MigrationProgress)
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
      return { migrationId, alreadyCompleted: true, progress };
    }

    const usersRoot = db.ref('users');
    let lastKey = progress.lastKey;
    let keepGoing = true;

    while (keepGoing) {
      const q = lastKey
        ? usersRoot.orderByKey().startAfter(lastKey).limitToFirst(PAGE_SIZE)
        : usersRoot.orderByKey().limitToFirst(PAGE_SIZE);
      const pageSnap = await q.get();
      const page = pageSnap.val() as Record<string, { status?: string }> | null;
      if (!page) {
        keepGoing = false;
        break;
      }
      const entries = Object.entries(page);
      if (entries.length === 0) {
        keepGoing = false;
        break;
      }

      for (const [uid, profile] of entries) {
        try {
          if (profile?.status && profile.status !== 'active') {
            progress.skipped += 1;
          } else {
            const claims = await buildClaimsFromProfile(uid);
            if (!dryRun) {
              await admin.auth().setCustomUserClaims(uid, claims);
              await appendAuditLog(db, claims.hospitalId, {
                actorUid: req.auth.uid,
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
          progress.errors.push({
            uid,
            error: err instanceof Error ? err.message : String(err),
          });
        }
        progress.processed += 1;
        lastKey = uid;
      }

      progress.lastKey = lastKey;
      await progressRef.set(progress);

      if (entries.length < PAGE_SIZE) {
        keepGoing = false;
      }
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

    return { migrationId, dryRun, progress };
  },
);
