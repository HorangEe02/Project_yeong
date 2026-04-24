import * as admin from 'firebase-admin';
import { onSchedule } from 'firebase-functions/v2/scheduler';
import { buildDefaultDispatcher } from '../notifications/factory';

/**
 * 10분마다 실행되는 스케줄러 — 현재 시각에서 55~65분 후에 예약된
 * `status==='scheduled'` + `reminderSent !== true` 항목에 리마인더 발송.
 *
 * 윈도우 설계:
 *  - 10분 주기 + 10분 윈도우 폭(55~65min) → 이론상 각 예약이 정확히 1회 커버
 *  - `reminderSent` flag 를 true 로 set → 중복 발송 차단 (idempotency 이중 안전장치)
 *  - dispatcher 의 idempotencyKey 도 병행 (재기동·클락 드리프트 안전)
 *
 * 비용: O(N_hospitals × N_appointments). demo 규모에서 무시할 수준.
 * 대규모 이행 시 appointments_by_time 인덱스 path 추가 고려.
 */
export const appointmentReminderScheduler = onSchedule(
  {
    schedule: 'every 10 minutes',
    region: 'asia-northeast3',
    timeZone: 'Asia/Seoul',
  },
  async () => {
    const db = admin.database();
    const now = Date.now();
    const windowStart = now + 55 * 60 * 1000;
    const windowEnd = now + 65 * 60 * 1000;

    const hospSnap = await db.ref('hospitals').get();
    if (!hospSnap.exists()) return;

    const dispatcher = buildDefaultDispatcher();
    const tasks: Array<Promise<void>> = [];

    hospSnap.forEach((hospChild) => {
      const hospitalId = hospChild.key;
      if (!hospitalId) return false;
      const apptsNode = hospChild.child('appointments');
      apptsNode.forEach((apptChild) => {
        const a = apptChild.val() as {
          patientUid?: string;
          department?: string;
          scheduledAt?: number;
          status?: string;
          reminderSent?: boolean;
        } | null;
        const apptId = apptChild.key;
        if (!apptId || !a) return false;
        if (a.status !== 'scheduled') return false;
        if (a.reminderSent === true) return false;
        if (!a.patientUid || !a.department || typeof a.scheduledAt !== 'number') {
          return false;
        }
        if (a.scheduledAt < windowStart || a.scheduledAt > windowEnd) return false;

        tasks.push(
          (async () => {
            // 환자 name 조회 (실패 fallback)
            let name = '환자';
            try {
              const p = await db.ref(`users/${a.patientUid}`).get();
              const profile = p.val() as { displayName?: string } | null;
              if (profile?.displayName) name = profile.displayName;
            } catch {
              /* ignore */
            }

            await dispatcher.send({
              type: 'appointment.reminder',
              hospitalId,
              targetUid: a.patientUid as string,
              vars: { name, department: a.department as string },
              idempotencyKey: `appointment-reminder:${apptId}`,
            });
            // reminderSent flag 기록 — 다음 주기에서 재발송 차단
            await db
              .ref(`hospitals/${hospitalId}/appointments/${apptId}/reminderSent`)
              .set(true);
          })().catch((err) => {
            console.warn(
              `[appointmentReminderScheduler] appt=${apptId} 발송 실패`,
              err,
            );
          }),
        );
        return false;
      });
      return false;
    });

    await Promise.all(tasks);
    console.log(`[appointmentReminderScheduler] processed ${tasks.length} tasks`);
  },
);
