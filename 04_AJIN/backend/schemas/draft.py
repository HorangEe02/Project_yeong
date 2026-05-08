"""초안 생성 관련 Pydantic 스키마.

Day 8 Phase 1 — 5 신규 엔드포인트용 스키마 추가:
- DocTypeListResponse, DocTypeMeta
- DraftStreamRequest
- CCRecRequest, CCRecResponse, CCGroup
- QualityRequest, QualityResponse, QualityScores, QualityIssue
- DiffRequest, DiffResponse, DiffStats

기존 4개 모델 (DraftGenerateRequest 등)은 backwards compatibility 위해 보존.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════
# 기존 모델 (보존)
# ═══════════════════════════════════════════════════════════


class DraftGenerateRequest(BaseModel):
    user_input: str
    doc_type: str | None = None
    tone: str = "공식적"
    include_ref: bool = True
    model: str | None = None
    language: str = "ko"
    recipient: str = "사내"
    context: str = "external"  # "internal" | "external"


class DraftResponse(BaseModel):
    session_id: str = ""
    doc_type: str = ""
    content: str = ""


class DraftReviseRequest(BaseModel):
    session_id: str
    instruction: str


class DraftExportRequest(BaseModel):
    content: str
    doc_type: str = "email_oem"
    format: str = "docx"  # "docx" | "pdf" | "hwpx" | "txt" | "odt" | "xlsx" | "csv"


# ═══════════════════════════════════════════════════════════
# Day 8 Phase 1 — 신규 5 엔드포인트 스키마
# ═══════════════════════════════════════════════════════════

# ── 1. GET /draft/doc-types ───────────────────────────────────


class DocTypeMeta(BaseModel):
    """13 문서 유형 메타 (canonical Draft.jsx 매핑)."""

    id: str
    category: Literal["internal", "external"]
    name_ko: str
    name_en: str = ""
    required_fields: list[str] = Field(default_factory=list)


class DocTypeListResponse(BaseModel):
    items: list[DocTypeMeta]
    internal_count: int = 0
    external_count: int = 0


# ── 2. POST /draft/stream (SSE) ───────────────────────────────


class DraftStreamRequest(BaseModel):
    """SSE 스트리밍 초안 생성 요청."""

    doc_type: str
    tone: str = "공식적"
    meta: dict[str, Any] = Field(default_factory=dict)  # title, recipient, content_request 등
    language: Literal["ko", "en"] = "ko"
    context: Literal["internal", "external"] = "internal"
    model: str | None = None


# ── 3. POST /draft/cc/recommend ───────────────────────────────


class CCRecRequest(BaseModel):
    """CC 자동 추천 요청 — features/draft/cc_recommender.recommend_cc 매핑."""

    doc_type: str
    sender_department: str = ""
    sender_division: str = ""
    recipient: str = ""  # 향후 확장용 (현재 cc_recommender 미사용)


class CCGroup(BaseModel):
    """CC 그룹 (필수/권장/선택)."""

    tier: Literal["required", "recommended", "optional"]
    label_ko: str
    label_en: str
    departments: list[str] = Field(default_factory=list)


class CCRecResponse(BaseModel):
    """3-tier CC 추천 결과."""

    groups: list[CCGroup]
    doc_type: str
    sender_department: str = ""


# ── 4. POST /draft/quality/score ──────────────────────────────


class QualityRequest(BaseModel):
    text: str
    doc_type: str
    reference_template: str = ""


class QualityScoresDetail(BaseModel):
    """5기준 점수 (각 max 다름)."""

    structure: float = 0.0  # 0~25
    structure_max: int = 25
    length: float = 0.0  # 0~20
    length_max: int = 20
    terminology: float = 0.0  # 0~25
    terminology_max: int = 25
    completeness: float = 0.0  # 0~15
    completeness_max: int = 15
    tone: float = 0.0  # 0~15
    tone_max: int = 15


class QualityResponse(BaseModel):
    """문서 품질 평가 응답 — features/draft/doc_quality_scorer.evaluate_document 매핑."""

    total_score: float = 0.0  # 0~100
    grade: str = "C"  # A / B+ / B / C / D / F
    scores: QualityScoresDetail = Field(default_factory=QualityScoresDetail)
    improvements: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


# ── 5. POST /draft/diff ───────────────────────────────────────


class DiffRequest(BaseModel):
    old: str
    new: str
    context_lines: int = 3


class DiffStats(BaseModel):
    added: int = 0
    removed: int = 0
    unchanged: int = 0
    similarity: float = 0.0  # 0.0 ~ 1.0


class DiffLine(BaseModel):
    """개별 diff 라인 (Frontend 렌더링용 — lg-diff-line.{add/del/mod/ctx})."""

    type: Literal["add", "del", "mod", "ctx", "header"]
    text: str


class DiffResponse(BaseModel):
    lines: list[DiffLine]
    stats: DiffStats
    diff_html: str = ""  # legacy HTML (선택)


# ═══════════════════════════════════════════════════════════
# Plan v1.0 — Module B 진단 / 모델 셀렉터 / SSE v2
# ═══════════════════════════════════════════════════════════


class DiagnoseCheck(BaseModel):
    """단일 의존성 점검 결과."""

    ok: bool
    detail: str = ""
    meta: dict[str, Any] = Field(default_factory=dict)


class DiagnoseResponse(BaseModel):
    """Module B 진단 — UI 헬스 배너용. 5개 항목.

    - ollama: 로컬 LLM 서버 가동 여부 + 설치 모델
    - gemini: Gemini API 키 존재 여부 (Feature B 에서는 차단되지만 진단은 노출)
    - pipeline: ENABLE_FEATURE_B + DraftPipeline 부팅 여부
    - templates: data/templates 의 .j2 템플릿 수
    - prompts: features/draft/prompts 의 시스템 프롬프트 수
    """

    ollama: DiagnoseCheck
    gemini: DiagnoseCheck
    pipeline: DiagnoseCheck
    templates: DiagnoseCheck
    prompts: DiagnoseCheck
    summary_ok: bool = False


class LLMOption(BaseModel):
    """모델 셀렉터 한 항목."""

    provider: Literal["ollama", "gemini"]
    id: str
    label: str
    available: bool = True
    blocked: bool = False  # Feature B 에서 보안상 차단됨
    blocked_reason: str = ""
    # v3.3 Feature C — exaone 패밀리 추가 (한국어 특화)
    family: Literal["qwen", "gemma", "gemini", "exaone", "other"] = "other"


class LLMOptionsResponse(BaseModel):
    options: list[LLMOption]
    default_provider: Literal["ollama", "gemini"] | None = None
    default_id: str | None = None
    feature: str = "draft"


class DraftStreamV2Request(BaseModel):
    """SSE v2 — Jinja2 템플릿 + RAG + LLMRouter 통합 흐름.

    기존 DraftStreamRequest 와 호환되며, provider/model 명시 + render_template 토글 추가.

    v3.6: reference_template_text — 사용자가 업로드한 참조 양식 (DOCX/PDF/HWP/TXT 추출 후
    POST /draft/upload-reference 의 응답 텍스트). 비어있지 않으면 LLM 프롬프트에 강력한
    "이 양식 그대로 따르세요" 지시문으로 prepend 됨.
    """

    doc_type: str
    tone: str = "공식적"
    meta: dict[str, Any] = Field(default_factory=dict)
    language: Literal["ko", "en"] = "ko"
    context: Literal["internal", "external"] = "internal"
    user_request: str = ""
    provider: Literal["ollama", "gemini"] | None = None
    model: str | None = None
    render_template: bool = True  # False 면 자유형 LLM 출력만 (호환 모드)
    reference_template_text: str = ""  # v3.6: 사용자 업로드 양식 (텍스트 추출본)
    reference_template_name: str = ""  # 원본 파일명 (UI 표시용)


class UploadReferenceResponse(BaseModel):
    """POST /draft/upload-reference 응답."""

    ok: bool
    filename: str
    extracted_chars: int
    truncated: bool  # UPLOAD_MAX_TEXT_CHARS 초과 시 잘림
    text: str  # 추출 텍스트 (LLM 프롬프트에 그대로 주입)
    detected_format: str  # docx / pdf / hwp / txt / md / unsupported
    warning: str = ""  # 부분 추출 등 경고
