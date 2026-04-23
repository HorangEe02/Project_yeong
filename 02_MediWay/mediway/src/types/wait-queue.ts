/** 대기 순번 상태 전이: waiting → called → in-progress → completed (또는 cancelled) */
export type QueueStatus =
  | 'waiting'
  | 'called'
  | 'in-progress'
  | 'completed'
  | 'cancelled';

/**
 * 대기 엔트리 (RTDB: `/hospitals/{hospitalId}/wait_queue/{department}/{date}/{entryId}`)
 *
 * 역인덱스: `/hospitals/{hospitalId}/wait_queue_by_patient/{uid}/{entryId}`
 *   → { department, date, number, status } (환자 홈 위젯 구독용)
 *
 * 순번 카운터: `/hospitals/{hospitalId}/wait_queue_counters/{department}/{date}`
 *   → { current: number } (runTransaction으로 증가)
 */
export interface WaitEntry {
  id: string;
  hospitalId: string;
  department: string;
  /** 진료 날짜 YYYY-MM-DD (KST 기준) */
  date: string;
  /** 부서·날짜 내 순번 (1부터) */
  number: number;
  patientUid: string;
  /** 연결된 예약 (선택) */
  appointmentId?: string;
  status: QueueStatus;
  /** 의료진이 호출한 시각 */
  calledAt?: number;
  /** 진료 시작 시각 */
  startedAt?: number;
  /** 완료/취소 시각 */
  completedAt?: number;
  createdAt: number;
}

/** 환자별 역인덱스 entry (경량) */
export interface WaitEntryIndex {
  department: string;
  date: string;
  number: number;
  status: QueueStatus;
}

/** enqueue 입력 */
export interface EnqueueInput {
  department: string;
  /** YYYY-MM-DD, 생략 시 오늘(KST) */
  date?: string;
  appointmentId?: string;
}

/** 활성 상태 (대기 중이거나 호출·진료 중) */
export function isActiveStatus(status: QueueStatus): boolean {
  return status === 'waiting' || status === 'called' || status === 'in-progress';
}
