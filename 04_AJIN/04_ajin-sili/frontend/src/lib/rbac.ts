// RBAC + 부서 기반 모듈 가시성

export interface ModulePermission {
  slug: string;
  minRoleLevel: number;
  maxRoleLevel?: number;          // 옵션. 메뉴 노출 상한 — 라우트 직접 접근은 허용.
  allowedDepartments?: string[];  // undefined = 모든 부서
  deptBypassLevel?: number;       // 이 레벨 이상이면 부서 무관 노출. 기본 5(SYS_ADMIN).
}

export const MODULE_PERMISSIONS: ModulePermission[] = [
  { slug: 'dashboard', minRoleLevel: 1 },
  { slug: 'search', minRoleLevel: 1 },
  { slug: 'draft', minRoleLevel: 1 },
  { slug: 'chat', minRoleLevel: 1 },
  // 신입 가이드: L1~L3 만 사이드바 메뉴 노출 (L4+ 는 URL 직접 접근으로 참조용)
  { slug: 'onboarding', minRoleLevel: 1, maxRoleLevel: 3 },
  {
    slug: 'compliance',
    minRoleLevel: 2,
    allowedDepartments: ['품질보증팀', '환경안전팀', '법무팀', '구매팀', '해외영업팀', '생산기술팀', '경영기획팀'],
  },
  // v4.8 — 기능 G(HR) 완전 삭제. admin 만 유지.
  {
    slug: 'admin',
    minRoleLevel: 4,
    allowedDepartments: [
      'IT전략팀', '총무인사팀', '품질경영팀', '내부감사팀', '경영기획팀',
    ],
  },
  // v4.7 — management 는 admin alias (저장된 prefs 호환). /management → /admin redirect.
  {
    slug: 'management',
    minRoleLevel: 4,
    allowedDepartments: [
      'IT전략팀', '총무인사팀', '품질경영팀', '내부감사팀', '경영기획팀',
    ],
  },
  {
    slug: 'equipment',
    minRoleLevel: 1,
    allowedDepartments: [
      '생산기술팀', '품질보증팀', '정비팀', '금형팀', '프레스팀', '용접팀',
      '도장팀', '검사팀', '환경안전팀', '사출팀', 'CNC팀', '컨베이어팀', '자재팀', '시스템관리팀',
    ],
    // 백엔드 require_equipment_access 와 일치 — L4+ 는 부서 무관 열람 허용
    // (쇼케이스 게스트 L4 포함). 프론트만 L5 였던 불일치 해소.
    deptBypassLevel: 4,
  },
];

export function isMenuVisible(
  slug: string,
  user: { role_level: number; department?: string; role_name?: string } | null,
): boolean {
  if (!user) return false;
  if (user.role_name === 'INACTIVE') return false;
  const perm = MODULE_PERMISSIONS.find((m) => m.slug === slug);
  if (!perm) return true;
  if (user.role_level < perm.minRoleLevel) return false;
  // 메뉴 노출 상한 — 이전 주석 "SYS/HR_ADMIN 도 적용" 정책 철회 (2026-05-28).
  // L5 SYS_ADMIN 은 모든 기능 사용 가능해야 (사용자 요청). onboarding 같은
  // 신입 전용(maxRoleLevel:3) 메뉴도 L5 가 사이드바에서 볼 수 있도록.
  if (perm.maxRoleLevel !== undefined && user.role_level > perm.maxRoleLevel) {
    if (user.role_level >= 5) return true; // L5 bypass — maxRoleLevel 우회
    return false;
  }
  if (perm.allowedDepartments && user.department) {
    // 부서 무관 노출 상한 — 기본 L5(SYS_ADMIN). 모듈별 deptBypassLevel 로 조정
    // (equipment 는 백엔드와 동일하게 L4+ 부서 무관).
    if (user.role_level >= (perm.deptBypassLevel ?? 5)) return true;
    return perm.allowedDepartments.includes(user.department);
  }
  return true;
}

export function getLockReason(
  slug: string,
  user: { role_level: number; department?: string; role_name?: string } | null,
): string | null {
  if (!user) return '로그인 필요';
  if (user.role_name === 'INACTIVE') return '비활성 계정';
  const perm = MODULE_PERMISSIONS.find((m) => m.slug === slug);
  if (!perm) return null;
  if (user.role_level < perm.minRoleLevel) return `L${perm.minRoleLevel} 이상 필요`;
  if (perm.allowedDepartments && user.department && user.role_level < (perm.deptBypassLevel ?? 5)) {
    if (!perm.allowedDepartments.includes(user.department)) return '부서 권한 없음';
  }
  return null;
}
