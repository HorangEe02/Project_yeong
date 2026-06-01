/**
 * Plan A 변형 — Mac Ollama 가용성 상태 (zustand store).
 *
 * Cloud Run 백엔드의 OllamaHealthMiddleware 가 503 + AI_UNAVAILABLE 을 반환하면
 * client.ts response interceptor 가 setActive(true) 호출.
 * App.tsx 의 polling hook 이 60s 간격 /api/health 으로 llm_connected 동기화.
 */
import { create } from 'zustand';

export interface MaintenanceState {
  active: boolean;
  message: string;
  reason: string;
  /** 마지막 갱신 시각 (epoch ms). debounce 용. */
  updatedAt: number;
  setActive: (active: boolean, message?: string, reason?: string) => void;
}

const DEFAULT_MESSAGE = 'AI 서버 점검 중입니다. 잠시 후 다시 시도해주세요. (운영시간: 평일 09~18시)';

export const useMaintenanceStore = create<MaintenanceState>((set) => ({
  active: false,
  message: '',
  reason: '',
  updatedAt: 0,
  setActive: (active, message = '', reason = '') =>
    set({
      active,
      message: active ? message || DEFAULT_MESSAGE : '',
      reason: active ? reason : '',
      updatedAt: Date.now(),
    }),
}));
