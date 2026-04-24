import {
  ref,
  set,
  get,
  update,
  onValue,
  type Unsubscribe,
} from 'firebase/database';
import { db, isFirebaseConfigured } from '@/config/firebase';
import type { Session } from '@/types/session';
import type { QRToken, QRTokenStatus } from '@/types/session';

// ============================================================
// QR 토큰 관리
// ============================================================

/** QR 토큰을 DB에 등록 (환자 측) */
export async function createQRToken(
  token: string,
  patientUid: string,
): Promise<void> {
  if (!isFirebaseConfigured()) return;
  const tokenRef = ref(db, `qr_tokens/${token}`);
  await set(tokenRef, {
    patientUid,
    status: 'waiting' as QRTokenStatus,
    createdAt: Date.now(),
  });
}

/** QR 토큰 조회 (의료진 측 — 스캔 후 검증) */
export async function getQRToken(token: string): Promise<QRToken | null> {
  if (!isFirebaseConfigured()) return null;
  const tokenRef = ref(db, `qr_tokens/${token}`);
  const snapshot = await get(tokenRef);
  if (!snapshot.exists()) return null;
  return snapshot.val() as QRToken;
}

/** QR 토큰 상태 변경 (매칭 시) */
export async function updateQRTokenStatus(
  token: string,
  status: QRTokenStatus,
  sessionId?: string,
): Promise<void> {
  if (!isFirebaseConfigured()) return;
  const updates: Record<string, unknown> = { status };
  if (sessionId) updates.sessionId = sessionId;
  await update(ref(db, `qr_tokens/${token}`), updates);
}

/** QR 토큰 상태 실시간 구독 (환자 측 — 매칭 대기) */
export function subscribeQRToken(
  token: string,
  callback: (data: QRToken | null) => void,
): Unsubscribe {
  if (!isFirebaseConfigured()) {
    callback(null);
    return () => {};
  }
  const tokenRef = ref(db, `qr_tokens/${token}`);
  return onValue(tokenRef, (snapshot) => {
    callback(snapshot.exists() ? (snapshot.val() as QRToken) : null);
  });
}

// ============================================================
// 세션 관리
// ============================================================

/** 세션 생성 (의료진 측 — 동선 전송) */
export async function createSession(session: Session): Promise<void> {
  if (!isFirebaseConfigured()) return;
  const sessionRef = ref(db, `sessions/${session.sessionId}`);
  await set(sessionRef, {
    ...session,
    createdAt: Date.now(),
  });
}

/** 세션 조회 */
export async function getSession(sessionId: string): Promise<Session | null> {
  if (!isFirebaseConfigured()) return null;
  const sessionRef = ref(db, `sessions/${sessionId}`);
  const snapshot = await get(sessionRef);
  if (!snapshot.exists()) return null;
  return snapshot.val() as Session;
}

/** 세션 실시간 구독 (환자 측 — 동선 수신 및 상태 변경 감지) */
export function subscribeSession(
  sessionId: string,
  callback: (session: Session | null) => void,
): Unsubscribe {
  if (!isFirebaseConfigured()) {
    callback(null);
    return () => {};
  }
  const sessionRef = ref(db, `sessions/${sessionId}`);
  return onValue(sessionRef, (snapshot) => {
    callback(snapshot.exists() ? (snapshot.val() as Session) : null);
  });
}

/** 경유지 도착 처리 (환자 측) */
export async function markWaypointArrived(
  sessionId: string,
  waypointIndex: number,
  totalWaypoints: number,
): Promise<void> {
  if (!isFirebaseConfigured()) return;

  const updates: Record<string, unknown> = {};

  // 현재 경유지 → completed
  updates[`sessions/${sessionId}/waypoints/${waypointIndex}/status`] = 'completed';
  updates[`sessions/${sessionId}/waypoints/${waypointIndex}/arrivedAt`] = Date.now();

  const nextIndex = waypointIndex + 1;
  const isLast = nextIndex >= totalWaypoints;

  if (isLast) {
    // 모든 경유지 완료
    updates[`sessions/${sessionId}/status`] = 'completed';
    updates[`sessions/${sessionId}/completedAt`] = Date.now();
    updates[`sessions/${sessionId}/currentWaypointIndex`] = nextIndex;
  } else {
    // 다음 경유지 → current
    updates[`sessions/${sessionId}/waypoints/${nextIndex}/status`] = 'current';
    updates[`sessions/${sessionId}/currentWaypointIndex`] = nextIndex;
  }

  await update(ref(db), updates);
}

/** 세션 상태 업데이트 */
export async function updateSessionStatus(
  sessionId: string,
  status: Session['status'],
): Promise<void> {
  if (!isFirebaseConfigured()) return;
  await update(ref(db, `sessions/${sessionId}`), { status });
}
