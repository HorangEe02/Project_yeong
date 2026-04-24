import {
  ref,
  get,
  set,
  remove,
  update,
  onValue,
  type Unsubscribe,
} from 'firebase/database';
import { auth, db, isFirebaseConfigured } from '@/config/firebase';
import { appendAudit } from '@/services/auditLog';
import { useAuthStore } from '@/stores/authStore';
import {
  DEFAULT_PLAN_TTL_MS,
  type PlannedWaypoint,
  type SetVisitPlanInput,
  type VisitPlan,
  type VisitPlanSource,
} from '@/types/visit-plan';

/**
 * T1-2b dual-write 단계 (2026-04-24 이후):
 *   - nested (authoritative): `/hospitals/{hospitalId}/visit_plans/{uid}`
 *   - legacy (transitional):  `/visit_plans/{uid}`
 *
 * hospitalId 해석 순서:
 *   1) 호출자가 명시한 값 (SetVisitPlanInput.hospitalId 등)
 *   2) 현재 로그인 사용자 본인 plan 이면 authStore.profile.hospitalId
 *   3) 위 둘 다 불가능하면 null → legacy-only write (전환 기간 안전장치)
 *
 * T1-2a 로 기존 legacy entries 를 nested 로 backfill 완료 후,
 * T1-2c 에서 legacy write 를 제거하고 rules 로 관대처리 차단한다.
 */

const LEGACY_PATH = (uid: string) => `visit_plans/${uid}`;
const NESTED_PATH = (hid: string, uid: string) =>
  `hospitals/${hid}/visit_plans/${uid}`;

/** uid 기준 hospitalId 해석. hint 우선 → 본인 profile → null. */
function resolveHospitalId(uid: string, hint?: string | null): string | null {
  if (hint && hint.trim()) return hint.trim();
  const state = useAuthStore.getState();
  if (state.user?.uid === uid) {
    const hid = state.profile?.hospitalId;
    if (hid && hid.trim()) return hid.trim();
  }
  return null;
}

/**
 * 계획 조회 — nested 우선 → legacy fallback.
 * hospitalId 해석 실패 시 legacy 만 조회.
 */
export async function getVisitPlan(
  uid: string,
  hospitalIdHint?: string | null,
): Promise<VisitPlan | null> {
  if (!isFirebaseConfigured()) return null;
  const hid = resolveHospitalId(uid, hospitalIdHint);
  if (hid) {
    const nested = await get(ref(db, NESTED_PATH(hid, uid)));
    if (nested.exists()) return nested.val() as VisitPlan;
  }
  const legacy = await get(ref(db, LEGACY_PATH(uid)));
  return legacy.exists() ? (legacy.val() as VisitPlan) : null;
}

/**
 * 계획 설정 (create or replace). dual-write:
 *   - nested 가 authoritative (hospitalId 해석 가능 시)
 *   - legacy 는 T1-2c 까지 transitional 유지
 * 감사 로그는 환자 본인 아닐 때만 기록.
 */
export async function setVisitPlan(
  uid: string,
  input: SetVisitPlanInput,
): Promise<VisitPlan> {
  if (!isFirebaseConfigured()) throw new Error('Firebase 미설정');
  const user = auth.currentUser;
  if (!user) throw new Error('로그인이 필요합니다');

  validateWaypoints(input.waypoints);

  const hid = resolveHospitalId(uid, input.hospitalId);
  const now = Date.now();
  const ttl = input.ttlMs ?? DEFAULT_PLAN_TTL_MS;
  const plan: VisitPlan = {
    uid,
    waypoints: input.waypoints.map(sanitize),
    source: input.source,
    updatedBy: user.uid,
    updatedAt: now,
    expiresAt: now + ttl,
  };
  if (hid) plan.hospitalId = hid;

  // dual-write: legacy + nested (nested 는 hid 가 있을 때만)
  const writes: Array<Promise<void>> = [
    set(ref(db, LEGACY_PATH(uid)), plan),
  ];
  if (hid) writes.push(set(ref(db, NESTED_PATH(hid, uid)), plan));
  await Promise.all(writes);

  if (input.source !== 'patient') {
    await appendAudit(
      'visit_plan.set',
      uid,
      { source: input.source, waypointCount: plan.waypoints.length },
      hid,
    );
  }
  return plan;
}

/** 계획 삭제 — dual-remove. */
export async function clearVisitPlan(uid: string): Promise<void> {
  if (!isFirebaseConfigured()) return;
  const hid = resolveHospitalId(uid);
  const removes: Array<Promise<void>> = [remove(ref(db, LEGACY_PATH(uid)))];
  if (hid) removes.push(remove(ref(db, NESTED_PATH(hid, uid))));
  await Promise.all(removes);

  const actor = auth.currentUser;
  if (actor && actor.uid !== uid) {
    await appendAudit('visit_plan.clear', uid, undefined, hid);
  }
}

/** 자동 전송 동의 토글 — dual-update (본인만). */
export async function setAutoSendOptIn(
  uid: string,
  optIn: boolean,
): Promise<void> {
  if (!isFirebaseConfigured()) return;
  const user = auth.currentUser;
  if (!user || user.uid !== uid) {
    throw new Error('본인만 자동 전송 설정을 변경할 수 있습니다');
  }
  const hid = resolveHospitalId(uid);
  const patch = { autoSendOptIn: optIn, updatedAt: Date.now() };
  const updates: Array<Promise<void>> = [update(ref(db, LEGACY_PATH(uid)), patch)];
  if (hid) updates.push(update(ref(db, NESTED_PATH(hid, uid)), patch));
  await Promise.all(updates);
}

/**
 * 계획 실시간 구독 — dual-subscribe.
 * nested 와 legacy 양쪽 수신 후 updatedAt 이 더 최신인 쪽을 emit.
 * (동점이면 nested 우선 — T1-2c 이후 legacy 는 write 금지되므로 유지되지 않는다.)
 */
export function subscribeVisitPlan(
  uid: string,
  callback: (plan: VisitPlan | null) => void,
  hospitalIdHint?: string | null,
): Unsubscribe {
  if (!isFirebaseConfigured()) {
    callback(null);
    return () => {};
  }
  let nestedPlan: VisitPlan | null = null;
  let legacyPlan: VisitPlan | null = null;
  const emit = () => {
    const n = nestedPlan?.updatedAt ?? 0;
    const l = legacyPlan?.updatedAt ?? 0;
    callback(n >= l ? nestedPlan : legacyPlan);
  };
  const hid = resolveHospitalId(uid, hospitalIdHint);
  const unsubLegacy = onValue(ref(db, LEGACY_PATH(uid)), (snap) => {
    legacyPlan = snap.exists() ? (snap.val() as VisitPlan) : null;
    emit();
  });
  if (!hid) {
    return unsubLegacy;
  }
  const unsubNested = onValue(ref(db, NESTED_PATH(hid, uid)), (snap) => {
    nestedPlan = snap.exists() ? (snap.val() as VisitPlan) : null;
    emit();
  });
  return () => {
    unsubLegacy();
    unsubNested();
  };
}

/** 만료 여부 — now 기준 expiresAt 지났는지 */
export function isPlanExpired(plan: VisitPlan | null, now = Date.now()): boolean {
  if (!plan) return true;
  return plan.expiresAt < now;
}

/** 유효 계획만 반환 (null or 만료되면 null) */
export async function getActiveVisitPlan(
  uid: string,
  hospitalIdHint?: string | null,
): Promise<VisitPlan | null> {
  const plan = await getVisitPlan(uid, hospitalIdHint);
  return plan && !isPlanExpired(plan) ? plan : null;
}

/** 자동 전송 가능 여부
 *  - 계획이 유효하고
 *  - 자동 전송 옵트인이 true 이며
 *  - source가 patient가 아님 (장난 방지)
 *  - hospitalId가 지정되어 있다면 병원 일치
 */
export function canAutoSend(
  plan: VisitPlan | null,
  currentHospitalId?: string,
  now = Date.now(),
): boolean {
  if (!plan || isPlanExpired(plan, now)) return false;
  if (!plan.autoSendOptIn) return false;
  if (plan.source === 'patient') return false;
  if (plan.hospitalId && currentHospitalId && plan.hospitalId !== currentHospitalId) {
    return false;
  }
  return true;
}

// ============================================================
// Validation
// ============================================================

const MAX_WAYPOINTS = 10;

function validateWaypoints(waypoints: PlannedWaypoint[]): void {
  if (!Array.isArray(waypoints) || waypoints.length === 0) {
    throw new Error('최소 1개 이상의 목적지가 필요합니다');
  }
  if (waypoints.length > MAX_WAYPOINTS) {
    throw new Error(`목적지는 최대 ${MAX_WAYPOINTS}개까지 가능합니다`);
  }
  for (const w of waypoints) {
    if (!w.poiId || typeof w.poiId !== 'string') {
      throw new Error('잘못된 poiId');
    }
  }
}

function sanitize(w: PlannedWaypoint): PlannedWaypoint {
  const out: PlannedWaypoint = { poiId: w.poiId };
  if (w.note) out.note = w.note.slice(0, 200);
  return out;
}

// 내부 유틸 — 다른 모듈에서 활용 가능
export function planToWaypoints(plan: VisitPlan): Array<{ poiId: string }> {
  return plan.waypoints.map((w) => ({ poiId: w.poiId }));
}

export function describePlanSource(source: VisitPlanSource): string {
  switch (source) {
    case 'patient':
      return '환자 본인 입력';
    case 'staff':
      return '의료진 배정';
    case 'admin':
      return '관리자 배정';
  }
}
