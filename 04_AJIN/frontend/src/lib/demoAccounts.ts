// 데모 빠른 로그인 칩 — DEV 모드 또는 ?demo=1 URL 파라미터일 때 노출

export interface DemoChip {
  employee_id: string;
  password: string;
  username: string;
  role_label: string;
  role_level: number;
}

export const DEMO_CHIPS: DemoChip[] = [
  { employee_id: 'SYS-0001', password: 'Demo!2026', username: '박준영', role_label: 'SYS_ADMIN', role_level: 6 },
  { employee_id: 'HR-0001', password: 'Demo!2026', username: '이영희', role_label: 'HR_ADMIN', role_level: 5 },
  { employee_id: 'QA-0001', password: 'Demo!2026', username: '김민수', role_label: 'TEAM_LEAD', role_level: 4 },
  { employee_id: 'PE-0019', password: 'Demo!2026', username: '최유진', role_label: 'EMPLOYEE', role_level: 2 },
];

export function shouldShowDemoChips(): boolean {
  if (import.meta.env.DEV) return true;
  if (typeof window !== 'undefined') {
    return new URLSearchParams(window.location.search).get('demo') === '1';
  }
  return false;
}
