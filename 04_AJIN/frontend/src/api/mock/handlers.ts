// Mock URL → 핸들러 맵
// 실제 백엔드 통합 전 데모용 응답 제공

import { ACCOUNTS } from './seed/accounts';
import { EMPLOYEES, ORG, TOTAL_HEADCOUNT } from './seed/employees';
import { METRICS, INGESTION, SYSTEM_HEALTH, SYSTEM_INFO } from './seed/system';
import { ALARMS } from './seed/alarms';

export interface MockError {
  status: number;
  detail: string;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: 'bearer';
  employee_id: string;
  username: string;
  role_name: string;
  role_level: number;
  must_change_pw: boolean;
  department?: string;
  position?: string;
}

const networkLatency = (ms = 200) =>
  new Promise<void>((res) => setTimeout(res, ms + Math.random() * 200));

export async function mockLogin(body: { employee_id: string; password: string }): Promise<LoginResponse> {
  await networkLatency();
  const account = ACCOUNTS.find((a) => a.employee_id === body.employee_id);

  if (!account) {
    throw { status: 401, detail: '잘못된 사번 또는 비밀번호입니다.' } satisfies MockError;
  }

  if (account.role_name === 'INACTIVE') {
    throw { status: 403, detail: '비활성화된 계정입니다. 관리자에게 문의하세요.' } satisfies MockError;
  }

  if (account.locked_until) {
    const until = new Date(account.locked_until);
    if (until > new Date()) {
      throw { status: 423, detail: `계정이 잠금 상태입니다. ${until.toLocaleString('ko-KR')}` } satisfies MockError;
    }
  }

  if (account.password !== body.password) {
    account.failed_attempts += 1;
    if (account.failed_attempts >= 5) {
      const lock = new Date(Date.now() + 30 * 60 * 1000);
      account.locked_until = lock.toISOString();
      throw { status: 401, detail: `5회 연속 실패. ${lock.toLocaleTimeString('ko-KR')} 까지 잠금됩니다.` } satisfies MockError;
    }
    throw { status: 401, detail: `비밀번호가 올바르지 않습니다. 남은 시도: ${5 - account.failed_attempts}회` } satisfies MockError;
  }

  // 로그인 성공
  account.failed_attempts = 0;
  account.locked_until = null;
  account.last_login = new Date().toISOString();

  return {
    access_token: `mock.jwt.${account.employee_id}.${Date.now()}`,
    refresh_token: `mock.refresh.${account.employee_id}`,
    token_type: 'bearer',
    employee_id: account.employee_id,
    username: account.username,
    role_name: account.role_name,
    role_level: account.role_level,
    must_change_pw: account.must_change_pw,
    department: account.department,
    position: account.position,
  };
}

export async function mockChangePassword(body: {
  employee_id: string;
  current_password: string;
  new_password: string;
}): Promise<{ message: string; must_change_pw: boolean }> {
  await networkLatency();
  const account = ACCOUNTS.find((a) => a.employee_id === body.employee_id);
  if (!account) throw { status: 404, detail: '사용자를 찾을 수 없습니다.' } satisfies MockError;
  if (account.password !== body.current_password)
    throw { status: 401, detail: '현재 비밀번호가 올바르지 않습니다.' } satisfies MockError;
  if (body.new_password.length < 8)
    throw { status: 400, detail: '새 비밀번호는 8자 이상이어야 합니다.' } satisfies MockError;

  account.password = body.new_password;
  account.must_change_pw = false;
  return { message: '비밀번호가 변경되었습니다.', must_change_pw: false };
}

export async function mockGetMetrics() {
  await networkLatency(80);
  return METRICS;
}

export async function mockGetIngestion() {
  await networkLatency(80);
  return INGESTION;
}

export async function mockGetSystemHealth() {
  await networkLatency(80);
  return SYSTEM_HEALTH;
}

export async function mockGetSystemInfo() {
  await networkLatency(80);
  return SYSTEM_INFO;
}

export async function mockGetAlarms() {
  await networkLatency(120);
  return ALARMS;
}

export async function mockGetEmployees() {
  await networkLatency(150);
  return { results: EMPLOYEES, total: EMPLOYEES.length, headcount: TOTAL_HEADCOUNT };
}

export async function mockGetOrgChart() {
  await networkLatency(80);
  return { org: ORG, total: TOTAL_HEADCOUNT };
}
