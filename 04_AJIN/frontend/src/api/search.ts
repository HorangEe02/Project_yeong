// Module A · 문서 검색 API 클라이언트.
// backend/routers/search.py 매핑 — POST /search/documents (BM25+Vector RRF)
//                                  POST /search/summarize (LLM SSE)
//
// 백엔드 SearchResultItem 스키마는 doc_id/title/doc_type/part_name/content/score/metadata.
// 프론트는 추가로 snippet(클라이언트 사이드 절단)과 highlightTokens(키워드 하이라이트)를 파생.

import { api } from './client';

// ─────────────────────────────────────────────────────────────
// Request / Response (백엔드 schemas/search.py 와 1:1)
// ─────────────────────────────────────────────────────────────

export interface DocSearchRequest {
  query: string;
  k?: number;                  // 1~20, default 5
  doc_type_filter?: string;    // '8d_report' | 'ecn' | 'email' | 'meeting_note' | 'ppap'
  part_name_filter?: string;
  date_from?: string;          // ISO YYYY-MM-DD
  date_to?: string;
}

export interface DocSearchResultItem {
  doc_id: string;
  title: string;
  doc_type: string;
  part_name: string;
  content: string;
  score: number;
  metadata: Record<string, unknown>;
}

export interface DocSearchResponse {
  results: DocSearchResultItem[];
  total: number;
  query: string;
}

// ─────────────────────────────────────────────────────────────
// 호출부
// ─────────────────────────────────────────────────────────────

export async function searchDocuments(req: DocSearchRequest): Promise<DocSearchResponse> {
  const body: DocSearchRequest = { k: 8, ...req };
  const { data } = await api.post<DocSearchResponse>('/search/documents', body);
  return data;
}

// ─────────────────────────────────────────────────────────────
// v4.7 Sprint 2 P0 — Intent · Vision · Capabilities
// 백엔드 routes — POST /search/intent · POST /search/vision-query · GET /search/capabilities
// ─────────────────────────────────────────────────────────────

export interface IntentAlternative {
  intent: string;
  confidence: number;
}

export interface IntentResponse {
  intent: string;
  confidence: number;
  suggested_category: string | null; // SearchCategory 와 동일 키
  alternatives: IntentAlternative[];
}

export async function fetchIntent(query: string): Promise<IntentResponse> {
  const { data } = await api.post<IntentResponse>('/search/intent', { query });
  // store 의 SearchCategory 타입과 호환 (10 카테고리 키).
  return data;
}

export interface VisionSearchResult {
  ocr_text: string;
  search_results: DocSearchResultItem[];
}

export async function visionQuerySearch(file: File): Promise<VisionSearchResult> {
  const form = new FormData();
  form.append('image', file);
  const { data } = await api.post<VisionSearchResult>('/search/vision-query', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

export interface SearchCapabilities {
  vision_enabled: boolean;
  intent_classifier: boolean;
}

export async function fetchCapabilities(): Promise<SearchCapabilities> {
  const { data } = await api.get<SearchCapabilities>('/search/capabilities');
  return data;
}

// ─────────────────────────────────────────────────────────────
// 클라이언트 사이드 헬퍼 — 본문에서 쿼리 토큰을 중심으로 스니펫을 뽑고,
// 하이라이트 가능한 토큰 배열을 반환. 백엔드 응답이 짧다면 그대로 반환.
// ─────────────────────────────────────────────────────────────

const STOPWORDS = new Set([
  '의', '가', '이', '은', '는', '을', '를', '에', '와', '과', '도', '으로', '로', '에서',
]);

export function extractTokens(query: string): string[] {
  return query
    .split(/\s+/)
    .map((t) => t.trim())
    .filter((t) => t.length >= 2 && !STOPWORDS.has(t));
}

/** 본문에서 첫 매칭 위치를 중심으로 ±radius 글자의 스니펫 반환. */
export function buildSnippet(
  content: string,
  tokens: string[],
  radius: number = 80,
): string {
  if (!content) return '';
  if (!tokens.length) return content.slice(0, radius * 2);
  const lower = content.toLowerCase();
  let earliest = -1;
  for (const tok of tokens) {
    const i = lower.indexOf(tok.toLowerCase());
    if (i >= 0 && (earliest === -1 || i < earliest)) earliest = i;
  }
  if (earliest === -1) return content.slice(0, radius * 2);
  const start = Math.max(0, earliest - radius);
  const end = Math.min(content.length, earliest + radius);
  const prefix = start > 0 ? '… ' : '';
  const suffix = end < content.length ? ' …' : '';
  return prefix + content.slice(start, end) + suffix;
}

// ─────────────────────────────────────────────────────────────
// CitationItem — RAG 출처 인용 (CITATION_UI_SPEC.md §3)
// CITATION_UI_SPEC.md §12 — 백엔드 미지원 시 클라이언트 fallback.
// ─────────────────────────────────────────────────────────────

export interface CitationItem {
  id: string;
  documentTitle: string;
  docType: string;
  chunkText: string;
  pageNumber?: number;
  sourceRef: string;
  confidence: number;
  lastUpdated: string;
  bm25Score?: number;
  vectorScore?: number;
  department?: string;
  status?: '완료' | '진행중' | '보류';
}

/** DocSearchResultItem → CitationItem 변환 (백엔드 citations[] 미수신 시 fallback). */
export function toCitationItem(item: DocSearchResultItem, _index: number): CitationItem {
  const meta = (item.metadata ?? {}) as Record<string, unknown>;
  return {
    id: item.doc_id,
    documentTitle: item.title,
    docType: item.doc_type,
    chunkText: item.content ?? '',
    pageNumber: (meta['page_number'] as number) ?? undefined,
    sourceRef: item.doc_id,
    confidence: Math.min(1, Math.max(0, item.score)),
    lastUpdated:
      (meta['created_date'] as string) ??
      (meta['date'] as string) ??
      (meta['created_at'] as string) ??
      (meta['updated_at'] as string) ??
      '',
    bm25Score: (meta['bm25_score'] as number) ?? undefined,
    vectorScore: (meta['vector_score'] as number) ?? undefined,
    department: (meta['department'] as string) ?? undefined,
    status: (meta['status'] as CitationItem['status']) ?? undefined,
  };
}

/** 백엔드 CitationSchema (snake_case) → CitationItem (camelCase). */
export function fromBackendCitation(bc: {
  id: string;
  document_title: string;
  doc_type: string;
  chunk_text: string;
  page_number?: number | null;
  source_ref: string;
  confidence: number;
  last_updated: string;
  bm25_score?: number | null;
  vector_score?: number | null;
  department?: string | null;
  status?: string | null;
}): CitationItem {
  return {
    id: bc.id,
    documentTitle: bc.document_title,
    docType: bc.doc_type,
    chunkText: bc.chunk_text,
    pageNumber: bc.page_number ?? undefined,
    sourceRef: bc.source_ref,
    confidence: Math.min(1, Math.max(0, bc.confidence)),
    lastUpdated: bc.last_updated ?? '',
    bm25Score: bc.bm25_score ?? undefined,
    vectorScore: bc.vector_score ?? undefined,
    department: bc.department ?? undefined,
    status: (bc.status as CitationItem['status']) ?? undefined,
  };
}
