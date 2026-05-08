// Day 6 Phase 2 — 설비/공정 AI (Module F) TS 타입.
// backend/schemas/equipment.py 의 Pydantic 모델과 1:1 정합.

export type Severity = 'critical' | 'warning' | 'info';
export type RiskLevel = 'critical' | 'warning' | 'normal';
export type ProcessStatus = 'good' | 'warning' | 'critical';
export type EngineStatus = 'online' | 'offline' | 'warning';

export type EquipmentSubTab = 'overview' | 'alerts' | 'equipment' | 'predictive' | 'ml';

// 5공정 슬러그 (DAY6_7_PLAN Section 7-1)
export type ProcessSlug = 'cch' | 'obc' | 'bumper_beam' | 'door' | 'ball_seat' | 'cch_plate';

// ── Overview ────────────────────────────────────────────────

export interface ProcessHealthCard {
  process_id: string;
  process_name: string;
  status: ProcessStatus;
  current_cpk: number;
  cpk_trend: string;
  violation_count: number;
  violated_rules: number[];
  risk_level: RiskLevel;
  anomaly_rate: number;
}

export interface EquipmentTypeCard {
  type: string;
  icon: string;
  codes: number;
  key_metric: string;
  color: string;
}

export interface DashboardMetrics {
  error_codes_total: number;
  error_codes_critical: number;
  molds_total: number;
  molds_warning: number;
  molds_critical: number;
  spc_processes: number;
  inspections_templates: number;
  inspections_recent: number;
}

export interface MLAlert {
  level: string;
  source: string;
  message: string;
}

export interface OverviewResponse {
  processes: ProcessHealthCard[];
  equipment_types: EquipmentTypeCard[];
  metrics: DashboardMetrics;
  ml_alerts: MLAlert[];
}

// ── SPC ─────────────────────────────────────────────────────

export interface NelsonViolation {
  rule_number: number;
  rule_name: string;
  description: string;
  severity: Severity;
  points: number[];
  recommended_action: string;
  chart_annotation: string;
}

export interface SPCData {
  process_id: string;
  process_name: string;
  timestamps: number[];
  values: number[];
  mean: number;
  sigma: number;
  ucl: number;
  lcl: number;
  sigma_1_upper: number;
  sigma_1_lower: number;
  sigma_2_upper: number;
  sigma_2_lower: number;
  usl: number | null;
  lsl: number | null;
}

export interface SPCResponse {
  data: SPCData;
  violations: NelsonViolation[];
  out_of_control: boolean;
  violation_count: number;
}

export interface RecentViolation {
  id: string;
  process_id: string;
  process_name: string;
  rule_number: number;
  severity: Severity;
  message: string;
  timestamp: number;
}

export interface ViolationsResponse {
  items: RecentViolation[];
  total: number;
}

// ── Error Search ────────────────────────────────────────────

export interface ErrorSearchResult {
  code: string;
  equipment_type: string;
  category: string;
  description: string;
  cause: string;
  action: string;
  severity: string;
  score: number;
  rank: number;
}

export interface CausalityInfo {
  causes: string[];
  actions: string[];
}

export interface ManualExcerpt {
  content: string;
  source: string;
  page: string;
  relevance: number;
}

export interface ErrorSearchResponse {
  results: ErrorSearchResult[];
  causality: CausalityInfo | null;
  manual_excerpts: ManualExcerpt[];
}

export interface CategoryGroup {
  equipment_type: string;
  symptoms: string[];
}

export interface ErrorCategoriesResponse {
  groups: CategoryGroup[];
  total_synonyms: number;
}

// ── Markov ──────────────────────────────────────────────────

export interface MarkovPrediction {
  code: string;
  category: string;
  equipment_type: string;
  probability: number;
  expected_delay_hours: number;
  description: string;
  recommended_action: string;
}

export interface CascadeStep {
  code: string;
  category: string;
  probability: number;
  expected_delay_hours: number;
}

export interface CascadeChainItem {
  steps: CascadeStep[];
  total_probability: number;
  total_hours: number;
}

export interface MarkovResponse {
  current_code: string;
  current_category: string;
  next_predictions: MarkovPrediction[];
  cascade_chains: CascadeChainItem[];
  risk_level: RiskLevel;
  prevention_message: string;
}

// ── Mold ────────────────────────────────────────────────────

export interface MoldItem {
  mold_id: string;
  mold_name: string;
  mold_type: string;
  part_name: string;
  current_shots: number;
  max_shots: number;
  life_percent: number;
  remaining_shots: number;
  status: string;
  predicted_remaining_life: number | null;
  predicted_replacement_date: string | null;
  risk_level: RiskLevel | null;
  confidence_interval: number[] | null;
}

export interface MoldsResponse {
  items: MoldItem[];
  total: number;
  critical: number;
  warning: number;
  active: number;
}

// ── MTBF ────────────────────────────────────────────────────

export interface MTBFItem {
  machine_id: string;
  machine_name: string;
  total_repairs: number;
  mtbf_days: number;
  mtbf_std_days: number;
  last_repair_date: string;
  next_predicted_date: string;
  days_until_next: number;
  risk_level: string;
  avg_repair_hours: number;
  avg_repair_cost: number;
  seasonal_pattern: Record<string, number>;
}

export interface MTBFTopCost {
  machine_name: string;
  total_cost: number;
}

export interface MTBFResponse {
  items: MTBFItem[];
  top5_cost: MTBFTopCost[];
  seasonal_message: string;
  machines_attention: number;
}

// ── ML Engines ──────────────────────────────────────────────

export interface MLEngineStatus {
  id: string;
  name_en: string;
  name_ko: string;
  library: string;
  status: EngineStatus;
  accuracy: number | null;
  last_trained: string | null;
  description: string;
}

export interface MLEnginesStatusResponse {
  engines: MLEngineStatus[];
  online_count: number;
  total: number;
}

// ── Manual / Inspection ─────────────────────────────────────

export interface ManualSearchResponse {
  items: ManualExcerpt[];
  total: number;
}

export interface ChecklistItem {
  item: string;
  standard: string;
  unit: string;
}

export interface ChecklistTemplate {
  id: number;
  template_name: string;
  equipment_type: string;
  checklist_type: string;
  items: ChecklistItem[];
}

export interface InspectionChecklistResponse {
  templates: ChecklistTemplate[];
  total: number;
}

export interface SPCUploadResponse {
  process_id: string;
  n_samples: number;
  mean: number;
  std: number;
  cpk: number | null;
  grade: string;
  violation_count: number;
}
