"""공통 Pydantic 스키마."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str  # "ok" | "degraded" | "error"
    llm_connected: bool
    # ADR-0008: ChromaDB 제거, Supabase pgvector 일원화
    pgvector_connected: bool
    pgvector_doc_count: int
    models_loaded: list[str] = []


class ErrorResponse(BaseModel):
    detail: str
    code: str | None = None


class ModelInfo(BaseModel):
    id: str
    display: str
    size_gb: float = 0.0
    lang: str = ""
    vision: bool = False
    speed: str = ""
    quality: str = ""
    best_for: list[str] = []


class ModelListResponse(BaseModel):
    models: list[str]
    total: int


class AvailableModelsResponse(BaseModel):
    models: list[ModelInfo]
    total: int


class AutoSelectResponse(BaseModel):
    model: str
    feature: str
