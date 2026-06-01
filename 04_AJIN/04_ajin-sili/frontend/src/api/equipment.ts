// Day 6 Phase 2 — 설비/공정 AI (Module F) API 클라이언트.
// 12 endpoints — backend/routers/equipment.py 와 1:1 매핑.

import { api } from './client';
import type {
  ErrorCategoriesResponse,
  ErrorSearchResponse,
  HeadlineResponse,
  InspectionChecklistResponse,
  ManualSearchResponse,
  MarkovResponse,
  MLEnginesStatusResponse,
  MoldsResponse,
  MTBFResponse,
  OverviewResponse,
  SPCResponse,
  SPCUploadResponse,
  ViolationsResponse,
} from '@/types/equipment';

// baseURL 이 이미 '/api' 로 끝남 (client.ts) — 짧은 path 사용
const BASE = '/equipment';

// 1. GET /equipment/dashboard/overview
export async function fetchOverview(): Promise<OverviewResponse> {
  const { data } = await api.get<OverviewResponse>(`${BASE}/dashboard/overview`);
  return data;
}

// 2. GET /equipment/spc/{process_id}
export async function fetchSPC(processId: string): Promise<SPCResponse> {
  const { data } = await api.get<SPCResponse>(`${BASE}/spc/${encodeURIComponent(processId)}`);
  return data;
}

// 3. GET /equipment/spc/violations/recent
export async function fetchSPCViolationsRecent(
  sinceTs = 0,
  limit = 20,
): Promise<ViolationsResponse> {
  const { data } = await api.get<ViolationsResponse>(`${BASE}/spc/violations/recent`, {
    params: { since_ts: sinceTs, limit },
  });
  return data;
}

// 4. POST /equipment/error/search
export interface ErrorSearchPayload {
  query: string;
  top_k?: number;
  equipment_filter?: string | null;
}

export async function searchError(payload: ErrorSearchPayload): Promise<ErrorSearchResponse> {
  const { data } = await api.post<ErrorSearchResponse>(`${BASE}/error/search`, payload);
  return data;
}

// 5. GET /equipment/error/categories
export async function fetchErrorCategories(): Promise<ErrorCategoriesResponse> {
  const { data } = await api.get<ErrorCategoriesResponse>(`${BASE}/error/categories`);
  return data;
}

// 6. GET /equipment/markov/{error_code}
export async function fetchMarkov(errorCode: string, depth = 3): Promise<MarkovResponse> {
  const { data } = await api.get<MarkovResponse>(`${BASE}/markov/${encodeURIComponent(errorCode)}`, {
    params: { depth },
  });
  return data;
}

// 7. GET /equipment/molds
export async function fetchMolds(): Promise<MoldsResponse> {
  const { data } = await api.get<MoldsResponse>(`${BASE}/molds`);
  return data;
}

// 8. GET /equipment/mtbf
export async function fetchMTBF(): Promise<MTBFResponse> {
  const { data } = await api.get<MTBFResponse>(`${BASE}/mtbf`);
  return data;
}

// 9. GET /equipment/ml-engines/status
export async function fetchMLEngines(): Promise<MLEnginesStatusResponse> {
  const { data } = await api.get<MLEnginesStatusResponse>(`${BASE}/ml-engines/status`);
  return data;
}

// 10. POST /equipment/manual/search
export interface ManualSearchPayload {
  query: string;
  equipment_type?: string | null;
  n_results?: number;
}

export async function searchManual(payload: ManualSearchPayload): Promise<ManualSearchResponse> {
  const { data } = await api.post<ManualSearchResponse>(`${BASE}/manual/search`, payload);
  return data;
}

// 11. POST /equipment/spc/upload-csv
export async function uploadSPCCsv(file: File): Promise<SPCUploadResponse> {
  const fd = new FormData();
  fd.append('file', file);
  const { data } = await api.post<SPCUploadResponse>(`${BASE}/spc/upload-csv`, fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

// 12. GET /equipment/inspection/checklist/{type}
export async function fetchChecklist(equipmentType: string): Promise<InspectionChecklistResponse> {
  const { data } = await api.get<InspectionChecklistResponse>(
    `${BASE}/inspection/checklist/${encodeURIComponent(equipmentType)}`,
  );
  return data;
}

// 13. GET /equipment/headline — W8 Daily Headline
export async function fetchHeadline(): Promise<HeadlineResponse> {
  const { data } = await api.get<HeadlineResponse>(`${BASE}/headline`);
  return data;
}

// ─────────────────────────────────────────────────────────────
// v4.3 — 점검 이력 ETL (CSV 업로드 + PWA 제출 + ingest_log 조회)
// ─────────────────────────────────────────────────────────────

export interface InspectionIngestErrorRow {
  row_index: number;
  error_code: string;
  error_msg: string;
  raw_payload?: Record<string, unknown>;
}

export interface InspectionIngestResult {
  rows_total: number;
  rows_inserted: number;
  rows_updated: number;
  rows_skipped: number;
  rows_error: number;
  dry_run: boolean;
  source: string;
  started_at: string;
  finished_at: string;
  error_payload: InspectionIngestErrorRow[];
  ingest_log_id?: number | null;
}

export async function uploadInspectionCsv(
  file: File,
  opts: { dryRun?: boolean } = {},
): Promise<InspectionIngestResult> {
  const fd = new FormData();
  fd.append('file', file);
  const { data } = await api.post<InspectionIngestResult>(
    `${BASE}/inspection/upload-csv`,
    fd,
    {
      headers: { 'Content-Type': 'multipart/form-data' },
      params: { dry_run: opts.dryRun ? true : false },
    },
  );
  return data;
}

export interface InspectionResultItem {
  item_no: number;
  passed: boolean;
  score?: number | null;
  comment?: string;
}

export interface InspectionSubmitPayload {
  equipment_id: string;
  template_id: number;
  inspection_date?: string;
  results: InspectionResultItem[];
  overall_status: 'PASS' | 'WARN' | 'FAIL';
  note?: string;
  client_uuid?: string;
}

export interface InspectionSubmitResponse {
  inspection_log_id: number;
  deduplicated: boolean;
  source: string;
}

export async function submitInspection(
  payload: InspectionSubmitPayload,
): Promise<InspectionSubmitResponse> {
  const { data } = await api.post<InspectionSubmitResponse>(
    `${BASE}/inspection/submit`,
    payload,
  );
  return data;
}

export interface IngestLogEntry {
  id: number;
  started_at: string;
  finished_at: string | null;
  source_label: string;
  file_name: string;
  rows_total: number;
  rows_inserted: number;
  rows_updated: number;
  rows_skipped: number;
  rows_error: number;
  actor: string;
}

export async function fetchIngestLogRecent(limit = 20): Promise<{ items: IngestLogEntry[]; total: number }> {
  const { data } = await api.get<{ items: IngestLogEntry[]; total: number }>(
    `${BASE}/inspection/ingest-log/recent`,
    { params: { limit } },
  );
  return data;
}

// ─────────────────────────────────────────────────────────────
// v4.8 Feature F 트랙 A — PLC 라이브 상태 + 도면 OCR
// ─────────────────────────────────────────────────────────────

export interface PLCStatusResponse {
  healthy: boolean;
  active_lanes: number;
  last_message_ts: string | null;
  last_message_age_sec: number | null;
  rtdb_live: boolean;
  streams: string[];
  data_class: 'real' | 'synthetic' | 'system' | 'unknown';
  source_system: string;
  source_label: string;
  error: string | null;
}

export async function fetchPLCStatus(): Promise<PLCStatusResponse> {
  const { data } = await api.get<PLCStatusResponse>(`${BASE}/plc/status`);
  return data;
}

export interface DrawingOCRResponse {
  drawing_id: number;
  part_numbers: string[];
  source: string;
  data_class: 'real' | 'synthetic' | 'system' | 'unknown';
  source_system: string;
  source_label: string;
}

export async function extractPartNumbers(drawingId: number): Promise<DrawingOCRResponse> {
  const { data } = await api.post<DrawingOCRResponse>(
    `${BASE}/drawing/${drawingId}/ocr`,
  );
  return data;
}
