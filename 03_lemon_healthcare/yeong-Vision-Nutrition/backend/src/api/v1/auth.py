"""Auth API — register / login / refresh.

Reference:
    /Users/yeong/.claude/plans/lemon-track-b/phase-05-api-integration.md Step 11
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select

from src.api.deps import (
    SessionDep,
    SettingsDep,
    get_audit_service,
    get_consent_service,
)
from src.auth.jwt import (
    InvalidTokenError,
    decode_token,
    encode_access,
    encode_refresh,
)
from src.auth.password import hash_password, verify_password
from src.config import Settings
from src.models.db.user import User, UserProfile
from src.models.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    TokenResponse,
    UserRegisterRequest,
)
from src.services.audit_service import AuditService
from src.services.consent_service import ConsentService

router = APIRouter(tags=["auth"])


def _client_ip(request: Request) -> str | None:
    if request.client is None:
        return None
    return request.client.host


def _user_agent(request: Request) -> str | None:
    return request.headers.get("user-agent")


def _issue_tokens(user_id: uuid.UUID, settings: Settings) -> TokenResponse:
    access, _ = encode_access(str(user_id), settings)
    refresh_token, _ = encode_refresh(str(user_id), settings)
    return TokenResponse(
        access_token=access,
        refresh_token=refresh_token,
        expires_in_seconds=settings.access_token_ttl_minutes * 60,
    )


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="회원가입 + 동의 + 토큰 발급",
)
async def register(
    body: UserRegisterRequest,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    consent_service: Annotated[ConsentService, Depends(get_consent_service)],
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
) -> TokenResponse:
    """이메일·비밀번호 + 프로필 + 동의를 한 번에 받아 ``User`` 생성."""
    existing = await session.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    accepted_types = {c.consent_type for c in body.consents if c.accepted}
    required: set[str] = {"service_terms", "general_profile"}
    if body.profile.chronic_diseases:
        required.add("chronic_disease")
    if body.profile.medications:
        required.add("medications")
    missing = required - accepted_types
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "consent_required", "missing": sorted(missing)},
        )

    user = User(
        id=uuid.uuid4(),
        email=body.email,
        password_hash=hash_password(body.password),
        created_at=datetime.now(UTC),
    )
    user.profile = UserProfile(
        user_id=user.id,
        age=body.profile.age,
        sex=body.profile.sex,
        height_cm=body.profile.height_cm,
        weight_kg=body.profile.weight_kg,
        is_pregnant=body.profile.is_pregnant,
        is_lactating=body.profile.is_lactating,
        is_smoker=body.profile.is_smoker,
        chronic_diseases=list(body.profile.chronic_diseases),
        medications=list(body.profile.medications),
        updated_at=datetime.now(UTC),
    )
    session.add(user)
    await session.flush()  # user.id 가 cascade insert 에 보이도록

    for c in body.consents:
        if c.accepted:
            await consent_service.accept(user.id, c.consent_type)

    await audit_service.log(
        actor_user_id=user.id,
        action="auth.register",
        resource_type="user",
        resource_id=str(user.id),
        ip_address=_client_ip(request),
        user_agent=_user_agent(request),
    )
    await session.commit()
    return _issue_tokens(user.id, settings)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="로그인 → 토큰 발급",
)
async def login(
    body: LoginRequest,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
) -> TokenResponse:
    """이메일 + 비밀번호 검증 → access/refresh 토큰 반환."""
    result = await session.execute(
        select(User).where(User.email == body.email, User.deleted_at.is_(None))
    )
    user = result.scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        await audit_service.log(
            actor_user_id=None,
            action="auth.login.failed",
            resource_type="user",
            ip_address=_client_ip(request),
            user_agent=_user_agent(request),
            success=False,
            error_code="invalid_credentials",
        )
        await session.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    await audit_service.log(
        actor_user_id=user.id,
        action="auth.login.success",
        resource_type="user",
        resource_id=str(user.id),
        ip_address=_client_ip(request),
        user_agent=_user_agent(request),
    )
    await session.commit()
    return _issue_tokens(user.id, settings)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="refresh 토큰으로 새 access 발급",
)
async def refresh(body: RefreshRequest, settings: SettingsDep) -> TokenResponse:
    """``refresh_token`` 검증 → 새 access + refresh 발급."""
    try:
        payload = decode_token(body.refresh_token, settings)
    except InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    if payload.typ != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token required"
        )
    try:
        user_id = uuid.UUID(payload.sub)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user id"
        ) from exc
    return _issue_tokens(user_id, settings)
