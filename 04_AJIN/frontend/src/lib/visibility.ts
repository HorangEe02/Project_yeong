// 가시성 3-Tier — 같은 부서/본부 vs 타 부서 vs INACTIVE
// FastAPI v3.0 visibility 정책 React 포팅

import type { MockEmployee } from '@api/mock/seed/employees';
import type { AuthUser } from '@store/auth';

export type VisibilityLevel = 'FULL' | 'PARTIAL' | 'HIDDEN';

export function determineVisibility(
  user: AuthUser | null,
  empHq: string,
  empTeam: string,
  empRoleName?: string,
): VisibilityLevel {
  if (empRoleName === 'INACTIVE') return 'HIDDEN';
  if (!user) return 'PARTIAL';
  // SYS_ADMIN / HR_ADMIN 은 모두 FULL
  if (user.role_level >= 5) return 'FULL';
  // 같은 본부(division) 또는 같은 팀 → FULL
  if (user.department === empTeam) return 'FULL';
  if ((user as { division?: string }).division === empHq) return 'FULL';
  return 'PARTIAL';
}

export function maskEmail(email: string, level: VisibilityLevel): string {
  if (level === 'FULL') return email;
  if (level === 'HIDDEN') return '';
  // PARTIAL: 앞 2자만 노출
  const [name, domain] = email.split('@');
  if (!name || !domain) return '***@***';
  const visible = name.slice(0, 2);
  return `${visible}${'*'.repeat(Math.max(name.length - 2, 1))}@***`;
}

export function maskPhone(phone: string, level: VisibilityLevel): string {
  if (level === 'FULL') return phone;
  if (level === 'HIDDEN') return '';
  return '***-****-****';
}

export interface FilteredEmployee extends MockEmployee {
  visibility: VisibilityLevel;
  emailMasked: string;
  phoneMasked: string;
  extMasked: string;
}

export function applyVisibility(
  employees: MockEmployee[],
  user: AuthUser | null,
): FilteredEmployee[] {
  return employees
    .map((e) => {
      const level = determineVisibility(user, e.hq, e.team);
      return {
        ...e,
        visibility: level,
        emailMasked: maskEmail(e.email, level),
        phoneMasked: maskPhone(e.mobile, level),
        extMasked: level === 'FULL' ? `#${e.ext}` : '#***',
      };
    })
    .filter((e) => e.visibility !== 'HIDDEN');
}
