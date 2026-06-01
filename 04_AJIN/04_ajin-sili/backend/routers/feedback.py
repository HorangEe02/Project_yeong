"""Feedback API backed by server-side storage.

프론트의 Firebase RTDB 직접 write를 제거하고, AJIN JWT 인증 컨텍스트를
유지한 채 서버가 feedback_events 테이블에 기록한다.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.dependencies import get_current_user
from backend.services.feedback_events import record_feedback_event

router = APIRouter(prefix="/feedback", tags=["feedback"])


class FeedbackIn(BaseModel):
    """Feedback request payload."""

    message_id: str = Field(min_length=1, max_length=120)
    rating: str = Field(pattern="^(thumbs_up|thumbs_down)$")


class FeedbackOut(BaseModel):
    """Feedback creation response."""

    ok: bool
    event_id: str


def _employee_id_of(user) -> str:
    """Return a stable employee id from an authenticated context.

    Args:
        user: Authenticated AJIN user context.

    Returns:
        str: Employee id-like identifier for feedback attribution.
    """

    return str(
        getattr(user, "employee_id", "")
        or getattr(user, "user_id", "")
        or getattr(user, "username", "")
        or "anonymous"
    )


@router.post("", response_model=FeedbackOut)
async def create_feedback(payload: FeedbackIn, user=Depends(get_current_user)):
    """Persist chat/message feedback through the backend.

    Args:
        payload: Feedback request body.
        user: Authenticated user.

    Returns:
        FeedbackOut: Stored feedback event id.

    Raises:
        HTTPException: 400 when validation fails at the persistence layer.
    """
    try:
        event_id = record_feedback_event(
            message_id=payload.message_id,
            rating=payload.rating,
            employee_id=_employee_id_of(user),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "event_id": event_id}
