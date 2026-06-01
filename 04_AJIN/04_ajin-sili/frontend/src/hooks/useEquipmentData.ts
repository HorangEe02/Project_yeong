// equipment.tsx Mount-load 6 endpoint 묶음.
// 각 자원별 { data, error } 를 분리 노출 → mock fallback 없이 실패는 실패로 표면화.
//
// 사용처: routes/equipment.tsx
//   const { overview, molds, mtbf, mlEngines, categories, checklist, isLoading, refetch } = useEquipmentData();

import { useCallback, useEffect, useState } from 'react';

import {
  fetchChecklist,
  fetchErrorCategories,
  fetchMLEngines,
  fetchMTBF,
  fetchMolds,
  fetchOverview,
} from '@api/equipment';
import type {
  ErrorCategoriesResponse,
  InspectionChecklistResponse,
  MLEnginesStatusResponse,
  MTBFResponse,
  MoldsResponse,
  OverviewResponse,
} from '@/types/equipment';

export interface ResourceState<T> {
  data: T | null;
  error: Error | null;
}

export interface EquipmentDataState {
  overview: ResourceState<OverviewResponse>;
  molds: ResourceState<MoldsResponse>;
  mtbf: ResourceState<MTBFResponse>;
  mlEngines: ResourceState<MLEnginesStatusResponse>;
  categories: ResourceState<ErrorCategoriesResponse>;
  checklist: ResourceState<InspectionChecklistResponse>;
  isLoading: boolean;
  refetch: () => Promise<void>;
}

const EMPTY = <T>(): ResourceState<T> => ({ data: null, error: null });

function toError(value: unknown, label: string): Error {
  if (value instanceof Error) return value;
  return new Error(`${label}: ${String(value)}`);
}

export function useEquipmentData(checklistType = '프레스'): EquipmentDataState {
  const [overview, setOverview] = useState<ResourceState<OverviewResponse>>(EMPTY);
  const [molds, setMolds] = useState<ResourceState<MoldsResponse>>(EMPTY);
  const [mtbf, setMtbf] = useState<ResourceState<MTBFResponse>>(EMPTY);
  const [mlEngines, setMlEngines] = useState<ResourceState<MLEnginesStatusResponse>>(EMPTY);
  const [categories, setCategories] = useState<ResourceState<ErrorCategoriesResponse>>(EMPTY);
  const [checklist, setChecklist] = useState<ResourceState<InspectionChecklistResponse>>(EMPTY);
  const [isLoading, setIsLoading] = useState(true);

  const load = useCallback(async () => {
    setIsLoading(true);
    const results = await Promise.allSettled([
      fetchOverview(),
      fetchMolds(),
      fetchMTBF(),
      fetchMLEngines(),
      fetchErrorCategories(),
      fetchChecklist(checklistType),
    ]);

    const [ov, mld, mt, ml, cat, ck] = results;

    setOverview(
      ov.status === 'fulfilled'
        ? { data: ov.value, error: null }
        : { data: null, error: toError(ov.reason, 'overview') },
    );
    setMolds(
      mld.status === 'fulfilled'
        ? { data: mld.value, error: null }
        : { data: null, error: toError(mld.reason, 'molds') },
    );
    setMtbf(
      mt.status === 'fulfilled'
        ? { data: mt.value, error: null }
        : { data: null, error: toError(mt.reason, 'mtbf') },
    );
    setMlEngines(
      ml.status === 'fulfilled'
        ? { data: ml.value, error: null }
        : { data: null, error: toError(ml.reason, 'ml-engines') },
    );
    setCategories(
      cat.status === 'fulfilled'
        ? { data: cat.value, error: null }
        : { data: null, error: toError(cat.reason, 'error-categories') },
    );
    setChecklist(
      ck.status === 'fulfilled'
        ? { data: ck.value, error: null }
        : { data: null, error: toError(ck.reason, 'checklist') },
    );

    setIsLoading(false);
  }, [checklistType]);

  useEffect(() => {
    void load();
  }, [load]);

  return {
    overview,
    molds,
    mtbf,
    mlEngines,
    categories,
    checklist,
    isLoading,
    refetch: load,
  };
}
