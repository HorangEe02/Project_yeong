import { httpsCallable } from 'firebase/functions';
import { functions, isFirebaseConfigured } from '@/config/firebase';
import type {
  TriageError,
  TriageErrorCode,
  TriageRequest,
  TriageResponse,
} from '@/types/triage';

/**
 * `triageSymptoms` (asia-northeast3) callable 래퍼.
 *
 * 서버 원본: mediway/functions/src/triage/triageSymptoms.ts
 * 서버 스키마: `{ hospitalId, symptomText }` → `TriageResult` (TriageResponse 와 1:1)
 *
 * 본 래퍼는:
 *  1) symptomText trim — 빈/짧은 문자열은 즉시 로컬 거절 (네트워크 왕복 절감)
 *  2) Firebase 미설정 시 internal 에러로 빠르게 실패
 *  3) Firebase HttpsError 를 `TriageError` 로 normalize — UI 가 code 분기로 사용
 */
export async function requestTriageRecommendation(
  input: TriageRequest,
): Promise<TriageResponse> {
  const symptomText = input.symptomText.trim();
  if (!symptomText) {
    throw asTriageError('invalid_argument', '증상 설명을 입력해 주세요');
  }
  if (symptomText.length < 10) {
    throw asTriageError(
      'invalid_argument',
      '증상 설명은 10자 이상 입력해 주세요',
    );
  }
  if (symptomText.length > 500) {
    throw asTriageError(
      'invalid_argument',
      '증상 설명은 500자 이내로 입력해 주세요',
    );
  }
  if (!isFirebaseConfigured()) {
    throw asTriageError('internal', 'Firebase 미설정');
  }

  const payload: TriageRequest = {
    hospitalId: input.hospitalId,
    symptomText,
  };

  const callable = httpsCallable<TriageRequest, TriageResponse>(
    functions,
    'triageSymptoms',
  );
  try {
    const result = await callable(payload);
    return result.data;
  } catch (err) {
    throw normalizeError(err);
  }
}

function normalizeError(err: unknown): TriageError {
  const anyErr = err as {
    code?: string;
    message?: string;
    details?: { retryAfterSeconds?: number };
  } | null;
  const codeRaw = anyErr?.code ?? 'unknown';
  const message = anyErr?.message ?? '알 수 없는 오류';

  if (codeRaw.includes('unauthenticated')) {
    return asTriageError('unauthenticated', '로그인 후 다시 시도해 주세요');
  }
  if (codeRaw.includes('failed-precondition')) {
    // 두 케이스: features.aiTriage=false / GEMINI_API_KEY 미설정
    // message 키워드로 구분
    if (/aiTriage|기능|활성화/.test(message)) {
      return asTriageError(
        'feature_disabled',
        '이 병원에서는 AI 진료과 추천이 제공되지 않습니다',
      );
    }
    return asTriageError('internal', 'AI 추천 서비스 일시 중단');
  }
  if (codeRaw.includes('resource-exhausted')) {
    return {
      code: 'rate_limited',
      message,
      retryAfterSeconds: anyErr?.details?.retryAfterSeconds,
    };
  }
  if (codeRaw.includes('invalid-argument')) {
    return asTriageError('invalid_argument', message);
  }
  if (codeRaw.includes('unavailable') || codeRaw.includes('deadline-exceeded')) {
    return asTriageError(
      'network',
      '네트워크 오류 — 잠시 후 다시 시도해 주세요',
    );
  }
  if (codeRaw.includes('internal')) {
    return asTriageError('internal', message);
  }
  return asTriageError('unknown', message);
}

function asTriageError(code: TriageErrorCode, message: string): TriageError {
  return { code, message };
}
