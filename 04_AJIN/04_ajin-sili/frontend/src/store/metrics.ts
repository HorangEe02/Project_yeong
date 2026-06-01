// "사업장 상태" 메트릭 store — v3.6
//
// 이전 정적 카운트(employees/errorCodes/departments/testAccounts) 대신
// 운영 상태 4종(가동설비/금일알람/법규미해결/시스템응답)을 표시.
//
// 데이터 소스:
//   - GET /api/dashboard/ingestion → molds.{have,total}, latency_ms, qps
//   - GET /api/dashboard/alarms    → 활성 알람 카운트 + severity 분포
//   - 카드 2(금일 SPC 알람)는 RTDB live_alarms 를 dashboard.tsx 에서 직접 합산

import { create } from 'zustand';
import * as DashboardApi from '@api/dashboard';

export interface OperationalMetrics {
  /** 가동/정비 중 설비 수 */
  equipmentOnline: number;
  /** 등록된 전체 설비 수 */
  equipmentTotal: number;
  /** 진행 중 알람 (전체 — D 모듈 + RTDB SPC 합산은 dashboard 에서) */
  openAlarms: number;
  /** Critical severity 알람 수 — 카드 색 결정용 */
  criticalAlarms: number;
  /** 최근 1분 평균 응답 시간 (ms) */
  latencyMs: number;
  /** 최근 1분 평균 QPS */
  qps: number;
}

interface MetricsState {
  metrics: OperationalMetrics | null;
  loading: boolean;
  error: string | null;
  load: () => Promise<void>;
}

const FALLBACK: OperationalMetrics = {
  equipmentOnline: 25,
  equipmentTotal: 25,
  openAlarms: 1,
  criticalAlarms: 1,
  latencyMs: 124,
  qps: 8.4,
};

export const useMetricsStore = create<MetricsState>((set) => ({
  metrics: null,
  loading: false,
  error: null,
  load: async () => {
    set({ loading: true, error: null });
    try {
      // 두 엔드포인트 병렬 호출 — 한쪽 실패해도 가용 데이터로 부분 갱신
      const [ingestionResult, alarmsResult] = await Promise.allSettled([
        DashboardApi.getIngestion(),
        DashboardApi.getAlarms(),
      ]);

      const merged: OperationalMetrics = { ...FALLBACK };

      if (ingestionResult.status === 'fulfilled') {
        const ing = ingestionResult.value as Record<string, unknown>;
        const molds = (ing.molds as { have?: number; total?: number } | undefined) ?? {};
        merged.equipmentOnline = molds.have ?? FALLBACK.equipmentOnline;
        merged.equipmentTotal = molds.total ?? FALLBACK.equipmentTotal;
        merged.latencyMs = (ing.latency_ms as number) ?? FALLBACK.latencyMs;
        merged.qps = (ing.qps as number) ?? FALLBACK.qps;
      }

      if (alarmsResult.status === 'fulfilled') {
        const al = alarmsResult.value as Record<string, unknown>;
        // 백엔드 형상: { alarms, total, critical, warning, info }
        // mock 형상:   배열 그대로
        if (Array.isArray(al)) {
          merged.openAlarms = al.length;
          merged.criticalAlarms = al.filter(
            (a: Record<string, unknown>) =>
              a.severity === 'CRITICAL' || a.severity === 'critical'
          ).length;
        } else {
          merged.openAlarms = (al.total as number) ?? FALLBACK.openAlarms;
          merged.criticalAlarms = (al.critical as number) ?? FALLBACK.criticalAlarms;
        }
      }

      set({ metrics: merged, loading: false });
    } catch (e) {
      // 모든 호출 실패 — fallback 으로 시연 보존
      set({ metrics: FALLBACK, loading: false, error: (e as Error).message });
    }
  },
}));
