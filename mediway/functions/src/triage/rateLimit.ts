import * as admin from 'firebase-admin';

/**
 * Triage 함수의 rate limiter — chatbot 의 일/시간 이중 bucket 과 달리 시간 단위만 사용.
 *
 * 정책 (LOCAL_SYNC_GAPS §1.1 + e2e §E):
 *  - `/triage_usage/{uid}/{epochHour}` = 정수 카운터
 *  - `epochHour` = `Math.floor(now_ms / 3_600_000)` (UTC 시 단위)
 *  - 시간당 10회 — 초과 시 `resource-exhausted` 로 거절
 *  - 다음 시간 windows 까지 retryAfterSeconds 계산
 */

export const TRIAGE_LIMIT_PER_HOUR = 10;

export interface TriageRateCheckResult {
  allowed: boolean;
  /** 현 hour bucket 의 남은 횟수 (응답 직전 검증치 — 사용 후엔 -1) */
  remainingHour: number;
  /** 막혔을 때 다음 hour 까지 남은 초 — 0 if allowed */
  retryAfterSeconds: number;
}

function epochHour(nowMs: number): number {
  return Math.floor(nowMs / 3_600_000);
}

/** 현재 사용량 조회 + 판정. 증가는 `incrementTriageUsage()` 가 별도 수행. */
export async function checkTriageRateLimit(
  uid: string,
  nowMs: number = Date.now(),
): Promise<TriageRateCheckResult> {
  const hour = epochHour(nowMs);
  const ref = admin.database().ref(`triage_usage/${uid}/${hour}`);
  const snap = await ref.get();
  const count = (snap.val() ?? 0) as number;
  const remainingHour = Math.max(0, TRIAGE_LIMIT_PER_HOUR - count);
  const allowed = remainingHour > 0;

  let retryAfterSeconds = 0;
  if (!allowed) {
    // 다음 정시까지 남은 초
    const nextHour = (hour + 1) * 3_600_000;
    retryAfterSeconds = Math.max(1, Math.ceil((nextHour - nowMs) / 1000));
  }

  return { allowed, remainingHour, retryAfterSeconds };
}

/**
 * 성공 호출 후 카운터 +1 (transaction 으로 race 안전).
 * 다른 hour bucket 에 진입했어도 nowMs 기준 hour 에 기록 — 호출 시점이 진실.
 */
export async function incrementTriageUsage(
  uid: string,
  nowMs: number = Date.now(),
): Promise<void> {
  const hour = epochHour(nowMs);
  await admin
    .database()
    .ref(`triage_usage/${uid}/${hour}`)
    .transaction((c) => (typeof c === 'number' ? c : 0) + 1);
}
