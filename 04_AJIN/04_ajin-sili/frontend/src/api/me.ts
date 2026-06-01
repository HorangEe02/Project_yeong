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
  /** v3.9 — 디지털 사원증 사진 (data:image/jpeg;base64,...). 미설정 시 빈 문자열. */
  photo_url?: string;
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

// v3.9 — 디지털 사원증 증명사진 변경.
// backend `PATCH /api/auth/me/photo` → users.photo_url 인라인 저장 (base64 dataUrl).
// 추후 Supabase Storage signed-upload 로 마이그레이션 시 같은 endpoint signature 유지.
export async function updateMyPhoto(photoDataUrl: string): Promise<MeProfile> {
  const { data } = await api.patch<MeProfile>('/auth/me/photo', {
    photo_data_url: photoDataUrl,
  });
  return data;
}
