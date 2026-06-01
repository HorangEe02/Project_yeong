// 공통 export 포맷 타입 — 모든 모듈(B/D/F/E/A)에서 공유.
// HWP 추가 (Phase 1) — rhwp WASM 통합.

export type ExportFormat =
  | 'docx'
  | 'pdf'
  | 'xlsx'
  | 'csv'
  | 'txt'
  | 'hwp'    // HWP 5.0 바이너리 (rhwp WASM, Phase 1)
  | 'hwpx'   // HWPX XML (rhwp WASM, Phase 1)
  | 'odt'    // ODT (현재 DOCX fallback)
  | 'clipboard';

export interface ExportFormatMeta {
  fmt: ExportFormat;
  label: string;
  ext: string;
  mime: string;
  channel: 'frontend' | 'backend' | 'browser'; // hwp/hwpx → frontend WASM, etc.
}

export const EXPORT_FORMAT_META: Record<ExportFormat, ExportFormatMeta> = {
  docx:      { fmt: 'docx',      label: 'DOCX',  ext: 'docx',  mime: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', channel: 'backend' },
  pdf:       { fmt: 'pdf',       label: 'PDF',   ext: 'pdf',   mime: 'application/pdf',                channel: 'backend' },
  xlsx:      { fmt: 'xlsx',      label: 'XLSX',  ext: 'xlsx',  mime: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', channel: 'backend' },
  csv:       { fmt: 'csv',       label: 'CSV',   ext: 'csv',   mime: 'text/csv; charset=utf-8',         channel: 'backend' },
  txt:       { fmt: 'txt',       label: 'TXT',   ext: 'txt',   mime: 'text/plain; charset=utf-8',       channel: 'backend' },
  hwp:       { fmt: 'hwp',       label: 'HWP',   ext: 'hwp',   mime: 'application/x-hwp',               channel: 'frontend' },
  hwpx:      { fmt: 'hwpx',      label: 'HWPX',  ext: 'hwpx',  mime: 'application/vnd.hancom.hwpx',     channel: 'frontend' },
  odt:       { fmt: 'odt',       label: 'ODT',   ext: 'odt',   mime: 'application/vnd.oasis.opendocument.text', channel: 'backend' },
  clipboard: { fmt: 'clipboard', label: '복사',  ext: '',      mime: '',                                channel: 'browser' },
};

/** 모듈별 권장 포맷 프리셋 */
export const FORMAT_PRESETS: Record<string, ExportFormat[]> = {
  // Module B (Draft) — 모든 포맷 지원
  draft: ['docx', 'pdf', 'hwp', 'hwpx', 'odt', 'xlsx', 'csv', 'txt', 'clipboard'],
  // Module D (Compliance) — 보고서 위주
  compliance: ['docx', 'pdf', 'hwp', 'hwpx', 'xlsx', 'csv'],
  // Module F (Equipment) — 점검/MTBF 보고서
  equipment: ['docx', 'pdf', 'hwp', 'xlsx', 'csv'],
  // Module E (Admin) — 명단/이력
  admin: ['xlsx', 'csv', 'hwp', 'pdf'],
  // Module A (Search) — 인사 검색 결과
  search: ['xlsx', 'csv', 'hwp', 'pdf'],
  // 기본
  default: ['docx', 'pdf', 'hwp', 'xlsx', 'csv', 'txt'],
};

export const FORMAT_LABELS_KO: Record<ExportFormat, string> = {
  docx: 'DOCX',
  pdf: 'PDF',
  xlsx: 'XLSX',
  csv: 'CSV',
  txt: 'TXT',
  hwp: 'HWP',
  hwpx: 'HWPX',
  odt: 'ODT',
  clipboard: '복사',
};
