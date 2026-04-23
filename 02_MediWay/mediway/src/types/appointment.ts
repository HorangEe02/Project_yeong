/** 예약 상태 */
export type AppointmentStatus = 'scheduled' | 'cancelled' | 'completed';

/**
 * 외래 예약 (RTDB: `/hospitals/{hospitalId}/appointments/{apptId}`)
 *
 * 역인덱스: `/hospitals/{hospitalId}/appointments_by_patient/{uid}/{apptId}: { scheduledAt, status }`
 *   환자별 My 예약 조회용 lightweight lookup.
 */
export interface Appointment {
  id: string;
  hospitalId: string;
  patientUid: string;
  department: string;
  /** 의료진 지정 (선택) */
  staffUid?: string;
  /** 예약 시각 (Unix ms) */
  scheduledAt: number;
  /** 예상 소요 시간 (분) */
  durationMin: number;
  status: AppointmentStatus;
  notes?: string;
  createdAt: number;
  updatedAt: number;
}

/** 환자별 역인덱스 엔트리 (경량) */
export interface AppointmentIndexEntry {
  scheduledAt: number;
  status: AppointmentStatus;
  department: string;
}

/** 예약 생성 입력 */
export interface CreateAppointmentInput {
  department: string;
  scheduledAt: number;
  durationMin: number;
  staffUid?: string;
  notes?: string;
}
