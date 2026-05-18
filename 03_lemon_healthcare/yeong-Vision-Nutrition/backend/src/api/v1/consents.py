"""Consents API — list / accept / revoke.

Reference:
    /Users/yeong/.claude/plans/lemon-track-b/phase-05-api-integration.md Step 11
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from src.api.deps import (
    SessionDep,
    get_audit_service,
    get_consent_service,
    get_current_user,
)
from src.models.db.consent import ConsentRecord
from src.models.db.user import User
from src.services.audit_service import AuditService
from src.services.consent_service import ConsentService

router = APIRouter(tags=["consents"])


class ConsentRow(BaseModel):
    """현재 사용자의 단일 동의 row 응답."""

    model_config = ConfigDict(frozen=True)

    consent_type: str
    accepted_at: str
    revoked_at: str | None


class ConsentList(BaseModel):
    """전체 동의 현황."""

    model_config = ConfigDict(frozen=True)

    consents: list[ConsentRow]


class ConsentResult(BaseModel):
    """단일 동의 작업의 결과 응답."""

    model_config = ConfigDict(frozen=True)

    consent_type: str
    status: str
    revoked_count: int | None = None


@router.get("", response_model=ConsentList, summary="내 동의 목록")
async def list_consents(
    session: SessionDep,
    user: Annotated[User, Depends(get_current_user)],
) -> ConsentList:
    result = await session.execute(select(ConsentRecord).where(ConsentRecord.user_id == user.id))
    records = list(result.scalars().all())
    return ConsentList(
        consents=[
            ConsentRow(
                consent_type=r.consent_type,
                accepted_at=r.accepted_at.isoformat(),
                revoked_at=r.revoked_at.isoformat() if r.revoked_at else None,
            )
            for r in records
        ]
    )


@router.post(
    "/{consent_type}",
    response_model=ConsentResult,
    status_code=status.HTTP_201_CREATED,
    summary="동의 수락",
)
async def accept_consent(
    consent_type: str,
    request: Request,
    session: SessionDep,
    user: Annotated[User, Depends(get_current_user)],
    consent_service: Annotated[ConsentService, Depends(get_consent_service)],
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
) -> ConsentResult:
    record = await consent_service.accept(user.id, consent_type)
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    await audit_service.log(
        actor_user_id=user.id,
        action="consent.accept",
        resource_type="consent",
        resource_id=str(record.id),
        ip_address=ip,
        user_agent=ua,
    )
    await session.commit()
    return ConsentResult(consent_type=consent_type, status="accepted")


@router.delete(
    "/{consent_type}",
    response_model=ConsentResult,
    summary="동의 철회",
)
async def revoke_consent(
    consent_type: str,
    request: Request,
    session: SessionDep,
    user: Annotated[User, Depends(get_current_user)],
    consent_service: Annotated[ConsentService, Depends(get_consent_service)],
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
) -> ConsentResult:
    count = await consent_service.revoke(user.id, consent_type)
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    await audit_service.log(
        actor_user_id=user.id,
        action="consent.revoke",
        resource_type="consent",
        ip_address=ip,
        user_agent=ua,
    )
    await session.commit()
    return ConsentResult(consent_type=consent_type, status="revoked", revoked_count=count)
