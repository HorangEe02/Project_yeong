import type { SenderAdapter } from './adapters/base';
import { renderTemplate, templateSupports } from './templates';
import {
  createLogEntry,
  finalizeLog,
  findByIdempotencyKey,
  loadUserPrefs,
} from './logStore';
import type {
  Channel,
  CHANNEL_PRIORITY as CHANNEL_PRIORITY_T,
  DispatchOutcome,
  NotificationEvent,
  SendResult,
  UserNotificationPrefs,
} from './types';
import { CHANNEL_PRIORITY } from './types';
import type * as admin from 'firebase-admin';

/**
 * 알림 dispatcher — priority cascade 로 각 채널을 시도.
 *
 * 흐름:
 *   1. idempotencyKey 로 기존 로그 조회 → 발견 시 duplicate 반환 (발송 skip)
 *   2. 사용자 preferences 로드 (revokedAt 설정되어 있으면 전체 skip)
 *   3. 로그 엔트리 upfront 생성 (/notification_logs/{uid}/{pushId})
 *   4. CHANNEL_PRIORITY 순회:
 *      - pref 에서 해당 채널·시나리오가 disabled 면 skipped
 *      - 템플릿이 해당 채널 미지원이면 skipped
 *      - 렌더된 content 로 adapter.send() 시도
 *      - 성공 시 즉시 loop 종료 (deliveredChannel 기록)
 *      - 실패 시 Error 잡아서 failed 결과 축적 후 다음 채널
 *   5. 최종 attempts + deliveredChannel 로 log finalize
 *
 * 이 모듈은 pure infra — F5b 에서 기존 trigger (onQueueCall 등) 에서 호출해 사용.
 */

export function isChannelEnabled(
  prefs: UserNotificationPrefs,
  event: NotificationEvent,
  channel: Channel,
): boolean {
  if (prefs.revokedAt) return false;
  if (prefs.channels && prefs.channels[channel] === false) return false;
  if (prefs.scenarios && prefs.scenarios[event.type] === false) return false;
  return true;
}

export interface Dispatcher {
  send(event: NotificationEvent): Promise<DispatchOutcome>;
}

export function createDispatcher(
  db: admin.database.Database,
  adapters: Partial<Record<Channel, SenderAdapter>>,
  opts?: { priority?: Channel[] },
): Dispatcher {
  const priority: Channel[] = opts?.priority ?? [...CHANNEL_PRIORITY];
  return {
    async send(event: NotificationEvent): Promise<DispatchOutcome> {
      // 1) idempotency
      if (event.idempotencyKey) {
        const prev = await findByIdempotencyKey(db, event.targetUid, event.idempotencyKey);
        if (prev) {
          return {
            deliveredChannel: prev.entry.deliveredChannel ?? null,
            attempts: prev.entry.attempts,
            logId: prev.logId,
            duplicateOfLogId: prev.logId,
          };
        }
      }

      // 2) preferences
      const prefs = await loadUserPrefs(db, event.targetUid);

      // 3) create log entry upfront
      const { logId } = await createLogEntry(db, event);

      // 4) cascade
      const attempts: SendResult[] = [];
      let delivered: Channel | null = null;
      for (const channel of priority) {
        const adapter = adapters[channel];
        if (!adapter) {
          attempts.push({
            channel,
            status: 'skipped',
            errorCode: 'no_adapter',
            at: Date.now(),
          });
          continue;
        }
        if (!templateSupports(event.type, channel)) {
          attempts.push({
            channel,
            status: 'skipped',
            errorCode: 'template_unsupported',
            at: Date.now(),
          });
          continue;
        }
        if (!isChannelEnabled(prefs, event, channel)) {
          attempts.push({
            channel,
            status: 'skipped',
            errorCode: 'pref_disabled',
            at: Date.now(),
          });
          continue;
        }
        const content = renderTemplate(event.type, channel, event.vars);
        if (!content) {
          attempts.push({
            channel,
            status: 'skipped',
            errorCode: 'render_failed',
            at: Date.now(),
          });
          continue;
        }
        try {
          const result = await adapter.send(event.targetUid, content, event);
          attempts.push(result);
          if (result.status === 'sent') {
            delivered = channel;
            break;
          }
        } catch (err) {
          attempts.push({
            channel,
            status: 'failed',
            errorMessage: err instanceof Error ? err.message : String(err),
            at: Date.now(),
          });
        }
      }

      // 5) finalize
      await finalizeLog(db, event.targetUid, logId, attempts, delivered);

      return { deliveredChannel: delivered, attempts, logId };
    },
  };
}

export type { CHANNEL_PRIORITY_T };
