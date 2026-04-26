import { useEffect, useState } from 'react';
import { subscribeActiveVisitsByDepartment } from '@/services/visit';
import type { Visit } from '@/types/visit';

export interface UseStaffActiveVisitsReturn {
  visits: Visit[];
  loading: boolean;
}

/**
 * Phase I.2.3 — staff 의 부서별 active visit 실시간 구독 hook.
 *
 * @param slug - HospitalShell.slug. null/empty 이면 idle.
 * @param dept - 진료과 (예: 'IM'). null/empty 이면 idle.
 * @param dateMs - 일 기준 ms (default Date.now()).
 * @returns visits + loading 상태.
 *  - slug 또는 dept 없음 → `{ visits: [], loading: false }` (idle)
 *  - 있음 + 첫 emit 전 → `{ visits: [], loading: true }`
 *  - emit 후 → `{ visits: Visit[], loading: false }` (createdAt asc 정렬)
 */
export function useStaffActiveVisits(
  slug: string | null,
  dept: string | null,
  dateMs: number = Date.now(),
): UseStaffActiveVisitsReturn {
  const [visits, setVisits] = useState<Visit[]>([]);
  const [loading, setLoading] = useState<boolean>(false);

  useEffect(() => {
    if (!slug || !dept) {
      setVisits([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    setVisits([]);
    const unsub = subscribeActiveVisitsByDepartment(slug, dept, dateMs, (vs) => {
      setVisits(vs);
      setLoading(false);
    });
    return unsub;
  }, [slug, dept, dateMs]);

  return { visits, loading };
}
