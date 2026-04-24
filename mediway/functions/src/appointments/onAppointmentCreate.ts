import * as admin from 'firebase-admin';
import { onValueCreated } from 'firebase-functions/v2/database';
import { buildDefaultDispatcher } from '../notifications/factory';

/**
 * 예약 생성 시 환자에게 '예약 확인' 알림 발송.
 *
 * 트리거: `/hospitals/{hospitalId}/appointments/{appointmentId}` onCreate
 * 조건: data.status === 'scheduled' AND patientUid/department/scheduledAt 존재
 *
 * Idempotency: appointment id 고정 → 재시도/중복 생성 시에도 한 번만 발송.
 */
export const onAppointmentCreate = onValueCreated(
  {
    ref: '/hospitals/{hospitalId}/appointments/{appointmentId}',
    // RTDB trigger 는 asia-northeast3 미지원 — onQueueCall 과 동일 us-central1 사용
    region: 'us-central1',
  },
  async (event) => {
    const data = event.data.val() as {
      patientUid?: string;
      department?: string;
      scheduledAt?: number;
      status?: string;
    } | null;
    if (!data?.patientUid || !data.department || typeof data.scheduledAt !== 'number') {
      return;
    }
    if (data.status !== 'scheduled') return;

    const { hospitalId, appointmentId } = event.params;
    const db = admin.database();

    // 환자 displayName 조회 (실패해도 fallback)
    let name = '환자';
    try {
      const profileSnap = await db.ref(`users/${data.patientUid}`).get();
      const profile = profileSnap.val() as { displayName?: string } | null;
      if (profile?.displayName) name = profile.displayName;
    } catch (err) {
      console.warn('[onAppointmentCreate] profile 조회 실패 — name fallback', err);
    }

    // KST 기준 날짜/시각 포맷
    const kst = new Date(data.scheduledAt + 9 * 60 * 60 * 1000);
    const dateStr = kst.toISOString().slice(0, 10);
    const timeStr = kst.toISOString().slice(11, 16);

    const dispatcher = buildDefaultDispatcher();
    const outcome = await dispatcher.send({
      type: 'appointment.confirmed',
      hospitalId: String(hospitalId),
      targetUid: data.patientUid,
      vars: { name, date: dateStr, time: timeStr, department: data.department },
      idempotencyKey: `appointment-confirmed:${appointmentId}`,
    });

    console.log(
      `[onAppointmentCreate] hospital=${hospitalId} appt=${appointmentId} ` +
        `patient=${data.patientUid} delivered=${outcome.deliveredChannel ?? 'none'} ` +
        `attempts=${outcome.attempts.length}`,
    );
  },
);
