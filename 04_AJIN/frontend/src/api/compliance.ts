// Module D — Compliance API 클라이언트.
// backend/routers/compliance.py 12 endpoints 1:1 매핑.

import { api } from './client';

// baseURL 이 이미 '/api' 로 끝남 (client.ts) — 짧은 path 사용
const BASE = '/compliance';

// ─────────────────────────────────────────────────────────────
// Scenarios
// ─────────────────────────────────────────────────────────────

export interface ScenarioRaw {
  scenario_id?: string;
  id?: string;
  title?: string;
  description?: string;
  severity?: 'high' | 'medium' | 'low' | string;
  category?: string;
  deadline?: string;
  effective_date?: string;
  applicable_plants?: string[];
  affected_facility_ids?: string[];
  affected_process_types?: string[];
  required_actions?: string[];
  estimated_cost?: string;
  reference_url?: string;
  regulation?: { name?: string; article?: string; authority?: string; category?: string };
  change_detail?: {
    before?: { text?: string; effective_date?: string; version?: string };
    after?: { text?: string; effective_date?: string; version?: string };
  };
}

export interface ScenarioListResponse {
  scenarios: ScenarioRaw[];
  total: number;
}

export async function fetchScenarios(): Promise<ScenarioListResponse> {
  const { data } = await api.get<ScenarioListResponse>(`${BASE}/scenarios`);
  return data;
}

// ─────────────────────────────────────────────────────────────
// Facilities (19 개소)
// ─────────────────────────────────────────────────────────────

export interface FacilityItem {
  plant_id: string;
  name: string;
  location: string;
  address: string;
  certifications: string[];
  processes: string[];
  kind: 'plant' | 'subsidiary_domestic' | 'subsidiary_overseas';
  country: string;
  lat?: number | null;
  lng?: number | null;
}

export interface FacilityListResponse {
  facilities: FacilityItem[];
  total: number;
  domestic: number;
  overseas: number;
}

export async function fetchFacilities(): Promise<FacilityListResponse> {
  const { data } = await api.get<FacilityListResponse>(`${BASE}/facilities`);
  return data;
}

// ─────────────────────────────────────────────────────────────
// Risk scores (D-2-2)
// ─────────────────────────────────────────────────────────────

export interface RiskScoreItem {
  scenario_id: string;
  title: string;
  total_score: number;
  grade: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | string;
  financial_impact: number;
  likelihood: number;
  urgency: number;
  deadline: string | null;
  days_remaining: number | null;
  affected_plants: string[];
  mitigation_status: string;
}

export interface RiskScoreResponse {
  total: number;
  summary: {
    total?: number;
    critical?: number;
    high?: number;
    medium?: number;
    low?: number;
    avg_score?: number;
    top_risk?: string;
    nearest_deadline?: RiskScoreItem;
  };
  scores: RiskScoreItem[];
}

export async function fetchRiskScores(): Promise<RiskScoreResponse> {
  const { data } = await api.get<RiskScoreResponse>(`${BASE}/risk/scores`);
  return data;
}

// ─────────────────────────────────────────────────────────────
// Tariff simulator (D-2-5)
// ─────────────────────────────────────────────────────────────

export interface TariffSimItem {
  product: string;
  tariff_rate: number;
  unit_tariff: number;
  annual_tariff: number;
  annual_tariff_krw: number;
  cost_increase_pct: number;
}

export interface TariffSimResponse {
  tariff_rate: number;
  exchange_rate: number;
  total_annual_usd: number;
  total_annual_krw: number;
  total_annual_krw_billion: number;
  avg_cost_increase: number;
  results: TariffSimItem[];
}

export async function simulateTariff(
  tariff_rate: number,
  exchange_rate = 1380,
): Promise<TariffSimResponse> {
  const { data } = await api.post<TariffSimResponse>(`${BASE}/tariff/simulate`, {
    tariff_rate,
    exchange_rate,
  });
  return data;
}

// ─────────────────────────────────────────────────────────────
// Plotly Figure (timeline / network)
// ─────────────────────────────────────────────────────────────

export interface PlotlyFigure {
  data: unknown[];
  layout: Record<string, unknown>;
}

export interface PlotlyResponse {
  figure: PlotlyFigure;
}

export async function fetchTimeline(): Promise<PlotlyResponse> {
  const { data } = await api.get<PlotlyResponse>(`${BASE}/timeline`);
  return data;
}

export async function fetchImpactNetwork(scenarioId: string): Promise<PlotlyResponse> {
  const { data } = await api.get<PlotlyResponse>(
    `${BASE}/network/${encodeURIComponent(scenarioId)}`,
  );
  return data;
}

// ─────────────────────────────────────────────────────────────
// Change detector (D-2-6)
// ─────────────────────────────────────────────────────────────

export interface ChangeItem {
  id: number;
  regulation_type: string;
  change_type: 'added' | 'modified' | 'removed' | string;
  item_id: string;
  title: string;
  summary: string;
  detected_at: string;
  acknowledged: boolean;
  // v4.x — Issue 3: 보고서 enrichment (변경 이력 + 사내 영향)
  before_text?: string;
  after_text?: string;
  diff_html?: string;
  impact_json?: string;
}

/** ImpactAnalyzer 결과 (impact_json 을 JSON.parse 한 결과). */
export interface RegulationImpact {
  affected_plants?: string[];
  affected_processes?: string[];
  affected_workers?: number;
  affected_chemicals?: string[];
  affected_standards?: string[];
  risk_score?: number;
  severity?: string;
  required_actions?: string[];
  deadline?: string;
  estimated_cost?: string;
}

export interface ChangeListResponse {
  total: number;
  stats: {
    total?: number;
    unacknowledged?: number;
    added?: number;
    modified?: number;
    removed?: number;
  };
  changes: ChangeItem[];
}

export async function fetchChanges(
  limit = 20,
  unackOnly = false,
  regulationType?: string,
  itemId?: string,
): Promise<ChangeListResponse> {
  const params: Record<string, string | number | boolean> = {
    limit,
    unack_only: unackOnly,
  };
  if (regulationType) params.regulation_type = regulationType;
  if (itemId) params.item_id = itemId;
  const { data } = await api.get<ChangeListResponse>(`${BASE}/changes/recent`, {
    params,
  });
  return data;
}

export async function acknowledgeChange(id: number): Promise<{ ok: boolean; change_id: number }> {
  const { data } = await api.post<{ ok: boolean; change_id: number }>(
    `${BASE}/changes/${id}/acknowledge`,
  );
  return data;
}

// ─────────────────────────────────────────────────────────────
// MVP — Change Feed + Workflow + KPI
// ─────────────────────────────────────────────────────────────

export type ChangeGrade = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
export type ChangeStatus =
  | 'pending'
  | 'reviewing'
  | 'planning'
  | 'announced'
  | 'done'
  | 'filtered';

export type LegalClass =
  | 'criminal'
  | 'administrative'
  | 'civil'
  | 'contract'
  | 'standardization';

export interface AuditEvent {
  ts: string;
  user: string;
  action: string;
  from?: string;
  to?: string;
}

export interface ChangeFeedItem {
  id: number;
  regulation_type: string;
  change_type: string; // added | modified | removed
  item_id: string;
  item_title: string;
  summary_ko: string;
  grade: ChangeGrade;
  severity: string;
  status: ChangeStatus;
  affected_departments: string[];
  affected_plants: string[];
  assigned_to: string;
  detected_at: string;
  acknowledged: boolean;
  audit_trail: AuditEvent[];
  old_value: string;
  new_value: string;
  // P1 D1 — 법무 5분류 + 벌칙
  legal_class: LegalClass[];
  penalty_extract: string;
  penalty_severity_krw_mn: number;
}

export interface ChangeFeedResponse {
  total: number;
  items: ChangeFeedItem[];
  has_more: boolean;
}

export async function fetchChangeFeed(opts: {
  grade?: ChangeGrade;
  status?: ChangeStatus;
  dept?: string;
  legalClass?: LegalClass;
  since?: string;
  includeFiltered?: boolean;
  limit?: number;
  offset?: number;
} = {}): Promise<ChangeFeedResponse> {
  const { data } = await api.get<ChangeFeedResponse>(`${BASE}/changes/feed`, {
    params: {
      grade: opts.grade,
      status: opts.status,
      dept: opts.dept,
      legal_class: opts.legalClass,
      since: opts.since,
      include_filtered: opts.includeFiltered ?? false,
      limit: opts.limit ?? 50,
      offset: opts.offset ?? 0,
    },
  });
  return data;
}

export async function transitionChangeStatus(
  id: number,
  newStatus: ChangeStatus,
  opts: { reviewNote?: string; overrideReason?: string } = {},
): Promise<{
  ok: boolean;
  change_id: number;
  new_status: string;
  review_required?: boolean;
  override_used?: boolean;
}> {
  const { data } = await api.post(`${BASE}/changes/${id}/transition`, {
    new_status: newStatus,
    review_note: opts.reviewNote ?? '',
    override_reason: opts.overrideReason ?? '',
  });
  return data;
}

export interface ChangeKpiTrendPoint {
  day: string;
  CRITICAL: number;
  HIGH: number;
  MEDIUM: number;
  LOW: number;
}

export interface ChangeKpiResponse {
  month_critical: number;
  month_high: number;
  month_medium: number;
  month_low: number;
  open_count: number;
  avg_hours_to_done: number;
  today_new: number;
  trend: ChangeKpiTrendPoint[];
}

export async function fetchChangeKpi(windowDays = 30): Promise<ChangeKpiResponse> {
  const { data } = await api.get<ChangeKpiResponse>(`${BASE}/changes/kpi`, {
    params: { window_days: windowDays },
  });
  return data;
}

// P3 D13 — 확장 트렌드
export interface DeptHandlingTime {
  department: string;
  avg_hours: number;
  count: number;
}

export interface ExtendedTrendResponse {
  window_days: number;
  monthly_grade_trend: Array<{
    month: string;
    CRITICAL: number;
    HIGH: number;
    MEDIUM: number;
    LOW: number;
  }>;
  by_dept_handling_hours: DeptHandlingTime[];
  by_legal_class: Record<string, number>;
  total: number;
}

export async function fetchExtendedTrend(windowDays = 180): Promise<ExtendedTrendResponse> {
  const { data } = await api.get<ExtendedTrendResponse>(`${BASE}/changes/extended-trend`, {
    params: { window_days: windowDays },
  });
  return data;
}

// P3 D9 — 협업 티켓
export interface CollabTicketOwner {
  employee_id: string;
  name: string;
  email: string;
  position: string;
}

export interface CreateTicketResponse {
  ok: boolean;
  ticket_id: number;
  departments: string[];
  owners: CollabTicketOwner[];
  slack_sent: boolean;
  external_url: string;
  error?: string;
}

export async function createCollabTicket(changeId: number): Promise<CreateTicketResponse> {
  const { data } = await api.post<CreateTicketResponse>(
    `${BASE}/changes/${changeId}/tickets`,
  );
  return data;
}

// P3 D10 — What-if 시뮬레이션
export type WhatIfScenarioType = 'tariff' | 'fx' | 'chemical' | 'labor' | 'carbon' | 'natural_language';

export interface WhatIfMeta {
  data_source?: string;
  confidence?: number;
  as_of?: string;
  corp_code?: string;
}

export interface WhatIfResponse {
  scenario_type: string;
  params: Record<string, unknown>;
  baseline_kpi: Record<string, number>;
  new_kpi: Record<string, number>;
  delta: Record<string, number>;
  delta_pct: Record<string, number>;
  by_dimension: Array<Record<string, unknown>>;
  note: string;
  meta?: WhatIfMeta;
}

export async function simulateWhatIf(
  scenarioType: WhatIfScenarioType,
  params: Record<string, unknown>,
  changeId?: number,
): Promise<WhatIfResponse> {
  const { data } = await api.post<WhatIfResponse>(`${BASE}/whatif/simulate`, {
    scenario_type: scenarioType,
    params,
    change_id: changeId ?? null,
  });
  return data;
}

// P3 D11 — 산업 트렌드
export interface IndustryCorpFilings {
  corp_code: string;
  corp_name: string;
  count: number;
  sample_reports: Array<{
    rcept_no: string;
    report_nm: string;
    rcept_dt: string;
  }>;
}

export interface IndustryContextResponse {
  change_keywords: string[];
  matching_filings_count: number;
  by_corp: IndustryCorpFilings[];
  industry_average_filings: number;
  verdict: 'industry_wide' | 'company_specific' | 'no_data' | string;
  available: boolean;
}

export async function fetchIndustryContext(changeId: number): Promise<IndustryContextResponse> {
  const { data } = await api.get<IndustryContextResponse>(
    `${BASE}/changes/${changeId}/industry-context`,
  );
  return data;
}

// P2 D5 — Feedback Loop
export type CorrectableField =
  | 'affected_departments'
  | 'affected_plants'
  | 'legal_class'
  | 'grade'
  | 'summary_ko'
  | 'penalty_extract';

export async function correctChange(
  id: number,
  field: CorrectableField,
  newValue: unknown,
  note?: string,
): Promise<{ ok: boolean; correction_id: number }> {
  const { data } = await api.post(`${BASE}/changes/${id}/correct`, {
    field,
    new_value: newValue,
    note: note ?? '',
  });
  return data;
}

export interface CorrectionStats {
  total: number;
  by_field: Record<string, number>;
  by_role: Record<string, number>;
  frequent_dept_changes: Array<[string, number]>;
  accuracy_signal: Record<string, number>;
  window_days: number;
}

export async function fetchCorrectionStats(windowDays = 30): Promise<CorrectionStats> {
  const { data } = await api.get<CorrectionStats>(`${BASE}/changes/correction-stats`, {
    params: { window_days: windowDays },
  });
  return data;
}

// P2 D8 — 외부 판례 RAG
export interface CaseLawItem {
  case_id: string;
  court: string;
  date: string;
  title: string;
  summary_excerpt: string;
  similarity: number;
  full_url: string;
}

export interface SimilarCasesResponse {
  items: CaseLawItem[];
  available: boolean;
  note: string;
}

export async function fetchSimilarCases(
  changeId: number,
  topK = 3,
): Promise<SimilarCasesResponse> {
  const { data } = await api.get<SimilarCasesResponse>(
    `${BASE}/changes/${changeId}/similar-cases`,
    { params: { top_k: topK } },
  );
  return data;
}

// P2 D7 — 계약 영향 분석
export interface AffectedContractItem {
  contract_id: string;
  counterparty: string;
  type: string;
  clause_no: string;
  title: string;
  body_excerpt: string;
  similarity?: number | null;
  match_keywords: string[];
  source: 'vector' | 'keyword' | string;
}

export interface AffectedContractsResponse {
  items: AffectedContractItem[];
}

export async function fetchAffectedContracts(
  changeId: number,
  topK = 5,
): Promise<AffectedContractsResponse> {
  const { data } = await api.get<AffectedContractsResponse>(
    `${BASE}/changes/${changeId}/affected-contracts`,
    { params: { top_k: topK } },
  );
  return data;
}

// P2 D6 — 공급망
export interface AffectedSupplierItem {
  supplier_id: string;
  name: string;
  tier: number;
  country: string;
  contact_email: string;
  annual_volume_krw_mn: number;
  compliance_score: number;
  match_reasons: string[];
}

export interface AffectedSuppliersResponse {
  items: AffectedSupplierItem[];
}

export async function fetchAffectedSuppliers(
  changeId: number,
  topK = 20,
): Promise<AffectedSuppliersResponse> {
  const { data } = await api.get<AffectedSuppliersResponse>(
    `${BASE}/changes/${changeId}/affected-suppliers`,
    { params: { top_k: topK } },
  );
  return data;
}

export interface CostSimSupplierBreakdown {
  supplier_id: string;
  name: string;
  country: string;
  baseline_krw_mn: number;
  additional_tariff_krw_mn: number;
}

export interface CostSimulationResponse {
  baseline_cost_krw_mn: number;
  new_cost_krw_mn: number;
  delta_krw_mn: number;
  delta_pct: number;
  by_supplier: CostSimSupplierBreakdown[];
  applicable_hs: string[];
  scenario_rate_pct: number;
  chemical_substitution: {
    substances_detected?: string[];
    estimated_delta_pct?: number;
    by_substance?: Array<{ name: string; delta_pct: number }>;
    note?: string;
  };
}

export async function fetchCostSimulation(
  changeId: number,
  scenarioRatePct = 25.0,
): Promise<CostSimulationResponse> {
  const { data } = await api.get<CostSimulationResponse>(
    `${BASE}/changes/${changeId}/cost-simulation`,
    { params: { scenario_rate_pct: scenarioRatePct } },
  );
  return data;
}

export interface AlternativeSupplierItem {
  supplier_id: string;
  name: string;
  tier: number;
  country: string;
  compliance_score: number;
  annual_volume_krw_mn: number;
  avg_unit_price_krw: number;
  score_total: number;
  score_breakdown: Record<string, number>;
}

export async function fetchSupplierAlternatives(
  supplierId: string,
  topK = 3,
): Promise<{ items: AlternativeSupplierItem[] }> {
  const { data } = await api.get<{ items: AlternativeSupplierItem[] }>(
    `${BASE}/suppliers/${encodeURIComponent(supplierId)}/alternatives`,
    { params: { top_k: topK } },
  );
  return data;
}

export async function sendSupplierAssessment(
  supplierId: string,
  changeId: number,
): Promise<{
  ok: boolean;
  assessment_id: number;
  status: string;
  sent_via_smtp: boolean;
  error?: string;
}> {
  const { data } = await api.post(
    `${BASE}/suppliers/${encodeURIComponent(supplierId)}/send-assessment`,
    { change_id: changeId },
  );
  return data;
}

// P1 D2 — 임원 보고서 다운로드
export type ExecReportFormat = 'markdown' | 'docx_boon_bujang';

/** 보고서 다운로드 — Blob 응답을 호출자가 다운로드 트리거. */
export async function downloadExecReport(opts: {
  format: ExecReportFormat;
  since?: string; // YYYY-MM-DD
  until?: string;
}): Promise<{ blob: Blob; filename: string }> {
  const res = await api.get<Blob>(`${BASE}/changes/exec-report`, {
    params: {
      format: opts.format,
      since: opts.since,
      until: opts.until,
    },
    responseType: 'blob',
  });
  // Content-Disposition 에서 filename 추출
  const disp = res.headers['content-disposition'] || '';
  const match = /filename="([^"]+)"/.exec(disp);
  const filename = match
    ? match[1]
    : `compliance-report.${opts.format === 'markdown' ? 'md' : 'docx'}`;
  return { blob: res.data, filename };
}

// ─────────────────────────────────────────────────────────────
// Classifier (D-2-8)
// ─────────────────────────────────────────────────────────────

export interface ClassifyResponse {
  severity: 'HIGH' | 'MEDIUM' | 'LOW' | string;
  confidence: number;
  all_scores: Record<string, number>;
  related_departments: string[];
  affected_plants: string[];
  risk_score: number;
  recommended_actions: string[];
  response_deadline: string;
}

export async function classifyRegulation(text: string): Promise<ClassifyResponse> {
  const { data } = await api.post<ClassifyResponse>(`${BASE}/classify`, { text });
  return data;
}

// ─────────────────────────────────────────────────────────────
// Crawler (D-2-1, D-2-12)
// ─────────────────────────────────────────────────────────────

export type CrawlerName =
  | 'iso'
  | 'apqp'
  | 'msds'
  | 'domestic_law'
  | 'eu_regulation'
  | 'oem_quality'
  | 'carbon_esg'
  | 'ev_battery'
  | 'global_trade';

export interface CrawlRunResult {
  name: string;
  crawled_at: string;
  source: string;
  total_count: number;
  updates_found: number;
  errors: string[];
  source_type?: 'live' | 'curated';
}

export type CrawlSlaStatus = 'fresh' | 'stale' | 'degraded' | 'missing_credential';

export interface CrawlSlaItem {
  status: CrawlSlaStatus;
  official_source: string;
  cadence: string;
  max_stale_hours: number;
  fallback_allowed: boolean;
  official_domains: string[];
  credential_required: boolean;
  credential_present: boolean;
  source_type: 'live' | 'curated' | 'unknown';
  last_success_at: string;
  last_run_at: string;
  last_http_status: number | null;
  last_http_etag: string;
  last_http_last_modified: string;
  age_hours: number | null;
}

export interface CrawlRunAllResult {
  crawlers: Record<CrawlerName, CrawlRunResult>;
  total_changes: number;
}

export async function runCrawler(name: CrawlerName): Promise<CrawlRunResult> {
  const { data } = await api.post<CrawlRunResult>(`${BASE}/crawl/run/${name}`, null, {
    timeout: 60_000,
  });
  return data;
}

export async function runAllCrawlers(): Promise<CrawlRunAllResult> {
  const { data } = await api.post<CrawlRunAllResult>(`${BASE}/crawl/run-all`, null, {
    timeout: 180_000,
  });
  return data;
}

// ─────────────────────────────────────────────────────────────
// Check (rule-based, 기존)
// ─────────────────────────────────────────────────────────────

export interface ComplianceCheckResponse {
  answer: string;
  relevant_standards: string[];
  compliance_status: string;
  source: string;
}

export async function checkCompliance(
  query: string,
  targetDepartment?: string,
): Promise<ComplianceCheckResponse> {
  const { data } = await api.post<ComplianceCheckResponse>(`${BASE}/check`, {
    query,
    target_department: targetDepartment,
  });
  return data;
}


// ─────────────────────────────────────────────────────────────
// v3.6 Phase 2 — 시나리오 통합 시뮬레이션 + 크롤링 결과 조회
// ─────────────────────────────────────────────────────────────

export interface ScenarioSimRiskScore {
  total: number;
  fin: number;
  pos: number;
  urg: number;
}

export interface ScenarioSimImpact {
  plants: string[];
  departments: string[];
  cost_estimate_krw_bn: number;
  cost_breakdown: Record<string, unknown>[];
}

export interface ScenarioSimEvidence {
  title: string;
  url: string;
}

export interface ScenarioSimulateResponse {
  scenario_id: string;
  title: string;
  category: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | string;
  deadline_days: number;
  description: string;
  risk_score: ScenarioSimRiskScore;
  impact: ScenarioSimImpact;
  recommended_actions: string[];
  evidence_links: ScenarioSimEvidence[];
}

export async function simulateScenario(
  scenarioId: string,
  opts?: { tariff_rate?: number; exchange_rate?: number },
): Promise<ScenarioSimulateResponse> {
  const { data } = await api.post<ScenarioSimulateResponse>(
    `${BASE}/scenarios/${encodeURIComponent(scenarioId)}/simulate`,
    opts ?? {},
  );
  return data;
}

export interface CrawlResultMeta {
  name: string;
  filename: string;
  crawled_at: string;
  source: string;
  total_count: number;
  updates_found: number;
  errors: string[];
  size_bytes: number;
  source_type?: 'live' | 'curated';
}

export interface CrawlResultsListResponse {
  crawlers: CrawlResultMeta[];
  total: number;
}

export async function fetchCrawlResultsList(): Promise<CrawlResultsListResponse> {
  const { data } = await api.get<CrawlResultsListResponse>(`${BASE}/crawl/results`);
  return data;
}

export interface CrawlResultItem {
  title: string;
  url: string;
  summary: string;
  extra: Record<string, unknown>;
}

export interface CrawlResultDetailResponse {
  name: string;
  filename: string;
  crawled_at: string;
  source: string;
  total: number;
  items: CrawlResultItem[];
  has_more: boolean;
}

export async function fetchCrawlResultDetail(
  name: string,
  limit = 50,
  offset = 0,
): Promise<CrawlResultDetailResponse> {
  const { data } = await api.get<CrawlResultDetailResponse>(
    `${BASE}/crawl/results/${encodeURIComponent(name)}`,
    { params: { limit, offset } },
  );
  return data;
}


// ─────────────────────────────────────────────────────────────
// v3.6 Phase 3 — 시나리오 상세 (Item 1)
// ─────────────────────────────────────────────────────────────

export interface ScenarioRegulationMeta {
  name: string;
  article: string;
  authority: string;
  category: string;
}

export interface ScenarioChangeVersion {
  text: string;
  effective_date: string;
  version: string;
}

export interface ScenarioReference {
  title: string;
  url: string;
}

export interface ScenarioDetailResponse {
  scenario_id: string;
  title: string;
  description: string;
  regulation: ScenarioRegulationMeta;
  change_before: ScenarioChangeVersion | null;
  change_after: ScenarioChangeVersion | null;
  severity: string;
  impact_areas: string[];
  applicable_plants: string[];
  affected_facility_ids: string[];
  affected_process_types: string[];
  deadline: string;
  days_remaining: number;
  required_actions: string[];
  estimated_cost: string;
  references: ScenarioReference[];
  raw: Record<string, unknown>;
}

export async function fetchScenarioDetail(
  scenarioId: string,
): Promise<ScenarioDetailResponse> {
  const { data } = await api.get<ScenarioDetailResponse>(
    `${BASE}/scenarios/${encodeURIComponent(scenarioId)}/detail`,
  );
  return data;
}

// ─────────────────────────────────────────────────────────────
// G1: 법규 전문 검색 (Meilisearch)
// ─────────────────────────────────────────────────────────────

export type ComplianceSearchIndex = 'regulations' | 'scenarios' | 'glossary' | 'all';

export interface ComplianceSearchHit {
  id: string;
  index: 'regulations' | 'scenarios' | 'glossary';
  title: string;
  snippet: string;
  score?: number | null;
  payload: Record<string, unknown>;
}

export interface ComplianceSearchResponse {
  query: string;
  total: number;
  elapsed_ms: number;
  hits: ComplianceSearchHit[];
  available: boolean;
}

export interface ComplianceSearchHealth {
  meili_status: string;
  available: boolean;
  counts: Record<string, number>;
  is_indexing: boolean;
}

export async function searchCompliance(params: {
  q: string;
  index?: ComplianceSearchIndex;
  limit?: number;
  offset?: number;
  doc_type?: string;
  severity?: string;
  country?: string;
}): Promise<ComplianceSearchResponse> {
  const { data } = await api.get<ComplianceSearchResponse>(`${BASE}/search`, { params });
  return data;
}

export async function fetchComplianceSearchHealth(): Promise<ComplianceSearchHealth> {
  const { data } = await api.get<ComplianceSearchHealth>(`${BASE}/search/health`);
  return data;
}

// ─────────────────────────────────────────────────────────────
// G1-F5: 단일 법령 상세 (/compliance/reg/:id)
// ─────────────────────────────────────────────────────────────

export interface RegulationDoc {
  reg_id: string;
  parent_pk?: number;
  natural_id?: string;
  title: string;
  title_ko?: string;
  article_no?: string;
  body?: string;
  doc_type?: string;
  category?: string;
  authority?: string;
  compliance_status?: string;
  country?: string;
  tags?: string[];
  effective_date?: string;
  last_amended?: string;
  [key: string]: unknown;
}

export async function fetchRegulationById(regId: string): Promise<RegulationDoc> {
  const { data } = await api.get<RegulationDoc>(
    `${BASE}/regulations/${encodeURIComponent(regId)}`,
  );
  return data;
}

// ─────────────────────────────────────────────────────────────
// G7: 글로서리 (용어 사전)
// ─────────────────────────────────────────────────────────────

export interface GlossaryTerm {
  term: string;
  ko?: string;
  en?: string;
  definition: string;
  category?: string;
  aliases?: string[];
}

export interface GlossaryListResponse {
  terms: GlossaryTerm[];
  total: number;
}

export async function fetchGlossary(): Promise<GlossaryListResponse> {
  const { data } = await api.get<GlossaryListResponse>(`${BASE}/glossary`);
  return data;
}

// ─────────────────────────────────────────────────────────────
// P4 D14 — 권한 위임 룰 엔진
// ─────────────────────────────────────────────────────────────

export interface DelegationConditions {
  grade_in?: string[] | null;
  departments_subset_of?: string[] | null;
  legal_class_in?: string[] | null;
  penalty_max_krw_mn?: number | null;
  keywords_any?: string[] | null;
}

export interface DelegationActions {
  assign_to?: string | null;
  transition_to?: string | null;
  notify_slack?: string[] | null;
  auto_create_ticket?: boolean;
}

export interface DelegationRuleItem {
  id: number;
  name: string;
  owner: string;
  enabled: boolean;
  conditions: DelegationConditions;
  actions: DelegationActions;
  priority: number;
  created_at: string;
  updated_at: string;
}

export interface DelegationRuleListResponse {
  items: DelegationRuleItem[];
  total: number;
}

export interface DelegationRuleCreatePayload {
  name: string;
  enabled?: boolean;
  conditions?: DelegationConditions;
  actions?: DelegationActions;
  priority?: number;
}

export type DelegationRuleUpdatePayload = Partial<DelegationRuleCreatePayload>;

export interface DelegationRuleMutationResponse {
  ok: boolean;
  rule_id: number;
}

export interface DelegationDryRunMatch {
  change_id: number;
  item_title: string;
  rule_id: number;
  rule_name: string;
  applied_actions: Record<string, unknown>;
}

export interface DelegationDryRunResponse {
  scanned: number;
  matched: number;
  by_rule: Record<string, number>;
  matches: DelegationDryRunMatch[];
}

export async function listDelegationRules(
  enabledOnly = false,
): Promise<DelegationRuleListResponse> {
  const { data } = await api.get<DelegationRuleListResponse>(
    `${BASE}/delegation-rules`,
    { params: { enabled_only: enabledOnly } },
  );
  return data;
}

export async function createDelegationRule(
  payload: DelegationRuleCreatePayload,
): Promise<DelegationRuleMutationResponse> {
  const { data } = await api.post<DelegationRuleMutationResponse>(
    `${BASE}/delegation-rules`,
    payload,
  );
  return data;
}

export async function updateDelegationRule(
  ruleId: number,
  payload: DelegationRuleUpdatePayload,
): Promise<DelegationRuleMutationResponse> {
  const { data } = await api.patch<DelegationRuleMutationResponse>(
    `${BASE}/delegation-rules/${ruleId}`,
    payload,
  );
  return data;
}

export async function deleteDelegationRule(
  ruleId: number,
): Promise<DelegationRuleMutationResponse> {
  const { data } = await api.delete<DelegationRuleMutationResponse>(
    `${BASE}/delegation-rules/${ruleId}`,
  );
  return data;
}

export async function dryRunDelegationRules(
  limit = 50,
): Promise<DelegationDryRunResponse> {
  const { data } = await api.post<DelegationDryRunResponse>(
    `${BASE}/delegation-rules/dry-run`,
    null,
    { params: { limit } },
  );
  return data;
}

// ─────────────────────────────────────────────────────────────
// P4 D15 — 신입 학습경로
// ─────────────────────────────────────────────────────────────

export interface LearningProgressItem {
  id: number;
  path_id: number;
  week: number;
  change_id: number;
  read_at: string;
  quiz_score: number;
  quiz_attempts: number;
  mentor_review: string;
  mentor_comment: string;
  updated_at: string;
}

export interface LearningPathDetail {
  id: number;
  name: string;
  owner_employee_id: string;
  week_count: number;
  curriculum: { week: number; change_ids: number[]; min_quiz_score: number }[];
  progress: LearningProgressItem[];
  status: string;
  created_at: string;
}

export interface LearningMyProgressResponse {
  paths: LearningPathDetail[];
}

export interface LearningMentorQueueItem {
  id: number;
  path_id: number;
  path_name: string;
  assignee_employee_id: string;
  week: number;
  change_id: number;
  quiz_score: number;
  quiz_attempts: number;
  mentor_review: string;
  updated_at: string;
}

export interface LearningMentorQueueResponse {
  items: LearningMentorQueueItem[];
  total: number;
}

export interface LearningPathCreatePayload {
  name: string;
  assignee_employee_id: string;
  week_split: number[][];
  min_quiz_score?: number;
}

export interface LearningPathCreateResponse {
  ok: boolean;
  path_id: number;
}

export interface LearningQuizResponse {
  ok: boolean;
  correct: boolean;
  score: number;
  answer_index: number;
  question: string;
  error?: string;
}

export interface LearningReviewResponse {
  ok: boolean;
  verdict: string;
  reviewer: string;
  error?: string;
}

export async function createLearningPath(
  payload: LearningPathCreatePayload,
): Promise<LearningPathCreateResponse> {
  const { data } = await api.post<LearningPathCreateResponse>(
    `${BASE}/learning-path`, payload,
  );
  return data;
}

export async function fetchMyLearning(): Promise<LearningMyProgressResponse> {
  const { data } = await api.get<LearningMyProgressResponse>(`${BASE}/learning-path/my`);
  return data;
}

export async function fetchMentorQueue(): Promise<LearningMentorQueueResponse> {
  const { data } = await api.get<LearningMentorQueueResponse>(
    `${BASE}/learning-path/mentor-queue`,
  );
  return data;
}

export interface LearningQuizPreviewResponse {
  ok: boolean;
  progress_id: number;
  change_id: number;
  question: string;
  choices: string[];
  generated_by: string;
  error?: string;
}

export async function fetchLearningQuizPreview(
  progressId: number,
): Promise<LearningQuizPreviewResponse> {
  const { data } = await api.get<LearningQuizPreviewResponse>(
    `${BASE}/learning-path/${progressId}/quiz`,
  );
  return data;
}

export async function takeLearningQuiz(
  progressId: number,
  choiceIndex: number,
): Promise<LearningQuizResponse> {
  const { data } = await api.post<LearningQuizResponse>(
    `${BASE}/learning-path/${progressId}/quiz`,
    { choice_index: choiceIndex },
  );
  return data;
}

export async function requestLearningReview(
  progressId: number,
): Promise<{ ok: boolean; slack_sent: boolean }> {
  const { data } = await api.post(`${BASE}/learning-path/${progressId}/request-review`);
  return data as { ok: boolean; slack_sent: boolean };
}

export async function submitLearningReview(
  progressId: number,
  verdict: 'pass' | 'redo' | 'pass_with_comment',
  comment = '',
): Promise<LearningReviewResponse> {
  const { data } = await api.post<LearningReviewResponse>(
    `${BASE}/learning-path/${progressId}/review`,
    { verdict, comment },
  );
  return data;
}

// ─────────────────────────────────────────────────────────────
// P4 D16 — 공급망 그래프
// ─────────────────────────────────────────────────────────────

export interface SupplierGraphNode {
  supplier_id: string;
  name: string;
  tier: number;
  tier_depth: number;
  parent_supplier_id: string;
  relation_type: string;
  country: string;
  annual_volume_krw_mn: number;
  compliance_score: number;
  depth_from_origin: number;
}

export interface SupplierGraphResponse {
  origin: string;
  direction: 'down' | 'up';
  max_depth: number;
  nodes: SupplierGraphNode[];
  cycles_detected: string[][];
}

// P5 §1 — affected-suppliers 응답에 match_method 추가됨
export interface AffectedSupplierItem {
  supplier_id: string;
  name: string;
  tier: number;
  country: string;
  contact_email: string;
  annual_volume_krw_mn: number;
  compliance_score: number;
  match_reasons: string[];
  tier_depth: number;
  cascade_path: string[];
  depth_from_match: number;
  relation_type: string;
  match_method: 'primary' | 'cascade' | string;
}

export async function fetchSupplierGraph(
  supplierId: string,
  direction: 'down' | 'up' = 'down',
  maxDepth = 3,
): Promise<SupplierGraphResponse> {
  const { data } = await api.get<SupplierGraphResponse>(
    `${BASE}/suppliers/${encodeURIComponent(supplierId)}/graph`,
    { params: { direction, max_depth: maxDepth } },
  );
  return data;
}

// ─────────────────────────────────────────────────────────────
// P4 D17 — What-if 정밀화 (baseline + 회계)
// ─────────────────────────────────────────────────────────────

export interface WhatIfBaselineResponse {
  revenue_krw_mn: number;
  cogs_krw_mn: number;
  labor_share: number;
  emissions: { scope_1?: number; scope_2?: number; scope_3?: number | null; source?: string };
  data_source: 'erp' | 'dart' | 'industry_avg' | 'hardcoded' | 'none' | string;
  confidence: number;
  as_of: string;
  corp_code: string;
}

export interface PnlImpactItem {
  line: string;
  delta_krw_mn: number;
  direction: 'increase' | 'decrease' | 'neutral' | string;
  explain: string;
  scenario_type: string;
  confidence: number;
}

export interface WhatIfAccountingResponse {
  items: PnlImpactItem[];
}

export async function fetchWhatIfBaseline(
  corpCode?: string,
): Promise<WhatIfBaselineResponse> {
  const { data } = await api.get<WhatIfBaselineResponse>(
    `${BASE}/whatif/baseline`,
    corpCode ? { params: { corp_code: corpCode } } : undefined,
  );
  return data;
}

export async function fetchWhatIfAccounting(
  whatifResult: Record<string, unknown>,
): Promise<WhatIfAccountingResponse> {
  const { data } = await api.post<WhatIfAccountingResponse>(
    `${BASE}/whatif/simulate/accounting`,
    { whatif_result: whatifResult },
  );
  return data;
}

// ─────────────────────────────────────────────────────────────
// P5 §7 — 자체 결재 워크플로
// ─────────────────────────────────────────────────────────────

export interface ApprovalStepInputApi {
  approver_id: string;
  role_label?: string;
}

export interface ApprovalChainCreatePayload {
  change_id: number;
  name: string;
  steps: ApprovalStepInputApi[];
}

export interface ApprovalStepItemApi {
  id: number;
  chain_id: number;
  step_order: number;
  approver_id: string;
  role_label: string;
  decision: 'pending' | 'approved' | 'rejected' | 'delegated' | string;
  comment: string;
  decided_at: string;
}

export interface ApprovalChainDetail {
  id: number;
  change_id: number;
  name: string;
  requested_by: string;
  status: 'pending' | 'approved' | 'rejected' | string;
  current_step: number;
  created_at: string;
  completed_at: string;
  steps: ApprovalStepItemApi[];
}

export interface ApprovalMyPendingResponse {
  items: Record<string, unknown>[];
  total: number;
}

export async function startApprovalChain(
  payload: ApprovalChainCreatePayload,
): Promise<{ ok: boolean; chain_id: number; error?: string }> {
  const { data } = await api.post(`${BASE}/approvals`, payload);
  return data as { ok: boolean; chain_id: number; error?: string };
}

export async function fetchMyApprovals(): Promise<ApprovalMyPendingResponse> {
  const { data } = await api.get<ApprovalMyPendingResponse>(`${BASE}/approvals/my`);
  return data;
}

export async function fetchApprovalChain(chainId: number): Promise<ApprovalChainDetail> {
  const { data } = await api.get<ApprovalChainDetail>(`${BASE}/approvals/${chainId}`);
  return data;
}

export async function decideApprovalStep(
  stepId: number,
  decision: 'approved' | 'rejected' | 'delegated',
  comment = '',
): Promise<{
  ok: boolean;
  chain_id: number;
  step_order: number;
  new_chain_status: string;
  next_step_order: number;
  error?: string;
}> {
  const { data } = await api.post(
    `${BASE}/approvals/steps/${stepId}/decide`,
    { decision, comment },
  );
  return data as {
    ok: boolean;
    chain_id: number;
    step_order: number;
    new_chain_status: string;
    next_step_order: number;
    error?: string;
  };
}

// ─────────────────────────────────────────────────────────────
// D6 — Impact Network 실 데이터 그래프
// ─────────────────────────────────────────────────────────────

export interface ImpactNetworkNode {
  id: string;
  type: 'regulation' | 'plant';
  label: string;
  meta: { scope?: string; description?: string; plant_count?: number };
}

export interface ImpactNetworkEdge {
  source: string;
  target: string;
}

export interface ImpactNetworkResponse {
  nodes: ImpactNetworkNode[];
  edges: ImpactNetworkEdge[];
  stats: { regulation_count: number; plant_count: number; edge_count: number };
}

export async function fetchImpactNetworkGraph(): Promise<ImpactNetworkResponse> {
  const { data } = await api.get(`${BASE}/impact-network`);
  return data as ImpactNetworkResponse;
}

// ─────────────────────────────────────────────────────────────
// D7 — Docs 라이브러리 (DB-backed)
// ─────────────────────────────────────────────────────────────

export interface ComplianceDoc {
  id: number;
  title: string;
  summary: string;
  file_url: string;
  regulation_ref: string;
  doc_type: string;
  version: string;
  source_authority: string;
  uploaded_by: string;
  uploaded_at: string;
}

export async function fetchComplianceDocs(
  params: { limit?: number; offset?: number; doc_type?: string } = {},
): Promise<{ docs: ComplianceDoc[]; total: number }> {
  const { data } = await api.get(`${BASE}/docs`, { params });
  return data as { docs: ComplianceDoc[]; total: number };
}

export async function createComplianceDoc(
  payload: Partial<ComplianceDoc>,
): Promise<{ id: number; ok: boolean }> {
  const { data } = await api.post(`${BASE}/docs`, payload);
  return data as { id: number; ok: boolean };
}

export async function deleteComplianceDoc(
  docId: number,
): Promise<{ id: number; deleted: boolean }> {
  const { data } = await api.delete(`${BASE}/docs/${docId}`);
  return data as { id: number; deleted: boolean };
}

// ─────────────────────────────────────────────────────────────
// D5 — Kanban / Collab Tickets
// ─────────────────────────────────────────────────────────────

export type TicketStatus = 'created' | 'acknowledged' | 'in_progress' | 'resolved';

export interface CollabTicket {
  id: number;
  change_id: number;
  title: string;
  departments: string[];
  owners: string[];
  status: TicketStatus;
  external_id: string;
  external_url: string;
  created_at: string;
  resolved_at: string;
  assignee: string;
  deadline: string;
  progress_pct: number;
}

export async function fetchCollabTickets(
  params: { status?: TicketStatus; department?: string; limit?: number } = {},
): Promise<{ tickets: CollabTicket[]; total: number }> {
  const { data } = await api.get<{ items: CollabTicket[]; total: number }>(
    `${BASE}/tickets`, { params },
  );
  return { tickets: data.items, total: data.total };
}

export async function transitionTicket(
  ticketId: number,
  status: TicketStatus,
): Promise<{ id: number; status: TicketStatus }> {
  const { data } = await api.post<{ ok: boolean; ticket_id: number; new_status: string }>(
    `${BASE}/tickets/${ticketId}/transition`,
    { new_status: status },
  );
  return { id: data.ticket_id, status: data.new_status as TicketStatus };
}

export async function patchTicket(
  ticketId: number,
  patch: { assignee?: string; deadline?: string; progress_pct?: number },
): Promise<{ id: number; patched: boolean }> {
  const { data } = await api.patch(`${BASE}/tickets/${ticketId}`, patch);
  return data as { id: number; patched: boolean };
}

// ─────────────────────────────────────────────────────────────
// D4 — SOP diff
// ─────────────────────────────────────────────────────────────

export interface SopDocument {
  id: number;
  title: string;
  version: string;
  plant_id: string;
  dept: string;
  body_excerpt: string;
  related_regulation_ids: string[];
  sop_type: string;
  status: string;
  uploaded_at: string;
}

export interface SopDiffBlock {
  op: 'equal' | 'replace' | 'delete' | 'insert';
  old: string;
  new: string;
}

export interface AffectedSopItem {
  sop_id: number;
  sop_title: string;
  version: string;
  dept: string;
  match_method: string;
  regulation_diff: SopDiffBlock[];
  sop_excerpt: string;
  sop_diff: SopDiffBlock[];
}

export interface SopDiffResponse {
  change_id: number;
  regulation_type: string;
  affected_sops: AffectedSopItem[];
  match_count: number;
}

export async function fetchSops(limit = 100): Promise<{ sops: SopDocument[]; total: number }> {
  const { data } = await api.get(`${BASE}/sop`, { params: { limit } });
  return data as { sops: SopDocument[]; total: number };
}

export async function createSop(payload: Partial<SopDocument>): Promise<{ id: number; ok: boolean }> {
  const { data } = await api.post(`${BASE}/sop`, payload);
  return data as { id: number; ok: boolean };
}

export async function fetchSopDiff(changeId: number): Promise<SopDiffResponse> {
  const { data } = await api.post<SopDiffResponse>(
    `${BASE}/changes/${changeId}/sop-diff`,
  );
  return data;
}

// ─────────────────────────────────────────────────────────────
// F12 — Crawl audit history (운영 가시성)
// ─────────────────────────────────────────────────────────────

export interface CrawlRunAuditRow {
  run_id: number;
  crawler_name: string;
  started_at: string;
  elapsed_ms: number;
  ok: number;
  updates_found: number;
  errors: string;
  trigger_source: string;
  http_status: number | null;
  http_etag: string;
  http_last_modified: string;
  user_id: string;
}

export async function fetchCrawlHistory(
  params: { limit?: number; crawler_name?: string; only_failed?: boolean; since_iso?: string } = {},
): Promise<{ runs: CrawlRunAuditRow[]; total: number }> {
  const { data } = await api.get(`${BASE}/crawl/history`, { params });
  return data as { runs: CrawlRunAuditRow[]; total: number };
}

export interface CrawlHistoryStats {
  window: string;
  total_runs: number;
  failed_runs: number;
  per_crawler: { crawler_name: string; cnt: number; ok_cnt: number }[];
  sla?: Partial<Record<CrawlerName, CrawlSlaItem>>;
  queried_at: string;
}

export async function fetchCrawlHistoryStats(): Promise<CrawlHistoryStats> {
  const { data } = await api.get<CrawlHistoryStats>(`${BASE}/crawl/history/stats`);
  return data;
}

// ─────────────────────────────────────────────────────────────
// v4.2 — D 컴플라이언스 실시간 알람
// ─────────────────────────────────────────────────────────────

export type ComplianceAlarmSeverity = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
export type ComplianceAlarmSource =
  | 'law_change'
  | 'dday'
  | 'impact_score'
  | 'unresolved'
  | 'trend';

export interface ComplianceAlarm {
  id: string;
  severity: ComplianceAlarmSeverity;
  title: string;
  detail: string;
  module: 'D';
  source: ComplianceAlarmSource;
  regulation_id?: string;
  effective_date?: string;
  timestamp: string;
  acknowledged: boolean;
}

export interface ComplianceAlarmsResponse {
  items: ComplianceAlarm[];
  total: number;
}

export interface ComplianceAlarmAckResponse {
  alarm_id: string;
  acknowledged_at: string;
  actor: string;
}

export async function fetchComplianceAlarms(
  sinceTs = 0,
  limit = 50,
): Promise<ComplianceAlarmsResponse> {
  const { data } = await api.get<ComplianceAlarmsResponse>(`${BASE}/alarms/recent`, {
    params: { since_ts: sinceTs, limit },
  });
  return data;
}

export async function ackComplianceAlarm(alarmId: string): Promise<ComplianceAlarmAckResponse> {
  const { data } = await api.post<ComplianceAlarmAckResponse>(
    `${BASE}/alarms/${encodeURIComponent(alarmId)}/ack`,
  );
  return data;
}
