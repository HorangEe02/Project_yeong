"""검색 라우터."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from backend.auth_middleware import log_api_access
from backend.dependencies import get_current_user, get_searcher
from backend.schemas.search import SearchRequest, SearchResponse, SearchResultItem
from backend.sse import create_sse_response, sse_from_sync_generator
from core.data_lineage import normalize_data_class
from core.security import sanitize_llm_input

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/search",
    tags=["search"],
    dependencies=[Depends(get_current_user)],
)


_SENSITIVE_METADATA_KEYS = {
    "absolute_path",
    "file_path",
    "full_path",
    "local_path",
    "object_path",
    "path",
    "raw_path",
    "source_path",
    "storage_path",
}


def _employee_id_of(user: Any) -> str:
    """Return a stable employee id from a user context.

    Args:
        user: Authenticated user context.

    Returns:
        str: Employee id or username fallback.
    """
    return str(
        getattr(user, "employee_id", "")
        or getattr(user, "user_id", "")
        or getattr(user, "username", "")
        or ""
    )


def _role_level_of(user: Any) -> int:
    """Resolve RBAC role level from user context.

    Args:
        user: Authenticated user context.

    Returns:
        int: Numeric role level. Unknown roles fail closed to 0.
    """
    raw = getattr(user, "role_level", None)
    if raw is not None:
        try:
            return int(raw)
        except (TypeError, ValueError):
            return 0
    try:
        from core.auth.rbac import get_role_level

        return int(get_role_level(str(getattr(user, "role", "") or "")))
    except Exception:
        return 0


def _search_visibility(user: Any, target_department: str | None) -> str:
    """Return search result visibility for the current user.

    Args:
        user: Authenticated user context.
        target_department: Department owning the result.

    Returns:
        str: ``full`` for same department or L4+, otherwise ``partial``.
    """
    if _role_level_of(user) >= 4:
        return "full"
    if target_department and str(getattr(user, "department", "") or "") == target_department:
        return "full"
    return "partial"


def _source_value(source: Any, key: str, default: Any = "") -> Any:
    """Read a value from either a dict or object result.

    Args:
        source: Dict-like or attribute-style source.
        key: Field name.
        default: Value used when the field is missing.

    Returns:
        Any: Source value or default.
    """
    if isinstance(source, dict):
        return source.get(key, default)
    return getattr(source, key, default)


def _lineage_metadata(source: Any, metadata: dict[str, Any] | None) -> dict[str, Any]:
    """Build response metadata with consistent source labeling.

    Args:
        source: Search result source object.
        metadata: Existing result metadata.

    Returns:
        dict[str, Any]: Metadata with lineage defaults filled in.
    """
    clean = dict(metadata or {})
    data_class = clean.get("data_class") or _source_value(source, "data_class", "unknown")
    source_system = clean.get("source_system") or _source_value(source, "source_system", "unknown")
    source_label = clean.get("source_label") or _source_value(source, "source_label", "")
    clean["data_class"] = normalize_data_class(str(data_class or "unknown"))
    clean["source_system"] = str(source_system or "unknown")
    clean["source_label"] = str(source_label or "")
    return clean


def _metadata_department(source: Any, metadata: dict[str, Any]) -> str:
    """Extract a result-owning department from metadata or source.

    Args:
        source: Search result source object.
        metadata: Normalized metadata.

    Returns:
        str: Department name or empty string.
    """
    return str(
        metadata.get("department")
        or metadata.get("dept")
        or _source_value(source, "department", "")
        or ""
    )


def _is_sensitive_without_context(metadata: dict[str, Any], department: str) -> bool:
    """Return whether a result lacks enough ownership context to expose.

    Args:
        metadata: Result metadata.
        department: Owning department.

    Returns:
        bool: True for explicitly sensitive records with no department context.
    """
    if department:
        return False
    classification = str(metadata.get("classification") or "").lower()
    return bool(metadata.get("sensitive")) or classification in {"confidential", "secret"}


def _apply_metadata_visibility(metadata: dict[str, Any], visibility: str) -> dict[str, Any]:
    """Remove internal location metadata unless the viewer has full visibility.

    Args:
        metadata: Metadata to filter.
        visibility: ``full`` or ``partial``.

    Returns:
        dict[str, Any]: Filtered metadata.
    """
    clean = dict(metadata)
    if visibility != "full":
        for key in _SENSITIVE_METADATA_KEYS:
            clean.pop(key, None)
    clean["visibility"] = visibility
    return clean


def _search_item_from_result(source: Any, user: Any) -> SearchResultItem | None:
    """Convert one backend search result into a visibility-filtered response item.

    Args:
        source: Search result object or dict.
        user: Authenticated user context.

    Returns:
        SearchResultItem | None: Filtered response item, or None if hidden.
    """
    metadata = _lineage_metadata(source, _source_value(source, "metadata", {}) or {})
    department = _metadata_department(source, metadata)
    visibility = _search_visibility(user, department)
    if visibility != "full" and _is_sensitive_without_context(metadata, department):
        return None
    metadata = _apply_metadata_visibility(metadata, visibility)
    return SearchResultItem(
        doc_id=str(_source_value(source, "doc_id", "")),
        title=str(_source_value(source, "title", "")),
        doc_type=str(_source_value(source, "doc_type", "")),
        part_name=str(_source_value(source, "part_name", "")),
        content=str(_source_value(source, "content", "")),
        score=float(_source_value(source, "score", 0.0) or 0.0),
        metadata=metadata,
    )


def _audit_search_event(
    *,
    endpoint: str,
    method: str,
    user: Any,
    query: str = "",
    status_code: int = 200,
    result_count: int | None = None,
    extra: str = "",
) -> None:
    """Write a search audit row without storing raw query text.

    Args:
        endpoint: API endpoint path.
        method: HTTP method.
        user: Authenticated user context.
        query: Raw query used only for length accounting.
        status_code: Response status code.
        result_count: Number of visible results when known.
        extra: Additional non-sensitive summary text.
    """
    parts = [f"query_len={len(query or '')}"]
    if extra:
        parts.append(extra[:120])
    log_api_access(
        endpoint=endpoint,
        method=method,
        status_code=status_code,
        detail=", ".join(parts),
        user=user,
        intent=endpoint.rsplit("/", 1)[-1],
        result_count=result_count,
    )


@router.post("/documents", response_model=SearchResponse)
async def search_documents(
    req: SearchRequest,
    user=Depends(get_current_user),
    searcher=Depends(get_searcher),
):
    """하이브리드 검색 (BM25 + Vector + RRF)."""
    if searcher is None:
        _audit_search_event(
            endpoint="/api/search/documents",
            method="POST",
            user=user,
            query=req.query,
            status_code=503,
            result_count=0,
            extra="feature_disabled",
        )
        raise HTTPException(
            status_code=503,
            detail={
                "error": "feature_disabled",
                "feature": "search.documents",
                "reason": "HybridSearcher is not available",
            },
        )
    try:
        results = searcher.search(
            query=req.query,
            k=req.k,
            doc_type_filter=req.doc_type_filter,
            part_name_filter=req.part_name_filter,
            date_from=req.date_from,
            date_to=req.date_to,
        )

        # v4.x — CRAG retrieval evaluator (Phase 1 PR2). raw results 기반 verdict.
        # visibility 필터 전에 평가 — top-1 rerank_score 그대로 사용.
        # docs/RAG_ENHANCEMENT_PLAN.md §2.2 / config.CRAG_*.
        from config import CRAG_ENABLED

        crag_verdict = "correct"
        crag_top_score = 0.0
        crag_rationale = ""
        if CRAG_ENABLED:
            from features.search.crag_evaluator import evaluate_retrieval

            crag = evaluate_retrieval(results)
            crag_verdict = crag.verdict
            crag_top_score = crag.top_score
            crag_rationale = crag.rationale

        items = []
        for result in results:
            item = _search_item_from_result(result, user)
            if item is not None:
                items.append(item)
        _audit_search_event(
            endpoint="/api/search/documents",
            method="POST",
            user=user,
            query=req.query,
            result_count=len(items),
            extra=f"crag={crag_verdict}({crag_top_score:.2f})",
        )
        return SearchResponse(
            results=items,
            total=len(items),
            query=req.query,
            crag_verdict=crag_verdict,
            crag_top_score=crag_top_score,
            crag_rationale=crag_rationale,
        )
    except HTTPException:
        raise
    except Exception as e:
        _audit_search_event(
            endpoint="/api/search/documents",
            method="POST",
            user=user,
            query=req.query,
            status_code=500,
            result_count=0,
        )
        logger.error("search_documents error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


# ──────────────────────────────────────────────────────────────────────────
# v4.7 Sprint 2 P0 (축 ②) — Intent → Palette auto-category
# ──────────────────────────────────────────────────────────────────────────


class IntentRequest(BaseModel):
    """`/search/intent` 요청 body — 분류할 단일 쿼리."""

    query: str = Field(..., min_length=1, max_length=512)


class IntentAlternative(BaseModel):
    intent: str
    confidence: float


class IntentResponse(BaseModel):
    """프론트엔드 store/search.IntentResult 와 1:1."""

    intent: str
    confidence: float = 0.0
    suggested_category: str | None = None
    alternatives: list[IntentAlternative] = Field(default_factory=list)


@router.post("/intent", response_model=IntentResponse)
def classify_palette_intent(req: IntentRequest):
    """팔레트용 의도 분류. 10 카테고리 중 하나 + confidence(0~1)."""
    try:
        from features.search.palette_intent import classify_intent_with_overrides

        result = classify_intent_with_overrides(req.query)
        return IntentResponse(
            intent=result.intent,
            confidence=result.confidence,
            suggested_category=result.suggested_category,
            alternatives=[IntentAlternative(**a) for a in result.alternatives],
        )
    except Exception as e:
        logger.error("intent classify error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="intent classification failed")


# ──────────────────────────────────────────────────────────────────────────
# v4.7 Sprint 2 P0 (축 ④) — Vision OCR + 검색 + Capabilities
# ──────────────────────────────────────────────────────────────────────────


class SearchCapabilities(BaseModel):
    vision_enabled: bool
    intent_classifier: bool


@router.get("/capabilities", response_model=SearchCapabilities)
def get_search_capabilities():
    """현재 검색 모듈에서 활성화된 기능 토글 (프론트 UI 토글용)."""
    import os

    return SearchCapabilities(
        vision_enabled=bool(os.environ.get("GEMINI_API_KEY")),
        intent_classifier=True,
    )


class VisionSearchResponse(BaseModel):
    ocr_text: str = ""
    search_results: list[SearchResultItem] = Field(default_factory=list)


@router.post("/vision-query", response_model=VisionSearchResponse)
async def vision_query_search(
    image: UploadFile = File(...),
    user=Depends(get_current_user),
    searcher=Depends(get_searcher),
):
    """이미지 첨부 → Gemini Vision OCR → OCR 텍스트로 RRF 검색 (축 ④).

    GEMINI_API_KEY 미설정 시 403 + body `{error: "vision_disabled"}`.
    """
    import os

    if not os.environ.get("GEMINI_API_KEY"):
        _audit_search_event(
            endpoint="/api/search/vision-query",
            method="POST",
            user=user,
            status_code=403,
            result_count=0,
            extra="vision_disabled",
        )
        raise HTTPException(status_code=403, detail={"error": "vision_disabled"})

    image_bytes = await image.read()
    try:
        from features.search.vision_query import vision_search

        ocr_text, raw_results = vision_search(image_bytes, searcher=searcher)
    except RuntimeError as e:
        # vision_query 가 키 없거나 외부 호출 실패 시 RuntimeError 로 표준화.
        if str(e) == "vision_disabled":
            _audit_search_event(
                endpoint="/api/search/vision-query",
                method="POST",
                user=user,
                status_code=403,
                result_count=0,
                extra="vision_disabled",
            )
            raise HTTPException(status_code=403, detail={"error": "vision_disabled"}) from e
        _audit_search_event(
            endpoint="/api/search/vision-query",
            method="POST",
            user=user,
            status_code=502,
            result_count=0,
            extra="vision_failed",
        )
        logger.error("vision_query error: %s", e, exc_info=True)
        raise HTTPException(status_code=502, detail={"error": "vision_failed"}) from e
    except Exception as e:
        _audit_search_event(
            endpoint="/api/search/vision-query",
            method="POST",
            user=user,
            status_code=502,
            result_count=0,
            extra="vision_failed",
        )
        logger.error("vision_query error: %s", e, exc_info=True)
        raise HTTPException(status_code=502, detail={"error": "vision_failed"}) from e

    items = []
    for result in raw_results:
        item = _search_item_from_result(result, user)
        if item is not None:
            items.append(item)
    _audit_search_event(
        endpoint="/api/search/vision-query",
        method="POST",
        user=user,
        query=ocr_text,
        result_count=len(items),
    )
    return VisionSearchResponse(ocr_text=ocr_text, search_results=items)


@router.post("/summarize")
async def summarize_results(req: SearchRequest, user=Depends(get_current_user)):
    """검색 결과를 LLM으로 요약한다 (SSE 스트리밍)."""
    from core.llm_client import auto_select_model, stream_generate

    model = auto_select_model("search")
    prompt = f"다음 검색 결과를 바탕으로 '{sanitize_llm_input(req.query)}'에 대해 요약해주세요."
    _audit_search_event(
        endpoint="/api/search/summarize",
        method="POST",
        user=user,
        query=req.query,
        result_count=0,
    )

    return create_sse_response(
        sse_from_sync_generator(
            stream_generate,
            prompt=prompt,
            model=model,
            feature="search",
        )
    )


# ──────────────────────────────────────────────────────────────────────────
# P2 (Weakness #3) — 도면 메타 검색 + Vision 캡션 인덱스 PoC
# ──────────────────────────────────────────────────────────────────────────


class DrawingItem(BaseModel):
    """도면 메타 1건. drawing_search SQLite 컬럼 1:1."""

    id: int = 0
    drawing_number: str = ""
    part_number: str = ""
    part_name: str = ""
    revision: str = ""
    equipment_type: str = ""
    material: str = ""
    process_type: str = ""
    department: str = ""
    file_path: str = ""
    description: str = ""
    bom_info: str = ""
    source_type: str = "drawing"
    data_class: str = "unknown"
    source_system: str = "unknown"
    source_label: str = ""
    visibility: str = "partial"


class DrawingListResponse(BaseModel):
    items: list[DrawingItem]
    total: int


class DrawingCaptionItem(BaseModel):
    id: int = 0
    caption: str = ""
    keywords: str = ""
    department: str = ""
    uploader: str = ""
    file_name: str = ""
    image_size: int = 0
    source_model: str = ""
    created_at: str = ""
    source_type: str = "caption"
    data_class: str = "unknown"
    source_system: str = "drawing_caption_index"
    source_label: str = ""
    visibility: str = "partial"


class DrawingCaptionListResponse(BaseModel):
    items: list[DrawingCaptionItem]
    total: int


class AddCaptionRequest(BaseModel):
    caption: str = Field(..., min_length=2)
    keywords: str = ""
    department: str = ""
    uploader: str = ""
    file_name: str = ""
    image_size: int = 0
    source_model: str = ""


class AddCaptionResponse(BaseModel):
    id: int
    total: int


def _drawing_item_from_row(row: dict, user: Any) -> DrawingItem:
    """Build a visibility-filtered drawing response item.

    Args:
        row: Drawing metadata row.
        user: Authenticated user context.

    Returns:
        DrawingItem: Response item with internal paths hidden when partial.
    """
    data = dict(row)
    visibility = _search_visibility(user, str(data.get("department") or ""))
    data["data_class"] = normalize_data_class(str(data.get("data_class") or "unknown"))
    data["source_system"] = str(data.get("source_system") or "unknown")
    data["source_label"] = str(data.get("source_label") or "")
    data["visibility"] = visibility
    if visibility != "full":
        data["file_path"] = ""
        data["bom_info"] = ""
    return DrawingItem(**{**data, "source_type": "drawing"})


def _caption_item_from_row(row: dict, user: Any) -> DrawingCaptionItem:
    """Build a visibility-filtered drawing caption response item.

    Args:
        row: Drawing caption row.
        user: Authenticated user context.

    Returns:
        DrawingCaptionItem: Response item with uploader/file details hidden when partial.
    """
    data = dict(row)
    visibility = _search_visibility(user, str(data.get("department") or ""))
    data["data_class"] = normalize_data_class(str(data.get("data_class") or "unknown"))
    data["source_system"] = str(data.get("source_system") or "drawing_caption_index")
    data["source_label"] = str(data.get("source_label") or data.get("source_model") or "")
    data["visibility"] = visibility
    if visibility != "full":
        data["file_name"] = ""
        data["uploader"] = ""
    return DrawingCaptionItem(**{**data, "source_type": "caption"})


@router.get("/drawings", response_model=DrawingListResponse)
def list_drawings(
    q: str = Query("", description="도면번호/부품번호/키워드 통합 검색"),
    equipment_type: str = "",
    department: str = "",
    user=Depends(get_current_user),
):
    """도면 메타 검색. q 가 비어 있으면 전체 키워드 검색(필터만)."""
    try:
        from features.equipment.drawing_search import (
            search_by_keyword,
            search_by_number,
        )

        results: list[dict] = []
        seen_ids: set[int] = set()
        if q:
            for r in search_by_number(q):
                rid = int(r.get("id", 0))
                if rid in seen_ids:
                    continue
                seen_ids.add(rid)
                results.append(r)
        for r in search_by_keyword(q, equipment_type=equipment_type, department=department):
            rid = int(r.get("id", 0))
            if rid in seen_ids:
                continue
            seen_ids.add(rid)
            results.append(r)

        items = [_drawing_item_from_row(row, user) for row in results]
        _audit_search_event(
            endpoint="/api/search/drawings",
            method="GET",
            user=user,
            query=q,
            result_count=len(items),
            extra=f"dept_filter={bool(department)}",
        )
        return DrawingListResponse(items=items, total=len(items))
    except Exception as e:
        _audit_search_event(
            endpoint="/api/search/drawings",
            method="GET",
            user=user,
            query=q,
            status_code=500,
            result_count=0,
        )
        logger.error("list_drawings error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="도면 검색 실패")


@router.get("/drawings/captions", response_model=DrawingCaptionListResponse)
def list_drawing_captions(
    q: str = Query("", description="캡션 텍스트/키워드 검색"),
    department: str = "",
    limit: int = 20,
    user=Depends(get_current_user),
):
    """Vision 캡션 인덱스 검색 (PoC)."""
    try:
        from features.equipment.drawing_captions import search_captions

        rows = search_captions(query=q, department=department, limit=limit)
        items = [_caption_item_from_row(row, user) for row in rows]
        _audit_search_event(
            endpoint="/api/search/drawings/captions",
            method="GET",
            user=user,
            query=q,
            result_count=len(items),
            extra=f"dept_filter={bool(department)}",
        )
        return DrawingCaptionListResponse(items=items, total=len(items))
    except Exception as e:
        _audit_search_event(
            endpoint="/api/search/drawings/captions",
            method="GET",
            user=user,
            query=q,
            status_code=500,
            result_count=0,
        )
        logger.error("list_drawing_captions error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="캡션 검색 실패")


@router.post("/drawings/captions", response_model=AddCaptionResponse)
def add_drawing_caption(req: AddCaptionRequest, user=Depends(get_current_user)):
    """Vision LLM 캡션을 인덱스에 저장. 향후 ChromaDB 임베딩 통합 예정."""
    try:
        from features.equipment.drawing_captions import add_caption, count_captions

        new_id = add_caption(
            caption=req.caption,
            keywords=req.keywords,
            department=req.department,
            uploader=req.uploader or _employee_id_of(user),
            file_name=req.file_name,
            image_size=req.image_size,
            source_model=req.source_model,
        )
        total = count_captions()
        _audit_search_event(
            endpoint="/api/search/drawings/captions",
            method="POST",
            user=user,
            query=req.caption,
            result_count=1,
            extra=f"total={total}",
        )
        return AddCaptionResponse(id=new_id, total=total)
    except Exception as e:
        _audit_search_event(
            endpoint="/api/search/drawings/captions",
            method="POST",
            user=user,
            query=req.caption,
            status_code=500,
            result_count=0,
        )
        logger.error("add_drawing_caption error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="캡션 저장 실패")


@router.get("/drawings/{drawing_id}", response_model=DrawingItem)
def get_drawing_detail(drawing_id: int, user=Depends(get_current_user)):
    """도면 상세."""
    try:
        from features.equipment.drawing_search import get_drawing

        row = get_drawing(drawing_id)
        if not row:
            raise HTTPException(status_code=404, detail="도면을 찾을 수 없습니다.")
        clean = {k: v for k, v in row.items() if k != "bom"}
        item = _drawing_item_from_row(clean, user)
        _audit_search_event(
            endpoint="/api/search/drawings/{drawing_id}",
            method="GET",
            user=user,
            result_count=1,
            extra=f"drawing_id={drawing_id}",
        )
        return item
    except HTTPException:
        raise
    except Exception as e:
        _audit_search_event(
            endpoint="/api/search/drawings/{drawing_id}",
            method="GET",
            user=user,
            status_code=500,
            result_count=0,
            extra=f"drawing_id={drawing_id}",
        )
        logger.error("get_drawing error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="도면 상세 조회 실패")
