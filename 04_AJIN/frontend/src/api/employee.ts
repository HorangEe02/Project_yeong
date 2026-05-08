// Module A · 인원 검색 API 클라이언트.
// backend/routers/employee.py 매핑 — 자연어 search + 부서/본부 단위 list.

import { api } from './client';

export interface BackendEmployee {
  name: string;
  department: string;
  division: string;
  position: string;
  email: string;
  phone: string;
  extension: string;
  plant: string;
}

// ─────────────────────────────────────────────────────────────
// POST /employee/search — 자연어 (기존)
// ─────────────────────────────────────────────────────────────

export interface EmployeeSearchResponse {
  mode: string;
  results: BackendEmployee[];
  message: string;
  formatted_markdown: string;
  total: number;
}

export async function searchEmployees(query: string): Promise<EmployeeSearchResponse> {
  const { data } = await api.post<EmployeeSearchResponse>('/employee/search', { query });
  return data;
}

// ─────────────────────────────────────────────────────────────
// GET /employee/by-department — 부서/본부 단위 전체 (신규, limit 없음)
// ─────────────────────────────────────────────────────────────

export interface EmployeeListResponse {
  scope: 'department' | 'division' | string;
  name: string;
  total: number;
  masked: number;
  excluded: number;
  employees: BackendEmployee[];
}

export async function fetchByDepartment(dept: string): Promise<EmployeeListResponse> {
  const { data } = await api.get<EmployeeListResponse>('/employee/by-department', {
    params: { dept },
  });
  return data;
}

export async function fetchByDivision(division: string): Promise<EmployeeListResponse> {
  const { data } = await api.get<EmployeeListResponse>('/employee/by-department', {
    params: { division },
  });
  return data;
}

// v3.6 — GET /employee/list — 전체 인사 DB 페이지네이션 (인사 검색 첫 화면용)
// 이전에는 mock seed 24명을 첫 화면에 노출했지만 실 DB(329명)와 정합 안 됨 → 실 DB 부분 표시.
export async function fetchEmployeeList(
  limit: number = 24,
  offset: number = 0,
): Promise<EmployeeListResponse> {
  const { data } = await api.get<EmployeeListResponse>('/employee/list', {
    params: { limit, offset },
  });
  return data;
}

// ─────────────────────────────────────────────────────────────
// GET /employee/org-tree — 본부 → 팀 트리
// ─────────────────────────────────────────────────────────────

export interface TeamNode {
  name: string;
  headcount: number;
}

export interface DivisionNode {
  name: string;
  headcount: number;
  teams: TeamNode[];
}

export interface OrgTreeResponse {
  total: number;
  divisions: DivisionNode[];
}

export async function fetchOrgTree(): Promise<OrgTreeResponse> {
  const { data } = await api.get<OrgTreeResponse>('/employee/org-tree');
  return data;
}
