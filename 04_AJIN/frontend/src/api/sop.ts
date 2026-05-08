// Day 5 — SOP API 클라이언트
// 백엔드 backend/routers/onboarding.py 의 GET /sop/list, GET /sop/{id} 와 1:1 정합.

import { ONBOARDING_BASE, authHeaders } from '@api/onboarding';

export interface SopSummary {
  sop_id: string;
  title: string;
  department: string;
  category: string;
  steps_count: number;
}

export interface SopStep {
  step_number: number;
  title: string;
  description: string;
  checklist: string[];
  caution: string;
  related_terms: string[];
  estimated_time: string;
  responsible: string;
}

export interface SopDetail {
  sop_id: string;
  title: string;
  department: string;
  category: string;
  prerequisites: string[];
  safety_warnings: string[];
  related_sops: string[];
  steps: SopStep[];
}

export interface SopListResponse {
  items: SopSummary[];
  total: number;
}

export async function fetchSopList(): Promise<SopListResponse> {
  const res = await fetch(`${ONBOARDING_BASE}/sop/list`, {
    headers: authHeaders(),
  });
  if (!res.ok) {
    throw new Error(`SOP 목록 로드 실패: ${res.status}`);
  }
  return (await res.json()) as SopListResponse;
}

export async function fetchSopDetail(sopId: string): Promise<SopDetail> {
  const res = await fetch(`${ONBOARDING_BASE}/sop/${encodeURIComponent(sopId)}`, {
    headers: authHeaders(),
  });
  if (!res.ok) {
    throw new Error(`SOP '${sopId}' 로드 실패: ${res.status}`);
  }
  return (await res.json()) as SopDetail;
}

// v3.6 — SOP 별 자동 생성 퀴즈
export interface SopQuizQuestion {
  question: string;
  options: string[];
  correct_index: number;
  explanation: string;
  category: string;
  source_id: string;
  related_step: number;
}

export interface SopQuizResponse {
  sop_id: string;
  title: string;
  questions: SopQuizQuestion[];
  total: number;
}

export async function fetchSopQuiz(sopId: string, count = 3): Promise<SopQuizResponse> {
  const res = await fetch(
    `${ONBOARDING_BASE}/sop/${encodeURIComponent(sopId)}/quiz?count=${count}`,
    { headers: authHeaders() },
  );
  if (!res.ok) {
    throw new Error(`SOP '${sopId}' 퀴즈 로드 실패: ${res.status}`);
  }
  return (await res.json()) as SopQuizResponse;
}
