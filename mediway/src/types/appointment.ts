/**
 * 외래 예약 status 전이:
 *   scheduled → completed (정상 종료)
 *   scheduled → cancelled (취소)
 *
 * 접수(check-in)는 예약 status 를 바꾸지 않고 별도의 wait_queue 엔트리를 만든다.
 * 예약은 동일 시간대에 하나만 활성으로 유지되는 기록용 장부 역할.
 */
export type AppointmentStatus = 'scheduled' | 'cancelled' | 'completed';

/**
 * `/hospitals/{hid}/appointments/{id}` — 전체 예약 레코드.
 *
 * 쓰기: 본인 patientUid 와 hospitalId 가 일치하거나 staff/admin/platformAdmin.
 * 읽기: 본인, 혹은 해당 병원 staff/admin, 혹은 platformAdmin.
 */
export interface Appointment {
  id: string;
  hospitalId: string;
  patientUid: string;
  department: string;
  /** epoch ms — 예약 일시 (KST 기준 로컬 표시는 UI 계층에서) */
  scheduledAt: number;
  durationMin: number;
  status: AppointmentStatus;
  createdAt: number;
  updatedAt: number;
  /** 선택: 담당 의료진 uid */
  staffUid?: string;
  /** 선택: 환자 메모 */
  notes?: string;
}

/**
 * `/hospitals/{hid}/appointments_by_patient/{uid}/{id}` — 환자 index.
 *
 * 예약 생성 시 full record 와 함께 dual-write.
 * status 전이 (cancel/complete) 시 `status` 필드도 동기화.
 * widget/목록용 최소 subset — 상세는 full path에서 읽는다.
 */
export interface AppointmentPatientIndex {
  id: string;
  scheduledAt: number;
  status: AppointmentStatus;
  department: string;
}
