/**
 * F5c 사용자 알림 환경설정 — server `functions/src/notifications/types.ts` 와 1:1 미러.
 *
 * RTDB path: `/users/{uid}/notifications`
 *
 * Dispatcher 해석 원칙 (기본값 = 허용):
 *  - `revokedAt` 설정 시 모든 채널/시나리오 전체 차단 (PIPA 대응)
 *  - `channels.{channel} === false` → 해당 채널 skip
 *  - `scenarios.{eventType} === false` → 해당 시나리오 전체 skip
 *  - 누락 필드는 기본 허용
 */

export type NotificationChannel = 'alimtalk' | 'fcm' | 'sms' | 'email';

export type NotificationEventType =
  | 'appointment.confirmed'
  | 'appointment.reminder'
  | 'queue.call'
  | 'queue.preCall'
  | 'payment.completed'
  | 'payment.request'
  | 'prescription.sent';

export interface UserNotificationPrefs {
  channels?: Partial<Record<NotificationChannel, boolean>>;
  scenarios?: Partial<Record<NotificationEventType, boolean>>;
  /** 철회 시각 (timestamp ms). 존재 시 모든 채널 차단. */
  revokedAt?: number;
  updatedAt?: number;
}

/** UI 라벨 (i18n 대응은 후속) */
export const CHANNEL_LABELS: Record<NotificationChannel, string> = {
  alimtalk: '카카오 알림톡',
  fcm: '앱 푸시',
  sms: '문자 (SMS)',
  email: '이메일',
};

export const SCENARIO_LABELS: Record<NotificationEventType, string> = {
  'appointment.confirmed': '예약 확인',
  'appointment.reminder': '예약 1시간 전 알림',
  'queue.call': '호출 알림',
  'queue.preCall': '호출 5분 전',
  'payment.completed': '결제 완료',
  'payment.request': '대리결제 요청',
  'prescription.sent': '처방전 전송',
};

export const CHANNEL_ORDER: NotificationChannel[] = ['alimtalk', 'fcm', 'sms', 'email'];

export const SCENARIO_ORDER: NotificationEventType[] = [
  'appointment.confirmed',
  'appointment.reminder',
  'queue.call',
  'queue.preCall',
  'payment.completed',
  'payment.request',
  'prescription.sent',
];

/** pref 해석 헬퍼 — dispatcher 의 isChannelEnabled 와 동일 로직. */
export function isChannelEnabled(
  prefs: UserNotificationPrefs,
  channel: NotificationChannel,
  scenario: NotificationEventType,
): boolean {
  if (prefs.revokedAt) return false;
  if (prefs.channels && prefs.channels[channel] === false) return false;
  if (prefs.scenarios && prefs.scenarios[scenario] === false) return false;
  return true;
}
