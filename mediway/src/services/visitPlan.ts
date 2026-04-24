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
 * T1-2c cutover (2026-04-24 이후):
 *   - **authoritative path**: `/hospitals/{hospitalId}/visit_plans/{uid}`
 *   - legacy root `/visit_plans/{uid}` 는 rules 로 write:false, read:platformAdmin only
 *
 * hospitalId 해석 순서:
 *   1) 호출자 명시 값 (SetVisitPlanInput.hospitalId 등)
 *   2) 현재 로그인 사용자 본인 plan 이면 authStore.profile.hospitalId
 *   3) 위 둘 다 불가 → read 는 null 반환, write 는 throw
 */

const NESTED_PATH = (hid: string, uid: string) =>
  `hospitals/${hid}/visit_plans/${uid}`;

function resolveHospitalId(uid: string, hint?: string | null): string | null {
  if (hint && hint.trim()) return hint.trim();
  const state = useAuthStore.getState();
  if (state.user?.uid === uid) {
    const hid = state.profile?.hospitalId;
    if (hid && hid.trim()) return hid.trim();
  }
  return null;
}

function requireHospitalId(uid: string, hint?: string | null): string {
  const hid = resolveHospitalId(uid, hint);
  if (!hid) {
    throw new Error('병원 식별자를 확인할 수 없어 방문 계획을 저장할 수 없습니다');
  }
  return hid;
}

export async function getVisitPlan(
  uid: string,
  hospitalIdHint?: string | null,
): Promise<VisitPlan | null> {
  if (!isFirebaseConfigured()) return null;
  const hid = resolveHospitalId(uid, hospitalIdHint);
  if (!hid) return null;
  const snap = await get(ref(db, NESTED_PATH(hid, uid)));
  return snap.exists() ? (snap.val() as VisitPlan) : null;
}

export async function setVisitPlan(
  uid: string,
  input: SetVisitPlanInput,
): Promise<VisitPlan> {
  if (!isFirebaseConfigured()) throw new Error('Firebase 미설정');
  const user = auth.currentUser;
  if (!user) throw new Error('로그인이 필요합니다');

  validateWaypoints(input.waypoints);
  const hid = requireHospitalId(uid, input.hospitalId);

  const now = Date.now();
  const ttl = input.ttlMs ?? DEFAULT_PLAN_TTL_MS;
  const plan: VisitPlan = {
    uid,
    hospitalId: hid,
    waypoints: input.waypoints.map(sanitize),
    source: input.source,
    updatedBy: user.uid,
    updatedAt: now,
    expiresAt: now + ttl,
  };

  await set(ref(db, NESTED_PATH(hid, uid)), plan);

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

export async function clearVisitPlan(uid: string): Promise<void> {
  if (!isFirebaseConfigured()) return;
  const hid = resolveHospitalId(uid);
  if (!hid) return; // 해석 불가 시 no-op (레거시 삭제는 rules 로 이미 금지됨)
  await remove(ref(db, NESTED_PATH(hid, uid)));
  const actor = auth.currentUser;
  if (actor && actor.uid !== uid) {
    await appendAudit('visit_plan.clear', uid, undefined, hid);
  }
}

export async function setAutoSendOptIn(
  uid: string,
  optIn: boolean,
): Promise<void> {
  if (!isFirebaseConfigured()) return;
  const user = auth.currentUser;
  if (!user || user.uid !== uid) {
    throw new Error('본인만 자동 전송 설정을 변경할 수 있습니다');
  }
  const hid = requireHospitalId(uid);
  await update(ref(db, NESTED_PATH(hid, uid)), {
    autoSendOptIn: optIn,
    updatedAt: Date.now(),
  });
}

export function subscribeVisitPlan(
  uid: string,
  callback: (plan: VisitPlan | null) => void,
  hospitalIdHint?: string | null,
): Unsubscribe {
  if (!isFirebaseConfigured()) {
    callback(null);
    return () => {};
  }
  const hid = resolveHospitalId(uid, hospitalIdHint);
  if (!hid) {
    callback(null);
    return () => {};
  }
  return onValue(ref(db, NESTED_PATH(hid, uid)), (snap) => {
    callback(snap.exists() ? (snap.val() as VisitPlan) : null);
  });
}

export function isPlanExpired(plan: VisitPlan | null, now = Date.now()): boolean {
  if (!plan) return true;
  return plan.expiresAt < now;
}

export async function getActiveVisitPlan(
  uid: string,
  hospitalIdHint?: string | null,
): Promise<VisitPlan | null> {
  const plan = await getVisitPlan(uid, hospitalIdHint);
  return plan && !isPlanExpired(plan) ? plan : null;
}

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
