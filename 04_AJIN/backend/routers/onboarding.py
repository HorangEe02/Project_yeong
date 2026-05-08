"""온보딩 채팅 라우터.

v3.0: 선택적 사용자 추적 — 토큰이 있으면 부서 정보를 LLM에 주입
v4.0 (Phase 2): LLMRouter (Gemini → Ollama → LM Studio) 폴백 체인 + Circuit Breaker + 메트릭
"""

import base64
import json
import logging
import urllib.parse

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
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
)
from backend.dependencies import get_optional_user
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

router = APIRouter(prefix="/onboarding", tags=["onboarding"])

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
    - 비인증: req.department 그대로 사용 (DEMO 환경 호환).
    - L<3 (EMPLOYEE): 자기 부서 강제. req.department 가 다르면 경고 로그 + 무시.
    - L=3 (MANAGER): 같은 본부 내 부서만 허용. 타 본부 시도 시 자기 부서 fallback + 경고.
    - L>=4 (EXECUTIVE/SYS): 전사 자유 변경.
    """
    if user is None:
        return (req_dept or "").strip() or _DEFAULT_DEPT

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


@router.post("/chat")
async def onboarding_chat(
    req: OnboardingChatRequest,
    request: Request,
    user=Depends(get_optional_user),
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

{f'[이전 대화]{chr(10)}{history_text}' if history_text else ''}
{file_ctx}{action_context}

[질문] {sanitize_llm_input(req.query)}

한국어로 친절하게 답변하세요. 아진산업 자동차 부품 제조 맥락에서 설명하세요."""

    # 라우터 history 는 {role, content} 형태 — Pydantic 모델은 dict 변환
    history_payload = [{"role": m.role, "content": m.content} for m in (req.history or [])]

    # Day 5 Phase 5 — UI ModelSelect 가 force_provider=[provider, model] 로 강제 가능.
    force = None
    if req.force_provider and len(req.force_provider) == 2:
        force = (req.force_provider[0], req.force_provider[1])

    async def event_stream():
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

        try:
            async for ev in _llm_router.stream(
                prompt=prompt,
                mode=LLMMode.CHAT_KOREAN,
                history=history_payload,
                force_provider=force,
            ):
                yield {"data": json.dumps(ev, ensure_ascii=False, default=str)}
        except Exception as e:
            logger.exception("온보딩 채팅 스트리밍 오류")
            yield {"data": json.dumps({"type": "error", "content": str(e), "metadata": None})}

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
    user=Depends(get_optional_user),
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
        # 비인증 / 익명 — L1 (신입) 으로 취급해 보수적 노출
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
async def match_scenario(req: ScenarioMatchRequest, user=Depends(get_optional_user)):
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
