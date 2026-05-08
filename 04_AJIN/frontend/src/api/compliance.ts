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
): Promise<ChangeListResponse> {
  const { data } = await api.get<ChangeListResponse>(`${BASE}/changes/recent`, {
    params: { limit, unack_only: unackOnly },
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
}

export interface CrawlRunAllResult {
  crawlers: Record<CrawlerName, CrawlRunResult>;
  total_changes: number;
}

export async function runCrawler(name: CrawlerName): Promise<CrawlRunResult> {
  const { data } = await api.post<CrawlRunResult>(`${BASE}/crawl/run/${name}`);
  return data;
}

export async function runAllCrawlers(): Promise<CrawlRunAllResult> {
  const { data } = await api.post<CrawlRunAllResult>(`${BASE}/crawl/run-all`);
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
