/**
 * 환자 Visit (외래/입원 admission) 타입.
 * 본 모듈은 zod 의존성 없이 순수 타입만 정의 — runtime validation 은:
 *  - frontend form 레이어 (AdminVisitsPage)
 *  - 서버 RTDB rules `.validate` (database.rules.json `/hospitals/{hid}/visits`)
 *  - 또는 functions/ 측 zod (필요 시)
 *
 * RTDB path: `/hospitals/{hid}/visits/{visitId}`
 *
 * 기존 `/visit_plans` (waypoints 진료 동선) 와 별개 개념 — visit 는 admission/방문 record.
 */

export type VisitType = 'outpatient' | 'inpatient' | 'checkup' | 'emergency';

export type VisitStatus =
  | 'scheduled'    // 예약됨 (방문 전)
  | 'checked-in'   // 접수 완료
  | 'in-progress'  // 진료 중 / 입원 중
  | 'completed'    // 종료
  | 'cancelled';   // 취소

export interface Visit {
  visitId: string;
  patientUid: string;
  hospitalId: string;       // = HospitalShell.slug
  type: VisitType;
  status: VisitStatus;

  // 위치 — type 별 의미 분기
  zone: string;             // 외래/검진/응급: 대기실 또는 구역. 입원: ward+room 우선이라 보조 표시
  ward?: string;            // 입원만: 병동 (예: "3W")
  room?: string;            // 입원만: 병실 호수 (예: "302")
  bed?: string;             // 입원만: 침대 (예: "A")

  // 메타
  department?: string;      // ER / IM / GS / PED ... (외래/응급 시 강하게 권장)
  displayName?: string;     // 환자명 cache (RTDB join 회피)
  scheduledFor?: number;    // 예약 시각 (ms epoch)
  checkedInAt?: number;
  completedAt?: number;
  createdAt: number;
  updatedAt: number;
  createdBy: string;        // admin/staff uid
  notes?: string;           // 자유 메모 (max 500, frontend 측 form validation 으로 강제)
}

// ============================================================
// Type narrowing helpers
// ============================================================

export type OutpatientVisit = Visit & { type: 'outpatient'; department: string };
export type InpatientVisit = Visit & { type: 'inpatient'; ward: string; room: string };
export type CheckupVisit = Visit & { type: 'checkup' };
export type EmergencyVisit = Visit & { type: 'emergency'; department: string };

export function isOutpatientVisit(v: Visit): v is OutpatientVisit {
  return v.type === 'outpatient' && typeof v.department === 'string';
}

export function isInpatientVisit(v: Visit): v is InpatientVisit {
  return (
    v.type === 'inpatient' &&
    typeof v.ward === 'string' &&
    typeof v.room === 'string'
  );
}

export function isCheckupVisit(v: Visit): v is CheckupVisit {
  return v.type === 'checkup';
}

export function isEmergencyVisit(v: Visit): v is EmergencyVisit {
  return v.type === 'emergency' && typeof v.department === 'string';
}

// ============================================================
// Status helpers
// ============================================================

/** active = checked-in 또는 in-progress (환자가 현재 진료/입원 중). */
export function isActiveStatus(s: VisitStatus): boolean {
  return s === 'checked-in' || s === 'in-progress';
}

// ============================================================
// Form validation 메타 — AdminVisitsPage 에서 type 별 필수 필드 강제.
// ============================================================

export const VISIT_TYPE_REQUIRED_FIELDS: Readonly<Record<VisitType, readonly string[]>> =
  Object.freeze({
    outpatient: Object.freeze(['patientUid', 'zone', 'department']),
    inpatient: Object.freeze(['patientUid', 'ward', 'room']),
    checkup: Object.freeze(['patientUid', 'zone']),
    emergency: Object.freeze(['patientUid', 'zone', 'department']),
  });

export const VISIT_NOTES_MAX_LENGTH = 500;
