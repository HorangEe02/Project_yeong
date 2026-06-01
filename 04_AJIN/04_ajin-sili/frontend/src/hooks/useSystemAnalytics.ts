// Day 5++ — 5초 폴링 훅 (DAY5_PLUS_HUD_PLAN Section 8-3, 핵심 코드 사양).
// AbortController 와 cleanup 으로 메모리 누수 방지.

import { useEffect, useState } from 'react';
import { fetchSystemAnalytics, type SystemAnalytics } from '@api/analytics';

const DEFAULT_INTERVAL_MS = 5000;

export function useSystemAnalytics(intervalMs: number = DEFAULT_INTERVAL_MS): {
  data: SystemAnalytics | null;
  loading: boolean;
  error: string | null;
} {
  const [data, setData] = useState<SystemAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const fetchOnce = async () => {
      try {
        const result = await fetchSystemAnalytics();
        if (!cancelled) {
          setData(result);
          setError(null);
          setLoading(false);
        }
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : String(e));
          setLoading(false);
        }
      }
    };

    void fetchOnce();
    const id = window.setInterval(() => {
      void fetchOnce();
    }, intervalMs);

    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [intervalMs]);

  return { data, loading, error };
}
