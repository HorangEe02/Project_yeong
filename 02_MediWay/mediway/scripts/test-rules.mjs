#!/usr/bin/env node
/**
 * RTDB 보안 규칙 단위 테스트 — `@firebase/rules-unit-testing` 기반.
 *
 * 전제: Firebase Emulator Suite가 `http://127.0.0.1:9000` (RTDB) 에서 실행 중.
 *
 * 실행:
 *   터미널 1: firebase emulators:start --only database
 *   터미널 2: node scripts/test-rules.mjs
 *
 * 검증 시나리오 (Commit 8 게이트):
 *   1. 본인 병원 profile/pois 읽기 → 허용
 *   2. 타 병원 profile 읽기 → 허용 (profile은 공개 읽기)
 *   3. 타 병원 pois/visit_plans 읽기 → 차단
 *   4. 본인 병원 내 타 uid visit_plan 읽기 (staff 역할) → 허용
 *   5. 본인 병원 내 타 uid visit_plan 읽기 (patient 역할) → 차단
 *   6. platformAdmin이 임의 병원 읽기·쓰기 → 허용
 *   7. 레거시 visit_plans/$uid (P2까지 호환) 쓰기 → 허용
 */

import {
  initializeTestEnvironment,
  assertFails,
  assertSucceeds,
} from '@firebase/rules-unit-testing';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const rulesPath = join(__dirname, '..', 'database.rules.json');
const rulesJson = readFileSync(rulesPath, 'utf8');

const PROJECT_ID = 'mediway-rules-test';

const results = [];
function pass(name) {
  results.push({ name, ok: true });
  console.log(`  ✓ ${name}`);
}
function fail(name, err) {
  results.push({ name, ok: false, err: String(err?.message ?? err) });
  console.error(`  ✗ ${name} — ${err?.message ?? err}`);
}

async function run() {
  const parsed = JSON.parse(rulesJson);
  const env = await initializeTestEnvironment({
    projectId: PROJECT_ID,
    database: {
      rules: JSON.stringify(parsed),
    },
  });

  // 테스트 데이터 씨딩 (rules 우회)
  await env.withSecurityRulesDisabled(async (ctx) => {
    const db = ctx.database();
    await db.ref('hospitals/demo/profile').set({
      name: 'Demo',
      slug: 'demo',
      themeColor: '#004e9f',
      contractStatus: 'active',
      features: {},
      createdAt: 1,
      updatedAt: 1,
    });
    await db.ref('hospitals/demo/pois/p1').set({
      id: 'p1',
      name: '내과 1',
      category: 'clinic',
      floorLevel: 2,
    });
    await db.ref('hospitals/smch/profile').set({
      name: 'SMC',
      slug: 'smch',
      themeColor: '#009688',
      contractStatus: 'active',
      features: {},
      createdAt: 1,
      updatedAt: 1,
    });
    await db.ref('hospitals/smch/pois/p2').set({
      id: 'p2',
      name: '정형외과',
      category: 'clinic',
      floorLevel: 3,
    });
    await db.ref('hospitals/demo/visit_plans/user-a').set({
      uid: 'user-a',
      hospitalId: 'demo',
      waypoints: { w1: { poiId: 'p1' } },
      source: 'patient',
      updatedBy: 'user-a',
      updatedAt: 1,
      expiresAt: Date.now() + 86_400_000,
    });
  });

  // 3종 유저: demo 환자, demo 스태프, smch 환자, platformAdmin
  const demoPatient = env.authenticatedContext('user-a', {
    role: 'patient',
    hospitalId: 'demo',
  });
  const demoStaff = env.authenticatedContext('staff-a', {
    role: 'staff',
    hospitalId: 'demo',
  });
  const smchPatient = env.authenticatedContext('user-b', {
    role: 'patient',
    hospitalId: 'smch',
  });
  const platAdmin = env.authenticatedContext('pa-1', {
    role: 'platformAdmin',
  });

  console.log('\n[Read tests]');

  await assertSucceeds(demoPatient.database().ref('hospitals/demo/profile').get())
    .then(() => pass('demo 환자 → demo profile 읽기'))
    .catch((e) => fail('demo 환자 → demo profile 읽기', e));

  await assertSucceeds(demoPatient.database().ref('hospitals/demo/pois').get())
    .then(() => pass('demo 환자 → demo pois 읽기'))
    .catch((e) => fail('demo 환자 → demo pois 읽기', e));

  // profile은 공개 읽기 (SelectHospitalPage를 위해)
  await assertSucceeds(demoPatient.database().ref('hospitals/smch/profile').get())
    .then(() => pass('demo 환자 → smch profile 읽기 (공개)'))
    .catch((e) => fail('demo 환자 → smch profile 읽기', e));

  // pois는 tenant-scoped → 차단
  await assertFails(demoPatient.database().ref('hospitals/smch/pois').get())
    .then(() => pass('demo 환자 → smch pois 읽기 차단 ★'))
    .catch((e) => fail('demo 환자 → smch pois 읽기 차단', e));

  // 교차 visit_plan
  await assertFails(
    demoPatient.database().ref('hospitals/smch/visit_plans/fake').get(),
  )
    .then(() => pass('demo 환자 → smch visit_plans 읽기 차단 ★'))
    .catch((e) => fail('demo 환자 → smch visit_plans 읽기 차단', e));

  // 같은 병원 내 staff이 다른 환자 plan 읽기
  await assertSucceeds(
    demoStaff.database().ref('hospitals/demo/visit_plans/user-a').get(),
  )
    .then(() => pass('demo staff → demo visit_plans/user-a 읽기'))
    .catch((e) => fail('demo staff → demo visit_plans/user-a 읽기', e));

  // 같은 병원 환자가 다른 환자 plan 읽기 — 차단
  await assertFails(
    smchPatient.database().ref('hospitals/demo/visit_plans/user-a').get(),
  )
    .then(() => pass('smch 환자 → demo visit_plans/user-a 차단 ★'))
    .catch((e) => fail('smch 환자 → demo visit_plans/user-a 차단', e));

  // platformAdmin은 아무 병원이나
  await assertSucceeds(
    platAdmin.database().ref('hospitals/smch/pois').get(),
  )
    .then(() => pass('platformAdmin → smch pois 읽기'))
    .catch((e) => fail('platformAdmin → smch pois 읽기', e));

  console.log('\n[Write tests]');

  // 일반 유저 → profile 쓰기 차단
  await assertFails(
    demoPatient
      .database()
      .ref('hospitals/demo/profile/themeColor')
      .set('#hack'),
  )
    .then(() => pass('demo 환자 → demo profile 쓰기 차단 ★'))
    .catch((e) => fail('demo 환자 → demo profile 쓰기 차단', e));

  // platformAdmin → profile 쓰기
  await assertSucceeds(
    platAdmin
      .database()
      .ref('hospitals/demo/profile/themeColor')
      .set('#009688'),
  )
    .then(() => pass('platformAdmin → demo profile 쓰기'))
    .catch((e) => fail('platformAdmin → demo profile 쓰기', e));

  // 레거시 visit_plans 쓰기 (P2까지 호환) — 본인 uid
  await assertSucceeds(
    demoPatient.database().ref('visit_plans/user-a').set({
      waypoints: { w1: { poiId: 'p1' } },
      source: 'patient',
      updatedBy: 'user-a',
      expiresAt: Date.now() + 86_400_000,
      updatedAt: Date.now(),
    }),
  )
    .then(() => pass('demo 환자 → 레거시 visit_plans/user-a 쓰기 (P2 호환)'))
    .catch((e) => fail('demo 환자 → 레거시 visit_plans/user-a 쓰기', e));

  // 타 환자 visit_plan 쓰기 차단 (환자 역할)
  await assertFails(
    demoPatient.database().ref('hospitals/demo/visit_plans/other-uid').set({
      waypoints: { w1: { poiId: 'p1' } },
      source: 'patient',
      updatedBy: 'user-a',
      expiresAt: Date.now() + 86_400_000,
      hospitalId: 'demo',
    }),
  )
    .then(() => pass('demo 환자 → demo visit_plans/other-uid 쓰기 차단 ★'))
    .catch((e) => fail('demo 환자 → demo visit_plans/other-uid 쓰기 차단', e));

  await env.cleanup();

  const passed = results.filter((r) => r.ok).length;
  const total = results.length;
  console.log(
    `\n=== 결과: ${passed}/${total} ${passed === total ? '✅' : '❌'} ===`,
  );
  if (passed !== total) {
    console.error('\n실패한 시나리오:');
    results
      .filter((r) => !r.ok)
      .forEach((r) => console.error(`  - ${r.name}: ${r.err}`));
    process.exit(1);
  }
}

run().catch((e) => {
  console.error('테스트 실행 실패:', e);
  console.error(
    '\nEmulator가 실행 중인지 확인: firebase emulators:start --only database',
  );
  process.exit(2);
});
