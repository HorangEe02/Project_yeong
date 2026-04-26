import { ref, runTransaction, set } from 'firebase/database';
import { db, isFirebaseConfigured } from '@/config/firebase';
import type { QRTokenStatus } from '@/types/session';

/**
 * QR 토큰 자가 발급 서비스 — `QRGuidePlaceholder` 의 「내 QR 코드 발급」 버튼 흐름.
 *
 * Rate limit (시간당 30회):
 *  - `/qr_token_usage/{uid}/{epochHour}` epoch-hour bucket counter
 *  - RTDB rules 가 `<= 30` 검증 — 클라이언트 우회 시도 차단
 *  - Transaction 으로 race-safe — 동시 호출 시 한 쪽이 실패
 *
 * Token register (`/qr_tokens/{token}`):
 *  - 기존 `services/session.ts:createQRToken` 동등 schema (status='waiting' + patientUid + createdAt)
 *  - rate-limit 통과 후에만 set 수행
 *
 * 정상 사용량은 시간당 ~20건 (3분 자동 갱신 + 수동 갱신 몇 회) — 30 cap 은 어뷰즈 방어용.
 */

export const QR_TOKEN_LIMIT_PER_HOUR = 30;

export class QRTokenRateLimitError extends Error {
  retryAfterSeconds: number;
  constructor(retryAfterSeconds: number) {
    super('QR 토큰 발급 한도를 초과했습니다');
    this.name = 'QRTokenRateLimitError';
    this.retryAfterSeconds = retryAfterSeconds;
  }
}

function epochHour(nowMs: number): number {
  return Math.floor(nowMs / 3_600_000);
}

/** 다음 정시까지 남은 초. */
function secondsUntilNextHour(nowMs: number): number {
  const hour = epochHour(nowMs);
  const nextHour = (hour + 1) * 3_600_000;
  return Math.max(1, Math.ceil((nextHour - nowMs) / 1000));
}

/**
 * 시간당 사용량 +1 (transaction). 30 초과 시 abort → `QRTokenRateLimitError` throw.
 *
 * RTDB rule 이 `<= 30` 으로 강제하므로 우회 불가능. 본 함수는 클라이언트 사전 차단 +
 * 친근한 에러 메시지를 위해 transaction abort 결과를 검사한다.
 */
async function incrementUsage(
  uid: string,
  nowMs: number,
): Promise<void> {
  const hour = epochHour(nowMs);
  const usageRef = ref(db, `qr_token_usage/${uid}/${hour}`);
  const result = await runTransaction(usageRef, (current) => {
    const next = (typeof current === 'number' ? current : 0) + 1;
    if (next > QR_TOKEN_LIMIT_PER_HOUR) return; // abort transaction
    return next;
  });
  if (!result.committed) {
    throw new QRTokenRateLimitError(secondsUntilNextHour(nowMs));
  }
}

/**
 * 자가 QR 토큰 발급 — rate-limit 검증 후 `/qr_tokens/{token}` 등록.
 *
 * 호출 흐름:
 *  1. `incrementUsage(uid)` — RTDB rule + transaction 으로 cap 강제
 *  2. 통과 시 `/qr_tokens/{token}` 에 자기 patientUid + status='waiting' 기록
 *  3. 의료진 스캔 시 `useSession` 이 자동으로 sessionId 매칭 후 navigating 전환
 *
 * 실패 케이스:
 *  - `QRTokenRateLimitError` — 시간당 30회 초과 (RTDB rule 거부 + transaction abort)
 *  - 네트워크 / 권한 거부 등 일반 에러는 그대로 propagate
 */
export async function issueSelfQRToken(
  token: string,
  patientUid: string,
  nowMs: number = Date.now(),
): Promise<void> {
  if (!isFirebaseConfigured()) return;
  await incrementUsage(patientUid, nowMs);
  await set(ref(db, `qr_tokens/${token}`), {
    patientUid,
    status: 'waiting' as QRTokenStatus,
    createdAt: nowMs,
  });
}
