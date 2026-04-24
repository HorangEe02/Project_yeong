/**
 * F5 알림 시스템 타입 정의.
 *
 * Dispatcher 입력: NotificationEvent — "무엇을 누구에게 보낼지" 의 논리적 단위.
 * Adapter 반환: SendResult — 시도별 결과.
 * 저장: /notification_logs/{uid}/{pushId} — attempts + finalStatus.
 * 사용자 설정: /users/{uid}/notifications — 채널/시나리오별 on/off.
 */

export type NotificationEventType =
  | 'appointment.confirmed'
  | 'appointment.reminder'
  | 'queue.call'
  | 'queue.preCall'
  | 'payment.completed'
  | 'payment.request'
  | 'prescription.sent';

export type Channel = 'alimtalk' | 'fcm' | 'sms' | 'email';

/** Dispatcher 우선순위 — 먼저 성공하는 채널에서 종료 */
export const CHANNEL_PRIORITY: Channel[] = ['alimtalk', 'fcm', 'sms', 'email'];

export interface NotificationEvent {
  type: NotificationEventType;
  hospitalId: string;
  targetUid: string;
  actorUid?: string;
  /** 템플릿 변수 치환용 */
  vars: Record<string, string | number>;
  /** 중복 발송 방지 키. 동일 key 로 재요청 시 dispatcher 가 skip. */
  idempotencyKey?: string;
}

export interface SendResult {
  channel: Channel;
  status: 'sent' | 'failed' | 'skipped';
  providerMessageId?: string;
  errorCode?: string;
  errorMessage?: string;
  at: number;
}

export interface DispatchOutcome {
  /** 최종 성공한 채널. 모두 실패하면 null. */
  deliveredChannel: Channel | null;
  attempts: SendResult[];
  logId: string | null;
  /** 멱등성 키 중복으로 기존 로그만 반환했을 때 true */
  duplicateOfLogId?: string;
}

export interface NotificationLogEntry {
  event: NotificationEvent;
  attempts: SendResult[];
  finalStatus: 'delivered' | 'failed' | 'duplicate';
  deliveredChannel?: Channel;
  createdAt: number;
  updatedAt: number;
}

export interface UserNotificationPrefs {
  channels?: Partial<Record<Channel, boolean>>;
  scenarios?: Partial<Record<NotificationEventType, boolean>>;
  /** 철회 시각 (PIPA 대응) */
  revokedAt?: number;
  updatedAt?: number;
}

/** Adapter 가 템플릿에서 받는 렌더된 content */
export interface RenderedContent {
  /** 간결 제목 (FCM notification title / 이메일 subject 등) */
  title: string;
  /** 본문 */
  body: string;
  /** 채널별 payload (예: FCM data, 알림톡 template code + buttons) */
  extras?: Record<string, unknown>;
}
