// Day 5 — 업무 액션 라우터 API 클라이언트
// 백엔드 POST /api/onboarding/actions/match — error_code/employee/spc/regulation 즉시 응답.

import { ONBOARDING_BASE, authHeaders } from '@api/onboarding';

export interface ActionResultPayload {
  action_type: string;
  success: boolean;
  display_text: string;
  bridge_target: string;
}

export interface ActionMatchResponse {
  matched: boolean;
  action_type: string;
  result: ActionResultPayload | null;
}

export async function matchAction(query: string): Promise<ActionMatchResponse> {
  const res = await fetch(`${ONBOARDING_BASE}/actions/match`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
    },
    body: JSON.stringify({ query }),
  });
  if (!res.ok) {
    throw new Error(`액션 매칭 실패: ${res.status}`);
  }
  return (await res.json()) as ActionMatchResponse;
}
