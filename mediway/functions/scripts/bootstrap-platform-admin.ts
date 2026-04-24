/**
 * 최초 platformAdmin 부트스트랩 스크립트.
 *
 * 실행 시점: Commit 9 배포 후, `migrateAllClaims` 호출 이전에 1회.
 *   platformAdmin이 0명인 상태에서는 migrateAllClaims를 호출할 주체가 없으므로
 *   이 스크립트를 Cloud Functions 환경(또는 service account가 로컬 구성된 환경)에서 실행하여
 *   Admin SDK로 최초 platformAdmin 1명을 직접 생성한다.
 *
 * 사용법:
 *   1. 서비스 계정 키 경로 또는 Application Default Credentials 구성
 *      (로컬: `gcloud auth application-default login` + `gcloud config set project mediway-demo`)
 *   2. 다음 명령 실행:
 *        ts-node functions/scripts/bootstrap-platform-admin.ts <target-uid> [--hospitalId=<id>]
 *      예: ts-node functions/scripts/bootstrap-platform-admin.ts ABC123xyz
 *
 * 결과:
 *   - `users/<uid>/role` 을 'platformAdmin'으로 설정 (RTDB)
 *   - `setCustomUserClaims` 로 동일한 role claim 주입 (Auth)
 *   - audit_logs에 기록
 *
 * 롤백:
 *   같은 스크립트를 `--revert` 플래그로 재실행하면 platformAdmin → admin으로 되돌림.
 */

import * as admin from 'firebase-admin';

function parseArgs(argv: string[]) {
  const positional: string[] = [];
  const flags: Record<string, string | boolean> = {};
  for (const raw of argv.slice(2)) {
    if (raw.startsWith('--')) {
      const [k, v] = raw.slice(2).split('=');
      flags[k] = v ?? true;
    } else {
      positional.push(raw);
    }
  }
  return { positional, flags };
}

async function main() {
  const { positional, flags } = parseArgs(process.argv);
  const targetUid = positional[0];
  if (!targetUid) {
    console.error('사용법: ts-node bootstrap-platform-admin.ts <uid> [--hospitalId=<id>] [--revert]');
    process.exit(1);
  }

  admin.initializeApp({
    credential: admin.credential.applicationDefault(),
    databaseURL:
      process.env.FIREBASE_DATABASE_URL ??
      'https://mediway-demo-default-rtdb.firebaseio.com',
    projectId: process.env.GOOGLE_CLOUD_PROJECT ?? 'mediway-demo',
  });

  const db = admin.database();
  const profileRef = db.ref(`users/${targetUid}`);
  const snap = await profileRef.get();
  if (!snap.exists()) {
    console.error(`[bootstrap] ERROR: users/${targetUid} 프로필이 존재하지 않습니다. 먼저 로그인하여 프로필을 생성하세요.`);
    process.exit(2);
  }
  const profile = snap.val() as { role?: string; hospitalId?: string };

  const revert = flags.revert === true;
  const nextRole = revert ? 'admin' : 'platformAdmin';
  const hospitalIdFlag = typeof flags.hospitalId === 'string' ? flags.hospitalId : profile.hospitalId ?? null;

  console.log(`[bootstrap] target=${targetUid} currentRole=${profile.role} → nextRole=${nextRole} hospitalId=${hospitalIdFlag ?? '(none)'}`);

  // RTDB 프로필 업데이트
  await profileRef.update({
    role: nextRole,
    hospitalId: hospitalIdFlag,
    updatedAt: Date.now(),
  });

  // Custom Claims 주입
  const claims = {
    role: nextRole,
    hospitalId: hospitalIdFlag,
    hospitalIds: [] as string[],
    claimsSetAt: Date.now(),
  };
  await admin.auth().setCustomUserClaims(targetUid, claims);

  // audit_logs
  await db.ref('audit_logs').push({
    actorUid: 'bootstrap-script',
    action: revert ? 'user.claims.bootstrap.revert' : 'user.claims.bootstrap.platformAdmin',
    target: targetUid,
    meta: { claims, previousRole: profile.role ?? null },
    timestamp: claims.claimsSetAt,
  });

  console.log('[bootstrap] 완료. 대상 유저는 다음 로그인 또는 refreshMyClaims 호출 시 platformAdmin 권한을 획득합니다.');
  console.log('[bootstrap] 대상 유저가 현재 로그인되어 있다면 수동으로 로그아웃 후 재로그인 안내하거나 토큰 1시간 만료를 대기하세요.');

  process.exit(0);
}

main().catch((err) => {
  console.error('[bootstrap] 실패:', err);
  process.exit(10);
});
