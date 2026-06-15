// 부록 K — 부서별 Vision/문서 분석 카드 공통 API 클라이언트.
// 16개 카드가 동일 패턴으로 multipart POST → JSON 결과 반환.

import { api } from './client';

export type VisionTaskId =
  | 'business-card' | 'rfq' | 'defect' | 'msds-label' | 'receipt'           // Phase 1
  | 'contract' | 'resume' | 'po' | 'financial-statement' | 'incident'      // Phase 2
  | 'cad-verify' | '5s' | 'error-log' | 'esg' | 'inventory-receive' | 'certificate'; // Phase 3

// PDF/문서 기반 task 는 /document/ 경로, 이미지 기반은 /vision/ 경로.
const DOCUMENT_TASKS = new Set<VisionTaskId>([
  'contract', 'resume', 'financial-statement', 'esg',
]);

export interface VisionTaskResponse<T = Record<string, unknown>> {
  task: string;
  department: string;
  data: T & { _parse_error?: boolean; _raw?: string; _error?: string };
  sources?: Array<{
    citation_id: string;
    source_path: string;
    source_type: string;
    reviewed_at?: string;
    title?: string;
  }>;
  citation_status?: 'verified' | 'corrected' | 'model_only' | 'failed';
}

export async function runVisionTask<T = Record<string, unknown>>(
  task: VisionTaskId,
  file: File,
  department = '',
): Promise<VisionTaskResponse<T>> {
  const prefix = DOCUMENT_TASKS.has(task) ? '/onboarding/document' : '/onboarding/vision';
  const fd = new FormData();
  fd.append('file', file);
  if (department) fd.append('department', department);
  const { data } = await api.post<VisionTaskResponse<T>>(
    `${prefix}/${task}`,
    fd,
    { headers: { 'Content-Type': 'multipart/form-data' } },
  );
  return data;
}

// ── 도메인별 타입 (Phase 1 5개) ──

export interface BusinessCardData {
  name: string;
  name_en: string;
  company: string;
  title: string;
  department: string;
  email: string;
  phone_mobile: string;
  phone_office: string;
  address: string;
}

export interface RFQData {
  customer: string;
  contact_person: string;
  part_number: string;
  part_name: string;
  quantity: number | string;
  due_date: string;
  delivery_location: string;
  special_requirements: string[];
}

export interface DefectData {
  defect_type: string;
  severity: 'critical' | 'major' | 'minor' | string;
  estimated_location: string;
  possible_causes: string[];
  containment_actions: string[];
  recommended_8d_step: string;
}

export interface MSDSLabelData {
  product_name: string;
  manufacturer: string;
  cas_no: string;
  hazard_category: string;
  ghs_pictograms: string[];
  first_aid: string;
  required_ppe: string[];
}

export interface ReceiptData {
  merchant: string;
  date: string;
  amount_supply: number | string;
  amount_vat: number | string;
  amount_total: number | string;
  category: string;
  purpose: string;
  journal_entry: {
    debit_account: string;
    credit_account: string;
    summary: string;
  };
}

// ── Phase 2 ──

export interface ContractData {
  parties: string[];
  duration: string;
  payment_terms: string;
  warranty: string;
  ip_clause: string;
  governing_law: string;
  force_majeure: string;
  termination: string;
  defect_warranty: string;
  confidentiality: string;
  risk_flags: string[];
  checklist_score: number | string;
}

export interface ResumeData {
  name: string;
  email: string;
  phone: string;
  education: { school: string; major: string; graduated: string }[];
  experience: { company: string; role: string; years: string }[];
  skills: string[];
  strengths: string[];
  concerns: string[];
  fit_score: number | string;
  interview_questions: string[];
}

export interface POData {
  po_number: string;
  vendor: string;
  buyer: string;
  issued_date: string;
  delivery_date: string;
  items: { part_number: string; name: string; qty: number; unit_price: number; total: number }[];
  total_amount: number | string;
  payment_terms: string;
  delivery_location: string;
}

export interface FinancialStatementData {
  company: string;
  fiscal_year: string;
  revenue: number | string;
  operating_profit: number | string;
  net_profit: number | string;
  total_assets: number | string;
  total_liabilities: number | string;
  equity: number | string;
  debt_ratio: number | string;
  current_ratio: number | string;
  risk_signals: string[];
  overall_rating: string;
}

export interface IncidentData {
  scene_type: string;
  observed_hazards: string[];
  severity_estimate: string;
  potential_4m_causes: { man: string; machine: string; material: string; method: string };
  immediate_actions: string[];
  report_summary: string;
  required_ppe_missing: string[];
}

// ── Phase 3 ──

export interface CADVerifyData {
  drawing_number: string;
  revision: string;
  title_block_ok: boolean | string;
  dimension_unit: string;
  tolerance_spec: string;
  material_spec: string;
  compliance_score: number | string;
  violations: string[];
}

export interface FiveSData {
  scores: { seiri: number; seiton: number; seiso: number; seiketsu: number; shitsuke: number };
  total_score: number | string;
  strengths: string[];
  improvements: string[];
  priority_actions: string[];
}

export interface ErrorLogData {
  error_message: string;
  stack_excerpt: string;
  likely_cause: string;
  category: string;
  fix_suggestions: string[];
  related_kb_keywords: string[];
}

export interface ESGData {
  company: string;
  report_year: string;
  environment: { carbon_emission_t: number | string; water_use: number | string; renewable_energy_pct: number | string };
  social: { employees: number | string; safety_accidents: number | string; diversity_pct: number | string };
  governance: { board_independence_pct: number | string; audit_findings: number | string };
  rating: string;
}

export interface InventoryReceiveData {
  vendor: string;
  part_number: string;
  package_count: number | string;
  package_condition: string;
  visible_defects: string[];
  ok_to_receive: boolean | string;
  next_action: string;
}

export interface CertificateData {
  course_name: string;
  institution: string;
  completion_date: string;
  hours: number | string;
  certificate_no: string;
  recipient: string;
  category: string;
  hrd_eligible: boolean | string;
}
