import { api } from './client';

export interface LiveAlarmItem {
  id: string;
  domain: string;
  severity: string;
  message: string;
  payload: Record<string, unknown>;
  created_at: string;
  acknowledged_at: string | null;
}

export interface LiveAlarmListResponse {
  alarms: LiveAlarmItem[];
  total: number;
}

/** Fetch recent backend-backed live alarms that replace legacy RTDB reads. */
export async function fetchLiveAlarmsRecent(
  domain = 'equipment',
  limit = 50,
): Promise<LiveAlarmListResponse> {
  const { data } = await api.get<LiveAlarmListResponse>('/live-alarms/recent', {
    params: { domain, limit },
  });
  return data;
}
