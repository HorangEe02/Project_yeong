// v3.3 Feature C — 피처 플래그 클라이언트 (Phase 0-4).
//
// 백엔드 GET /api/feature-flags/c 를 단일 진실 원천으로 사용한다.
// 모듈 수준 5분 캐시 + 컴포넌트 마운트 시 1회 fetch (codebase 표준 패턴 — react-query 미사용).
//
// 사용 예:
//   const flags = useFeatureCFlags();
//   if (flags.cad_upload) accept += ',.dxf,.step';

import { useEffect, useState } from 'react';

export interface FeatureCFlags {
  multi_llm: boolean;
  compare_mode: boolean;
  dept_lock: boolean;
  division_boundary: boolean;
  work_fullscreen: boolean;
  quick_questions_v2: boolean;
  inline_actions: boolean;
  cad_upload: boolean;
}

export const FEATURE_C_DEFAULTS: FeatureCFlags = {
  multi_llm: false,
  compare_mode: false,
  dept_lock: false,
  division_boundary: false,
  work_fullscreen: false,
  quick_questions_v2: false,
  inline_actions: false,
  cad_upload: false,
};

interface FeatureFlagsResponse {
  version: string;
  feature: string;
  flags: FeatureCFlags;
}

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const CACHE_TTL_MS = 5 * 60 * 1000;

let cachedFlags: FeatureCFlags | null = null;
let cachedAt = 0;
let inFlight: Promise<FeatureCFlags> | null = null;

async function fetchFeatureCFlags(): Promise<FeatureCFlags> {
  const now = Date.now();
  if (cachedFlags && now - cachedAt < CACHE_TTL_MS) return cachedFlags;
  if (inFlight) return inFlight;

  inFlight = (async () => {
    try {
      const res = await fetch(`${API_URL}/api/feature-flags/c`, {
        headers: { Accept: 'application/json' },
      });
      if (!res.ok) return FEATURE_C_DEFAULTS;
      const data: FeatureFlagsResponse = await res.json();
      const merged = { ...FEATURE_C_DEFAULTS, ...(data.flags ?? {}) };
      cachedFlags = merged;
      cachedAt = Date.now();
      return merged;
    } catch {
      // 백엔드 미응답 → 모두 비활성 (안전)
      return FEATURE_C_DEFAULTS;
    } finally {
      inFlight = null;
    }
  })();

  return inFlight;
}

/** 캐시 강제 무효화 — 환경변수 변경 후 즉시 반영용. */
export function invalidateFeatureCFlagsCache(): void {
  cachedFlags = null;
  cachedAt = 0;
}

/**
 * Feature C 피처 플래그 훅.
 *
 * 첫 마운트 시 백엔드 호출, 이후 같은 세션 내에서는 모듈 캐시 사용 (5분 TTL).
 * 백엔드 미응답 시 안전한 기본값(모두 false) 반환.
 */
export function useFeatureCFlags(): FeatureCFlags {
  const [flags, setFlags] = useState<FeatureCFlags>(cachedFlags ?? FEATURE_C_DEFAULTS);

  useEffect(() => {
    let cancelled = false;
    void fetchFeatureCFlags().then((v) => {
      if (!cancelled) setFlags(v);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  return flags;
}
