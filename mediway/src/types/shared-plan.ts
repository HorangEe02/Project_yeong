import type { PlannedWaypoint } from '@/types/visit-plan';

/** 공유된 방문 계획 스냅샷 (RTDB: shared_plans/{code}) */
export interface SharedPlan {
  code: string;
  uid: string; // 공유한 원작성자 (감사용)
  snapshot: {
    waypoints: PlannedWaypoint[];
    hospitalId?: string;
    sharedAt: number;
    sharerName: string | null;
  };
  expiresAt: number;
  createdAt: number;
}

/** 공유 조회 결과 */
export type SharedPlanResult =
  | { valid: true; plan: SharedPlan }
  | { valid: false; reason: 'not_found' | 'expired' };

export const SHARE_TTL_MS = 30 * 60 * 1000; // 30분
export const SHARE_CODE_LENGTH = 6;
