import { useEffect, useState } from 'react';
import { subscribeActiveVisit } from '@/services/visit';
import type { Visit } from '@/types/visit';

export interface UseActiveVisitReturn {
  visit: Visit | null;
  loading: boolean;
}

/**
 * 환자의 active visit (status ∈ {checked-in, in-progress}) 1건 실시간 구독 hook.
 *
 * @param slug - HospitalShell.slug. null/empty 이면 idle.
 * @param patientUid - 환자 uid. null/empty 이면 idle.
 * @returns visit + loading 상태.
 *  - slug 또는 patientUid 없음 → `{ loading: false, visit: null }` (idle)
 *  - 있음 + 첫 emit 전 → `{ loading: true, visit: null }`
 *  - 있음 + emit 후 → `{ loading: false, visit: Visit | null }`
 *
 * Service 위임: `subscribeActiveVisit(slug, patientUid, cb)` — RTDB query 자동 cleanup.
 */
export function useActiveVisit(
  slug: string | null,
  patientUid: string | null,
): UseActiveVisitReturn {
  const [visit, setVisit] = useState<Visit | null>(null);
  const [loading, setLoading] = useState<boolean>(false);

  useEffect(() => {
    if (!slug || !patientUid) {
      setVisit(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    setVisit(null);
    const unsub = subscribeActiveVisit(slug, patientUid, (v) => {
      setVisit(v);
      setLoading(false);
    });
    return unsub;
  }, [slug, patientUid]);

  return { visit, loading };
}
