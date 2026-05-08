// G2: 알림 환경설정 + 테스트 발송 API.
import { api } from './client';

export type Severity = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

export interface NotificationPrefs {
  enabled: boolean;
  channel_email: boolean;
  channel_slack: boolean;          // 차분기
  severity_threshold: Severity;
  digest_enabled: boolean;
  digest_hour_kst: number;         // 0~23
  plant_filter: string[] | null;
  department_filter: string | null;
}

export interface NotificationPrefsOut extends NotificationPrefs {
  user_id: string;
  email: string;
}

export async function fetchMyPrefs(): Promise<NotificationPrefsOut> {
  const { data } = await api.get<NotificationPrefsOut>('/notifications/me');
  return data;
}

export async function updateMyPrefs(p: NotificationPrefs): Promise<NotificationPrefsOut> {
  const { data } = await api.put<NotificationPrefsOut>('/notifications/me', p);
  return data;
}

export async function sendTestNotification(): Promise<{ queued: boolean }> {
  const { data } = await api.post<{ queued: boolean }>(
    '/notifications/test',
    { to_self: true },
  );
  return data;
}
