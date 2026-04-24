/**
 * 데모 병원용 샘플 계정 시드 스크립트.
 *   - admin 1명 (hospitalId=demo)
 *   - staff 7명 (각 부서별 1명)
 *
 * Auth 계정 + RTDB /users 프로필 + Custom Claims + /hospitals/demo/departments 시드.
 *
 * 사용법:
 *   GOOGLE_CLOUD_PROJECT=mediway-demo GOOGLE_CLOUD_QUOTA_PROJECT=mediway-demo \
 *     npx tsx scripts/seed-sample-accounts.ts
 *
 * 재실행: 이미 존재하는 이메일은 skip (status 리포트만).
 */

import * as admin from 'firebase-admin';

interface AccountSeed {
  email: string;
  displayName: string;
  role: 'admin' | 'staff';
  department?: string; // staff만
  hospitalId: string;
}

const HOSPITAL_ID = 'demo';
const DOMAIN = 'demo-hospital.test';

const DEPARTMENTS: Array<{ code: string; name: string }> = [
  { code: 'er', name: '응급의학과' },
  { code: 'im', name: '내과' },
  { code: 'gs', name: '외과' },
  { code: 'ped', name: '소아청소년과' },
  { code: 'os', name: '정형외과' },
  { code: 'fm', name: '가정의학과' },
  { code: 'rad', name: '영상의학과' },
];

const ACCOUNTS: AccountSeed[] = [
  {
    email: `admin@${DOMAIN}`,
    displayName: '데모 전체 관리자',
    role: 'admin',
    hospitalId: HOSPITAL_ID,
  },
  ...DEPARTMENTS.map((d) => ({
    email: `staff-${d.code}@${DOMAIN}`,
    displayName: `${d.name} 샘플 의료진`,
    role: 'staff' as const,
    department: d.name,
    hospitalId: HOSPITAL_ID,
  })),
];

const TEMP_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789';
const SYMBOLS = '!@#$%';

function generateTempPassword(): string {
  const nodeCrypto = require('crypto') as typeof import('crypto');
  const bytes = new Uint8Array(14);
  nodeCrypto.randomFillSync(bytes);
  let out = '';
  for (let i = 0; i < 12; i++) out += TEMP_ALPHABET[bytes[i] % TEMP_ALPHABET.length];
  out += SYMBOLS[bytes[12] % SYMBOLS.length];
  out += String(bytes[13] % 10);
  return out;
}

async function seedDepartments(db: admin.database.Database): Promise<void> {
  const ref = db.ref(`hospitals/${HOSPITAL_ID}/departments`);
  const existing = await ref.get();
  if (existing.exists()) {
    console.log(`[seed] /hospitals/${HOSPITAL_ID}/departments 이미 존재 — 유지`);
    return;
  }
  const payload: Record<string, { name: string; code: string; active: boolean }> = {};
  for (const d of DEPARTMENTS) {
    payload[d.code] = { name: d.name, code: d.code, active: true };
  }
  await ref.set(payload);
  console.log(`[seed] /hospitals/${HOSPITAL_ID}/departments 시드 완료 (${DEPARTMENTS.length}개)`);
}

async function ensureAccount(
  seed: AccountSeed,
): Promise<{ uid: string; email: string; tempPassword: string | null; action: string }> {
  const db = admin.database();
  const auth = admin.auth();

  // 1. 기존 이메일 검사
  try {
    const existing = await auth.getUserByEmail(seed.email);
    // 이미 존재 — 프로필과 claim만 재검증/업데이트
    const profileRef = db.ref(`users/${existing.uid}`);
    const now = Date.now();
    const profilePatch: Record<string, unknown> = {
      email: seed.email,
      displayName: seed.displayName,
      role: seed.role,
      status: 'active',
      hospitalId: seed.hospitalId,
      updatedAt: now,
    };
    if (seed.department) profilePatch.department = seed.department;
    const snap = await profileRef.get();
    if (snap.exists()) {
      await profileRef.update(profilePatch);
    } else {
      await profileRef.set({
        uid: existing.uid,
        providers: ['password'],
        createdAt: now,
        ...profilePatch,
      });
    }
    const claims = {
      role: seed.role,
      hospitalId: seed.hospitalId,
      hospitalIds: [seed.hospitalId],
      claimsSetAt: now,
    };
    await auth.setCustomUserClaims(existing.uid, claims);
    await db.ref('audit_logs').push({
      actorUid: 'seed-script',
      action: 'user.claims.seed.update',
      target: existing.uid,
      meta: { claims, email: seed.email },
      timestamp: now,
    });
    return {
      uid: existing.uid,
      email: seed.email,
      tempPassword: null,
      action: 'updated (이미 존재)',
    };
  } catch (err) {
    const code = (err as { code?: string }).code;
    if (code !== 'auth/user-not-found') {
      throw err;
    }
  }

  // 2. 신규 계정 생성
  const tempPassword = generateTempPassword();
  const user = await auth.createUser({
    email: seed.email,
    password: tempPassword,
    displayName: seed.displayName,
    emailVerified: true, // .test 도메인 검증 불가 → true로 설정해 로그인 즉시 가능
  });

  const now = Date.now();
  const profile: Record<string, unknown> = {
    uid: user.uid,
    email: seed.email,
    displayName: seed.displayName,
    role: seed.role,
    status: 'active',
    providers: ['password'],
    hospitalId: seed.hospitalId,
    createdAt: now,
    updatedAt: now,
  };
  if (seed.department) profile.department = seed.department;
  await db.ref(`users/${user.uid}`).set(profile);

  const claims = {
    role: seed.role,
    hospitalId: seed.hospitalId,
    hospitalIds: [seed.hospitalId],
    claimsSetAt: now,
  };
  await auth.setCustomUserClaims(user.uid, claims);

  await db.ref('audit_logs').push({
    actorUid: 'seed-script',
    action: 'user.claims.seed.create',
    target: user.uid,
    meta: { claims, email: seed.email, department: seed.department ?? null },
    timestamp: now,
  });

  return { uid: user.uid, email: seed.email, tempPassword, action: 'created' };
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

  console.log(`[seed] hospital=${HOSPITAL_ID} 샘플 계정 시드 시작 (총 ${ACCOUNTS.length}개)`);
  console.log('');

  await seedDepartments(db);
  console.log('');

  const results: Array<{ email: string; action: string; tempPassword: string | null; role: string; department?: string }> = [];
  for (const seed of ACCOUNTS) {
    try {
      const r = await ensureAccount(seed);
      results.push({
        email: r.email,
        action: r.action,
        tempPassword: r.tempPassword,
        role: seed.role,
        department: seed.department,
      });
      console.log(`[seed] ${r.email} — ${r.action}${r.tempPassword ? ` (pw=${r.tempPassword})` : ''}`);
    } catch (err) {
      console.error(`[seed] ${seed.email} FAILED:`, err);
      results.push({
        email: seed.email,
        action: `FAILED: ${err instanceof Error ? err.message : String(err)}`,
        tempPassword: null,
        role: seed.role,
        department: seed.department,
      });
    }
  }

  console.log('\n=== 시드 결과 ===');
  console.log('이메일 | role | department | 작업 | 임시 패스워드');
  console.log('---|---|---|---|---');
  for (const r of results) {
    console.log(
      `${r.email} | ${r.role} | ${r.department ?? '-'} | ${r.action} | ${r.tempPassword ?? '(이미 존재 or 실패)'}`,
    );
  }
  console.log('\n⚠️  임시 패스워드는 즉시 안전한 곳에 저장하고, 로그인 후 변경하세요.');
  process.exit(0);
}

main().catch((err) => {
  console.error('[seed] 치명적 오류:', err);
  process.exit(10);
});
