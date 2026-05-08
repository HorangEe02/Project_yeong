// System Analytics — 5초 폴링용.
// 1차: 백엔드 /api/dashboard/ingestion 호출 (실 DB count)
// 2차 fallback: 네트워크/인증 실패 시 mock (오프라인 데모 안전망)

import { api } from './client';

export interface IngestionItem {
  label: string;       // 영문 라벨 (DRAWINGS, MOLD_ASSETS 등)
  labelKo: string;     // 한글 부제
  current: number;
  total: number;
}

export interface SystemAnalytics {
  gpu_pct: number;
  latency_ms: number;
  qps: number;
  ingestion: IngestionItem[];
  generated_at: number;
  /** 'live' = 백엔드 응답 / 'mock' = fallback */
  source: 'live' | 'mock';
}

// 라벨 매핑 — 백엔드 키 → UI 라벨
const KEY_TO_LABEL: { key: string; label: string; labelKo: string }[] = [
  { key: 'errorCodes', label: 'ERROR_CODES', labelKo: '에러코드' },
  { key: 'molds', label: 'MOLD_ASSETS', labelKo: '금형' },
  { key: 'spc', label: 'SPC_PROCESS', labelKo: 'SPC 공정' },
  { key: 'drawings', label: 'DRAWINGS', labelKo: '도면' },
  { key: 'inspections', label: 'INSPECTIONS', labelKo: '검사' },
];

// ─────────────────────────────────────────────────────────────
// Mock fallback (백엔드 실패 시)
// ─────────────────────────────────────────────────────────────

// 실 DB 와 일관된 값 — drawings 15 (백엔드 카운트), 추후 자산 추가 시 동기화
const MOCK_TOTALS = [201, 25, 5, 15, 72] as const;

function buildMock(): SystemAnalytics {
  const ingestion: IngestionItem[] = KEY_TO_LABEL.map((it, i) => {
    const total = MOCK_TOTALS[i];
    // INSPECTIONS 만 흔들림 (시연 효과)
    const current = i === 4
      ? Math.min(total, Math.floor(60 + Math.random() * 13))
      : total;
    return { label: it.label, labelKo: it.labelKo, current, total };
  });

  return {
    gpu_pct: 38 + Math.random() * 8,
    latency_ms: Math.round(100 + Math.random() * 50),
    qps: Math.round(7000 + Math.random() * 3000),
    ingestion,
    generated_at: Date.now(),
    source: 'mock',
  };
}

// ─────────────────────────────────────────────────────────────
// Backend → UI 어댑터
// ─────────────────────────────────────────────────────────────

interface BackendIngestEntry {
  have: number;
  total: number;
}

interface BackendIngestResponse {
  errorCodes: BackendIngestEntry;
  molds: BackendIngestEntry;
  spc: BackendIngestEntry;
  drawings: BackendIngestEntry;
  inspections: BackendIngestEntry;
  // (옵션) Phase 4 에서 백엔드가 추가하는 시스템 메트릭
  gpu_pct?: number;
  latency_ms?: number;
  qps?: number;
}

function adapt(d: BackendIngestResponse): SystemAnalytics {
  const ingestion: IngestionItem[] = KEY_TO_LABEL.map(({ key, label, labelKo }) => {
    const entry = d[key as keyof BackendIngestResponse] as BackendIngestEntry | undefined;
    return {
      label,
      labelKo,
      current: entry?.have ?? 0,
      total: entry?.total ?? 0,
    };
  });

  return {
    gpu_pct: d.gpu_pct ?? 38 + Math.random() * 8,
    latency_ms: d.latency_ms ?? Math.round(100 + Math.random() * 50),
    qps: d.qps ?? Math.round(7000 + Math.random() * 3000),
    ingestion,
    generated_at: Date.now(),
    source: 'live',
  };
}

// ─────────────────────────────────────────────────────────────
// Public API
// ─────────────────────────────────────────────────────────────

export async function fetchSystemAnalytics(): Promise<SystemAnalytics> {
  try {
    const { data } = await api.get<BackendIngestResponse>('/dashboard/ingestion');
    return adapt(data);
  } catch (err) {
    if (import.meta.env.DEV) {
      console.warn('[analytics] backend 실패 → mock fallback', err);
    }
    return buildMock();
  }
}
