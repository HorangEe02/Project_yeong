import type * as admin from 'firebase-admin';
import type { SenderAdapter } from './base';
import type { Channel, NotificationEvent, RenderedContent, SendResult } from '../types';

/**
 * Firebase Cloud Messaging adapter.
 *
 * 환자의 `/user_fcm_tokens/{uid}/*` 에 저장된 모든 토큰으로 send.
 * 무효 토큰은 감지 즉시 제거 (messaging/registration-token-not-registered 등).
 *
 * 기존 `onQueueCall` 의 FCM 발송 로직을 재사용 (dispatcher 통합 전 지점).
 */
export class FcmAdapter implements SenderAdapter {
  readonly channel: Channel = 'fcm';

  constructor(
    private readonly db: admin.database.Database,
    private readonly messaging: admin.messaging.Messaging,
  ) {}

  async send(
    targetUid: string,
    content: RenderedContent,
    _event: NotificationEvent,
  ): Promise<SendResult> {
    const tokensSnap = await this.db.ref(`user_fcm_tokens/${targetUid}`).get();
    const tokens = tokensSnap.val() as Record<
      string,
      { token: string; createdAt?: number }
    > | null;
    if (!tokens) {
      throw new Error('no_fcm_tokens');
    }

    let sent = 0;
    let failed = 0;
    const removalPromises: Array<Promise<void>> = [];
    const providerMessageIds: string[] = [];

    for (const [tokenKey, entry] of Object.entries(tokens)) {
      if (!entry?.token) continue;
      try {
        const messageId = await this.messaging.send({
          token: entry.token,
          notification: { title: content.title, body: content.body },
          data: (content.extras ?? {}) as Record<string, string>,
          webpush: {
            notification: {
              icon: '/favicon-256.png',
              requireInteraction: true,
            },
          },
        });
        providerMessageIds.push(messageId);
        sent += 1;
      } catch (err) {
        failed += 1;
        const code = (err as { code?: string }).code;
        if (
          code === 'messaging/registration-token-not-registered' ||
          code === 'messaging/invalid-registration-token'
        ) {
          removalPromises.push(
            this.db.ref(`user_fcm_tokens/${targetUid}/${tokenKey}`).remove(),
          );
        }
      }
    }

    await Promise.all(removalPromises);

    if (sent === 0) {
      throw new Error(`fcm_all_failed:${failed}`);
    }
    return {
      channel: 'fcm',
      status: 'sent',
      providerMessageId: providerMessageIds.join(','),
      at: Date.now(),
    };
  }
}
