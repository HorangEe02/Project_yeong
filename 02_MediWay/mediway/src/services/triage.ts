import { httpsCallable } from 'firebase/functions';
import { functions } from '@/config/firebase';

export interface TriageRecommendation {
  department: string;
  confidence: number;
  reason: string;
}

export interface TriageResponse {
  recommendations: TriageRecommendation[];
  disclaimer: string;
}

/**
 * AI 증상 triage 호출 — Cloud Function `triageSymptoms`.
 *
 * 증상 텍스트는 서버에 저장되지 않는다 (Cloud Function이 파기).
 * Rate limit: 사용자·시간당 10회.
 */
export async function requestTriage(
  symptoms: string,
): Promise<TriageResponse> {
  const fn = httpsCallable<{ symptoms: string }, TriageResponse>(
    functions,
    'triageSymptoms',
  );
  const result = await fn({ symptoms });
  return result.data;
}
