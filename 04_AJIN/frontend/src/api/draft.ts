// Day 8 Phase 2 — Draft (Module B) API 클라이언트.
// backend/routers/draft.py 9 endpoints — 1:1 매핑.
//
// 신규 5 (Day 8): GET /doc-types, POST /cc/recommend, /quality/score, /diff, /stream
// 기존 4: POST /generate, /generate-pipeline, /export, GET /templates

import { api } from './client';
import type {
  CCRecRequest,
  CCRecResponse,
  DiagnoseResponse,
  DiffRequest,
  DiffResponse,
  DocTypeListResponse,
  DraftExportRequest,
  DraftStreamRequest,
  DraftStreamV2Request,
  ExportFormat,
  LLMOptionsResponse,
  QualityRequest,
  QualityResponse,
  UploadReferenceResponse,
} from '@/types/draft';

// baseURL 이 이미 '/api' 로 끝남 (client.ts) — 짧은 path 사용
const BASE = '/draft';

// v3.6 — SSE 호출은 axios 아닌 raw fetchEventSource 를 사용하므로
// axios baseURL ('/api') 이 prepend 되지 않음. SSE 빌더 전용 절대 경로 상수.
// (Module C onboarding 의 ensureApiSuffix() 와 동일 패턴.)
const SSE_BASE = '/api/draft';

// ──────────────────────────────────────────────────────────
// 신규 5 (Day 8 Phase 1)
// ──────────────────────────────────────────────────────────

/** 1. GET /draft/doc-types — 13 문서 유형 메타 (internal 7 + external 6) */
export async function fetchDocTypes(): Promise<DocTypeListResponse> {
  const { data } = await api.get<DocTypeListResponse>(`${BASE}/doc-types`);
  return data;
}

/** 2. POST /draft/cc/recommend — CC 자동 추천 3-tier (필수/권장/선택) */
export async function recommendCC(payload: CCRecRequest): Promise<CCRecResponse> {
  const { data } = await api.post<CCRecResponse>(`${BASE}/cc/recommend`, payload);
  return data;
}

/** 3. POST /draft/quality/score — 품질 평가 5기준 + A/B+/B/C/D/F */
export async function scoreQuality(payload: QualityRequest): Promise<QualityResponse> {
  const { data } = await api.post<QualityResponse>(`${BASE}/quality/score`, payload);
  return data;
}

/** 4. POST /draft/diff — 버전 diff (lg-diff-line.{add/del/mod/ctx} 매핑) */
export async function computeDiff(payload: DiffRequest): Promise<DiffResponse> {
  const { data } = await api.post<DiffResponse>(`${BASE}/diff`, payload);
  return data;
}

/** 5. POST /draft/stream — SSE 스트리밍 (Few-shot RAG + LLM 라우터 DRAFT 모드).
 *
 * SSE 응답이라 axios 대신 useSSE 훅 또는 fetch+EventSource 사용 권장.
 * 이 함수는 URL/페이로드 빌드 헬퍼. 실제 SSE 호출은 hooks/useSSE.ts.
 */
export function buildStreamRequest(payload: DraftStreamRequest): {
  url: string;
  body: DraftStreamRequest;
} {
  return { url: `${SSE_BASE}/stream`, body: payload };
}

// ──────────────────────────────────────────────────────────
// Plan v1.0 — 신규 3 endpoint (diagnose, llm-options, stream-v2)
// ──────────────────────────────────────────────────────────

/** GET /draft/diagnose — Module B 의 5개 의존성 진단 (UI 헬스 배너용). */
export async function fetchDiagnose(): Promise<DiagnoseResponse> {
  const { data } = await api.get<DiagnoseResponse>(`${BASE}/diagnose`);
  return data;
}

/** GET /models/llm-options?feature=draft — Feature 별 모델 셀렉터 옵션. */
export async function fetchLlmOptions(feature = 'draft'): Promise<LLMOptionsResponse> {
  const { data } = await api.get<LLMOptionsResponse>(`/models/llm-options`, {
    params: { feature },
  });
  return data;
}

/** POST /draft/stream-v2 — SSE v2 (Jinja2 + LLMRouter + provider/model 셀렉터).
 *
 * 호출 측은 useSSE 훅 활용. 본 함수는 URL/페이로드 빌드 헬퍼.
 */
export function buildStreamV2Request(payload: DraftStreamV2Request): {
  url: string;
  body: DraftStreamV2Request;
} {
  return { url: `${SSE_BASE}/stream-v2`, body: payload };
}

/** POST /draft/upload-reference — 사용자 양식 업로드 후 텍스트 추출 (v3.6).
 *
 * 지원 포맷: .docx · .pdf · .hwp · .hwpx · .txt · .md
 * 응답의 `text` 를 그대로 stream-v2 의 reference_template_text 필드로 전달한다.
 */
export async function uploadReference(file: File): Promise<UploadReferenceResponse> {
  const form = new FormData();
  form.append('file', file);
  const { data } = await api.post<UploadReferenceResponse>(
    `${BASE}/upload-reference`,
    form,
    { headers: { 'Content-Type': 'multipart/form-data' } },
  );
  return data;
}

// ──────────────────────────────────────────────────────────
// 기존 4 (보존)
// ──────────────────────────────────────────────────────────

export interface DraftGeneratePipelineRequest {
  user_input: string;
  doc_type?: string | null;
  tone?: string;
  include_ref?: boolean;
  model?: string | null;
  language?: string;
  recipient?: string;
  context?: 'internal' | 'external';
}

export interface DraftGeneratePipelineResponse {
  session_id: string;
  doc_type: string;
  content: string;
}

/** 6. POST /draft/generate-pipeline — 비스트리밍 단일 응답 (fallback) */
export async function generateDraftPipeline(
  payload: DraftGeneratePipelineRequest,
): Promise<DraftGeneratePipelineResponse> {
  const { data } = await api.post<DraftGeneratePipelineResponse>(
    `${BASE}/generate-pipeline`,
    payload,
  );
  return data;
}

/** 7. POST /draft/export — 7포맷 내보내기 (binary blob) */
export async function exportDraft(payload: DraftExportRequest): Promise<Blob> {
  const { data } = await api.post(`${BASE}/export`, payload, {
    responseType: 'blob',
  });
  return data as Blob;
}

/** 7-1. exportDraft 헬퍼: blob → 브라우저 다운로드 트리거 */
export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

/** 7-2. 통합 export+download (UI에서 1회 호출) */
export async function exportAndDownload(
  content: string,
  format: ExportFormat,
  docType = 'email_oem',
  filename?: string,
): Promise<void> {
  const blob = await exportDraft({ content, format, doc_type: docType });
  const ext = format === 'hwpx' ? 'hwpx' : format;
  downloadBlob(blob, filename ?? `draft.${ext}`);
}

export interface TemplateItem {
  id: string;
  name: string;
  language: 'ko' | 'en';
  category: string;
  filename: string;
}

export interface TemplatesResponse {
  templates: TemplateItem[];
  count: number;
}

/** 8. GET /draft/templates — Jinja2 템플릿 목록 */
export async function fetchTemplates(): Promise<TemplatesResponse> {
  const { data } = await api.get<TemplatesResponse>(`${BASE}/templates`);
  return data;
}
