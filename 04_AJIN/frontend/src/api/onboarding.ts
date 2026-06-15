// Day 4 — 온보딩 채팅 API 클라이언트
// SSE 호출은 useSSE 훅이 직접 fetchEventSource 로 처리.
// 본 파일은 URL/헤더 빌더 + 비스트리밍 health 만 담당.

import { apiUrl } from './baseUrl';

export const ONBOARDING_BASE = apiUrl('/onboarding');

export function buildChatUrl(): string {
  return `${ONBOARDING_BASE}/chat`;
}

export function buildHealthUrl(): string {
  return `${ONBOARDING_BASE}/health`;
}

export function authHeaders(): Record<string, string> {
  return {};
}

export interface OnboardingHealth {
  providers: string[];
  circuit: Record<string, { state: string } | string>;
  metrics?: Record<string, unknown>;
}

export async function fetchOnboardingHealth(): Promise<OnboardingHealth> {
  const res = await fetch(buildHealthUrl(), {
    headers: authHeaders(),
    credentials: 'include',
  });
  if (!res.ok) {
    throw new Error(`onboarding health failed: ${res.status}`);
  }
  return (await res.json()) as OnboardingHealth;
}
