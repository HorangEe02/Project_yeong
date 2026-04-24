import type { SenderAdapter } from './base';
import type { Channel, NotificationEvent, RenderedContent, SendResult } from '../types';

/**
 * 카카오 알림톡 adapter — **F5a stub**.
 *
 * F5d 에서 실제 연결 예정:
 *  - 카카오 비즈메시지 API (톡비즈) 또는 Aligo / Lunasoft 재판매
 *  - 템플릿 심사 완료 후 `alimtalkCode` 매핑해 API 호출
 *  - Secret Manager: `KAKAO_ALIMTALK_API_KEY`, `KAKAO_SENDER_KEY`
 *
 * 현재는 항상 `not_configured` 로 throw 하여 dispatcher 가 다음 채널 (FCM) 로 cascade.
 */
export class AlimtalkAdapter implements SenderAdapter {
  readonly channel: Channel = 'alimtalk';

  async send(
    _targetUid: string,
    _content: RenderedContent,
    _event: NotificationEvent,
  ): Promise<SendResult> {
    throw new Error('alimtalk_not_configured');
  }
}
