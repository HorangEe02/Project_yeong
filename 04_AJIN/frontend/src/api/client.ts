import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios';
import { useAuthStore, type AuthUser } from '@store/auth';
import { useMaintenanceStore } from '@store/maintenance';
import { getFirebaseIdToken } from '@lib/firebaseAuth';

/**
 * baseURL invariant: 항상 `/api` 로 끝난다.
 *
 * VITE_API_URL 가 빈 문자열/undefined → '/api' (same-origin, Hosting rewrite 가 Cloud Run 에 위임)
 * VITE_API_URL='http://localhost:8000' → 'http://localhost:8000/api' (dev cross-origin)
 * VITE_API_URL='http://localhost:8000/api' → 그대로
 *
 * 모든 API 호출은 `api.post('/auth/login')` 처럼 짧은 path 사용.
 */
function _resolveApiUrl(): string {
  const raw = (import.meta.env.VITE_API_URL ?? '').toString().replace(/\/$/, '');
  if (!raw) return '/api';
  if (raw.endsWith('/api')) return raw;
  return `${raw}/api`;
}

const API_URL = _resolveApiUrl();

export const api = axios.create({
  baseURL: API_URL,
  timeout: 30_000,
  withCredentials: true,
});

// Request interceptor — JWT 자동 첨부
api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = useAuthStore.getState().accessToken;
  if (token) {
    config.headers.set('Authorization', `Bearer ${token}`);
  }
  return config;
});

// Day 5++.5: 401 자동 복구 — refresh → firebase-exchange → fallback
// 동시 다중 401 요청에 대해 inflight 중복을 막기 위해 전역 promise 캐시.
let refreshing: Promise<string | null> | null = null;
let exchanging: Promise<string | null> | null = null;

interface FirebaseExchangeResponse {
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

api.interceptors.response.use(
  (response) => {
    // Plan A 변형: 정상 응답 시 maintenance 해제 (Mac on 신호)
    if (useMaintenanceStore.getState().active) {
      useMaintenanceStore.getState().setActive(false);
    }
    return response;
  },
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & {
      _retry?: boolean;
    };

    // Plan A 변형: 503 + AI_UNAVAILABLE → maintenance banner 활성화
    if (error.response?.status === 503) {
      const data = error.response.data as
        | { error?: string; message?: string; reason?: string }
        | undefined;
      if (data?.error === 'AI_UNAVAILABLE') {
        useMaintenanceStore
          .getState()
          .setActive(true, data.message, data.reason ?? '');
        // 그대로 reject — 호출 측이 알아서 무시 또는 toast
        return Promise.reject(error);
      }
    }

    if (error.response?.status === 401 && originalRequest && !originalRequest._retry) {
      originalRequest._retry = true;

      // 1) refresh_token 으로 access_token 재발급
      if (useAuthStore.getState().refreshToken) {
        refreshing ??= refreshAccessToken();
        const newToken = await refreshing;
        refreshing = null;

        if (newToken && originalRequest.headers) {
          originalRequest.headers.set('Authorization', `Bearer ${newToken}`);
          return api(originalRequest);
        }
      }

      // 2) Firebase ID Token 으로 백엔드 JWT 재발급 (silent recovery)
      exchanging ??= exchangeFirebaseToken();
      const exchangedToken = await exchanging;
      exchanging = null;

      if (exchangedToken && originalRequest.headers) {
        originalRequest.headers.set('Authorization', `Bearer ${exchangedToken}`);
        return api(originalRequest);
      }

      // 3) 모두 실패 → clearAuth + /login 리다이렉트 (마지막 resort)
      useAuthStore.getState().clear();
      if (typeof window !== 'undefined' && window.location.pathname !== '/login') {
        // replace 사용 — 뒤로가기 시 protected 페이지로 돌아가 무한 401 루프 방지
        window.location.replace('/login');
      }
    }

    return Promise.reject(error);
  },
);

async function refreshAccessToken(): Promise<string | null> {
  try {
    const refreshToken = useAuthStore.getState().refreshToken;
    if (!refreshToken) return null;

    const response = await axios.post<{ access_token: string }>(
      `${API_URL}/auth/refresh`,
      { refresh_token: refreshToken },
    );

    const newToken = response.data.access_token;
    useAuthStore.getState().setAccessToken(newToken);
    return newToken;
  } catch (e) {
    if (import.meta.env.DEV) {
      console.warn('[Auth] refresh 실패:', e);
    }
    return null;
  }
}

async function exchangeFirebaseToken(): Promise<string | null> {
  try {
    const idToken = await getFirebaseIdToken(true);
    if (!idToken) return null;

    const response = await axios.post<FirebaseExchangeResponse>(
      `${API_URL}/auth/firebase-exchange`,
      { id_token: idToken },
    );

    const data = response.data;
    const user: AuthUser = {
      employee_id: data.employee_id,
      username: data.username,
      role_name: data.role_name,
      role_level: data.role_level,
      department: data.department,
      position: data.position,
    };
    useAuthStore.getState().setSession(data.access_token, data.refresh_token, user);
    return data.access_token;
  } catch (e) {
    if (import.meta.env.DEV) {
      console.warn('[Auth] Firebase exchange 실패:', e);
    }
    return null;
  }
}
