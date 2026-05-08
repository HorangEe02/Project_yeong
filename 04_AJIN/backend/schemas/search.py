"""검색 관련 Pydantic 스키마."""

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str
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
    metadata: dict = {}


class SearchResponse(BaseModel):
    results: list[SearchResultItem]
    total: int
    query: str
