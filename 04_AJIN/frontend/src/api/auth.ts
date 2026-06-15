// 인증 API — Mock / 실 백엔드 분기

import { api } from './client';
import { USE_MOCK, mockLogin, mockChangePassword, type LoginResponse, type MockError } from './mock';
import { useAuthStore } from '@store/auth';

export interface LoginRequest {
  employee_id: string;
  password: string;
}

export interface ChangePasswordRequest {
  current_password: string;
  new_password: string;
}

export type { LoginResponse };

export async function login(body: LoginRequest): Promise<LoginResponse> {
  if (USE_MOCK) {
    return mockLogin(body);
  }
  const { data } = await api.post<LoginResponse>('/auth/login', body);
  return data;
}

// 공개 쇼케이스용 게스트(읽기 전용) 세션 — 자격증명 없이 /auth/guest 호출.
// 쿠키(세션) 설정 + 게스트 사용자 정보 반환. role_level=2 라 mutation 은 백엔드 RBAC 가 차단.
export async function guestLogin(): Promise<LoginResponse> {
  const { data } = await api.post<LoginResponse>('/auth/guest', {});
  return data;
}

export async function changePassword(body: ChangePasswordRequest) {
  if (USE_MOCK) {
    const employee_id = useAuthStore.getState().user?.employee_id ?? '';
    return mockChangePassword({ ...body, employee_id });
  }
  const { data } = await api.post('/auth/change-password', body);
  return data;
}

export async function logout(): Promise<void> {
  if (!USE_MOCK) {
    await api.post('/auth/logout', {});
  }
  useAuthStore.getState().clear();
}

// ──────────────────────────────────────────────────────────────
// v4.7 Feature E — 2FA (TOTP) + 외부 IdP 캐퍼빌리티
// ──────────────────────────────────────────────────────────────

export interface TwoFactorEnrollResponse {
  secret_b32: string;
  otpauth_url: string;
  backup_codes: string[];
  issuer: string;
}

export async function fetch2FAStatus(): Promise<{ enabled: boolean }> {
  try {
    const { data } = await api.get<{ enabled: boolean }>('/auth/2fa/status');
    return data;
  } catch {
    return { enabled: false };
  }
}

export async function enroll2FA(): Promise<TwoFactorEnrollResponse> {
  const { data } = await api.post<TwoFactorEnrollResponse>('/auth/2fa/enroll');
  return data;
}

export async function confirm2FA(code: string): Promise<{ enabled: boolean }> {
  const { data } = await api.post<{ enabled: boolean }>('/auth/2fa/confirm', { code });
  return data;
}

export async function verify2FA(mid_token: string, code: string): Promise<LoginResponse> {
  const { data } = await api.post<LoginResponse>('/auth/2fa/verify', { mid_token, code });
  return data;
}

export async function regenBackupCodes(password: string): Promise<{ backup_codes: string[] }> {
  const { data } = await api.post<{ backup_codes: string[] }>('/auth/2fa/backup-regen', { password });
  return data;
}

export async function disable2FA(password: string): Promise<{ enabled: boolean }> {
  const { data } = await api.post<{ enabled: boolean }>('/auth/2fa/disable', { password });
  return data;
}

export interface IdPCapabilities {
  providers: string[];
}

export async function fetchIdPCapabilities(): Promise<IdPCapabilities> {
  try {
    const { data } = await api.get<IdPCapabilities>('/auth/idp/capabilities');
    return data;
  } catch {
    // 백엔드 미배포/구버전 → 비활성으로 처리
    return { providers: [] };
  }
}

export function extractError(e: unknown): { status: number; detail: string } {
  // Mock 에러 형태
  const me = e as MockError;
  if (typeof me?.status === 'number' && typeof me?.detail === 'string') {
    return { status: me.status, detail: me.detail };
  }
  // axios 에러 형태
  const ax = e as { response?: { status?: number; data?: { detail?: string } } };
  if (ax?.response) {
    return {
      status: ax.response.status ?? 500,
      detail: ax.response.data?.detail ?? '서버 오류가 발생했습니다.',
    };
  }
  return { status: 0, detail: '네트워크 연결 실패' };
}
