// Realtime Database 값 실시간 구독 — Day 6+ 알람용

import { useEffect, useState } from 'react';
import { ref, onValue, off } from 'firebase/database';
import { rtdb } from '@lib/firebase';

export interface RTDBResult<T> {
  data: T | null;
  loading: boolean;
  error: Error | null;
}

export function useRTDBValue<T>(path: string): RTDBResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (!rtdb) {
      setError(new Error('RTDB 미초기화 — VITE_FIREBASE_DATABASE_URL 확인'));
      setLoading(false);
      return;
    }
    setLoading(true);
    const r = ref(rtdb, path);
    const unsub = onValue(
      r,
      (snap) => {
        setData(snap.val() as T);
        setLoading(false);
        setError(null);
      },
      (err) => {
        setError(err as Error);
        setLoading(false);
      },
    );
    return () => off(r, 'value', unsub);
  }, [path]);

  return { data, loading, error };
}
