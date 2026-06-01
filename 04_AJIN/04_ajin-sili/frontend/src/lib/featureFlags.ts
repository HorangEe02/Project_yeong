// v3.3 Feature C — 피처 플래그 클라이언트 (Phase 0-4).
//
// 백엔드 GET /api/feature-flags/c 를 단일 진실 원천으로 사용한다.
// 모듈 수준 5분 캐시 + 컴포넌트 마운트 시 1회 fetch (codebase 표준 패턴 — react-query 미사용).
//
// 사용 예:
//   const flags = useFeatureCFlags();
//   if (flags.cad_upload) accept += ',.dxf,.step';

import { useEffect, useState } from 'react';
import { apiUrl } from '@api/baseUrl';

export interface FeatureCFlags {
  multi_llm: boolean;
  compare_mode: boolean;
  dept_lock: boolean;
  division_boundary: boolean;
  work_fullscreen: boolean;
  quick_questions_v2: boolean;
  inline_actions: boolean;
  cad_upload: boolean;
  analyzers_enabled: boolean;
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
  analyzers_enabled: false,
};

interface FeatureFlagsResponse {
  version: string;
  feature: string;
  flags: FeatureCFlags;
}

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
      const res = await fetch(apiUrl('/feature-flags/c'), {
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

// ────────────────────────────────────────────────────────────────
// Feature D — D1 MVP 분리 (P2)
//
// D1 (변경감지+알림) 만 GA. D2/D3/D4/D5 는 env-gated 로 봉인.
// 백엔드 GET /api/feature-flags/d 를 단일 진실 원천으로 사용한다.
// ────────────────────────────────────────────────────────────────

export interface FeatureDFlags {
  d1_alerts: boolean;
  d2_rag: boolean;
  d3_whatif: boolean;
  d4_workflow: boolean;
  d5_supply: boolean;
}

export const FEATURE_D_DEFAULTS: FeatureDFlags = {
  d1_alerts: true,
  d2_rag: false,
  d3_whatif: false,
  d4_workflow: false,
  d5_supply: false,
};

interface FeatureDFlagsResponse {
  version: string;
  feature: string;
  flags: FeatureDFlags;
}

let cachedFeatureDFlags: FeatureDFlags | null = null;
let cachedFeatureDAt = 0;
let inFlightFeatureD: Promise<FeatureDFlags> | null = null;

async function fetchFeatureDFlags(): Promise<FeatureDFlags> {
  const now = Date.now();
  if (cachedFeatureDFlags && now - cachedFeatureDAt < CACHE_TTL_MS) return cachedFeatureDFlags;
  if (inFlightFeatureD) return inFlightFeatureD;

  inFlightFeatureD = (async () => {
    try {
      const res = await fetch(apiUrl('/feature-flags/d'), {
        headers: { Accept: 'application/json' },
      });
      if (!res.ok) return FEATURE_D_DEFAULTS;
      const data: FeatureDFlagsResponse = await res.json();
      const merged = { ...FEATURE_D_DEFAULTS, ...(data.flags ?? {}) };
      cachedFeatureDFlags = merged;
      cachedFeatureDAt = Date.now();
      return merged;
    } catch {
      return FEATURE_D_DEFAULTS;
    } finally {
      inFlightFeatureD = null;
    }
  })();

  return inFlightFeatureD;
}

/** 캐시 강제 무효화 — Feature D 환경변수 변경 후 즉시 반영용. */
export function invalidateFeatureDFlagsCache(): void {
  cachedFeatureDFlags = null;
  cachedFeatureDAt = 0;
}

/**
 * Feature D 피처 플래그 상태 훅.
 *
 * 백엔드 런타임 플래그를 조회하고, 실패 시 D1만 켜진 안전 기본값을 반환한다.
 */
export function useFeatureDFlagsState(): { flags: FeatureDFlags; loading: boolean } {
  const [state, setState] = useState<{ flags: FeatureDFlags; loading: boolean }>({
    flags: cachedFeatureDFlags ?? FEATURE_D_DEFAULTS,
    loading: cachedFeatureDFlags === null,
  });

  useEffect(() => {
    let cancelled = false;
    void fetchFeatureDFlags().then((v) => {
      if (!cancelled) setState({ flags: v, loading: false });
    });
    return () => {
      cancelled = true;
    };
  }, []);

  return state;
}

/**
 * Feature D 피처 플래그 훅.
 *
 * Returns:
 *   FeatureDFlags: 현재 D 플래그. 로딩 중에는 안전 기본값을 반환한다.
 */
export function useFeatureDFlags(): FeatureDFlags {
  return useFeatureDFlagsState().flags;
}
