"""협업 시나리오 관리 Pydantic 스키마.

backend/routers/admin_scenarios.py + backend/routers/scenarios.py 와 매핑.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ───────────────────────────────────────────────────────────────
# 공용 모델
# ───────────────────────────────────────────────────────────────

class ScenarioItem(BaseModel):
    scenario_id: str
    is_system_default: bool = False
    trigger_keywords: list[str] = Field(default_factory=list)
    situation: str = ""
    requesting_dept: str = ""
    my_actions: list[str] = Field(default_factory=list)
    hand_off_to: str = ""
    hand_off_items: list[str] = Field(default_factory=list)
    deadline_info: str = ""
    related_sop_id: str = ""
    tips: list[str] = Field(default_factory=list)
    priority: int = 100
    scope_division: str = ""
    lang: str = "ko"
    created_by: str = ""
    updated_by: str = ""
    created_at: str = ""
    updated_at: str = ""
    is_active: bool = True


class ScenarioListResponse(BaseModel):
    total: int
    items: list[ScenarioItem]


class ScenarioHistoryEntry(BaseModel):
    id: int
    scenario_id: str
    action: str
    changed_by: str = ""
    changed_at: str = ""
    before: dict[str, Any] = Field(default_factory=dict)
    after: dict[str, Any] = Field(default_factory=dict)


class ScenarioHistoryResponse(BaseModel):
    scenario_id: str
    total: int
    history: list[ScenarioHistoryEntry]


# ───────────────────────────────────────────────────────────────
# CRUD 요청
# ───────────────────────────────────────────────────────────────

class ScenarioCreateRequest(BaseModel):
    scenario_id: str = Field(min_length=1, max_length=64)
    trigger_keywords: list[str] = Field(default_factory=list)
    situation: str = ""
    requesting_dept: str = ""
    my_actions: list[str] = Field(default_factory=list)
    hand_off_to: str = ""
    hand_off_items: list[str] = Field(default_factory=list)
    deadline_info: str = ""
    related_sop_id: str = ""
    tips: list[str] = Field(default_factory=list)
    priority: int = 100
    scope_division: str = ""
    lang: str = "ko"


class ScenarioUpdateRequest(BaseModel):
    trigger_keywords: list[str] | None = None
    situation: str | None = None
    requesting_dept: str | None = None
    my_actions: list[str] | None = None
    hand_off_to: str | None = None
    hand_off_items: list[str] | None = None
    deadline_info: str | None = None
    related_sop_id: str | None = None
    tips: list[str] | None = None
    priority: int | None = None
    scope_division: str | None = None
    lang: str | None = None
    is_active: bool | None = None


# ───────────────────────────────────────────────────────────────
# Phase 3 — 즐겨찾기 / 통계
# ───────────────────────────────────────────────────────────────

class FavoriteRequest(BaseModel):
    note: str = ""


class FavoriteItem(BaseModel):
    scenario_id: str
    note: str = ""
    created_at: str = ""
    situation: str = ""
    requesting_dept: str = ""
    deadline_info: str = ""
    is_active: bool = True


class FavoriteListResponse(BaseModel):
    total: int
    items: list[FavoriteItem]


class UsageRow(BaseModel):
    scenario_id: str
    hits: int
    situation: str = ""
    requesting_dept: str = ""


class ZeroMatchRow(BaseModel):
    scenario_id: str
    situation: str = ""
    requesting_dept: str = ""


class UsageStatsResponse(BaseModel):
    days: int
    by_scenario: list[UsageRow]
    zero_match: list[ZeroMatchRow]
