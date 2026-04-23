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
      host: process.env.RTDB_EMULATOR_HOST ?? '127.0.0.1',
      port: Number(process.env.RTDB_EMULATOR_PORT ?? 9000),
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

  // rules-unit-testing v5: database() 호출 시마다 useEmulator 중복 호출되어 FATAL.
  // context별 단일 db 인스턴스 캐싱으로 우회.
  const demoPatientDb = demoPatient.database();
  const demoStaffDb = demoStaff.database();
  const smchPatientDb = smchPatient.database();
  const platAdminDb = platAdmin.database();

  console.log('\n[Read tests]');

  await assertSucceeds(demoPatientDb.ref('hospitals/demo/profile').get())
    .then(() => pass('demo 환자 → demo profile 읽기'))
    .catch((e) => fail('demo 환자 → demo profile 읽기', e));

  await assertSucceeds(demoPatientDb.ref('hospitals/demo/pois').get())
    .then(() => pass('demo 환자 → demo pois 읽기'))
    .catch((e) => fail('demo 환자 → demo pois 읽기', e));

  // profile은 공개 읽기 (SelectHospitalPage를 위해)
  await assertSucceeds(demoPatientDb.ref('hospitals/smch/profile').get())
    .then(() => pass('demo 환자 → smch profile 읽기 (공개)'))
    .catch((e) => fail('demo 환자 → smch profile 읽기', e));

  // pois는 tenant-scoped → 차단
  await assertFails(demoPatientDb.ref('hospitals/smch/pois').get())
    .then(() => pass('demo 환자 → smch pois 읽기 차단 ★'))
    .catch((e) => fail('demo 환자 → smch pois 읽기 차단', e));

  // 교차 visit_plan
  await assertFails(
    demoPatientDb.ref('hospitals/smch/visit_plans/fake').get(),
  )
    .then(() => pass('demo 환자 → smch visit_plans 읽기 차단 ★'))
    .catch((e) => fail('demo 환자 → smch visit_plans 읽기 차단', e));

  // 같은 병원 내 staff이 다른 환자 plan 읽기
  await assertSucceeds(
    demoStaffDb.ref('hospitals/demo/visit_plans/user-a').get(),
  )
    .then(() => pass('demo staff → demo visit_plans/user-a 읽기'))
    .catch((e) => fail('demo staff → demo visit_plans/user-a 읽기', e));

  // 같은 병원 환자가 다른 환자 plan 읽기 — 차단
  await assertFails(
    smchPatientDb.ref('hospitals/demo/visit_plans/user-a').get(),
  )
    .then(() => pass('smch 환자 → demo visit_plans/user-a 차단 ★'))
    .catch((e) => fail('smch 환자 → demo visit_plans/user-a 차단', e));

  // platformAdmin은 아무 병원이나
  await assertSucceeds(
    platAdminDb.ref('hospitals/smch/pois').get(),
  )
    .then(() => pass('platformAdmin → smch pois 읽기'))
    .catch((e) => fail('platformAdmin → smch pois 읽기', e));

  console.log('\n[Write tests]');

  // 일반 유저 → profile 쓰기 차단
  await assertFails(
    demoPatientDb.ref('hospitals/demo/profile/themeColor')
      .set('#hack'),
  )
    .then(() => pass('demo 환자 → demo profile 쓰기 차단 ★'))
    .catch((e) => fail('demo 환자 → demo profile 쓰기 차단', e));

  // platformAdmin → profile 쓰기
  await assertSucceeds(
    platAdminDb.ref('hospitals/demo/profile/themeColor')
      .set('#009688'),
  )
    .then(() => pass('platformAdmin → demo profile 쓰기'))
    .catch((e) => fail('platformAdmin → demo profile 쓰기', e));

  // 레거시 visit_plans 쓰기 (P2까지 호환) — 본인 uid
  await assertSucceeds(
    demoPatientDb.ref('visit_plans/user-a').set({
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
    demoPatientDb.ref('hospitals/demo/visit_plans/other-uid').set({
      waypoints: { w1: { poiId: 'p1' } },
      source: 'patient',
      updatedBy: 'user-a',
      expiresAt: Date.now() + 86_400_000,
      hospitalId: 'demo',
    }),
  )
    .then(() => pass('demo 환자 → demo visit_plans/other-uid 쓰기 차단 ★'))
    .catch((e) => fail('demo 환자 → demo visit_plans/other-uid 쓰기 차단', e));

  console.log('\n[Appointments tests]');

  const future = Date.now() + 86_400_000;

  // 환자가 자기 병원 예약 생성
  await assertSucceeds(
    demoPatientDb.ref('hospitals/demo/appointments/appt-1').set({
      id: 'appt-1',
      hospitalId: 'demo',
      patientUid: 'user-a',
      department: '내과',
      scheduledAt: future,
      durationMin: 30,
      status: 'scheduled',
      createdAt: Date.now(),
      updatedAt: Date.now(),
    }),
  )
    .then(() => pass('demo 환자 → demo appointments 본인 예약 생성'))
    .catch((e) => fail('demo 환자 → demo appointments 본인 예약 생성', e));

  // 환자가 타 병원 예약 생성 차단 (hospitalId 불일치)
  await assertFails(
    demoPatientDb.ref('hospitals/smch/appointments/appt-x').set({
      id: 'appt-x',
      hospitalId: 'smch',
      patientUid: 'user-a',
      department: '내과',
      scheduledAt: future,
      durationMin: 30,
      status: 'scheduled',
      createdAt: Date.now(),
      updatedAt: Date.now(),
    }),
  )
    .then(() => pass('demo 환자 → smch appointments 생성 차단 ★'))
    .catch((e) => fail('demo 환자 → smch appointments 생성 차단', e));

  // 환자가 본인 예약 읽기
  await assertSucceeds(
    demoPatientDb.ref('hospitals/demo/appointments/appt-1').get(),
  )
    .then(() => pass('demo 환자 → 본인 appointments 읽기'))
    .catch((e) => fail('demo 환자 → 본인 appointments 읽기', e));

  // 같은 병원 staff이 해당 환자 예약 읽기
  await assertSucceeds(
    demoStaffDb.ref('hospitals/demo/appointments/appt-1').get(),
  )
    .then(() => pass('demo staff → demo appointments 읽기'))
    .catch((e) => fail('demo staff → demo appointments 읽기', e));

  // 환자가 역인덱스 본인 엔트리 쓰기
  await assertSucceeds(
    demoPatientDb.ref('hospitals/demo/appointments_by_patient/user-a/appt-1')
      .set({
        scheduledAt: future,
        status: 'scheduled',
      }),
  )
    .then(() => pass('demo 환자 → 역인덱스 본인 엔트리 쓰기'))
    .catch((e) => fail('demo 환자 → 역인덱스 본인 엔트리 쓰기', e));

  // 환자가 다른 환자 역인덱스 쓰기 차단
  await assertFails(
    demoPatientDb.ref('hospitals/demo/appointments_by_patient/other-uid/appt-z')
      .set({
        scheduledAt: future,
        status: 'scheduled',
      }),
  )
    .then(() => pass('demo 환자 → 다른 환자 역인덱스 차단 ★'))
    .catch((e) => fail('demo 환자 → 다른 환자 역인덱스 차단', e));

  // 과거 시각 scheduledAt 차단
  await assertFails(
    demoPatientDb.ref('hospitals/demo/appointments/appt-past').set({
      id: 'appt-past',
      hospitalId: 'demo',
      patientUid: 'user-a',
      department: '내과',
      scheduledAt: Date.now() - 2 * 86_400_000,
      durationMin: 30,
      status: 'scheduled',
      createdAt: Date.now(),
      updatedAt: Date.now(),
    }),
  )
    .then(() => pass('demo 환자 → 과거 시각 예약 validate 차단 ★'))
    .catch((e) => fail('demo 환자 → 과거 시각 예약 validate 차단', e));

  console.log('\n[Wait queue tests — P3 C2]');

  const today = new Date().toISOString().slice(0, 10);

  // ① 환자가 본인 병원 대기 entry 생성 (접수)
  await assertSucceeds(
    demoPatientDb.ref(`hospitals/demo/wait_queue/내과/${today}/entry-1`)
      .set({
        id: 'entry-1',
        hospitalId: 'demo',
        department: '내과',
        date: today,
        number: 1,
        patientUid: 'user-a',
        status: 'waiting',
        createdAt: Date.now(),
      }),
  )
    .then(() => pass('demo 환자 → 본인 wait_queue 생성 (접수)'))
    .catch((e) => fail('demo 환자 → 본인 wait_queue 생성', e));

  // ② 타 병원에 자기 entry 생성 차단 (hospitalId 불일치)
  await assertFails(
    demoPatientDb.ref(`hospitals/smch/wait_queue/내과/${today}/entry-x`)
      .set({
        id: 'entry-x',
        hospitalId: 'smch',
        department: '내과',
        date: today,
        number: 1,
        patientUid: 'user-a',
        status: 'waiting',
        createdAt: Date.now(),
      }),
  )
    .then(() => pass('demo 환자 → smch wait_queue 생성 차단 ★'))
    .catch((e) => fail('demo 환자 → smch wait_queue 생성 차단', e));

  // ③ 환자가 본인 entry 읽기
  await assertSucceeds(
    demoPatientDb.ref(`hospitals/demo/wait_queue/내과/${today}/entry-1`)
      .get(),
  )
    .then(() => pass('demo 환자 → 본인 wait_queue entry 읽기'))
    .catch((e) => fail('demo 환자 → 본인 wait_queue entry 읽기', e));

  // ④ 환자가 부서·date 전체 구독 차단 (본인 여부 무관하게 전체 노출 금지)
  await assertFails(
    demoPatientDb.ref(`hospitals/demo/wait_queue/내과/${today}`)
      .get(),
  )
    .then(() => pass('demo 환자 → 부서 전체 wait_queue 구독 차단 ★'))
    .catch((e) => fail('demo 환자 → 부서 전체 wait_queue 구독 차단', e));

  // ⑤ 의료진이 부서 전체 대기열 구독 허용
  await assertSucceeds(
    demoStaffDb.ref(`hospitals/demo/wait_queue/내과/${today}`)
      .get(),
  )
    .then(() => pass('demo staff → 부서 전체 wait_queue 구독'))
    .catch((e) => fail('demo staff → 부서 전체 wait_queue 구독', e));

  // ⑥ 환자가 다른 환자의 entry 생성 차단 (newData.patientUid !== auth.uid)
  await assertFails(
    demoPatientDb.ref(`hospitals/demo/wait_queue/내과/${today}/entry-spoof`)
      .set({
        id: 'entry-spoof',
        hospitalId: 'demo',
        department: '내과',
        date: today,
        number: 2,
        patientUid: 'other-uid',
        status: 'waiting',
        createdAt: Date.now(),
      }),
  )
    .then(() => pass('demo 환자 → 타 환자 wait_queue entry 생성 차단 ★'))
    .catch((e) => fail('demo 환자 → 타 환자 wait_queue entry 생성 차단', e));

  // ⑦ 환자가 본인 역인덱스 쓰기
  await assertSucceeds(
    demoPatientDb.ref(`hospitals/demo/wait_queue_by_patient/user-a/entry-1`)
      .set({
        department: '내과',
        date: today,
        number: 1,
        status: 'waiting',
      }),
  )
    .then(() => pass('demo 환자 → 본인 역인덱스 쓰기'))
    .catch((e) => fail('demo 환자 → 본인 역인덱스 쓰기', e));

  // ⑧ 환자가 counter 증가 (runTransaction의 단일 write 시뮬레이션)
  await assertSucceeds(
    demoPatientDb.ref(`hospitals/demo/wait_queue_counters/내과/${today}/current`)
      .set(5),
  )
    .then(() => pass('demo 환자 → counter current 증가 (enqueue)'))
    .catch((e) => fail('demo 환자 → counter current 증가', e));

  // ⑨ 타 병원 counter 차단
  await assertFails(
    demoPatientDb.ref(`hospitals/smch/wait_queue_counters/내과/${today}/current`)
      .set(1),
  )
    .then(() => pass('demo 환자 → smch counter 차단 ★'))
    .catch((e) => fail('demo 환자 → smch counter 차단', e));

  console.log('\n[FCM tokens tests — P3 C5]');

  const longToken =
    'fake-fcm-token-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';

  // ⓐ 본인 FCM 토큰 쓰기 허용
  await assertSucceeds(
    demoPatientDb.ref('user_fcm_tokens/user-a/tok1').set({
      token: longToken,
      createdAt: Date.now(),
      userAgent: 'Mozilla/5.0 test',
    }),
  )
    .then(() => pass('demo 환자 → 본인 fcm token 쓰기'))
    .catch((e) => fail('demo 환자 → 본인 fcm token 쓰기', e));

  // ⓑ 타 uid FCM 토큰 쓰기 차단
  await assertFails(
    demoPatientDb.ref('user_fcm_tokens/other-uid/tok1').set({
      token: longToken,
      createdAt: Date.now(),
      userAgent: 'hack',
    }),
  )
    .then(() => pass('demo 환자 → 타 uid fcm token 쓰기 차단 ★'))
    .catch((e) => fail('demo 환자 → 타 uid fcm token 쓰기 차단', e));

  // ⓒ 짧은 토큰 validate 차단
  await assertFails(
    demoPatientDb.ref('user_fcm_tokens/user-a/tok2').set({
      token: 'short',
      createdAt: Date.now(),
      userAgent: 'ua',
    }),
  )
    .then(() => pass('demo 환자 → 짧은 fcm token validate 차단 ★'))
    .catch((e) => fail('demo 환자 → 짧은 fcm token validate 차단', e));

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
