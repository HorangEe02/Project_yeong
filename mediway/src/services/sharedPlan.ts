import { ref, get, set, remove } from 'firebase/database';
import { auth, db, isFirebaseConfigured } from '@/config/firebase';
import { getActiveVisitPlan } from '@/services/visitPlan';
import type { SharedPlan, SharedPlanResult } from '@/types/shared-plan';
import { SHARE_CODE_LENGTH, SHARE_TTL_MS } from '@/types/shared-plan';

const CODE_ALPHABET = '23456789ABCDEFGHJKLMNPQRSTUVWXYZ'; // 혼동 문자 제외

/** 암호학적으로 안전한 6자리 공유 코드 생성 */
export function generateShareCode(): string {
  const buf = new Uint32Array(SHARE_CODE_LENGTH);
  crypto.getRandomValues(buf);
  let out = '';
  for (let i = 0; i < SHARE_CODE_LENGTH; i++) {
    out += CODE_ALPHABET[buf[i] % CODE_ALPHABET.length];
  }
  return out;
}

/**
 * 현재 로그인 사용자의 유효 계획을 공유 코드로 스냅샷.
 * source === 'patient' 이고 본인 계획일 때만 허용.
 */
export async function createShareCode(
  sharerName: string | null,
): Promise<SharedPlan> {
  if (!isFirebaseConfigured()) throw new Error('Firebase 미설정');
  const user = auth.currentUser;
  if (!user) throw new Error('로그인이 필요합니다');

  const plan = await getActiveVisitPlan(user.uid);
  if (!plan) throw new Error('공유할 유효한 방문 계획이 없습니다');
  if (plan.source !== 'patient') {
    throw new Error('본인이 직접 입력한 계획만 공유할 수 있습니다');
  }

  const now = Date.now();
  // 최대 3회 재시도: 극히 낮은 충돌 가능성 대비
  for (let attempt = 0; attempt < 3; attempt++) {
    const code = generateShareCode();
    const snapshot: SharedPlan = {
      code,
      uid: user.uid,
      snapshot: {
        waypoints: plan.waypoints.map((w) => ({ poiId: w.poiId })),
        hospitalId: plan.hospitalId,
        sharedAt: now,
        sharerName: sharerName ?? user.displayName ?? null,
      },
      expiresAt: now + SHARE_TTL_MS,
      createdAt: now,
    };
    try {
      const snap = await get(ref(db, `shared_plans/${code}`));
      if (snap.exists()) continue; // 충돌 — 재시도
      await set(ref(db, `shared_plans/${code}`), snapshot);
      return snapshot;
    } catch (err) {
      if (attempt === 2) throw err;
    }
  }
  throw new Error('공유 코드 생성 실패 — 잠시 후 다시 시도하세요');
}

/** 공유 코드로 계획 조회 (익명 포함 로그인 사용자) */
export async function getSharedPlan(code: string): Promise<SharedPlanResult> {
  if (!isFirebaseConfigured()) return { valid: false, reason: 'not_found' };
  const normalized = code.trim().toUpperCase();
  const snap = await get(ref(db, `shared_plans/${normalized}`));
  if (!snap.exists()) return { valid: false, reason: 'not_found' };
  const data = snap.val() as SharedPlan;
  if (data.expiresAt < Date.now()) {
    return { valid: false, reason: 'expired' };
  }
  return { valid: true, plan: data };
}

/** 공유 코드 폐기 (본인만) */
export async function revokeShareCode(code: string): Promise<void> {
  if (!isFirebaseConfigured()) return;
  await remove(ref(db, `shared_plans/${code.toUpperCase()}`));
}

export function buildShareUrl(code: string): string {
  const origin =
    typeof window !== 'undefined' ? window.location.origin : 'https://mediway-demo.web.app';
  return `${origin}/share/plan/${code}`;
}
