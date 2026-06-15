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

// F5 — 마스킹 정책 완화 (2026-05-10 합의):
//   사내 협업 자산(내선/이메일)은 PARTIAL 등급에서도 공개. 개인 휴대폰만 마스킹.
//   인사팀 별도 운영 정책에 따른 결정.
export function maskEmail(email: string, level: VisibilityLevel): string {
  if (level === 'HIDDEN') return '';
  // PARTIAL/FULL 모두 사내 이메일 공개
  return email;
}

export function maskPhone(phone: string, level: VisibilityLevel): string {
  if (level === 'FULL') return phone;
  if (level === 'HIDDEN') return '';
  // PARTIAL: 휴대폰만 마스킹 유지
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
        // F5 — 내선번호는 사내 협업 자산. PARTIAL/FULL 모두 공개.
        extMasked: level === 'HIDDEN' ? '' : `#${e.ext}`,
      };
    })
    .filter((e) => e.visibility !== 'HIDDEN');
}
