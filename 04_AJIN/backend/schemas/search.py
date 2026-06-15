"""검색 관련 Pydantic 스키마."""

from typing import Literal

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    # v4.x — query optional: 검색어 없이 doc_type/part_name 필터만으로 결과 노출.
    query: str = ""
    k: int = Field(default=5, ge=1, le=20)
    doc_type_filter: str | None = None
    part_name_filter: str | None = None
    date_from: str | None = None
    date_to: str | None = None


class SearchResultItem(BaseModel):
    doc_id: str = ""
    title: str = ""
    doc_type: str = ""
    part_name: str = ""
    content: str = ""
    score: float = 0.0
    metadata: dict = Field(default_factory=dict)


# v4.x — CRAG retrieval evaluator (Phase 1 PR2).
# docs/RAG_ENHANCEMENT_PLAN.md §2.2 — Yan et al. 2024, arXiv:2401.15884.
# verdict='incorrect' 시 frontend 는 답변 영역을 비활성하고 부서 안내 메시지만 노출.
CRAGVerdict = Literal["correct", "ambiguous", "incorrect"]


class SearchResponse(BaseModel):
    results: list[SearchResultItem]
    total: int
    query: str
    crag_verdict: CRAGVerdict = "correct"
    crag_top_score: float = 0.0
    crag_rationale: str = ""
