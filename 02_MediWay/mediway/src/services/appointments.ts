import {
  ref,
  get,
  push,
  update,
  onValue,
  type Unsubscribe,
} from 'firebase/database';
import { db, isFirebaseConfigured } from '@/config/firebase';
import type {
  Appointment,
  AppointmentIndexEntry,
  AppointmentStatus,
  CreateAppointmentInput,
} from '@/types/appointment';

/**
 * 외래 예약 서비스 — `/hospitals/{hid}/appointments/*`
 *
 * - 생성: main record + index 동시 write (atomic via update fan-out)
 * - 취소: status 전이 + index 동기 업데이트
 * - 환자 My 예약: index 구독 + main fetch
 */

/** 예약 생성 — main record + 환자 역인덱스 동시 write */
export async function createAppointment(
  hospitalId: string,
  patientUid: string,
  input: CreateAppointmentInput,
): Promise<Appointment> {
  if (!isFirebaseConfigured()) {
    throw new Error('Firebase 미설정');
  }
  const newKey = push(ref(db, `hospitals/${hospitalId}/appointments`)).key;
  if (!newKey) throw new Error('키 생성 실패');

  const now = Date.now();
  const appt: Appointment = {
    id: newKey,
    hospitalId,
    patientUid,
    department: input.department.trim(),
    scheduledAt: input.scheduledAt,
    durationMin: input.durationMin,
    status: 'scheduled',
    createdAt: now,
    updatedAt: now,
    ...(input.staffUid ? { staffUid: input.staffUid } : {}),
    ...(input.notes ? { notes: input.notes } : {}),
  };

  const indexEntry: AppointmentIndexEntry = {
    scheduledAt: appt.scheduledAt,
    status: appt.status,
    department: appt.department,
  };

  const fanOut: Record<string, unknown> = {
    [`hospitals/${hospitalId}/appointments/${newKey}`]: appt,
    [`hospitals/${hospitalId}/appointments_by_patient/${patientUid}/${newKey}`]:
      indexEntry,
  };
  await update(ref(db), fanOut);
  return appt;
}

/** 예약 취소 — status='cancelled' 전이 + index 동기화 */
export async function cancelAppointment(
  hospitalId: string,
  patientUid: string,
  apptId: string,
): Promise<void> {
  if (!isFirebaseConfigured()) throw new Error('Firebase 미설정');
  const now = Date.now();
  const fanOut: Record<string, unknown> = {
    [`hospitals/${hospitalId}/appointments/${apptId}/status`]: 'cancelled',
    [`hospitals/${hospitalId}/appointments/${apptId}/updatedAt`]: now,
    [`hospitals/${hospitalId}/appointments_by_patient/${patientUid}/${apptId}/status`]:
      'cancelled',
  };
  await update(ref(db), fanOut);
}

/** 예약 단건 조회 */
export async function getAppointment(
  hospitalId: string,
  apptId: string,
): Promise<Appointment | null> {
  if (!isFirebaseConfigured()) return null;
  const snap = await get(
    ref(db, `hospitals/${hospitalId}/appointments/${apptId}`),
  );
  return snap.exists() ? (snap.val() as Appointment) : null;
}

/**
 * 환자 My 예약 목록 실시간 구독.
 * 역인덱스 onValue → entry 배열 반환.
 * 상세(Appointment)가 필요하면 consumer가 getAppointment로 fetch.
 */
export function subscribeMyAppointmentIndex(
  hospitalId: string,
  patientUid: string,
  onChange: (entries: Array<AppointmentIndexEntry & { id: string }>) => void,
  onError?: (e: Error) => void,
): Unsubscribe {
  if (!isFirebaseConfigured()) {
    onChange([]);
    return () => {};
  }
  return onValue(
    ref(db, `hospitals/${hospitalId}/appointments_by_patient/${patientUid}`),
    (snap) => {
      if (!snap.exists()) {
        onChange([]);
        return;
      }
      const raw = snap.val() as Record<string, AppointmentIndexEntry>;
      const list = Object.entries(raw)
        .map(([id, entry]) => ({ id, ...entry }))
        .sort((a, b) => a.scheduledAt - b.scheduledAt);
      onChange(list);
    },
    (err) => onError?.(err),
  );
}

/** 현재 status가 취소 가능한 상태인지 */
export function isCancellable(status: AppointmentStatus): boolean {
  return status === 'scheduled';
}
