// firestore-equipment.ts — Phase 4: 685건 에러 이력 + 25 금형 Firestore 시드 유틸리티.
// 본선 시연 시 한 번 실행하여 Firestore 에 데이터 채움 (idempotent — 기존 데이터 있으면 skip).
// 컬렉션 구조:
//   /equipment_error_history/{auto_id}        — 685 docs
//   /equipment_molds/{mold_id}                — 25 docs
//
// 호출 예: window 콘솔에서 `seedEquipmentToFirestore()` 또는 admin UI 버튼.

import {
  collection,
  doc,
  getCountFromServer,
  serverTimestamp,
  writeBatch,
} from 'firebase/firestore';
import { firestore } from '@lib/firebase';

// ──────────────────────────────────────────────────────────────────
// Seed data generators
// ──────────────────────────────────────────────────────────────────

const EQUIPMENT_TYPES = ['프레스', '용접', 'CNC', '사출', '도장', '검사', '컨베이어'] as const;

const SEVERITY_DIST = [
  { sev: 'LOW', mttr_min: 10 },
  { sev: 'MEDIUM', mttr_min: 30 },
  { sev: 'HIGH', mttr_min: 120 },
  { sev: 'CRITICAL', mttr_min: 480 },
] as const;

const ERROR_NAMES_BY_TYPE: Record<string, string[]> = {
  프레스: ['베어링 마모', '가이드 핀 마모', '클러치 슬립', '구동축 진동', '전기 모터 이음', '유압 누수', '성형 불량'],
  용접: ['전극 마모', '와이어 끊김', '아크 불안', '스패터 과다', '전류 불안', '냉각수 부족'],
  CNC: ['공구 마모', '채터링', '치수 불량', '주축 진동', '냉각수 누수', '제어 신호 오류'],
  사출: ['플래시 발생', '쇼트샷', '게이트 막힘', '냉각 불균', '버닝 발생', '수축 불량'],
  도장: ['오렌지필', '핀홀', '색차 발생', '광택 불량', '먼지 부착', '흐름 자국'],
  검사: ['센서 오감지', '캘리브레이션 오류', '광원 변동', '데이터 누락', '통신 오류'],
  컨베이어: ['벨트 슬립', '롤러 마모', '속도 불안', '체인 늘어짐', '센서 오감지'],
};

const PART_NAMES = ['CCH-FR', 'OBC-RR', 'BUMPER', 'DOOR-IN', 'DOOR-OUT', 'EV-CASE', 'CCH-RR', '볼시트', '시트레일', '필러'];
const RISKS = ['LOW', 'MED', 'HIGH'] as const;

// 결정론적 PRNG (시드 기반) — 매 호출마다 동일한 데이터
function seededRandom(seed: number) {
  let s = seed;
  return () => {
    s = (s * 9301 + 49297) % 233280;
    return s / 233280;
  };
}

interface ErrorHistoryRecord {
  id: string;
  equipment_type: string;
  error_code: string;
  error_name: string;
  severity: string;
  mttr_minutes: number;
  occurred_at: number; // ms epoch
  resolved: boolean;
  cause: string;
  action: string;
}

function generateErrorHistory(): ErrorHistoryRecord[] {
  const rand = seededRandom(20260427);
  const records: ErrorHistoryRecord[] = [];
  const now = Date.now();
  const oneYearMs = 365 * 24 * 3600 * 1000;

  // 685건 = 7장비 × ~98건 (균등 분포)
  for (let i = 0; i < 685; i++) {
    const eqType = EQUIPMENT_TYPES[i % EQUIPMENT_TYPES.length];
    const errors = ERROR_NAMES_BY_TYPE[eqType];
    const errName = errors[Math.floor(rand() * errors.length)];
    const sevIdx = Math.min(Math.floor(rand() * 4), 3);
    const sev = SEVERITY_DIST[sevIdx];
    const mttr = sev.mttr_min + Math.floor(rand() * sev.mttr_min);
    const errCode = `E-${String(100 + (i % 200)).padStart(3, '0')}`;
    const occurred = now - Math.floor(rand() * oneYearMs);
    records.push({
      id: `EH-${String(i + 1).padStart(4, '0')}`,
      equipment_type: eqType,
      error_code: errCode,
      error_name: errName,
      severity: sev.sev,
      mttr_minutes: mttr,
      occurred_at: occurred,
      resolved: rand() > 0.05, // 95% 해결
      cause: `${errName} 누적`,
      action: `${eqType} ${errName.split(' ')[0]} 점검·교체`,
    });
  }
  return records;
}

interface MoldRecord {
  mold_id: string;
  part_name: string;
  current_shots: number;
  max_shots: number;
  life_percent: number;
  remaining_shots: number;
  risk_level: string;
  status: string;
  last_maintenance: number;
}

function generateMolds(): MoldRecord[] {
  const rand = seededRandom(20260428);
  const records: MoldRecord[] = [];
  const now = Date.now();
  for (let i = 1; i <= 25; i++) {
    const part = PART_NAMES[i % PART_NAMES.length];
    const max = [400000, 500000, 600000, 800000][Math.floor(rand() * 4)];
    const usage = rand();
    const current = Math.floor(max * usage);
    const lifePct = current / max;
    const risk: string = lifePct > 0.9 ? RISKS[2] : lifePct > 0.7 ? RISKS[1] : RISKS[0];
    records.push({
      mold_id: `MD-${String(i).padStart(3, '0')}`,
      part_name: part,
      current_shots: current,
      max_shots: max,
      life_percent: Math.round(lifePct * 1000) / 1000,
      remaining_shots: max - current,
      risk_level: risk,
      status: 'active',
      last_maintenance: now - Math.floor(rand() * 30 * 24 * 3600 * 1000),
    });
  }
  return records;
}

// ──────────────────────────────────────────────────────────────────
// Seed functions
// ──────────────────────────────────────────────────────────────────

export interface SeedResult {
  collection: string;
  written: number;
  skipped: boolean;
  reason?: string;
}

const ERROR_COLLECTION = 'equipment_error_history';
const MOLDS_COLLECTION = 'equipment_molds';

/** 에러 이력 685건을 Firestore 에 시드. 이미 데이터 있으면 skip. */
export async function seedErrorHistory(force = false): Promise<SeedResult> {
  if (!firestore) {
    return { collection: ERROR_COLLECTION, written: 0, skipped: true, reason: 'Firestore 미초기화' };
  }
  try {
    const col = collection(firestore, ERROR_COLLECTION);
    if (!force) {
      const snap = await getCountFromServer(col);
      if (snap.data().count > 0) {
        return {
          collection: ERROR_COLLECTION,
          written: 0,
          skipped: true,
          reason: `이미 ${snap.data().count}건 존재`,
        };
      }
    }

    const records = generateErrorHistory();
    // Firestore batch 한도 500개 — 2 chunks 로 분할
    const CHUNK = 400;
    let written = 0;
    for (let i = 0; i < records.length; i += CHUNK) {
      const batch = writeBatch(firestore);
      const slice = records.slice(i, i + CHUNK);
      for (const r of slice) {
        const ref = doc(col, r.id);
        batch.set(ref, { ...r, _seeded_at: serverTimestamp() });
      }
      await batch.commit();
      written += slice.length;
    }
    return { collection: ERROR_COLLECTION, written, skipped: false };
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    return { collection: ERROR_COLLECTION, written: 0, skipped: true, reason: msg };
  }
}

/** 금형 25기를 Firestore 에 시드. 이미 데이터 있으면 skip. */
export async function seedMolds(force = false): Promise<SeedResult> {
  if (!firestore) {
    return { collection: MOLDS_COLLECTION, written: 0, skipped: true, reason: 'Firestore 미초기화' };
  }
  try {
    const col = collection(firestore, MOLDS_COLLECTION);
    if (!force) {
      const snap = await getCountFromServer(col);
      if (snap.data().count > 0) {
        return {
          collection: MOLDS_COLLECTION,
          written: 0,
          skipped: true,
          reason: `이미 ${snap.data().count}건 존재`,
        };
      }
    }

    const records = generateMolds();
    const batch = writeBatch(firestore);
    for (const r of records) {
      const ref = doc(col, r.mold_id);
      batch.set(ref, { ...r, _seeded_at: serverTimestamp() });
    }
    await batch.commit();
    return { collection: MOLDS_COLLECTION, written: records.length, skipped: false };
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    return { collection: MOLDS_COLLECTION, written: 0, skipped: true, reason: msg };
  }
}

/** 에러 이력 + 금형 통합 시드. 본선 시연 사전 1회 실행. */
export async function seedEquipmentToFirestore(force = false): Promise<SeedResult[]> {
  const results = await Promise.all([seedErrorHistory(force), seedMolds(force)]);
  if (import.meta.env.DEV) {
    console.info('[firestore-equipment] seed result:', results);
  }
  return results;
}

// 개발 편의: window 에서 직접 호출 가능
if (typeof window !== 'undefined' && import.meta.env.DEV) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (window as any).__seedEquipment = seedEquipmentToFirestore;
}
