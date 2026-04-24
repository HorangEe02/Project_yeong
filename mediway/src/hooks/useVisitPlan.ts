import { useEffect, useState } from 'react';
import {
  isPlanExpired,
  subscribeVisitPlan,
  setVisitPlan,
  clearVisitPlan,
  setAutoSendOptIn,
} from '@/services/visitPlan';
import type {
  PlannedWaypoint,
  VisitPlan,
  VisitPlanSource,
} from '@/types/visit-plan';

interface UseVisitPlan {
  plan: VisitPlan | null;
  loading: boolean;
  expired: boolean;
  save: (waypoints: PlannedWaypoint[], source?: VisitPlanSource, hospitalId?: string) => Promise<void>;
  clear: () => Promise<void>;
  toggleAutoSend: (optIn: boolean) => Promise<void>;
  saving: boolean;
  error: string | null;
}

export function useVisitPlan(uid: string | null | undefined): UseVisitPlan {
  const [plan, setPlan] = useState<VisitPlan | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!uid) {
      setPlan(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    const unsub = subscribeVisitPlan(uid, (p) => {
      setPlan(p);
      setLoading(false);
    });
    return () => unsub();
  }, [uid]);

  const save = async (
    waypoints: PlannedWaypoint[],
    source: VisitPlanSource = 'patient',
    hospitalId?: string,
  ) => {
    if (!uid) return;
    setSaving(true);
    setError(null);
    try {
      await setVisitPlan(uid, { waypoints, source, hospitalId });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      throw e;
    } finally {
      setSaving(false);
    }
  };

  const clear = async () => {
    if (!uid) return;
    setSaving(true);
    setError(null);
    try {
      await clearVisitPlan(uid);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      throw e;
    } finally {
      setSaving(false);
    }
  };

  const toggleAutoSend = async (optIn: boolean) => {
    if (!uid) return;
    setError(null);
    try {
      await setAutoSendOptIn(uid, optIn);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      throw e;
    }
  };

  return {
    plan,
    loading,
    expired: isPlanExpired(plan),
    save,
    clear,
    toggleAutoSend,
    saving,
    error,
  };
}
