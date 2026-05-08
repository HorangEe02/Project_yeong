// Day 8 Phase 2 — Draft (Module B) TS 타입.
// backend/schemas/draft.py 의 Pydantic 모델과 1:1 정합.

export type DocCategory = 'internal' | 'external';
export type DraftPageTab = 'internal' | 'external' | 'history';
export type DraftToneId =
  | 'formal_internal'
  | 'formal_external'
  | 'standard'
  | 'friendly'
  | 'concise'
  | '공식적'
  | '친근함'
  | '중립';
export type CCTier = 'required' | 'recommended' | 'optional';

// ── 1. Doc Types (GET /draft/doc-types) ─────────────────────

export interface DocTypeMeta {
  id: string;
  category: DocCategory;
  name_ko: string;
  name_en: string;
  required_fields: string[];
}

export interface DocTypeListResponse {
  items: DocTypeMeta[];
  internal_count: number;
  external_count: number;
}

// ── 2. Stream Request (POST /draft/stream) ──────────────────

export interface DraftStreamRequest {
  doc_type: string;
  tone: string;
  meta: Record<string, unknown>;
  language?: 'ko' | 'en';
  context?: DocCategory;
  model?: string | null;
}

// ── 3. CC Recommend (POST /draft/cc/recommend) ──────────────

export interface CCRecRequest {
  doc_type: string;
  sender_department?: string;
  sender_division?: string;
  recipient?: string;
}

export interface CCGroup {
  tier: CCTier;
  label_ko: string;
  label_en: string;
  departments: string[];
}

export interface CCRecResponse {
  groups: CCGroup[];
  doc_type: string;
  sender_department: string;
}

// ── 4. Quality Score (POST /draft/quality/score) ────────────

export interface QualityRequest {
  text: string;
  doc_type: string;
  reference_template?: string;
}

export interface QualityScoresDetail {
  structure: number;
  structure_max: number;
  length: number;
  length_max: number;
  terminology: number;
  terminology_max: number;
  completeness: number;
  completeness_max: number;
  tone: number;
  tone_max: number;
}

export interface QualityResponse {
  total_score: number;
  grade: 'A' | 'B+' | 'B' | 'C' | 'D' | 'F';
  scores: QualityScoresDetail;
  improvements: string[];
  details: Record<string, unknown>;
}

// ── 5. Diff (POST /draft/diff) ──────────────────────────────

export interface DiffRequest {
  old: string;
  new: string;
  context_lines?: number;
}

export interface DiffStats {
  added: number;
  removed: number;
  unchanged: number;
  similarity: number;
}

export type DiffLineType = 'add' | 'del' | 'mod' | 'ctx' | 'header';

export interface DiffLine {
  type: DiffLineType;
  text: string;
}

export interface DiffResponse {
  lines: DiffLine[];
  stats: DiffStats;
  diff_html?: string;
}

// ── 6. Export (기존 POST /draft/export) ─────────────────────

export type ExportFormat = 'docx' | 'odt' | 'pdf' | 'xlsx' | 'csv' | 'txt' | 'hwpx';

export interface DraftExportRequest {
  content: string;
  doc_type?: string;
  format: ExportFormat;
}

// ── 7. Frontend 도메인 모델 (Firestore documents/{uid}/items/{id}) ──

export interface DraftDocumentMeta {
  title?: string;
  recipient?: string;
  cc?: string[];
  custom_fields?: Record<string, string>;
}

export interface DraftQualityRecord {
  total_score: number;
  grade: string;
  scores?: QualityScoresDetail;
}

export interface DraftVersionEntry {
  content: string;
  _at: number; // ms epoch
  source: 'llm' | 'user';
}

export interface DraftStorageUrls {
  docx?: string;
  odt?: string;
  pdf?: string;
  xlsx?: string;
  csv?: string;
  txt?: string;
}

export interface DraftDocument {
  id: string;
  user_uid: string;
  doc_type: string;
  tone: string;
  context: DocCategory;
  meta: DraftDocumentMeta;
  content: string;
  quality?: DraftQualityRecord;
  cc_recommended?: CCGroup[];
  versions: DraftVersionEntry[];
  storage_urls?: DraftStorageUrls;
  status: 'draft' | 'completed' | 'archived';
  created_at: number;
  updated_at: number;
}

// ═══════════════════════════════════════════════════════════
// Plan v1.0 — 진단 / 모델 옵션 / Stream v2
// ═══════════════════════════════════════════════════════════

export interface DiagnoseCheck {
  ok: boolean;
  detail: string;
  meta?: Record<string, unknown>;
}

export interface DiagnoseResponse {
  ollama: DiagnoseCheck;
  gemini: DiagnoseCheck;
  pipeline: DiagnoseCheck;
  templates: DiagnoseCheck;
  prompts: DiagnoseCheck;
  summary_ok: boolean;
}

export type LLMProvider = 'ollama' | 'gemini';
export type LLMFamily = 'qwen' | 'gemma' | 'gemini' | 'other';

export interface LLMOption {
  provider: LLMProvider;
  id: string;
  label: string;
  available: boolean;
  blocked: boolean;
  blocked_reason: string;
  family: LLMFamily;
}

export interface LLMOptionsResponse {
  options: LLMOption[];
  default_provider: LLMProvider | null;
  default_id: string | null;
  feature: string;
}

export interface DraftStreamV2Request {
  doc_type: string;
  tone: string;
  meta: Record<string, unknown>;
  language?: 'ko' | 'en';
  context?: DocCategory;
  user_request?: string;
  provider?: LLMProvider | null;
  model?: string | null;
  render_template?: boolean;
  /** v3.6 — 사용자 업로드 양식 텍스트 (POST /draft/upload-reference 응답 text) */
  reference_template_text?: string;
  /** v3.6 — 원본 파일명 (UI 표시용, 서버에서 프롬프트 파일명 라벨로 사용) */
  reference_template_name?: string;
}

/** POST /draft/upload-reference 응답 (v3.6 — 사용자 양식 업로드 후 텍스트 추출). */
export interface UploadReferenceResponse {
  ok: boolean;
  filename: string;
  extracted_chars: number;
  truncated: boolean;
  text: string;
  detected_format: 'docx' | 'pdf' | 'hwp' | 'hwpx' | 'txt' | 'md' | 'unsupported';
  warning: string;
}

export type StageStatus = 'running' | 'ok' | 'warn' | 'error';

export interface StageEvent {
  name: string;
  status: StageStatus;
  meta?: Record<string, unknown>;
}
