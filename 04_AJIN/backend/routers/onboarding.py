"""온보딩 채팅 라우터.

v3.0: 인증 사용자 추적 — 부서 정보를 LLM에 주입
v4.0 (Phase 2): LLMRouter (Gemini → Ollama → LM Studio) 폴백 체인 + Circuit Breaker + 메트릭
"""

import base64
import json
import logging
import urllib.parse
from pathlib import Path
from typing import Iterable

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from backend.schemas.onboarding import (
    ActionMatchRequest,
    ActionMatchResponse,
    ActionResultPayload,
    DownloadRequest,
    OnboardingChatRequest,
    OnboardingChatResponse,
    ScenarioCard,
    ScenarioMatchRequest,
    ScenarioMatchResponse,
    SopDetailResponse,
    SopListResponse,
    SopStep,
    SopSummary,
    SourceRef,
)
from backend.dependencies import get_current_user
from backend.services import download_service
from core.llm_router import LLMRouter
from core.llm_types import LLMMode
from core.security import sanitize_llm_input, validate_path

logger = logging.getLogger(__name__)

_MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB
_MAX_QUERY_CHARS = 8000
# v3.3 Phase G-2 — CAD / HWP 확장자 화이트리스트 추가.
# - 텍스트 CAD: dxf, step/stp, igs/iges (ezdxf + 정규식)
# - 바이너리 CAD: sldprt, sldasm, prt, catpart, catproduct (메타만)
# - 한글: hwp (olefile), hwpx (zip+xml — 기존 _extract_hwpx 재사용)
# - 추가: md, log (기존 llm_client 가 처리)
_ALLOWED_EXTENSIONS = {
    # 기존
    ".pdf", ".txt", ".md", ".log", ".docx", ".doc", ".xlsx", ".xls",
    ".csv", ".hwp", ".hwpx",
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp",
    # v3.3 Phase G — 텍스트 CAD
    ".dxf", ".step", ".stp", ".igs", ".iges",
    # v3.3 Phase G — 바이너리 CAD (메타만)
    ".sldprt", ".sldasm", ".prt", ".catpart", ".catproduct",
}

# 새 dispatcher 가 처리하는 확장자 (G-1) — 기존 extract_text_from_file 보다 우선.
_RICH_EXTRACTOR_EXTENSIONS = {
    ".dxf", ".step", ".stp", ".igs", ".iges",
    ".sldprt", ".sldasm", ".prt", ".catpart", ".catproduct",
    ".hwp",
}
_ANALYZER_MAX_UPLOAD_BYTES = 20 * 1024 * 1024
_IMAGE_ANALYZER_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}
_DOCUMENT_ANALYZER_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".hwp", ".hwpx"}
_IMAGE_ANALYZER_CONTENT_TYPES = {
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/bmp",
    "image/webp",
}
_DOCUMENT_ANALYZER_CONTENT_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.hancom.hwp",
    "application/haansofthwp",
    "application/octet-stream",
    "text/plain",
    "text/markdown",
}

router = APIRouter(
    prefix="/onboarding",
    tags=["onboarding"],
    dependencies=[Depends(get_current_user)],
)

# 모듈 싱글톤 — LLMRouter 는 무거운 SDK 클라이언트를 lazy 로 보유
_llm_router = LLMRouter()


_DEFAULT_DEPT = "품질보증팀"
_MANAGER_LEVEL = 3   # 같은 본부 내 부서 컨텍스트 변경 가능
_EXECUTIVE_LEVEL = 4  # 전사 부서 컨텍스트 변경 가능


def _get_division(dept_name: str) -> str | None:
    """부서명 → 본부명. DEPARTMENT_PROFILES 활용 (없으면 None)."""
    from features.onboarding.department_router import DEPARTMENT_PROFILES

    profile = DEPARTMENT_PROFILES.get(dept_name)
    return profile.division if profile else None


def _resolve_effective_department(req_dept: str | None, user) -> str:
    """v3.3 Phase B — 부서 컨텍스트 RBAC 강제 + 본부 경계.

    권한 매트릭스:
    - 인증 사용자만 허용하며, 권한 레벨에 따라 부서 변경 범위를 제한.
    - L<3 (EMPLOYEE): 자기 부서 강제. req.department 가 다르면 경고 로그 + 무시.
    - L=3 (MANAGER): 같은 본부 내 부서만 허용. 타 본부 시도 시 자기 부서 fallback + 경고.
    - L>=4 (EXECUTIVE/SYS): 전사 자유 변경.
    """
    if user is None:
        return _DEFAULT_DEPT

    user_dept = getattr(user, "department", None) or _DEFAULT_DEPT
    user_level = getattr(user, "role_level", 0) or 0
    req_dept_clean = (req_dept or "").strip()

    # L>=4 — 전사 자유
    if user_level >= _EXECUTIVE_LEVEL:
        return req_dept_clean or user_dept

    # L=3 — 같은 본부 내만
    if user_level >= _MANAGER_LEVEL:
        if not req_dept_clean or req_dept_clean == user_dept:
            return user_dept
        user_div = _get_division(user_dept)
        req_div = _get_division(req_dept_clean)
        if user_div and req_div and user_div == req_div:
            return req_dept_clean
        # 본부 경계 위반 — 자기 부서 fallback + 경고
        logger.warning(
            "본부 경계 위반 차단 — user=%s L%s user_div=%s req=%s req_div=%s forced=%s",
            getattr(user, "username", "?"),
            user_level,
            user_div,
            req_dept_clean,
            req_div,
            user_dept,
        )
        return user_dept

    # L<3 — 자기 부서 강제
    if req_dept_clean and req_dept_clean != user_dept:
        logger.warning(
            "부서 변경 시도 차단 — user=%s L%s requested=%s forced=%s",
            getattr(user, "username", "?"),
            user_level,
            req_dept_clean,
            user_dept,
        )
    return user_dept


async def _require_analyzer_enabled(request: Request, user=Depends(get_current_user)) -> bool:
    """Guard department-specific OCR/analyzer endpoints behind a feature flag.

    Args:
        request: Current FastAPI request.
        user: Authenticated user context.

    Returns:
        bool: True when analyzer endpoints are enabled.

    Raises:
        HTTPException: 403 when ``FEATURE_C_ANALYZERS_ENABLED`` is false.
    """

    from backend.auth_middleware import log_api_access
    from core.feature_flags import load_feature_c_flags

    if not load_feature_c_flags().analyzers_enabled:
        log_api_access(
            endpoint=str(request.url.path),
            method=request.method,
            status_code=403,
            detail="analyzer_disabled",
            ip_address=request.client.host if request.client else "",
            user=user,
            intent="feature_c_analyzer",
        )
        raise HTTPException(status_code=403, detail="analyzer_disabled")

    log_api_access(
        endpoint=str(request.url.path),
        method=request.method,
        status_code=200,
        detail="analyzer_enabled",
        ip_address=request.client.host if request.client else "",
        user=user,
        intent="feature_c_analyzer",
    )
    return True


def _normalize_content_type(content_type: str | None) -> str:
    """Normalize an upload content type by removing parameters.

    Args:
        content_type: Raw content type from the upload.

    Returns:
        Lowercase MIME type without ``; charset=...`` suffixes.
    """

    return (content_type or "").split(";", 1)[0].strip().lower()


async def _read_analyzer_upload(
    file: UploadFile,
    *,
    allowed_extensions: Iterable[str],
    allowed_content_types: Iterable[str],
) -> bytes:
    """Read and validate an analyzer upload before any model call.

    Args:
        file: Uploaded file object.
        allowed_extensions: Extension allowlist for this analyzer family.
        allowed_content_types: MIME type allowlist for this analyzer family.

    Returns:
        bytes: Uploaded file bytes.

    Raises:
        HTTPException: 413 for oversized uploads or 415 for unsupported files.
    """

    filename = file.filename or ""
    ext = Path(filename).suffix.lower()
    allowed_ext = {item.lower() for item in allowed_extensions}
    if ext not in allowed_ext:
        raise HTTPException(status_code=415, detail="analyzer_file_type_unsupported")

    normalized_type = _normalize_content_type(file.content_type)
    allowed_types = {item.lower() for item in allowed_content_types}
    if normalized_type and normalized_type not in allowed_types:
        raise HTTPException(status_code=415, detail="analyzer_content_type_unsupported")

    data = await file.read()
    if len(data) > _ANALYZER_MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="analyzer_file_too_large")
    return data


async def _read_vision_analyzer_upload(file: UploadFile) -> bytes:
    """Read an image analyzer upload.

    Args:
        file: Uploaded image file.

    Returns:
        bytes: Validated upload bytes.
    """

    return await _read_analyzer_upload(
        file,
        allowed_extensions=_IMAGE_ANALYZER_EXTENSIONS,
        allowed_content_types=_IMAGE_ANALYZER_CONTENT_TYPES,
    )


async def _read_document_analyzer_upload(file: UploadFile) -> bytes:
    """Read a document analyzer upload.

    Args:
        file: Uploaded document file.

    Returns:
        bytes: Validated upload bytes.
    """

    return await _read_analyzer_upload(
        file,
        allowed_extensions=_DOCUMENT_ANALYZER_EXTENSIONS,
        allowed_content_types=_DOCUMENT_ANALYZER_CONTENT_TYPES,
    )


def _analyzer_response(task: str, department: str, data: dict, route_family: str) -> dict:
    """Build a normalized analyzer response with trust metadata.

    Args:
        task: Analyzer task id.
        department: Department context passed by the caller.
        data: Model-extracted task payload.
        route_family: ``vision`` or ``document``.

    Returns:
        dict: Backward-compatible analyzer response plus source metadata.
    """

    from features.onboarding.citations import analyzer_source_ref

    source = analyzer_source_ref(task, route_family).to_dict()
    return {
        "task": task,
        "department": department,
        "data": data,
        "sources": [source],
        "citation_status": "model_only",
    }


@router.post("/chat")
async def onboarding_chat(
    req: OnboardingChatRequest,
    request: Request,
    user=Depends(get_current_user),
):
    """온보딩 챗봇 응답 (SSE 스트리밍).

    LLMRouter 의 Gemini → Ollama → LM Studio 폴백 체인을 사용한다.
    v3.3 Phase B — 부서 컨텍스트는 _resolve_effective_department() 로 RBAC 강제.
    v3.3 Phase E — FEATURE_C_INLINE_ACTIONS 활성 시 detect_actions() → action_card 이벤트 송출.
    """
    # 입력 살균 — 너무 길면 거부 (DoS 방어)
    if not req.query or not req.query.strip():
        raise HTTPException(status_code=400, detail="query 가 비어 있습니다.")
    if len(req.query) > _MAX_QUERY_CHARS:
        raise HTTPException(status_code=413, detail=f"query 가 {_MAX_QUERY_CHARS}자를 초과합니다.")

    dept = _resolve_effective_department(req.department, user)

    history_text = ""
    if req.history:
        history_text = "\n".join(
            f"{'사용자' if m.role == 'user' else 'AI'}: {sanitize_llm_input(m.content)}"
            for m in req.history[-4:]
        )

    file_ctx = ""
    if req.file_context:
        file_ctx = f"\n\n[첨부 파일 내용]\n{req.file_context[:2000]}"

    # ── v3.3 Phase E — 인-챗 액션 감지 + 카드 페이로드 사전 계산 ──
    # 피처 플래그 비활성 시 detect_actions 자체를 건너뛴다 (점진 활성화).
    from core.feature_flags import load_feature_c_flags
    from features.onboarding.action_handlers import (
        dispatch_action,
        summarize_payload_for_llm,
    )
    from features.onboarding.work_actions import detect_actions

    flags = load_feature_c_flags()
    detected_actions: list = []
    action_payloads: list[tuple] = []  # [(DetectedAction, payload_dict), ...]

    if flags.inline_actions:
        try:
            detected_actions = detect_actions(req.query)
        except Exception:
            logger.exception("detect_actions 실패")
            detected_actions = []

        # 의존성 주입 — app.state 에서 검색기/엔진 추출 (없으면 None 으로 graceful)
        searcher = getattr(request.app.state, "searcher", None)
        employee_engine = getattr(request.app.state, "employee_engine", None)

        for act in detected_actions:
            try:
                payload = dispatch_action(
                    action=act,
                    query=req.query,
                    user=user,
                    department=dept,
                    searcher=searcher,
                    employee_engine=employee_engine,
                )
                action_payloads.append((act, payload))
            except Exception:
                logger.exception("dispatch_action 실패: kind=%s", act.kind)

    # 액션 결과를 LLM 프롬프트에 system context 로 주입 — 후속 답변에서 참조 가능
    action_context = ""
    if action_payloads:
        summaries = [summarize_payload_for_llm(a.kind, p) for a, p in action_payloads]
        action_context = "\n\n[액션 실행 결과 (이미 사용자에게 카드로 표시됨)]\n" + "\n".join(
            s for s in summaries if s
        )

    # C5 v4.0 — Quick Question 의 promptText 매칭 시 KB markdown 자동 prepend
    # (직원 복리후생 / 시설관리 / 사회 환원활동 / 채용 등 사내 정형 답변)
    # Feature C Sprint 1 P0 (plan §27.2): load_kb_context 가 KBContext TypedDict 반환.
    # citation_id 를 prompt 에 포함 → Sprint 2 citation_enforcer 가 출처 검증.
    from features.onboarding.citations import (
        SourceRef as RuntimeSourceRef,
        enforce_citations,
        source_ref_from_kb_context,
    )
    from features.onboarding.kb_lookup import load_kb_context
    from features.onboarding.i18n_router import (
        resolve_language,
        build_language_instruction,
    )

    # v4.7 C-2 — 응답 언어 결정 (auto 면 query 언어 감지)
    resolved_lang = resolve_language(req.query, req.chat_language)

    kb_context = ""
    source_refs: list[RuntimeSourceRef] = []
    kb_ctx = load_kb_context(req.query, dept, max_chars=4000, language=resolved_lang)
    if kb_ctx:
        cid = kb_ctx["citation_id"]
        try:
            source_refs.append(source_ref_from_kb_context(kb_ctx))
        except ValueError:
            logger.warning("KB context citation metadata invalid: %s", kb_ctx.get("source_path"))
        kb_context = (
            "\n\n[사내 지식베이스 자료 — 이 문서를 근거로 답변하세요]\n"
            f"[출처ID: {cid}]\n"
            "──────────────────────────────────────\n"
            f"{kb_ctx['text']}\n"
            "──────────────────────────────────────\n"
            f"위 자료를 1차 근거로 답변하고, 각 사실 진술 뒤에 반드시 [출처:{cid}] 를 부착하세요. "
            "자료에 없는 항목은 인사관리팀 문의로 안내하세요."
        )

    # v4.x Phase 1 PR2 follow-up — CRAG retrieval evaluator wiring.
    # 사용자 §11 #3 확정: incorrect → LLM 호출 우회 강제 차단.
    # searcher 가 있으면 검색 호출 → top-1 rerank_score 기반 verdict.
    # docs/RAG_ENHANCEMENT_PLAN.md §2.2.
    crag_verdict = "correct"
    crag_top_score = 0.0
    crag_blocked_message = ""
    try:
        from config import CRAG_ENABLED
    except ImportError:
        CRAG_ENABLED = False

    searcher_for_crag = getattr(request.app.state, "searcher", None)
    if CRAG_ENABLED and searcher_for_crag is not None and req.query:
        try:
            from features.search.crag_evaluator import (
                blocked_response_message,
                evaluate_retrieval,
                should_block_llm,
            )

            crag_results = searcher_for_crag.search(query=req.query, k=5)
            crag = evaluate_retrieval(crag_results)
            crag_verdict = crag.verdict
            crag_top_score = crag.top_score
            if should_block_llm(crag.verdict):
                crag_blocked_message = blocked_response_message(crag.rationale)
            logger.info(
                "[CRAG/chat] verdict=%s top_score=%.3f query=%s",
                crag_verdict,
                crag_top_score,
                req.query[:60],
            )
        except Exception:
            logger.exception("CRAG evaluator 호출 실패 — 정상 흐름 진행")

    # v4.7 Sprint 2 P0 (축 ①) — InputComposer "/" 으로 인용된 항목을 system prompt 에 주입.
    ref_context = ""
    if req.references:
        ref_lines = ["\n\n[사용자가 인용한 항목]"]
        for ref in req.references:
            title = (ref.title or "").strip()
            kind = (ref.kind or "item").strip()
            if not title:
                continue
            citation_id = f"{kind}:{ref.id}".replace(" ", "_")
            source_refs.append(
                RuntimeSourceRef(
                    citation_id=citation_id,
                    source_path=ref.id,
                    source_type=kind,
                    title=title,
                )
            )
            ref_lines.append(f"- 사용자가 인용한 항목: {kind} {title} [출처ID: {citation_id}]")
        if len(ref_lines) > 1:
            ref_lines.append(
                "위 항목들을 답변에서 우선적으로 참조하세요. "
                "데이터가 없으면 추측하지 말고 사용자에게 추가 조회를 안내하세요. "
                "인용 항목을 근거로 답할 때는 반드시 해당 [출처:<출처ID>] 를 붙이세요."
            )
            ref_context = "\n".join(ref_lines)

    # v4.7 C-2 — 언어 지시문 (KO/EN 동적). 시스템 prompt 의 마지막 줄에 주입.
    lang_instruction = build_language_instruction(resolved_lang)
    citation_instruction = (
        "6. 제공된 사내 자료나 인용 항목을 근거로 답할 때는 각 근거 문장에 반드시 [출처:<출처ID>] 를 붙이세요."
        if source_refs
        else "6. 현재 매칭된 사내 자료 출처가 없으므로 답변에 '사내 자료에서 확인된 출처 없음'을 명시하고 최신성 확인은 담당 부서에 안내하세요."
    )

    prompt = f"""당신은 아진산업 사내 AI 업무 도우미입니다.
운영 환경: **온프레미스 사내 시스템** — 모든 사용자는 인증된 아진산업 직원입니다.
소속 부서: {dept}

== 응답 정책 (반드시 준수) ==
1. 사내 직원 연락처/이메일/내선/휴대폰은 **업무 목적 공유 가능** (사내 인트라넷 공개 정보 수준).
   "보안상 공개를 삼가야 합니다" 같은 외부 환경용 마스킹 표현 **사용 금지**.
2. 액션 카드(인사 검색, 문서 검색 등) 결과가 제공되면 **그 데이터를 정확히 그대로** 사용.
   결과에 없는 정보(가짜 전화번호/이메일/사원번호) **추가 절대 금지**.
3. 검색 결과가 0건이면 정직하게 답변:
   - 인사 검색 0건 → "인사 DB 미등록 — 부서장 또는 총무인사팀에 문의"
   - 문서 검색 0건 → "관련 문서를 찾지 못했습니다"
   가짜 데이터 채우지 말고 **정보 없음을 명시**.
4. `010-X xxxx-xxxx` 같은 마스킹 번호 또는 임의 생성 이메일 **출력 금지**.
5. 인물 정보를 답할 때는 카드 데이터의 visibility 라벨([FULL]/[PARTIAL])을 신뢰하고
   FULL 이면 모든 필드, PARTIAL 이면 카드에 노출된 필드만 답변.
{citation_instruction}

{f'[이전 대화]{chr(10)}{history_text}' if history_text else ''}
{file_ctx}{action_context}{kb_context}{ref_context}

[질문] {sanitize_llm_input(req.query)}

== Language Policy ==
{lang_instruction}
아진산업 자동차 부품 제조 맥락에서 설명하세요."""

    # 라우터 history 는 {role, content} 형태 — Pydantic 모델은 dict 변환
    history_payload = [{"role": m.role, "content": m.content} for m in (req.history or [])]

    # Day 5 Phase 5 — UI ModelSelect 가 force_provider=[provider, model] 로 강제 가능.
    force = None
    if req.force_provider and len(req.force_provider) == 2:
        force = (req.force_provider[0], req.force_provider[1])

    serialized_sources = [source.to_dict() for source in source_refs]

    async def event_stream():
        yield {"data": json.dumps(
            {
                "type": "sources",
                "content": None,
                "metadata": {
                    "sources": serialized_sources,
                    "citation_status": "verified" if serialized_sources else "model_only",
                },
            },
            ensure_ascii=False,
        )}
        # v3.3 Phase E — 액션 카드 이벤트 (detection → action_card) 가 LLM 토큰보다 먼저.
        for act, payload in action_payloads:
            yield {"data": json.dumps(
                {
                    "type": "detection",
                    "kind": act.kind,
                    "confidence": act.confidence,
                    "matched_keyword": act.matched_keyword,
                },
                ensure_ascii=False,
            )}
            yield {"data": json.dumps(
                {"type": "action_card", "kind": act.kind, "payload": payload},
                ensure_ascii=False,
                default=str,
            )}

        # CRAG verdict='incorrect' → LLM 호출 우회 강제 차단 (사용자 §11 #3).
        # 사내 자료 없음 안내만 token + done 으로 송출하고 stream 종료.
        if crag_blocked_message:
            yield {"data": json.dumps(
                {"type": "token", "content": crag_blocked_message, "metadata": None},
                ensure_ascii=False,
            )}
            yield {"data": json.dumps(
                {
                    "type": "done",
                    "content": None,
                    "metadata": {
                        "citation_status": "crag_blocked",
                        "crag_verdict": crag_verdict,
                        "crag_top_score": crag_top_score,
                        "sources": [],
                    },
                },
                ensure_ascii=False,
            )}
            return

        try:
            chunks: list[str] = []
            final_meta: dict = {}
            async for ev in _llm_router.stream(
                prompt=prompt,
                mode=LLMMode.CHAT_KOREAN,
                history=history_payload,
                force_provider=force,
            ):
                ev_type = ev.get("type") if isinstance(ev, dict) else ""
                if ev_type == "token":
                    chunks.append(str(ev.get("content") or ""))
                if ev_type == "done":
                    final_meta = dict(ev.get("metadata") or {})
                    continue
                if ev_type == "error":
                    yield {"data": json.dumps(ev, ensure_ascii=False, default=str)}
                    return
                yield {"data": json.dumps(ev, ensure_ascii=False, default=str)}
            enforced = enforce_citations("".join(chunks), source_refs)
            if enforced.footer:
                yield {"data": json.dumps(
                    {"type": "token", "content": enforced.footer, "metadata": None},
                    ensure_ascii=False,
                )}
            yield {"data": json.dumps(
                {
                    "type": "done",
                    "content": None,
                    "metadata": {
                        **final_meta,
                        "citation_status": enforced.citation_status,
                        "sources": enforced.sources,
                    },
                },
                ensure_ascii=False,
                default=str,
            )}
        except Exception as e:
            logger.exception("온보딩 채팅 스트리밍 오류")
            yield {"data": json.dumps({
                "type": "error",
                "content": str(e),
                "metadata": {"citation_status": "failed", "sources": serialized_sources},
            }, ensure_ascii=False)}

    return EventSourceResponse(event_stream())


@router.get("/health")
async def onboarding_health():
    """LLMRouter 의 등록 프로바이더와 Circuit Breaker 상태를 반환한다."""
    snapshot = _llm_router.health.snapshot()
    return {
        "providers": list(_llm_router.providers.keys()),
        "circuit": {p: snapshot.get(p, {"state": "closed"}) for p in _llm_router.providers},
        "metrics": _llm_router.metrics.snapshot(),
    }


# ═══════════════════════════════════════════════════════════
# v3.3 Phase D — Quick Questions 개인화 엔드포인트
# 부서 / 직급 / 팀 매트릭스 기반 6 슬롯 추천 질문 반환.
# 인증 사용자: Phase B 의 RBAC 적용 — L<3 은 자기 부서 강제, L=3 같은 본부, L>=4 전사.
# 비인증: ?department= 그대로 사용 (DEMO 환경).
# ═══════════════════════════════════════════════════════════


@router.get("/quick-questions")
async def get_quick_questions_endpoint(
    response: Response,
    department: str = "",
    user=Depends(get_current_user),
):
    """v3.3 Phase D — 부서/직급별 Quick Questions 6개 반환.

    프런트엔드 chat.tsx 가 마운트 시 1회 + dept/role 변경 시 재호출.
    Cache-Control 5분으로 admin 시뮬레이션 시에도 빠른 전환 가능.
    """
    from features.onboarding.quick_questions import get_quick_questions

    # Phase B 권한 매트릭스 재사용 — 부서 컨텍스트 강제
    effective_dept = _resolve_effective_department(department, user)

    role_level = getattr(user, "role_level", 0) or 0
    if role_level == 0:
        # 테스트/레거시 컨텍스트 방어: role_level 누락 시 L1 로 보수적 노출.
        role_level = 1

    position = getattr(user, "position", None) if user else None
    items = get_quick_questions(
        department=effective_dept,
        role_level=role_level,
        position=position,
    )

    response.headers["Cache-Control"] = "private, max-age=300"
    return {
        "items": items,
        "department": effective_dept,
        "role_level": role_level,
        "total": len(items),
    }


@router.post("/chat/vision", response_model=OnboardingChatResponse)
async def onboarding_vision(
    query: str = Form(...),
    department: str = Form(default="품질보증팀"),
    model: str | None = Form(default=None),
    file: UploadFile = File(...),
):
    """이미지를 포함한 비전 모델 채팅."""
    from core.llm_client import auto_select_vision_model, invoke_vision

    vision_model = model or auto_select_vision_model()
    if not vision_model:
        raise HTTPException(status_code=400, detail="비전 모델이 설치되어 있지 않습니다.")

    image_bytes = await file.read()
    prompt = f"아진산업 {department} 맥락에서 분석해주세요.\n{query}"
    response = invoke_vision(prompt, image_bytes, model=vision_model)

    return OnboardingChatResponse(
        response=response,
        model_used=vision_model,
        source="vision",
    )


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """파일 업로드 후 텍스트/메타를 추출한다.

    v3.3 Phase G-2 — CAD/HWP 확장 (FEATURE_C_CAD_UPLOAD 플래그 게이트).
    응답은 backward compat 유지하며 CAD/HWP 의 경우 ``metadata`` + ``preview_image_b64`` 추가.
    """
    from core.llm_client import extract_text_from_file
    from core.feature_flags import load_feature_c_flags

    file_bytes = await file.read()
    filename = file.filename or "unknown"

    # 파일 크기 검증 (최대 20 MB)
    if len(file_bytes) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="파일 크기가 20MB를 초과합니다.")

    # 파일 확장자 검증
    from pathlib import Path as _Path
    import tempfile as _tempfile
    ext = _Path(filename).suffix.lower()

    # v3.3 Phase G-2 — CAD 업로드 플래그 비활성 시 CAD 확장자 차단
    flags = load_feature_c_flags()
    allowed = set(_ALLOWED_EXTENSIONS)
    if not flags.cad_upload:
        # HWP 는 항상 허용 (Phase 0 이전부터 지원). CAD 만 게이트.
        allowed -= (_RICH_EXTRACTOR_EXTENSIONS - {".hwp"})

    if ext not in allowed:
        raise HTTPException(status_code=415, detail=f"허용되지 않는 파일 형식입니다: {ext}")

    # 경로 순회 공격 방어: 파일명이 허용된 임시 디렉토리 내에 있는지 확인
    if not validate_path(_Path(_tempfile.gettempdir()) / _Path(filename).name, _tempfile.gettempdir()):
        raise HTTPException(status_code=400, detail="잘못된 파일 이름입니다.")

    # 이미지 여부 확인
    is_image = filename.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"))

    if is_image:
        return {
            "filename": filename,
            "is_image": True,
            "text": "",
            "image_base64": base64.b64encode(file_bytes).decode("utf-8"),
        }

    # v3.3 Phase G-2 — CAD/HWP 는 신규 dispatcher (rich metadata + preview_image_b64)
    if ext in _RICH_EXTRACTOR_EXTENSIONS:
        from core.file_extractors import extract_with_meta

        result = extract_with_meta(file_bytes, filename=filename)
        return {
            "filename": filename,
            "is_image": False,
            "text": result.get("text", ""),
            "metadata": result.get("metadata", {}),
            "preview_image_b64": result.get("preview_image_b64", ""),
        }

    # 기타 (pdf/docx/xlsx/csv/hwpx 등) — 기존 추출기
    text = extract_text_from_file(file_bytes, filename)
    return {
        "filename": filename,
        "is_image": False,
        "text": text,
    }


# ═══════════════════════════════════════════════════════════
# Day 5 — SOP / 시나리오 / 액션 / 다운로드 (Phase 1)
# features/onboarding/* 의 LLM 0회 매칭 기능을 그대로 노출.
# ═══════════════════════════════════════════════════════════


@router.get("/sop/list", response_model=SopListResponse)
async def list_sops():
    """SOP 8종 목록을 사이드 패널용 요약으로 반환."""
    from features.onboarding.sop_guide import get_all_sops

    docs = get_all_sops()
    items = [
        SopSummary(
            sop_id=d.sop_id,
            title=d.title,
            department=d.department,
            category=d.category,
            steps_count=len(d.steps),
            citation_id=d.citation_id,
            owner_department=d.owner_department,
            reviewed_at=d.reviewed_at,
            effective_date=d.effective_date,
            version=d.version,
            status=d.status,
        )
        for d in docs
    ]
    return SopListResponse(items=items, total=len(items))


@router.get("/sop/{sop_id}", response_model=SopDetailResponse)
async def get_sop_detail(sop_id: str):
    """SOP 단일 상세 — Stepper Drawer 표시용."""
    from features.onboarding.sop_guide import SOP_DATABASE

    doc = SOP_DATABASE.get(sop_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"SOP '{sop_id}' 가 존재하지 않습니다.")

    return SopDetailResponse(
        sop_id=doc.sop_id,
        title=doc.title,
        department=doc.department,
        category=doc.category,
        citation_id=doc.citation_id,
        owner_department=doc.owner_department,
        reviewed_at=doc.reviewed_at,
        effective_date=doc.effective_date,
        version=doc.version,
        status=doc.status,
        sources=[
            SourceRef(
                citation_id=doc.citation_id,
                source_path=f"data/knowledge_base/sops/{doc.sop_id}.json",
                source_type="sop",
                reviewed_at=doc.reviewed_at,
                title=doc.title,
            )
        ] if doc.citation_id else [],
        prerequisites=list(doc.prerequisites),
        safety_warnings=list(doc.safety_warnings),
        related_sops=list(doc.related_sops),
        steps=[
            SopStep(
                step_number=s.step_number,
                title=s.title,
                description=s.description,
                checklist=list(s.checklist),
                caution=s.caution,
                related_terms=list(s.related_terms),
                estimated_time=s.estimated_time,
                responsible=s.responsible,
            )
            for s in doc.steps
        ],
    )


# ──────────────────────────────────────────────────────────────────
# v3.6 — GET /sop/{sop_id}/quiz
# 선택된 SOP 의 단계·체크리스트·주의사항을 기반으로 4지선다 퀴즈 N문항 생성.
# 프론트 Module C 의 퀴즈 탭이 이 엔드포인트를 호출하여 SOP 별 동적 퀴즈 표시.
# ──────────────────────────────────────────────────────────────────


@router.get("/sop/{sop_id}/quiz")
async def get_sop_quiz(sop_id: str, count: int = 3):
    """SOP 기반 퀴즈 자동 생성 — 사용자가 선택한 SOP 의 단계·체크리스트·주의사항에서
    4지선다 문제 N개 (기본 3) 생성.

    quiz_engine.generate_sop_quiz() 가 호출 1회당 1문항 반환하므로 count 만큼 반복.
    중복은 허용 (random pick — 단계 수가 적은 SOP 의 경우 일부 반복될 수 있음).
    """
    from features.onboarding.quiz_engine import generate_sop_quiz
    from features.onboarding.sop_guide import SOP_DATABASE

    if sop_id not in SOP_DATABASE:
        raise HTTPException(status_code=404, detail=f"SOP '{sop_id}' 가 존재하지 않습니다.")

    # 1 ~ 10 범위로 클램프
    n = max(1, min(count, 10))

    questions = []
    seen_questions: set[str] = set()
    # 최대 시도 N*3 — 동일 문제가 너무 자주 나오면 조기 탈출
    for _ in range(n * 3):
        if len(questions) >= n:
            break
        q = generate_sop_quiz(sop_id)
        if q is None:
            continue
        if q.question in seen_questions:
            continue
        seen_questions.add(q.question)
        questions.append(
            {
                "question": q.question,
                "options": list(q.options),
                "correct_index": q.correct_index,
                "explanation": q.explanation,
                "category": q.category,
                "source_id": q.source_id,
                "related_step": q.related_step,
            }
        )

    return {
        "sop_id": sop_id,
        "title": SOP_DATABASE[sop_id].title,
        "questions": questions,
        "total": len(questions),
    }


@router.post("/scenarios/match", response_model=ScenarioMatchResponse)
async def match_scenario(req: ScenarioMatchRequest, user=Depends(get_current_user)):
    """협업 시나리오 키워드 매칭 (LLM 호출 0회 — 본선 시연 차별점).

    Phase 2: 로그인 사용자의 division/lang 컨텍스트로 매칭.
    Phase 3: 매칭 성공 시 scenario_usage 에 통계 기록.
    """
    from features.onboarding.collaboration_guide import (
        format_collaboration_response,
        match_collaboration,
    )

    if not req.query or not req.query.strip():
        raise HTTPException(status_code=400, detail="query 가 비어 있습니다.")

    division = getattr(user, "division", "") or ""
    matched = match_collaboration(req.query, division=division, lang="ko")
    if matched is None:
        return ScenarioMatchResponse(matched=False, card=None)

    # Phase 3: usage 통계 기록 (실패해도 응답은 그대로)
    try:
        from core.scenarios import repository as _scenarios_repo

        _scenarios_repo.record_usage(
            scenario_id=matched.id,
            matched_by=getattr(user, "employee_id", "") or "",
            query_text=req.query,
        )
    except Exception:  # noqa: BLE001
        pass

    card = ScenarioCard(
        scenario_id=matched.id,
        situation=matched.situation,
        requesting_dept=matched.requesting_dept,
        my_actions=list(matched.my_actions),
        hand_off_to=matched.hand_off_to,
        hand_off_items=list(matched.hand_off_items),
        deadline_info=matched.deadline_info,
        related_sop_id=matched.related_sop_id or "",
        tips=list(matched.tips),
        formatted_text=format_collaboration_response(matched),
    )
    return ScenarioMatchResponse(matched=True, card=card)


@router.post("/actions/match", response_model=ActionMatchResponse)
async def match_action(req: ActionMatchRequest):
    """업무 액션 라우터 — error_code / employee / spc / regulation 등을 채팅 내 즉시 응답."""
    from features.onboarding.work_actions import detect_action, execute_action

    if not req.query or not req.query.strip():
        raise HTTPException(status_code=400, detail="query 가 비어 있습니다.")

    detected = detect_action(req.query)
    if detected is None:
        return ActionMatchResponse(matched=False)

    action_type, params = detected
    try:
        result = execute_action(action_type, params, req.query)
    except Exception as e:
        logger.exception("업무 액션 실행 오류")
        raise HTTPException(status_code=500, detail=f"액션 실행 실패: {e}")

    return ActionMatchResponse(
        matched=True,
        action_type=action_type,
        result=ActionResultPayload(
            action_type=result.action_type,
            success=result.success,
            display_text=result.display_text,
            bridge_target=result.bridge_target,
        ),
    )


_DOWNLOAD_MAX_CHARS = 200_000


@router.post("/download")
async def download_response(req: DownloadRequest):
    """채팅 응답을 4 포맷 (DOCX/XLSX/CSV/TXT) 으로 변환하여 바이트 다운로드."""
    if not req.content or not req.content.strip():
        raise HTTPException(status_code=400, detail="content 가 비어 있습니다.")
    if len(req.content) > _DOWNLOAD_MAX_CHARS:
        raise HTTPException(
            status_code=413,
            detail=f"content 가 {_DOWNLOAD_MAX_CHARS}자를 초과합니다.",
        )

    try:
        data, mime, ext = download_service.generate(req.content, req.format)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("다운로드 변환 오류")
        raise HTTPException(status_code=500, detail=f"파일 생성 실패: {e}")

    base = (req.filename or "ajin-ai-response").strip() or "ajin-ai-response"
    # 파일명 sanitization — 경로 구분자/제어문자 제거
    base = "".join(c for c in base if c.isprintable() and c not in r'\/:*?"<>|')[:80] or "ajin-ai-response"
    full_name = f"{base}{ext}"
    quoted = urllib.parse.quote(full_name)

    return Response(
        content=data,
        media_type=mime,
        headers={
            "Content-Disposition": f"attachment; filename=\"{full_name}\"; filename*=UTF-8''{quoted}",
            "Content-Length": str(len(data)),
        },
    )


# ═══════════════════════════════════════════════════════════════════════
# 부록 K Phase 1 — 부서별 Vision 카드 5개 endpoint
# 각 endpoint 는 invoke_vision_json 헬퍼로 부서별 JSON 스키마 추출.
# 결과는 프론트 카드 컴포넌트가 도메인 UI 로 표시 + 후속 액션 라우팅.
# ═══════════════════════════════════════════════════════════════════════


@router.post("/vision/business-card", dependencies=[Depends(_require_analyzer_enabled)])
async def vision_business_card(
    file: UploadFile = File(...),
    department: str = Form(default=""),
):
    """G6 영업 — 고객 명함 OCR. 결과는 CRM 등록 액션으로 연결."""
    from core.vision_extractor import invoke_vision_json
    image_bytes = await _read_vision_analyzer_upload(file)
    schema = """{
  "name": "이름 (한글)",
  "name_en": "이름 (영문, 없으면 빈 문자열)",
  "company": "회사명",
  "title": "직책",
  "department": "부서",
  "email": "이메일",
  "phone_mobile": "휴대전화",
  "phone_office": "사무실 전화",
  "address": "주소"
}"""
    prompt = "이 명함 이미지에서 정보를 추출하세요. 빈 필드는 빈 문자열로."
    data = invoke_vision_json(prompt, image_bytes, schema_hint=schema)
    return _analyzer_response("business-card", department, data, "vision")


@router.post("/vision/rfq", dependencies=[Depends(_require_analyzer_enabled)])
async def vision_rfq(
    file: UploadFile = File(...),
    department: str = Form(default=""),
):
    """G6 영업 — RFQ 스캔본 분석. 결과는 /draft prefill 로 연결."""
    from core.vision_extractor import invoke_vision_json
    image_bytes = await _read_vision_analyzer_upload(file)
    schema = """{
  "customer": "고객사",
  "contact_person": "담당자",
  "part_number": "부품번호",
  "part_name": "부품명",
  "quantity": "수량 (숫자)",
  "due_date": "납기 (YYYY-MM-DD)",
  "delivery_location": "납품지",
  "special_requirements": ["특이사항 리스트"]
}"""
    prompt = "이 RFQ 문서에서 견적 요청 정보를 추출하세요."
    data = invoke_vision_json(prompt, image_bytes, schema_hint=schema)
    return _analyzer_response("rfq", department, data, "vision")


@router.post("/vision/defect", dependencies=[Depends(_require_analyzer_enabled)])
async def vision_defect(
    file: UploadFile = File(...),
    department: str = Form(default=""),
):
    """G3 생산현장 — 불량품 외관 사진. 결과는 8D Report prefill 로 연결."""
    from core.vision_extractor import invoke_vision_json
    image_bytes = await _read_vision_analyzer_upload(file)
    schema = """{
  "defect_type": "결함 유형 (스크래치/덴트/도장 핀홀/이물/색상 차이/치수 불량/기타)",
  "severity": "심각도 (critical/major/minor)",
  "estimated_location": "결함 위치 추정",
  "possible_causes": ["원인 후보 리스트 (4M 관점)"],
  "containment_actions": ["즉시 격리 조치 후보"],
  "recommended_8d_step": "권장 8D 단계 (D0~D8)"
}"""
    prompt = "이 부품 외관 불량 사진을 분석하세요. 자동차 부품 제조 도메인."
    data = invoke_vision_json(prompt, image_bytes, schema_hint=schema)
    return _analyzer_response("defect", department, data, "vision")


@router.post("/vision/msds-label", dependencies=[Depends(_require_analyzer_enabled)])
async def vision_msds_label(
    file: UploadFile = File(...),
    department: str = Form(default=""),
):
    """G4 안전 — 화학물질 용기 라벨 OCR. 결과는 MSDS 카드 매칭으로 연결."""
    from core.vision_extractor import invoke_vision_json
    image_bytes = await _read_vision_analyzer_upload(file)
    schema = """{
  "product_name": "제품명",
  "manufacturer": "제조사",
  "cas_no": "CAS 번호 (없으면 빈 문자열)",
  "hazard_category": "위험 분류 (인화성/부식성/독성/질식/자극/혼합)",
  "ghs_pictograms": ["GHS 그림문자 (해골/불꽃/감탄부호/환경 등)"],
  "first_aid": "응급조치 핵심 3줄",
  "required_ppe": ["PPE 리스트 (보안경/마스크/장갑/내화학복)"]
}"""
    prompt = "이 화학물질 용기 라벨을 분석하세요. GHS 분류 기준."
    data = invoke_vision_json(prompt, image_bytes, schema_hint=schema)
    return _analyzer_response("msds-label", department, data, "vision")


@router.post("/vision/receipt", dependencies=[Depends(_require_analyzer_enabled)])
async def vision_receipt(
    file: UploadFile = File(...),
    department: str = Form(default=""),
):
    """G7-Finance — 영수증·세금계산서 OCR. 결과는 회계 분개 자동 생성."""
    from core.vision_extractor import invoke_vision_json
    image_bytes = await _read_vision_analyzer_upload(file)
    schema = """{
  "merchant": "사용처/거래처",
  "date": "사용일 (YYYY-MM-DD)",
  "amount_supply": "공급가액 (숫자, 부가세 별도)",
  "amount_vat": "부가세 (숫자)",
  "amount_total": "합계 (숫자)",
  "category": "회계 항목 (식비/교통비/접대비/소모품비/통신비/기타)",
  "purpose": "사용 목적 추정",
  "journal_entry": {
    "debit_account": "차변 계정",
    "credit_account": "대변 계정",
    "summary": "요약 적요"
  }
}"""
    prompt = "이 영수증·세금계산서를 분석하여 회계 분개까지 제안하세요."
    data = invoke_vision_json(prompt, image_bytes, schema_hint=schema)
    return _analyzer_response("receipt", department, data, "vision")


# ═══════════════════════════════════════════════════════════════════════
# 부록 K Phase 2 (5 endpoint) — 사무직 PDF 처리 비중 큼
# ═══════════════════════════════════════════════════════════════════════


@router.post("/document/contract", dependencies=[Depends(_require_analyzer_enabled)])
async def document_contract(
    file: UploadFile = File(...),
    department: str = Form(default=""),
):
    """G9 법무 — 계약서 PDF 분석 + 10 체크리스트."""
    from core.vision_extractor import invoke_vision_json
    data_bytes = await _read_document_analyzer_upload(file)
    schema = """{
  "parties": ["계약 당사자 리스트"],
  "duration": "계약 기간",
  "payment_terms": "대금 지급 조건",
  "warranty": "품질·납기 보증 조항 (위약금 포함)",
  "ip_clause": "지적재산권·NDA 조항 요약",
  "governing_law": "준거법·관할 법원",
  "force_majeure": "불가항력 조항 유무",
  "termination": "해지 사유·통보 기간",
  "defect_warranty": "하자 보수 기간",
  "confidentiality": "비밀유지 의무 기간",
  "risk_flags": ["위험 조항 리스트"],
  "checklist_score": "10 체크리스트 충족 개수 (0~10)"
}"""
    prompt = "이 계약서 PDF 를 분석하세요. 한국 법무 기준."
    data = invoke_vision_json(prompt, data_bytes, schema_hint=schema)
    return _analyzer_response("contract", department, data, "document")


@router.post("/document/resume", dependencies=[Depends(_require_analyzer_enabled)])
async def document_resume(
    file: UploadFile = File(...),
    department: str = Form(default=""),
):
    """G7-HR — 이력서 PDF 분석 + 면접 질문 자동 생성."""
    from core.vision_extractor import invoke_vision_json
    data_bytes = await _read_document_analyzer_upload(file)
    schema = """{
  "name": "지원자",
  "email": "이메일",
  "phone": "연락처",
  "education": [{"school": "학교", "major": "전공", "graduated": "졸업 연도"}],
  "experience": [{"company": "회사", "role": "직책", "years": "근속"}],
  "skills": ["스킬 리스트"],
  "strengths": ["강점 3가지"],
  "concerns": ["우려 사항"],
  "fit_score": "JD 일치도 점수 (0~100)",
  "interview_questions": ["맞춤 면접 질문 5개"]
}"""
    prompt = "이 이력서를 분석하세요. JD 일치도 + 면접 질문 자동 생성."
    data = invoke_vision_json(prompt, data_bytes, schema_hint=schema)
    return _analyzer_response("resume", department, data, "document")


@router.post("/vision/po", dependencies=[Depends(_require_analyzer_enabled)])
async def vision_po(
    file: UploadFile = File(...),
    department: str = Form(default=""),
):
    """G8 구매 — 발주서 OCR + ERP 등록 가이드."""
    from core.vision_extractor import invoke_vision_json
    image_bytes = await _read_vision_analyzer_upload(file)
    schema = """{
  "po_number": "발주번호",
  "vendor": "협력사",
  "buyer": "구매자/부서",
  "issued_date": "발행일",
  "delivery_date": "납기",
  "items": [{"part_number": "부품번호", "name": "부품명", "qty": 0, "unit_price": 0, "total": 0}],
  "total_amount": "총액",
  "payment_terms": "결제 조건",
  "delivery_location": "납품지"
}"""
    prompt = "이 발주서를 분석하세요. 표 형식 부품 리스트 추출."
    data = invoke_vision_json(prompt, image_bytes, schema_hint=schema)
    return _analyzer_response("po", department, data, "vision")


@router.post("/document/financial-statement", dependencies=[Depends(_require_analyzer_enabled)])
async def document_financial_statement(
    file: UploadFile = File(...),
    department: str = Form(default=""),
):
    """G7-Finance — 협력사 재무제표 PDF + 부채비율·위험 신호."""
    from core.vision_extractor import invoke_vision_json
    data_bytes = await _read_document_analyzer_upload(file)
    schema = """{
  "company": "회사명",
  "fiscal_year": "회계 연도",
  "revenue": "매출액 (백만원)",
  "operating_profit": "영업이익",
  "net_profit": "당기순이익",
  "total_assets": "자산총계",
  "total_liabilities": "부채총계",
  "equity": "자본총계",
  "debt_ratio": "부채비율 (%)",
  "current_ratio": "유동비율 (%)",
  "risk_signals": ["위험 신호 리스트 (부채비율 200%+, 매출 감소, 영업손실 등)"],
  "overall_rating": "종합 평가 (A/B/C/D)"
}"""
    prompt = "이 재무제표를 분석하세요. 협력사 리스크 평가 관점."
    data = invoke_vision_json(prompt, data_bytes, schema_hint=schema)
    return _analyzer_response("financial-statement", department, data, "document")


@router.post("/vision/incident", dependencies=[Depends(_require_analyzer_enabled)])
async def vision_incident(
    file: UploadFile = File(...),
    department: str = Form(default=""),
):
    """G4 안전 — 사고 현장 사진 + 위험 요소 + 사고 보고서 prefill."""
    from core.vision_extractor import invoke_vision_json
    image_bytes = await _read_vision_analyzer_upload(file)
    schema = """{
  "scene_type": "현장 유형 (작업장/창고/사무실/실외)",
  "observed_hazards": ["관찰된 위험 요소 리스트"],
  "severity_estimate": "심각도 (critical/major/minor)",
  "potential_4m_causes": {"man": "사람 요인", "machine": "설비", "material": "재료", "method": "방법"},
  "immediate_actions": ["즉시 조치"],
  "report_summary": "사고 보고서 요약 (3~5줄)",
  "required_ppe_missing": ["미착용 PPE 추정 리스트"]
}"""
    prompt = "이 사고 현장 사진을 분석하세요. 4M + PPE + 보고서 prefill."
    data = invoke_vision_json(prompt, image_bytes, schema_hint=schema)
    return _analyzer_response("incident", department, data, "vision")


# ═══════════════════════════════════════════════════════════════════════
# 부록 K Phase 3 (6 endpoint) — 나머지 부서 카드
# ═══════════════════════════════════════════════════════════════════════


@router.post("/vision/cad-verify", dependencies=[Depends(_require_analyzer_enabled)])
async def vision_cad_verify(
    file: UploadFile = File(...),
    department: str = Form(default=""),
):
    """G5 R&D — CAD 도면 표준 검증."""
    from core.vision_extractor import invoke_vision_json
    image_bytes = await _read_vision_analyzer_upload(file)
    schema = """{
  "drawing_number": "도면번호",
  "revision": "리비전",
  "title_block_ok": "표제란 양식 일치 (true/false)",
  "dimension_unit": "단위 (mm 권장)",
  "tolerance_spec": "공차 표기 (KS B ISO 2768-m 권장)",
  "material_spec": "재질 표기",
  "compliance_score": "표준 적합도 점수 (0~100)",
  "violations": ["표준 위반 항목 리스트"]
}"""
    prompt = "이 CAD 도면의 사내 표준 적합도를 검사하세요."
    data = invoke_vision_json(prompt, image_bytes, schema_hint=schema)
    return _analyzer_response("cad-verify", department, data, "vision")


@router.post("/vision/5s", dependencies=[Depends(_require_analyzer_enabled)])
async def vision_5s(
    file: UploadFile = File(...),
    department: str = Form(default=""),
):
    """G3 생산현장 — 작업장 5S 점수."""
    from core.vision_extractor import invoke_vision_json
    image_bytes = await _read_vision_analyzer_upload(file)
    schema = """{
  "scores": {"seiri": 0, "seiton": 0, "seiso": 0, "seiketsu": 0, "shitsuke": 0},
  "total_score": "5S 총점 (0~100)",
  "strengths": ["잘 된 점"],
  "improvements": ["개선 필요"],
  "priority_actions": ["우선 조치 3개"]
}"""
    prompt = "이 작업장 사진의 5S(정리·정돈·청소·청결·습관) 점수를 0~20 으로 각각 평가하세요."
    data = invoke_vision_json(prompt, image_bytes, schema_hint=schema)
    return _analyzer_response("5s", department, data, "vision")


@router.post("/vision/error-log", dependencies=[Depends(_require_analyzer_enabled)])
async def vision_error_log(
    file: UploadFile = File(...),
    department: str = Form(default=""),
):
    """G7-IT — 시스템 에러 로그 스크린샷 + 원인·해결 가이드."""
    from core.vision_extractor import invoke_vision_json
    image_bytes = await _read_vision_analyzer_upload(file)
    schema = """{
  "error_message": "에러 메시지",
  "stack_excerpt": "스택 트레이스 핵심 (3~5줄)",
  "likely_cause": "원인 추정",
  "category": "분류 (네트워크/권한/메모리/DB/설정/코드 버그)",
  "fix_suggestions": ["해결 방안 리스트"],
  "related_kb_keywords": ["사내 KB 검색용 키워드"]
}"""
    prompt = "이 에러 화면을 분석하세요. 시스템 운영자 관점."
    data = invoke_vision_json(prompt, image_bytes, schema_hint=schema)
    return _analyzer_response("error-log", department, data, "vision")


@router.post("/document/esg", dependencies=[Depends(_require_analyzer_enabled)])
async def document_esg(
    file: UploadFile = File(...),
    department: str = Form(default=""),
):
    """G9 ESG — 자사/타사 ESG 보고서 PDF 핵심 지표 추출."""
    from core.vision_extractor import invoke_vision_json
    data_bytes = await _read_document_analyzer_upload(file)
    schema = """{
  "company": "회사명",
  "report_year": "보고 연도",
  "environment": {
    "carbon_emission_t": "탄소배출량 (톤CO2)",
    "water_use": "용수 사용량",
    "renewable_energy_pct": "재생에너지 비율 (%)"
  },
  "social": {
    "employees": "임직원 수",
    "safety_accidents": "산재 건수",
    "diversity_pct": "여성 임원 비율 (%)"
  },
  "governance": {
    "board_independence_pct": "사외이사 비율 (%)",
    "audit_findings": "감사 지적 사항 수"
  },
  "rating": "ESG 등급 (KCGS/MSCI 기준)"
}"""
    prompt = "이 ESG 보고서를 분석하세요. 환경·사회·지배구조 3축 핵심 지표."
    data = invoke_vision_json(prompt, data_bytes, schema_hint=schema)
    return _analyzer_response("esg", department, data, "document")


@router.post("/vision/inventory-receive", dependencies=[Depends(_require_analyzer_enabled)])
async def vision_inventory_receive(
    file: UploadFile = File(...),
    department: str = Form(default=""),
):
    """G8 자재 — 자재 입고 검수 (포장 박스 사진 → 수량·상태)."""
    from core.vision_extractor import invoke_vision_json
    image_bytes = await _read_vision_analyzer_upload(file)
    schema = """{
  "vendor": "협력사 (라벨 OCR)",
  "part_number": "부품번호",
  "package_count": "박스 수량",
  "package_condition": "포장 상태 (정상/파손/오염)",
  "visible_defects": ["외관 결함 리스트"],
  "ok_to_receive": "입고 가능 여부 (true/false)",
  "next_action": "다음 조치 (입고/반품/품질 격리)"
}"""
    prompt = "이 입고 자재 박스 사진을 검수하세요. 1차 자동 검수 후 인간 2차 확인."
    data = invoke_vision_json(prompt, image_bytes, schema_hint=schema)
    return _analyzer_response("inventory-receive", department, data, "vision")


# ═══════════════════════════════════════════════════════════════════════
# v4.7 C-4 — 게이미피케이션 endpoints
#   GET  /onboarding/badges/me                — 본인 보유 배지 + 전체 정의
#   GET  /onboarding/leaderboard/{dept}       — 부서 주간 리더보드
#   POST /onboarding/sop/progress             — SOP 단계 완료 영속화
#   POST /onboarding/quiz/result              — 퀴즈 결과 영속화 + 배지 평가
# ═══════════════════════════════════════════════════════════════════════


class _SopProgressBody(BaseModel):
    sop_id: str
    step_number: int
    completed_at: str = ""


class _QuizResultBody(BaseModel):
    is_correct: bool
    category: str = "sop"
    difficulty: str = "basic"
    sop_id: str = ""
    source_id: str = ""
    related_step: int = 0


@router.get("/badges/me")
async def get_my_badges(user=Depends(get_current_user)):
    """본인 보유 배지 + 전체 배지 정의 + 부서 리더보드 본인 순위.

    비인증 시 빈 응답.
    """
    if user is None:
        return {"earned": [], "definitions": [], "rank": None}
    from features.onboarding import gamification_db as gdb
    from features.onboarding.gamification import BADGE_DEFS, user_rank_in_dept

    uid = getattr(user, "employee_id", "") or getattr(user, "username", "") or "anonymous"
    dept = getattr(user, "department", "") or ""

    earned = gdb.get_earned_badges(uid)
    earned_ids = {b["badge_id"] for b in earned}
    definitions = [
        {
            "badge_id": bid,
            "category": bdef.category,
            "tier": bdef.tier,
            "earned": bid in earned_ids,
        }
        for bid, bdef in BADGE_DEFS.items()
    ]
    rank = user_rank_in_dept(uid, dept) if dept else None
    return {
        "earned": earned,
        "definitions": definitions,
        "rank": rank,
        "department": dept,
    }


@router.get("/leaderboard/{dept}")
async def get_leaderboard(dept: str, period: str = "week", user=Depends(get_current_user)):
    """부서 주간 리더보드. 부서 인원 < 3 이면 visible=false."""
    from features.onboarding.gamification import compute_dept_leaderboard

    return compute_dept_leaderboard(dept, period=period)


@router.post("/sop/progress")
async def post_sop_progress(body: _SopProgressBody, user=Depends(get_current_user)):
    """SOP 단계 1개 완료. user_daily_activity.sop_steps_completed +1 + 배지 평가."""
    if user is None:
        # 비인증도 허용 (DEMO 환경) — anonymous 사용자
        uid = "anonymous"
        dept = ""
    else:
        uid = getattr(user, "employee_id", "") or getattr(user, "username", "") or "anonymous"
        dept = getattr(user, "department", "") or ""

    from features.onboarding import gamification_db as gdb
    from features.onboarding.gamification import evaluate_badges

    gdb.record_sop_step(uid, body.sop_id, body.step_number, body.completed_at)
    gdb.upsert_daily(uid, field="sop_steps_completed", delta=1, user_department=dept)
    newly = evaluate_badges(uid, user_department=dept, event_hint="sop")
    return {"ok": True, "newly_earned": newly}


@router.post("/quiz/result")
async def post_quiz_result(body: _QuizResultBody, user=Depends(get_current_user)):
    """퀴즈 정/오답 결과 영속화 + 배지 평가."""
    if user is None:
        uid = "anonymous"
        dept = ""
    else:
        uid = getattr(user, "employee_id", "") or getattr(user, "username", "") or "anonymous"
        dept = getattr(user, "department", "") or ""

    from features.onboarding import gamification_db as gdb
    from features.onboarding.gamification import evaluate_badges
    from features.onboarding.quiz_engine import QuizQuestion, record_quiz_result

    # 가짜 QuizQuestion 페이로드 (record_quiz_result 의 시그니처 재활용)
    fake_q = QuizQuestion(
        question="",
        options=[],
        correct_index=0,
        explanation="",
        category=body.category,
        difficulty=body.difficulty,
        source_id=body.source_id or body.sop_id,
        related_step=body.related_step,
    )
    record_quiz_result(uid, fake_q, body.is_correct, user_department=dept)
    # evaluate_badges 는 record_quiz_result 내부에서 호출되지만 newly 반환을 위해 한 번 더
    newly = evaluate_badges(uid, user_department=dept, event_hint="quiz")
    return {"ok": True, "newly_earned": newly}


@router.post("/vision/certificate", dependencies=[Depends(_require_analyzer_enabled)])
async def vision_certificate(
    file: UploadFile = File(...),
    department: str = Form(default=""),
):
    """G10 교육 — 외부 교육 수료증 OCR + HRD 등록 가이드."""
    from core.vision_extractor import invoke_vision_json
    image_bytes = await _read_vision_analyzer_upload(file)
    schema = """{
  "course_name": "강좌명",
  "institution": "발급 기관",
  "completion_date": "이수일 (YYYY-MM-DD)",
  "hours": "이수 시간",
  "certificate_no": "수료증 번호",
  "recipient": "수료자",
  "category": "분류 (안전/품질/기술/경영/외국어/기타)",
  "hrd_eligible": "HRD 시스템 등록 적격 여부 (true/false)"
}"""
    prompt = "이 교육 수료증을 분석하세요. HRD 시스템 자동 등록 가이드."
    data = invoke_vision_json(prompt, image_bytes, schema_hint=schema)
    return _analyzer_response("certificate", department, data, "vision")
