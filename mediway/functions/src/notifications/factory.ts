import * as admin from 'firebase-admin';
import type { Channel } from './types';
import type { SenderAdapter } from './adapters/base';
import { FcmAdapter } from './adapters/fcm';
import { AlimtalkAdapter } from './adapters/alimtalk';
import { SmsAdapter } from './adapters/sms';
import { EmailAdapter } from './adapters/email';
import { createDispatcher, type Dispatcher } from './dispatcher';

/**
 * Dispatcher + adapter 세트를 생성. Functions 각 trigger 에서 재사용.
 *
 * F5a 기준:
 *  - fcm: 실제 구현 (messaging.send + 무효 토큰 제거)
 *  - alimtalk / sms / email: stub (not_configured 로 throw → cascade 로 다음 채널)
 *
 * 외부 API 연결 시점 (F5d/F5e) 에 adapter 구현체만 교체.
 */
export function buildDefaultDispatcher(): Dispatcher {
  const db = admin.database();
  const messaging = admin.messaging();
  const adapters: Partial<Record<Channel, SenderAdapter>> = {
    alimtalk: new AlimtalkAdapter(),
    fcm: new FcmAdapter(db, messaging),
    sms: new SmsAdapter(),
    email: new EmailAdapter(),
  };
  return createDispatcher(db, adapters);
}
