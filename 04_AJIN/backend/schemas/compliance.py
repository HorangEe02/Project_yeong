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


class ChangeListResponse(BaseModel):
    total: int
    stats: dict[str, Any] = {}
    changes: list[ChangeItem]


class AcknowledgeResponse(BaseModel):
    ok: bool = True
    change_id: int


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


# ── D-2-1 / D-2-12 Crawler control ────────────────────────────


class CrawlRunResponse(BaseModel):
    name: str
    crawled_at: str = ""
    source: str = ""
    total_count: int = 0
    updates_found: int = 0
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
