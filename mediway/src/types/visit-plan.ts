/** 방문 계획 입력 주체 */
export type VisitPlanSource = 'patient' | 'staff' | 'admin';

/** 계획된 경유지 — 세션으로 승격 시 Waypoint로 변환됨 */
export interface PlannedWaypoint {
  poiId: string;
  note?: string;
}

/** 환자별 방문 계획 (RTDB: visit_plans/{uid}) */
export interface VisitPlan {
  uid: string;
  hospitalId?: string;
  waypoints: PlannedWaypoint[];
  source: VisitPlanSource;
  updatedBy: string;
  updatedAt: number;
  expiresAt: number;
  autoSendOptIn?: boolean;
}

/** 계획 생성/수정 입력 */
export interface SetVisitPlanInput {
  waypoints: PlannedWaypoint[];
  source: VisitPlanSource;
  hospitalId?: string;
  ttlMs?: number;
}

/** 기본 TTL — 24시간 */
export const DEFAULT_PLAN_TTL_MS = 24 * 60 * 60 * 1000;
