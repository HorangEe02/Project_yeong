// Module H1 v4.0 · 모델 카탈로그 API 클라이언트.
// 백엔드 GET /api/models/catalog (config.py MODEL_PROFILES 노출)
// + GET /api/models/recommend (휴리스틱 부서·기능 매핑)

import { api } from './client';

export type ModelSpeed = 'fast' | 'medium' | 'slow';
export type ModelQuality = 'good' | 'high' | 'very_high';
export type ModelLang = 'multilingual' | 'korean';

export interface ModelCatalogItem {
  id: string;
  display: string;
  size_gb: number;
  lang: ModelLang;
  vision: boolean;
  speed: ModelSpeed;
  quality: ModelQuality;
  best_for: string[];
  tags_ko: string[];
  summary_ko: string;
  use_when_ko: string;
  avoid_when_ko: string;
}

export interface ModelCatalogResponse {
  items: ModelCatalogItem[];
  total: number;
}

export async function fetchModelCatalog(): Promise<ModelCatalogResponse> {
  const { data } = await api.get<ModelCatalogResponse>('/models/catalog');
  return data;
}

// ─────────────────────────────────────────────────────────────
// 추천
// ─────────────────────────────────────────────────────────────

export interface ModelRecommendQuery {
  feature?: string;
  department?: string;
  needs_vision?: boolean;
  prefers_speed?: boolean;
}

export interface ModelRecommendResponse {
  recommended_model_id: string;
  display: string;
  reason: string;
  input: ModelRecommendQuery;
}

export async function recommendModel(
  q: ModelRecommendQuery,
): Promise<ModelRecommendResponse> {
  const { data } = await api.get<ModelRecommendResponse>('/models/recommend', {
    params: q,
  });
  return data;
}

// ─────────────────────────────────────────────────────────────
// 클라이언트 캐시 (24h) — 카탈로그는 정적이라 매 요청 무의미
// ─────────────────────────────────────────────────────────────

const CACHE_KEY = 'ajin-model-catalog-cache';
const CACHE_TTL_MS = 24 * 60 * 60 * 1000;

interface CacheEntry {
  fetchedAt: number;
  data: ModelCatalogResponse;
}

export async function fetchModelCatalogCached(): Promise<ModelCatalogResponse> {
  if (typeof window === 'undefined') {
    return fetchModelCatalog();
  }
  try {
    const raw = localStorage.getItem(CACHE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as CacheEntry;
      if (Date.now() - parsed.fetchedAt < CACHE_TTL_MS && parsed.data?.items?.length) {
        return parsed.data;
      }
    }
  } catch {
    // 캐시 손상 → 무시하고 fresh fetch
  }
  const fresh = await fetchModelCatalog();
  try {
    localStorage.setItem(
      CACHE_KEY,
      JSON.stringify({ fetchedAt: Date.now(), data: fresh } satisfies CacheEntry),
    );
  } catch {
    // 용량 초과 등 — 조용히 실패
  }
  return fresh;
}
