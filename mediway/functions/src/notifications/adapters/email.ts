import type { SenderAdapter } from './base';
import type { Channel, NotificationEvent, RenderedContent, SendResult } from '../types';

/**
 * Email adapter — **F5a stub**.
 *
 * F5e 에서 실제 연결 예정 (SendGrid / AWS SES / Mailgun).
 * Secret Manager: `EMAIL_API_KEY`.
 *
 * 현재는 항상 `not_configured` 로 throw.
 */
export class EmailAdapter implements SenderAdapter {
  readonly channel: Channel = 'email';

  async send(
    _targetUid: string,
    _content: RenderedContent,
    _event: NotificationEvent,
  ): Promise<SendResult> {
    throw new Error('email_not_configured');
  }
}
