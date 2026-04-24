import * as admin from 'firebase-admin';

export const LIMITS = {
  perHour: 20,
  perDay: 100,
};

export interface RateCheckResult {
  allowed: boolean;
  remainingHour: number;
  remainingDay: number;
  retryAfterSeconds: number;
  dailyTotalBefore: number;
}

function hhFromNow(nowMs: number): string {
  return String(new Date(nowMs).getUTCHours()).padStart(2, '0');
}

function ymdFromNow(nowMs: number): string {
  return new Date(nowMs).toISOString().slice(0, 10); // YYYY-MM-DD
}

/**
 * 사용량 조회 + 판정. `chatbot_usage/{uid}/{yyyy-mm-dd}` 에서 hourly.HH · dailyTotal 읽기.
 * 호출만 하며 증가는 incrementUsage에서 별도 수행 — 판정/기록 분리.
 */
export async function checkRateLimit(
  uid: string,
  nowMs: number = Date.now(),
): Promise<RateCheckResult> {
  const day = ymdFromNow(nowMs);
  const hh = hhFromNow(nowMs);
  const ref = admin.database().ref(`chatbot_usage/${uid}/${day}`);
  const snap = await ref.get();
  const v = (snap.val() ?? {}) as {
    dailyTotal?: number;
    hourly?: Record<string, number>;
  };
  const hourlyCount = v.hourly?.[hh] ?? 0;
  const dailyTotal = v.dailyTotal ?? 0;

  const remainingHour = Math.max(0, LIMITS.perHour - hourlyCount);
  const remainingDay = Math.max(0, LIMITS.perDay - dailyTotal);
  const allowed = remainingHour > 0 && remainingDay > 0;

  // 다음 window까지 재시도 대기 (간단 근사):
  // hour 막혔으면 현재 시간 끝까지, day 막혔으면 자정까지
  let retryAfterSeconds = 0;
  if (!allowed) {
    const d = new Date(nowMs);
    if (remainingDay <= 0) {
      const next = new Date(d);
      next.setUTCHours(24, 0, 0, 0);
      retryAfterSeconds = Math.ceil((next.getTime() - nowMs) / 1000);
    } else {
      const next = new Date(d);
      next.setUTCMinutes(60, 0, 0);
      retryAfterSeconds = Math.ceil((next.getTime() - nowMs) / 1000);
    }
  }

  return {
    allowed,
    remainingHour,
    remainingDay,
    retryAfterSeconds,
    dailyTotalBefore: dailyTotal,
  };
}

/**
 * 성공한 chatbot 호출 후 usage 카운터 원자적 증가.
 * hourly.{HH}와 dailyTotal 양쪽 다 increment.
 */
export async function incrementUsage(
  uid: string,
  nowMs: number = Date.now(),
): Promise<void> {
  const day = ymdFromNow(nowMs);
  const hh = hhFromNow(nowMs);
  const ref = admin.database().ref(`chatbot_usage/${uid}/${day}`);
  await ref.update({
    [`hourly/${hh}`]: admin.database.ServerValue.increment(1),
    dailyTotal: admin.database.ServerValue.increment(1),
    lastMessageAt: nowMs,
  });
}
