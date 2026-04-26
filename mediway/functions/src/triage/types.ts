import { z } from 'zod';

/**
 * `triageSymptoms` callable 의 서버 측 타입 + Zod 검증 스키마.
 *
 * Source-of-truth: prod 번들이 호출하던 함수의 spec (LOCAL_SYNC_GAPS §1.1) +
 * e2e-wait-queue.html 시나리오 E. 응답 schema 는 `TriageResult` 가 권위.
 *
 * 프런트엔드 미러: `mediway/src/types/triage.ts`.
 */

/** 추천 가능한 진료과 — Gemini 가 이 목록에서 선택하도록 system prompt 에서 강제. */
export const ALLOWED_DEPARTMENTS = [
  '내과',
  '외과',
  '정형외과',
  '소아청소년과',
  '가정의학과',
  '응급의학과',
  '영상의학과',
  '이비인후과',
  '안과',
  '피부과',
  '산부인과',
  '비뇨의학과',
  '정신건강의학과',
  '신경과',
  '재활의학과',
] as const;

export type AllowedDepartment = (typeof ALLOWED_DEPARTMENTS)[number];

/** Zod request schema — Cloud Functions onCall 에서 검증. */
export const TriageRequestSchema = z.object({
  hospitalId: z
    .string()
    .min(1, 'hospitalId 가 비어있습니다')
    .max(64, 'hospitalId 길이 초과'),
  symptomText: z
    .string()
    .min(10, '증상 설명은 10자 이상 입력해 주세요')
    .max(500, '증상 설명은 500자 이내로 입력해 주세요'),
});

export type TriageRequest = z.infer<typeof TriageRequestSchema>;

/**
 * 진료과 추천 1건 — Gemini 응답 + fallback 모두 동일 shape.
 *  - `confidence` 는 0..1 (합이 1 이 아닐 수 있음 — 독립 신뢰도)
 *  - `reason` 1-2 문장 한국어 추천 근거
 */
export interface TriageRecommendation {
  department: string;
  confidence: number;
  reason: string;
}

/** 처리 결과 분류 — audit 에 기록. */
export type TriageOutcome =
  | 'ok'
  | 'rate_limited'
  | 'emergency'
  | 'pii_refuse'
  | 'feature_disabled'
  | 'invalid_argument'
  | 'internal';

/** Callable 응답 — 클라이언트 `TriageResponse` 와 1:1 미러. */
export interface TriageResult {
  recommendations: TriageRecommendation[];
  /** STANDARD_DISCLAIMER 와 동일 — 프런트가 굳이 변형하지 않음 */
  disclaimer: string;
  model: string;
  tokensIn: number;
  tokensOut: number;
  /** 본 호출 직후 남은 시간당 횟수 (UI 배너용). 0 가능. */
  rateLimit: { remainingHour: number };
  /** outcome=emergency 인 경우 추가 안내 메시지 (응급실/119 안내) */
  emergencyNotice?: string;
}

/**
 * `/triage_audit/{pushId}` RTDB 엔트리.
 *
 * 권한 (rules):
 *  - 클라이언트가 새 entry 를 self-append 가능 (`!data.exists() && actorUid === auth.uid`)
 *  - read 는 platformAdmin 만
 *
 * 본 함수는 Admin SDK 로 작성 — rules 우회. 단 schema 는 클라이언트 self-append 와
 * 호환되도록 같은 모양 유지.
 */
export interface TriageAuditEntry {
  actorUid: string;
  hospitalId: string;
  symptomLen: number;
  /** PII 보호 — 원문 80자만 저장 */
  symptomSnippet: string;
  recommendations: Array<Pick<TriageRecommendation, 'department' | 'confidence'>>;
  model: string;
  tokensIn: number;
  tokensOut: number;
  outcome: TriageOutcome;
  timestamp: number;
}
