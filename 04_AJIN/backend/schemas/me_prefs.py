"""사용자 prefs schema (v4.5)."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class MobileTabPrefs(BaseModel):
    """BottomTabBar 동적 슬롯 4·5 사용자 설정.

    슬롯 1·2·3 (DRAFT / CHAT / HOME) 은 항상 고정 — 본 schema 미포함.
    """
    override: bool = Field(False, description="True 시 custom_slots 사용. False 면 페르소나 자동 추천")
    custom_slots: list[str] = Field(
        default_factory=lambda: ["compliance", "equipment"],
        description="동적 4·5 슬롯의 module slug 2개 (e.g. ['compliance', 'equipment'])",
        min_length=0,
        max_length=2,
    )
    updated_at: Optional[str] = None
