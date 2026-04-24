import { onValue, ref } from 'firebase/database';
import { db, isFirebaseConfigured } from '@/config/firebase';
import type { WaitQueuePatientIndex, WaitQueueStatus } from '@/types/waitQueue';

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
