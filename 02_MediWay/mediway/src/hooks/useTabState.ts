import { useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  filterVisibleTabs,
  isTabId,
  TAB_DEFS,
  type TabDef,
  type TabId,
} from '@/types/tabs';
import type { HospitalFeatures } from '@/types/hospital';

/**
 * URL query `?tab=<id>` 기반 탭 상태 관리.
 *
 * - 새로고침·공유 강건 (URL에 영속)
 * - 유효하지 않은 tab 값이면 기본 'home'으로 fallback
 * - features flag 변경으로 현재 탭이 사라지면 자동 리다이렉트
 *
 * @param features HospitalFeatures — 노출 탭 필터링용 (옵션)
 */
export interface UseTabStateResult {
  activeTab: TabId;
  visibleTabs: TabDef[];
  setTab: (id: TabId) => void;
}

export function useTabState(
  features: HospitalFeatures | undefined,
): UseTabStateResult {
  const [params, setParams] = useSearchParams();

  const visibleTabs = useMemo(() => filterVisibleTabs(features), [features]);

  const visibleIds = useMemo(
    () => new Set(visibleTabs.map((t) => t.id)),
    [visibleTabs],
  );

  const activeTab: TabId = useMemo(() => {
    const raw = params.get('tab');
    if (isTabId(raw) && visibleIds.has(raw)) return raw;
    const defaultTab =
      TAB_DEFS.find((t) => t.isDefault && visibleIds.has(t.id))?.id ?? 'home';
    return defaultTab;
  }, [params, visibleIds]);

  const setTab = useCallback(
    (id: TabId) => {
      if (!visibleIds.has(id)) return;
      setParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          next.set('tab', id);
          return next;
        },
        { replace: false },
      );
    },
    [setParams, visibleIds],
  );

  return { activeTab, visibleTabs, setTab };
}
