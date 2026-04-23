#!/usr/bin/env -S npx tsx
/**
 * Phase 1 Commit 9 — 데모 병원 RTDB 마이그레이션 (1회성).
 *
 * 전환 내용:
 *   1. /hospitals/demo/profile           ← 프로필 신규
 *   2. /hospitals/demo/pois/{id}         ← src/data/hospital/pois.ts
 *   3. /hospitals/demo/floor-plans/{n}   ← src/data/hospital/floor-plans/*.ts
 *   4. /users/{uid}                       ← primaryHospitalId='demo', hospitalIds=['demo']
 *   5. /visit_plans/{uid}                 ← hospitalId='demo' 필드 주입
 *   (sessions는 이미 hospitalId 필수 필드라 스킵)
 *
 * 사용:
 *   export GOOGLE_APPLICATION_CREDENTIALS=~/path/to/service-account.json
 *   npx tsx scripts/migrate-demo-hospital.mts --dry-run
 *   npx tsx scripts/migrate-demo-hospital.mts --dry-run --step=2
 *   npx tsx scripts/migrate-demo-hospital.mts --commit
 *
 * 모든 step은 idempotent — 이미 존재하면 skip.
 * 실행 전 `firebase database:get / > backup.json`로 백업 필수.
 */

import admin from 'firebase-admin';
import { allPOIs } from '../src/data/hospital/pois';
import { floor1Data } from '../src/data/hospital/floor-plans/floor1';
import { floor2Data } from '../src/data/hospital/floor-plans/floor2';
import { floor3Data } from '../src/data/hospital/floor-plans/floor3';
import { floor4Data } from '../src/data/hospital/floor-plans/floor4';
import {
  DEFAULT_HOSPITAL_FEATURES,
  type HospitalProfile,
} from '../src/types/hospital';

// ============================================================================
// CLI 파싱
// ============================================================================

const args = new Set(process.argv.slice(2));
const dryRun = args.has('--dry-run');
const commit = args.has('--commit');
const stepArg =
  process.argv.slice(2).find((a) => a.startsWith('--step=')) ?? null;
const onlyStep = stepArg ? parseInt(stepArg.split('=')[1], 10) : null;

if (!dryRun && !commit) {
  console.error('에러: --dry-run 또는 --commit 중 하나는 필수입니다');
  process.exit(2);
}
if (dryRun && commit) {
  console.error('에러: --dry-run과 --commit은 동시 사용 불가');
  process.exit(2);
}

const MODE = dryRun ? 'DRY-RUN' : 'COMMIT';

// ============================================================================
// Firebase Admin 초기화
// ============================================================================

if (!process.env.GOOGLE_APPLICATION_CREDENTIALS) {
  console.error(
    '에러: GOOGLE_APPLICATION_CREDENTIALS 환경변수 필수 (서비스 계정 JSON 경로)',
  );
  process.exit(2);
}

const databaseURL = process.env.MEDIWAY_DB_URL ?? 'https://mediway-demo-default-rtdb.firebaseio.com';
admin.initializeApp({ databaseURL });
const db = admin.database();

console.log(`\n=== MediWay P1 마이그레이션 · ${MODE} ===`);
console.log(`대상 DB: ${databaseURL}`);
if (onlyStep) console.log(`단계 제한: step ${onlyStep}만 실행`);
console.log('');

// ============================================================================
// 헬퍼
// ============================================================================

type Counts = { wrote: number; skipped: number; errors: number };
const totals: Counts = { wrote: 0, skipped: 0, errors: 0 };

async function idempotentSet(
  path: string,
  value: unknown,
  counts: Counts,
): Promise<void> {
  const ref = db.ref(path);
  const snap = await ref.get();
  if (snap.exists()) {
    counts.skipped++;
    if (process.env.VERBOSE) console.log(`  · skip (exists) ${path}`);
    return;
  }
  if (dryRun) {
    counts.wrote++;
    console.log(`  ✎ would write ${path}`);
    return;
  }
  try {
    await ref.set(value);
    counts.wrote++;
    console.log(`  ✔ wrote ${path}`);
  } catch (err) {
    counts.errors++;
    console.error(`  ✗ ${path}: ${(err as Error).message}`);
  }
}

async function idempotentUpdate(
  path: string,
  patch: Record<string, unknown>,
  counts: Counts,
): Promise<void> {
  const ref = db.ref(path);
  const snap = await ref.get();
  if (!snap.exists()) {
    counts.skipped++;
    if (process.env.VERBOSE) console.log(`  · skip (not exists) ${path}`);
    return;
  }
  const current = snap.val() as Record<string, unknown>;
  const needsUpdate = Object.keys(patch).some(
    (k) => current[k] === undefined || current[k] === null,
  );
  if (!needsUpdate) {
    counts.skipped++;
    if (process.env.VERBOSE) console.log(`  · skip (already set) ${path}`);
    return;
  }
  if (dryRun) {
    counts.wrote++;
    console.log(`  ✎ would update ${path} with ${JSON.stringify(patch)}`);
    return;
  }
  try {
    await ref.update(patch);
    counts.wrote++;
    console.log(`  ✔ updated ${path}`);
  } catch (err) {
    counts.errors++;
    console.error(`  ✗ ${path}: ${(err as Error).message}`);
  }
}

function shouldRunStep(n: number): boolean {
  return onlyStep === null || onlyStep === n;
}

// ============================================================================
// Step 1 — /hospitals/demo/profile
// ============================================================================

async function step1_profile(): Promise<Counts> {
  const counts: Counts = { wrote: 0, skipped: 0, errors: 0 };
  if (!shouldRunStep(1)) return counts;
  console.log('Step 1 · /hospitals/demo/profile');

  const now = Date.now();
  const profile: HospitalProfile = {
    name: 'MediWay 데모 병원',
    slug: 'demo',
    themeColor: '#004e9f',
    contractStatus: 'active',
    features: {
      ...DEFAULT_HOSPITAL_FEATURES,
      // P1에서는 기본 기능만 활성화 — 후속 Phase가 개별 flag 활성
      appointments: false,
      checkup: false,
    },
    createdAt: now,
    updatedAt: now,
  };

  await idempotentSet('hospitals/demo/profile', profile, counts);
  return counts;
}

// ============================================================================
// Step 2 — POIs
// ============================================================================

async function step2_pois(): Promise<Counts> {
  const counts: Counts = { wrote: 0, skipped: 0, errors: 0 };
  if (!shouldRunStep(2)) return counts;
  console.log(`Step 2 · /hospitals/demo/pois (${allPOIs.length}개)`);

  for (const poi of allPOIs) {
    await idempotentSet(`hospitals/demo/pois/${poi.id}`, poi, counts);
  }
  return counts;
}

// ============================================================================
// Step 3 — Floor Plans
// ============================================================================

async function step3_floorPlans(): Promise<Counts> {
  const counts: Counts = { wrote: 0, skipped: 0, errors: 0 };
  if (!shouldRunStep(3)) return counts;
  console.log('Step 3 · /hospitals/demo/floor-plans (4개 층)');

  const entries = [
    [1, floor1Data],
    [2, floor2Data],
    [3, floor3Data],
    [4, floor4Data],
  ] as const;

  for (const [level, data] of entries) {
    await idempotentSet(`hospitals/demo/floor-plans/${level}`, data, counts);
  }
  return counts;
}

// ============================================================================
// Step 4 — Users backfill (primaryHospitalId + hospitalIds)
// ============================================================================

async function step4_usersBackfill(): Promise<Counts> {
  const counts: Counts = { wrote: 0, skipped: 0, errors: 0 };
  if (!shouldRunStep(4)) return counts;
  console.log('Step 4 · /users/{uid} primaryHospitalId 백필');

  const snap = await db.ref('users').get();
  if (!snap.exists()) {
    console.log('  · users 노드 없음 — 스킵');
    return counts;
  }

  const users = snap.val() as Record<
    string,
    {
      primaryHospitalId?: string;
      hospitalIds?: string[];
      hospitalId?: string;
      role?: string;
    }
  >;

  for (const [uid, profile] of Object.entries(users)) {
    // 이미 primaryHospitalId가 있으면 skip
    if (profile.primaryHospitalId) {
      counts.skipped++;
      continue;
    }
    const patch: Record<string, unknown> = {
      primaryHospitalId: 'demo',
      hospitalIds: profile.hospitalIds?.length ? profile.hospitalIds : ['demo'],
      updatedAt: Date.now(),
    };
    await idempotentUpdate(`users/${uid}`, patch, counts);
  }
  return counts;
}

// ============================================================================
// Step 5 — visit_plans backfill (legacy 경로에 hospitalId 필드 주입)
// ============================================================================

async function step5_visitPlansBackfill(): Promise<Counts> {
  const counts: Counts = { wrote: 0, skipped: 0, errors: 0 };
  if (!shouldRunStep(5)) return counts;
  console.log('Step 5 · /visit_plans/{uid} hospitalId 필드 백필');

  const snap = await db.ref('visit_plans').get();
  if (!snap.exists()) {
    console.log('  · visit_plans 노드 없음 — 스킵');
    return counts;
  }

  const plans = snap.val() as Record<string, { hospitalId?: string }>;
  for (const [uid, plan] of Object.entries(plans)) {
    if (plan.hospitalId) {
      counts.skipped++;
      continue;
    }
    await idempotentUpdate(
      `visit_plans/${uid}`,
      { hospitalId: 'demo', updatedAt: Date.now() },
      counts,
    );
  }
  return counts;
}

// ============================================================================
// 실행
// ============================================================================

(async () => {
  try {
    const results = [
      await step1_profile(),
      await step2_pois(),
      await step3_floorPlans(),
      await step4_usersBackfill(),
      await step5_visitPlansBackfill(),
    ];
    for (const c of results) {
      totals.wrote += c.wrote;
      totals.skipped += c.skipped;
      totals.errors += c.errors;
    }
    console.log('\n=== 요약 ===');
    console.log(`모드: ${MODE}`);
    console.log(`작성/예정: ${totals.wrote}`);
    console.log(`스킵(이미 존재): ${totals.skipped}`);
    console.log(`오류: ${totals.errors}`);
    if (dryRun) {
      console.log('\n※ DRY-RUN이므로 실제 쓰기는 일어나지 않았습니다.');
      console.log('  결과 확인 후 --commit으로 재실행하세요.');
    }
    process.exit(totals.errors > 0 ? 1 : 0);
  } catch (err) {
    console.error('치명적 오류:', err);
    process.exit(3);
  }
})();
