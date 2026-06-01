// Day 6 Phase 2 — 설비/공정 AI 스토어 (Zustand).
// currentProcessId + lastViolations + mlEngines 등 화면 간 동기화 상태.

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type {
  MLEngineStatus,
  ProcessHealthCard,
  ProcessSlug,
  RecentViolation,
} from '@/types/equipment';

interface EquipmentState {
  /** 현재 활성화된 공정 슬러그 (장비 유형 탭 진입 시 어떤 공정 SPC 차트를 표시할지) */
  currentProcessId: ProcessSlug | string;

  /** 최근 5개 위반 (Toast 후 알람 탭 캐시) */
  lastViolations: RecentViolation[];

  /** ML 엔진 상태 캐시 (탭 재진입 시 즉시 표시) */
  mlEngines: MLEngineStatus[];

  /** 5공정 건강 카드 캐시 (Overview 진입 시 즉시 표시) */
  processCards: ProcessHealthCard[];

  /** 마지막 위반 폴링 timestamp (ms epoch) */
  lastSeenViolationsTs: number;

  setCurrentProcessId: (id: ProcessSlug | string) => void;
  setLastViolations: (items: RecentViolation[]) => void;
  appendViolation: (item: RecentViolation) => void;
  setMLEngines: (engines: MLEngineStatus[]) => void;
  setProcessCards: (cards: ProcessHealthCard[]) => void;
  setLastSeenViolationsTs: (ts: number) => void;
  reset: () => void;
}

const INITIAL: Pick<
  EquipmentState,
  | 'currentProcessId'
  | 'lastViolations'
  | 'mlEngines'
  | 'processCards'
  | 'lastSeenViolationsTs'
> = {
  currentProcessId: 'cch',
  lastViolations: [],
  mlEngines: [],
  processCards: [],
  lastSeenViolationsTs: 0,
};

export const useEquipmentStore = create<EquipmentState>()(
  persist(
    (set) => ({
      ...INITIAL,
      setCurrentProcessId: (currentProcessId) => set({ currentProcessId }),
      setLastViolations: (lastViolations) => set({ lastViolations }),
      appendViolation: (item) =>
        set((s) => {
          // 중복 id 방어 + 최대 50건 유지
          if (s.lastViolations.some((v) => v.id === item.id)) return s;
          const next = [item, ...s.lastViolations].slice(0, 50);
          return { lastViolations: next };
        }),
      setMLEngines: (mlEngines) => set({ mlEngines }),
      setProcessCards: (processCards) => set({ processCards }),
      setLastSeenViolationsTs: (lastSeenViolationsTs) => set({ lastSeenViolationsTs }),
      reset: () => set(INITIAL),
    }),
    {
      name: 'ajin-equipment',
      partialize: (state) => ({
        currentProcessId: state.currentProcessId,
        // lastViolations / processCards 는 매 진입 시 fresh 갱신 — persist 제외.
      }),
    },
  ),
);
