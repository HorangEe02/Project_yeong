import { useEffect, useState } from 'react';
import { canAutoSend, getActiveVisitPlan } from '@/services/visitPlan';
import type { VisitPlan } from '@/types/visit-plan';

interface UseAutoFillFromPlan {
  plan: VisitPlan | null;
  loading: boolean;
  mismatched: boolean; // hospitalId 불일치
  autoSendEligible: boolean;
}

/**
 * 환자 uid로부터 유효한 방문 계획을 조회하고, 의료진이 자동 적용 가능한지 판정.
 * - patientUid 가 null/undefined 이면 상태 초기화
 * - hospitalId 가 지정되어 있으면 현재 의료진 병원과 비교
 */
export function useAutoFillFromPlan(
  patientUid: string | null | undefined,
  currentHospitalId?: string,
): UseAutoFillFromPlan {
  const [plan, setPlan] = useState<VisitPlan | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!patientUid) {
      setPlan(null);
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    void (async () => {
      try {
        const result = await getActiveVisitPlan(patientUid);
        if (!cancelled) setPlan(result);
      } catch {
        if (!cancelled) setPlan(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [patientUid]);

  const mismatched = !!(
    plan?.hospitalId &&
    currentHospitalId &&
    plan.hospitalId !== currentHospitalId
  );

  return {
    plan,
    loading,
    mismatched,
    autoSendEligible: canAutoSend(plan, currentHospitalId) && !mismatched,
  };
}
