// Day 5 — SOP 진행 상태 스토어 (zustand persist)
// 사용자별 SOP 단계 진행을 localStorage 에 보존하여 재방문 시 이어서 학습.

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface SopProgress {
  /** 0-based 현재 단계 인덱스 */
  currentStep: number;
  /** 완료한 단계 step_number 목록 (1-based — backend 의 step_number 와 일치) */
  completedSteps: number[];
  /** 마지막 갱신 timestamp (ms) */
  updatedAt: number;
}

interface SopState {
  /** sop_id → SopProgress */
  progress: Record<string, SopProgress>;
  /** 현재 Drawer 에 열려있는 sop_id (null 이면 닫힘) */
  activeSopId: string | null;

  openSop: (sopId: string) => void;
  closeSop: () => void;
  setCurrentStep: (sopId: string, idx: number) => void;
  toggleStepCompleted: (sopId: string, stepNumber: number) => void;
  resetSop: (sopId: string) => void;
}

function emptyProgress(): SopProgress {
  return {
    currentStep: 0,
    completedSteps: [],
    updatedAt: Date.now(),
  };
}

export const useSopStore = create<SopState>()(
  persist(
    (set) => ({
      progress: {},
      activeSopId: null,

      openSop: (sopId) =>
        set((s) => ({
          activeSopId: sopId,
          progress: s.progress[sopId] ? s.progress : { ...s.progress, [sopId]: emptyProgress() },
        })),

      closeSop: () => set({ activeSopId: null }),

      setCurrentStep: (sopId, idx) =>
        set((s) => {
          const prev = s.progress[sopId] ?? emptyProgress();
          return {
            progress: {
              ...s.progress,
              [sopId]: { ...prev, currentStep: idx, updatedAt: Date.now() },
            },
          };
        }),

      toggleStepCompleted: (sopId, stepNumber) =>
        set((s) => {
          const prev = s.progress[sopId] ?? emptyProgress();
          const has = prev.completedSteps.includes(stepNumber);
          const completedSteps = has
            ? prev.completedSteps.filter((n) => n !== stepNumber)
            : [...prev.completedSteps, stepNumber].sort((a, b) => a - b);
          return {
            progress: {
              ...s.progress,
              [sopId]: { ...prev, completedSteps, updatedAt: Date.now() },
            },
          };
        }),

      resetSop: (sopId) =>
        set((s) => {
          const next = { ...s.progress };
          delete next[sopId];
          return { progress: next };
        }),
    }),
    {
      name: 'ajin-sop-progress',
      partialize: (state) => ({ progress: state.progress }), // activeSopId 는 세션마다 초기화
    },
  ),
);
