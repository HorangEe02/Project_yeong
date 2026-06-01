"""규정 준수 관련 Pydantic 스키마."""

from typing import Any
from pydantic import BaseModel


class ComplianceCheckRequest(BaseModel):
    query: str
    use_llm: bool = False
    model: str | None = None


class ComplianceCheckResponse(BaseModel):
    answer: str = ""
    relevant_standards: list[str] = []
    compliance_status: str = ""
    source: str = "rules"
    disclaimer: str = ""


class ScenarioItem(BaseModel):
    scenario_id: str = ""
    title: str = ""
    severity: str = ""
    category: str = ""
    description: str = ""


class FacilityItem(BaseModel):
    plant_id: str = ""
    name: str = ""
    location: str = ""
    address: str = ""
    certifications: list[str] = []
    processes: list[str] = []
    kind: str = "plant"  # plant | subsidiary_domestic | subsidiary_overseas
    country: str = ""
    lat: float | None = None
    lng: float | None = None


# ── D-2-2 RiskScorer ──────────────────────────────────────────


class RiskScoreItem(BaseModel):
    scenario_id: str
    title: str
    total_score: float
    grade: str
    financial_impact: float
    likelihood: float
    urgency: float
    deadline: str | None = None
    days_remaining: int | None = None
    affected_plants: list[str] = []
    mitigation_status: str = "미착수"


class RiskScoreResponse(BaseModel):
    total: int
    summary: dict[str, Any] = {}
    scores: list[RiskScoreItem]


# ── D-2-5 TariffSimulator ─────────────────────────────────────


class TariffSimulateRequest(BaseModel):
    tariff_rate: float = 25.0  # %
    exchange_rate: float = 1380.0  # KRW/USD


class TariffSimulateItem(BaseModel):
    product: str
    tariff_rate: float
    unit_tariff: float
    annual_tariff: float
    annual_tariff_krw: float
    cost_increase_pct: float


class TariffSimulateResponse(BaseModel):
    tariff_rate: float
    exchange_rate: float
    total_annual_usd: float
    total_annual_krw: float
    total_annual_krw_billion: float
    avg_cost_increase: float
    results: list[TariffSimulateItem]


# ── D-2-4 / D-2-7 Plotly Figure (JSON) ────────────────────────


class PlotlyResponse(BaseModel):
    figure: dict[str, Any]  # plotly.io.to_json -> dict


# ── D-2-6 ChangeDetector ──────────────────────────────────────


class ChangeItem(BaseModel):
    id: int = 0
    regulation_type: str = ""
    change_type: str = ""  # added | modified | removed
    item_id: str = ""
    title: str = ""
    summary: str = ""
    detected_at: str = ""
    acknowledged: bool = False
    # v4.x — Issue 3 보고서 enrichment (변경 이력 카드 + 사내 영향 카드)
    before_text: str = ""
    after_text: str = ""
    diff_html: str = ""
    impact_json: str = ""


class ChangeListResponse(BaseModel):
    total: int
    stats: dict[str, Any] = {}
    changes: list[ChangeItem]


class AcknowledgeResponse(BaseModel):
    ok: bool = True
    change_id: int


# ── MVP — 변경 피드·워크플로우·KPI (Stage 7 + 8c) ──────────────


class ChangeFeedItem(BaseModel):
    """변경 피드 카드 1건 — ChangeItem 의 enrich 버전."""
    id: int = 0
    regulation_type: str = ""
    change_type: str = ""
    item_id: str = ""
    item_title: str = ""
    summary_ko: str = ""                          # Stage 3 LLM 1줄
    grade: str = "MEDIUM"                          # CRITICAL / HIGH / MEDIUM / LOW
    severity: str = "info"                         # change_detector 원본
    status: str = "pending"                        # pending/reviewing/planning/announced/done/filtered
    affected_departments: list[str] = []
    affected_plants: list[str] = []
    assigned_to: str = ""
    detected_at: str = ""
    acknowledged: bool = False
    audit_trail: list[dict[str, Any]] = []         # workflow 이력
    old_value: str = ""
    new_value: str = ""
    # P1 D1 — 법무 5분류 + 벌칙
    legal_class: list[str] = []                    # criminal/administrative/civil/contract/standardization
    penalty_extract: str = ""                      # 한 줄 (예: '5년 이하 징역, 1억 이하 벌금')
    penalty_severity_krw_mn: int = 0               # 백만원 단위, 정렬·집계용


class ChangeFeedResponse(BaseModel):
    total: int = 0
    items: list[ChangeFeedItem] = []
    has_more: bool = False


class ChangeTransitionRequest(BaseModel):
    new_status: str  # pending/reviewing/planning/announced/done/filtered
    review_note: str = ""
    override_reason: str = ""


class ChangeTransitionResponse(BaseModel):
    ok: bool = True
    change_id: int
    new_status: str = ""
    review_required: bool = False
    override_used: bool = False


class ChangeKpiResponse(BaseModel):
    """임원용 KPI 1페이지 — `/changes/kpi` 응답."""
    month_critical: int = 0
    month_high: int = 0
    month_medium: int = 0
    month_low: int = 0
    open_count: int = 0                            # 미해결 누적 (status not in done/filtered)
    avg_hours_to_done: float = 0.0                 # 평균 처리 시간 (시간 단위)
    today_new: int = 0
    trend: list[dict[str, Any]] = []               # [{day, CRITICAL, HIGH, MEDIUM, LOW}]


# ── P2 D5 — Feedback Loop ────────────────────────


class ChangeCorrectionRequest(BaseModel):
    """사용자 수정 이벤트 — `POST /changes/{id}/correct`."""
    field: str                               # affected_departments / legal_class / grade / summary_ko / ...
    new_value: Any                           # str 또는 list[str] (필드별)
    note: str = ""


class ChangeCorrectionResponse(BaseModel):
    ok: bool = True
    correction_id: int = 0
    error: str = ""


class CorrectionStatsResponse(BaseModel):
    total: int = 0
    by_field: dict[str, int] = {}
    by_role: dict[str, int] = {}
    frequent_dept_changes: list[Any] = []     # [(dept, count), ...]
    accuracy_signal: dict[str, float] = {}
    window_days: int = 30


# ── P2 D8 — 외부 판례 RAG ───────────────────────


class CaseLawItem(BaseModel):
    case_id: str
    court: str = ""
    date: str = ""
    title: str = ""
    summary_excerpt: str = ""
    similarity: float = 0.0
    full_url: str = ""


class SimilarCasesResponse(BaseModel):
    items: list[CaseLawItem] = []
    available: bool = True                    # ChromaDB / API 사용 가능 여부
    note: str = ""                            # 미가용 시 안내 텍스트


class CaseLawIndexResponse(BaseModel):
    by_keyword: dict[str, int] = {}            # 키워드별 적재 건수
    total: int = 0


# ── P2 D7 — 계약 영향 분석 ────────────────────────


class ContractMeta(BaseModel):
    contract_id: str
    counterparty: str = ""
    type: str = ""
    effective_date: str = ""
    expiry_date: str = ""
    annual_value_krw_mn: int = 0
    status: str = "active"


class ContractListResponse(BaseModel):
    items: list[ContractMeta] = []
    total: int = 0


class AffectedContractItem(BaseModel):
    contract_id: str
    counterparty: str = ""
    type: str = ""
    clause_no: str = ""
    title: str = ""
    body_excerpt: str = ""
    similarity: float | None = None
    match_keywords: list[str] = []
    source: str = ""                          # 'vector' | 'keyword'


class AffectedContractsResponse(BaseModel):
    items: list[AffectedContractItem] = []


class ContractIngestResponse(BaseModel):
    ok: bool = True
    contract_id: str
    clause_count: int = 0
    error: str = ""


# ── P2 D6 — 공급망 ────────────────────────────────


class SupplierMeta(BaseModel):
    supplier_id: str
    name: str = ""
    tier: int = 1
    country: str = "KR"
    contact_email: str = ""
    contact_phone: str = ""
    annual_volume_krw_mn: int = 0
    compliance_score: int = 0
    last_self_assessed_at: str = ""


class SupplierListResponse(BaseModel):
    items: list[SupplierMeta] = []
    total: int = 0


class SupplierComponentItem(BaseModel):
    component_code: str = ""
    hs_code: str = ""
    unit_price_krw: int = 0
    qty_per_year: int = 0


class SupplierDetailResponse(BaseModel):
    meta: SupplierMeta
    components: list[SupplierComponentItem] = []


class SupplierImportRequest(BaseModel):
    csv_text: str
    target: str = "suppliers"  # suppliers | components


class SupplierImportResponse(BaseModel):
    imported: int = 0
    skipped: int = 0
    errors: list[str] = []


class AffectedSupplierItem(BaseModel):
    supplier_id: str
    name: str = ""
    tier: int = 1
    country: str = "KR"
    contact_email: str = ""
    annual_volume_krw_mn: int = 0
    compliance_score: int = 0
    match_reasons: list[str] = []
    # P4 D16 — 다중 tier 영향 (선택, default=1차 직접 매치)
    tier_depth: int = 1
    cascade_path: list[str] = []
    depth_from_match: int = 0
    # P4.1 §11 — 협력 유형 (direct | sub_assembly | raw_material | logistics)
    relation_type: str = "direct"
    # P5 §1 — primary (1차 직접 매치) vs cascade (자식, keyword/HS/country 통과)
    match_method: str = "primary"


class AffectedSuppliersResponse(BaseModel):
    items: list[AffectedSupplierItem] = []


class SendAssessmentRequest(BaseModel):
    change_id: int


class SendAssessmentResponse(BaseModel):
    ok: bool = True
    assessment_id: int = 0
    status: str = ""
    sent_via_smtp: bool = False
    error: str = ""


class CostSimulationRequest(BaseModel):
    scenario_rate_pct: float = 25.0


class CostSimulationSupplierBreakdown(BaseModel):
    supplier_id: str
    name: str = ""
    country: str = ""
    baseline_krw_mn: int = 0
    additional_tariff_krw_mn: int = 0


class CostSimulationResponse(BaseModel):
    baseline_cost_krw_mn: int = 0
    new_cost_krw_mn: int = 0
    delta_krw_mn: int = 0
    delta_pct: float = 0.0
    by_supplier: list[CostSimulationSupplierBreakdown] = []
    applicable_hs: list[str] = []
    scenario_rate_pct: float = 0.0
    chemical_substitution: dict[str, Any] = {}


class AlternativeSupplierItem(BaseModel):
    supplier_id: str
    name: str = ""
    tier: int = 1
    country: str = ""
    compliance_score: int = 0
    annual_volume_krw_mn: int = 0
    avg_unit_price_krw: int = 0
    score_total: float = 0.0
    score_breakdown: dict[str, float] = {}


class AlternativesResponse(BaseModel):
    items: list[AlternativeSupplierItem] = []


# ── P3 D13 — 확장 트렌드 KPI ──────────────────────


class DeptHandlingTime(BaseModel):
    department: str
    avg_hours: float = 0.0
    count: int = 0


class ExtendedTrendResponse(BaseModel):
    window_days: int = 180
    monthly_grade_trend: list[dict[str, Any]] = []
    by_dept_handling_hours: list[DeptHandlingTime] = []
    by_legal_class: dict[str, int] = {}
    total: int = 0


# ── P3 D12 — Feedback Loop 자동화 ─────────────────


class FeedbackLoopApplyRequest(BaseModel):
    window_days: int = 30
    min_occurrences: int = 5
    dry_run: bool = True


class FeedbackLoopApplyResponse(BaseModel):
    dry_run: bool = True
    window_days: int = 30
    min_occurrences: int = 5
    added_dept_mappings: list[dict[str, Any]] = []
    fewshot_added: int = 0
    audit_log_path: str = ""


# ── P3 D9 — 협업 티켓 ─────────────────────────────


class CollabTicketOwner(BaseModel):
    employee_id: str = ""
    name: str = ""
    email: str = ""
    position: str = ""


class CreateTicketResponse(BaseModel):
    ok: bool = True
    ticket_id: int = 0
    departments: list[str] = []
    owners: list[CollabTicketOwner] = []
    slack_sent: bool = False
    external_url: str = ""
    error: str = ""


class CollabTicketItem(BaseModel):
    id: int
    change_id: int
    title: str
    departments: list[str] = []
    owners: list[str] = []                       # employee_id list
    status: str = "created"
    external_id: str = ""
    external_url: str = ""
    created_at: str = ""
    resolved_at: str = ""
    # D5 — Kanban 확장
    assignee: str = ""
    deadline: str = ""
    progress_pct: int = 0


class CollabTicketListResponse(BaseModel):
    items: list[CollabTicketItem] = []
    total: int = 0


class TicketTransitionRequest(BaseModel):
    new_status: str  # created/acknowledged/in_progress/resolved


class TicketTransitionResponse(BaseModel):
    ok: bool = True
    ticket_id: int
    new_status: str = ""


# ── P3 D10 — What-if 시뮬레이션 ───────────────────


class WhatIfRequest(BaseModel):
    scenario_type: str  # tariff/fx/chemical/labor/carbon/natural_language
    params: dict[str, Any] = {}
    change_id: int | None = None


class WhatIfResponse(BaseModel):
    scenario_type: str = ""
    params: dict[str, Any] = {}
    baseline_kpi: dict[str, Any] = {}
    new_kpi: dict[str, Any] = {}
    delta: dict[str, Any] = {}
    delta_pct: dict[str, Any] = {}
    by_dimension: list[dict[str, Any]] = []
    note: str = ""
    # P4 D17 — 정확도 metric (data_source / confidence / as_of / corp_code)
    meta: dict[str, Any] = {}


# ── P3 D11 — 산업 트렌드 ─────────────────────────


class IndustryFetchResponse(BaseModel):
    fetched: int = 0
    indexed: int = 0
    note: str = ""


class IndustryCorpFilings(BaseModel):
    corp_code: str
    corp_name: str
    count: int = 0
    sample_reports: list[dict[str, Any]] = []


class IndustryContextResponse(BaseModel):
    change_keywords: list[str] = []
    matching_filings_count: int = 0
    by_corp: list[IndustryCorpFilings] = []
    industry_average_filings: float = 0.0
    verdict: str = "no_data"  # industry_wide | company_specific | no_data
    available: bool = False


# ── P4 D14 — 권한 위임 룰 엔진 ──────────────────────────────


class DelegationConditions(BaseModel):
    grade_in: list[str] | None = None
    departments_subset_of: list[str] | None = None
    legal_class_in: list[str] | None = None
    penalty_max_krw_mn: int | None = None
    keywords_any: list[str] | None = None


class DelegationActions(BaseModel):
    assign_to: str | None = None
    transition_to: str | None = None
    notify_slack: list[str] | None = None
    auto_create_ticket: bool = False


class DelegationRuleItem(BaseModel):
    id: int
    name: str
    owner: str = ""
    enabled: bool = True
    conditions: dict[str, Any] = {}
    actions: dict[str, Any] = {}
    priority: int = 100
    created_at: str = ""
    updated_at: str = ""


class DelegationRuleListResponse(BaseModel):
    items: list[DelegationRuleItem] = []
    total: int = 0


class DelegationRuleCreateRequest(BaseModel):
    name: str
    enabled: bool = True
    conditions: dict[str, Any] = {}
    actions: dict[str, Any] = {}
    priority: int = 100


class DelegationRuleUpdateRequest(BaseModel):
    name: str | None = None
    enabled: bool | None = None
    conditions: dict[str, Any] | None = None
    actions: dict[str, Any] | None = None
    priority: int | None = None


class DelegationRuleMutationResponse(BaseModel):
    ok: bool = True
    rule_id: int = 0


class DelegationDryRunMatch(BaseModel):
    change_id: int
    item_title: str = ""
    rule_id: int
    rule_name: str = ""
    applied_actions: dict[str, Any] = {}


class DelegationDryRunResponse(BaseModel):
    scanned: int = 0
    matched: int = 0
    by_rule: dict[str, int] = {}
    matches: list[DelegationDryRunMatch] = []


# ── P4 D15 — 신입 학습경로 ───────────────────────────


class LearningPathCreateRequest(BaseModel):
    name: str
    assignee_employee_id: str
    week_split: list[list[int]]                     # [[10,11], [20,21,22], [30]]
    min_quiz_score: int = 60


class LearningPathCreateResponse(BaseModel):
    ok: bool = True
    path_id: int = 0


class LearningProgressItem(BaseModel):
    id: int
    path_id: int
    week: int
    change_id: int
    read_at: str = ""
    quiz_score: int = -1
    quiz_attempts: int = 0
    mentor_review: str = "pending"
    mentor_comment: str = ""
    updated_at: str = ""


class LearningPathDetail(BaseModel):
    id: int
    name: str
    owner_employee_id: str
    week_count: int = 0
    curriculum: list[dict[str, Any]] = []
    progress: list[LearningProgressItem] = []
    status: str = "active"
    created_at: str = ""


class LearningMyProgressResponse(BaseModel):
    paths: list[LearningPathDetail] = []


class LearningMentorQueueItem(BaseModel):
    id: int
    path_id: int
    path_name: str = ""
    assignee_employee_id: str = ""
    week: int
    change_id: int
    quiz_score: int = -1
    quiz_attempts: int = 0
    mentor_review: str = "pending"
    updated_at: str = ""


class LearningMentorQueueResponse(BaseModel):
    items: list[LearningMentorQueueItem] = []
    total: int = 0


class LearningQuizPreviewResponse(BaseModel):
    ok: bool = True
    progress_id: int = 0
    change_id: int = 0
    question: str = ""
    choices: list[str] = []
    generated_by: str = ""        # 'llm' | 'rule'
    error: str = ""


class LearningQuizRequest(BaseModel):
    choice_index: int


class LearningQuizResponse(BaseModel):
    ok: bool = True
    correct: bool = False
    score: int = 0
    answer_index: int = 0
    question: str = ""
    error: str = ""


class LearningReviewRequest(BaseModel):
    verdict: str                                    # pass | redo | pass_with_comment
    comment: str = ""


class LearningReviewResponse(BaseModel):
    ok: bool = True
    verdict: str = ""
    reviewer: str = ""
    error: str = ""


class LearningRequestReviewResponse(BaseModel):
    ok: bool = True
    slack_sent: bool = False
    error: str = ""


# ── P5 §7 — 자체 결재 워크플로 ────────────────────────


class ApprovalStepInput(BaseModel):
    approver_id: str
    role_label: str = ""


class ApprovalChainCreateRequest(BaseModel):
    change_id: int
    name: str
    steps: list[ApprovalStepInput]


class ApprovalChainCreateResponse(BaseModel):
    ok: bool = True
    chain_id: int = 0
    error: str = ""


class ApprovalStepItem(BaseModel):
    id: int
    chain_id: int
    step_order: int
    approver_id: str
    role_label: str = ""
    decision: str = "pending"
    comment: str = ""
    decided_at: str = ""


class ApprovalChainDetailResponse(BaseModel):
    id: int
    change_id: int = 0
    name: str
    requested_by: str = ""
    status: str = "pending"
    current_step: int = 1
    created_at: str = ""
    completed_at: str = ""
    steps: list[ApprovalStepItem] = []


class ApprovalMyPendingResponse(BaseModel):
    items: list[dict[str, Any]] = []
    total: int = 0


class ApprovalDecideRequest(BaseModel):
    decision: str  # approved | rejected | delegated
    comment: str = ""


class ApprovalDecideResponse(BaseModel):
    ok: bool = True
    chain_id: int = 0
    step_order: int = 0
    new_chain_status: str = ""
    next_step_order: int = 0
    error: str = ""


# ── P5 §10 — 2차 협력사 자동 발굴 ─────────────────────


class SupplierDiscoveryCandidate(BaseModel):
    corp_code: str
    corp_name: str
    filing_count: int = 0
    latest_rcept_dt: str = ""
    suggested_tier: int = 2


class SupplierDiscoveryListResponse(BaseModel):
    candidates: list[SupplierDiscoveryCandidate] = []
    total: int = 0
    note: str = ""


class SupplierPromoteRequest(BaseModel):
    name_override: str | None = None
    tier: int = 2
    relation_type: str = "sub_assembly"  # sub_assembly | raw_material | logistics | direct
    parent_supplier_id: str = ""


class SupplierPromoteResponse(BaseModel):
    ok: bool = True
    supplier_id: str = ""
    name: str = ""
    tier_depth: int = 0
    error: str = ""


# ── P5 §6 — Jira 양방향 sync ─────────────────────────


class JiraHealthResponse(BaseModel):
    enabled: bool = False
    myself_ok: bool = False
    default_project_ok: bool = False
    note: str = ""


class JiraWebhookEvent(BaseModel):
    """Jira webhook payload — Atlassian 표준 (jira:issue_updated 등)."""
    webhookEvent: str = ""
    issue: dict[str, Any] = {}
    changelog: dict[str, Any] | None = None
    user: dict[str, Any] | None = None


class JiraWebhookAckResponse(BaseModel):
    ok: bool = True
    synced_ticket_id: int = 0
    issue_key: str = ""
    new_status: str = ""
    note: str = ""


# ── P4 D17 — What-if 정밀화 ─────────────────────────


class WhatIfBaselineResponse(BaseModel):
    revenue_krw_mn: int = 0
    cogs_krw_mn: int = 0
    labor_share: float = 0.25
    emissions: dict[str, Any] = {}
    data_source: str = "hardcoded"
    confidence: float = 0.30
    as_of: str = ""
    corp_code: str = ""


class WhatIfAccountingRequest(BaseModel):
    whatif_result: dict[str, Any]


class PnlImpactItem(BaseModel):
    line: str
    delta_krw_mn: int = 0
    direction: str = "neutral"
    explain: str = ""
    scenario_type: str = ""
    confidence: float = 0.0


class WhatIfAccountingResponse(BaseModel):
    items: list[PnlImpactItem] = []


# ── P4 D16 — 2차/3차 협력사 그래프 ────────────────────


class SupplierGraphNode(BaseModel):
    supplier_id: str
    name: str = ""
    tier: int = 1
    tier_depth: int = 1
    parent_supplier_id: str = ""
    relation_type: str = "direct"
    country: str = ""
    annual_volume_krw_mn: int = 0
    compliance_score: int = 0
    depth_from_origin: int = 0


class SupplierGraphResponse(BaseModel):
    origin: str
    direction: str = "down"
    max_depth: int = 3
    nodes: list[SupplierGraphNode] = []
    cycles_detected: list[list[str]] = []


class SupplierCycleResponse(BaseModel):
    cycles: list[list[str]] = []


# ── D-2-8 Classifier ──────────────────────────────────────────


class ClassifyRequest(BaseModel):
    text: str


class ClassifyResponse(BaseModel):
    severity: str
    confidence: float
    all_scores: dict[str, float]
    related_departments: list[str]
    affected_plants: list[str]
    risk_score: int
    recommended_actions: list[str]
    response_deadline: str = ""
    disclaimer: str = ""


# ── D-2-1 / D-2-12 Crawler control ────────────────────────────


class CrawlRunResponse(BaseModel):
    name: str
    crawled_at: str = ""
    source: str = ""
    total_count: int = 0
    updates_found: int = 0
    # Phase 1: "live" — 외부 API 호출 성공, "curated" — 마스터 dict 폴백.
    # 프런트는 이 값을 보고 🟢 Live / 📋 Curated 배지를 노출 (Phase 3 작업).
    source_type: str = "curated"
    errors: list[str] = []


class CrawlRunAllResponse(BaseModel):
    crawlers: dict[str, CrawlRunResponse]
    total_changes: int = 0


# ─────────────────────────────────────────────────────────────
# v3.6 — Phase 2: 시나리오 통합 시뮬레이션 + 크롤링 결과 조회
# ─────────────────────────────────────────────────────────────


class ScenarioSimRiskScore(BaseModel):
    total: int = 0
    fin: int = 0  # 재무 영향 (0-40)
    pos: int = 0  # 가능성 (0-30)
    urg: int = 0  # 긴급도 (0-30)


class ScenarioSimImpact(BaseModel):
    plants: list[str] = []
    departments: list[str] = []
    cost_estimate_krw_bn: float = 0.0  # 원화 추정 (10억 단위)
    cost_breakdown: list[dict[str, Any]] = []  # 관세 시나리오 상세


class ScenarioSimEvidence(BaseModel):
    title: str
    url: str = ""


class ScenarioSimulateRequest(BaseModel):
    """선택 옵션 — 관세 시나리오 시뮬레이션 시 사용."""
    tariff_rate: float | None = None
    exchange_rate: float | None = None


class ScenarioSimulateResponse(BaseModel):
    scenario_id: str
    title: str
    category: str = "MEDIUM"  # CRITICAL/HIGH/MEDIUM/LOW
    deadline_days: int = 0
    description: str = ""
    risk_score: ScenarioSimRiskScore
    impact: ScenarioSimImpact
    recommended_actions: list[str] = []
    evidence_links: list[ScenarioSimEvidence] = []


class CrawlResultMeta(BaseModel):
    name: str  # iso, apqp, msds, ...
    filename: str  # iso_standards.json
    crawled_at: str = ""
    source: str = ""
    total_count: int = 0
    updates_found: int = 0
    errors: list[str] = []
    size_bytes: int = 0


class CrawlResultsListResponse(BaseModel):
    crawlers: list[CrawlResultMeta]
    total: int = 0


class CrawlResultItem(BaseModel):
    """개별 크롤링 항목 — 크롤러마다 필드가 달라 dict 로 유지."""
    title: str = ""
    url: str = ""
    summary: str = ""
    extra: dict[str, Any] = {}  # 원본 필드 보존


class CrawlResultDetailResponse(BaseModel):
    name: str
    filename: str
    crawled_at: str = ""
    source: str = ""
    total: int = 0
    items: list[CrawlResultItem] = []
    has_more: bool = False  # 페이지네이션


# ─────────────────────────────────────────────────────────────
# v3.6 Phase 3 — 시나리오 상세 (Item 1)
# 시뮬레이션이 아닌 "법규 원문·이력·체크리스트" 표시용
# ─────────────────────────────────────────────────────────────


class ScenarioRegulationMeta(BaseModel):
    name: str = ""  # 예: "산업안전보건기준에 관한 규칙"
    article: str = ""  # 예: "제99조 (프레스 등의 위험 방지)"
    authority: str = ""  # 예: "고용노동부"
    category: str = ""


class ScenarioChangeVersion(BaseModel):
    text: str = ""
    effective_date: str = ""
    version: str = ""


class ScenarioReference(BaseModel):
    title: str = ""
    url: str = ""


class ScenarioDetailResponse(BaseModel):
    scenario_id: str
    title: str
    description: str = ""
    regulation: ScenarioRegulationMeta
    change_before: ScenarioChangeVersion | None = None
    change_after: ScenarioChangeVersion | None = None
    severity: str = "medium"
    impact_areas: list[str] = []
    applicable_plants: list[str] = []
    affected_facility_ids: list[str] = []
    affected_process_types: list[str] = []
    deadline: str = ""
    days_remaining: int = 0
    required_actions: list[str] = []
    estimated_cost: str = ""
    references: list[ScenarioReference] = []  # reference_url 외 추가 자료
    raw: dict[str, Any] = {}  # 전체 원본 (디버그/extra)
