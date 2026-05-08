// 백엔드 응답 → UI 상태 매핑 헬퍼.

import type { EquipState, RiskLevel } from './types';

export function backendStatusToUI(status: string): EquipState {
  const s = status.toLowerCase();
  if (s === 'good' || s === 'normal' || s === 'ok' || s === 'active') return 'ok';
  if (s === 'critical' || s === 'crit') return 'crit';
  return 'warn';
}

export function backendRiskToUI(risk: string | null | undefined): RiskLevel {
  const r = (risk ?? '').toLowerCase();
  if (r === 'critical') return 'HIGH';
  if (r === 'warning') return 'MED';
  return 'LOW';
}
