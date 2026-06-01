"""inspection_logs ETL 스키마 (v4.3 Phase 1).

CSV/XLSX 업로드 결과 + PWA 실시간 제출 요청·응답 모델.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════
# 업로드 결과
# ═══════════════════════════════════════════════════════════


class IngestErrorRow(BaseModel):
    row_index: int = Field(..., description="CSV 1-based 행 번호 (헤더 제외)")
    error_code: str
    error_msg: str
    raw_payload: dict = Field(default_factory=dict)


class IngestResult(BaseModel):
    rows_total: int = 0
    rows_inserted: int = 0
    rows_updated: int = 0
    rows_skipped: int = 0
    rows_error: int = 0
    dry_run: bool = False
    source: str = "csv_upload"
    started_at: str
    finished_at: str
    error_payload: list[IngestErrorRow] = Field(default_factory=list)
    ingest_log_id: Optional[int] = None


# ═══════════════════════════════════════════════════════════
# PWA 실시간 제출
# ═══════════════════════════════════════════════════════════


class InspectionResultItem(BaseModel):
    item_no: int = Field(..., ge=1)
    passed: bool
    score: Optional[int] = Field(None, ge=0, le=100)
    comment: str = ""


class InspectionSubmitRequest(BaseModel):
    equipment_id: str = Field(..., min_length=1, max_length=30)
    template_id: int = Field(..., ge=1)
    inspection_date: Optional[str] = Field(None, description="ISO 8601. 생략 시 서버 today")
    results: list[InspectionResultItem] = Field(default_factory=list)
    overall_status: Literal["PASS", "WARN", "FAIL"] = "PASS"
    note: str = ""
    client_uuid: Optional[str] = Field(None, description="PWA offline queue 중복 방지 식별자")


class InspectionSubmitResponse(BaseModel):
    inspection_log_id: int
    deduplicated: bool = False
    source: str = "tablet_pwa"


# ═══════════════════════════════════════════════════════════
# ingest_log 조회
# ═══════════════════════════════════════════════════════════


class IngestLogEntry(BaseModel):
    id: int
    started_at: str
    finished_at: Optional[str]
    source_label: str
    file_name: str
    rows_total: int
    rows_inserted: int
    rows_updated: int
    rows_skipped: int
    rows_error: int
    actor: str


class IngestLogResponse(BaseModel):
    items: list[IngestLogEntry]
    total: int
