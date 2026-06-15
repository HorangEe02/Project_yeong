import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios';
import { useAuthStore } from '@store/auth';
import { useMaintenanceStore } from '@store/maintenance';
import { API_BASE_URL } from './baseUrl';
import { csrfHeaderFor } from './csrf';

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30_000,
  withCredentials: true,
});

// Request interceptor — browser cookie auth + CSRF for unsafe methods.
api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const method = config.method ?? 'GET';
  for (const [key, value] of Object.entries(csrfHeaderFor(method))) {
    config.headers.set(key, value);
  }
  return config;
});

// 401 자동 복구 — HttpOnly refresh cookie 기준으로만 재발급.
// 동시 다중 401 요청에 대해 inflight 중복을 막기 위해 전역 promise 캐시.
const GUEST_EMPLOYEE_ID = 'GUEST';
let refreshing: Promise<boolean> | null = null;
let minting: Promise<boolean> | null = null;

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
      _guestRetry?: boolean;
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

      refreshing ??= refreshBrowserSession();
      const refreshed = await refreshing;
      refreshing = null;

      if (refreshed) {
        return api(originalRequest);
      }

      // refresh 실패 — 게스트(쇼케이스) 세션이면 /login 으로 튕기는 대신 게스트로
      // 재발급해 복구한다. 한 화면의 401 이 공유 세션을 clear() 로 날려 전 패널이
      // 로그인 화면으로 빠지는 cascade 를 막는다 (showcase 읽기전용 UX 보호).
      const current = useAuthStore.getState().user;
      if (current?.employee_id === GUEST_EMPLOYEE_ID && !originalRequest._guestRetry) {
        originalRequest._guestRetry = true;
        minting ??= mintGuestSession();
        const minted = await minting;
        minting = null;
        if (minted) {
          return api(originalRequest);
        }
      }

      // refresh·게스트 재발급 모두 실패 → clearAuth + /login 리다이렉트
      useAuthStore.getState().clear();
      if (typeof window !== 'undefined' && window.location.pathname !== '/login') {
        // replace 사용 — 뒤로가기 시 protected 페이지로 돌아가 무한 401 루프 방지
        window.location.replace('/login');
      }
    }

    return Promise.reject(error);
  },
);

async function refreshBrowserSession(): Promise<boolean> {
  try {
    const response = await axios.post(
      `${API_BASE_URL}/auth/refresh`,
      {},
      {
        withCredentials: true,
        headers: csrfHeaderFor('POST'),
      },
    );

    useAuthStore.getState().setSession(response.data);
    return true;
  } catch (e) {
    if (import.meta.env.DEV) {
      console.warn('[Auth] refresh 실패:', e);
    }
    return false;
  }
}

// 게스트(쇼케이스) 세션 재발급 — refresh 불가한 게스트가 401 을 만나도 로그인으로
// 튕기지 않고 읽기전용 세션을 자동 복구하기 위함. /auth/guest 는
// SHOWCASE_GUEST_ENABLED=false 면 404 → 실패 처리되어 정상 로그인 흐름으로 폴백.
async function mintGuestSession(): Promise<boolean> {
  try {
    const response = await axios.post(
      `${API_BASE_URL}/auth/guest`,
      {},
      { withCredentials: true, headers: csrfHeaderFor('POST') },
    );
    useAuthStore.getState().setSession(response.data);
    return true;
  } catch (e) {
    if (import.meta.env.DEV) {
      console.warn('[Auth] 게스트 세션 재발급 실패:', e);
    }
    return false;
  }
}
