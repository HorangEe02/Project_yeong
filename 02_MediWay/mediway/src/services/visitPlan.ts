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
import {
  DEFAULT_PLAN_TTL_MS,
  type PlannedWaypoint,
  type SetVisitPlanInput,
  type VisitPlan,
  type VisitPlanSource,
} from '@/types/visit-plan';

/**
 * RTDB에서 읽은 plan을 정규화한다.
 * Firebase RTDB는 array를 저장할 때 sparse·인덱스 비연속이면 object로 반환한다.
 * 호환을 위해 모든 read 경로에서 waypoints를 array로 강제한다.
 * (P4 QA에서 /account/visits 빈 화면(useMemo의 draft.map 호출 throw)으로 드러남)
 */
function normalizeWaypoints(raw: unknown): PlannedWaypoint[] {
  if (Array.isArray(raw)) return raw as PlannedWaypoint[];
  if (raw && typeof raw === 'object') {
    return Object.values(raw as Record<string, PlannedWaypoint>);
  }
  return [];
}

function normalizePlan(raw: VisitPlan | null): VisitPlan | null {
  if (!raw) return null;
  return { ...raw, waypoints: normalizeWaypoints(raw.waypoints) };
}

/** 계획 조회 (만료 여부와 무관하게 raw 반환, waypoints는 array 정규화) */
export async function getVisitPlan(uid: string): Promise<VisitPlan | null> {
  if (!isFirebaseConfigured()) return null;
  const snap = await get(ref(db, `visit_plans/${uid}`));
  if (!snap.exists()) return null;
  return normalizePlan(snap.val() as VisitPlan);
}

/** 계획 설정 — 24h 기본 TTL + 감사 로그(의료진/관리자 주체 시) */
export async function setVisitPlan(
  uid: string,
  input: SetVisitPlanInput,
): Promise<VisitPlan> {
  if (!isFirebaseConfigured()) throw new Error('Firebase 미설정');
  const user = auth.currentUser;
  if (!user) throw new Error('로그인이 필요합니다');

  validateWaypoints(input.waypoints);

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
  if (input.hospitalId) plan.hospitalId = input.hospitalId;

  await set(ref(db, `visit_plans/${uid}`), plan);

  if (input.source !== 'patient') {
    await appendAudit('visit_plan.set', uid, {
      source: input.source,
      waypointCount: plan.waypoints.length,
    });
  }
  return plan;
}

/** 계획 삭제 — 환자가 완료했거나 수동 초기화 */
export async function clearVisitPlan(uid: string): Promise<void> {
  if (!isFirebaseConfigured()) return;
  await remove(ref(db, `visit_plans/${uid}`));
  const actor = auth.currentUser;
  if (actor && actor.uid !== uid) {
    await appendAudit('visit_plan.clear', uid);
  }
}

/** 자동 전송 동의 토글 — 환자 본인만 */
export async function setAutoSendOptIn(
  uid: string,
  optIn: boolean,
): Promise<void> {
  if (!isFirebaseConfigured()) return;
  const user = auth.currentUser;
  if (!user || user.uid !== uid) {
    throw new Error('본인만 자동 전송 설정을 변경할 수 있습니다');
  }
  await update(ref(db, `visit_plans/${uid}`), {
    autoSendOptIn: optIn,
    updatedAt: Date.now(),
  });
}

/** 계획 실시간 구독 */
export function subscribeVisitPlan(
  uid: string,
  callback: (plan: VisitPlan | null) => void,
  onError?: (err: Error) => void,
): Unsubscribe {
  if (!isFirebaseConfigured()) {
    callback(null);
    return () => {};
  }
  return onValue(
    ref(db, `visit_plans/${uid}`),
    (snap) => {
      callback(
        snap.exists() ? normalizePlan(snap.val() as VisitPlan) : null,
      );
    },
    (err) => {
      // 권한 거부·네트워크 실패 시 호출. onError 미등록이면 무시되어 loading이
      // 영구 true가 되던 버그 (P4 QA에서 빈 /account/visits 화면으로 드러남).
      onError?.(err);
    },
  );
}

/** 만료 여부 — now 기준 expiresAt 지났는지 */
export function isPlanExpired(plan: VisitPlan | null, now = Date.now()): boolean {
  if (!plan) return true;
  return plan.expiresAt < now;
}

/** 유효 계획만 반환 (null or 만료되면 null) */
export async function getActiveVisitPlan(
  uid: string,
): Promise<VisitPlan | null> {
  const plan = await getVisitPlan(uid);
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
