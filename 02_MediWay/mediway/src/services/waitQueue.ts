import {
  ref,
  get,
  push,
  update,
  onValue,
  runTransaction,
  type Unsubscribe,
} from 'firebase/database';
import { db, isFirebaseConfigured } from '@/config/firebase';
import type {
  WaitEntry,
  WaitEntryIndex,
  QueueStatus,
  EnqueueInput,
} from '@/types/wait-queue';

/**
 * 대기 순번 서비스 — `/hospitals/{hid}/wait_queue/*`
 *
 * 스키마 (P3 §4.1):
 *   main:    /hospitals/{hid}/wait_queue/{dept}/{date}/{entryId}
 *   index:   /hospitals/{hid}/wait_queue_by_patient/{uid}/{entryId}
 *   counter: /hospitals/{hid}/wait_queue_counters/{dept}/{date}
 *
 * 동시성:
 *   - 순번은 counter runTransaction으로 증가 (atomic)
 *   - entryId는 push key (충돌 없음)
 *   - main + index는 fan-out update (단일 write)
 */

/** 오늘 날짜 YYYY-MM-DD (KST 기준). Test 가능하도록 export. */
export function getTodayDateKst(now: Date = new Date()): string {
  const kst = new Date(now.getTime() + 9 * 60 * 60 * 1000);
  return kst.toISOString().slice(0, 10);
}

/** 부서·날짜 counter 경로 */
function counterPath(hid: string, dept: string, date: string): string {
  return `hospitals/${hid}/wait_queue_counters/${dept}/${date}`;
}

/**
 * 접수 — counter transaction 증가 후 main + index fan-out write.
 *
 * @throws Error Firebase 미설정 또는 transaction 실패 시
 */
export async function enqueue(
  hospitalId: string,
  patientUid: string,
  input: EnqueueInput,
): Promise<WaitEntry> {
  if (!isFirebaseConfigured()) throw new Error('Firebase 미설정');
  const department = input.department.trim();
  if (!department) throw new Error('부서명 필수');
  const date = input.date ?? getTodayDateKst();

  const counterRef = ref(db, `${counterPath(hospitalId, department, date)}/current`);
  const txResult = await runTransaction(counterRef, (current) => {
    return (typeof current === 'number' ? current : 0) + 1;
  });
  if (!txResult.committed) throw new Error('순번 할당 실패');
  const number = txResult.snapshot.val() as number;

  const newKey = push(
    ref(db, `hospitals/${hospitalId}/wait_queue/${department}/${date}`),
  ).key;
  if (!newKey) throw new Error('키 생성 실패');

  const now = Date.now();
  const entry: WaitEntry = {
    id: newKey,
    hospitalId,
    department,
    date,
    number,
    patientUid,
    status: 'waiting',
    createdAt: now,
    ...(input.appointmentId ? { appointmentId: input.appointmentId } : {}),
  };

  const indexEntry: WaitEntryIndex = {
    department,
    date,
    number,
    status: 'waiting',
  };

  await update(ref(db), {
    [`hospitals/${hospitalId}/wait_queue/${department}/${date}/${newKey}`]: entry,
    [`hospitals/${hospitalId}/wait_queue_by_patient/${patientUid}/${newKey}`]:
      indexEntry,
  });

  return entry;
}

/** 환자 본인 취소 — main + index status 동기화 */
export async function cancelMyEntry(
  hospitalId: string,
  patientUid: string,
  entry: Pick<WaitEntry, 'id' | 'department' | 'date'>,
): Promise<void> {
  if (!isFirebaseConfigured()) throw new Error('Firebase 미설정');
  const now = Date.now();
  await update(ref(db), {
    [`hospitals/${hospitalId}/wait_queue/${entry.department}/${entry.date}/${entry.id}/status`]:
      'cancelled',
    [`hospitals/${hospitalId}/wait_queue/${entry.department}/${entry.date}/${entry.id}/completedAt`]:
      now,
    [`hospitals/${hospitalId}/wait_queue_by_patient/${patientUid}/${entry.id}/status`]:
      'cancelled',
  });
}

/**
 * 의료진 "다음 환자 호출" — waiting 중 number 최소값을 called로 전환.
 * 호출된 entry 반환 (대기 없으면 null).
 */
export async function callNext(
  hospitalId: string,
  department: string,
  date: string,
): Promise<WaitEntry | null> {
  if (!isFirebaseConfigured()) return null;
  const snap = await get(
    ref(db, `hospitals/${hospitalId}/wait_queue/${department}/${date}`),
  );
  if (!snap.exists()) return null;
  const raw = snap.val() as Record<string, WaitEntry>;
  const waiting = Object.values(raw)
    .filter((e) => e.status === 'waiting')
    .sort((a, b) => a.number - b.number);
  const next = waiting[0];
  if (!next) return null;

  const now = Date.now();
  await update(ref(db), {
    [`hospitals/${hospitalId}/wait_queue/${department}/${date}/${next.id}/status`]:
      'called',
    [`hospitals/${hospitalId}/wait_queue/${department}/${date}/${next.id}/calledAt`]:
      now,
    [`hospitals/${hospitalId}/wait_queue_by_patient/${next.patientUid}/${next.id}/status`]:
      'called',
  });
  return { ...next, status: 'called', calledAt: now };
}

/** 진료 시작 — called → in-progress */
export async function startConsultation(
  hospitalId: string,
  entry: Pick<WaitEntry, 'id' | 'department' | 'date' | 'patientUid'>,
): Promise<void> {
  if (!isFirebaseConfigured()) throw new Error('Firebase 미설정');
  const now = Date.now();
  await update(ref(db), {
    [`hospitals/${hospitalId}/wait_queue/${entry.department}/${entry.date}/${entry.id}/status`]:
      'in-progress',
    [`hospitals/${hospitalId}/wait_queue/${entry.department}/${entry.date}/${entry.id}/startedAt`]:
      now,
    [`hospitals/${hospitalId}/wait_queue_by_patient/${entry.patientUid}/${entry.id}/status`]:
      'in-progress',
  });
}

/** 진료 완료 — any → completed */
export async function completeEntry(
  hospitalId: string,
  entry: Pick<WaitEntry, 'id' | 'department' | 'date' | 'patientUid'>,
): Promise<void> {
  if (!isFirebaseConfigured()) throw new Error('Firebase 미설정');
  const now = Date.now();
  await update(ref(db), {
    [`hospitals/${hospitalId}/wait_queue/${entry.department}/${entry.date}/${entry.id}/status`]:
      'completed',
    [`hospitals/${hospitalId}/wait_queue/${entry.department}/${entry.date}/${entry.id}/completedAt`]:
      now,
    [`hospitals/${hospitalId}/wait_queue_by_patient/${entry.patientUid}/${entry.id}/status`]:
      'completed',
  });
}

/** 단건 조회 */
export async function getEntry(
  hospitalId: string,
  department: string,
  date: string,
  entryId: string,
): Promise<WaitEntry | null> {
  if (!isFirebaseConfigured()) return null;
  const snap = await get(
    ref(db, `hospitals/${hospitalId}/wait_queue/${department}/${date}/${entryId}`),
  );
  return snap.exists() ? (snap.val() as WaitEntry) : null;
}

/**
 * 환자 자기 대기 엔트리 실시간 구독.
 * 역인덱스 onValue → number 오름차순 정렬.
 */
export function subscribeMyEntries(
  hospitalId: string,
  patientUid: string,
  onChange: (entries: Array<WaitEntryIndex & { id: string }>) => void,
  onError?: (e: Error) => void,
): Unsubscribe {
  if (!isFirebaseConfigured()) {
    onChange([]);
    return () => {};
  }
  return onValue(
    ref(db, `hospitals/${hospitalId}/wait_queue_by_patient/${patientUid}`),
    (snap) => {
      if (!snap.exists()) {
        onChange([]);
        return;
      }
      const raw = snap.val() as Record<string, WaitEntryIndex>;
      const list = Object.entries(raw)
        .map(([id, entry]) => ({ id, ...entry }))
        .sort((a, b) => a.number - b.number);
      onChange(list);
    },
    (err) => onError?.(err),
  );
}

/**
 * 의료진 — 부서·날짜 대기열 전체 실시간 구독.
 * 활성(waiting/called/in-progress)만 필터링, number 오름차순.
 */
export function subscribeDeptQueue(
  hospitalId: string,
  department: string,
  date: string,
  onChange: (entries: WaitEntry[]) => void,
  onError?: (e: Error) => void,
  options: { includeCompleted?: boolean } = {},
): Unsubscribe {
  if (!isFirebaseConfigured()) {
    onChange([]);
    return () => {};
  }
  return onValue(
    ref(db, `hospitals/${hospitalId}/wait_queue/${department}/${date}`),
    (snap) => {
      if (!snap.exists()) {
        onChange([]);
        return;
      }
      const raw = snap.val() as Record<string, WaitEntry>;
      const list = Object.values(raw)
        .filter((e) =>
          options.includeCompleted
            ? true
            : e.status !== 'completed' && e.status !== 'cancelled',
        )
        .sort((a, b) => a.number - b.number);
      onChange(list);
    },
    (err) => onError?.(err),
  );
}

/** 현재 상태가 환자 본인 취소 가능한지 */
export function isCancellableByPatient(status: QueueStatus): boolean {
  return status === 'waiting';
}
