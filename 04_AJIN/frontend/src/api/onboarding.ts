// Day 4 — 온보딩 채팅 API 클라이언트
// SSE 호출은 useSSE 훅이 직접 fetchEventSource 로 처리.
// 본 파일은 URL/헤더 빌더 + 비스트리밍 health 만 담당.

import { useAuthStore } from '@store/auth';

const API_BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? '/api';

function ensureApiSuffix(base: string): string {
  // VITE_API_URL 이 ":8000" 처럼 /api 접미사 없이 들어오면 보정.
  if (base.endsWith('/api') || base.endsWith('/api/')) return base;
  return `${base.replace(/\/$/, '')}/api`;
}

export const ONBOARDING_BASE = `${ensureApiSuffix(API_BASE)}/onboarding`;

export function buildChatUrl(): string {
  return `${ONBOARDING_BASE}/chat`;
}

export function buildHealthUrl(): string {
  return `${ONBOARDING_BASE}/health`;
}

export function authHeaders(): Record<string, string> {
  const token = useAuthStore.getState().accessToken;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export interface OnboardingHealth {
  providers: string[];
  circuit: Record<string, { state: string } | string>;
  metrics?: Record<string, unknown>;
}

export async function fetchOnboardingHealth(): Promise<OnboardingHealth> {
  const res = await fetch(buildHealthUrl(), {
    headers: authHeaders(),
  });
  if (!res.ok) {
    throw new Error(`onboarding health failed: ${res.status}`);
  }
  return (await res.json()) as OnboardingHealth;
}
