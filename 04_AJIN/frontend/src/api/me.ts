// 본인 프로필 API — backend/routers/auth.py 의 /me, /me, /me/login-history 매핑.

import { api } from './client';

export interface MeProfile {
  employee_id: string;
  username: string;
  role_name: string;
  role_level: number;
  department: string;
  position: string;
  email: string;
  phone: string;
  hire_date: string;
  last_login: string | null;
  created_at: string | null;
  updated_at: string | null;
  is_active: boolean;
  must_change_pw: boolean;
}

export interface MeUpdateRequest {
  email?: string;
  phone?: string;
  position?: string;
  // HR_ADMIN(Lv4)+ 전용 필드
  employee_id?: string;
  username?: string;
  department?: string;
  role_name?: string;
}

export interface MeUpdateResponse {
  profile: MeProfile;
  /** 사번/역할 변경 시 true → 프론트가 강제 로그아웃 후 재로그인. */
  reissued: boolean;
}

export interface LoginHistoryEntry {
  id: number;
  action: string;
  success: boolean;
  ip_address: string;
  user_agent: string;
  timestamp: string;
}

export interface LoginHistoryResponse {
  employee_id: string;
  total: number;
  history: LoginHistoryEntry[];
}

export async function getMe(): Promise<MeProfile> {
  const { data } = await api.get<MeProfile>('/auth/me');
  return data;
}

export async function updateMe(req: MeUpdateRequest): Promise<MeUpdateResponse> {
  const { data } = await api.put<MeUpdateResponse>('/auth/me', req);
  return data;
}

export async function getMyLoginHistory(limit = 20): Promise<LoginHistoryResponse> {
  const { data } = await api.get<LoginHistoryResponse>('/auth/me/login-history', {
    params: { limit },
  });
  return data;
}
