import * as admin from 'firebase-admin';
import { onValueUpdated } from 'firebase-functions/v2/database';
import { appendAuditLog } from '../util/auditLog';
import { buildDefaultDispatcher } from '../notifications/factory';

/**
 * 대기열 엔트리 status가 'called'로 전환될 때 NotificationDispatcher 로 환자에게 알림 발송.
 *
 * 트리거: `/hospitals/{hospitalId}/wait_queue/{department}/{date}/{queueNumber}` update
 * 발송 조건: before.status !== 'called' && after.status === 'called'
 *
 * F5b 이후: 직접 messaging.send 하지 않고 Dispatcher 에 위임 →
 *   alimtalk (stub, F5d 에서 real) → fcm (실제) → sms (stub) → email (stub) cascade.
 *   채널 실패 / 사용자 preference / 템플릿 미지원 등은 log 에 attempts 로 기록.
 *
 * 권한 모델: Admin SDK로 실행되므로 RTDB rules 우회. 함수 자체가 staff 의
 *   wait_queue write(.write 규칙)로만 트리거되므로 권한 검증은 rule layer 에 위임.
 */
export const onQueueCall = onValueUpdated(
  {
    ref: '/hospitals/{hospitalId}/wait_queue/{department}/{date}/{queueNumber}',
    region: 'us-central1',
  },
  async (event) => {
    const before = event.data.before.val() as { status?: string } | null;
    const after = event.data.after.val() as {
      status?: string;
      patientUid?: string;
      queueNumber?: number;
    } | null;
    if (!after) return;

    const wasCalledBefore = before?.status === 'called';
    const isCalledNow = after.status === 'called';
    if (wasCalledBefore || !isCalledNow) return;

    const patientUid = after.patientUid;
    if (!patientUid) {
      console.warn('[onQueueCall] patientUid missing — skip push', event.params);
      return;
    }

    const { hospitalId, department, date, queueNumber } = event.params;
    const dispatcher = buildDefaultDispatcher();

    const outcome = await dispatcher.send({
      type: 'queue.call',
      hospitalId: String(hospitalId),
      targetUid: patientUid,
      vars: {
        department: String(department),
        queueNumber: String(after.queueNumber ?? queueNumber),
        hospitalId: String(hospitalId),
        date: String(date),
      },
      idempotencyKey: `queue-call:${hospitalId}:${department}:${date}:${queueNumber}`,
    });

    console.log(
      `[onQueueCall] hospital=${hospitalId} dept=${department} patient=${patientUid} ` +
        `queueNumber=${queueNumber} delivered=${outcome.deliveredChannel ?? 'none'} ` +
        `attempts=${outcome.attempts.length}`,
    );

    // audit — dual-write (T1-1b)
    await appendAuditLog(admin.database(), String(hospitalId), {
      actorUid: 'system:onQueueCall',
      action: 'wait_queue.call.push',
      target: patientUid,
      meta: {
        hospitalId,
        department,
        date,
        queueNumber,
        deliveredChannel: outcome.deliveredChannel,
        attemptsCount: outcome.attempts.length,
        dispatchLogId: outcome.logId,
      },
      timestamp: Date.now(),
    });
  },
);
