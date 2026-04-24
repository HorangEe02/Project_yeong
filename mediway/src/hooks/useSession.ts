import { useEffect, useState } from 'react';
import { subscribeQRToken, subscribeSession } from '@/services/session';
import { isFirebaseConfigured } from '@/config/firebase';
import type { Session } from '@/types/session';
import type { QRToken } from '@/types/session';

interface UseSessionReturn {
  /** QR 토큰 데이터 (실시간) */
  qrTokenData: QRToken | null;
  /** 세션 데이터 (실시간) */
  session: Session | null;
  /** Firebase 연결 여부 */
  isConnected: boolean;
}

/**
 * QR 토큰 → 세션 실시간 구독 훅.
 *
 * 1. qrToken이 있으면 /qr_tokens/{token} 구독
 * 2. QR 토큰 status가 "matched"가 되면 sessionId를 추출하여 /sessions/{sessionId} 구독
 * 3. 세션 상태 변경(경유지 도착 등)이 실시간으로 반영됨
 */
export function useSession(qrToken: string | null): UseSessionReturn {
  const [qrTokenData, setQrTokenData] = useState<QRToken | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const isConnected = isFirebaseConfigured();

  // QR 토큰 구독
  useEffect(() => {
    if (!qrToken || !isConnected) return;

    const unsubscribe = subscribeQRToken(qrToken, (data) => {
      setQrTokenData(data);
    });

    return unsubscribe;
  }, [qrToken, isConnected]);

  // QR 토큰이 matched되면 세션 구독
  useEffect(() => {
    if (!qrTokenData?.sessionId || qrTokenData.status !== 'matched' || !isConnected) {
      return;
    }

    const unsubscribe = subscribeSession(qrTokenData.sessionId, (data) => {
      setSession(data);
    });

    return unsubscribe;
  }, [qrTokenData?.sessionId, qrTokenData?.status, isConnected]);

  return { qrTokenData, session, isConnected };
}
