// Module A · 인사 부가 정보 API 클라이언트.
// 백엔드 GET /employee/{id}/extras 매핑. 권한 분기는 서버가 결정.
// W7 — ERP/HRIS 어댑터 스텁의 클라이언트 측 인터페이스.

import { api } from './client';

export type ExtrasPermission = 'FULL' | 'PARTIAL' | 'DENIED';

export interface TripRecord {
  trip_id: string;
  destination: string;
  purpose: string;
  started_on: string;
  ended_on: string;
  cost_krw: number;
}

export interface DirectReport {
  employee_id: string;
  name: string;
  position: string;
  department: string;
}

export interface ApprovalSummary {
  pending: number;
  approved_30d: number;
  rejected_30d: number;
}

export interface EmployeeExtras {
  employee_id: string;
  permission: ExtrasPermission;
  reason: string;
  trips: TripRecord[];
  direct_reports: DirectReport[];
  approvals: ApprovalSummary | null;
}

export async function fetchEmployeeExtras(employeeId: string): Promise<EmployeeExtras> {
  const { data } = await api.get<EmployeeExtras>(
    `/employee/${encodeURIComponent(employeeId)}/extras`,
  );
  return data;
}
