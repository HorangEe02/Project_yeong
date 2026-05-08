// RBAC + 부서 기반 모듈 가시성

export interface ModulePermission {
  slug: string;
  minRoleLevel: number;
  allowedDepartments?: string[]; // undefined = 모든 부서
}

export const MODULE_PERMISSIONS: ModulePermission[] = [
  { slug: 'dashboard', minRoleLevel: 1 },
  { slug: 'search', minRoleLevel: 1 },
  { slug: 'draft', minRoleLevel: 1 },
  { slug: 'chat', minRoleLevel: 1 },
  {
    slug: 'compliance',
    minRoleLevel: 2,
    allowedDepartments: ['품질보증팀', '환경안전팀', '법무팀', '구매팀', '해외영업팀', '생산기술팀', '경영기획팀'],
  },
  { slug: 'admin', minRoleLevel: 3 },
  {
    slug: 'equipment',
    minRoleLevel: 1,
    allowedDepartments: [
      '생산기술팀', '품질보증팀', '정비팀', '금형팀', '프레스팀', '용접팀',
      '도장팀', '검사팀', '환경안전팀', '사출팀', 'CNC팀', '컨베이어팀', '자재팀', '시스템관리팀',
    ],
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
  if (perm.allowedDepartments && user.department) {
    if (user.role_level >= 5) return true; // SYS/HR_ADMIN bypass
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
  if (perm.allowedDepartments && user.department && user.role_level < 5) {
    if (!perm.allowedDepartments.includes(user.department)) return '부서 권한 없음';
  }
  return null;
}
