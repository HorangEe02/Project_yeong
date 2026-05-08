"""온보딩 채팅 + SOP/시나리오/액션/다운로드 관련 Pydantic 스키마."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


# ── 기존 채팅 ────────────────────────────────────────────────


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class OnboardingChatRequest(BaseModel):
    query: str
    department: str = "품질보증팀"
    model: str | None = None
    history: list[ChatMessage] = []
    file_context: str | None = None
    # Day 5 Phase 5 — Frontend ModelSelect 가 강제하는 (provider, model) 튜플.
    # Pydantic 은 tuple 직접 지원이 미흡하므로 list[str] 로 받아 라우터에서 tuple 변환.
    force_provider: list[str] | None = None


class OnboardingChatResponse(BaseModel):
    response: str
    model_used: str
    source: str = "llm"  # "llm" | "employee_db" | "glossary"


# ── SOP ──────────────────────────────────────────────────────


class SopSummary(BaseModel):
    """SOP 목록 항목 (사이드 패널용)."""

    sop_id: str
    title: str
    department: str
    category: str
    steps_count: int


class SopListResponse(BaseModel):
    items: list[SopSummary]
    total: int


class SopStep(BaseModel):
    step_number: int
    title: str
    description: str
    checklist: list[str] = Field(default_factory=list)
    caution: str = ""
    related_terms: list[str] = Field(default_factory=list)
    estimated_time: str = ""
    responsible: str = ""


class SopDetailResponse(BaseModel):
    sop_id: str
    title: str
    department: str
    category: str
    prerequisites: list[str] = Field(default_factory=list)
    safety_warnings: list[str] = Field(default_factory=list)
    related_sops: list[str] = Field(default_factory=list)
    steps: list[SopStep]


# ── 시나리오 (협업) ──────────────────────────────────────────


class ScenarioMatchRequest(BaseModel):
    query: str


class ScenarioCard(BaseModel):
    """매칭된 협업 시나리오 카드 (LLM 호출 0회 즉시 응답)."""

    scenario_id: str
    situation: str
    requesting_dept: str
    my_actions: list[str]
    hand_off_to: str
    hand_off_items: list[str]
    deadline_info: str
    related_sop_id: str = ""
    tips: list[str] = Field(default_factory=list)
    formatted_text: str  # 마크다운 응답 (메시지 풍선 표시용)


class ScenarioMatchResponse(BaseModel):
    matched: bool
    card: Optional[ScenarioCard] = None


# ── 업무 액션 ────────────────────────────────────────────────


class ActionMatchRequest(BaseModel):
    query: str


class ActionResultPayload(BaseModel):
    """work_actions.execute_action() 결과."""

    action_type: str
    success: bool
    display_text: str
    bridge_target: str = ""


class ActionMatchResponse(BaseModel):
    matched: bool
    action_type: str = ""
    result: Optional[ActionResultPayload] = None


# ── 다운로드 ─────────────────────────────────────────────────


DownloadFormat = Literal["docx", "xlsx", "csv", "txt"]


class DownloadRequest(BaseModel):
    content: str
    format: DownloadFormat
    filename: str | None = None  # 확장자 미포함 — 서비스에서 부여


# ═══════════════════════════════════════════════════════════
# v3.3 Phase E — 인-챗 액션 카드 (SSE 이벤트 + 5종 페이로드)
# 챗 안에서 검색/문서/규제/인사/설비 결과를 카드로 노출.
# 일반 텍스트 응답에 앞서 detection → action_card 이벤트가 SSE 로 흐른다.
# ═══════════════════════════════════════════════════════════

# 5종 카드 kind — 프런트엔드 분기용 (cards/DocumentCard.tsx 등)
ActionKind = Literal["document", "draft", "compliance", "employee", "error"]


class ActionDetectionEvent(BaseModel):
    """SSE: 액션 디텍터 매칭 결과 (action_card 직전에 송출)."""

    type: Literal["detection"] = "detection"
    kind: ActionKind
    confidence: float = 0.0   # 0.0~1.0 (정규식 매칭=1.0, 키워드=0.7 등)
    matched_keyword: str = ""


# ── 5종 카드 페이로드 ──


class DocumentItem(BaseModel):
    """문서 검색 결과 한 항목."""

    doc_id: str
    title: str
    doc_type: str = ""
    snippet: str = ""
    score: float = 0.0
    download_url: str = ""  # /api/download?doc_id=... 또는 빈 문자열


class DocumentCardPayload(BaseModel):
    """문서 검색·다운로드 카드 (Module A 결과)."""

    items: list[DocumentItem] = Field(default_factory=list)
    total: int = 0
    query: str = ""


class DraftCardPayload(BaseModel):
    """초안 작성 카드 (Module B 결과 — 부분 미리보기 + 전체 화면 링크)."""

    title: str = ""
    doc_type: str = ""
    markdown_preview: str = ""  # 첫 단락 ~ 500자
    full_view_url: str = ""     # /draft?prefill=... — 전체 화면 진입


class ComplianceCardPayload(BaseModel):
    """규제 조회 카드 (Module D 결과)."""

    regulation_id: str = ""
    title: str = ""
    severity: str = ""              # CRITICAL / HIGH / MEDIUM
    effective_date: str = ""        # YYYY-MM-DD
    days_until_effective: int | None = None  # D-30 등
    excerpt: str = ""               # 발췌 (최대 ~300자)
    affected_departments: list[str] = Field(default_factory=list)
    full_view_url: str = ""


class EmployeeContact(BaseModel):
    """가시성 적용 후 연락처 (PARTIAL 시 마스킹됨)."""

    extension: str | None = None
    email: str | None = None  # PARTIAL: ma***@ajin.com
    phone: str | None = None  # HIDDEN 시 None


class EmployeeItem(BaseModel):
    name: str
    department: str
    position: str
    visibility: Literal["FULL", "PARTIAL"] = "PARTIAL"
    contact: EmployeeContact = Field(default_factory=EmployeeContact)


class EmployeeCardPayload(BaseModel):
    """인사 검색 카드 (Module E 결과 — 가시성 매트릭스 적용)."""

    items: list[EmployeeItem] = Field(default_factory=list)
    total: int = 0
    query: str = ""
    auth_required: bool = False  # 비인증 시 true → 프런트가 로그인 안내 카드로 폴백


class ErrorPrediction(BaseModel):
    code: str
    probability: float = 0.0  # 0.0~1.0
    description: str = ""


class ErrorCardPayload(BaseModel):
    """설비 에러 + Markov 후속 + SPC 통합 카드 (Module F 결과)."""

    code: str = ""
    error_name: str = ""
    severity: str = ""              # HIGH / MEDIUM / LOW
    cause: str = ""
    action: str = ""
    avg_recovery_min: int | None = None
    history_count: int | None = None
    next_likely: list[ErrorPrediction] = Field(default_factory=list)  # Markov
    full_view_url: str = ""


class ActionCardEvent(BaseModel):
    """SSE: 액션 카드 페이로드 송출 (kind 별 payload 동적 분기).

    프런트엔드 useSSE.onActionCard 콜백이 받아 cards/{Kind}Card.tsx 로 라우팅.
    """

    type: Literal["action_card"] = "action_card"
    kind: ActionKind
    payload: dict  # DocumentCardPayload | DraftCardPayload | ... model_dump()

