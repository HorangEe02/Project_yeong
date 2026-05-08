"""검색 라우터."""

import logging

from fastapi import APIRouter, Depends, HTTPException

from backend.dependencies import get_searcher
from backend.schemas.search import SearchRequest, SearchResponse, SearchResultItem
from backend.sse import create_sse_response, sse_from_sync_generator
from core.security import sanitize_llm_input

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["search"])


@router.post("/documents", response_model=SearchResponse)
async def search_documents(req: SearchRequest, searcher=Depends(get_searcher)):
    """하이브리드 검색 (BM25 + Vector + RRF)."""
    try:
        results = searcher.search(
            query=req.query,
            k=req.k,
            doc_type_filter=req.doc_type_filter,
            part_name_filter=req.part_name_filter,
            date_from=req.date_from,
            date_to=req.date_to,
        )
        items = [
            SearchResultItem(
                doc_id=getattr(r, "doc_id", ""),
                title=getattr(r, "title", ""),
                doc_type=getattr(r, "doc_type", ""),
                part_name=getattr(r, "part_name", ""),
                content=getattr(r, "content", ""),
                score=getattr(r, "score", 0.0),
                metadata=getattr(r, "metadata", {}),
            )
            for r in results
        ]
        return SearchResponse(results=items, total=len(items), query=req.query)
    except Exception as e:
        logger.error("search_documents error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/summarize")
async def summarize_results(req: SearchRequest):
    """검색 결과를 LLM으로 요약한다 (SSE 스트리밍)."""
    from core.llm_client import auto_select_model, stream_generate

    model = auto_select_model("search")
    prompt = f"다음 검색 결과를 바탕으로 '{sanitize_llm_input(req.query)}'에 대해 요약해주세요."

    return create_sse_response(
        sse_from_sync_generator(
            stream_generate,
            prompt=prompt,
            model=model,
            feature="search",
        )
    )
