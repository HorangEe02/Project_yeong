// v4.7 C-4 — 게이미피케이션 API 클라이언트
//   GET  /api/onboarding/badges/me
//   GET  /api/onboarding/leaderboard/{dept}
//   POST /api/onboarding/sop/progress
//   POST /api/onboarding/quiz/result

import { authHeaders } from '@api/onboarding';
import { apiUrl } from './baseUrl';

function api(path: string): string {
  return apiUrl(path);
}

export interface BadgeDefinition {
  badge_id: string;
  category: string;
  tier: string;
  earned: boolean;
}

export interface EarnedBadge {
  badge_id: string;
  earned_at: string;
  metadata: Record<string, unknown>;
}

export interface BadgesMeResponse {
  earned: EarnedBadge[];
  definitions: BadgeDefinition[];
  rank: { rank: number; total: number; percentile: number } | null;
  department?: string;
}

export interface LeaderboardResponse {
  dept: string;
  period: string;
  visible: boolean;
  top_users: Array<{ user_id: string; score: number }>;
  total_active: number;
}

export async function fetchMyBadges(): Promise<BadgesMeResponse> {
  const res = await fetch(api('/onboarding/badges/me'), {
    headers: { ...authHeaders() },
  });
  if (!res.ok) throw new Error(`badges/me failed: ${res.status}`);
  return (await res.json()) as BadgesMeResponse;
}

export async function fetchDeptLeaderboard(dept: string): Promise<LeaderboardResponse> {
  const res = await fetch(
    api(`/onboarding/leaderboard/${encodeURIComponent(dept)}`),
    { headers: { ...authHeaders() } },
  );
  if (!res.ok) throw new Error(`leaderboard failed: ${res.status}`);
  return (await res.json()) as LeaderboardResponse;
}

export async function reportSopProgress(sopId: string, stepNumber: number): Promise<{ ok: boolean; newly_earned: string[] }> {
  const res = await fetch(api('/onboarding/sop/progress'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ sop_id: sopId, step_number: stepNumber }),
  });
  if (!res.ok) throw new Error(`sop/progress failed: ${res.status}`);
  return (await res.json()) as { ok: boolean; newly_earned: string[] };
}

export async function reportQuizResult(payload: {
  is_correct: boolean;
  category?: string;
  difficulty?: string;
  sop_id?: string;
  source_id?: string;
  related_step?: number;
}): Promise<{ ok: boolean; newly_earned: string[] }> {
  const res = await fetch(api('/onboarding/quiz/result'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`quiz/result failed: ${res.status}`);
  return (await res.json()) as { ok: boolean; newly_earned: string[] };
}
