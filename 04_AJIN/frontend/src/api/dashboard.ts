// Dashboard API — Mock / 실 백엔드 분기

import { api } from './client';
import {
  USE_MOCK,
  mockGetMetrics,
  mockGetIngestion,
  mockGetSystemHealth,
  mockGetSystemInfo,
  mockGetAlarms,
} from './mock';

export async function getMetrics() {
  if (USE_MOCK) return mockGetMetrics();
  const { data } = await api.get('/dashboard/metrics');
  return data;
}

export async function getIngestion() {
  if (USE_MOCK) return mockGetIngestion();
  const { data } = await api.get('/dashboard/ingestion');
  return data;
}

export async function getSystemHealth() {
  if (USE_MOCK) return mockGetSystemHealth();
  const { data } = await api.get('/dashboard/system-health');
  return data;
}

/**
 * 대시보드 시스템 정보 응답 — 백엔드 `/dashboard/system-info` 와 mock SYSTEM_INFO 공통 형상.
 * 모델 목록은 .env 기반으로 백엔드가 동적 구성하므로 mock 은 폴백 용도로만 사용한다.
 */
export interface SystemInfoResponse {
  llm: string[];
  vision: string[];
  embedding: string;
  router?: string;
  ml: string;
  rbac: string;
  data?: {
    employees: number;
    errorCodes: number;
    molds: number;
    spcProcesses: number;
    glossary: number;
    fewShotRag: number;
  };
  // 레거시/부가 필드
  version?: string;
  environment?: string;
}

export async function getSystemInfo(): Promise<SystemInfoResponse> {
  if (USE_MOCK) return mockGetSystemInfo() as Promise<SystemInfoResponse>;
  const { data } = await api.get<SystemInfoResponse>('/dashboard/system-info');
  return data;
}

export async function getAlarms() {
  if (USE_MOCK) return mockGetAlarms();
  const { data } = await api.get('/dashboard/alarms');
  return data;
}

export interface ModuleCounts {
  crawlers: number;
  sopGuides: number;
  collaborations: number;
  molds: number;
  roles: number;
  fewShotRag: number;
}

export async function getModuleCounts(): Promise<ModuleCounts> {
  const { data } = await api.get<ModuleCounts>('/dashboard/module-counts');
  return data;
}
