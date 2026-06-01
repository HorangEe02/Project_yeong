"""D 컴플라이언스 알람 schema (v4.2).

dashboard.tsx 의 `MockAlarm` 형상과 호환되도록 필드 명명.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


AlarmSeverity = Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
AlarmSource = Literal["law_change", "dday", "impact_score", "unresolved", "trend"]


class ComplianceAlarm(BaseModel):
    """대시보드 알람 카드에 표시되는 D 모듈 알람 단위."""

    id: str = Field(..., description="안정 ID — 'D-{source}-{regulation_id}'")
    severity: AlarmSeverity
    title: str = Field(..., description="알람 카드 제목 (한 줄)")
    detail: str = Field(..., description="설명 — 영향 라인·필요 조치 등")
    module: Literal["D"] = "D"
    source: AlarmSource
    regulation_id: Optional[str] = Field(None, description="원본 regulation_changes.id 추적")
    effective_date: Optional[str] = Field(None, description="ISO 8601, D-day 알람일 때만")
    timestamp: str = Field(..., description="ISO 8601 알람 발생 시각")
    acknowledged: bool = False


class ComplianceAlarmsResponse(BaseModel):
    items: list[ComplianceAlarm]
    total: int


class ComplianceAlarmAckResponse(BaseModel):
    alarm_id: str
    acknowledged_at: str
    actor: str
