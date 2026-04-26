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
 * @param dateMs - 일 기준 ms. 미지정 시 마운트 시점의 `Date.now()` 한 번만 (날짜 변경 시 새 hook 인스턴스 필요).
 * @returns visits + loading 상태.
 *  - slug 또는 dept 없음 → `{ visits: [], loading: false }` (idle)
 *  - 있음 + 첫 emit 전 → `{ visits: [], loading: true }`
 *  - emit 후 → `{ visits: Visit[], loading: false }` (createdAt asc 정렬)
 */
export function useStaffActiveVisits(
  slug: string | null,
  dept: string | null,
  dateMs?: number,
): UseStaffActiveVisitsReturn {
  const [visits, setVisits] = useState<Visit[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  // 마운트 시점의 Date.now() 한 번만 capture — default param 의 매-render 재평가 회피.
  const [stableNow] = useState<number>(() => Date.now());
  const effectiveDate = dateMs ?? stableNow;

  useEffect(() => {
    if (!slug || !dept) {
      setVisits([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    setVisits([]);
    const unsub = subscribeActiveVisitsByDepartment(slug, dept, effectiveDate, (vs) => {
      setVisits(vs);
      setLoading(false);
    });
    return unsub;
  }, [slug, dept, effectiveDate]);

  return { visits, loading };
}
