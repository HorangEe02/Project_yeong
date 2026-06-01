// 알람 도메인 타입 + presentation 라벨.
// v4.2 M3 — `@api/mock/seed/alarms` 에서 분리. 더 이상 mock 이 아닌 presentation 타입.

import { COMPLIANCE_GRADE_META } from '@lib/complianceSeverity';
import type { ChangeGrade } from '@api/compliance';

export type AlarmSeverity = ChangeGrade;

export interface Alarm {
  id: string;
  severity: AlarmSeverity;
  title: string;
  detail: string;
  module: 'A' | 'B' | 'C' | 'D' | 'E' | 'F';
  timestamp: string;
  acknowledged: boolean;
}

export const SEVERITY_LABEL: Record<AlarmSeverity, { ko: string; en: string; color: string }> = {
  CRITICAL: { ko: '위급', en: 'CRITICAL', color: COMPLIANCE_GRADE_META.CRITICAL.color },
  HIGH: { ko: '높음', en: 'HIGH', color: COMPLIANCE_GRADE_META.HIGH.color },
  MEDIUM: { ko: '보통', en: 'MEDIUM', color: COMPLIANCE_GRADE_META.MEDIUM.color },
  LOW: { ko: '낮음', en: 'LOW', color: COMPLIANCE_GRADE_META.LOW.color },
};
