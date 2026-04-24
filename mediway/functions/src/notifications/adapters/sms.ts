import type { SenderAdapter } from './base';
import type { Channel, NotificationEvent, RenderedContent, SendResult } from '../types';

/**
 * SMS adapter — **F5a stub**.
 *
 * F5e 에서 실제 연결 예정 (NHN Toast SMS / Aligo / CoolSMS 등).
 * Secret Manager: `SMS_API_KEY`, `SMS_SENDER_NUMBER`.
 *
 * 현재는 항상 `not_configured` 로 throw.
 */
export class SmsAdapter implements SenderAdapter {
  readonly channel: Channel = 'sms';

  async send(
    _targetUid: string,
    _content: RenderedContent,
    _event: NotificationEvent,
  ): Promise<SendResult> {
    throw new Error('sms_not_configured');
  }
}
