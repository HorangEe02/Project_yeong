// 데모 빠른 로그인 칩 — DEV/TEST mock 모드에서만 노출

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

/**
 * Return true only when the hard-coded demo credentials are expected to work.
 *
 * `Demo!2026` belongs to the mock seed data. Supabase/Postgres release smoke
 * must use the bootstrap secret or short-lived smoke JWT path instead.
 */
export function shouldShowDemoChips(): boolean {
  const mockMode = import.meta.env.VITE_USE_MOCK === 'true';
  const explicitlyEnabled = import.meta.env.VITE_DEMO_CHIPS_ENABLED === 'true';
  if (import.meta.env.PROD) return false;
  if (import.meta.env.DEV && mockMode) return true;
  if (!explicitlyEnabled) return false;
  if (typeof window !== 'undefined') {
    return new URLSearchParams(window.location.search).get('demo') === '1';
  }
  return false;
}
