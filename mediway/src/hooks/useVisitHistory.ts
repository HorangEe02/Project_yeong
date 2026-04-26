import { useCallback, useEffect, useState } from 'react';
import { listVisitsByPatient } from '@/services/visit';
import type { Visit } from '@/types/visit';

export interface UseVisitHistoryReturn {
  visits: Visit[];
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

/**
 * Phase I.4.1 — 환자의 visit history 조회 hook (일회성 read).
 *
 * 실시간 subscribe 가 아닌 fetch — visit history 는 자주 변하지 않음 (read 부하 ↓).
 * status 변경 등 active visit 흐름은 별도 hook (`useActiveVisit`).
 *
 * @param slug - HospitalShell.slug. null/empty 이면 idle.
 * @param patientUid - 환자 uid. null/empty 이면 idle.
 * @param opts.limit - 최대 반환 개수 (default: 50).
 * @returns visits + loading + error + refresh().
 *  - slug 또는 uid 없음 → idle (visits=[], loading=false, error=null)
 *  - fetch 중 → loading=true
 *  - 성공 → visits=Visit[], loading=false (createdAt desc)
 *  - 실패 → error=string, loading=false
 */
export function useVisitHistory(
  slug: string | null,
  patientUid: string | null,
  opts?: { limit?: number },
): UseVisitHistoryReturn {
  const [visits, setVisits] = useState<Visit[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState<number>(0);

  const limit = opts?.limit ?? 50;

  const refresh = useCallback(() => {
    setReloadKey((k) => k + 1);
  }, []);

  useEffect(() => {
    if (!slug || !patientUid) {
      setVisits([]);
      setLoading(false);
      setError(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    listVisitsByPatient(slug, patientUid, { limit })
      .then((vs) => {
        if (cancelled) return;
        setVisits(vs);
        setLoading(false);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const msg = err instanceof Error ? err.message : '조회 실패';
        setError(msg);
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [slug, patientUid, limit, reloadKey]);

  return { visits, loading, error, refresh };
}
