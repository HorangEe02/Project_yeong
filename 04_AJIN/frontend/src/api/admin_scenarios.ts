// admin_scenarios.ts — 협업 시나리오 관리 API 클라이언트 (HR_ADMIN+).
// backend/routers/admin_scenarios.py 와 1:1 매핑.

import { api } from './client';

export interface ScenarioItem {
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
  created_by: string;
  updated_by: string;
  created_at: string;
  updated_at: string;
  is_active: boolean;
}

export interface ScenarioListResponse {
  total: number;
  items: ScenarioItem[];
}

export async function fetchScenarios(includeInactive = true): Promise<ScenarioListResponse> {
  const { data } = await api.get<ScenarioListResponse>('/admin/scenarios', {
    params: { include_inactive: includeInactive },
  });
  return data;
}

export async function fetchScenario(id: string): Promise<ScenarioItem> {
  const { data } = await api.get<ScenarioItem>(`/admin/scenarios/${encodeURIComponent(id)}`);
  return data;
}

export interface ScenarioCreatePayload {
  scenario_id: string;
  trigger_keywords?: string[];
  situation?: string;
  requesting_dept?: string;
  my_actions?: string[];
  hand_off_to?: string;
  hand_off_items?: string[];
  deadline_info?: string;
  related_sop_id?: string;
  tips?: string[];
  priority?: number;
  scope_division?: string;
  lang?: string;
}

export async function createScenario(payload: ScenarioCreatePayload): Promise<ScenarioItem> {
  const { data } = await api.post<ScenarioItem>('/admin/scenarios', payload);
  return data;
}

export type ScenarioUpdatePayload = Partial<Omit<ScenarioCreatePayload, 'scenario_id'>> & {
  is_active?: boolean;
};

export async function updateScenario(id: string, patch: ScenarioUpdatePayload): Promise<ScenarioItem> {
  const { data } = await api.put<ScenarioItem>(`/admin/scenarios/${encodeURIComponent(id)}`, patch);
  return data;
}

export async function resetScenario(id: string): Promise<ScenarioItem> {
  const { data } = await api.post<ScenarioItem>(`/admin/scenarios/${encodeURIComponent(id)}/reset`);
  return data;
}

export interface DeleteScenarioResponse {
  action: string;
  scenario_id: string;
  is_system_default: boolean;
}

export async function deleteScenario(id: string): Promise<DeleteScenarioResponse> {
  const { data } = await api.delete<DeleteScenarioResponse>(`/admin/scenarios/${encodeURIComponent(id)}`);
  return data;
}

export interface ScenarioHistoryEntry {
  id: number;
  scenario_id: string;
  action: string;
  changed_by: string;
  changed_at: string;
  before: Record<string, unknown>;
  after: Record<string, unknown>;
}

export interface ScenarioHistoryResponse {
  scenario_id: string;
  total: number;
  history: ScenarioHistoryEntry[];
}

export async function fetchScenarioHistory(id: string, limit = 50): Promise<ScenarioHistoryResponse> {
  const { data } = await api.get<ScenarioHistoryResponse>(
    `/admin/scenarios/${encodeURIComponent(id)}/history`,
    { params: { limit } },
  );
  return data;
}

export async function restoreScenarioVersion(id: string, historyId: number): Promise<ScenarioItem> {
  const { data } = await api.post<ScenarioItem>(
    `/admin/scenarios/${encodeURIComponent(id)}/restore/${historyId}`,
  );
  return data;
}

export interface UsageStatsRow {
  scenario_id: string;
  hits: number;
  situation: string;
  requesting_dept: string;
}

export interface ZeroMatchRow {
  scenario_id: string;
  situation: string;
  requesting_dept: string;
}

export interface UsageStatsResponse {
  days: number;
  by_scenario: UsageStatsRow[];
  zero_match: ZeroMatchRow[];
}

export async function fetchScenarioUsageStats(days = 30): Promise<UsageStatsResponse> {
  const { data } = await api.get<UsageStatsResponse>('/admin/scenarios/usage-stats', {
    params: { days },
  });
  return data;
}
