import type { ChangeGrade } from '@api/compliance';

export interface ComplianceGradeMeta {
  grade: ChangeGrade;
  className: string;
  labelKo: string;
  actionLabel: string;
  color: string;
  foreground: string;
}

export const COMPLIANCE_GRADE_META: Record<ChangeGrade, ComplianceGradeMeta> = {
  CRITICAL: {
    grade: 'CRITICAL',
    className: 'severity-critical',
    labelKo: '위급',
    actionLabel: '즉시',
    color: 'var(--hud-red, #C0392B)',
    foreground: '#fff',
  },
  HIGH: {
    grade: 'HIGH',
    className: 'severity-high',
    labelKo: '높음',
    actionLabel: '우선',
    color: 'var(--hud-orange, #E8A317)',
    foreground: '#111',
  },
  MEDIUM: {
    grade: 'MEDIUM',
    className: 'severity-medium',
    labelKo: '보통',
    actionLabel: '검토',
    color: 'var(--hud-yellow, #FCB132)',
    foreground: '#111',
  },
  LOW: {
    grade: 'LOW',
    className: 'severity-low',
    labelKo: '낮음',
    actionLabel: '모니터링',
    color: 'var(--hud-green, #2D8A4E)',
    foreground: '#fff',
  },
};

/** Normalize backend/user-provided grade values to the release risk ladder. */
export function normalizeComplianceGrade(value: string | null | undefined): ChangeGrade {
  const normalized = String(value ?? '').trim().toUpperCase();
  if (normalized === 'CRITICAL' || normalized === 'HIGH' || normalized === 'LOW') {
    return normalized;
  }
  return 'MEDIUM';
}

/** Return presentation metadata for a Feature D risk grade. */
export function getComplianceGradeMeta(value: string | null | undefined): ComplianceGradeMeta {
  return COMPLIANCE_GRADE_META[normalizeComplianceGrade(value)];
}
