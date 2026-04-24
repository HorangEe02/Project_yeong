import type { Channel, NotificationEvent, RenderedContent, SendResult } from '../types';

/**
 * 채널별 sender adapter 가 구현할 공통 인터페이스.
 *
 * Dispatcher 는 동일 시그니처로 각 채널을 시도한다.
 * 성공 시 `sent` + providerMessageId 반환 권장 (감사 추적용).
 * 실패는 Error throw — dispatcher 가 catch 해서 `failed` 결과로 기록한다.
 */
export interface SenderAdapter {
  readonly channel: Channel;
  /**
   * 단일 수신자에게 발송.
   * @throws 발송 실패 시 Error (dispatcher 가 cascade 를 위해 catch).
   */
  send(
    targetUid: string,
    content: RenderedContent,
    event: NotificationEvent,
  ): Promise<SendResult>;
}
