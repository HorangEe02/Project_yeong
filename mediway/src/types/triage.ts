/**
 * 프런트엔드 측 Triage 타입 — 서버 `triageSymptoms` callable 과 1:1 미러.
 * 서버 원본: `mediway/functions/src/triage/types.ts`.
 *
 * 본 모듈은 zod 의존성 없이 순수 타입만 정의 (런타임 검증은 호출 측 로직 + 서버에서 처리).
 */

export interface TriageRequest {
  hospitalId: string;
  symptomText: string;
}

export interface TriageRecommendation {
  /** 진료과 한국어 키 (예: '내과') */
  department: string;
  /** 0..1 신뢰도. 합이 1 이 아닐 수 있음 — 각 추천의 독립 점수 */
  confidence: number;
  /** 1-2 문장 추천 근거 */
  reason: string;
}

export interface TriageResponse {
  recommendations: TriageRecommendation[];
  disclaimer: string;
  model: string;
  tokensIn: number;
  tokensOut: number;
  rateLimit: { remainingHour: number };
  /** outcome=emergency 일 때 119 / 응급실 안내. */
  emergencyNotice?: string;
}

/**
 * 프런트 서비스 계층이 Firebase HttpsError 를 normalize 해서 던지는 커스텀 에러.
 * UI 가 `code` 로 분기, `message` 는 그대로 사용자에게 표시 가능 수준.
 */
export type TriageErrorCode =
  | 'unauthenticated'
  | 'feature_disabled'
  | 'invalid_argument'
  | 'rate_limited'
  | 'network'
  | 'internal'
  | 'unknown';

export interface TriageError {
  code: TriageErrorCode;
  message: string;
  /** rate_limited 일 때 retry 까지 남은 초 */
  retryAfterSeconds?: number;
}
