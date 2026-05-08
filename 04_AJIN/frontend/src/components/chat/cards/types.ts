// v3.3 Phase F — 인-챗 액션 카드 5종 공통 타입.
// 백엔드 backend/schemas/onboarding.py 의 *CardPayload 와 정합.

export type ActionKind = 'document' | 'draft' | 'compliance' | 'employee' | 'error';

// ── Document ─────────────────────────────────────────
export interface DocumentItem {
  doc_id: string;
  title: string;
  doc_type?: string;
  snippet?: string;
  score?: number;
  download_url?: string;
}

export interface DocumentCardPayload {
  items: DocumentItem[];
  total: number;
  query: string;
}

// ── Draft ────────────────────────────────────────────
export interface DraftCardPayload {
  title: string;
  doc_type: string;
  markdown_preview: string;
  full_view_url: string;
}

// ── Compliance ───────────────────────────────────────
export interface ComplianceCardPayload {
  regulation_id: string;
  title: string;
  severity: string; // "CRITICAL" | "HIGH" | "MEDIUM" | ""
  effective_date: string;
  days_until_effective: number | null;
  excerpt: string;
  affected_departments: string[];
  full_view_url: string;
}

// ── Employee ─────────────────────────────────────────
export interface EmployeeContact {
  extension?: string | null;
  email?: string | null;
  phone?: string | null;
}

export interface EmployeeItem {
  name: string;
  department: string;
  position: string;
  visibility: 'FULL' | 'PARTIAL';
  contact: EmployeeContact;
}

export interface EmployeeCardPayload {
  items: EmployeeItem[];
  total: number;
  query: string;
  auth_required: boolean;
  // v3.6 — total > items.length 인 경우 백엔드가 표시 cap 을 적용했음을 알림
  truncated?: boolean;
}

// ── Error / SPC ──────────────────────────────────────
export interface ErrorPrediction {
  code: string;
  probability: number; // 0.0 ~ 1.0
  description: string;
}

export interface ErrorCardPayload {
  code: string;
  error_name: string;
  severity: string; // "HIGH" | "MEDIUM" | "LOW" | ""
  cause: string;
  action: string;
  avg_recovery_min: number | null;
  history_count: number | null;
  next_likely: ErrorPrediction[];
  full_view_url: string;
}

// ── 통합 카드 union ───────────────────────────────────
export type ActionCard =
  | { kind: 'document'; payload: DocumentCardPayload }
  | { kind: 'draft'; payload: DraftCardPayload }
  | { kind: 'compliance'; payload: ComplianceCardPayload }
  | { kind: 'employee'; payload: EmployeeCardPayload }
  | { kind: 'error'; payload: ErrorCardPayload };
