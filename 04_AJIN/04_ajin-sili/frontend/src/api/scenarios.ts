// Day 5 — 협업 시나리오 매칭 API 클라이언트
// 백엔드 POST /api/onboarding/scenarios/match — LLM 호출 0회 즉시 응답 (본선 시연 차별점).
// Phase 2: 사용자 컨텍스트 list — GET /api/scenarios
// Phase 3: 즐겨찾기 / 메모

import { api } from './client';
import { ONBOARDING_BASE, authHeaders } from '@api/onboarding';

export interface ScenarioCard {
  scenario_id: string;
  situation: string;
  requesting_dept: string;
  my_actions: string[];
  hand_off_to: string;
  hand_off_items: string[];
  deadline_info: string;
  related_sop_id: string;
  tips: string[];
  formatted_text: string;
}

export interface ScenarioMatchResponse {
  matched: boolean;
  card: ScenarioCard | null;
}

export async function matchScenario(query: string): Promise<ScenarioMatchResponse> {
  const res = await fetch(`${ONBOARDING_BASE}/scenarios/match`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
    },
    body: JSON.stringify({ query }),
  });
  if (!res.ok) {
    throw new Error(`시나리오 매칭 실패: ${res.status}`);
  }
  return (await res.json()) as ScenarioMatchResponse;
}

// ─────────────────────────────────────────────────────────────
// 사용자용 시나리오 목록 (부서/언어 컨텍스트)
// ─────────────────────────────────────────────────────────────

export interface UserScenarioItem {
  scenario_id: string;
  is_system_default: boolean;
  trigger_keywords: string[];
  situation: string;
  requesting_dept: string;
  my_actions: string[];
  hand_off_to: string;
  hand_off_items: string[];
  deadline_info: string;
  related_sop_id: string;
  tips: string[];
  priority: number;
  scope_division: string;
  lang: string;
  is_active: boolean;
}

export interface UserScenarioListResponse {
  total: number;
  items: UserScenarioItem[];
}

export async function fetchUserScenarios(division = '', lang = 'ko'): Promise<UserScenarioListResponse> {
  const { data } = await api.get<UserScenarioListResponse>('/scenarios', {
    params: { division, lang },
  });
  return data;
}

// ─────────────────────────────────────────────────────────────
// 즐겨찾기 / 메모 (Phase 3)
// ─────────────────────────────────────────────────────────────

export interface FavoriteItem {
  scenario_id: string;
  note: string;
  created_at: string;
  situation: string;
  requesting_dept: string;
  deadline_info: string;
  is_active: boolean;
}

export interface FavoriteListResponse {
  total: number;
  items: FavoriteItem[];
}

export async function fetchMyFavorites(): Promise<FavoriteListResponse> {
  const { data } = await api.get<FavoriteListResponse>('/scenarios/favorites');
  return data;
}

export async function addFavorite(scenarioId: string, note = ''): Promise<{ scenario_id: string; note: string }> {
  const { data } = await api.post(`/scenarios/${encodeURIComponent(scenarioId)}/favorite`, { note });
  return data;
}

export async function updateFavoriteNote(scenarioId: string, note: string): Promise<{ scenario_id: string; note: string }> {
  const { data } = await api.put(`/scenarios/${encodeURIComponent(scenarioId)}/favorite`, { note });
  return data;
}

export async function removeFavorite(scenarioId: string): Promise<{ removed: number }> {
  const { data } = await api.delete<{ removed: number }>(`/scenarios/${encodeURIComponent(scenarioId)}/favorite`);
  return data;
}
