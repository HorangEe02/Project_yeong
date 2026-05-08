"""Day 6 Phase 1 — 설비/공정 AI Pydantic 스키마.

Module F (Equipment & Process AI) 의 12 엔드포인트 요청/응답 모델.
features/equipment/* 19 모듈을 React UI 로 노출하기 위한 wire 포맷.
"""

from __future__ import annotations

from typing import Literal, Optional, Any

from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════
# 1. 공통 — Severity / Risk Level
# ═══════════════════════════════════════════════════════════

Severity = Literal["critical", "warning", "info"]
RiskLevel = Literal["critical", "warning", "normal"]
ProcessStatus = Literal["good", "warning", "critical"]


# ═══════════════════════════════════════════════════════════
# 2. Dashboard Overview — GET /equipment/dashboard/overview
# ═══════════════════════════════════════════════════════════


class ProcessHealthCard(BaseModel):
    """5공정 건강 카드 (CCH/OBC/범퍼빔/도어/볼시트)."""

    process_id: str
    process_name: str
    status: ProcessStatus
    current_cpk: float
    cpk_trend: str = "stable"
    violation_count: int = 0
    violated_rules: list[int] = Field(default_factory=list)
    risk_level: RiskLevel = "normal"
    anomaly_rate: float = 0.0


class EquipmentTypeCard(BaseModel):
    """7장비 카드 (프레스/용접기/로봇/사출기/CNC/레이저/공통설비)."""

    type: str
    icon: str
    codes: int
    key_metric: str
    color: str


class DashboardMetrics(BaseModel):
    """대시보드 5종 핵심 메트릭."""

    error_codes_total: int = 0
    error_codes_critical: int = 0
    molds_total: int = 0
    molds_warning: int = 0
    molds_critical: int = 0
    spc_processes: int = 0
    inspections_templates: int = 0
    inspections_recent: int = 0


class MLAlert(BaseModel):
    """ML 경고 카드."""

    level: str
    source: str
    message: str


class OverviewResponse(BaseModel):
    """GET /equipment/dashboard/overview 응답."""

    processes: list[ProcessHealthCard]
    equipment_types: list[EquipmentTypeCard]
    metrics: DashboardMetrics
    ml_alerts: list[MLAlert] = Field(default_factory=list)


# ═══════════════════════════════════════════════════════════
# 3. SPC Chart — GET /equipment/spc/{process_id}
# ═══════════════════════════════════════════════════════════


class NelsonViolationItem(BaseModel):
    """Nelson 8 Rules 위반 항목."""

    rule_number: int
    rule_name: str
    description: str
    severity: Severity
    points: list[int] = Field(default_factory=list)
    recommended_action: str = ""
    chart_annotation: str = ""


class SPCData(BaseModel):
    """SPC 관리도 데이터 (Plotly 시각화용)."""

    process_id: str
    process_name: str
    timestamps: list[int]
    values: list[float]
    mean: float
    sigma: float
    ucl: float
    lcl: float
    sigma_1_upper: float
    sigma_1_lower: float
    sigma_2_upper: float
    sigma_2_lower: float
    usl: Optional[float] = None
    lsl: Optional[float] = None


class SPCResponse(BaseModel):
    """GET /equipment/spc/{process_id} 응답."""

    data: SPCData
    violations: list[NelsonViolationItem]
    out_of_control: bool = False
    violation_count: int = 0


# ═══════════════════════════════════════════════════════════
# 4. SPC Recent Violations — GET /equipment/spc/violations/recent
# ═══════════════════════════════════════════════════════════


class RecentViolation(BaseModel):
    """최근 SPC 위반 — RTDB push 대상."""

    id: str
    process_id: str
    process_name: str
    rule_number: int
    severity: Severity
    message: str
    timestamp: int  # ms epoch


class ViolationsResponse(BaseModel):
    items: list[RecentViolation]
    total: int


# ═══════════════════════════════════════════════════════════
# 5. ML Error Search — POST /equipment/error/search
# ═══════════════════════════════════════════════════════════


class ErrorSearchRequest(BaseModel):
    query: str
    top_k: int = 5
    equipment_filter: Optional[str] = None


class ErrorSearchResult(BaseModel):
    code: str
    equipment_type: str
    category: str
    description: str
    cause: str
    action: str
    severity: str
    score: float
    rank: int


class CausalityInfo(BaseModel):
    causes: list[str] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)


class ManualExcerpt(BaseModel):
    content: str
    source: str = ""
    page: str = ""
    relevance: float = 0.0


class ErrorSearchResponse(BaseModel):
    results: list[ErrorSearchResult]
    causality: Optional[CausalityInfo] = None
    manual_excerpts: list[ManualExcerpt] = Field(default_factory=list)


# ═══════════════════════════════════════════════════════════
# 6. Error Categories — GET /equipment/error/categories
# ═══════════════════════════════════════════════════════════


class CategoryGroup(BaseModel):
    equipment_type: str
    symptoms: list[str]


class ErrorCategoriesResponse(BaseModel):
    groups: list[CategoryGroup]
    total_synonyms: int = 0


# ═══════════════════════════════════════════════════════════
# 7. Markov Chain — GET /equipment/markov/{error_code}
# ═══════════════════════════════════════════════════════════


class MarkovPrediction(BaseModel):
    code: str
    category: str
    equipment_type: str
    probability: float
    expected_delay_hours: float
    description: str
    recommended_action: str


class CascadeStep(BaseModel):
    code: str
    category: str
    probability: float
    expected_delay_hours: float


class CascadeChainItem(BaseModel):
    steps: list[CascadeStep]
    total_probability: float
    total_hours: float


class MarkovResponse(BaseModel):
    current_code: str
    current_category: str
    next_predictions: list[MarkovPrediction]
    cascade_chains: list[CascadeChainItem] = Field(default_factory=list)
    risk_level: RiskLevel = "normal"
    prevention_message: str = ""


# ═══════════════════════════════════════════════════════════
# 8. Mold list + XGBoost — GET /equipment/molds
# ═══════════════════════════════════════════════════════════


class MoldItem(BaseModel):
    mold_id: str
    mold_name: str
    mold_type: str = ""
    part_name: str = ""
    current_shots: int = 0
    max_shots: int = 0
    life_percent: float = 0.0
    remaining_shots: int = 0
    status: str = "active"

    # XGBoost 예측 (선택 — 모델 파일 부재 시 None)
    predicted_remaining_life: Optional[int] = None
    predicted_replacement_date: Optional[str] = None
    risk_level: Optional[RiskLevel] = None
    confidence_interval: Optional[list[int]] = None


class MoldsResponse(BaseModel):
    items: list[MoldItem]
    total: int
    critical: int = 0
    warning: int = 0
    active: int = 0


# ═══════════════════════════════════════════════════════════
# 9. MTBF — GET /equipment/mtbf
# ═══════════════════════════════════════════════════════════


class MTBFItem(BaseModel):
    machine_id: str
    machine_name: str
    total_repairs: int
    mtbf_days: float
    mtbf_std_days: float = 0.0
    last_repair_date: str = ""
    next_predicted_date: str = ""
    days_until_next: int = 0
    risk_level: str = "정상"
    avg_repair_hours: float = 0.0
    avg_repair_cost: float = 0.0
    seasonal_pattern: dict[str, float] = Field(default_factory=dict)


class MTBFTopCost(BaseModel):
    machine_name: str
    total_cost: float


class MTBFResponse(BaseModel):
    items: list[MTBFItem]
    top5_cost: list[MTBFTopCost] = Field(default_factory=list)
    seasonal_message: str = ""
    machines_attention: int = 0


# ═══════════════════════════════════════════════════════════
# 10. ML Engines Status — GET /equipment/ml-engines/status
# ═══════════════════════════════════════════════════════════


EngineStatus = Literal["online", "offline", "warning"]


class MLEngineStatus(BaseModel):
    """7종 ML 모델 개별 상태."""

    id: str
    name_en: str
    name_ko: str
    library: str
    status: EngineStatus
    accuracy: Optional[float] = None
    last_trained: Optional[str] = None
    description: str = ""


class MLEnginesStatusResponse(BaseModel):
    engines: list[MLEngineStatus]
    online_count: int = 0
    total: int = 7


# ═══════════════════════════════════════════════════════════
# 11. Manual RAG — POST /equipment/manual/search
# ═══════════════════════════════════════════════════════════


class ManualSearchRequest(BaseModel):
    query: str
    equipment_type: Optional[str] = None
    n_results: int = 5


class ManualSearchResponse(BaseModel):
    items: list[ManualExcerpt]
    total: int


# ═══════════════════════════════════════════════════════════
# 12. SPC CSV Upload — POST /equipment/spc/upload-csv
# ═══════════════════════════════════════════════════════════


class SPCUploadResponse(BaseModel):
    process_id: str
    n_samples: int
    mean: float
    std: float
    cpk: Optional[float] = None
    grade: str = ""
    violation_count: int = 0


# ═══════════════════════════════════════════════════════════
# 13. Inspection Checklist — GET /equipment/inspection/checklist/{type}
# ═══════════════════════════════════════════════════════════


class ChecklistItem(BaseModel):
    item: str
    standard: str = ""
    unit: str = ""


class ChecklistTemplate(BaseModel):
    id: int
    template_name: str
    equipment_type: str
    checklist_type: str
    items: list[ChecklistItem]


class InspectionChecklistResponse(BaseModel):
    templates: list[ChecklistTemplate]
    total: int
