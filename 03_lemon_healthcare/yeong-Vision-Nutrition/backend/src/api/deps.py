"""FastAPI 의존성 주입.

Reference:
    /Users/yeong/.claude/plans/lemon-track-b/phase-05-api-integration.md Step 8
"""

from __future__ import annotations

import time
import uuid
from typing import Annotated

import redis.asyncio as redis_async
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.jwt import InvalidTokenError, decode_token
from src.cache.ocr_cache import OCRCache
from src.config import Settings, get_settings
from src.db.session import get_session
from src.llm.ollama import OllamaAdapter
from src.models.db.user import User
from src.ocr.base import OCRAdapter
from src.ocr.google_vision import GoogleVisionOCR
from src.ocr.pipeline import OCRPipeline
from src.services.audit_service import AuditService
from src.services.consent_service import ConsentService
from src.services.supplement_service import SupplementService

SettingsDep = Annotated[Settings, Depends(get_settings)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_ocr_pipeline(settings: SettingsDep) -> OCRPipeline:
    """주력 OCR 어댑터 + Redis 캐시로 파이프라인 구성.

    ``settings.ocr_provider`` 분기:
        - ``"paddleocr"`` (default): host-local PaddleOCR, 외부 자격 증명 X
        - ``"google_vision"``: cloud Google Vision, ``GOOGLE_APPLICATION_CREDENTIALS`` 필요

    PaddleOCRAdapter 는 lazy import 로 paddleocr 미설치 환경에서도 google_vision
    경로가 동작하도록 설계.
    """
    primary: OCRAdapter
    if settings.ocr_provider == "paddleocr":
        from src.ocr.paddleocr_adapter import PaddleOCRAdapter

        primary = PaddleOCRAdapter(lang=settings.paddleocr_lang)
    else:
        primary = GoogleVisionOCR()
    redis_client: redis_async.Redis[bytes] = redis_async.from_url(
        settings.redis_url, decode_responses=False
    )
    ttl = max(settings.image_retention_history_days * 86400, 3600)
    cache = OCRCache(redis_client, ttl_seconds=ttl)
    return OCRPipeline(primary=primary, cache=cache)


def get_primary_llm(settings: SettingsDep) -> OllamaAdapter:
    """Ollama 로컬 LLM 어댑터."""
    return OllamaAdapter(model=settings.ollama_model, host=settings.ollama_base_url)


def get_consent_service(session: SessionDep) -> ConsentService:
    return ConsentService(session)


def get_audit_service(session: SessionDep) -> AuditService:
    return AuditService(session)


def get_supplement_service(
    session: SessionDep,
    ocr: Annotated[OCRPipeline, Depends(get_ocr_pipeline)],
    llm: Annotated[OllamaAdapter, Depends(get_primary_llm)],
    consent: Annotated[ConsentService, Depends(get_consent_service)],
    audit: Annotated[AuditService, Depends(get_audit_service)],
) -> SupplementService:
    return SupplementService(ocr, llm, session, consent, audit)


async def get_current_user(
    session: SessionDep,
    settings: SettingsDep,
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    """``Authorization: Bearer <jwt>`` 헤더 → ``User`` ORM 인스턴스.

    Raises:
        HTTPException 401: 토큰 누락 / 디코드 실패 / 만료 / refresh 사용 / soft-deleted.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer token required"
        )
    try:
        payload = decode_token(authorization[7:], settings)
    except InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    if payload.typ != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Access token required"
        )
    try:
        user_id = uuid.UUID(payload.sub)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user id"
        ) from exc

    result = await session.execute(
        select(User).where(User.id == user_id, User.deleted_at.is_(None))
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


async def check_register_rate_limit(
    settings: SettingsDep,
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    """``/supplements/register`` per-user-per-minute rate limit.

    Redis ``INCR + EXPIRE`` 기반 fixed-window.
    """
    limit = settings.rate_limit_register_per_minute
    minute_bucket = int(time.time() // 60)
    key = f"ratelimit:supplement_register:{user.id}:{minute_bucket}"
    redis_client: redis_async.Redis[bytes] = redis_async.from_url(
        settings.redis_url, decode_responses=False
    )
    try:
        count = await redis_client.incr(key)
        if count == 1:
            await redis_client.expire(key, 60)
    finally:
        await redis_client.aclose()  # type: ignore[attr-defined]

    if count > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded ({limit} per minute).",
        )
