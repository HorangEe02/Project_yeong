import { onValue, push, ref, update } from 'firebase/database';
import { db, isFirebaseConfigured } from '@/config/firebase';
import type {
  Appointment,
  AppointmentPatientIndex,
  AppointmentStatus,
} from '@/types/appointment';

/**
 * `/hospitals/{hospitalId}/appointments_by_patient/{uid}` 실시간 구독.
 * 콜백 인자: scheduledAt 오름차순으로 정렬된 리스트 (비어있으면 []).
 *
 * 환자 본인 이 자기 것 read 가능 (rule 상). staff/admin 은 해당 병원 환자 record 도 read.
 */
export function subscribeMyAppointments(
  hospitalId: string,
  uid: string,
  onData: (entries: AppointmentPatientIndex[]) => void,
  onError?: (err: Error) => void,
): () => void {
  if (!isFirebaseConfigured()) {
    onData([]);
    return () => {};
  }

  const path = `hospitals/${hospitalId}/appointments_by_patient/${uid}`;
  const unsubscribe = onValue(
    ref(db, path),
    (snap) => {
      const val = snap.val() as Record<string, Omit<AppointmentPatientIndex, 'id'>> | null;
      if (!val) {
        onData([]);
        return;
      }
      const list: AppointmentPatientIndex[] = Object.entries(val)
        .map(([id, v]) => ({ id, ...v }))
        .sort((a, b) => a.scheduledAt - b.scheduledAt);
      onData(list);
    },
    (err) => {
      console.error('[appointments] subscription error:', err);
      onError?.(err as Error);
    },
  );
  return unsubscribe;
}

export interface CreateAppointmentInput {
  department: string;
  /** epoch ms */
  scheduledAt: number;
  durationMin: number;
  staffUid?: string;
  notes?: string;
}

/**
 * 예약 생성. 두 path 에 dual-write:
 *  - `/hospitals/{hid}/appointments/{id}`                → full record
 *  - `/hospitals/{hid}/appointments_by_patient/{uid}/{id}` → subset index
 *
 * id 는 `push()` 로 생성된 stable key. 반환 값은 생성된 full Appointment.
 *
 * 유효성 (호출 전 UI에서 검증 필수):
 *  - department 비지 않음 (trim 후)
 *  - scheduledAt 은 현재 시각 이후 (UI 경고만 — 서버 기록은 허용)
 *  - durationMin > 0
 */
export async function createAppointment(
  hospitalId: string,
  patientUid: string,
  input: CreateAppointmentInput,
): Promise<Appointment> {
  if (!isFirebaseConfigured()) throw new Error('Firebase 미설정');
  const department = input.department.trim();
  if (!department) throw new Error('부서명이 비어 있습니다');
  if (!input.scheduledAt || !Number.isFinite(input.scheduledAt)) {
    throw new Error('예약 일시가 유효하지 않습니다');
  }
  if (!input.durationMin || input.durationMin <= 0) {
    throw new Error('진료 시간이 유효하지 않습니다');
  }

  const id = push(ref(db, `hospitals/${hospitalId}/appointments`)).key;
  if (!id) throw new Error('예약 id 생성 실패');

  const now = Date.now();
  const full: Appointment = {
    id,
    hospitalId,
    patientUid,
    department,
    scheduledAt: input.scheduledAt,
    durationMin: input.durationMin,
    status: 'scheduled',
    createdAt: now,
    updatedAt: now,
    ...(input.staffUid ? { staffUid: input.staffUid } : {}),
    ...(input.notes ? { notes: input.notes } : {}),
  };
  const index: Omit<AppointmentPatientIndex, 'id'> = {
    scheduledAt: full.scheduledAt,
    status: full.status,
    department: full.department,
  };

  await update(ref(db), {
    [`hospitals/${hospitalId}/appointments/${id}`]: full,
    [`hospitals/${hospitalId}/appointments_by_patient/${patientUid}/${id}`]: index,
  });
  return full;
}

/**
 * 예약 취소 — status `cancelled` + updatedAt 갱신. Full record 와 patient index 동시 업데이트.
 * 완료(`completed`)로 이미 전이된 예약에 대한 취소는 서버 규칙이 받을 순 있으나 UI 에서 차단.
 */
export async function cancelAppointment(
  hospitalId: string,
  patientUid: string,
  appointmentId: string,
): Promise<void> {
  if (!isFirebaseConfigured()) throw new Error('Firebase 미설정');
  const now = Date.now();
  const nextStatus: AppointmentStatus = 'cancelled';
  await update(ref(db), {
    [`hospitals/${hospitalId}/appointments/${appointmentId}/status`]: nextStatus,
    [`hospitals/${hospitalId}/appointments/${appointmentId}/updatedAt`]: now,
    [`hospitals/${hospitalId}/appointments_by_patient/${patientUid}/${appointmentId}/status`]: nextStatus,
  });
}
