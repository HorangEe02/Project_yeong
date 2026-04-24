import { get, onValue, push, ref, runTransaction, update } from 'firebase/database';
import { db, isFirebaseConfigured } from '@/config/firebase';
import type {
  WaitQueueEntry,
  WaitQueuePatientIndex,
  WaitQueueStatus,
} from '@/types/waitQueue';

/**
 * KST(UTC+9) 기준 오늘 날짜를 `'YYYY-MM-DD'` 형식으로 반환.
 *
 * 계산 방식: UTC 시각에 +9시간 오프셋을 더한 뒤 `toISOString().slice(0, 10)`.
 * 이는 서버 함수 `wait_queue` 경로에서 쓰는 날짜와 동일하다 (prod 번들 `ag` 함수 동일 식).
 *
 * @example
 * ```ts
 * // 실제 브라우저 환경에서 (KST 기준)
 * todayDateKST() // '2026-04-24'
 * ```
 */
export function todayDateKST(now: Date = new Date()): string {
  const kst = new Date(now.getTime() + 9 * 60 * 60 * 1000);
  return kst.toISOString().slice(0, 10);
}

/**
 * `/hospitals/{hospitalId}/wait_queue_by_patient/{uid}` 실시간 구독.
 *
 * 콜백에 전달되는 리스트는 `number` 오름차순 정렬. 데이터 없으면 빈 배열.
 *
 * 권한:
 * - 환자 본인만 read 가능 (`auth.uid === uid`).
 * - 접수 이후 서버 트리거 `onQueueCall` + staff 액션이 이 path 의 status 를 실시간 갱신한다.
 *
 * 주의: local `database.rules.json` 에는 이 path 의 rule 이 명시돼 있지 않다. 반면
 *   LIVE Firebase(v3 rules) 에는 존재 → 실 Firebase 대상 호출은 성공, 로컬 emulator
 *   만 돌릴 땐 denied 가능. rule 파일 동기화는 별도 sprint (T0-1 범위 밖).
 */
export function subscribeMyWaitQueue(
  hospitalId: string,
  uid: string,
  onData: (entries: WaitQueuePatientIndex[]) => void,
  onError?: (err: Error) => void,
): () => void {
  if (!isFirebaseConfigured()) {
    onData([]);
    return () => {};
  }

  const path = `hospitals/${hospitalId}/wait_queue_by_patient/${uid}`;
  const unsubscribe = onValue(
    ref(db, path),
    (snap) => {
      const val = snap.val() as Record<string, Omit<WaitQueuePatientIndex, 'id'>> | null;
      if (!val) {
        onData([]);
        return;
      }
      const list: WaitQueuePatientIndex[] = Object.entries(val)
        .map(([id, v]) => ({ id, ...v }))
        .sort((a, b) => a.number - b.number);
      onData(list);
    },
    (err) => {
      console.error('[waitQueue] subscription error:', err);
      onError?.(err as Error);
    },
  );
  return unsubscribe;
}

/**
 * 위젯이 "가장 먼저 보여줘야 할" 단일 엔트리를 고른다.
 *
 * 필터: `date === today` & `status !== completed/cancelled`
 * 정렬 우선순위 (환자 행동 urgency 순):
 *   called (진료실로 이동해야 함)
 *   > in-progress (이미 진료실 안)
 *   > waiting (그냥 대기)
 *
 * 여러 부서 동시 접수(예: 내과 + 정형외과)인 경우 urgency 가 같으면 number 오름차순.
 */
export function selectPrimaryActive(
  entries: WaitQueuePatientIndex[],
  today: string,
): WaitQueuePatientIndex | null {
  const URGENCY: Record<WaitQueueStatus, number> = {
    called: 0,
    'in-progress': 1,
    waiting: 2,
    completed: 99,
    cancelled: 99,
  };
  const active = entries
    .filter((e) => e.date === today && e.status !== 'completed' && e.status !== 'cancelled')
    .sort((a, b) => {
      const d = URGENCY[a.status] - URGENCY[b.status];
      return d !== 0 ? d : a.number - b.number;
    });
  return active[0] ?? null;
}

// =====================================================================
// Staff-side — 의료진이 쓰는 대기열 관리 함수들
// 권한: RTDB rule이 staff|admin of same hospital OR platformAdmin 만 허용.
// prod 번들의 fg / cg / lg / ug 함수와 동일 schema/semantics.
// =====================================================================

interface SubscribeDeptQueueOptions {
  /** true면 completed/cancelled 엔트리도 포함 (default: false) */
  includeCompleted?: boolean;
}

/**
 * `/hospitals/{hospitalId}/wait_queue/{department}/{date}` 실시간 구독.
 * 의료진 콘솔에서 해당 부서·날짜의 모든 엔트리를 보기 위한 용도.
 *
 * 기본 필터: completed / cancelled 제외.
 * 정렬: number 오름차순 (먼저 접수된 순).
 */
export function subscribeDeptQueue(
  hospitalId: string,
  department: string,
  date: string,
  onData: (entries: WaitQueueEntry[]) => void,
  onError?: (err: Error) => void,
  opts: SubscribeDeptQueueOptions = {},
): () => void {
  if (!isFirebaseConfigured()) {
    onData([]);
    return () => {};
  }
  const path = `hospitals/${hospitalId}/wait_queue/${department}/${date}`;
  const unsubscribe = onValue(
    ref(db, path),
    (snap) => {
      const val = snap.val() as Record<string, WaitQueueEntry> | null;
      if (!val) {
        onData([]);
        return;
      }
      const list = Object.values(val)
        .filter((e) =>
          opts.includeCompleted
            ? true
            : e.status !== 'completed' && e.status !== 'cancelled',
        )
        .sort((a, b) => a.number - b.number);
      onData(list);
    },
    (err) => {
      console.error('[waitQueue] dept subscription error:', err);
      onError?.(err as Error);
    },
  );
  return unsubscribe;
}

/**
 * 해당 부서·날짜에서 **아직 waiting** 인 가장 낮은 number 엔트리를 `called` 로 전이.
 *
 * 구현:
 *   1) `/hospitals/{hid}/wait_queue/{dept}/{date}` 한 번 get
 *   2) Object.values → filter(status === 'waiting') → sort by number → [0]
 *   3) 해당 엔트리의 `status=called` + `calledAt=now` 를 wait_queue 와
 *      wait_queue_by_patient 양쪽에 멀티-update (dual-write).
 *   4) 업데이트된 엔트리 객체 반환 (호출 없음 시 null)
 *
 * 주의: 읽기-수정-쓰기 사이 race 가능성 — 두 staff 가 동시에 호출하면
 *   같은 환자를 두 번 호출할 수 있음. prod 번들(`cg`)도 동일한 단순 패턴이라
 *   parity 우선. 필요 시 후속에서 transaction 으로 강화.
 *
 * FCM push 는 onQueueCall 서버 트리거가 담당 (status 'called' 감지 시 발송).
 */
export async function callNextWaiting(
  hospitalId: string,
  department: string,
  date: string,
): Promise<WaitQueueEntry | null> {
  if (!isFirebaseConfigured()) return null;

  const snap = await get(ref(db, `hospitals/${hospitalId}/wait_queue/${department}/${date}`));
  if (!snap.exists()) return null;

  const val = snap.val() as Record<string, WaitQueueEntry>;
  const next = Object.values(val)
    .filter((e) => e.status === 'waiting')
    .sort((a, b) => a.number - b.number)[0];
  if (!next) return null;

  const now = Date.now();
  await update(ref(db), {
    [`hospitals/${hospitalId}/wait_queue/${department}/${date}/${next.id}/status`]: 'called',
    [`hospitals/${hospitalId}/wait_queue/${department}/${date}/${next.id}/calledAt`]: now,
    [`hospitals/${hospitalId}/wait_queue_by_patient/${next.patientUid}/${next.id}/status`]: 'called',
  });
  return { ...next, status: 'called', calledAt: now };
}

/**
 * 엔트리를 `in-progress` 로 전이 + `startedAt` 기록. dual-write.
 * 전제: 호출자가 해당 엔트리 객체를 가지고 있음 (subscribeDeptQueue 결과 카드).
 */
export async function markInProgress(
  hospitalId: string,
  entry: WaitQueueEntry,
): Promise<void> {
  if (!isFirebaseConfigured()) throw new Error('Firebase 미설정');
  const now = Date.now();
  await update(ref(db), {
    [`hospitals/${hospitalId}/wait_queue/${entry.department}/${entry.date}/${entry.id}/status`]: 'in-progress',
    [`hospitals/${hospitalId}/wait_queue/${entry.department}/${entry.date}/${entry.id}/startedAt`]: now,
    [`hospitals/${hospitalId}/wait_queue_by_patient/${entry.patientUid}/${entry.id}/status`]: 'in-progress',
  });
}

/**
 * 엔트리를 `completed` 로 전이 + `completedAt` 기록. dual-write.
 */
export async function markCompleted(
  hospitalId: string,
  entry: WaitQueueEntry,
): Promise<void> {
  if (!isFirebaseConfigured()) throw new Error('Firebase 미설정');
  const now = Date.now();
  await update(ref(db), {
    [`hospitals/${hospitalId}/wait_queue/${entry.department}/${entry.date}/${entry.id}/status`]: 'completed',
    [`hospitals/${hospitalId}/wait_queue/${entry.department}/${entry.date}/${entry.id}/completedAt`]: now,
    [`hospitals/${hospitalId}/wait_queue_by_patient/${entry.patientUid}/${entry.id}/status`]: 'completed',
  });
}

// =====================================================================
// Patient-side check-in (접수) — prod 번들 `sg` 함수 동일 스키마.
// Rules (2026-04-24 edbe495 배포 이후) 가 환자 self write 허용.
// =====================================================================

export interface CheckInInput {
  department: string;
  /** KST YYYY-MM-DD — 기본값 오늘 */
  date?: string;
  /** 선택: 원본 예약 id (있으면 wait_queue 엔트리에 연결 기록) */
  appointmentId?: string;
}

/**
 * 환자가 외래 예약에 대해 **접수**를 수행.
 *
 * 동작:
 *  1) `/hospitals/{hid}/wait_queue_counters/{dept}/{date}/current` 에 transaction 으로
 *     current += 1 (없으면 1) — 부서·날짜별 순번 할당.
 *  2) `push()` 로 entryId 생성.
 *  3) multi-update (원자):
 *     - `/hospitals/{hid}/wait_queue/{dept}/{date}/{entryId}` = full entry
 *     - `/hospitals/{hid}/wait_queue_by_patient/{uid}/{entryId}` = index subset
 *  4) 생성된 WaitQueueEntry 반환.
 *
 * 권한 (2026-04-24 rules 기준):
 *  - wait_queue_counters: hospitalId 일치 유저 자유롭게 증분 (validate 로 +1 enforce)
 *  - wait_queue leaf: !data.exists() + patientUid===auth.uid + status=waiting +
 *    department/date/hospitalId path match → 환자 본인만 신규 생성
 *  - wait_queue_by_patient: 본인 $uid 에 자유 write
 *
 * UX:
 *  - AppointmentsTab 의 [접수] 버튼이 호출.
 *  - 성공 후 환자 홈 WaitQueueWidget 이 구독 중인 wait_queue_by_patient 에 새 엔트리
 *    반영 → 순번 즉시 표시.
 */
export async function checkInToQueue(
  hospitalId: string,
  patientUid: string,
  input: CheckInInput,
): Promise<WaitQueueEntry> {
  if (!isFirebaseConfigured()) throw new Error('Firebase 미설정');
  const department = input.department.trim();
  if (!department) throw new Error('부서명이 비어 있습니다');
  const date = input.date ?? todayDateKST();

  // 1) counter transaction
  const counterRef = ref(db, `hospitals/${hospitalId}/wait_queue_counters/${department}/${date}/current`);
  const tx = await runTransaction(counterRef, (current) =>
    (typeof current === 'number' ? current : 0) + 1,
  );
  if (!tx.committed) throw new Error('순번 할당 실패');
  const number = tx.snapshot.val() as number;

  // 2) generate entry id
  const entryRef = push(ref(db, `hospitals/${hospitalId}/wait_queue/${department}/${date}`));
  const entryId = entryRef.key;
  if (!entryId) throw new Error('엔트리 id 생성 실패');

  // 3) dual-write
  const now = Date.now();
  const entry: WaitQueueEntry = {
    id: entryId,
    hospitalId,
    department,
    date,
    number,
    patientUid,
    status: 'waiting',
    createdAt: now,
    ...(input.appointmentId ? { appointmentId: input.appointmentId } : {}),
  };
  const indexRow: Omit<WaitQueuePatientIndex, 'id'> = {
    department,
    date,
    number,
    status: 'waiting',
  };
  await update(ref(db), {
    [`hospitals/${hospitalId}/wait_queue/${department}/${date}/${entryId}`]: entry,
    [`hospitals/${hospitalId}/wait_queue_by_patient/${patientUid}/${entryId}`]: indexRow,
  });
  return entry;
}
