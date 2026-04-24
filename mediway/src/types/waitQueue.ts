/**
 * 대기열 엔트리의 status 전이 (prod 번들 역엔지니어링으로 확인):
 *   waiting → called → in-progress → completed
 *   또는 waiting → cancelled (환자/의료진 취소)
 *
 * 'in-progress'는 하이픈 표기 — prod 번들 및 onQueueCall 함수와 동일 spelling.
 */
export type WaitQueueStatus =
  | 'waiting'
  | 'called'
  | 'in-progress'
  | 'completed'
  | 'cancelled';

/**
 * `/hospitals/{hid}/wait_queue/{department}/{date}/{entryId}` — 전체 엔트리.
 *
 * 쓰기: staff/admin of same hospital, 또는 platformAdmin.
 * 읽기 (parent): staff/admin of same hospital, 또는 platformAdmin. (환자는 불가)
 * 읽기 (leaf): 환자 본인 (`data.child('patientUid').val() === auth.uid`).
 *
 * entryId는 `push()` key (순번 아님 — `number` 필드에 순번 저장).
 */
export interface WaitQueueEntry {
  id: string;
  hospitalId: string;
  department: string;
  /** KST(UTC+9) 'YYYY-MM-DD' */
  date: string;
  /** 부서·날짜별 1부터 시작하는 순번 */
  number: number;
  patientUid: string;
  status: WaitQueueStatus;
  createdAt: number;
  /** 접수 시 원본 예약 id (선택) */
  appointmentId?: string;
  calledAt?: number;
  startedAt?: number;
  completedAt?: number;
}

/**
 * `/hospitals/{hid}/wait_queue_by_patient/{uid}/{entryId}` — 환자 본인 index.
 *
 * 접수 트랜잭션에서 wait_queue 엔트리와 함께 dual-write.
 * 상태 전이(호출/진료/완료/취소) 시 서버가 이 path 의 status 도 동기화한다.
 * 환자 widget 은 이 path 만 구독하면 된다 — wait_queue parent 는 read 불가.
 */
export interface WaitQueuePatientIndex {
  id: string;
  department: string;
  date: string;
  number: number;
  status: WaitQueueStatus;
}
