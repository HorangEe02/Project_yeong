import {
  ref,
  push,
  set,
  get,
  update,
  remove,
  query,
  orderByChild,
  equalTo,
  onValue,
  type Unsubscribe,
} from 'firebase/database';
import { db, isFirebaseConfigured } from '@/config/firebase';
import { appendAudit } from './auditLog';
import { isActiveStatus, type Visit, type VisitStatus } from '@/types/visit';

/**
 * 환자 visit (외래/입원 admission) CRUD + 실시간 구독.
 *
 * RTDB path: `/visits/{hospitalId}/{visitId}` (database.rules.json 정책 강제)
 *  - read: 환자 본인 / same-hospital staff·admin / platformAdmin
 *  - write: same-hospital admin / platformAdmin (환자·staff read-only)
 *  - validate: type/status enum, zone 1-50, hospitalId === $hospitalId
 *
 * Audit: visit.create / visit.update / visit.status.change / visit.delete
 */

export type VisitInput = Omit<Visit, 'visitId' | 'hospitalId' | 'createdAt' | 'updatedAt'>;

/**
 * 새 visit 생성. visitId 는 RTDB push key. hospitalId 는 slug 로 자동 주입.
 * 호출자는 admin/platformAdmin 권한 필요 (RTDB rules 강제).
 */
export async function createVisit(slug: string, input: VisitInput): Promise<string> {
  if (!isFirebaseConfigured()) throw new Error('Firebase not configured');
  const visitsRef = ref(db, `visits/${slug}`);
  const newRef = push(visitsRef);
  const visitId = newRef.key;
  if (!visitId) throw new Error('Failed to allocate visitId');
  const now = Date.now();
  const entry: Visit = {
    ...input,
    visitId,
    hospitalId: slug,
    createdAt: now,
    updatedAt: now,
  };
  await set(newRef, entry);
  await appendAudit(
    'visit.create',
    visitId,
    { type: input.type, status: input.status, patientUid: input.patientUid },
    slug,
  );
  return visitId;
}

/** Visit 부분 수정 + updatedAt 자동 갱신. */
export async function updateVisit(
  slug: string,
  visitId: string,
  partial: Partial<Visit>,
): Promise<void> {
  if (!isFirebaseConfigured()) return;
  const r = ref(db, `visits/${slug}/${visitId}`);
  const patch: Record<string, unknown> = { ...partial, updatedAt: Date.now() };
  await update(r, patch);
  await appendAudit('visit.update', visitId, { fields: Object.keys(partial) }, slug);
}

/**
 * Status 변경 + 시각 stamp 자동.
 *  - checked-in → checkedInAt 갱신
 *  - completed  → completedAt 갱신
 */
export async function updateVisitStatus(
  slug: string,
  visitId: string,
  status: VisitStatus,
): Promise<void> {
  if (!isFirebaseConfigured()) return;
  const now = Date.now();
  const r = ref(db, `visits/${slug}/${visitId}`);
  const patch: Record<string, unknown> = { status, updatedAt: now };
  if (status === 'checked-in') patch.checkedInAt = now;
  if (status === 'completed') patch.completedAt = now;
  await update(r, patch);
  await appendAudit('visit.status.change', visitId, { status }, slug);
}

/** Visit 삭제 (admin/platformAdmin only). */
export async function deleteVisit(slug: string, visitId: string): Promise<void> {
  if (!isFirebaseConfigured()) return;
  await remove(ref(db, `visits/${slug}/${visitId}`));
  await appendAudit('visit.delete', visitId, null, slug);
}

/**
 * 환자의 active visit 1건 실시간 구독.
 * active = status ∈ {checked-in, in-progress}.
 *  - 0건 → null
 *  - 1+ → 가장 최근 createdAt 1건 (다중 active 방어)
 */
export function subscribeActiveVisit(
  slug: string,
  patientUid: string,
  cb: (v: Visit | null) => void,
): Unsubscribe {
  if (!isFirebaseConfigured()) {
    cb(null);
    return () => {};
  }
  const q = query(
    ref(db, `visits/${slug}`),
    orderByChild('patientUid'),
    equalTo(patientUid),
  );
  return onValue(q, (snap) => {
    if (!snap.exists()) {
      cb(null);
      return;
    }
    let latest: Visit | null = null;
    snap.forEach((child) => {
      const v = child.val() as Visit;
      if (!isActiveStatus(v.status)) return;
      if (!latest || (v.createdAt ?? 0) > (latest.createdAt ?? 0)) latest = v;
    });
    cb(latest);
  });
}

/** 환자의 visit history (최신순). 옵션 limit 지정 가능. */
export async function listVisitsByPatient(
  slug: string,
  patientUid: string,
  opts?: { limit?: number },
): Promise<Visit[]> {
  if (!isFirebaseConfigured()) return [];
  const q = query(
    ref(db, `visits/${slug}`),
    orderByChild('patientUid'),
    equalTo(patientUid),
  );
  const snap = await get(q);
  if (!snap.exists()) return [];
  const out: Visit[] = [];
  snap.forEach((child) => {
    out.push(child.val() as Visit);
  });
  out.sort((a, b) => (b.createdAt ?? 0) - (a.createdAt ?? 0));
  return opts?.limit ? out.slice(0, opts.limit) : out;
}

/**
 * 부서/진료과 단위 일별 visits.
 * department 인덱스 없음 — 전체 fetch 후 in-memory filter (소규모 hospital 가정).
 * 데이터 ↑ 시 별도 인덱스 추가 검토 (별도 sprint).
 */
export async function listVisitsByDepartment(
  slug: string,
  dept: string,
  dateMs: number,
): Promise<Visit[]> {
  if (!isFirebaseConfigured()) return [];
  const snap = await get(ref(db, `visits/${slug}`));
  if (!snap.exists()) return [];
  const dayStart = new Date(dateMs).setHours(0, 0, 0, 0);
  const dayEnd = new Date(dateMs).setHours(23, 59, 59, 999);
  const out: Visit[] = [];
  snap.forEach((child) => {
    const v = child.val() as Visit;
    if (v.department !== dept) return;
    const created = v.createdAt ?? 0;
    if (created < dayStart || created > dayEnd) return;
    out.push(v);
  });
  out.sort((a, b) => (b.createdAt ?? 0) - (a.createdAt ?? 0));
  return out;
}
