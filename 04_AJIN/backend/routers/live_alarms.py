"""Live alarm API backed by Postgres/SQLite.

Firebase RTDB 알람 피드를 대체하는 서버 API다. 프론트는 이 API를 polling
또는 SSE의 상위 추상화로 사용할 수 있고, 데이터의 source of truth는
`live_alarms` 테이블이다.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.routers.equipment import require_equipment_access
from backend.services.live_events import acknowledge_alarm, list_recent_alarms

router = APIRouter(prefix="/live-alarms", tags=["live-alarms"])


class LiveAlarmItem(BaseModel):
    """A live alarm item returned to frontend clients."""

    id: str
    domain: str
    severity: str
    message: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    acknowledged_at: str | None = None


class LiveAlarmListResponse(BaseModel):
    """Recent live alarm list response."""

    alarms: list[LiveAlarmItem]
    total: int


class AckResponse(BaseModel):
    """Live alarm acknowledgement response."""

    ok: bool
    alarm_id: str


@router.get("/recent", response_model=LiveAlarmListResponse)
async def get_recent_live_alarms(
    domain: str | None = None,
    limit: int = 50,
    user=Depends(require_equipment_access(1)),
):
    """Return recent live alarms.

    Args:
        domain: Optional alarm domain filter.
        limit: Maximum rows to return.
        user: Current authenticated user.

    Returns:
        LiveAlarmListResponse: Recent alarm rows.
    """
    del user
    alarms = list_recent_alarms(domain=domain, limit=limit)
    return {"alarms": alarms, "total": len(alarms)}


@router.post("/{alarm_id}/ack", response_model=AckResponse)
async def ack_live_alarm(alarm_id: str, user=Depends(require_equipment_access(3))):
    """Mark one live alarm as acknowledged.

    Args:
        alarm_id: Live alarm id.
        user: Current authenticated user.

    Returns:
        AckResponse: Ack result.

    Raises:
        HTTPException: 404 when the alarm does not exist.
    """
    del user
    if not acknowledge_alarm(alarm_id):
        raise HTTPException(status_code=404, detail="alarm_not_found")
    return {"ok": True, "alarm_id": alarm_id}
