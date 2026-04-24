import * as admin from 'firebase-admin';
import { onValueUpdated } from 'firebase-functions/v2/database';
import { appendAuditLog } from '../util/auditLog';

/**
 * 대기열 엔트리 status가 'called'로 전환될 때 해당 환자에게 FCM push 발송.
 *
 * 트리거: `/hospitals/{hospitalId}/wait_queue/{department}/{date}/{queueNumber}` update
 * 발송 조건: before.status !== 'called' && after.status === 'called'
 * 토큰 출처: `/user_fcm_tokens/{patientUid}/*`
 * 로그: sent/failed 카운트
 * 에러 처리: 무효 토큰은 자동 제거
 *
 * 권한 모델 주의: Admin SDK로 실행되므로 RTDB rules를 우회한다. 함수 자체가 staff의
 *   wait_queue write(.write 규칙)로만 트리거되므로 권한 검증은 rule layer에 위임.
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

    const db = admin.database();
    const tokensSnap = await db.ref(`user_fcm_tokens/${patientUid}`).get();
    const tokens = tokensSnap.val() as Record<
      string,
      { token: string; createdAt?: number }
    > | null;
    if (!tokens) {
      console.log(
        `[onQueueCall] no FCM tokens for patient=${patientUid} queue=${department}/${queueNumber}`,
      );
      return;
    }

    const messaging = admin.messaging();
    let sent = 0;
    let failed = 0;
    const removalPromises: Array<Promise<void>> = [];

    for (const [tokenKey, entry] of Object.entries(tokens)) {
      if (!entry?.token) continue;
      try {
        await messaging.send({
          token: entry.token,
          notification: {
            title: '호출되었습니다',
            body: `${department} ${after.queueNumber ?? queueNumber}번 환자님, 진료실로 이동해 주세요.`,
          },
          data: {
            type: 'queue_call',
            hospitalId: String(hospitalId),
            department: String(department),
            date: String(date),
            queueNumber: String(queueNumber),
          },
          webpush: {
            notification: {
              icon: '/favicon-256.png',
              requireInteraction: true,
            },
          },
        });
        sent += 1;
      } catch (err) {
        failed += 1;
        const code = (err as { code?: string }).code;
        console.warn(`[onQueueCall] FCM 발송 실패 uid=${patientUid} token=${tokenKey} code=${code}`);
        // 토큰 등록 해제된 경우 정리
        if (
          code === 'messaging/registration-token-not-registered' ||
          code === 'messaging/invalid-registration-token'
        ) {
          removalPromises.push(
            db.ref(`user_fcm_tokens/${patientUid}/${tokenKey}`).remove(),
          );
        }
      }
    }

    await Promise.all(removalPromises);

    console.log(
      `[onQueueCall] hospital=${hospitalId} dept=${department} patient=${patientUid} queueNumber=${queueNumber} sent=${sent} failed=${failed}`,
    );

    // audit — dual-write (T1-1b): legacy /audit_logs + nested /audit_logs_v2/{hid}
    await appendAuditLog(db, String(hospitalId), {
      actorUid: 'system:onQueueCall',
      action: 'wait_queue.call.push',
      target: patientUid,
      meta: {
        hospitalId,
        department,
        date,
        queueNumber,
        sent,
        failed,
      },
      timestamp: Date.now(),
    });
  },
);
