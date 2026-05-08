// 인증 API — Mock / 실 백엔드 분기

import { api } from './client';
import { USE_MOCK, mockLogin, mockChangePassword, type LoginResponse, type MockError } from './mock';

export interface LoginRequest {
  employee_id: string;
  password: string;
}

export interface ChangePasswordRequest {
  employee_id: string;
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

export async function changePassword(body: ChangePasswordRequest) {
  if (USE_MOCK) {
    return mockChangePassword(body);
  }
  const { data } = await api.post('/auth/change-password', body);
  return data;
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
