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

# ── B6 v4.0 — 메일 발송 인터페이스 + 첨부 추천 ─────────────────


class MailRecipientPayload(BaseModel):
    email: str
    name: str = ""


class MailSendRequest(BaseModel):
    """발송 요청 — 어댑터 (mock/SMTP/Graph) 가 처리."""

    subject: str
    body: str
    body_format: Literal["markdown", "html", "text"] = "markdown"
    to: list[MailRecipientPayload] = Field(default_factory=list)
    cc: list[MailRecipientPayload] = Field(default_factory=list)
    bcc: list[MailRecipientPayload] = Field(default_factory=list)
    attachments: list[str] = Field(default_factory=list)
    doc_type: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    # Feature B Sprint 1 P0 (plan §14.2) — mail send guard fields.
    # version_id: 승인된 version_db row id. 0 = 미전달 → 가드가 412 block_no_version.
    version_id: int = Field(default=0, ge=0, description="승인된 version_db row id")
    # acknowledged_external: 외부 도메인 발송 시 사용자가 확인했는지.
    acknowledged_external: bool = Field(default=False, description="외부 도메인 발송 확인 체크")
    # watermark_id: docx/pdf/hwpx exporter 가 산출한 SHA1 8자. 감사 추적용.
    watermark_id: str = Field(default="", description="export 단계에서 부여된 워터마크 ID")


class MailSendResponse(BaseModel):
    ok: bool
    message_id: str = ""
    sent_at: str = ""
    adapter: str = ""
    detail: str = ""


class AttachmentSuggestionItem(BaseModel):
    label: str
    description: str = ""
    required: bool = False
    file_hint: str = ""


class AttachmentRecommendResponse(BaseModel):
    doc_type: str
    items: list[AttachmentSuggestionItem]
    required_labels: list[str]


# ── B4 v4.0 — 버전 관리 (사용자별 영속 + 단일 검토자) ──────────


class VersionSaveRequest(BaseModel):
    """초안 새 버전 저장 요청."""

    doc_type: str
    title: str = ""
    rendered_text: str
    template_vars: dict[str, Any] = Field(default_factory=dict)
    change_summary: str = "초기 작성"
    document_id: int | None = None  # 기존 문서면 새 버전, 없으면 새 문서 생성


class VersionSaveResponse(BaseModel):
    document_id: int
    version_id: int
    version_num: int


class VersionListItem(BaseModel):
    version_id: int
    document_id: int
    version_num: int
    change_summary: str = ""
    created_at: str = ""
    created_by: str = ""
    status: str = "draft"  # draft | under_review | approved | rejected
    reviewer_id: str = ""
    reviewed_at: str = ""
    review_note: str = ""
    doc_type: str = ""
    title: str = ""
    author: str = ""
    department: str = ""


class VersionListResponse(BaseModel):
    items: list[VersionListItem]
    total: int


class VersionReviewRequest(BaseModel):
    """검토 액션 (submit / approve / reject)."""

    action: Literal["submit", "approve", "reject"]
    reviewer_id: str
    note: str = ""


class VersionDetailResponse(BaseModel):
    """단일 버전의 본문 + 메타. rollback / 비교용."""

    version_id: int
    document_id: int
    version_num: int
    rendered_text: str
    template_vars: dict[str, Any] = Field(default_factory=dict)
    change_summary: str = ""
    created_at: str = ""
    created_by: str = ""
    status: str = "draft"
    reviewer_id: str = ""
    reviewed_at: str = ""
    review_note: str = ""
    doc_type: str = ""
    title: str = ""
    author: str = ""
    department: str = ""


# ── B3 v4.0 — POST /draft/partial-edit ────────────────────────


class PartialEditSection(BaseModel):
    """단일 섹션 메타. 클라이언트에서 본문 파싱 결과 표시용."""

    index: int
    marker: str = ""
    title: str = ""
    start: int = 0
    end: int = 0
    preview: str = ""  # 첫 80자 정도 — 호버 시 노출


class PartialEditScanRequest(BaseModel):
    """본문 → 섹션 리스트 추출 (LLM 호출 없음)."""

    body: str


class PartialEditScanResponse(BaseModel):
    sections: list[PartialEditSection]
    total: int


class PartialEditRequest(BaseModel):
    """타겟 섹션 한 단락만 LLM 으로 재작성."""

    body: str
    target_section_index: int
    instruction: str
    doc_type: str = ""
    tone: str = "표준"


class PartialEditResponse(BaseModel):
    """전체 본문(섹션 교체 적용) + 변경된 섹션 본문."""

    new_body: str
    new_section_content: str
    target_section_index: int
    model: str = ""
    provider: str = ""


# ── 1. GET /draft/doc-types ───────────────────────────────────


class VarMetadata(BaseModel):
    """B2 — 변수 입력 폼 메타 (필수★ + 그룹 + placeholder 예시)."""

    name: str
    label_ko: str = ""
    required: bool = False
    group: str = "내용"  # "수신/발신" | "기본" | "내용" | "일정" | "참조"
    placeholder: str = ""


class DocTypeMeta(BaseModel):
    """문서 유형 메타. v4.0 에서 카드 미리보기·가이드·부서 추천 필드 추가."""

    id: str
    category: Literal["internal", "external"]
    name_ko: str
    name_en: str = ""
    required_fields: list[str] = Field(default_factory=list)
    # B1 — 카드 hover 미리보기 + 가이드 + 부서 추천 배지
    usage_hint: str = ""           # "이럴 때 씁니다" 한 줄 설명
    dept_recommend: list[str] = Field(default_factory=list)  # 추천 부서 (예: ["품질보증팀"])
    example_output: str = ""       # 카드 hover 시 노출할 출력 한 줄
    var_metadata: list[VarMetadata] = Field(default_factory=list)


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
    """CC 그룹 (필수/권장/자주 함께 보낸/선택). v4.0 — frequent 티어 추가."""

    tier: Literal["required", "recommended", "frequent", "optional"]
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
    # v3.5 — nemotron 패밀리 (NVIDIA 대형) 추가
    family: Literal["qwen", "gemma", "gemini", "exaone", "nemotron", "other"] = "other"
    # v3.5 — 사용자 친화 호버 카드 + Use case 그룹화 (config.py MODEL_PROFILES 에서 추출)
    summary_ko: str = ""
    use_when_ko: str = ""
    use_case: Literal["korean", "multilingual", "vision", "reasoning"] = "multilingual"


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
